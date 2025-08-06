"""
DCA+ Strategy (Dollar Cost Averaging Plus)

기존 DCA에 시장 상황을 고려한 지능형 매수 전략을 추가
- 변동성 기반 매수량 조절
- 공포/탐욕 지수 활용
- 축적 구간 감지 및 추가 매수
- 세금 효율적인 매수 스케줄링
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd
import numpy as np
from loguru import logger

from ..utils.market_data_provider import MarketDataProvider


@dataclass
class DCASignal:
    """DCA 신호 결과"""
    signal_strength: float  # 0.0 - 1.0
    recommended_amount: float  # 권장 투자 금액 (KRW)
    next_execution_date: datetime
    market_adjustment_factor: float  # 시장 상황 조정 배수
    reasoning: str  # 결정 근거
    market_conditions: Dict[str, Any] = field(default_factory=dict)


class FearGreedLevel(Enum):
    """공포/탐욕 지수 레벨"""
    EXTREME_FEAR = "extreme_fear"      # 0-25
    FEAR = "fear"                      # 26-45
    NEUTRAL = "neutral"                # 46-54
    GREED = "greed"                    # 55-75
    EXTREME_GREED = "extreme_greed"    # 76-100


class AccumulationSignal(Enum):
    """축적 신호 강도"""
    NONE = "none"
    WEAK = "weak"
    MODERATE = "moderate" 
    STRONG = "strong"
    EXTREME = "extreme"


@dataclass
class DCAEvent:
    """DCA 이벤트"""
    date: datetime
    asset: str
    amount_krw: float
    price: float
    quantity: float
    event_type: str  # regular, volatility_boost, fear_boost, accumulation_boost
    multiplier: float  # 기본 금액 대비 배수
    reasoning: str
    market_conditions: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DCASchedule:
    """DCA 스케줄"""
    base_amount_krw: float  # 기본 월간 투자 금액
    frequency_days: int     # 투자 주기 (일)
    assets: Dict[str, float]  # 자산별 비중
    volatility_multiplier: float  # 변동성 배수
    fear_greed_triggers: Dict[FearGreedLevel, float]  # 공포탐욕 배수
    accumulation_multiplier: float  # 축적 구간 배수
    max_monthly_amount: float  # 월 최대 투자 금액
    tax_optimization: bool  # 세금 최적화 여부


class DCAPlus:
    """
    DCA+ 전략 엔진
    
    시장 상황을 고려한 지능형 적립식 투자 시스템
    """
    
    def __init__(self, market_data_provider: Optional[MarketDataProvider] = None):
        """
        Args:
            market_data_provider: 시장 데이터 제공자
        """
        self.market_data_provider = market_data_provider
        
        # 기본 설정
        self.default_schedule = DCASchedule(
            base_amount_krw=1000000,    # 월 100만원
            frequency_days=7,           # 주간 투자
            assets={
                "BTC": 0.6,
                "ETH": 0.3,
                "SOL": 0.1
            },
            volatility_multiplier=2.0,  # 고변동성 시 2배
            fear_greed_triggers={
                FearGreedLevel.EXTREME_FEAR: 3.0,
                FearGreedLevel.FEAR: 2.0,
                FearGreedLevel.NEUTRAL: 1.0,
                FearGreedLevel.GREED: 0.7,
                FearGreedLevel.EXTREME_GREED: 0.3
            },
            accumulation_multiplier=1.5,  # 축적 구간에서 1.5배
            max_monthly_amount=5000000,    # 월 최대 500만원
            tax_optimization=True
        )
        
        # 기술적 분석 임계값들
        self.accumulation_thresholds = {
            "btc_dominance_min": 0.65,      # BTC 도미넌스 65% 이상
            "rsi_weekly_max": 35,           # 주간 RSI 35 이하
            "ma_deviation_min": -0.25,      # 200주 MA 대비 -25% 이하
            "volume_surge_min": 1.5         # 거래량 1.5배 이상 증가
        }
        
        logger.info("DCA+ 전략 엔진 초기화 완료")
    
    def calculate_dca_signal(
        self, 
        asset: str, 
        base_amount: float, 
        market_conditions: Dict[str, Any]
    ) -> DCASignal:
        """
        DCA 신호 계산 - 단일 자산에 대한 투자 신호 분석
        
        Args:
            asset: 자산명 (예: "BTC")
            base_amount: 기본 투자 금액 (KRW)
            market_conditions: 시장 상황 정보
            
        Returns:
            DCA 신호 결과
        """
        try:
            current_date = datetime.now()
            logger.info(f"DCA 신호 계산: {asset}, 기본금액 {base_amount:,.0f} KRW")
            
            # 시장 상황 분석 및 배수 계산
            fear_greed_index = market_conditions.get("fear_greed_index", 50)
            price_volatility = market_conditions.get("price_volatility", 0.03)
            trend_direction = market_conditions.get("trend_direction", "neutral")
            
            # 공포/탐욕 지수 기반 배수
            if fear_greed_index <= 25:  # 극도의 공포
                fear_greed_multiplier = 3.0
                fear_greed_level = FearGreedLevel.EXTREME_FEAR
            elif fear_greed_index <= 40:  # 공포
                fear_greed_multiplier = 2.0
                fear_greed_level = FearGreedLevel.FEAR
            elif fear_greed_index <= 55:  # 중립
                fear_greed_multiplier = 1.0
                fear_greed_level = FearGreedLevel.NEUTRAL
            elif fear_greed_index <= 75:  # 탐욕
                fear_greed_multiplier = 0.7
                fear_greed_level = FearGreedLevel.GREED
            else:  # 극도의 탐욕
                fear_greed_multiplier = 0.3
                fear_greed_level = FearGreedLevel.EXTREME_GREED
            
            # 변동성 기반 배수
            if price_volatility > 0.08:  # 8% 이상 고변동성
                volatility_multiplier = 1.5
            elif price_volatility > 0.05:  # 5% 이상 중변동성
                volatility_multiplier = 1.2
            else:  # 저변동성
                volatility_multiplier = 1.0
            
            # 트렌드 기반 배수
            if trend_direction == "down":
                trend_multiplier = 1.3  # 하락 시 더 많이 매수
            elif trend_direction == "up":
                trend_multiplier = 0.8  # 상승 시 적게 매수
            else:
                trend_multiplier = 1.0  # 횡보
            
            # 전체 배수 계산 (가중 평균)
            market_adjustment_factor = (
                fear_greed_multiplier * 0.5 +
                volatility_multiplier * 0.3 +
                trend_multiplier * 0.2
            )
            
            # 최종 투자 금액 계산
            recommended_amount = base_amount * market_adjustment_factor
            
            # 신호 강도 계산 (0.0 - 1.0)
            # 공포일수록, 변동성이 클수록, 하락장일수록 강한 신호
            signal_strength = min(1.0, (
                (100 - fear_greed_index) / 100 * 0.4 +  # 공포 지수 (역방향)
                min(price_volatility / 0.1, 1.0) * 0.3 +  # 변동성
                (1.3 if trend_direction == "down" else 0.8 if trend_direction == "up" else 1.0) * 0.3
            ))
            
            # 다음 실행 일자 계산 (기본 주간 DCA)
            next_execution_date = current_date + timedelta(days=7)
            
            # 결정 근거 생성
            reasoning_parts = []
            
            if fear_greed_level in [FearGreedLevel.EXTREME_FEAR, FearGreedLevel.FEAR]:
                reasoning_parts.append(f"시장 공포 상황({fear_greed_index}) - 기회 매수")
            elif fear_greed_level in [FearGreedLevel.GREED, FearGreedLevel.EXTREME_GREED]:
                reasoning_parts.append(f"시장 과열({fear_greed_index}) - 매수 축소")
            
            if price_volatility > 0.08:
                reasoning_parts.append(f"고변동성({price_volatility:.1%}) - 분할 매수 증가")
            
            if trend_direction == "down":
                reasoning_parts.append("하락 추세 - 적극 매수")
            elif trend_direction == "up":
                reasoning_parts.append("상승 추세 - 신중 매수")
            
            reasoning = "; ".join(reasoning_parts) if reasoning_parts else "정상적인 DCA 실행"
            
            # DCA 신호 생성
            dca_signal = DCASignal(
                signal_strength=signal_strength,
                recommended_amount=recommended_amount,
                next_execution_date=next_execution_date,
                market_adjustment_factor=market_adjustment_factor,
                reasoning=reasoning,
                market_conditions={
                    "fear_greed_index": fear_greed_index,
                    "fear_greed_level": fear_greed_level.value,
                    "price_volatility": price_volatility,
                    "trend_direction": trend_direction,
                    "fear_greed_multiplier": fear_greed_multiplier,
                    "volatility_multiplier": volatility_multiplier,
                    "trend_multiplier": trend_multiplier
                }
            )
            
            logger.info(f"DCA 신호 생성 완료: {asset} - 강도 {signal_strength:.2f}, "
                       f"권장금액 {recommended_amount:,.0f} KRW ({market_adjustment_factor:.2f}x)")
            logger.info(f"근거: {reasoning}")
            
            return dca_signal
            
        except Exception as e:
            logger.error(f"DCA 신호 계산 실패: {e}")
            # 실패 시 기본 신호 반환
            return DCASignal(
                signal_strength=0.5,
                recommended_amount=base_amount,
                next_execution_date=datetime.now() + timedelta(days=7),
                market_adjustment_factor=1.0,
                reasoning="계산 실패 - 기본값 적용",
                market_conditions=market_conditions
            )
    
    def calculate_dca_amount(
        self,
        schedule: DCASchedule,
        market_data: Dict[str, pd.DataFrame],
        current_date: datetime = None
    ) -> Dict[str, DCAEvent]:
        """
        DCA+ 매수 금액 계산
        
        Args:
            schedule: DCA 스케줄
            market_data: 시장 데이터
            current_date: 기준 날짜
            
        Returns:
            자산별 DCA 이벤트
        """
        try:
            if current_date is None:
                current_date = datetime.now()
                
            logger.info(f"DCA+ 매수 금액 계산: {current_date.strftime('%Y-%m-%d')}")
            
            dca_events = {}
            
            # 시장 상황 분석
            market_analysis = self._analyze_market_conditions(market_data, current_date)
            
            # 기본 매수 금액 (주기별 분할)
            base_amount = schedule.base_amount_krw * (schedule.frequency_days / 30)  # 월 기준을 주기별로 변환
            
            # 전체 시장 배수 계산
            overall_multiplier = self._calculate_overall_multiplier(
                schedule, market_analysis, current_date
            )
            
            # 월간 한도 체크
            monthly_total = base_amount * overall_multiplier
            if monthly_total > schedule.max_monthly_amount:
                overall_multiplier = schedule.max_monthly_amount / base_amount
                logger.warning(f"월간 한도 적용: {overall_multiplier:.2f}x")
            
            # 자산별 DCA 이벤트 생성
            for asset, weight in schedule.assets.items():
                asset_amount = base_amount * weight * overall_multiplier
                
                if asset_amount < 10000:  # 최소 매수 금액 1만원
                    continue
                
                # 자산별 세부 분석
                asset_analysis = self._analyze_asset_conditions(asset, market_data, current_date)
                
                # 현재 가격
                current_price = self._get_current_price(asset, market_data)
                if current_price <= 0:
                    continue
                
                quantity = asset_amount / current_price
                
                # 이벤트 타입 및 근거 결정
                event_type, reasoning = self._determine_event_type(
                    overall_multiplier, market_analysis, asset_analysis
                )
                
                dca_event = DCAEvent(
                    date=current_date,
                    asset=asset,
                    amount_krw=asset_amount,
                    price=current_price,
                    quantity=quantity,
                    event_type=event_type,
                    multiplier=overall_multiplier,
                    reasoning=reasoning,
                    market_conditions=market_analysis
                )
                
                dca_events[asset] = dca_event
                logger.info(f"{asset}: {asset_amount:,.0f} KRW ({overall_multiplier:.1f}x) - {reasoning}")
            
            return dca_events
            
        except Exception as e:
            logger.error(f"DCA+ 매수 금액 계산 실패: {e}")
            return {}
    
    def _analyze_market_conditions(self, market_data: Dict[str, pd.DataFrame], date: datetime) -> Dict[str, Any]:
        """시장 상황 종합 분석"""
        analysis = {
            "volatility_score": 0.5,
            "fear_greed_level": FearGreedLevel.NEUTRAL,
            "accumulation_signal": AccumulationSignal.NONE,
            "btc_dominance": 0.5,
            "market_trend": "sideways",
            "volume_profile": "normal"
        }
        
        try:
            # BTC 데이터 분석 (대표 지표로 사용)
            if "BTC" in market_data and len(market_data["BTC"]) > 30:
                btc_data = market_data["BTC"]
                
                # 변동성 점수 계산 (최근 30일)
                recent_returns = btc_data['Close'].tail(30).pct_change().dropna()
                volatility = recent_returns.std() * np.sqrt(365)  # 연화 변동성
                analysis["volatility_score"] = min(volatility / 1.0, 2.0)  # 0-2 스케일
                
                # 공포/탐욕 지수 추정 (RSI 기반)
                rsi = self._calculate_rsi(btc_data['Close'].tail(60))
                if len(rsi) > 0:
                    current_rsi = rsi.iloc[-1]
                    if current_rsi <= 25:
                        analysis["fear_greed_level"] = FearGreedLevel.EXTREME_FEAR
                    elif current_rsi <= 40:
                        analysis["fear_greed_level"] = FearGreedLevel.FEAR
                    elif current_rsi <= 55:
                        analysis["fear_greed_level"] = FearGreedLevel.NEUTRAL
                    elif current_rsi <= 75:
                        analysis["fear_greed_level"] = FearGreedLevel.GREED
                    else:
                        analysis["fear_greed_level"] = FearGreedLevel.EXTREME_GREED
                
                # 축적 신호 분석
                accumulation_score = self._calculate_accumulation_score(btc_data)
                if accumulation_score >= 0.8:
                    analysis["accumulation_signal"] = AccumulationSignal.EXTREME
                elif accumulation_score >= 0.6:
                    analysis["accumulation_signal"] = AccumulationSignal.STRONG
                elif accumulation_score >= 0.4:
                    analysis["accumulation_signal"] = AccumulationSignal.MODERATE
                elif accumulation_score >= 0.2:
                    analysis["accumulation_signal"] = AccumulationSignal.WEAK
                
                # 트렌드 분석
                ma_20 = btc_data['Close'].tail(20).mean()
                ma_200 = btc_data['Close'].tail(200).mean() if len(btc_data) >= 200 else ma_20
                current_price = btc_data['Close'].iloc[-1]
                
                if current_price > ma_20 > ma_200:
                    analysis["market_trend"] = "bullish"
                elif current_price < ma_20 < ma_200:
                    analysis["market_trend"] = "bearish"
                else:
                    analysis["market_trend"] = "sideways"
                
                # 거래량 프로필
                if 'Volume' in btc_data.columns:
                    recent_volume = btc_data['Volume'].tail(10).mean()
                    avg_volume = btc_data['Volume'].tail(50).mean()
                    volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1
                    
                    if volume_ratio > 1.5:
                        analysis["volume_profile"] = "high"
                    elif volume_ratio < 0.7:
                        analysis["volume_profile"] = "low"
                    else:
                        analysis["volume_profile"] = "normal"
            
            return analysis
            
        except Exception as e:
            logger.error(f"시장 상황 분석 실패: {e}")
            return analysis
    
    def _calculate_overall_multiplier(
        self, 
        schedule: DCASchedule, 
        market_analysis: Dict[str, Any],
        current_date: datetime
    ) -> float:
        """전체 시장 상황 기반 매수 배수 계산"""
        
        base_multiplier = 1.0
        
        # 1. 변동성 기반 배수
        volatility_score = market_analysis.get("volatility_score", 0.5)
        if volatility_score > 1.0:  # 고변동성
            volatility_multiplier = min(schedule.volatility_multiplier, 1 + volatility_score)
        else:
            volatility_multiplier = 1.0
        
        # 2. 공포/탐욕 지수 기반 배수
        fear_greed_level = market_analysis.get("fear_greed_level", FearGreedLevel.NEUTRAL)
        fear_greed_multiplier = schedule.fear_greed_triggers.get(fear_greed_level, 1.0)
        
        # 3. 축적 신호 기반 배수
        accumulation_signal = market_analysis.get("accumulation_signal", AccumulationSignal.NONE)
        accumulation_multipliers = {
            AccumulationSignal.NONE: 1.0,
            AccumulationSignal.WEAK: 1.1,
            AccumulationSignal.MODERATE: 1.2,
            AccumulationSignal.STRONG: 1.3,
            AccumulationSignal.EXTREME: 1.5
        }
        accumulation_multiplier = accumulation_multipliers[accumulation_signal]
        
        # 4. 시즌별 조정 (연말, 보너스 시즌 등)
        seasonal_multiplier = self._calculate_seasonal_multiplier(current_date)
        
        # 전체 배수 계산 (곱셈이 아닌 가중 평균으로 극단적 값 방지)
        components = [
            (volatility_multiplier, 0.3),
            (fear_greed_multiplier, 0.4),
            (accumulation_multiplier, 0.2),
            (seasonal_multiplier, 0.1)
        ]
        
        weighted_multiplier = sum(mult * weight for mult, weight in components)
        
        # 최종 배수 제한 (0.2x ~ 3.0x)
        final_multiplier = max(0.2, min(3.0, weighted_multiplier))
        
        logger.debug(f"배수 계산: 변동성 {volatility_multiplier:.1f}, 공포탐욕 {fear_greed_multiplier:.1f}, "
                    f"축적 {accumulation_multiplier:.1f}, 계절 {seasonal_multiplier:.1f} → 최종 {final_multiplier:.1f}")
        
        return final_multiplier
    
    def _calculate_accumulation_score(self, price_data: pd.DataFrame) -> float:
        """축적 구간 점수 계산 (0-1)"""
        try:
            score_components = []
            
            # 1. BTC 도미넌스 (가정: 높은 도미넌스 = 축적)
            # 실제로는 외부 API에서 가져와야 함
            btc_dominance = 0.6  # 기본값
            if btc_dominance >= self.accumulation_thresholds["btc_dominance_min"]:
                score_components.append(0.8)
            else:
                score_components.append(0.2)
            
            # 2. RSI 기반 과매도
            rsi = self._calculate_rsi(price_data['Close'].tail(100))
            if len(rsi) > 0:
                weekly_rsi = rsi.iloc[-7:].mean()  # 주간 평균 RSI
                if weekly_rsi <= self.accumulation_thresholds["rsi_weekly_max"]:
                    score_components.append(0.9)
                elif weekly_rsi <= 45:
                    score_components.append(0.6)
                else:
                    score_components.append(0.1)
            
            # 3. 200주 MA 대비 위치
            if len(price_data) >= 1400:  # 200주 데이터
                weekly_prices = price_data['Close'].iloc[::7]  # 주간 샘플링
                ma_200w = weekly_prices.tail(200).mean()
                current_price = price_data['Close'].iloc[-1]
                ma_deviation = (current_price - ma_200w) / ma_200w
                
                if ma_deviation <= self.accumulation_thresholds["ma_deviation_min"]:
                    score_components.append(1.0)
                elif ma_deviation <= -0.15:
                    score_components.append(0.7)
                elif ma_deviation <= 0:
                    score_components.append(0.4)
                else:
                    score_components.append(0.1)
            
            # 4. 거래량 분석 (높은 거래량 = 관심 증가)
            if 'Volume' in price_data.columns:
                recent_volume = price_data['Volume'].tail(10).mean()
                avg_volume = price_data['Volume'].tail(50).mean()
                volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1
                
                if volume_ratio >= self.accumulation_thresholds["volume_surge_min"]:
                    score_components.append(0.8)
                elif volume_ratio >= 1.2:
                    score_components.append(0.5)
                else:
                    score_components.append(0.2)
            
            return np.mean(score_components) if score_components else 0.0
            
        except Exception as e:
            logger.error(f"축적 점수 계산 실패: {e}")
            return 0.0
    
    def _analyze_asset_conditions(self, asset: str, market_data: Dict[str, pd.DataFrame], date: datetime) -> Dict[str, Any]:
        """개별 자산 상황 분석"""
        analysis = {
            "relative_strength": 0.5,
            "support_level": 0,
            "resistance_level": 0,
            "trend_score": 0.5
        }
        
        try:
            if asset in market_data and len(market_data[asset]) > 20:
                asset_data = market_data[asset]
                current_price = asset_data['Close'].iloc[-1]
                
                # 상대 강도 (vs BTC)
                if "BTC" in market_data and asset != "BTC":
                    btc_return = market_data["BTC"]['Close'].tail(30).pct_change().sum()
                    asset_return = asset_data['Close'].tail(30).pct_change().sum()
                    relative_performance = (asset_return - btc_return) + 1
                    analysis["relative_strength"] = max(0, min(2, relative_performance))
                
                # 지지/저항 레벨
                recent_high = asset_data['Close'].tail(50).max()
                recent_low = asset_data['Close'].tail(50).min()
                analysis["support_level"] = recent_low
                analysis["resistance_level"] = recent_high
                
                # 트렌드 점수
                ma_short = asset_data['Close'].tail(10).mean()
                ma_long = asset_data['Close'].tail(30).mean()
                if current_price > ma_short > ma_long:
                    analysis["trend_score"] = 0.8
                elif current_price < ma_short < ma_long:
                    analysis["trend_score"] = 0.2
                else:
                    analysis["trend_score"] = 0.5
            
            return analysis
            
        except Exception as e:
            logger.error(f"{asset} 자산 분석 실패: {e}")
            return analysis
    
    def _calculate_seasonal_multiplier(self, date: datetime) -> float:
        """계절별/시기별 매수 배수"""
        month = date.month
        
        # 연말 보너스 시즌 (12월)
        if month == 12:
            return 1.3
        
        # 연초 (1월) - 새해 결심
        elif month == 1:
            return 1.2
        
        # 중간 배당 시즌 (6월)
        elif month == 6:
            return 1.1
        
        # 일반 기간
        else:
            return 1.0
    
    def _determine_event_type(
        self, 
        multiplier: float, 
        market_analysis: Dict[str, Any],
        asset_analysis: Dict[str, Any]
    ) -> Tuple[str, str]:
        """이벤트 타입 및 근거 결정"""
        
        if multiplier >= 2.0:
            if market_analysis.get("accumulation_signal") in [AccumulationSignal.STRONG, AccumulationSignal.EXTREME]:
                return "accumulation_boost", f"축적 신호 감지 ({multiplier:.1f}x 매수)"
            elif market_analysis.get("fear_greed_level") in [FearGreedLevel.EXTREME_FEAR, FearGreedLevel.FEAR]:
                return "fear_boost", f"시장 공포 상황 기회매수 ({multiplier:.1f}x)"
            elif market_analysis.get("volatility_score", 0) > 1.0:
                return "volatility_boost", f"고변동성 기회매수 ({multiplier:.1f}x)"
        
        elif multiplier >= 1.2:
            return "enhanced_regular", f"시장 상황을 고려한 증액매수 ({multiplier:.1f}x)"
        
        elif multiplier < 0.8:
            return "reduced_regular", f"과열 구간 축소매수 ({multiplier:.1f}x)"
        
        else:
            return "regular", f"정기 적립매수 ({multiplier:.1f}x)"
    
    def _get_current_price(self, asset: str, market_data: Dict[str, pd.DataFrame]) -> float:
        """현재 가격 조회"""
        try:
            if asset in market_data and len(market_data[asset]) > 0:
                return float(market_data[asset]['Close'].iloc[-1])
            return 0.0
        except:
            return 0.0
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """RSI 계산"""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi.fillna(50)
        except:
            return pd.Series([50] * len(prices), index=prices.index)
    
    def generate_monthly_schedule(
        self, 
        schedule: DCASchedule, 
        start_date: datetime,
        market_data: Dict[str, pd.DataFrame]
    ) -> List[DCAEvent]:
        """월간 DCA 스케줄 생성"""
        
        monthly_events = []
        current_date = start_date
        end_date = start_date + timedelta(days=30)
        
        while current_date < end_date:
            # 주말 제외
            if current_date.weekday() < 5:  # 월~금
                dca_events = self.calculate_dca_amount(schedule, market_data, current_date)
                monthly_events.extend(dca_events.values())
            
            current_date += timedelta(days=schedule.frequency_days)
        
        return monthly_events
    
    def optimize_tax_timing(self, dca_events: List[DCAEvent], target_holding_period: int = 365) -> List[DCAEvent]:
        """세금 최적화를 위한 매수 타이밍 조정"""
        
        # 장기보유 우대세율을 위한 1년 보유 고려
        optimized_events = []
        
        for event in dca_events:
            # 현재는 단순히 이벤트를 유지
            # 실제로는 보유 기간, 세율, 매도 계획 등을 고려하여 조정
            optimized_events.append(event)
        
        return optimized_events
    
    def get_dca_performance_metrics(self, dca_history: List[DCAEvent]) -> Dict[str, Any]:
        """DCA 성과 지표 계산"""
        
        if not dca_history:
            return {}
        
        try:
            # 자산별 통계
            asset_stats = {}
            total_invested = 0
            total_quantity = {}
            
            for event in dca_history:
                asset = event.asset
                if asset not in asset_stats:
                    asset_stats[asset] = {
                        "total_invested": 0,
                        "total_quantity": 0,
                        "purchase_count": 0,
                        "avg_price": 0,
                        "event_types": {}
                    }
                
                asset_stats[asset]["total_invested"] += event.amount_krw
                asset_stats[asset]["total_quantity"] += event.quantity
                asset_stats[asset]["purchase_count"] += 1
                
                # 이벤트 타입별 통계
                event_type = event.event_type
                if event_type not in asset_stats[asset]["event_types"]:
                    asset_stats[asset]["event_types"][event_type] = 0
                asset_stats[asset]["event_types"][event_type] += 1
                
                total_invested += event.amount_krw
                
                if asset not in total_quantity:
                    total_quantity[asset] = 0
                total_quantity[asset] += event.quantity
            
            # 평균 매수 가격 계산
            for asset, stats in asset_stats.items():
                if stats["total_quantity"] > 0:
                    stats["avg_price"] = stats["total_invested"] / stats["total_quantity"]
            
            return {
                "total_invested_krw": total_invested,
                "asset_statistics": asset_stats,
                "total_purchases": len(dca_history),
                "avg_purchase_amount": total_invested / len(dca_history) if dca_history else 0,
                "date_range": {
                    "start": min(event.date for event in dca_history),
                    "end": max(event.date for event in dca_history)
                }
            }
            
        except Exception as e:
            logger.error(f"DCA 성과 지표 계산 실패: {e}")
            return {}