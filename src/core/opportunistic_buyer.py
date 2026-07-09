"""
Opportunistic Buyer Module

시장 하락 시 현금 보유분을 활용한 추가 매수 전략 모듈
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd
import numpy as np
from loguru import logger

from ..trading.coinone_client import CoinoneClient
from ..utils.database_manager import DatabaseManager
from ..utils.constants import MIN_ORDER_AMOUNTS_KRW


class OpportunityLevel(Enum):
    """매수 기회 수준"""
    NONE = "none"              # 기회 없음
    MINOR = "minor"            # 소폭 하락 (-5% ~ -10%)
    MODERATE = "moderate"      # 중간 하락 (-10% ~ -20%)
    MAJOR = "major"            # 대폭 하락 (-20% ~ -30%)
    EXTREME = "extreme"        # 극단적 하락 (-30% 이상)


@dataclass
class BuyOpportunity:
    """매수 기회 정보"""
    asset: str
    current_price: float
    avg_price_7d: float
    avg_price_30d: float
    price_drop_7d: float      # 7일 대비 하락률
    price_drop_30d: float     # 30일 대비 하락률
    rsi: float                # RSI 지표
    fear_greed_index: Optional[float]  # 공포탐욕 지수 (실데이터 없으면 None)
    opportunity_level: OpportunityLevel
    recommended_buy_ratio: float  # 현금 대비 매수 추천 비율
    confidence_score: float   # 신뢰도 점수 (0-1)
    timestamp: datetime = field(default_factory=datetime.now)


class OpportunisticBuyer:
    """
    기회적 매수 시스템
    
    시장 하락 시 보유 현금을 활용하여 추가 매수를 실행합니다.
    - RSI, 이동평균선 이탈도 등 기술적 지표 활용
    - 단계적 매수로 리스크 분산
    - 시장 공포 지수 연동
    """
    
    def __init__(
        self,
        coinone_client: CoinoneClient,
        db_manager: DatabaseManager,
        order_manager = None,  # 추가: OrderManager 의존성
        cash_reserve_ratio: float = 0.15,  # 기본 현금 보유 비율
        min_opportunity_threshold: float = 0.05,  # 최소 기회 임계값 (5% 하락)
        max_buy_per_opportunity: float = 0.3,  # 기회당 최대 매수 비율
        fear_greed_provider = None  # 실제 공포탐욕지수 제공자
    ):
        """
        Args:
            coinone_client: 코인원 API 클라이언트
            db_manager: 데이터베이스 매니저
            order_manager: 주문 관리자 (없으면 coinone_client 직접 사용)
            cash_reserve_ratio: 현금 보유 비율
            min_opportunity_threshold: 최소 매수 기회 임계값
            max_buy_per_opportunity: 기회당 최대 매수 비율
            fear_greed_provider: 실제 공포탐욕지수 제공자 (없으면 공포탐욕 조건 미적용)
        """
        self.coinone_client = coinone_client
        self.db_manager = db_manager
        self.order_manager = order_manager
        self.cash_reserve_ratio = cash_reserve_ratio
        self.min_opportunity_threshold = min_opportunity_threshold
        self.max_buy_per_opportunity = max_buy_per_opportunity
        self.fear_greed_provider = fear_greed_provider

        # 매수 기회 레벨별 설정 (drop: N일 고점 대비 하락률)
        self.opportunity_thresholds = {
            OpportunityLevel.MINOR: {"drop": 0.05, "buy_ratio": 0.1},
            OpportunityLevel.MODERATE: {"drop": 0.10, "buy_ratio": 0.2},
            OpportunityLevel.MAJOR: {"drop": 0.20, "buy_ratio": 0.3},
            OpportunityLevel.EXTREME: {"drop": 0.30, "buy_ratio": 0.4}
        }

        # 최근 매수 이력 (중복 매수 방지) - DB에서 복원 (재시작 시에도 유지)
        self.min_buy_interval_hours = 4  # 동일 자산 최소 매수 간격
        self.rebuy_drop_threshold = 0.03  # 재매수 조건: 직전 매수가 대비 추가 -3% 하락
        self.recent_buys: Dict[str, datetime] = {}
        self.last_buy_prices: Dict[str, float] = {}
        self._load_recent_buys_from_db()

        logger.info(f"OpportunisticBuyer 초기화 완료 (현금 보유: {cash_reserve_ratio:.1%})")

    def _load_recent_buys_from_db(self, days: int = 7):
        """DB에서 최근 기회적 매수 이력 복원 (프로세스 재시작 시 중복매수 방지 유지)"""
        try:
            records = self.db_manager.get_recent_opportunistic_buys(days=days)
            for record in records:
                asset = record.get("asset")
                if not asset:
                    continue
                buy_time = record.get("timestamp")
                if isinstance(buy_time, str):
                    buy_time = datetime.fromisoformat(buy_time)
                price = record.get("price")

                # 자산별 가장 최근 매수만 유지
                if asset not in self.recent_buys or buy_time > self.recent_buys[asset]:
                    self.recent_buys[asset] = buy_time
                    if price:
                        self.last_buy_prices[asset] = float(price)

            if self.recent_buys:
                logger.info(f"최근 기회적 매수 이력 {len(self.recent_buys)}건 복원")
        except Exception as e:
            logger.warning(f"기회적 매수 이력 복원 실패 (신규 이력으로 시작): {e}")
    
    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """
        RSI (Relative Strength Index) 계산
        
        Args:
            prices: 가격 시계열 데이터
            period: RSI 계산 기간
            
        Returns:
            RSI 값 (0-100)
        """
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            return rsi.iloc[-1] if not rsi.empty else 50.0
            
        except Exception as e:
            logger.error(f"RSI 계산 실패: {e}")
            return 50.0  # 중립값 반환
    
    def get_fear_greed_index(self) -> Optional[float]:
        """
        실제 공포탐욕 지수 조회 (alternative.me)

        변동성 등으로 "추정한 가짜 지수"를 만들지 않는다.
        조회 불가 시 None을 반환하며, 이 경우 공포탐욕 관련 조건/보너스는 적용되지 않는다.

        Returns:
            공포탐욕 지수 (0-100, 0=극도의 공포, 100=극도의 탐욕) 또는 None
        """
        try:
            if self.fear_greed_provider:
                value = self.fear_greed_provider.get_index()
                return float(value) if value is not None else None
            return None
        except Exception as e:
            logger.error(f"공포탐욕 지수 조회 실패: {e}")
            return None
    
    def identify_opportunities(self, assets: List[str]) -> tuple[List[BuyOpportunity], Dict[str, str]]:
        """
        매수 기회 식별
        
        Args:
            assets: 분석할 자산 목록
            
        Returns:
            튜플: (매수 기회 목록, 기회가 없는 자산의 이유)
        """
        opportunities = []
        no_opportunity_reasons = {}
        
        for asset in assets:
            if asset == "KRW":
                continue
                
            try:
                # 가격 데이터 조회
                price_data_7d = self.db_manager.get_market_data(asset, days=7)
                price_data_30d = self.db_manager.get_market_data(asset, days=30)
                
                if price_data_7d.empty or price_data_30d.empty:
                    no_opportunity_reasons[asset] = "가격 데이터 없음"
                    continue
                
                current_price = price_data_7d['Close'].iloc[-1]
                avg_price_7d = price_data_7d['Close'].mean()
                avg_price_30d = price_data_30d['Close'].mean()

                # 하락률 계산: 기간 내 "고점 대비" 하락률 (평균 대비가 아님 —
                # 평균 대비는 완만한 하락장에서 과도하게 자주 트리거됨)
                high_7d = price_data_7d['Close'].max()
                high_30d = price_data_30d['Close'].max()
                price_drop_7d = (current_price / high_7d) - 1 if high_7d > 0 else 0.0
                price_drop_30d = (current_price / high_30d) - 1 if high_30d > 0 else 0.0
                
                # RSI 계산
                rsi = self.calculate_rsi(price_data_30d['Close'])
                
                # 공포탐욕 지수
                fear_greed = self.get_fear_greed_index()
                
                # 기회 수준 판단
                opportunity_level = self._determine_opportunity_level(
                    price_drop_7d, price_drop_30d, rsi, fear_greed
                )
                
                if opportunity_level != OpportunityLevel.NONE:
                    # 매수 추천 비율 계산
                    buy_ratio = self._calculate_buy_ratio(opportunity_level, rsi, fear_greed)
                    
                    # 신뢰도 점수 계산
                    confidence = self._calculate_confidence_score(
                        price_drop_7d, price_drop_30d, rsi, fear_greed
                    )
                    
                    opportunity = BuyOpportunity(
                        asset=asset,
                        current_price=current_price,
                        avg_price_7d=avg_price_7d,
                        avg_price_30d=avg_price_30d,
                        price_drop_7d=price_drop_7d,
                        price_drop_30d=price_drop_30d,
                        rsi=rsi,
                        fear_greed_index=fear_greed,
                        opportunity_level=opportunity_level,
                        recommended_buy_ratio=buy_ratio,
                        confidence_score=confidence
                    )
                    
                    opportunities.append(opportunity)
                else:
                    # 매수 기회가 없는 이유 분석
                    reasons = []
                    if price_drop_7d > -0.05:  # 7일 고점 대비 5% 이상 하락하지 않음
                        reasons.append(f"7일 고점 대비 하락률 부족 ({price_drop_7d:.1%})")
                    if rsi > 30:  # RSI가 과매도 구간이 아님
                        reasons.append(f"RSI 과매도 아님 ({rsi:.1f})")
                    if fear_greed is None:
                        reasons.append("공포지수 데이터 없음")
                    elif fear_greed > 25:  # 공포 지수가 충분히 낮지 않음
                        reasons.append(f"공포지수 높음 ({fear_greed:.0f})")
                    
                    if not reasons:
                        reasons.append("기타 조건 미충족")
                    
                    no_opportunity_reasons[asset] = ", ".join(reasons)
                    
            except Exception as e:
                logger.error(f"{asset} 기회 분석 실패: {e}")
                no_opportunity_reasons[asset] = f"분석 오류: {str(e)}"
                continue
        
        # 신뢰도 점수 기준 정렬
        opportunities.sort(key=lambda x: x.confidence_score, reverse=True)
        
        return opportunities, no_opportunity_reasons
    
    def _determine_opportunity_level(
        self,
        drop_7d: float,
        drop_30d: float,
        rsi: float,
        fear_greed: Optional[float]
    ) -> OpportunityLevel:
        """
        매수 기회 수준 판단

        Args:
            drop_7d: 7일 고점 대비 하락률
            drop_30d: 30일 고점 대비 하락률
            rsi: RSI 지표
            fear_greed: 공포탐욕 지수 (None이면 실데이터 없음 — 공포 조건 미적용)

        Returns:
            기회 수준
        """
        # 주요 지표 종합 평가
        max_drop = min(drop_7d, drop_30d)  # 더 큰 하락률 사용

        # RSI 과매도 구간 (30 이하)
        rsi_oversold = rsi < 30

        # 극도의 공포 구간 (25 이하) — 실데이터가 있을 때만 판정
        extreme_fear = fear_greed is not None and fear_greed < 25

        # 기회 수준 판단
        if max_drop <= -0.30 and (rsi_oversold or extreme_fear):
            return OpportunityLevel.EXTREME
        elif max_drop <= -0.20 and rsi < 40:
            return OpportunityLevel.MAJOR
        elif max_drop <= -0.10 and rsi < 50:
            return OpportunityLevel.MODERATE
        elif max_drop <= -0.05:
            return OpportunityLevel.MINOR
        else:
            return OpportunityLevel.NONE
    
    def _calculate_buy_ratio(
        self,
        level: OpportunityLevel,
        rsi: float,
        fear_greed: Optional[float]
    ) -> float:
        """
        매수 비율 계산
        
        Args:
            level: 기회 수준
            rsi: RSI 지표
            fear_greed: 공포탐욕 지수
            
        Returns:
            현금 대비 매수 비율
        """
        base_ratio = self.opportunity_thresholds[level]["buy_ratio"]

        # RSI 조정 (과매도일수록 비율 증가)
        rsi_adjustment = max(0, (30 - rsi) / 100)  # RSI 30 이하에서 보너스

        # 공포지수 조정 (공포가 클수록 비율 증가) — 실데이터 없으면 보너스 없음
        fear_adjustment = max(0, (25 - fear_greed) / 100) if fear_greed is not None else 0.0
        
        # 최종 비율 계산 (보너스는 추가로 더함)
        final_ratio = base_ratio + (base_ratio * (rsi_adjustment + fear_adjustment))
        
        # 최대 비율 제한 (EXTREME 레벨은 제한 완화)
        if level == OpportunityLevel.EXTREME:
            return min(final_ratio, 0.5)  # EXTREME은 50%까지 허용
        else:
            return min(final_ratio, self.max_buy_per_opportunity)
    
    def _calculate_confidence_score(
        self,
        drop_7d: float,
        drop_30d: float,
        rsi: float,
        fear_greed: Optional[float]
    ) -> float:
        """
        신뢰도 점수 계산
        
        Args:
            drop_7d: 7일 하락률
            drop_30d: 30일 하락률
            rsi: RSI 지표
            fear_greed: 공포탐욕 지수
            
        Returns:
            신뢰도 점수 (0-1)
        """
        scores = []

        # 하락폭 점수
        drop_score = min(abs(min(drop_7d, drop_30d)) / 0.3, 1.0)
        scores.append(drop_score)

        # RSI 점수 (과매도일수록 높음)
        rsi_score = max(0, (50 - rsi) / 50)
        scores.append(rsi_score)

        # 공포지수 점수 (실데이터 있을 때만 반영)
        if fear_greed is not None:
            fear_score = max(0, (50 - fear_greed) / 50)
            scores.append(fear_score)
        
        # 7일과 30일 하락률 일관성
        consistency_score = 1 - abs(drop_7d - drop_30d) / 0.2
        scores.append(max(0, consistency_score))
        
        # 평균 점수
        return sum(scores) / len(scores)
    
    def execute_opportunistic_buys(
        self, 
        opportunities: List[BuyOpportunity],
        available_cash: float,
        max_total_buy: Optional[float] = None
    ) -> Dict:
        """
        기회적 매수 실행
        
        Args:
            opportunities: 매수 기회 목록
            available_cash: 사용 가능한 현금
            max_total_buy: 최대 총 매수 금액
            
        Returns:
            실행 결과
        """
        results = {
            "executed_orders": [],
            "failed_orders": [],
            "total_invested": 0,
            "remaining_cash": available_cash
        }
        
        # 최대 매수 금액 설정
        if max_total_buy is None:
            max_total_buy = available_cash * 0.5  # 기본적으로 현금의 50%까지만 사용

        total_budget = min(available_cash, max_total_buy)
        remaining_budget = total_budget

        for opportunity in opportunities:
            # 최근 매수 이력 확인 (시간 간격 + 직전 매수가 대비 추가 하락 조건)
            if not self._can_rebuy(opportunity.asset, opportunity.current_price):
                continue

            # 매수 금액 계산: 전체 예산 기준 레벨별 비율 (선순위 기회의 예산 독식 방지)
            buy_amount = min(
                total_budget * opportunity.recommended_buy_ratio,
                remaining_budget
            )
            
            # 최소 주문 금액 확인
            min_amount = MIN_ORDER_AMOUNTS_KRW.get(opportunity.asset, 5000)
            if buy_amount < min_amount:
                logger.info(f"⚠️ {opportunity.asset}: 매수 금액 {buy_amount:,.0f} KRW가 최소 금액 미달")
                continue
            
            try:
                # 매수 수량 계산 (분할 매수와 동일한 방식)
                calculated_quantity = buy_amount / opportunity.current_price
                
                # 최소/최대 주문량 검증 (분할 매수와 동일)
                min_order_quantities = {
                    "BTC": 0.0001,    "ETH": 0.001,     "XRP": 1.0,       "SOL": 0.01,      
                    "ADA": 2.0,       "DOT": 1.0,       "DOGE": 10.0,     "TRX": 10.0,      
                    "XLM": 10.0,      "ATOM": 0.2,      "ALGO": 5.0,      "VET": 50.0,
                }
                max_order_limits = {
                    "BTC": 10.0,      "ETH": 100.0,     "XRP": 10000.0,   "SOL": 100.0,     
                    "ADA": 50000.0,   "DOT": 1000.0,    "DOGE": 100000.0, "TRX": 100000.0,  
                    "XLM": 50000.0,   "ATOM": 1000.0,   "ALGO": 10000.0,  "VET": 100000.0,
                }
                
                min_limit = min_order_quantities.get(opportunity.asset, 0.0001)
                max_limit = max_order_limits.get(opportunity.asset, 1.0)

                # 최소 주문량 미달 시 스킵 (상향 조정하면 예산을 초과 매수하게 됨 — 금지)
                if calculated_quantity < min_limit:
                    logger.info(f"⚠️ {opportunity.asset}: 계산 수량 {calculated_quantity:.8f} < "
                                f"최소 주문량 {min_limit} — 건너뜀")
                    continue

                # 최대 주문량 상한만 적용
                final_quantity = min(calculated_quantity, max_limit)

                if final_quantity != calculated_quantity:
                    logger.info(f"📊 {opportunity.asset} 주문량 상한 조정: {calculated_quantity:.8f} → {final_quantity:.8f}")
                    buy_amount = final_quantity * opportunity.current_price
                
                # 매수 주문 실행 (분할 매수와 동일한 방식)
                if self.order_manager:
                    # OrderManager 사용하여 분할 매수와 일관성 유지
                    order_result_obj = self.order_manager.submit_market_order(
                        currency=opportunity.asset,
                        side="buy",
                        amount=final_quantity
                    )
                    
                    # Order 객체를 딕셔너리로 변환 (분할 매수와 동일한 방식)
                    if order_result_obj:
                        order_result = {
                            "success": order_result_obj.status.value != "FAILED",
                            "order_id": order_result_obj.order_id,
                            "status": order_result_obj.status.value,
                            "error": order_result_obj.error_message if order_result_obj.status.value == "FAILED" else None
                        }
                    else:
                        order_result = {
                            "success": False,
                            "error": "Order submission returned None"
                        }
                else:
                    # Fallback: coinone_client 직접 사용 (기존 방식)
                    order_result = self.coinone_client.place_limit_order(
                        currency=opportunity.asset,
                        side="buy",
                        price=opportunity.current_price,
                        amount=final_quantity,
                        order_type="limit"
                    )
                
                if order_result.get("success"):
                    results["executed_orders"].append({
                        "asset": opportunity.asset,
                        "amount": buy_amount,
                        "price": opportunity.current_price,
                        "opportunity_level": opportunity.opportunity_level.value,
                        "confidence": opportunity.confidence_score,
                        "order_id": order_result.get("order_id")
                    })
                    
                    results["total_invested"] += buy_amount
                    remaining_budget -= buy_amount

                    # 매수 이력 기록 (가격 포함 — 재매수 조건 판단용)
                    self.recent_buys[opportunity.asset] = datetime.now()
                    self.last_buy_prices[opportunity.asset] = opportunity.current_price
                    
                    logger.info(f"✅ {opportunity.asset} 기회적 매수 실행: {buy_amount:,.0f} KRW")
                    
                    # 데이터베이스 기록
                    self._record_opportunistic_buy(opportunity, buy_amount, order_result)
                    
                else:
                    results["failed_orders"].append({
                        "asset": opportunity.asset,
                        "amount": buy_amount,
                        "reason": order_result.get("error", "Unknown error")
                    })
                    logger.error(f"❌ {opportunity.asset} 매수 실패: {order_result.get('error')}")
                    
            except Exception as e:
                logger.error(f"{opportunity.asset} 매수 실행 중 오류: {e}")
                results["failed_orders"].append({
                    "asset": opportunity.asset,
                    "amount": buy_amount,
                    "reason": str(e)
                })
            
            # 예산 소진 시 중단
            if remaining_budget < 10000:  # 1만원 미만
                logger.info("예산 소진으로 기회적 매수 종료")
                break
        
        results["remaining_cash"] = available_cash - results["total_invested"]
        
        return results
    
    def _is_recently_bought(self, asset: str) -> bool:
        """
        최근 매수 여부 확인

        Args:
            asset: 자산 심볼

        Returns:
            최근 매수 여부
        """
        if asset not in self.recent_buys:
            return False

        last_buy_time = self.recent_buys[asset]
        time_since_buy = datetime.now() - last_buy_time

        return time_since_buy < timedelta(hours=self.min_buy_interval_hours)

    def _can_rebuy(self, asset: str, current_price: float) -> bool:
        """
        재매수 가능 여부 판단

        조건: ① 최소 매수 간격(4시간) 경과 AND
              ② 직전 매수가 대비 추가 하락(-3%) 발생 (지속 하락장에서 현금 소진 방지)

        직전 매수 이력이 없으면 항상 True.
        """
        if self._is_recently_bought(asset):
            logger.info(f"⏭️ {asset}: 최근 {self.min_buy_interval_hours}시간 내 매수 이력 있음, 건너뜀")
            return False

        # 추가 하락 조건은 직전 매수 후 72시간 이내에만 적용
        # (그 이후는 새로운 하락 국면으로 간주하고 시간 간격 조건만 적용)
        last_buy_time = self.recent_buys.get(asset)
        if last_buy_time and (datetime.now() - last_buy_time) < timedelta(hours=72):
            last_price = self.last_buy_prices.get(asset)
            if last_price and last_price > 0:
                required_price = last_price * (1 - self.rebuy_drop_threshold)
                if current_price > required_price:
                    logger.info(f"⏭️ {asset}: 직전 매수가({last_price:,.0f}) 대비 추가 하락 부족 "
                                f"(현재 {current_price:,.0f} > 기준 {required_price:,.0f}), 건너뜀")
                    return False

        return True
    
    def _record_opportunistic_buy(
        self, 
        opportunity: BuyOpportunity,
        amount: float,
        order_result: Dict
    ):
        """
        기회적 매수 기록
        
        Args:
            opportunity: 매수 기회 정보
            amount: 매수 금액
            order_result: 주문 결과
        """
        try:
            record = {
                "timestamp": datetime.now(),
                "asset": opportunity.asset,
                "amount_krw": amount,
                "price": opportunity.current_price,
                "opportunity_level": opportunity.opportunity_level.value,
                "price_drop_7d": opportunity.price_drop_7d,
                "price_drop_30d": opportunity.price_drop_30d,
                "rsi": opportunity.rsi,
                "fear_greed_index": opportunity.fear_greed_index,
                "confidence_score": opportunity.confidence_score,
                "order_id": order_result.get("order_id"),
                "status": "executed"
            }
            
            # 데이터베이스에 기록
            self.db_manager.save_opportunistic_buy_record(record)
            
        except Exception as e:
            logger.error(f"기회적 매수 기록 실패: {e}")
    
    def get_cash_utilization_strategy(self) -> Dict:
        """
        현금 활용 전략 조회
        
        Returns:
            현재 시장 상황에 맞는 현금 활용 전략
        """
        try:
            # 시장 상황 분석
            fear_greed = self.get_fear_greed_index()
            
            # BTC 기준 시장 동향
            btc_data = self.db_manager.get_market_data("BTC", days=30)
            if not btc_data.empty:
                btc_trend = (btc_data['Close'].iloc[-1] / btc_data['Close'].iloc[0]) - 1
                btc_volatility = btc_data['Close'].pct_change().std()
            else:
                btc_trend = 0
                btc_volatility = 0.02
            
            # 전략 결정 (공포탐욕 실데이터 없으면 중립 처리)
            if fear_greed is None:
                strategy = {
                    "mode": "balanced",
                    "description": "공포탐욕지수 데이터 없음 - 중립 접근",
                    "cash_deploy_ratio": 0.2,
                    "target_assets": ["BTC", "ETH"],
                    "buy_trigger": -0.10
                }
            elif fear_greed < 25:  # 극도의 공포
                strategy = {
                    "mode": "aggressive_buying",
                    "description": "극도의 공포 구간 - 적극적 매수",
                    "cash_deploy_ratio": 0.5,  # 현금의 50% 활용
                    "target_assets": ["BTC", "ETH"],  # 주요 자산 위주
                    "buy_trigger": -0.05  # 5% 하락 시 매수
                }
            elif fear_greed < 40:  # 공포
                strategy = {
                    "mode": "moderate_buying", 
                    "description": "공포 구간 - 선별적 매수",
                    "cash_deploy_ratio": 0.3,
                    "target_assets": ["BTC", "ETH", "SOL"],
                    "buy_trigger": -0.08
                }
            elif fear_greed > 75:  # 탐욕
                strategy = {
                    "mode": "defensive",
                    "description": "탐욕 구간 - 현금 보유 유지",
                    "cash_deploy_ratio": 0.1,
                    "target_assets": ["BTC"],
                    "buy_trigger": -0.15  # 15% 이상 하락 시만 매수
                }
            else:  # 중립
                strategy = {
                    "mode": "balanced",
                    "description": "중립 구간 - 균형적 접근",
                    "cash_deploy_ratio": 0.2,
                    "target_assets": ["BTC", "ETH"],
                    "buy_trigger": -0.10
                }
            
            # 변동성 조정
            if btc_volatility > 0.05:  # 높은 변동성
                strategy["cash_deploy_ratio"] *= 0.7  # 보수적 조정
                strategy["description"] += " (고변동성 조정)"
            
            strategy.update({
                "current_fear_greed": fear_greed,
                "btc_30d_trend": btc_trend,
                "btc_volatility": btc_volatility,
                "timestamp": datetime.now()
            })
            
            return strategy
            
        except Exception as e:
            logger.error(f"현금 활용 전략 조회 실패: {e}")
            return {
                "mode": "error",
                "description": "전략 조회 실패",
                "cash_deploy_ratio": 0.1,
                "error": str(e)
            }