"""
Market Season Filter

BTC 200주 이동평균선과 ±5% 완충 밴드를 활용한 시장 계절 판단 모듈
"""

from datetime import datetime, timedelta
from typing import Dict, Literal, Optional, Tuple
from enum import Enum
import pandas as pd
import numpy as np
from loguru import logger


class MarketSeason(Enum):
    """시장 계절 정의"""
    RISK_ON = "risk_on"     # 강세장 (암호화폐 70% / KRW 30%)
    RISK_OFF = "risk_off"   # 약세장 (암호화폐 30% / KRW 70%)
    NEUTRAL = "neutral"     # 횡보장 (기존 비중 유지)


class MarketSeasonFilter:
    """
    시장 계절 필터
    
    BTC 가격과 200주 이동평균선의 관계를 분석하여
    시장 상황(강세장/약세장/횡보장)을 판단합니다.
    """
    
    def __init__(self, buffer_band: float = 0.05):
        """
        Args:
            buffer_band: 완충 밴드 비율 (기본값: 5%)
        """
        self.buffer_band = buffer_band
        self.risk_on_threshold = 1 + buffer_band   # 1.05
        self.risk_off_threshold = 1 - buffer_band  # 0.95
        
        logger.info(f"MarketSeasonFilter 초기화: buffer_band={buffer_band}")
    
    def calculate_200week_ma(self, price_data: pd.DataFrame) -> float:
        """
        200주 이동평균 계산
        
        Args:
            price_data: BTC 가격 데이터 (DataFrame with 'Close' column)
            
        Returns:
            200주 이동평균값
        """
        try:
            # 데이터 유효성 검증
            if price_data.empty or 'Close' not in price_data.columns:
                logger.warning("가격 데이터가 비어있거나 'Close' 컬럼이 없습니다")
                return 50000000.0  # 5천만원 기본값
            
            # Close 컬럼에서 유효한 데이터만 필터링
            valid_prices = price_data['Close'].dropna()
            if len(valid_prices) == 0:
                logger.warning("유효한 가격 데이터가 없습니다")
                return 50000000.0
            
            # 데이터 길이 체크
            if len(valid_prices) < 200:
                logger.warning(f"데이터 부족: {len(valid_prices)}개 < 200개 필요")
                fallback_ma = valid_prices.mean()
                return fallback_ma if not pd.isna(fallback_ma) else 50000000.0
            
            # 인덱스가 datetime인지 확인
            if not isinstance(price_data.index, pd.DatetimeIndex):
                logger.warning("데이터 인덱스가 datetime이 아닙니다. 단순 이동평균 사용")
                # 단순 200개 이동평균으로 대체
                ma_200 = valid_prices.rolling(window=200).mean().iloc[-1]
                return ma_200 if not pd.isna(ma_200) else valid_prices.mean()
            
            # 주간 데이터로 리샘플링
            try:
                weekly_prices = price_data.resample('W')['Close'].last().dropna()
                if len(weekly_prices) < 200:
                    logger.warning(f"주간 데이터 부족: {len(weekly_prices)}주 < 200주")
                    # 일간 데이터로 200개 이동평균 계산 (대략 200일)
                    ma_200d = valid_prices.rolling(window=200).mean().iloc[-1]
                    return ma_200d if not pd.isna(ma_200d) else valid_prices.mean()
                
                # 200주 이동평균 계산
                ma_200w = weekly_prices.rolling(window=200).mean().iloc[-1]
                
                # 결과 검증
                if pd.isna(ma_200w):
                    logger.warning("200주 이동평균 계산 결과가 NaN입니다. 대체값 사용")
                    # 더 짧은 기간의 이동평균으로 대체
                    ma_50w = weekly_prices.rolling(window=50).mean().iloc[-1]
                    if not pd.isna(ma_50w):
                        return ma_50w
                    else:
                        return valid_prices.mean()
                
                logger.debug(f"200주 이동평균: {ma_200w:.2f}")
                return ma_200w
                
            except Exception as resample_error:
                logger.warning(f"리샘플링 실패: {resample_error}. 단순 이동평균 사용")
                ma_200 = valid_prices.rolling(window=200).mean().iloc[-1]
                return ma_200 if not pd.isna(ma_200) else valid_prices.mean()
                
        except Exception as e:
            logger.error(f"200주 이동평균 계산 중 오류: {e}")
            # 최종 fallback - BTC 대략적 평균가
            return 50000000.0  # 5천만원
    
    def determine_market_season(
        self, 
        current_price: float, 
        ma_200w: float,
        previous_season: Optional[MarketSeason] = None
    ) -> Tuple[MarketSeason, Dict]:
        """
        시장 계절 판단
        
        Args:
            current_price: 현재 BTC 가격
            ma_200w: 200주 이동평균
            previous_season: 이전 시장 계절 (횡보장 판단용)
            
        Returns:
            Tuple[MarketSeason, Dict]: (시장계절, 분석정보)
        """
        # NaN 값 처리
        if pd.isna(current_price) or pd.isna(ma_200w) or ma_200w == 0:
            logger.warning(f"잘못된 데이터: price={current_price}, ma_200w={ma_200w}")
            # 기본값으로 NEUTRAL 반환
            analysis_info = {
                "current_price": current_price,
                "ma_200w": ma_200w,
                "price_ratio": None,
                "risk_on_threshold": self.risk_on_threshold,
                "risk_off_threshold": self.risk_off_threshold,
                "timestamp": datetime.now(),
                "market_season": MarketSeason.NEUTRAL.value,
                "season_changed": False,
                "error": "Invalid price data"
            }
            return MarketSeason.NEUTRAL, analysis_info
        
        price_ratio = current_price / ma_200w
        
        analysis_info = {
            "current_price": current_price,
            "ma_200w": ma_200w,
            "price_ratio": price_ratio,
            "risk_on_threshold": self.risk_on_threshold,
            "risk_off_threshold": self.risk_off_threshold,
            "timestamp": datetime.now()
        }
        
        # 시장 계절 판단 로직
        if price_ratio >= self.risk_on_threshold:
            season = MarketSeason.RISK_ON
            logger.info(f"강세장 신호: {price_ratio:.3f} >= {self.risk_on_threshold}")
            
        elif price_ratio <= self.risk_off_threshold:
            season = MarketSeason.RISK_OFF
            logger.info(f"약세장 신호: {price_ratio:.3f} <= {self.risk_off_threshold}")
            
        else:
            # 완충 밴드 내 - 기존 상태 유지
            season = previous_season if previous_season else MarketSeason.NEUTRAL
            logger.info(f"횡보장 (밴드 내): {price_ratio:.3f}, 기존 상태 유지")
        
        analysis_info["market_season"] = season.value
        analysis_info["season_changed"] = (previous_season != season) if previous_season else True
        
        return season, analysis_info
    
    def get_allocation_weights(self, market_season: MarketSeason) -> Dict[str, float]:
        """
        시장 계절에 따른 자산 배분 비중 반환
        
        Args:
            market_season: 시장 계절
            
        Returns:
            자산 배분 비중 딕셔너리
        """
        allocation_map = {
            MarketSeason.RISK_ON: {
                "crypto": 0.70,  # 암호화폐 70%
                "krw": 0.30      # 원화 30%
            },
            MarketSeason.RISK_OFF: {
                "crypto": 0.30,  # 암호화폐 30%
                "krw": 0.70      # 원화 70%
            },
            MarketSeason.NEUTRAL: {
                "crypto": 0.50,  # 중립 상태: 50:50
                "krw": 0.50
            }
        }
        
        weights = allocation_map[market_season]
        logger.info(f"자산 배분 비중: {weights}")
        
        return weights
    
    def analyze_weekly(self, price_data: pd.DataFrame) -> Dict:
        """
        주간 시장 분석 실행
        
        Args:
            price_data: BTC 가격 데이터
            
        Returns:
            분석 결과 딕셔너리
        """
        try:
            # 200주 이동평균 계산
            ma_200w = self.calculate_200week_ma(price_data)
            
            # 현재 가격
            current_price = price_data['Close'].iloc[-1]
            
            # 시장 계절 판단
            season, analysis_info = self.determine_market_season(current_price, ma_200w)
            
            # 자산 배분 비중
            allocation_weights = self.get_allocation_weights(season)
            
            result = {
                "analysis_date": datetime.now(),
                "market_season": season.value,
                "allocation_weights": allocation_weights,
                "analysis_info": analysis_info,
                "success": True
            }
            
            logger.info(f"주간 분석 완료: {season.value}")
            return result
            
        except Exception as e:
            logger.error(f"주간 분석 실패: {e}")
            return {
                "analysis_date": datetime.now(),
                "error": str(e),
                "success": False
            }


# 설정 상수
DEFAULT_BUFFER_BAND = 0.05  # 5% 완충 밴드
ANALYSIS_FREQUENCY = "weekly"  # 주간 분석 