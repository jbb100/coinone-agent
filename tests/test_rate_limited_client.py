"""
Rate Limited Client 테스트 모듈

속도 제한 클라이언트 래퍼 테스트
"""

import pytest
import asyncio
from unittest.mock import Mock, MagicMock, patch, AsyncMock

from src.trading.rate_limited_client import (
    RateLimitedCoinoneClient,
    create_rate_limited_client
)


class TestRateLimitedCoinoneClient:
    """RateLimitedCoinoneClient 클래스 테스트"""

    @pytest.fixture
    def mock_original_client(self):
        """원본 Coinone 클라이언트 Mock"""
        client = Mock()
        client.get_account_info.return_value = {'account': 'info'}
        client.get_balances.return_value = {'KRW': 1000000, 'BTC': 0.1}
        client.get_portfolio_value.return_value = {'total': 5000000}
        client.place_order.return_value = {'order_id': '123', 'status': 'success'}
        client.get_latest_price.return_value = 50000000.0
        client.cancel_order.return_value = {'success': True}
        client.get_order_status.return_value = {'status': 'filled'}
        return client

    @pytest.fixture
    def mock_system_coordinator(self):
        """시스템 코디네이터 Mock"""
        coordinator = Mock()
        coordinator.api_rate_limiter = AsyncMock()
        coordinator.api_rate_limiter.acquire = AsyncMock()
        return coordinator

    @pytest.fixture
    def client(self, mock_original_client, mock_system_coordinator):
        """RateLimitedCoinoneClient 인스턴스"""
        with patch('src.trading.rate_limited_client.get_system_coordinator',
                   return_value=mock_system_coordinator):
            return RateLimitedCoinoneClient(mock_original_client)

    def test_init(self, client, mock_original_client):
        """초기화 테스트"""
        assert client.original_client is mock_original_client

    def test_get_account_info(self, client, mock_original_client):
        """계정 정보 조회 - 원본 메서드 호출"""
        result = client.get_account_info()

        assert result == {'account': 'info'}
        mock_original_client.get_account_info.assert_called_once()

    def test_get_balances(self, client, mock_original_client):
        """잔고 조회"""
        result = client.get_balances()

        assert 'KRW' in result
        assert 'BTC' in result
        mock_original_client.get_balances.assert_called_once()

    def test_get_portfolio_value(self, client, mock_original_client):
        """포트폴리오 가치 조회"""
        result = client.get_portfolio_value()

        assert result == {'total': 5000000}
        mock_original_client.get_portfolio_value.assert_called_once()

    def test_place_order(self, client, mock_original_client):
        """주문 실행"""
        result = client.place_order(currency='BTC', side='buy', amount=0.01)

        assert result['order_id'] == '123'
        mock_original_client.place_order.assert_called_once()

    def test_get_latest_price(self, client, mock_original_client):
        """최신 가격 조회"""
        result = client.get_latest_price('BTC')

        assert result == 50000000.0
        mock_original_client.get_latest_price.assert_called_once_with('BTC')

    def test_cancel_order(self, client, mock_original_client):
        """주문 취소"""
        result = client.cancel_order('123')

        assert result['success'] is True
        mock_original_client.cancel_order.assert_called_once_with('123')

    def test_get_order_status(self, client, mock_original_client):
        """주문 상태 조회"""
        result = client.get_order_status('123')

        assert result['status'] == 'filled'
        mock_original_client.get_order_status.assert_called_once_with('123')

    def test_getattr_non_api_method(self, client, mock_original_client):
        """API가 아닌 메서드 접근"""
        mock_original_client.some_helper_method = Mock(return_value='helper_result')

        result = client.some_helper_method()

        # API 메서드가 아니면 래핑 없이 직접 호출
        assert result == 'helper_result'

    def test_getattr_property(self, client, mock_original_client):
        """속성 접근"""
        mock_original_client.some_property = 'property_value'

        result = client.some_property

        assert result == 'property_value'


class TestCreateRateLimitedClient:
    """create_rate_limited_client 함수 테스트"""

    def test_creates_wrapper(self):
        """래퍼 생성 확인"""
        original = Mock()

        with patch('src.trading.rate_limited_client.get_system_coordinator'):
            wrapped = create_rate_limited_client(original)

        assert isinstance(wrapped, RateLimitedCoinoneClient)
        assert wrapped.original_client is original

    def test_preserves_original_methods(self):
        """원본 메서드 보존 확인"""
        original = Mock()
        original.get_balances.return_value = {'KRW': 1000000}

        with patch('src.trading.rate_limited_client.get_system_coordinator'):
            wrapped = create_rate_limited_client(original)

        result = wrapped.get_balances()
        assert result == {'KRW': 1000000}


