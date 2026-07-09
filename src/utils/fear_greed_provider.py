"""
Fear & Greed Index Provider

alternative.me의 실제 Crypto Fear & Greed Index를 조회하는 모듈.

원칙 (real-data-only):
- 실제 API 값 또는 24시간 이내 캐시만 사용한다.
- 조회 불가 시 변동성/RSI 등으로 "추정한 가짜 지수"를 만들지 않고 None을 반환한다.
  호출부는 None이면 공포탐욕 관련 조정을 적용하지 않아야 한다 (중립 처리).
"""

from datetime import datetime, timedelta
from typing import Optional

import requests
from loguru import logger

FNG_API_URL = "https://api.alternative.me/fng/"
CACHE_MAX_AGE_HOURS = 24
REQUEST_TIMEOUT_SECONDS = 10


class FearGreedProvider:
    """실제 공포탐욕지수(0-100) 제공자"""

    def __init__(self, db_manager=None):
        """
        Args:
            db_manager: 데이터베이스 매니저 (캐싱용, 없으면 API 직접 조회만)
        """
        self.db_manager = db_manager

    def get_index(self) -> Optional[int]:
        """
        공포탐욕지수 조회 (0=극도의 공포, 100=극도의 탐욕)

        Returns:
            지수 값 또는 None (실데이터 조회 불가 — 호출부는 중립 처리해야 함)
        """
        # 1. API 조회
        value = self._fetch_from_api()
        if value is not None:
            self._save_cache(value)
            return value

        # 2. 캐시 (24시간 이내)
        cached = self._load_cache()
        if cached is not None:
            logger.info(f"캐시된 공포탐욕지수 사용: {cached}")
            return cached

        logger.warning("공포탐욕지수 조회 불가 (API 실패, 캐시 없음) — 중립 처리 필요")
        return None

    def _fetch_from_api(self) -> Optional[int]:
        """alternative.me API에서 최신 지수 조회"""
        try:
            response = requests.get(
                FNG_API_URL,
                params={"limit": 1, "format": "json"},
                timeout=REQUEST_TIMEOUT_SECONDS
            )
            response.raise_for_status()
            data = response.json()

            entries = data.get("data", [])
            if not entries:
                logger.warning("공포탐욕지수 API 응답에 데이터가 없습니다")
                return None

            value = int(entries[0]["value"])
            if not 0 <= value <= 100:
                logger.warning(f"공포탐욕지수 값이 범위를 벗어남: {value}")
                return None

            logger.info(f"공포탐욕지수 조회 성공: {value} ({entries[0].get('value_classification', '')})")
            return value

        except Exception as e:
            logger.warning(f"공포탐욕지수 API 조회 실패: {e}")
            return None

    def _save_cache(self, value: int):
        """지수를 DB에 캐시"""
        if not self.db_manager:
            return
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS fear_greed_cache (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        value INTEGER NOT NULL,
                        fetched_at TEXT NOT NULL
                    )
                """)
                cursor.execute(
                    "INSERT INTO fear_greed_cache (value, fetched_at) VALUES (?, ?)",
                    (value, datetime.now().isoformat())
                )
                # 오래된 캐시 정리 (30일 이상)
                old_cutoff = datetime.now() - timedelta(days=30)
                cursor.execute(
                    "DELETE FROM fear_greed_cache WHERE fetched_at < ?",
                    (old_cutoff.isoformat(),)
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"공포탐욕지수 캐시 저장 실패: {e}")

    def _load_cache(self) -> Optional[int]:
        """24시간 이내 캐시 조회"""
        if not self.db_manager:
            return None
        try:
            cutoff = datetime.now() - timedelta(hours=CACHE_MAX_AGE_HOURS)
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT value FROM fear_greed_cache
                    WHERE fetched_at > ?
                    ORDER BY fetched_at DESC
                    LIMIT 1
                """, (cutoff.isoformat(),))
                row = cursor.fetchone()
                if row:
                    return int(row["value"])
            return None
        except Exception as e:
            logger.warning(f"공포탐욕지수 캐시 조회 실패: {e}")
            return None
