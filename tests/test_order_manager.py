"""
Order Manager Tests

주문 관리자 테스트
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.trading.order_manager import OrderManager, Order, OrderStatus


@pytest.mark.trading
class TestOrderStatus:
    """OrderStatus Enum 테스트"""

    def test_order_status_values(self):
        """주문 상태 값 확인"""
        assert OrderStatus.PENDING.value == "pending"
        assert OrderStatus.SUBMITTED.value == "submitted"
        assert OrderStatus.PARTIALLY_FILLED.value == "partially_filled"
        assert OrderStatus.FILLED.value == "filled"
        assert OrderStatus.CANCELLED.value == "cancelled"
        assert OrderStatus.FAILED.value == "failed"
        assert OrderStatus.EXPIRED.value == "expired"

    def test_order_status_count(self):
        """주문 상태 개수 확인"""
        assert len(OrderStatus) == 7


@pytest.mark.trading
class TestOrder:
    """Order 클래스 테스트"""

    def test_order_init(self):
        """Order 초기화"""
        order = Order(
            order_id="test_001",
            currency="BTC",
            side="buy",
            order_type="market",
            amount=100000
        )

        assert order.order_id == "test_001"
        assert order.currency == "BTC"
        assert order.side == "buy"
        assert order.order_type == "market"
        assert order.amount == 100000
        assert order.price is None
        assert order.status == OrderStatus.PENDING
        assert order.filled_amount == 0.0
        assert order.average_price == 0.0

    def test_order_init_with_price(self):
        """가격 포함 Order 초기화"""
        order = Order(
            order_id="test_002",
            currency="ETH",
            side="sell",
            order_type="limit",
            amount=0.5,
            price=3000000
        )

        assert order.price == 3000000
        assert order.order_type == "limit"

    def test_update_status(self):
        """상태 업데이트"""
        order = Order(
            order_id="test_003",
            currency="BTC",
            side="buy",
            order_type="market",
            amount=50000
        )

        order.update_status(OrderStatus.FILLED, filled_amount=0.001, average_price=50000000)

        assert order.status == OrderStatus.FILLED
        assert order.filled_amount == 0.001
        assert order.average_price == 50000000

    def test_update_status_with_error(self):
        """에러 상태 업데이트"""
        order = Order(
            order_id="test_004",
            currency="BTC",
            side="buy",
            order_type="market",
            amount=50000
        )

        order.update_status(OrderStatus.FAILED, error_message="Insufficient balance")

        assert order.status == OrderStatus.FAILED
        assert order.error_message == "Insufficient balance"

    def test_to_dict(self):
        """딕셔너리 변환"""
        order = Order(
            order_id="test_005",
            currency="BTC",
            side="buy",
            order_type="market",
            amount=100000
        )

        result = order.to_dict()

        assert result["order_id"] == "test_005"
        assert result["currency"] == "BTC"
        assert result["side"] == "buy"
        assert result["status"] == "pending"
        assert "created_at" in result
        assert "updated_at" in result


@pytest.mark.trading
class TestOrderManagerInit:
    """OrderManager 초기화 테스트"""

    def test_init(self):
        """초기화"""
        mock_client = Mock()
        manager = OrderManager(mock_client)

        assert manager.coinone_client == mock_client
        assert manager.active_orders == {}
        assert manager.completed_orders == []
        assert manager.max_retry_attempts == 3

    def test_init_settings(self):
        """설정 값 확인"""
        mock_client = Mock()
        manager = OrderManager(mock_client)

        assert manager.retry_delay == 5
        assert manager.order_timeout == 300
        assert manager.status_check_interval == 10


@pytest.mark.trading
class TestOrderManagerMarketOrder:
    """시장가 주문 테스트"""

    @pytest.fixture
    def mock_client(self):
        """Mock 클라이언트"""
        return Mock()

    @pytest.fixture
    def order_manager(self, mock_client):
        """OrderManager 인스턴스"""
        return OrderManager(mock_client)

    def test_submit_market_order_buy_success(self, order_manager, mock_client):
        """시장가 매수 성공"""
        mock_client.place_order.return_value = {
            "success": True,
            "order_id": "order_123"
        }

        order = order_manager.submit_market_order("BTC", "buy", 100000)

        assert order is not None
        assert order.order_id == "order_123"
        assert order.status == OrderStatus.SUBMITTED
        assert order.currency == "BTC"
        assert order.side == "buy"
        assert order.amount == 100000

    def test_submit_market_order_sell_success(self, order_manager, mock_client):
        """시장가 매도 성공"""
        mock_client.place_order.return_value = {
            "success": True,
            "order_id": "order_456"
        }

        order = order_manager.submit_market_order("ETH", "sell", 0.5)

        assert order is not None
        assert order.side == "sell"
        assert order.amount == 0.5

    def test_submit_market_order_failure(self, order_manager, mock_client):
        """시장가 주문 실패"""
        mock_client.place_order.return_value = {
            "success": False,
            "error_code": "103",
            "error_msg": "Lack of Balance"
        }

        order = order_manager.submit_market_order("BTC", "buy", 1000000000)

        assert order is not None
        assert order.status == OrderStatus.FAILED
        assert "103" in order.error_message

    def test_submit_market_order_exception(self, order_manager, mock_client):
        """시장가 주문 예외"""
        mock_client.place_order.side_effect = Exception("Network error")

        order = order_manager.submit_market_order("BTC", "buy", 100000)

        assert order is None

    def test_submit_market_order_amount_in_krw(self, order_manager, mock_client):
        """매수 시 KRW 금액으로 전달 확인"""
        mock_client.place_order.return_value = {"success": True, "order_id": "test"}

        order_manager.submit_market_order("BTC", "buy", 100000)

        # place_order 호출 시 amount_in_krw=True 확인
        call_kwargs = mock_client.place_order.call_args[1]
        assert call_kwargs["amount_in_krw"] is True


@pytest.mark.trading
class TestOrderManagerLimitOrder:
    """지정가 주문 테스트"""

    @pytest.fixture
    def mock_client(self):
        """Mock 클라이언트"""
        return Mock()

    @pytest.fixture
    def order_manager(self, mock_client):
        """OrderManager 인스턴스"""
        return OrderManager(mock_client)

    def test_submit_limit_order_success(self, order_manager, mock_client):
        """지정가 주문 성공"""
        mock_client.place_order.return_value = {
            "result": "success",
            "order_id": "limit_001"
        }

        order = order_manager.submit_limit_order("BTC", "buy", 100000, 50000000)

        assert order is not None
        assert order.order_id == "limit_001"
        assert order.order_type == "limit"
        assert order.price == 50000000

    def test_submit_limit_order_failure(self, order_manager, mock_client):
        """지정가 주문 실패"""
        mock_client.place_order.return_value = {
            "result": "error",
            "error_code": "405"
        }

        order = order_manager.submit_limit_order("BTC", "buy", 100, 50000000)

        assert order is None

    def test_submit_limit_order_exception(self, order_manager, mock_client):
        """지정가 주문 예외"""
        mock_client.place_order.side_effect = Exception("API error")

        order = order_manager.submit_limit_order("BTC", "buy", 100000, 50000000)

        assert order is None


@pytest.mark.trading
class TestOrderManagerCancelOrder:
    """주문 취소 테스트"""

    @pytest.fixture
    def mock_client(self):
        """Mock 클라이언트"""
        return Mock()

    @pytest.fixture
    def order_manager(self, mock_client):
        """OrderManager 인스턴스"""
        return OrderManager(mock_client)

    def test_cancel_order_success(self, order_manager, mock_client):
        """주문 취소 성공"""
        # 먼저 주문 생성
        mock_client.place_order.return_value = {"success": True, "order_id": "cancel_001"}
        order = order_manager.submit_market_order("BTC", "buy", 100000)

        # 취소 응답 설정
        mock_client.cancel_order.return_value = {"result": "success"}

        result = order_manager.cancel_order("cancel_001")

        assert result is True

    def test_cancel_order_not_found(self, order_manager, mock_client):
        """존재하지 않는 주문 취소"""
        result = order_manager.cancel_order("nonexistent_order")

        assert result is False
        mock_client.cancel_order.assert_not_called()

    def test_cancel_order_failure(self, order_manager, mock_client):
        """주문 취소 실패"""
        # 먼저 주문 생성
        mock_client.place_order.return_value = {"success": True, "order_id": "fail_cancel"}
        order_manager.submit_market_order("BTC", "buy", 100000)

        # 취소 실패 응답
        mock_client.cancel_order.return_value = {"result": "error"}

        result = order_manager.cancel_order("fail_cancel")

        assert result is False


@pytest.mark.trading
class TestOrderManagerStatus:
    """주문 상태 확인 테스트"""

    @pytest.fixture
    def mock_client(self):
        """Mock 클라이언트"""
        return Mock()

    @pytest.fixture
    def order_manager(self, mock_client):
        """OrderManager 인스턴스"""
        return OrderManager(mock_client)

    def test_check_order_status_filled(self, order_manager, mock_client):
        """체결 완료 상태 확인"""
        # 주문 생성
        mock_client.place_order.return_value = {"success": True, "order_id": "status_001"}
        order_manager.submit_market_order("BTC", "buy", 100000)

        # 상태 확인 응답
        mock_client.get_order_status.return_value = {
            "result": "success",
            "status": "filled"
        }

        status = order_manager.check_order_status("status_001")

        assert status == OrderStatus.FILLED

    def test_check_order_status_pending(self, order_manager, mock_client):
        """대기 상태 확인"""
        mock_client.place_order.return_value = {"success": True, "order_id": "status_002"}
        order_manager.submit_market_order("BTC", "buy", 100000)

        mock_client.get_order_status.return_value = {
            "result": "success",
            "status": "pending"
        }

        status = order_manager.check_order_status("status_002")

        assert status == OrderStatus.SUBMITTED

    def test_check_order_status_not_found(self, order_manager, mock_client):
        """존재하지 않는 주문"""
        status = order_manager.check_order_status("nonexistent")

        assert status is None


@pytest.mark.trading
class TestOrderManagerActiveOrders:
    """활성 주문 관리 테스트"""

    @pytest.fixture
    def mock_client(self):
        """Mock 클라이언트"""
        return Mock()

    @pytest.fixture
    def order_manager(self, mock_client):
        """OrderManager 인스턴스"""
        return OrderManager(mock_client)

    def test_active_orders_tracking(self, order_manager, mock_client):
        """활성 주문 추적"""
        mock_client.place_order.side_effect = [
            {"success": True, "order_id": "active_001"},
            {"success": True, "order_id": "active_002"}
        ]

        order_manager.submit_market_order("BTC", "buy", 100000)
        order_manager.submit_market_order("ETH", "buy", 50000)

        assert len(order_manager.active_orders) == 2

    def test_get_order_from_active(self, order_manager, mock_client):
        """활성 주문에서 조회"""
        mock_client.place_order.return_value = {"success": True, "order_id": "get_001"}

        order_manager.submit_market_order("BTC", "buy", 100000)

        order = order_manager.active_orders.get("get_001")

        assert order is not None
        assert order.currency == "BTC"


@pytest.mark.trading
class TestOrderManagerEdgeCases:
    """엣지 케이스 테스트"""

    @pytest.fixture
    def mock_client(self):
        """Mock 클라이언트"""
        return Mock()

    @pytest.fixture
    def order_manager(self, mock_client):
        """OrderManager 인스턴스"""
        return OrderManager(mock_client)

    def test_multiple_orders_same_currency(self, order_manager, mock_client):
        """같은 코인 여러 주문"""
        mock_client.place_order.side_effect = [
            {"success": True, "order_id": "btc_001"},
            {"success": True, "order_id": "btc_002"}
        ]

        order1 = order_manager.submit_market_order("BTC", "buy", 100000)
        order2 = order_manager.submit_market_order("BTC", "sell", 0.002)

        assert order1.order_id != order2.order_id
        assert len(order_manager.active_orders) == 2

    def test_order_with_zero_amount(self, order_manager, mock_client):
        """0 금액 주문 (경계값)"""
        mock_client.place_order.return_value = {
            "success": False,
            "error_code": "405",
            "error_msg": "Invalid amount"
        }

        order = order_manager.submit_market_order("BTC", "buy", 0)

        # 실패 주문으로 처리
        assert order.status == OrderStatus.FAILED

    def test_order_id_generation_on_missing(self, order_manager, mock_client):
        """order_id 없을 때 생성"""
        mock_client.place_order.return_value = {
            "success": True
            # order_id 없음
        }

        order = order_manager.submit_market_order("BTC", "buy", 100000)

        # 자동 생성된 ID 확인
        assert order is not None
        assert order.order_id.startswith("market_BTC_")