class TestRateLimitedClientApiMethods:
    """API 메서드 래핑 테스트"""

    @pytest.fixture
    def mock_original_client(self):
        """원본 클라이언트 Mock"""
        client = Mock()
        # 모든 API 메서드 설정
        client.get_account_info.return_value = {}
        client.get_balances.return_value = {}
        client.get_portfolio_value.return_value = {}
        client.place_order.return_value = {}
        client.cancel_order.return_value = {}
        client.get_order_status.return_value = {}
        client.get_latest_price.return_value = 0
        client.get_orderbook.return_value = {}
        client.get_ticker.return_value = {}
        client.get_orders_history.return_value = []
        client.get_order_info.return_value = {}
        client.get_user_info.return_value = {}
        client.submit_market_order.return_value = {}
        client.submit_limit_order.return_value = {}
        return client

    def test_api_methods_are_wrapped(self, mock_original_client):
        """API 메서드들이 래핑되는지 확인"""
        api_methods = [
            'get_account_info', 'get_balances', 'get_portfolio_value',
            'place_order', 'cancel_order', 'get_order_status',
            'get_latest_price', 'get_orderbook', 'get_ticker',
            'get_orders_history', 'get_order_info', 'get_user_info',
            'submit_market_order', 'submit_limit_order'
        ]

        with patch('src.trading.rate_limited_client.get_system_coordinator'):
            client = RateLimitedCoinoneClient(mock_original_client)

            for method_name in api_methods:
                method = getattr(client, method_name)
                # callable 확인
                assert callable(method), f"{method_name} should be callable"


class TestRateLimitedClientErrorHandling:
    """에러 처리 테스트"""

    def test_fallback_on_rate_limit_error(self):
        """속도 제한 에러 시 폴백"""
        original = Mock()
        original.get_balances.return_value = {'KRW': 1000000}

        with patch('src.trading.rate_limited_client.get_system_coordinator') as mock_coord:
            # 속도 제한에서 에러 발생
            mock_coord.return_value.api_rate_limiter.acquire.side_effect = Exception("Rate limit error")

            client = RateLimitedCoinoneClient(original)
            result = client.get_balances()

            # 에러 시에도 원본 메서드 호출
            assert result == {'KRW': 1000000}

    def test_handles_original_client_error(self):
        """원본 클라이언트 에러 처리"""
        original = Mock()
        original.get_balances.side_effect = Exception("API Error")

        with patch('src.trading.rate_limited_client.get_system_coordinator'):
            client = RateLimitedCoinoneClient(original)

            with pytest.raises(Exception) as excinfo:
                client.get_balances()

            assert "API Error" in str(excinfo.value)


class TestRateLimitingActuallyApplied:
    """운영 회귀 방지: 명시적 패스스루 메서드가 __getattr__ 래핑을 가려
    거래 경로 전체가 무제한이던 버그 — 모든 API 메서드는 리미터를 거쳐야 함"""

    @pytest.fixture
    def mock_coord(self):
        coordinator = Mock()
        coordinator.api_rate_limiter = AsyncMock()
        coordinator.api_rate_limiter.acquire = AsyncMock()
        return coordinator

    def make_client(self, original, coord):
        with patch('src.trading.rate_limited_client.get_system_coordinator',
                   return_value=coord):
            return RateLimitedCoinoneClient(original)

    def test_trading_path_methods_go_through_limiter(self, mock_coord):
        """place_order·get_order_status 등 파이프라인이 쓰는 모든 호출이
        rate limiter acquire를 거쳐야 함"""
        original = Mock()
        original.place_order.return_value = {'success': True}
        original.get_order_status.return_value = {}
        original.cancel_order.return_value = {}
        original.get_latest_price.return_value = 1.0
        original.get_balances.return_value = {}
        client = self.make_client(original, mock_coord)

        client.place_order(currency='BTC', side='buy', amount=0.01)
        client.get_order_status('123', 'BTC')
        client.cancel_order('123', 'BTC')
        client.get_latest_price('BTC')
        client.get_balances()

        assert mock_coord.api_rate_limiter.acquire.call_count == 5

    def test_method_called_exactly_once_when_limiter_fails(self, mock_coord):
        """리미터 획득 실패는 호출을 막지 않되, 메서드는 정확히 1회만 —
        폴백 재호출로 주문이 이중 제출되던 결함 회귀 방지"""
        mock_coord.api_rate_limiter.acquire = AsyncMock(
            side_effect=Exception("limiter down")
        )
        original = Mock()
        original.place_order.return_value = {'success': True}
        client = self.make_client(original, mock_coord)

        result = client.place_order(currency='BTC', side='buy', amount=0.01)

        assert result == {'success': True}
        assert original.place_order.call_count == 1

    def test_method_exception_propagates_without_second_call(self, mock_coord):
        """원본 메서드 실패 시 예외 전파 — 부작용 있는 호출의 이중 실행 금지"""
        original = Mock()
        original.place_order.side_effect = Exception("API Error")
        client = self.make_client(original, mock_coord)

        with pytest.raises(Exception, match="API Error"):
            client.place_order(currency='BTC', side='buy', amount=0.01)

        assert original.place_order.call_count == 1

    def test_non_api_attributes_not_wrapped(self, mock_coord):
        """네트워크 호출이 아닌 헬퍼(get_price_unit 등)는 리미터 미적용"""
        original = Mock()
        original.get_price_unit.return_value = 1000.0
        client = self.make_client(original, mock_coord)

        assert client.get_price_unit('BTC', 100.0) == 1000.0
        mock_coord.api_rate_limiter.acquire.assert_not_called()
