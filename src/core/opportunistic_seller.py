"""
Opportunistic Seller Module (Phase 3)

시장 과열 시 보유 암호화폐를 단계적으로 익절하는 모듈.
OpportunisticBuyer(하락장 매집)와 대칭 구조 — 상승장 분배를 담당한다.

매도 레벨 (모든 조건은 실데이터 기반):
| 레벨     | 조건 (AND)                                   | 매도 비율 (보유분 대비) |
|----------|----------------------------------------------|-------------------------|
| MINOR    | 30일 저점 대비 +25% AND RSI > 70             | 5%                      |
| MODERATE | 30일 저점 대비 +40% AND RSI > 75             | 10%                     |
| MAJOR    | 30일 저점 대비 +60% AND 탐욕지수 > 75        | 15%                     |
| EXTREME  | R(가격/200주MA) >= 2.8 AND 탐욕지수 > 85     | 20%                     |

원칙:
- 탐욕지수/200주 MA를 실데이터로 얻지 못하면 해당 조건이 필요한 레벨은 트리거되지 않는다
  (추정치 생성 금지)
- 재매도 조건: 최소 4시간 간격 + 72시간 내에는 직전 매도가 대비 +5% 추가 상승 필요
- 매도 대금은 KRW로 적립되어 다음 하락장에서 OpportunisticBuyer의 매수 재원이 된다
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

import pandas as pd
from loguru import logger

from ..utils.constants import MIN_ORDER_AMOUNTS_KRW


class SellLevel(Enum):
    """매도 기회 수준"""
    NONE = "none"
    MINOR = "minor"        # +25% 상승 & 과매수
    MODERATE = "moderate"  # +40% 상승 & 강한 과매수
    MAJOR = "major"        # +60% 상승 & 탐욕
    EXTREME = "extreme"    # 200주 MA 대비 극단적 고평가 & 극도의 탐욕


@dataclass
class SellOpportunity:
    """매도 기회 정보"""
    asset: str
    current_price: float
    low_30d: float
    rally_from_30d_low: float          # 30일 저점 대비 상승률
    rsi: float
    fear_greed_index: Optional[float]  # 실데이터 없으면 None
    price_to_ma200w_ratio: Optional[float]  # R값 (BTC만, 없으면 None)
    sell_level: SellLevel
    recommended_sell_ratio: float      # 보유분 대비 매도 비율
    timestamp: datetime = field(default_factory=datetime.now)


class OpportunisticSeller:
    """
    기회적 매도(단계적 익절) 시스템
    """

    # 레벨별 (저점 대비 상승률, RSI 최소, 탐욕지수 최소, 매도 비율)
    LEVEL_RULES = {
        SellLevel.MINOR: {"rally": 0.25, "rsi_min": 70, "greed_min": None, "sell_ratio": 0.05},
        SellLevel.MODERATE: {"rally": 0.40, "rsi_min": 75, "greed_min": None, "sell_ratio": 0.10},
        SellLevel.MAJOR: {"rally": 0.60, "rsi_min": None, "greed_min": 75, "sell_ratio": 0.15},
    }
    EXTREME_R_MIN = 2.8
    EXTREME_GREED_MIN = 85
    EXTREME_SELL_RATIO = 0.20

    def __init__(
        self,
        coinone_client,
        db_manager,
        order_manager=None,
        fear_greed_provider=None,
        market_data_provider=None,
    ):
        """
        Args:
            coinone_client: 코인원 API 클라이언트
            db_manager: 데이터베이스 매니저
            order_manager: 주문 관리자
            fear_greed_provider: 실제 공포탐욕지수 제공자
            market_data_provider: 시장 데이터 제공자 (200주 MA — EXTREME 판정용)
        """
        self.coinone_client = coinone_client
        self.db_manager = db_manager
        self.order_manager = order_manager
        self.fear_greed_provider = fear_greed_provider
        self.market_data_provider = market_data_provider

        self.min_sell_interval_hours = 4
        self.resell_rise_threshold = 0.05  # 72시간 내 재매도: 직전 매도가 대비 +5% 필요
        self.recent_sells: Dict[str, datetime] = {}
        self.last_sell_prices: Dict[str, float] = {}
        self._load_recent_sells_from_db()

        logger.info("OpportunisticSeller 초기화 완료")

    # ------------------------------------------------------------------
    # 이력 관리 (DB 영속화)
    # ------------------------------------------------------------------

    def _load_recent_sells_from_db(self, days: int = 7):
        """DB에서 최근 기회적 매도 이력 복원"""
        try:
            records = self.db_manager.get_recent_opportunistic_sells(days=days)
            for record in records:
                asset = record.get("asset")
                if not asset:
                    continue
                sell_time = record.get("timestamp")
                if isinstance(sell_time, str):
                    sell_time = datetime.fromisoformat(sell_time)
                price = record.get("price")

                if asset not in self.recent_sells or sell_time > self.recent_sells[asset]:
                    self.recent_sells[asset] = sell_time
                    if price:
                        self.last_sell_prices[asset] = float(price)

            if self.recent_sells:
                logger.info(f"최근 기회적 매도 이력 {len(self.recent_sells)}건 복원")
        except Exception as e:
            logger.warning(f"기회적 매도 이력 복원 실패 (신규 이력으로 시작): {e}")

    def _can_resell(self, asset: str, current_price: float) -> bool:
        """재매도 가능 여부 (시간 간격 + 추가 상승 조건)"""
        last_sell_time = self.recent_sells.get(asset)
        if last_sell_time:
            if datetime.now() - last_sell_time < timedelta(hours=self.min_sell_interval_hours):
                logger.info(f"⏭️ {asset}: 최근 {self.min_sell_interval_hours}시간 내 매도 이력 있음, 건너뜀")
                return False

            if datetime.now() - last_sell_time < timedelta(hours=72):
                last_price = self.last_sell_prices.get(asset)
                if last_price and last_price > 0:
                    required = last_price * (1 + self.resell_rise_threshold)
                    if current_price < required:
                        logger.info(f"⏭️ {asset}: 직전 매도가({last_price:,.0f}) 대비 추가 상승 부족 "
                                    f"(현재 {current_price:,.0f} < 기준 {required:,.0f}), 건너뜀")
                        return False
        return True

    # ------------------------------------------------------------------
    # 지표 (실데이터만)
    # ------------------------------------------------------------------

    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """RSI 계산 (실가격 데이터 기반)"""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return float(rsi.iloc[-1]) if not rsi.empty else 50.0
        except Exception as e:
            logger.error(f"RSI 계산 실패: {e}")
            return 50.0

    def _get_fear_greed(self) -> Optional[float]:
        """실제 공포탐욕지수 (없으면 None — 탐욕 조건 미적용)"""
        try:
            if self.fear_greed_provider:
                value = self.fear_greed_provider.get_index()
                return float(value) if value is not None else None
            return None
        except Exception as e:
            logger.warning(f"공포탐욕지수 조회 실패: {e}")
            return None

    def _get_btc_ma_ratio(self, btc_price: Optional[float]) -> Optional[float]:
        """R = BTC 현재가 / 200주 MA (실데이터 없으면 None — EXTREME 미적용)"""
        try:
            if self.market_data_provider and btc_price and btc_price > 0:
                ma_200w, _ = self.market_data_provider.get_btc_200w_ma()
                if ma_200w and ma_200w > 0:
                    return btc_price / ma_200w
            return None
        except Exception as e:
            logger.warning(f"200주 MA 비율 계산 실패 (EXTREME 판정 미적용): {e}")
            return None

    # ------------------------------------------------------------------
    # 기회 식별
    # ------------------------------------------------------------------

    def _determine_sell_level(
        self,
        rally: float,
        rsi: float,
        fear_greed: Optional[float],
        ma_ratio: Optional[float],
    ) -> SellLevel:
        """매도 레벨 판단 (높은 레벨부터 검사)"""
        # EXTREME: R + 극도의 탐욕 모두 실데이터로 확인돼야 함
        if (ma_ratio is not None and ma_ratio >= self.EXTREME_R_MIN
                and fear_greed is not None and fear_greed > self.EXTREME_GREED_MIN):
            return SellLevel.EXTREME

        major = self.LEVEL_RULES[SellLevel.MAJOR]
        if rally >= major["rally"] and fear_greed is not None and fear_greed > major["greed_min"]:
            return SellLevel.MAJOR

        moderate = self.LEVEL_RULES[SellLevel.MODERATE]
        if rally >= moderate["rally"] and rsi > moderate["rsi_min"]:
            return SellLevel.MODERATE

        minor = self.LEVEL_RULES[SellLevel.MINOR]
        if rally >= minor["rally"] and rsi > minor["rsi_min"]:
            return SellLevel.MINOR

        return SellLevel.NONE

    def _sell_ratio_for_level(self, level: SellLevel) -> float:
        if level == SellLevel.EXTREME:
            return self.EXTREME_SELL_RATIO
        if level in self.LEVEL_RULES:
            return self.LEVEL_RULES[level]["sell_ratio"]
        return 0.0

    def identify_sell_opportunities(
        self, assets: List[str]
    ) -> Tuple[List[SellOpportunity], Dict[str, str]]:
        """
        매도(익절) 기회 식별

        Returns:
            (매도 기회 목록, 기회가 없는 자산의 이유)
        """
        opportunities = []
        no_opportunity_reasons = {}

        fear_greed = self._get_fear_greed()

        for asset in assets:
            if asset == "KRW":
                continue
            try:
                price_data_30d = self.db_manager.get_market_data(asset, days=30)
                if price_data_30d.empty:
                    no_opportunity_reasons[asset] = "가격 데이터 없음"
                    continue

                current_price = float(price_data_30d['Close'].iloc[-1])
                low_30d = float(price_data_30d['Close'].min())
                rally = (current_price / low_30d) - 1 if low_30d > 0 else 0.0
                rsi = self.calculate_rsi(price_data_30d['Close'])

                # R값은 BTC 가격 기준 (시장 전체 과열 판정)
                btc_price = current_price if asset == "BTC" else None
                if asset != "BTC":
                    btc_data = self.db_manager.get_market_data("BTC", days=7)
                    if not btc_data.empty:
                        btc_price = float(btc_data['Close'].iloc[-1])
                ma_ratio = self._get_btc_ma_ratio(btc_price)

                level = self._determine_sell_level(rally, rsi, fear_greed, ma_ratio)

                if level != SellLevel.NONE:
                    opportunities.append(SellOpportunity(
                        asset=asset,
                        current_price=current_price,
                        low_30d=low_30d,
                        rally_from_30d_low=rally,
                        rsi=rsi,
                        fear_greed_index=fear_greed,
                        price_to_ma200w_ratio=ma_ratio,
                        sell_level=level,
                        recommended_sell_ratio=self._sell_ratio_for_level(level),
                    ))
                else:
                    reasons = []
                    if rally < 0.25:
                        reasons.append(f"저점 대비 상승률 부족 ({rally:.1%})")
                    if rsi <= 70:
                        reasons.append(f"RSI 과매수 아님 ({rsi:.1f})")
                    if fear_greed is None:
                        reasons.append("탐욕지수 데이터 없음")
                    elif fear_greed <= 75:
                        reasons.append(f"탐욕지수 낮음 ({fear_greed:.0f})")
                    no_opportunity_reasons[asset] = ", ".join(reasons) or "조건 미충족"

            except Exception as e:
                logger.error(f"{asset} 매도 기회 분석 실패: {e}")
                no_opportunity_reasons[asset] = f"분석 오류: {str(e)}"

        # 강한 레벨부터 실행
        level_priority = {
            SellLevel.EXTREME: 0, SellLevel.MAJOR: 1,
            SellLevel.MODERATE: 2, SellLevel.MINOR: 3
        }
        opportunities.sort(key=lambda o: level_priority.get(o.sell_level, 9))

        return opportunities, no_opportunity_reasons

    # ------------------------------------------------------------------
    # 실행
    # ------------------------------------------------------------------

    def execute_opportunistic_sells(
        self,
        opportunities: List[SellOpportunity],
        holdings: Dict[str, Dict],
        max_total_sell_krw: Optional[float] = None,
    ) -> Dict:
        """
        기회적 매도 실행

        Args:
            opportunities: 매도 기회 목록
            holdings: 자산별 보유 정보 {"BTC": {"amount": 수량, "value_krw": 평가액}, ...}
            max_total_sell_krw: 총 매도 한도 (AllocationArbiter의 밴드 한도 등)

        Returns:
            실행 결과
        """
        results = {
            "executed_orders": [],
            "failed_orders": [],
            "total_sold_krw": 0.0,
        }
        remaining_limit = max_total_sell_krw if max_total_sell_krw is not None else float("inf")

        for opp in opportunities:
            if remaining_limit < 10000:
                logger.info("매도 한도 소진으로 기회적 매도 종료")
                break

            if not self._can_resell(opp.asset, opp.current_price):
                continue

            holding = holdings.get(opp.asset, {})
            held_amount = float(holding.get("amount", 0) or 0)
            if held_amount <= 0:
                continue

            sell_quantity = held_amount * opp.recommended_sell_ratio
            sell_value_krw = sell_quantity * opp.current_price

            # 한도 초과 시 축소
            if sell_value_krw > remaining_limit:
                sell_quantity = remaining_limit / opp.current_price
                sell_value_krw = remaining_limit

            min_amount = MIN_ORDER_AMOUNTS_KRW.get(opp.asset, 5000)
            if sell_value_krw < min_amount:
                logger.info(f"⚠️ {opp.asset}: 매도 금액 {sell_value_krw:,.0f} KRW가 최소 금액 미달")
                continue

            try:
                if self.order_manager:
                    order_obj = self.order_manager.submit_market_order(
                        currency=opp.asset, side="sell", amount=sell_quantity
                    )
                    success = bool(order_obj) and order_obj.status.value != "FAILED"
                    order_id = order_obj.order_id if order_obj else None
                    error = (order_obj.error_message
                             if order_obj and order_obj.status.value == "FAILED" else None)
                else:
                    order_result = self.coinone_client.place_limit_order(
                        currency=opp.asset, side="sell",
                        price=opp.current_price, amount=sell_quantity,
                        order_type="limit"
                    )
                    success = bool(order_result.get("success"))
                    order_id = order_result.get("order_id")
                    error = order_result.get("error")

                if success:
                    results["executed_orders"].append({
                        "asset": opp.asset,
                        "quantity": sell_quantity,
                        "value_krw": sell_value_krw,
                        "price": opp.current_price,
                        "sell_level": opp.sell_level.value,
                        "order_id": order_id,
                    })
                    results["total_sold_krw"] += sell_value_krw
                    remaining_limit -= sell_value_krw

                    self.recent_sells[opp.asset] = datetime.now()
                    self.last_sell_prices[opp.asset] = opp.current_price
                    self._record_sell(opp, sell_quantity, sell_value_krw, order_id)

                    logger.info(f"✅ {opp.asset} 기회적 매도 실행: {sell_value_krw:,.0f} KRW "
                                f"({opp.sell_level.value}, 저점 대비 +{opp.rally_from_30d_low:.1%})")
                else:
                    results["failed_orders"].append({
                        "asset": opp.asset,
                        "value_krw": sell_value_krw,
                        "reason": error or "Unknown error",
                    })
                    logger.error(f"❌ {opp.asset} 매도 실패: {error}")

            except Exception as e:
                logger.error(f"{opp.asset} 매도 실행 중 오류: {e}")
                results["failed_orders"].append({
                    "asset": opp.asset,
                    "value_krw": sell_value_krw,
                    "reason": str(e),
                })

        return results

    def _record_sell(self, opp: SellOpportunity, quantity: float, value_krw: float, order_id):
        """기회적 매도 기록 (DB)"""
        try:
            self.db_manager.save_opportunistic_sell_record({
                "timestamp": datetime.now(),
                "asset": opp.asset,
                "quantity": quantity,
                "amount_krw": value_krw,
                "price": opp.current_price,
                "sell_level": opp.sell_level.value,
                "rally_from_30d_low": opp.rally_from_30d_low,
                "rsi": opp.rsi,
                "fear_greed_index": opp.fear_greed_index,
                "price_to_ma200w_ratio": opp.price_to_ma200w_ratio,
                "order_id": order_id,
                "status": "executed",
            })
        except Exception as e:
            logger.error(f"기회적 매도 기록 실패: {e}")
