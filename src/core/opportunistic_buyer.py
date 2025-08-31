"""
Opportunistic Buyer Module

시장 하락 시 현금 보유분을 활용한 추가 매수 전략 모듈
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd
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
    fear_greed_index: float   # 공포탐욕 지수
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
        max_buy_per_opportunity: float = 0.3  # 기회당 최대 매수 비율
    ):
        """
        Args:
            coinone_client: 코인원 API 클라이언트
            db_manager: 데이터베이스 매니저
            order_manager: 주문 관리자 (없으면 coinone_client 직접 사용)
            cash_reserve_ratio: 현금 보유 비율
            min_opportunity_threshold: 최소 매수 기회 임계값
            max_buy_per_opportunity: 기회당 최대 매수 비율
        """
        self.coinone_client = coinone_client
        self.db_manager = db_manager
        self.order_manager = order_manager
        self.cash_reserve_ratio = cash_reserve_ratio
        self.min_opportunity_threshold = min_opportunity_threshold
        self.max_buy_per_opportunity = max_buy_per_opportunity
        
        # 매수 기회 레벨별 설정
        self.opportunity_thresholds = {
            OpportunityLevel.MINOR: {"drop": 0.05, "buy_ratio": 0.1},
            OpportunityLevel.MODERATE: {"drop": 0.10, "buy_ratio": 0.2},
            OpportunityLevel.MAJOR: {"drop": 0.20, "buy_ratio": 0.3},
            OpportunityLevel.EXTREME: {"drop": 0.30, "buy_ratio": 0.4}
        }
        
        # 최근 매수 이력 (중복 매수 방지) - 메모리 기반은 유지하되 DB 기반으로 보완
        self.recent_buys: Dict[str, datetime] = {}
        self.min_buy_interval_hours = 4  # 동일 자산 최소 매수 간격
        
        # 일일 한도 설정
        self.daily_limits = {
            "max_buy_count": 3,        # 자산별 일일 최대 매수 횟수
            "max_buy_amount": 1000000,  # 자산별 일일 최대 매수 금액 (100만원)
            "max_portfolio_ratio": 0.4  # 포트폴리오 대비 최대 비중
        }
        
        # 점진적 매수 설정 (N번째 매수는 더 큰 하락 필요)
        self.progressive_thresholds = {
            1: -0.05,   # 첫 번째 매수: -5%
            2: -0.10,   # 두 번째 매수: -10%
            3: -0.20,   # 세 번째 매수: -20%
        }
        
        # 기회 레벨별 쿨다운 시간 (시간 단위)
        self.cooldown_hours = {
            OpportunityLevel.MINOR: 6,
            OpportunityLevel.MODERATE: 12,
            OpportunityLevel.MAJOR: 24,
            OpportunityLevel.EXTREME: 48
        }
        
        logger.info(f"OpportunisticBuyer 초기화 완료 (현금 보유: {cash_reserve_ratio:.1%})")
    
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
    
    def get_fear_greed_index(self) -> float:
        """
        공포탐욕 지수 조회 (외부 API 또는 자체 계산)
        
        Returns:
            공포탐욕 지수 (0-100, 0=극도의 공포, 100=극도의 탐욕)
        """
        try:
            # 실제 구현 시 alternative.me API 등 활용
            # 여기서는 간단한 시뮬레이션
            btc_data = self.db_manager.get_market_data("BTC", days=7)
            if btc_data.empty:
                return 50.0
            
            # 변동성 기반 간단한 공포지수 계산
            volatility = btc_data['Close'].pct_change().std()
            price_change_7d = (btc_data['Close'].iloc[-1] / btc_data['Close'].iloc[0]) - 1
            
            # 하락 + 높은 변동성 = 공포
            fear_score = 50 - (price_change_7d * 100) - (volatility * 200)
            fear_score = max(0, min(100, fear_score))
            
            return fear_score
            
        except Exception as e:
            logger.error(f"공포탐욕 지수 조회 실패: {e}")
            return 50.0
    
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
                
                # 하락률 계산
                price_drop_7d = (current_price / avg_price_7d) - 1
                price_drop_30d = (current_price / avg_price_30d) - 1
                
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
                    if price_drop_7d > -0.05:  # 7일간 5% 이상 하락하지 않음
                        reasons.append(f"7일 하락률 부족 ({price_drop_7d:.1%})")
                    if rsi > 30:  # RSI가 과매도 구간이 아님
                        reasons.append(f"RSI 과매도 아님 ({rsi:.1f})")
                    if fear_greed > 25:  # 공포 지수가 충분히 낮지 않음
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
        fear_greed: float
    ) -> OpportunityLevel:
        """
        매수 기회 수준 판단
        
        Args:
            drop_7d: 7일 하락률
            drop_30d: 30일 하락률
            rsi: RSI 지표
            fear_greed: 공포탐욕 지수
            
        Returns:
            기회 수준
        """
        # 주요 지표 종합 평가
        max_drop = min(drop_7d, drop_30d)  # 더 큰 하락률 사용
        
        # RSI 과매도 구간 (30 이하)
        rsi_oversold = rsi < 30
        
        # 극도의 공포 구간 (25 이하)
        extreme_fear = fear_greed < 25
        
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
        fear_greed: float
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
        
        # 공포지수 조정 (공포가 클수록 비율 증가)
        fear_adjustment = max(0, (25 - fear_greed) / 100)  # 극도의 공포에서 보너스
        
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
        fear_greed: float
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
        
        # 공포지수 점수
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
            "skipped_orders": [],
            "total_invested": 0,
            "remaining_cash": available_cash
        }
        
        # 최대 매수 금액 설정
        if max_total_buy is None:
            max_total_buy = available_cash * 0.5  # 기본적으로 현금의 50%까지만 사용
        
        remaining_budget = min(available_cash, max_total_buy)
        
        for opportunity in opportunities:
            # 매수 가능 여부 종합 체크
            can_buy, reason = self._can_execute_buy(opportunity.asset, 
                                                     remaining_budget * opportunity.recommended_buy_ratio)
            if not can_buy:
                logger.info(f"⏭️ {opportunity.asset}: {reason}")
                results["skipped_orders"].append({
                    "asset": opportunity.asset,
                    "reason": reason
                })
                continue
            
            # 점진적 매수 조건 확인
            daily_stats = self.db_manager.get_daily_buy_stats(opportunity.asset)
            if daily_stats['count'] > 0:
                required_drop = self.progressive_thresholds.get(
                    daily_stats['count'] + 1, -0.30
                )
                current_drop = self._calculate_current_drop(opportunity.asset)
                
                if current_drop > required_drop:
                    reason = f"점진적 매수 조건 미충족 (현재: {current_drop:.1%}, 필요: {required_drop:.1%})"
                    logger.info(f"📈 {opportunity.asset}: {reason}")
                    results["skipped_orders"].append({
                        "asset": opportunity.asset,
                        "reason": reason
                    })
                    continue
            
            # 매수 금액 계산
            buy_amount = min(
                remaining_budget * opportunity.recommended_buy_ratio,
                remaining_budget
            )
            
            # 최소 주문 금액 확인 및 조정
            min_amount = MIN_ORDER_AMOUNTS_KRW.get(opportunity.asset, 5000)
            if buy_amount < min_amount:
                # 최소 금액이 남은 예산보다 크면 건너뛰기
                if min_amount > remaining_budget:
                    reason = f"최소 금액 {min_amount:,.0f} KRW가 남은 예산 {remaining_budget:,.0f} KRW 초과"
                    logger.info(f"⏭️ {opportunity.asset}: {reason}")
                    results["skipped_orders"].append({
                        "asset": opportunity.asset,
                        "reason": reason
                    })
                    continue
                # 최소 금액으로 조정
                logger.info(f"📈 {opportunity.asset}: 매수 금액을 최소 금액으로 조정 {buy_amount:,.0f} → {min_amount:,.0f} KRW")
                buy_amount = min_amount
            
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
                
                # 수량 조정
                final_quantity = max(min_limit, min(calculated_quantity, max_limit))
                
                if final_quantity != calculated_quantity:
                    logger.info(f"📊 {opportunity.asset} 주문량 조정: {calculated_quantity:.8f} → {final_quantity:.8f} {opportunity.asset}")
                    logger.info(f"💵 매수 금액: {buy_amount:,.0f} KRW (현재가: {opportunity.current_price:,.0f} KRW)")
                
                # 매수 주문 실행 (분할 매수와 동일한 방식)
                if self.order_manager:
                    # OrderManager 사용하여 분할 매수와 일관성 유지
                    # 시장가 매수는 KRW 금액을 전달해야 함
                    order_result_obj = self.order_manager.submit_market_order(
                        currency=opportunity.asset,
                        side="buy",
                        amount=buy_amount  # KRW 금액 전달
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
                    # 가격 단위 조정 (코인원 요구사항)
                    adjusted_price = opportunity.current_price
                    
                    # 코인원 가격 단위 요구사항
                    if opportunity.asset == "BTC":
                        # BTC는 10000원 단위
                        adjusted_price = int(adjusted_price / 10000) * 10000
                    elif opportunity.asset == "ETH":
                        # ETH는 1000원 단위
                        adjusted_price = int(adjusted_price / 1000) * 1000
                    elif opportunity.asset in ["XRP", "ADA", "DOGE", "TRX", "XLM"]:
                        # 저가 코인은 1원 단위
                        adjusted_price = int(adjusted_price)
                    else:
                        # 기타 코인은 10원 단위
                        adjusted_price = int(adjusted_price / 10) * 10
                    
                    logger.info(f"💰 가격 조정: {opportunity.current_price:.0f} → {adjusted_price:.0f} KRW")
                    
                    # Fallback: coinone_client 직접 사용 (기존 방식)
                    # 지정가 매수 시에도 올바른 수량 계산이 필요함
                    order_result = self.coinone_client.place_order(
                        currency=opportunity.asset,
                        side="buy",
                        price=adjusted_price,
                        amount=final_quantity,  # 지정가는 코인 수량 전달
                        amount_in_krw=False  # 지정가는 코인 수량으로 처리
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
                    
                    # 매수 이력 기록
                    self.recent_buys[opportunity.asset] = datetime.now()
                    
                    # 일일 매수 한도 업데이트
                    self.db_manager.update_daily_buy_limits(
                        opportunity.asset, 
                        buy_amount, 
                        opportunity.current_price
                    )
                    
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
    
    def _is_recently_bought(self, asset: str) -> tuple[bool, str]:
        """
        최근 매수 여부 확인 (DB 기반)
        
        Args:
            asset: 자산 심볼
            
        Returns:
            tuple[bool, str]: (최근 매수 여부, 상세 정보)
        """
        # DB 기반 최근 매수 이력 확인
        # 최대 쿨다운 시간까지 조회하여 모든 레벨의 쿨다운 체크 가능
        max_cooldown = max(self.cooldown_hours.values())  # 48시간
        recent_buys = self.db_manager.get_recent_opportunistic_buys(
            asset, hours=max_cooldown
        )
        
        if recent_buys:
            # 가장 최근 매수의 기회 레벨에 따른 쿨다운 확인
            last_buy = recent_buys[0]
            if 'opportunity_level' in last_buy:
                level = OpportunityLevel(last_buy['opportunity_level'])
                cooldown = self.cooldown_hours.get(level, self.min_buy_interval_hours)
                
                last_buy_time = datetime.fromisoformat(last_buy['timestamp'])
                time_since_buy = datetime.now() - last_buy_time
                
                if time_since_buy < timedelta(hours=cooldown):
                    elapsed_hours = time_since_buy.total_seconds() / 3600
                    cooldown_info = f"쿨다운 기간 중 ({cooldown}시간 중 {elapsed_hours:.1f}시간 경과)"
                    logger.info(f"{asset}: {cooldown_info}")
                    return True, cooldown_info
        
        # 메모리 기반 확인 (폴백)
        if asset in self.recent_buys:
            last_buy_time = self.recent_buys[asset]
            time_since_buy = datetime.now() - last_buy_time
            if time_since_buy < timedelta(hours=self.min_buy_interval_hours):
                elapsed_hours = time_since_buy.total_seconds() / 3600
                cooldown_info = f"쿨다운 기간 중 ({self.min_buy_interval_hours}시간 중 {elapsed_hours:.1f}시간 경과)"
                return True, cooldown_info
        
        return False, ""
    
    def _can_execute_buy(self, asset: str, amount: float) -> tuple[bool, str]:
        """
        매수 가능 여부 확인
        
        Args:
            asset: 자산 심볼
            amount: 매수 예정 금액
            
        Returns:
            튜플: (가능 여부, 불가능한 경우 사유)
        """
        # 1. 거래 락 확인
        if self.db_manager.is_trading_locked('opportunistic_buy', asset):
            return False, "Trading locked by rebalancing or maintenance"
        
        # 2. 최근 리밸런싱 확인 (24시간 이내)
        last_rebalance = self.db_manager.get_last_rebalance_time()
        if last_rebalance:
            time_since_rebalance = datetime.now() - last_rebalance
            if time_since_rebalance < timedelta(hours=24):
                hours_passed = time_since_rebalance.total_seconds() / 3600
                return False, f"Recent rebalancing detected ({hours_passed:.1f}h ago)"
        
        # 3. 일일 매수 한도 확인
        daily_stats = self.db_manager.get_daily_buy_stats(asset)
        
        if daily_stats['count'] >= self.daily_limits['max_buy_count']:
            return False, f"Daily buy count limit reached ({daily_stats['count']}/{self.daily_limits['max_buy_count']})"
        
        if daily_stats['amount'] + amount > self.daily_limits['max_buy_amount']:
            remaining = self.daily_limits['max_buy_amount'] - daily_stats['amount']
            return False, f"Daily buy amount limit reached (remaining: {remaining:,.0f} KRW)"
        
        # 4. 최근 매수 이력 확인 (쿨다운)
        is_cooldown, cooldown_info = self._is_recently_bought(asset)
        if is_cooldown:
            return False, cooldown_info
        
        # 5. 포트폴리오 비중 확인
        try:
            portfolio = self.coinone_client.get_portfolio_value()
            if asset in portfolio['assets']:
                asset_value = portfolio['assets'][asset].get('value_krw', 0)
                total_value = portfolio['total_value_krw']
                
                if total_value > 0:
                    current_ratio = asset_value / total_value
                    if current_ratio > self.daily_limits['max_portfolio_ratio']:
                        return False, f"Portfolio ratio too high ({current_ratio:.1%} > {self.daily_limits['max_portfolio_ratio']:.1%})"
        except Exception as e:
            logger.warning(f"포트폴리오 비중 확인 실패: {e}")
        
        return True, "OK"
    
    def _calculate_current_drop(self, asset: str) -> float:
        """
        현재 하락률 계산
        
        Args:
            asset: 자산 심볼
            
        Returns:
            하락률 (음수)
        """
        try:
            price_data_7d = self.db_manager.get_market_data(asset, days=7)
            if not price_data_7d.empty:
                current_price = price_data_7d['Close'].iloc[-1]
                avg_price_7d = price_data_7d['Close'].mean()
                return (current_price / avg_price_7d) - 1
        except Exception as e:
            logger.error(f"하락률 계산 실패: {e}")
        
        return 0.0
    
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
            
            # 전략 결정
            if fear_greed < 25:  # 극도의 공포
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