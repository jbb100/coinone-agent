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


def season_from_string(value: Optional[str]) -> Optional[MarketSeason]:
    """DB 등에 저장된 문자열을 MarketSeason으로 변환 (알 수 없으면 None)"""
    if not value:
        return None
    season_map = {
        "risk_on": MarketSeason.RISK_ON,
        "risk_off": MarketSeason.RISK_OFF,
        "neutral": MarketSeason.NEUTRAL
    }
    return season_map.get(str(value).lower())


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
    
    def calculate_200week_ma(self, price_data: pd.DataFrame) -> Optional[float]:
        """
        200주 이동평균 계산

        실제 200주 이상의 주간 데이터가 있을 때만 계산한다.
        데이터가 부족하거나 유효하지 않으면 임의 값으로 대체하지 않고 None을 반환한다
        (다른 기간의 MA는 완전히 다른 지표이므로 대체 금지 — fail-safe 원칙).

        Args:
            price_data: BTC 가격 데이터 (DataFrame with 'Close' column, DatetimeIndex)

        Returns:
            200주 이동평균값 또는 None (계산 불가)
        """
        try:
            # 데이터 유효성 검증
            if price_data.empty or 'Close' not in price_data.columns:
                logger.error("200주 MA 계산 불가: 가격 데이터가 비어있거나 'Close' 컬럼이 없습니다")
                return None

            valid_prices = price_data['Close'].dropna()
            if len(valid_prices) == 0:
                logger.error("200주 MA 계산 불가: 유효한 가격 데이터가 없습니다")
                return None

            # 인덱스가 datetime이어야 주간 리샘플링이 가능
            if not isinstance(price_data.index, pd.DatetimeIndex):
                logger.error("200주 MA 계산 불가: 데이터 인덱스가 DatetimeIndex가 아닙니다")
                return None

            # 주간 데이터로 리샘플링
            weekly_prices = price_data.resample('W')['Close'].last().dropna()
            if len(weekly_prices) < 200:
                logger.error(f"200주 MA 계산 불가: 주간 데이터 부족 ({len(weekly_prices)}주 < 200주)")
                return None

            ma_200w = weekly_prices.rolling(window=200).mean().iloc[-1]

            if pd.isna(ma_200w) or ma_200w <= 0:
                logger.error(f"200주 MA 계산 불가: 결과가 유효하지 않음 ({ma_200w})")
                return None

            logger.debug(f"200주 이동평균: {ma_200w:.2f}")
            return float(ma_200w)

        except Exception as e:
            logger.error(f"200주 이동평균 계산 중 오류: {e}")
            return None
    
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
        # NaN 값 처리: 데이터가 유효하지 않으면 직전 상태를 유지한다 (임의 판단 금지)
        if current_price is None or ma_200w is None or pd.isna(current_price) or pd.isna(ma_200w) or ma_200w == 0:
            logger.error(f"시장 계절 판단 불가 (잘못된 데이터): price={current_price}, ma_200w={ma_200w}")
            fallback_season = previous_season if previous_season else MarketSeason.NEUTRAL
            analysis_info = {
                "current_price": current_price,
                "ma_200w": ma_200w,
                "price_ratio": None,
                "risk_on_threshold": self.risk_on_threshold,
                "risk_off_threshold": self.risk_off_threshold,
                "timestamp": datetime.now(),
                "market_season": fallback_season.value,
                "season_changed": False,
                "error": "Invalid price data"
            }
            return fallback_season, analysis_info
        
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
    
    def get_allocation_weights(
        self,
        market_season: MarketSeason,
        current_crypto_weight: Optional[float] = None
    ) -> Dict[str, float]:
        """
        시장 계절에 따른 자산 배분 비중 반환

        NEUTRAL(완충 밴드 내)은 "기존 비중 유지"를 의미한다:
        현재 비중이 주어지면 그대로 유지하고, 없을 때(최초 실행)만 50:50을 사용한다.

        Args:
            market_season: 시장 계절
            current_crypto_weight: 현재 암호화폐 비중 (NEUTRAL 시 유지용)

        Returns:
            자산 배분 비중 딕셔너리
        """
        if market_season == MarketSeason.RISK_ON:
            weights = {"crypto": 0.70, "krw": 0.30}
        elif market_season == MarketSeason.RISK_OFF:
            weights = {"crypto": 0.30, "krw": 0.70}
        else:  # NEUTRAL: 기존 비중 유지
            if current_crypto_weight is not None:
                # 극단값 방지를 위해 RISK_OFF~RISK_ON 범위로 제한
                crypto = max(0.30, min(0.70, current_crypto_weight))
                weights = {"crypto": crypto, "krw": 1.0 - crypto}
                logger.info(f"NEUTRAL: 기존 암호화폐 비중 {crypto:.1%} 유지")
            else:
                weights = {"crypto": 0.50, "krw": 0.50}

        logger.info(f"자산 배분 비중: {weights}")

        return weights
    
    def analyze_weekly(
        self,
        price_data: pd.DataFrame,
        previous_season: Optional[MarketSeason] = None,
        current_crypto_weight: Optional[float] = None
    ) -> Dict:
        """
        주간 시장 분석 실행

        Args:
            price_data: BTC 가격 데이터
            previous_season: 직전 시장 계절 (완충 밴드 히스테리시스용 — DB의 최근 분석 결과)
            current_crypto_weight: 현재 암호화폐 비중 (NEUTRAL 시 유지용)

        Returns:
            분석 결과 딕셔너리 (계산 불가 시 success=False, 거래 판단에 사용 금지)
        """
        try:
            # 200주 이동평균 계산 (실데이터 기준, 불가 시 None)
            ma_200w = self.calculate_200week_ma(price_data)

            if ma_200w is None:
                logger.error("주간 분석 중단: 200주 이동평균 계산 불가 — 시장 판단을 내리지 않습니다")
                return {
                    "analysis_date": datetime.now(),
                    "error": "200주 이동평균 계산 불가 (데이터 부족/유효하지 않음)",
                    "success": False
                }

            # 현재 가격
            current_price = price_data['Close'].iloc[-1]

            # 시장 계절 판단 (직전 계절 전달 → 완충 밴드 내에서는 직전 상태 유지)
            season, analysis_info = self.determine_market_season(
                current_price, ma_200w, previous_season=previous_season
            )

            # 자산 배분 비중
            allocation_weights = self.get_allocation_weights(season, current_crypto_weight)
            
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