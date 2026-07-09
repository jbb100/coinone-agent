"""
External API Client

외부 API 통합 클라이언트 (Fear & Greed Index, 환율, BTC 도미넌스, MVRV 등)
"""

import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from loguru import logger

from src.utils.constants import (
    API_REQUEST_TIMEOUT
)


class ExternalAPIClient:
    """
    외부 API 통합 클라이언트

    Fear & Greed Index, 환율, BTC 도미넌스 등 외부 데이터를 수집합니다.
    캐싱 및 폴백 로직을 포함합니다.
    """

    # API Endpoints
    FEAR_GREED_API = "https://api.alternative.me/fng/"
    EXCHANGE_RATE_API = "https://api.exchangerate-api.com/v4/latest/USD"
    BTC_DOMINANCE_API = "https://api.coingecko.com/api/v3/global"

    # Cache durations (seconds)
    FEAR_GREED_CACHE_DURATION = 3600  # 1 hour
    EXCHANGE_RATE_CACHE_DURATION = 3600  # 1 hour
    BTC_DOMINANCE_CACHE_DURATION = 1800  # 30 minutes

    def __init__(self, timeout: int = API_REQUEST_TIMEOUT):
        """
        Args:
            timeout: API 요청 타임아웃 (초)
        """
        self.timeout = timeout

        # Cache storage
        self._cache: Dict[str, Dict[str, Any]] = {}

        logger.info("ExternalAPIClient 초기화 완료")

    def get_fear_greed_index(self) -> Optional[int]:
        """
        Fear & Greed Index 조회

        Returns:
            Fear & Greed Index (0-100) 또는 None (실패 시)
        """
        cache_key = "fear_greed"

        # 캐시 확인
        cached = self._get_cached(cache_key, self.FEAR_GREED_CACHE_DURATION)
        if cached is not None:
            return cached

        try:
            response = requests.get(
                self.FEAR_GREED_API,
                timeout=self.timeout
            )

            if response.status_code == 429:  # Rate limited
                logger.warning("Fear & Greed API 호출 빈도 초과")
                return None

            if response.status_code != 200:
                logger.warning(f"Fear & Greed API 응답 오류: {response.status_code}")
                return None

            data = response.json()

            if "data" not in data or not data["data"]:
                logger.warning("Fear & Greed API 잘못된 응답 형식")
                return None

            value = int(data["data"][0]["value"])

            # 캐시 저장
            self._set_cache(cache_key, value)

            logger.debug(f"Fear & Greed Index: {value}")
            return value

        except requests.Timeout:
            logger.warning("Fear & Greed API 타임아웃")
            return None
        except Exception as e:
            logger.error(f"Fear & Greed API 오류: {e}")
            return None

    def get_usd_krw_rate(self) -> Optional[float]:
        """
        USD/KRW 환율 조회

        Returns:
            USD/KRW 환율 또는 None (실패 시 — 폴백 상수 금지)
        """
        cache_key = "usd_krw_rate"

        # 캐시 확인
        cached = self._get_cached(cache_key, self.EXCHANGE_RATE_CACHE_DURATION)
        if cached is not None:
            return cached

        try:
            response = requests.get(
                self.EXCHANGE_RATE_API,
                timeout=self.timeout
            )

            if response.status_code != 200:
                logger.warning(f"환율 API 응답 오류: {response.status_code}")
                return None

            data = response.json()

            # exchangerate-api.com 형식
            if "rates" in data and "KRW" in data["rates"]:
                rate = float(data["rates"]["KRW"])
            # 다른 형식 (conversion_rate)
            elif "conversion_rate" in data:
                rate = float(data["conversion_rate"])
            else:
                logger.warning("환율 API 잘못된 응답 형식")
                return None

            # 합리적 범위 검증 (1000~2000 KRW)
            if not (1000 <= rate <= 2000):
                logger.warning(f"환율 API 비정상 값: {rate}")
                return None

            # 캐시 저장
            self._set_cache(cache_key, rate)

            logger.debug(f"USD/KRW 환율: {rate}")
            return rate

        except requests.Timeout:
            logger.warning("환율 API 타임아웃")
            return None
        except Exception as e:
            logger.error(f"환율 API 오류: {e}")
            return None

    def get_btc_dominance(self) -> Optional[float]:
        """
        BTC 도미넌스 조회

        Returns:
            BTC 도미넌스 (0-1 범위) 또는 None (실패 시 — 폴백 상수 금지)
        """
        cache_key = "btc_dominance"

        # 캐시 확인
        cached = self._get_cached(cache_key, self.BTC_DOMINANCE_CACHE_DURATION)
        if cached is not None:
            return cached

        try:
            response = requests.get(
                self.BTC_DOMINANCE_API,
                timeout=self.timeout
            )

            if response.status_code != 200:
                logger.warning(f"BTC 도미넌스 API 응답 오류: {response.status_code}")
                return None

            data = response.json()

            # CoinGecko 형식
            if "data" in data and "bitcoin_dominance" in data["data"]:
                dominance_percent = float(data["data"]["bitcoin_dominance"])
                dominance = dominance_percent / 100  # 퍼센트를 비율로 변환

                # 캐시 저장
                self._set_cache(cache_key, dominance)

                logger.debug(f"BTC 도미넌스: {dominance:.2%}")
                return dominance
            else:
                logger.warning("BTC 도미넌스 API 잘못된 응답 형식")
                return None

        except requests.Timeout:
            logger.warning("BTC 도미넌스 API 타임아웃")
            return None
        except Exception as e:
            logger.error(f"BTC 도미넌스 API 오류: {e}")
            return None

    def get_mvrv_ratio(self) -> Optional[float]:
        """
        MVRV (Market Value to Realized Value) 비율 조회

        Returns:
            MVRV 비율 또는 None (API 미지원 또는 실패 시)
        """
        cache_key = "mvrv"

        # 캐시 확인
        cached = self._get_cached(cache_key, 3600)  # 1시간 캐시
        if cached is not None:
            return cached

        try:
            # MVRV는 무료 API가 제한적이므로 여기서는 기본 구현만 제공
            # 실제로는 Glassnode, CryptoQuant 등 유료 API 필요
            response = requests.get(
                "https://api.blockchain.info/charts/mvrv",
                params={"format": "json", "timespan": "1days"},
                timeout=self.timeout
            )

            if response.status_code != 200:
                return None

            data = response.json()

            if "values" in data and data["values"]:
                mvrv = float(data["values"][-1]["y"])
                self._set_cache(cache_key, mvrv)
                return mvrv

            # 다른 형식 처리
            if "mvrv" in data:
                mvrv = float(data["mvrv"])
                self._set_cache(cache_key, mvrv)
                return mvrv

            return None

        except Exception as e:
            logger.debug(f"MVRV API 오류 (예상된 실패): {e}")
            return None

    def check_api_health(self) -> Dict[str, bool]:
        """
        API 상태 확인

        Returns:
            각 API의 정상 여부
        """
        health = {}

        # Fear & Greed API
        try:
            response = requests.get(
                self.FEAR_GREED_API,
                timeout=5
            )
            health["fear_greed"] = response.status_code == 200
        except Exception:
            health["fear_greed"] = False

        # Exchange Rate API
        try:
            response = requests.get(
                self.EXCHANGE_RATE_API,
                timeout=5
            )
            health["exchange_rate"] = response.status_code == 200
        except Exception:
            health["exchange_rate"] = False

        # BTC Dominance API
        try:
            response = requests.get(
                self.BTC_DOMINANCE_API,
                timeout=5
            )
            health["btc_dominance"] = response.status_code == 200
        except Exception:
            health["btc_dominance"] = False

        return health

    def clear_cache(self):
        """캐시 초기화"""
        self._cache.clear()
        logger.debug("API 캐시 초기화됨")

    def _get_cached(self, key: str, max_age_seconds: int) -> Optional[Any]:
        """
        캐시에서 값 조회

        Args:
            key: 캐시 키
            max_age_seconds: 캐시 유효 시간 (초)

        Returns:
            캐시된 값 또는 None
        """
        if key not in self._cache:
            return None

        cache_entry = self._cache[key]
        cached_at = cache_entry.get("timestamp")
        value = cache_entry.get("value")

        if cached_at is None:
            return None

        age = (datetime.now() - cached_at).total_seconds()

        if age > max_age_seconds:
            return None

        return value

    def _set_cache(self, key: str, value: Any):
        """
        캐시에 값 저장

        Args:
            key: 캐시 키
            value: 저장할 값
        """
        self._cache[key] = {
            "value": value,
            "timestamp": datetime.now()
        }
