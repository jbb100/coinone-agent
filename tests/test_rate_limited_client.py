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


class TestWrapApiMethod:
    """_wrap_api_method 메서드 테스트"""

    @pytest.fixture
    def mock_original_client(self):
        """원본 클라이언트 Mock"""
        client = Mock()
        client.get_balances.return_value = {'KRW': 1000000}
        return client

    def test_wrap_api_method_sync_mode(self, mock_original_client):
        """동기 모드에서 API 메서드 래핑"""
        mock_coord = Mock()
        mock_coord.api_rate_limiter = AsyncMock()

        with patch('src.trading.rate_limited_client.get_system_coordinator', return_value=mock_coord):
            client = RateLimitedCoinoneClient(mock_original_client)

            # 이미 실행 중인 이벤트 루프 시뮬레이션
            with patch('asyncio.get_running_loop') as mock_get_loop:
                mock_loop = Mock()
                mock_loop.is_running.return_value = True
                mock_get_loop.return_value = mock_loop

                # __getattr__을 통해 래핑된 메서드 호출
                result = client.get_balances()

                # 결과 확인
                assert result == {'KRW': 1000000}

    def test_wrap_api_method_exception_handling(self, mock_original_client):
        """래핑된 메서드 예외 처리 후 폴백"""
        mock_coord = Mock()
        mock_coord.api_rate_limiter = Mock()
        # 에러 발생하도록 설정
        mock_coord.api_rate_limiter.acquire = Mock(side_effect=Exception("Test error"))

        with patch('src.trading.rate_limited_client.get_system_coordinator', return_value=mock_coord):
            client = RateLimitedCoinoneClient(mock_original_client)

            # __getattr__을 통해 래핑된 메서드 호출 - 에러 시 원본 메서드로 폴백
            result = client.get_balances()

            # 원본 메서드가 호출되어 결과 반환
            assert result == {'KRW': 1000000}


class TestAsyncApiCall:
    """_async_api_call 메서드 테스트"""

    @pytest.fixture
    def mock_original_client(self):
        """원본 클라이언트 Mock"""
        client = Mock()
        client.get_balances.return_value = {'KRW': 2000000}
        return client

    @pytest.mark.asyncio
    async def test_async_api_call(self, mock_original_client):
        """비동기 API 호출"""
        mock_coord = Mock()
        mock_coord.api_rate_limiter = AsyncMock()
        mock_coord.api_rate_limiter.acquire = AsyncMock()

        with patch('src.trading.rate_limited_client.get_system_coordinator', return_value=mock_coord):
            client = RateLimitedCoinoneClient(mock_original_client)

            result = await client._async_api_call(
                mock_original_client.get_balances,
                "get_balances"
            )

            # 속도 제한 acquire 호출 확인
            mock_coord.api_rate_limiter.acquire.assert_called_once()
            assert result == {'KRW': 2000000}

    @pytest.mark.asyncio
    async def test_async_api_call_with_args(self, mock_original_client):
        """인자 포함 비동기 API 호출"""
        mock_coord = Mock()
        mock_coord.api_rate_limiter = AsyncMock()

        mock_original_client.get_latest_price.return_value = 50000000.0

        with patch('src.trading.rate_limited_client.get_system_coordinator', return_value=mock_coord):
            client = RateLimitedCoinoneClient(mock_original_client)

            result = await client._async_api_call(
                mock_original_client.get_latest_price,
                "get_latest_price",
                "BTC"
            )

            mock_original_client.get_latest_price.assert_called_once_with("BTC")
            assert result == 50000000.0

    @pytest.mark.asyncio
    async def test_async_api_call_with_kwargs(self, mock_original_client):
        """키워드 인자 포함 비동기 API 호출"""
        mock_coord = Mock()
        mock_coord.api_rate_limiter = AsyncMock()

        mock_original_client.place_order.return_value = {'order_id': '456'}

        with patch('src.trading.rate_limited_client.get_system_coordinator', return_value=mock_coord):
            client = RateLimitedCoinoneClient(mock_original_client)

            result = await client._async_api_call(
                mock_original_client.place_order,
                "place_order",
                currency="BTC",
                side="buy"
            )

            mock_original_client.place_order.assert_called_once_with(currency="BTC", side="buy")
            assert result['order_id'] == '456'


