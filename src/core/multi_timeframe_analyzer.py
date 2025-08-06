"""
Multi-Timeframe Analysis System

다층 시간 프레임 분석을 통한 보다 정교한 시장 분석
- 단기 (20일): 노이즈 필터링 및 단기 트렌드
- 중기 (200주): 기존 시장 계절 시스템
- 장기 (4년): 비트코인 반감기 사이클 분석
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from dataclasses import dataclass
import pandas as pd
import numpy as np
from loguru import logger

from .market_season_filter import MarketSeasonFilter, MarketSeason


class TrendDirection(Enum):
    """트렌드 방향"""
    BULLISH = "bullish"
    BEARISH = "bearish"
    SIDEWAYS = "sideways"


class CyclePhase(Enum):
    """비트코인 사이클 단계"""
    ACCUMULATION = "accumulation"      # 축적 단계
    MARKUP = "markup"                  # 상승 단계
    DISTRIBUTION = "distribution"      # 분산 단계
    DECLINE = "decline"               # 하락 단계


@dataclass
class TimeframeAnalysis:
    """시간대별 분석 결과"""
    timeframe: str
    trend_direction: TrendDirection
    strength: float  # 트렌드 강도 (0-1)
    support_level: float
    resistance_level: float
    confidence: float  # 신뢰도 (0-1)
    last_updated: datetime


@dataclass 
class MultiTimeframeResult:
    """멀티 타임프레임 분석 결과"""
    short_term: TimeframeAnalysis      # 20일
    medium_term: TimeframeAnalysis     # 200주
    long_term: TimeframeAnalysis       # 4년
    market_season: MarketSeason
    cycle_phase: CyclePhase
    overall_confidence: float
    recommended_allocation: Dict[str, float]
    analysis_timestamp: datetime


class MultiTimeframeAnalyzer:
    """
    멀티 타임프레임 분석기
    
    다양한 시간 프레임에서 시장을 분석하여
    보다 정교한 투자 결정을 지원합니다.
    """
    
    def __init__(self, market_season_filter: MarketSeasonFilter):
        """
        Args:
            market_season_filter: 기존 시장 계절 필터
        """
        self.market_season_filter = market_season_filter
        
        # 비트코인 반감기 날짜들 (UTC 기준)
        self.halving_dates = [
            datetime(2012, 11, 28),  # 1차 반감기
            datetime(2016, 7, 9),    # 2차 반감기  
            datetime(2020, 5, 11),   # 3차 반감기
            datetime(2024, 4, 20),   # 4차 반감기 (예상)
            datetime(2028, 4, 20),   # 5차 반감기 (예상)
        ]
        
        logger.info("MultiTimeframeAnalyzer 초기화 완료")
    
    def analyze_multi_timeframe(self, symbol: str, price_data: pd.Series) -> Dict[str, Any]:
        """
        멀티 타임프레임 분석 (외부 인터페이스용)
        
        Args:
            symbol: 분석할 심볼 (예: "BTC")
            price_data: 가격 데이터 Series
            
        Returns:
            분석 결과 딕셔너리
        """
        try:
            logger.info(f"멀티 타임프레임 분석 시작: {symbol}")
            
            # Series를 DataFrame으로 변환
            if isinstance(price_data, pd.Series):
                df = pd.DataFrame({'Close': price_data})
                # 기본 OHLCV 데이터 생성
                df['Open'] = df['Close'].shift(1).fillna(df['Close'])
                df['High'] = df[['Open', 'Close']].max(axis=1)
                df['Low'] = df[['Open', 'Close']].min(axis=1)
                df['Volume'] = 1000000  # 기본값
            else:
                df = price_data
            
            # 전체 분석 수행
            result = self.analyze_all_timeframes(df)
            
            # 외부 인터페이스에 맞는 형태로 반환
            return self.get_analysis_summary(result)
            
        except Exception as e:
            logger.error(f"멀티 타임프레임 분석 실패: {e}")
            return {
                "overall_trend": {
                    "short": "sideways",
                    "medium": "sideways", 
                    "long": "sideways"
                },
                "market_season": "neutral",
                "cycle_phase": "accumulation",
                "confidence": 0.1,
                "recommended_allocation": {
                    "crypto": "50.0%",
                    "krw": "50.0%"
                },
                "key_levels": {
                    "short_term_support": 0,
                    "short_term_resistance": 0,
                    "long_term_support": 0,
                    "long_term_resistance": 0
                }
            }
    
    def analyze_all_timeframes(self, price_data: pd.DataFrame) -> MultiTimeframeResult:
        """
        전체 시간대 통합 분석
        
        Args:
            price_data: BTC 가격 데이터 (OHLCV)
            
        Returns:
            멀티 타임프레임 분석 결과
        """
        try:
            logger.info("멀티 타임프레임 분석 시작")
            
            # 각 시간대별 분석
            short_term = self._analyze_short_term(price_data)
            medium_term = self._analyze_medium_term(price_data) 
            long_term = self._analyze_long_term(price_data)
            
            # 기존 시장 계절 분석
            season_result = self.market_season_filter.analyze_weekly(price_data)
            market_season = MarketSeason(season_result.get("market_season", "neutral"))
            
            # 비트코인 사이클 단계 분석
            cycle_phase = self._analyze_bitcoin_cycle(price_data)
            
            # 전체적인 신뢰도 계산
            overall_confidence = self._calculate_overall_confidence(
                short_term, medium_term, long_term
            )
            
            # 권장 자산 배분 계산
            recommended_allocation = self._calculate_recommended_allocation(
                short_term, medium_term, long_term, market_season, cycle_phase
            )
            
            result = MultiTimeframeResult(
                short_term=short_term,
                medium_term=medium_term, 
                long_term=long_term,
                market_season=market_season,
                cycle_phase=cycle_phase,
                overall_confidence=overall_confidence,
                recommended_allocation=recommended_allocation,
                analysis_timestamp=datetime.now()
            )
            
            logger.info(f"멀티 타임프레임 분석 완료: 신뢰도 {overall_confidence:.1%}")
            return result
            
        except Exception as e:
            logger.error(f"멀티 타임프레임 분석 실패: {e}")
            raise
    
    def _analyze_short_term(self, price_data: pd.DataFrame) -> TimeframeAnalysis:
        """
        단기 분석 (20일)
        RSI, MACD, 볼린저 밴드 등을 활용한 단기 트렌드 분석
        """
        try:
            # 20일 이동평균
            close_prices = price_data['Close']
            ma_20 = close_prices.rolling(window=20).mean()
            current_price = close_prices.iloc[-1]
            current_ma = ma_20.iloc[-1]
            
            # RSI 계산
            rsi = self._calculate_rsi(close_prices, period=14)
            current_rsi = rsi.iloc[-1] if not rsi.empty else 50
            
            # 볼린저 밴드
            bb_upper, bb_lower = self._calculate_bollinger_bands(close_prices, period=20)
            
            # 트렌드 방향 결정
            if current_price > current_ma and current_rsi > 50:
                if current_rsi > 70:
                    trend = TrendDirection.BULLISH
                    strength = min((current_rsi - 50) / 50, 1.0)
                else:
                    trend = TrendDirection.BULLISH  
                    strength = (current_rsi - 50) / 50
            elif current_price < current_ma and current_rsi < 50:
                trend = TrendDirection.BEARISH
                strength = (50 - current_rsi) / 50
            else:
                trend = TrendDirection.SIDEWAYS
                strength = 0.3
            
            # 지지/저항 레벨
            recent_high = close_prices.tail(20).max()
            recent_low = close_prices.tail(20).min()
            
            # 신뢰도 계산
            price_distance_from_ma = abs(current_price - current_ma) / current_ma
            confidence = min(price_distance_from_ma * 10, 1.0)
            
            return TimeframeAnalysis(
                timeframe="short_term_20d",
                trend_direction=trend,
                strength=strength,
                support_level=recent_low,
                resistance_level=recent_high,
                confidence=confidence,
                last_updated=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"단기 분석 실패: {e}")
            return TimeframeAnalysis(
                timeframe="short_term_20d",
                trend_direction=TrendDirection.SIDEWAYS,
                strength=0.5,
                support_level=0,
                resistance_level=0,
                confidence=0.1,
                last_updated=datetime.now()
            )
    
    def _analyze_medium_term(self, price_data: pd.DataFrame) -> TimeframeAnalysis:
        """
        중기 분석 (200주)
        기존 200주 이동평균 시스템을 확장
        """
        try:
            close_prices = price_data['Close']
            
            # 200주 이동평균 (기존 시스템 활용)
            ma_200w = self.market_season_filter.calculate_200week_ma(price_data)
            current_price = close_prices.iloc[-1]
            
            # 트렌드 강도 계산
            price_ratio = current_price / ma_200w
            
            # 트렌드 방향 및 강도
            if price_ratio >= 1.1:  # 10% 이상
                trend = TrendDirection.BULLISH
                strength = min((price_ratio - 1.0) / 0.5, 1.0)  # 50% 상승을 최대로
            elif price_ratio <= 0.9:  # 10% 이하
                trend = TrendDirection.BEARISH  
                strength = min((1.0 - price_ratio) / 0.5, 1.0)
            else:
                trend = TrendDirection.SIDEWAYS
                strength = 0.4
            
            # 지지/저항 레벨 (200주 MA 기준)
            support_level = ma_200w * 0.85  # 15% 아래
            resistance_level = ma_200w * 1.15  # 15% 위
            
            # 신뢰도 (200주 MA는 일반적으로 신뢰도 높음)
            confidence = 0.8
            
            return TimeframeAnalysis(
                timeframe="medium_term_200w",
                trend_direction=trend,
                strength=strength,
                support_level=support_level,
                resistance_level=resistance_level,
                confidence=confidence,
                last_updated=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"중기 분석 실패: {e}")
            return TimeframeAnalysis(
                timeframe="medium_term_200w",
                trend_direction=TrendDirection.SIDEWAYS,
                strength=0.5,
                support_level=0,
                resistance_level=0,
                confidence=0.3,
                last_updated=datetime.now()
            )
    
    def _analyze_long_term(self, price_data: pd.DataFrame) -> TimeframeAnalysis:
        """
        장기 분석 (4년 사이클)
        비트코인 반감기 사이클 기반 분석
        """
        try:
            # 가장 최근 반감기 찾기
            current_date = datetime.now()
            last_halving = None
            next_halving = None
            
            for halving_date in self.halving_dates:
                if halving_date <= current_date:
                    last_halving = halving_date
                else:
                    next_halving = halving_date
                    break
            
            if not last_halving:
                last_halving = self.halving_dates[0]
            if not next_halving:
                next_halving = self.halving_dates[-1]
            
            # 현재 사이클 위치 계산
            cycle_length = (next_halving - last_halving).days
            days_since_halving = (current_date - last_halving).days
            cycle_progress = days_since_halving / cycle_length
            
            # 사이클 단계별 특성
            if cycle_progress < 0.25:
                trend = TrendDirection.SIDEWAYS  # 축적 단계
                strength = 0.3
            elif cycle_progress < 0.75:
                trend = TrendDirection.BULLISH  # 상승 단계
                strength = 0.8
            else:
                trend = TrendDirection.BEARISH  # 분산/하락 단계
                strength = 0.6
            
            # 장기 지지/저항 레벨
            close_prices = price_data['Close']
            current_price = close_prices.iloc[-1]
            
            # 과거 사이클 기준 지지/저항
            yearly_high = close_prices.tail(365).max() if len(close_prices) > 365 else current_price * 2
            yearly_low = close_prices.tail(365).min() if len(close_prices) > 365 else current_price * 0.5
            
            # 신뢰도는 사이클 단계에 따라
            confidence = 0.9 if 0.1 < cycle_progress < 0.9 else 0.6
            
            return TimeframeAnalysis(
                timeframe="long_term_4y",
                trend_direction=trend,
                strength=strength,
                support_level=yearly_low,
                resistance_level=yearly_high,
                confidence=confidence,
                last_updated=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"장기 분석 실패: {e}")
            return TimeframeAnalysis(
                timeframe="long_term_4y",
                trend_direction=TrendDirection.BULLISH,
                strength=0.6,
                support_level=0,
                resistance_level=0,
                confidence=0.5,
                last_updated=datetime.now()
            )
    
    def _analyze_bitcoin_cycle(self, price_data: pd.DataFrame) -> CyclePhase:
        """비트코인 4년 사이클 단계 분석"""
        try:
            current_date = datetime.now()
            last_halving = None
            
            for halving_date in reversed(self.halving_dates):
                if halving_date <= current_date:
                    last_halving = halving_date
                    break
            
            if not last_halving:
                return CyclePhase.ACCUMULATION
            
            days_since_halving = (current_date - last_halving).days
            
            # 대략적인 사이클 단계 (역사적 패턴 기반)
            if days_since_halving < 150:  # 약 5개월
                return CyclePhase.ACCUMULATION
            elif days_since_halving < 550:  # 약 18개월
                return CyclePhase.MARKUP
            elif days_since_halving < 750:  # 약 25개월  
                return CyclePhase.DISTRIBUTION
            else:
                return CyclePhase.DECLINE
                
        except Exception as e:
            logger.error(f"비트코인 사이클 분석 실패: {e}")
            return CyclePhase.ACCUMULATION
    
    def _calculate_overall_confidence(
        self, 
        short: TimeframeAnalysis, 
        medium: TimeframeAnalysis, 
        long: TimeframeAnalysis
    ) -> float:
        """전체 신뢰도 계산"""
        # 시간대별 일치도 확인
        trends = [short.trend_direction, medium.trend_direction, long.trend_direction]
        
        # 같은 방향이 많을수록 신뢰도 높음
        if trends.count(TrendDirection.BULLISH) >= 2:
            alignment_bonus = 0.3
        elif trends.count(TrendDirection.BEARISH) >= 2:
            alignment_bonus = 0.3
        else:
            alignment_bonus = 0.0
        
        # 각 시간대 신뢰도의 가중평균
        weighted_confidence = (
            short.confidence * 0.2 +    # 단기 20%
            medium.confidence * 0.5 +   # 중기 50%  
            long.confidence * 0.3       # 장기 30%
        ) + alignment_bonus
        
        return min(weighted_confidence, 1.0)
    
    def _calculate_recommended_allocation(
        self,
        short: TimeframeAnalysis,
        medium: TimeframeAnalysis, 
        long: TimeframeAnalysis,
        market_season: MarketSeason,
        cycle_phase: CyclePhase
    ) -> Dict[str, float]:
        """권장 자산 배분 계산"""
        
        # 기본 배분 (시장 계절 기준)
        base_allocations = {
            MarketSeason.RISK_ON: {"crypto": 0.70, "krw": 0.30},
            MarketSeason.RISK_OFF: {"crypto": 0.30, "krw": 0.70},
            MarketSeason.NEUTRAL: {"crypto": 0.50, "krw": 0.50}
        }
        
        base_allocation = base_allocations[market_season]
        crypto_weight = base_allocation["crypto"]
        krw_weight = base_allocation["krw"]
        
        # 사이클 단계별 조정
        cycle_adjustments = {
            CyclePhase.ACCUMULATION: 0.10,   # 암호화폐 비중 +10%
            CyclePhase.MARKUP: 0.05,         # 암호화폐 비중 +5%
            CyclePhase.DISTRIBUTION: -0.10,  # 암호화폐 비중 -10%
            CyclePhase.DECLINE: -0.15        # 암호화폐 비중 -15%
        }
        
        cycle_adjustment = cycle_adjustments[cycle_phase]
        
        # 시간대별 트렌드 강도 고려
        trend_strength_avg = (short.strength + medium.strength + long.strength) / 3
        
        # 강세 트렌드일 때 암호화폐 비중 증가
        bullish_trends = [t for t in [short.trend_direction, medium.trend_direction, long.trend_direction] 
                         if t == TrendDirection.BULLISH]
        bearish_trends = [t for t in [short.trend_direction, medium.trend_direction, long.trend_direction]
                         if t == TrendDirection.BEARISH]
        
        if len(bullish_trends) > len(bearish_trends):
            trend_adjustment = 0.05 * trend_strength_avg
        elif len(bearish_trends) > len(bullish_trends):
            trend_adjustment = -0.05 * trend_strength_avg
        else:
            trend_adjustment = 0.0
        
        # 최종 조정 적용
        final_crypto = crypto_weight + cycle_adjustment + trend_adjustment
        final_crypto = max(0.20, min(0.80, final_crypto))  # 20-80% 범위 제한
        final_krw = 1.0 - final_crypto
        
        return {
            "crypto": final_crypto,
            "krw": final_krw,
            "adjustments": {
                "cycle": cycle_adjustment,
                "trend": trend_adjustment,
                "final_crypto": final_crypto
            }
        }
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """RSI 계산"""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi
        except:
            return pd.Series([50] * len(prices), index=prices.index)
    
    def _calculate_bollinger_bands(self, prices: pd.Series, period: int = 20, std_dev: int = 2) -> Tuple[pd.Series, pd.Series]:
        """볼린저 밴드 계산"""
        try:
            ma = prices.rolling(window=period).mean()
            std = prices.rolling(window=period).std()
            upper_band = ma + (std * std_dev)
            lower_band = ma - (std * std_dev)
            return upper_band, lower_band
        except:
            return prices * 1.1, prices * 0.9
    
    def get_analysis_summary(self, result: MultiTimeframeResult) -> Dict[str, Any]:
        """분석 결과 요약"""
        return {
            "overall_trend": {
                "short": result.short_term.trend_direction.value,
                "medium": result.medium_term.trend_direction.value, 
                "long": result.long_term.trend_direction.value
            },
            "market_season": result.market_season.value,
            "cycle_phase": result.cycle_phase.value,
            "confidence": result.overall_confidence,
            "recommended_allocation": {
                "crypto": f"{result.recommended_allocation['crypto']:.1%}",
                "krw": f"{result.recommended_allocation['krw']:.1%}"
            },
            "key_levels": {
                "short_term_support": result.short_term.support_level,
                "short_term_resistance": result.short_term.resistance_level,
                "long_term_support": result.long_term.support_level,
                "long_term_resistance": result.long_term.resistance_level
            }
        }


# 유틸리티 함수들
def get_trend_consensus(trends: List[TrendDirection]) -> TrendDirection:
    """트렌드 합의 계산"""
    if trends.count(TrendDirection.BULLISH) >= 2:
        return TrendDirection.BULLISH
    elif trends.count(TrendDirection.BEARISH) >= 2:
        return TrendDirection.BEARISH
    else:
        return TrendDirection.SIDEWAYS


def calculate_trend_alignment_score(
    short: TrendDirection, 
    medium: TrendDirection, 
    long: TrendDirection
) -> float:
    """트렌드 정렬 점수 계산 (0-1)"""
    trends = [short, medium, long]
    
    if len(set(trends)) == 1:  # 모두 같음
        return 1.0
    elif len(set(trends)) == 2:  # 2개가 같음
        return 0.6
    else:  # 모두 다름
        return 0.2