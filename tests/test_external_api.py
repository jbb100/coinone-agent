"""
Tests for External API Integration - TDD Phase 4

Fear & Greed Index, 환율 API, 데이터 소스 우선순위 테스트
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import requests

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))


# ============================================================================
# TestFearGreedAPI - Fear & Greed Index API 테스트
# ============================================================================

class TestFearGreedAPI:
    """Fear & Greed Index API 테스트 클래스"""

    def test_api_success(self):
        """API 정상 응답"""
        from src.utils.external_api_client import ExternalAPIClient

        client = ExternalAPIClient()

        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "data": [{"value": "25", "value_classification": "Extreme Fear"}]
            }
            mock_get.return_value = mock_response

            result = client.get_fear_greed_index()

            assert result == 25
            assert mock_get.called

    def test_api_failure_fallback(self):
        """API 실패 시 자체 계산 폴백"""
        from src.utils.external_api_client import ExternalAPIClient

        client = ExternalAPIClient()

        with patch('requests.get') as mock_get:
            mock_get.side_effect = Exception("API Error")

            result = client.get_fear_greed_index()

            # 폴백 값은 None 또는 기본값
            assert result is None or (0 <= result <= 100)

    def test_api_timeout(self):
        """API 타임아웃 처리"""
        from src.utils.external_api_client import ExternalAPIClient

        client = ExternalAPIClient()

        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.Timeout()

            result = client.get_fear_greed_index()

            # 타임아웃 시에도 None 또는 기본값 반환
            assert result is None or (0 <= result <= 100)

    def test_api_invalid_response(self):
        """API 잘못된 응답 처리"""
        from src.utils.external_api_client import ExternalAPIClient

        client = ExternalAPIClient()

        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"invalid": "data"}
            mock_get.return_value = mock_response

            result = client.get_fear_greed_index()

            # 잘못된 응답 시 None 반환
            assert result is None

    def test_api_rate_limiting(self):
        """API 호출 빈도 제한"""
        from src.utils.external_api_client import ExternalAPIClient

        client = ExternalAPIClient()

        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 429  # Too Many Requests
            mock_get.return_value = mock_response

            result = client.get_fear_greed_index()

            assert result is None

    def test_fear_greed_caching(self):
        """Fear & Greed 캐싱 테스트"""
        from src.utils.external_api_client import ExternalAPIClient

        client = ExternalAPIClient()

        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "data": [{"value": "50", "value_classification": "Neutral"}]
            }
            mock_get.return_value = mock_response

            # 첫 번째 호출
            result1 = client.get_fear_greed_index()
            # 두 번째 호출 (캐시에서 반환)
            result2 = client.get_fear_greed_index()

            assert result1 == result2 == 50
            # 캐시가 동작하면 API는 1번만 호출됨
            assert mock_get.call_count == 1


# ============================================================================
# TestExchangeRateAPI - 환율 API 테스트
# ============================================================================

class TestExchangeRateAPI:
    """환율 API 테스트 클래스"""

    def test_rate_api_success(self):
        """환율 API 정상 응답"""
        from src.utils.external_api_client import ExternalAPIClient

        client = ExternalAPIClient()

        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "conversion_rate": 1350.0
            }
            mock_get.return_value = mock_response

            rate = client.get_usd_krw_rate()

            assert rate == 1350.0

    def test_rate_api_fallback(self):
        """환율 API 실패 시 기본값"""
        from src.utils.external_api_client import ExternalAPIClient
        from src.utils.constants import DEFAULT_USD_KRW_RATE

        client = ExternalAPIClient()

        with patch('requests.get') as mock_get:
            mock_get.side_effect = Exception("API Error")

            rate = client.get_usd_krw_rate()

            assert rate == DEFAULT_USD_KRW_RATE

    def test_rate_api_timeout(self):
        """환율 API 타임아웃 처리"""
        from src.utils.external_api_client import ExternalAPIClient
        from src.utils.constants import DEFAULT_USD_KRW_RATE

        client = ExternalAPIClient()

        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.Timeout()

            rate = client.get_usd_krw_rate()

            assert rate == DEFAULT_USD_KRW_RATE

    def test_rate_caching(self):
        """환율 캐싱 테스트"""
        from src.utils.external_api_client import ExternalAPIClient

        client = ExternalAPIClient()

        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"conversion_rate": 1380.0}
            mock_get.return_value = mock_response

            rate1 = client.get_usd_krw_rate()
            rate2 = client.get_usd_krw_rate()

            assert rate1 == rate2 == 1380.0
            # 캐시가 동작하면 API는 1번만 호출됨
            assert mock_get.call_count == 1

    def test_rate_reasonable_range(self):
        """환율 합리적 범위 검증"""
        from src.utils.external_api_client import ExternalAPIClient

        client = ExternalAPIClient()

        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"conversion_rate": 1350.0}
            mock_get.return_value = mock_response

            rate = client.get_usd_krw_rate()

            # 환율은 합리적 범위 내여야 함 (1000~2000 KRW)
            assert 1000 <= rate <= 2000


# ============================================================================
# TestBTCDominanceAPI - BTC 도미넌스 API 테스트
# ============================================================================

class TestBTCDominanceAPI:
    """BTC 도미넌스 API 테스트 클래스"""

    def test_dominance_api_success(self):
        """BTC 도미넌스 API 정상 응답"""
        from src.utils.external_api_client import ExternalAPIClient

        client = ExternalAPIClient()

        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "data": {"bitcoin_dominance": 52.5}
            }
            mock_get.return_value = mock_response

            dominance = client.get_btc_dominance()

            assert dominance == 0.525  # 52.5% -> 0.525

    def test_dominance_api_fallback(self):
        """BTC 도미넌스 API 실패 시 기본값"""
        from src.utils.external_api_client import ExternalAPIClient
        from src.utils.constants import DEFAULT_BTC_DOMINANCE

        client = ExternalAPIClient()

        with patch('requests.get') as mock_get:
            mock_get.side_effect = Exception("API Error")

            dominance = client.get_btc_dominance()

            assert dominance == DEFAULT_BTC_DOMINANCE


# ============================================================================
# TestMVRVAPI - MVRV API 테스트
# ============================================================================

class TestMVRVAPI:
    """MVRV API 테스트 클래스"""

    def test_mvrv_api_success(self):
        """MVRV API 정상 응답"""
        from src.utils.external_api_client import ExternalAPIClient

        client = ExternalAPIClient()

        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "mvrv": 1.5
            }
            mock_get.return_value = mock_response

            mvrv = client.get_mvrv_ratio()

            assert mvrv == 1.5

    def test_mvrv_api_fallback(self):
        """MVRV API 실패 시 None 반환"""
        from src.utils.external_api_client import ExternalAPIClient

        client = ExternalAPIClient()

        with patch('requests.get') as mock_get:
            mock_get.side_effect = Exception("API Error")

            mvrv = client.get_mvrv_ratio()

            assert mvrv is None


# ============================================================================
# TestAPIHealthCheck - API 상태 확인 테스트
# ============================================================================

class TestAPIHealthCheck:
    """API 상태 확인 테스트 클래스"""

    def test_health_check_all_healthy(self):
        """모든 API 정상 시 상태"""
        from src.utils.external_api_client import ExternalAPIClient

        client = ExternalAPIClient()

        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            health = client.check_api_health()

            assert "fear_greed" in health
            assert "exchange_rate" in health

    def test_health_check_partial_failure(self):
        """일부 API 실패 시 상태"""
        from src.utils.external_api_client import ExternalAPIClient

        client = ExternalAPIClient()

        def side_effect(*args, **kwargs):
            url = args[0] if args else kwargs.get('url', '')
            if 'alternative.me' in url:
                raise Exception("API Error")
            mock_response = Mock()
            mock_response.status_code = 200
            return mock_response

        with patch('requests.get', side_effect=side_effect):
            health = client.check_api_health()

            assert health["fear_greed"] == False
            assert health["exchange_rate"] == True


# ============================================================================
# TestExternalAPIClient - 클라이언트 통합 테스트
# ============================================================================

class TestExternalAPIClient:
    """External API Client 통합 테스트"""

    def test_client_initialization(self):
        """클라이언트 초기화"""
        from src.utils.external_api_client import ExternalAPIClient

        client = ExternalAPIClient()

        assert client is not None
        assert hasattr(client, 'get_fear_greed_index')
        assert hasattr(client, 'get_usd_krw_rate')
        assert hasattr(client, 'get_btc_dominance')

    def test_client_with_custom_timeout(self):
        """커스텀 타임아웃 설정"""
        from src.utils.external_api_client import ExternalAPIClient

        client = ExternalAPIClient(timeout=5)

        assert client.timeout == 5

    def test_client_cache_clear(self):
        """캐시 초기화"""
        from src.utils.external_api_client import ExternalAPIClient

        client = ExternalAPIClient()

        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "data": [{"value": "30", "value_classification": "Fear"}]
            }
            mock_get.return_value = mock_response

            # 첫 호출
            client.get_fear_greed_index()

            # 캐시 클리어
            client.clear_cache()

            # 두 번째 호출 (캐시 없으므로 API 재호출)
            client.get_fear_greed_index()

            assert mock_get.call_count == 2
