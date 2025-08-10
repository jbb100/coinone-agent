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
        cash_reserve_ratio: float = 0.15,  # 기본 현금 보유 비율
        min_opportunity_threshold: float = 0.05,  # 최소 기회 임계값 (5% 하락)
        max_buy_per_opportunity: float = 0.3  # 기회당 최대 매수 비율
    ):
        """
        Args:
            coinone_client: 코인원 API 클라이언트
            db_manager: 데이터베이스 매니저
            cash_reserve_ratio: 현금 보유 비율
            min_opportunity_threshold: 최소 매수 기회 임계값
            max_buy_per_opportunity: 기회당 최대 매수 비율
        """
        self.coinone_client = coinone_client
        self.db_manager = db_manager
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
        
        # 최근 매수 이력 (중복 매수 방지)
        self.recent_buys: Dict[str, datetime] = {}
        self.min_buy_interval_hours = 4  # 동일 자산 최소 매수 간격
        
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
    
    def identify_opportunities(self, assets: List[str]) -> List[BuyOpportunity]:
        """
        매수 기회 식별
        
        Args:
            assets: 분석할 자산 목록
            
        Returns:
            매수 기회 목록
        """
        opportunities = []
        
        for asset in assets:
            if asset == "KRW":
                continue
                
            try:
                # 가격 데이터 조회
                price_data_7d = self.db_manager.get_market_data(asset, days=7)
                price_data_30d = self.db_manager.get_market_data(asset, days=30)
                
                if price_data_7d.empty or price_data_30d.empty:
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
                    
                    logger.info(f"📉 매수 기회 발견: {asset}")
                    logger.info(f"  - 7일 하락률: {price_drop_7d:.1%}")
                    logger.info(f"  - RSI: {rsi:.1f}")
                    logger.info(f"  - 기회 수준: {opportunity_level.value}")
                    logger.info(f"  - 추천 매수 비율: {buy_ratio:.1%}")
                    
            except Exception as e:
                logger.error(f"{asset} 기회 분석 실패: {e}")
                continue
        
        # 신뢰도 점수 기준 정렬
        opportunities.sort(key=lambda x: x.confidence_score, reverse=True)
        
        return opportunities
    
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
            "total_invested": 0,
            "remaining_cash": available_cash
        }
        
        # 최대 매수 금액 설정
        if max_total_buy is None:
            max_total_buy = available_cash * 0.5  # 기본적으로 현금의 50%까지만 사용
        
        remaining_budget = min(available_cash, max_total_buy)
        
        for opportunity in opportunities:
            # 최근 매수 이력 확인
            if self._is_recently_bought(opportunity.asset):
                logger.info(f"⏭️ {opportunity.asset}: 최근 매수 이력 있음, 건너뜀")
                continue
            
            # 매수 금액 계산
            buy_amount = min(
                remaining_budget * opportunity.recommended_buy_ratio,
                remaining_budget
            )
            
            # 최소 주문 금액 확인
            min_amount = MIN_ORDER_AMOUNTS_KRW.get(opportunity.asset, 5000)
            if buy_amount < min_amount:
                logger.info(f"⚠️ {opportunity.asset}: 매수 금액 {buy_amount:,.0f} KRW가 최소 금액 미달")
                continue
            
            try:
                # 매수 주문 실행
                order_result = self.coinone_client.place_limit_order(
                    currency=opportunity.asset,
                    side="buy",
                    price=opportunity.current_price,
                    amount=buy_amount / opportunity.current_price,
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
                    
                    # 매수 이력 기록
                    self.recent_buys[opportunity.asset] = datetime.now()
                    
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