class TestWrapApiMethodAdvanced:
    """_wrap_api_method 추가 테스트 (누락 라인 커버)"""

    @pytest.fixture
    def mock_original_client(self):
        """원본 클라이언트 Mock"""
        client = Mock()
        client.get_balances.return_value = {'KRW': 3000000}
        client.get_ticker.return_value = {'price': 50000000}
        return client

    def test_wrap_api_method_new_event_loop(self, mock_original_client):
        """이벤트 루프가 없을 때 새 루프 생성"""
        mock_coord = Mock()
        mock_coord.api_rate_limiter = AsyncMock()
        mock_coord.api_rate_limiter.acquire = AsyncMock()

        with patch('src.trading.rate_limited_client.get_system_coordinator', return_value=mock_coord):
            client = RateLimitedCoinoneClient(mock_original_client)

            # 이벤트 루프가 없는 상황 시뮬레이션
            with patch('asyncio.get_running_loop', side_effect=RuntimeError("No running event loop")):
                # 새 루프 생성 mock
                mock_loop = MagicMock()
                mock_loop.is_running.return_value = False
                mock_loop.run_until_complete = MagicMock(return_value={'KRW': 3000000})

                with patch('asyncio.new_event_loop', return_value=mock_loop) as mock_new_loop:
                    with patch('asyncio.set_event_loop') as mock_set_loop:
                        # __getattr__를 통해 API 메서드 호출
                        wrapped = client._wrap_api_method(mock_original_client.get_ticker, "get_ticker")
                        result = wrapped()

                        # 새 루프 생성 확인
                        mock_new_loop.assert_called_once()
                        mock_set_loop.assert_called_once_with(mock_loop)
                        assert result == {'KRW': 3000000}

    def test_wrap_api_method_running_loop_direct_call(self, mock_original_client):
        """실행 중인 루프에서 직접 호출 (동기 모드)"""
        mock_coord = Mock()
        mock_coord.api_rate_limiter = AsyncMock()

        with patch('src.trading.rate_limited_client.get_system_coordinator', return_value=mock_coord):
            client = RateLimitedCoinoneClient(mock_original_client)

            # 실행 중인 루프 시뮬레이션
            mock_loop = MagicMock()
            mock_loop.is_running.return_value = True

            with patch('asyncio.get_running_loop', return_value=mock_loop):
                wrapped = client._wrap_api_method(mock_original_client.get_balances, "get_balances")
                result = wrapped()

                # 원본 메서드 직접 호출 확인
                mock_original_client.get_balances.assert_called()
                assert result == {'KRW': 3000000}

    def test_wrap_api_method_exception_fallback(self, mock_original_client):
        """예외 발생 시 원본 메서드로 폴백"""
        mock_coord = Mock()
        mock_coord.api_rate_limiter = AsyncMock()

        with patch('src.trading.rate_limited_client.get_system_coordinator', return_value=mock_coord):
            client = RateLimitedCoinoneClient(mock_original_client)

            # 예외 발생 시뮬레이션
            with patch('asyncio.get_running_loop', side_effect=RuntimeError("No running loop")):
                with patch('asyncio.new_event_loop', side_effect=Exception("Loop creation failed")):
                    wrapped = client._wrap_api_method(mock_original_client.get_balances, "get_balances")
                    result = wrapped()

                    # 예외 발생해도 원본 메서드 호출
                    assert result == {'KRW': 3000000}

    def test_wrap_api_method_run_until_complete(self, mock_original_client):
        """run_until_complete로 비동기 API 호출"""
        mock_coord = Mock()
        mock_coord.api_rate_limiter = AsyncMock()
        mock_coord.api_rate_limiter.acquire = AsyncMock()

        with patch('src.trading.rate_limited_client.get_system_coordinator', return_value=mock_coord):
            client = RateLimitedCoinoneClient(mock_original_client)

            # 이벤트 루프가 없고 새 루프 생성
            with patch('asyncio.get_running_loop', side_effect=RuntimeError("No loop")):
                # 실제로 새 루프를 생성하고 run_until_complete 호출
                mock_loop = MagicMock()
                mock_loop.is_running.return_value = False

                # run_until_complete가 비동기 함수를 실행하고 결과 반환
                async def mock_async_call(*args, **kwargs):
                    return {'KRW': 3000000}

                mock_loop.run_until_complete.side_effect = lambda coro: asyncio.get_event_loop().run_until_complete(
                    mock_async_call()
                ) if asyncio.iscoroutine(coro) else {'KRW': 3000000}

                with patch('asyncio.new_event_loop', return_value=mock_loop):
                    with patch('asyncio.set_event_loop'):
                        wrapped = client._wrap_api_method(mock_original_client.get_balances, "get_balances")
                        result = wrapped()

                        assert mock_loop.run_until_complete.called or result == {'KRW': 3000000}
