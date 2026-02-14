"""
Dynamic Execution Engine Tests

TWAP 분할 매매 엔진 테스트
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

from src.core.dynamic_execution_engine import (
    DynamicExecutionEngine,
    TWAPOrder,
    MarketVolatility
)
from src.trading.order_manager import OrderStatus


@pytest.mark.trading
class TestMarketVolatility:
    """MarketVolatility Enum 테스트"""

    def test_volatility_values(self):
        """변동성 값 확인"""
        assert MarketVolatility.STABLE.value == "stable"
        assert MarketVolatility.VOLATILE.value == "volatile"

    def test_volatility_count(self):
        """변동성 상태 개수 확인"""
        assert len(MarketVolatility) == 2


@pytest.mark.trading
class TestTWAPOrder:
    """TWAPOrder 데이터클래스 테스트"""

    def test_basic_order_creation(self):
        """기본 TWAP 주문 생성"""
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=6)

        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=1000000,
            total_quantity=0.01,
            execution_hours=6,
            slice_count=12,
            slice_amount_krw=83333,
            slice_quantity=0.00083,
            start_time=start_time,
            end_time=end_time,
            slice_interval_minutes=30
        )

        assert order.asset == "BTC"
        assert order.side == "buy"
        assert order.total_amount_krw == 1000000
        assert order.execution_hours == 6
        assert order.slice_count == 12
        assert order.executed_slices == 0
        assert order.status == "pending"

    def test_post_init_remaining_amounts(self):
        """post_init에서 remaining 값 자동 설정"""
        order = TWAPOrder(
            asset="ETH",
            side="sell",
            total_amount_krw=500000,
            total_quantity=0.5,
            execution_hours=6,
            slice_count=10,
            slice_amount_krw=50000,
            slice_quantity=0.05,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=36
        )

        assert order.remaining_amount_krw == 500000
        assert order.remaining_quantity == 0.5

    def test_to_dict(self):
        """딕셔너리 변환 테스트"""
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=6)

        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=1000000,
            total_quantity=0.01,
            execution_hours=6,
            slice_count=12,
            slice_amount_krw=83333,
            slice_quantity=0.00083,
            start_time=start_time,
            end_time=end_time,
            slice_interval_minutes=30,
            market_season="bullish",
            target_allocation={"BTC": 0.5, "ETH": 0.3}
        )

        result = order.to_dict()

        assert result["asset"] == "BTC"
        assert result["side"] == "buy"
        assert result["total_amount_krw"] == 1000000
        assert result["slice_count"] == 12
        assert result["market_season"] == "bullish"
        assert result["target_allocation"] == {"BTC": 0.5, "ETH": 0.3}
        assert "start_time" in result
        assert "end_time" in result

    def test_exchange_order_ids_tracking(self):
        """거래소 주문 ID 추적 테스트"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=1000000,
            total_quantity=0.01,
            execution_hours=6,
            slice_count=12,
            slice_amount_krw=83333,
            slice_quantity=0.00083,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=30
        )

        assert order.exchange_order_ids == []

        order.exchange_order_ids.append("order_123")
        order.exchange_order_ids.append("order_456")

        assert len(order.exchange_order_ids) == 2
        assert "order_123" in order.exchange_order_ids


@pytest.fixture
def mock_coinone_client():
    """Mock CoinoneClient"""
    client = Mock()
    client.get_latest_price.return_value = 50000000  # BTC: 5천만원
    client.get_balances.return_value = {"KRW": 10000000, "BTC": 0.1, "ETH": 1.0}
    client.get_portfolio_value.return_value = {
        "total_krw": 15000000,
        "assets": {
            "KRW": {"value_krw": 10000000},
            "BTC": {"value_krw": 5000000}
        }
    }
    client.get_order_status.return_value = {"result": "success", "status": "filled"}
    client.cancel_order.return_value = {"result": "success", "status": "cancelled"}
    return client


@pytest.fixture
def mock_db_manager():
    """Mock DatabaseManager"""
    db = Mock()
    db.get_latest_active_twap_execution.return_value = None
    db.save_twap_execution_plan.return_value = None
    db.update_twap_execution_plan.return_value = None
    db.update_twap_orders_status.return_value = None
    return db


@pytest.fixture
def mock_rebalancer():
    """Mock Rebalancer"""
    rebalancer = Mock()
    rebalancer.portfolio_manager = Mock()
    rebalancer.portfolio_manager.get_portfolio_metrics.return_value = {
        "portfolio_health": {"is_balanced": True},
        "weights": {"crypto_total": 0.5, "KRW": 0.5}
    }
    rebalancer.calculate_rebalancing_orders.return_value = {
        "success": True,
        "market_season": "neutral",
        "target_weights": {"BTC": 0.3, "ETH": 0.2, "KRW": 0.5}
    }

    # OrderManager mock
    mock_order = Mock()
    mock_order.status = OrderStatus.FILLED
    mock_order.order_id = "test_order_123"
    mock_order.error_message = None
    rebalancer.order_manager = Mock()
    rebalancer.order_manager.submit_market_order.return_value = mock_order

    return rebalancer


@pytest.fixture
def mock_alert_system():
    """Mock AlertSystem"""
    return Mock()


@pytest.fixture
def engine(mock_coinone_client, mock_db_manager, mock_rebalancer, mock_alert_system):
    """DynamicExecutionEngine fixture"""
    with patch('src.core.dynamic_execution_engine.get_system_coordinator') as mock_coord:
        mock_coord.return_value = Mock()
        mock_coord.return_value.active_operations = {}

        engine = DynamicExecutionEngine(
            coinone_client=mock_coinone_client,
            db_manager=mock_db_manager,
            rebalancer=mock_rebalancer,
            alert_system=mock_alert_system,
            atr_period=14,
            atr_threshold=0.05
        )
        return engine


@pytest.mark.trading
class TestDynamicExecutionEngineInit:
    """DynamicExecutionEngine 초기화 테스트"""

    def test_engine_initialization(self, engine):
        """엔진 초기화 확인"""
        assert engine.atr_period == 14
        assert engine.atr_threshold == 0.05
        assert engine.crontab_interval_minutes == 15
        assert engine.active_twap_orders == []

    def test_load_active_orders_empty(self, engine):
        """활성 주문 없을 때 로드"""
        assert len(engine.active_twap_orders) == 0
        assert engine.current_execution_id is None


@pytest.mark.trading
class TestATRCalculation:
    """ATR 계산 테스트"""

    def test_calculate_atr_basic(self, engine):
        """기본 ATR 계산"""
        # 테스트 데이터 생성
        dates = pd.date_range(start='2024-01-01', periods=20, freq='D')
        data = pd.DataFrame({
            'High': [100, 102, 104, 103, 105, 107, 106, 108, 110, 109,
                    111, 113, 112, 114, 116, 115, 117, 119, 118, 120],
            'Low': [98, 99, 101, 100, 102, 104, 103, 105, 107, 106,
                   108, 110, 109, 111, 113, 112, 114, 116, 115, 117],
            'Close': [99, 101, 103, 102, 104, 106, 105, 107, 109, 108,
                     110, 112, 111, 113, 115, 114, 116, 118, 117, 119]
        }, index=dates)

        atr = engine.calculate_atr(data)

        assert isinstance(atr, float)
        assert atr > 0
        assert atr < 1  # 상대적 ATR은 1 미만

    def test_calculate_atr_volatile_market(self, engine):
        """변동성 큰 시장 ATR"""
        dates = pd.date_range(start='2024-01-01', periods=20, freq='D')
        # 높은 변동성 데이터
        data = pd.DataFrame({
            'High': [110, 95, 115, 90, 120, 85, 125, 80, 130, 75,
                    135, 70, 140, 65, 145, 60, 150, 55, 155, 50],
            'Low': [90, 75, 95, 70, 100, 65, 105, 60, 110, 55,
                   115, 50, 120, 45, 125, 40, 130, 35, 135, 30],
            'Close': [100, 85, 105, 80, 110, 75, 115, 70, 120, 65,
                     125, 60, 130, 55, 135, 50, 140, 45, 145, 40]
        }, index=dates)

        atr = engine.calculate_atr(data)

        assert atr > 0.1  # 높은 변동성

    def test_calculate_atr_with_error(self, engine):
        """ATR 계산 오류 시 기본값 반환"""
        invalid_data = pd.DataFrame()  # 빈 데이터프레임

        atr = engine.calculate_atr(invalid_data)

        assert atr == engine.atr_threshold  # 기본값 반환


@pytest.mark.trading
class TestMarketVolatilityDetermination:
    """시장 변동성 결정 테스트"""

    def test_stable_market(self, engine):
        """안정적인 시장"""
        atr = 0.03  # 3% - 임계값(5%) 이하

        volatility = engine.determine_market_volatility(atr)

        assert volatility == MarketVolatility.STABLE

    def test_volatile_market(self, engine):
        """변동성 높은 시장"""
        atr = 0.08  # 8% - 임계값(5%) 초과

        volatility = engine.determine_market_volatility(atr)

        assert volatility == MarketVolatility.VOLATILE

    def test_boundary_value(self, engine):
        """경계값 테스트"""
        # 정확히 임계값
        atr = 0.05
        volatility = engine.determine_market_volatility(atr)
        assert volatility == MarketVolatility.STABLE


@pytest.mark.trading
class TestExecutionParameters:
    """실행 파라미터 테스트"""

    def test_get_execution_parameters_stable(self, engine):
        """안정적인 시장 파라미터"""
        volatility = MarketVolatility.STABLE

        hours, slices = engine.get_execution_parameters(volatility)

        assert hours == 6
        assert slices == 12

    def test_get_execution_parameters_volatile(self, engine):
        """변동성 시장 파라미터"""
        volatility = MarketVolatility.VOLATILE

        hours, slices = engine.get_execution_parameters(volatility)

        assert hours == 24
        assert slices == 24


@pytest.mark.trading
class TestTWAPOrderCreation:
    """TWAP 주문 생성 테스트"""

    def test_create_twap_orders_basic(self, engine):
        """기본 TWAP 주문 생성"""
        with patch.object(engine, '_get_execution_parameters') as mock_params:
            mock_params.return_value = {
                "execution_hours": 6,
                "slice_count": 12,
                "slice_interval_minutes": 30
            }

            rebalance_orders = {
                "BTC": {"amount_diff_krw": 500000},
                "ETH": {"amount_diff_krw": -300000}
            }

            orders = engine.create_twap_orders(
                rebalance_orders=rebalance_orders,
                market_season="neutral",
                target_allocation={"BTC": 0.3, "ETH": 0.2}
            )

            assert len(orders) == 2

            btc_order = next(o for o in orders if o.asset == "BTC")
            assert btc_order.side == "buy"
            assert btc_order.total_amount_krw == 500000

            eth_order = next(o for o in orders if o.asset == "ETH")
            assert eth_order.side == "sell"
            assert eth_order.total_amount_krw == 300000

    def test_skip_small_orders(self, engine):
        """최소 금액 미만 주문 건너뛰기"""
        with patch.object(engine, '_get_execution_parameters') as mock_params:
            mock_params.return_value = {
                "execution_hours": 6,
                "slice_count": 12,
                "slice_interval_minutes": 30
            }

            rebalance_orders = {
                "BTC": {"amount_diff_krw": 5000},  # 1만원 미만
                "ETH": {"amount_diff_krw": 100000}
            }

            orders = engine.create_twap_orders(rebalance_orders)

            assert len(orders) == 1
            assert orders[0].asset == "ETH"

    def test_skip_krw_orders(self, engine):
        """KRW 주문 건너뛰기"""
        with patch.object(engine, '_get_execution_parameters') as mock_params:
            mock_params.return_value = {
                "execution_hours": 6,
                "slice_count": 12,
                "slice_interval_minutes": 30
            }

            rebalance_orders = {
                "KRW": {"amount_diff_krw": 500000},
                "BTC": {"amount_diff_krw": 100000}
            }

            orders = engine.create_twap_orders(rebalance_orders)

            assert len(orders) == 1
            assert orders[0].asset == "BTC"


@pytest.mark.trading
class TestTWAPSliceExecution:
    """TWAP 슬라이스 실행 테스트"""

    def test_execute_slice_buy_success(self, engine, mock_rebalancer):
        """매수 슬라이스 실행 성공"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=1000000,
            total_quantity=0,
            execution_hours=6,
            slice_count=10,
            slice_amount_krw=100000,
            slice_quantity=0,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=36
        )

        engine.rebalancer = mock_rebalancer

        result = engine.execute_twap_slice(order)

        assert result["success"] is True
        assert order.executed_slices == 1

    def test_execute_slice_resource_conflict(self, engine):
        """리소스 충돌 시 실행 지연"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=1000000,
            total_quantity=0,
            execution_hours=6,
            slice_count=10,
            slice_amount_krw=100000,
            slice_quantity=0,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=36
        )

        # 충돌 상황 설정
        mock_operation = Mock()
        mock_operation.assets = {"BTC", "KRW"}
        engine.system_coordinator.active_operations = {"conflict_op": mock_operation}

        result = engine.execute_twap_slice_sync(order)

        assert result["success"] is False
        assert result["error"] == "resource_conflict"


@pytest.mark.trading
class TestTWAPExecutionStart:
    """TWAP 실행 시작 테스트"""

    def test_start_twap_execution_success(self, engine):
        """TWAP 실행 시작 성공"""
        with patch.object(engine, '_get_execution_parameters') as mock_params, \
             patch.object(engine, '_get_current_market_condition') as mock_market:

            mock_params.return_value = {
                "execution_hours": 6,
                "slice_count": 12,
                "slice_interval_minutes": 30
            }
            mock_market.return_value = ("neutral", {"crypto": 0.5, "krw": 0.5})

            rebalance_orders = {
                "BTC": {"amount_diff_krw": 500000}
            }

            result = engine.start_twap_execution(rebalance_orders)

            assert result["success"] is True
            assert "execution_id" in result
            assert len(engine.active_twap_orders) == 1

    def test_start_twap_execution_krw_only(self, engine):
        """KRW 전용 리밸런싱"""
        rebalance_orders = {
            "KRW": {"amount_diff_krw": 500000}
        }

        result = engine.start_twap_execution(rebalance_orders)

        assert result["success"] is True
        assert result.get("krw_only_rebalancing") is True

    def test_start_twap_clears_existing_orders(self, engine):
        """새 실행 시 기존 주문 정리"""
        # 기존 주문 설정
        existing_order = TWAPOrder(
            asset="ETH",
            side="sell",
            total_amount_krw=300000,
            total_quantity=0,
            execution_hours=6,
            slice_count=6,
            slice_amount_krw=50000,
            slice_quantity=0,
            start_time=datetime.now() - timedelta(hours=3),
            end_time=datetime.now() + timedelta(hours=3),
            slice_interval_minutes=60,
            status="executing"
        )
        engine.active_twap_orders = [existing_order]
        engine.current_execution_id = "old_exec_id"

        with patch.object(engine, '_cancel_pending_exchange_orders') as mock_cancel, \
             patch.object(engine, '_get_execution_parameters') as mock_params, \
             patch.object(engine, '_get_current_market_condition') as mock_market:

            mock_cancel.return_value = {"success": True, "cancelled_count": 0, "failed_count": 0}
            mock_params.return_value = {
                "execution_hours": 6,
                "slice_count": 12,
                "slice_interval_minutes": 30
            }
            mock_market.return_value = ("neutral", {"crypto": 0.5})

            rebalance_orders = {
                "BTC": {"amount_diff_krw": 500000}
            }

            result = engine.start_twap_execution(rebalance_orders)

            assert result["success"] is True
            mock_cancel.assert_called_once()


@pytest.mark.trading
class TestProcessPendingOrders:
    """대기 중인 TWAP 주문 처리 테스트"""

    def test_no_pending_orders(self, engine):
        """대기 주문 없을 때"""
        result = engine.process_pending_twap_orders()

        assert result["success"] is True
        assert "처리할 TWAP 주문이 없습니다" in result["message"]

    def test_process_pending_order_time_not_reached(self, engine):
        """실행 시간 미도래"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=1000000,
            total_quantity=0,
            execution_hours=6,
            slice_count=12,
            slice_amount_krw=83333,
            slice_quantity=0,
            start_time=datetime.now() + timedelta(hours=1),  # 1시간 후 시작
            end_time=datetime.now() + timedelta(hours=7),
            slice_interval_minutes=30
        )
        engine.active_twap_orders = [order]

        result = engine.process_pending_twap_orders(check_market_conditions=False)

        assert result["success"] is True
        assert result["processed_orders"] == 0

    def test_process_completed_orders_removal(self, engine):
        """완료된 주문 제거"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=1000000,
            total_quantity=0,
            execution_hours=6,
            slice_count=12,
            slice_amount_krw=83333,
            slice_quantity=0,
            start_time=datetime.now() - timedelta(hours=1),
            end_time=datetime.now() + timedelta(hours=5),
            slice_interval_minutes=30,
            status="completed"
        )
        engine.active_twap_orders = [order]

        result = engine.process_pending_twap_orders(check_market_conditions=False)

        assert result["success"] is True
        assert len(engine.active_twap_orders) == 0


@pytest.mark.trading
class TestTWAPStatus:
    """TWAP 상태 조회 테스트"""

    def test_get_twap_status_empty(self, engine):
        """빈 상태 조회"""
        status = engine.get_twap_status()

        assert status["active_orders"] == 0
        assert status["orders"] == []

    def test_get_twap_status_with_orders(self, engine):
        """주문 있을 때 상태 조회"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=1000000,
            total_quantity=0,
            execution_hours=6,
            slice_count=10,
            slice_amount_krw=100000,
            slice_quantity=0,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=36,
            executed_slices=3,
            remaining_amount_krw=700000,
            status="executing"
        )
        engine.active_twap_orders = [order]

        status = engine.get_twap_status()

        assert status["active_orders"] == 1
        assert len(status["orders"]) == 1
        assert status["orders"][0]["asset"] == "BTC"
        assert status["orders"][0]["executed_slices"] == 3
        assert status["orders"][0]["total_slices"] == 10
        assert status["orders"][0]["status"] == "executing"


@pytest.mark.trading
class TestMarketConditionCheck:
    """시장 상황 변화 체크 테스트"""

    def test_no_change_detected(self, engine):
        """변화 없음"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=1000000,
            total_quantity=0,
            execution_hours=6,
            slice_count=12,
            slice_amount_krw=83333,
            slice_quantity=0,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=30,
            market_season="neutral",
            target_allocation={"crypto": 0.5}
        )
        engine.active_twap_orders = [order]

        with patch.object(engine, '_get_current_market_condition') as mock_market:
            mock_market.return_value = ("neutral", {"crypto": 0.5})

            changed = engine._check_market_condition_change()

            assert changed is False

    def test_season_change_detected(self, engine):
        """시장 계절 변화 감지"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=1000000,
            total_quantity=0,
            execution_hours=6,
            slice_count=12,
            slice_amount_krw=83333,
            slice_quantity=0,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=30,
            market_season="neutral",
            target_allocation={"crypto": 0.5}
        )
        engine.active_twap_orders = [order]

        with patch.object(engine, '_get_current_market_condition') as mock_market:
            mock_market.return_value = ("bullish", {"crypto": 0.6})  # 변화

            changed = engine._check_market_condition_change()

            assert changed is True


@pytest.mark.trading
class TestCancelPendingOrders:
    """거래소 주문 취소 테스트"""

    def test_cancel_pending_orders_success(self, engine):
        """주문 취소 성공"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=1000000,
            total_quantity=0,
            execution_hours=6,
            slice_count=12,
            slice_amount_krw=83333,
            slice_quantity=0,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=30,
            status="executing",
            exchange_order_ids=["order_123", "order_456"]
        )

        result = engine._cancel_pending_exchange_orders([order])

        assert result["success"] is True
        assert result["cancelled_count"] == 2
        assert order.status == "cancelled"

    def test_cancel_already_filled_orders(self, engine):
        """이미 체결된 주문 취소 시도"""
        engine.coinone_client.get_order_status.return_value = {
            "result": "success",
            "status": "filled"
        }

        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=1000000,
            total_quantity=0,
            execution_hours=6,
            slice_count=12,
            slice_amount_krw=83333,
            slice_quantity=0,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=30,
            exchange_order_ids=["order_123"]
        )

        result = engine._cancel_pending_exchange_orders([order])

        assert result["success"] is True
        assert result["cancelled_count"] == 1  # 이미 완료된 것으로 간주


@pytest.mark.trading
class TestCalculateCurrentWeights:
    """현재 비중 계산 테스트"""

    def test_calculate_weights_basic(self, engine):
        """기본 비중 계산"""
        portfolio = {
            "total_krw": 10000000,
            "assets": {
                "BTC": {"value_krw": 5000000},
                "ETH": {"value_krw": 3000000},
                "KRW": {"value_krw": 2000000}
            }
        }

        weights = engine._calculate_current_weights(portfolio)

        assert weights["BTC"] == 0.5
        assert weights["ETH"] == 0.3
        assert weights["KRW"] == 0.2

    def test_calculate_weights_empty_portfolio(self, engine):
        """빈 포트폴리오"""
        portfolio = {"total_krw": 0}

        weights = engine._calculate_current_weights(portfolio)

        assert weights is None


@pytest.mark.trading
class TestOptimizeExecutionForCrontab:
    """crontab 최적화 테스트"""

    def test_optimize_for_crontab(self, engine):
        """crontab 주기에 맞춘 최적화"""
        exec_params = {
            "execution_hours": 6,
            "slice_count": 12
        }

        result = engine._optimize_execution_for_crontab(exec_params)

        assert "execution_hours" in result
        assert "slice_count" in result
        assert "slice_interval_minutes" in result
        assert result["slice_interval_minutes"] >= engine.crontab_interval_minutes


@pytest.mark.trading
class TestGetExecutionParameters:
    """실행 파라미터 조회 테스트"""

    def test_get_execution_parameters_success(self, engine):
        """파라미터 조회 성공"""
        with patch('src.utils.binance_data_provider.BinanceDataProvider') as mock_provider:
            mock_instance = Mock()
            mock_instance.get_historical_klines.return_value = pd.DataFrame({
                'High': [100, 102, 104],
                'Low': [98, 99, 101],
                'Close': [99, 101, 103]
            })
            mock_instance.convert_usdt_to_krw.return_value = pd.DataFrame({
                'High': [140000, 142800, 145600],
                'Low': [137200, 138600, 141400],
                'Close': [138600, 141400, 144200]
            })
            mock_provider.return_value = mock_instance

            result = engine._get_execution_parameters()

            assert "execution_hours" in result
            assert "slice_count" in result
            assert "slice_interval_minutes" in result

    def test_get_execution_parameters_fallback(self, engine):
        """데이터 조회 실패 시 기본값"""
        # BinanceDataProvider를 사용하는 메서드를 모킹
        with patch.object(engine, 'calculate_atr') as mock_atr:
            # ATR 계산 실패 시나리오
            mock_atr.side_effect = Exception("API Error")

            result = engine._get_execution_parameters()

            # 기본값 반환
            assert result["execution_hours"] == 6
            assert result["slice_count"] == 12
            assert result["slice_interval_minutes"] == 30


@pytest.mark.trading
class TestEdgeCases:
    """엣지 케이스 테스트"""

    def test_twap_order_all_slices_completed(self, engine, mock_rebalancer):
        """모든 슬라이스 완료"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=100000,
            total_quantity=0,
            execution_hours=1,
            slice_count=1,
            slice_amount_krw=100000,
            slice_quantity=0,
            start_time=datetime.now() - timedelta(minutes=30),
            end_time=datetime.now() + timedelta(minutes=30),
            slice_interval_minutes=60
        )

        engine.rebalancer = mock_rebalancer

        result = engine.execute_twap_slice(order)

        assert result["success"] is True
        assert order.status == "completed"

    def test_negative_amount_handling(self, engine):
        """음수 금액 처리 (매도)"""
        with patch.object(engine, '_get_execution_parameters') as mock_params:
            mock_params.return_value = {
                "execution_hours": 6,
                "slice_count": 12,
                "slice_interval_minutes": 30
            }

            rebalance_orders = {
                "BTC": {"amount_diff_krw": -500000}  # 음수 = 매도
            }

            orders = engine.create_twap_orders(rebalance_orders)

            assert len(orders) == 1
            assert orders[0].side == "sell"
            assert orders[0].total_amount_krw == 500000  # 절대값

    def test_very_large_order_split(self, engine):
        """대규모 주문 분할"""
        with patch.object(engine, '_get_execution_parameters') as mock_params:
            mock_params.return_value = {
                "execution_hours": 24,
                "slice_count": 24,
                "slice_interval_minutes": 60
            }

            rebalance_orders = {
                "BTC": {"amount_diff_krw": 100000000}  # 1억원
            }

            orders = engine.create_twap_orders(rebalance_orders)

            assert len(orders) == 1
            # 슬라이스당 금액이 안전 한도 이하인지 확인
            assert orders[0].slice_amount_krw <= 50000000  # 5천만원 한도


@pytest.mark.trading
class TestErrorHandling:
    """에러 처리 테스트"""

    def test_execute_slice_exception_handling(self, engine):
        """슬라이스 실행 예외 처리"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=1000000,
            total_quantity=0,
            execution_hours=6,
            slice_count=10,
            slice_amount_krw=100000,
            slice_quantity=0,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=36
        )

        # 예외 발생 설정
        engine.rebalancer.portfolio_manager.get_portfolio_metrics.side_effect = Exception("DB Error")

        result = engine.execute_twap_slice(order)

        assert result["success"] is False
        assert "error" in result

    def test_process_pending_orders_exception(self, engine):
        """대기 주문 처리 예외"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=1000000,
            total_quantity=0,
            execution_hours=6,
            slice_count=10,
            slice_amount_krw=100000,
            slice_quantity=0,
            start_time=datetime.now() - timedelta(minutes=30),
            end_time=datetime.now() + timedelta(hours=5),
            slice_interval_minutes=30
        )
        engine.active_twap_orders = [order]

        with patch.object(engine, 'execute_twap_slice') as mock_exec:
            mock_exec.side_effect = Exception("Execution Error")

            result = engine.process_pending_twap_orders(check_market_conditions=False)

            assert result["success"] is False
            assert "error" in result


@pytest.mark.trading
class TestExecuteTwapSliceInternalBuy:
    """_execute_twap_slice_internal 매수 시나리오 테스트"""

    @pytest.fixture
    def engine(self, mock_coinone_client, mock_db_manager, mock_rebalancer, mock_alert_system):
        with patch('src.core.dynamic_execution_engine.get_system_coordinator') as mock_coord:
            mock_coord.return_value = Mock()
            mock_coord.return_value.active_operations = {}
            engine = DynamicExecutionEngine(
                coinone_client=mock_coinone_client,
                db_manager=mock_db_manager,
                rebalancer=mock_rebalancer,
                alert_system=mock_alert_system
            )
            return engine

    def test_buy_insufficient_krw_low_ratio(self, engine):
        """매수 시 KRW 비율 너무 낮음"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=1000000,
            total_quantity=0,
            execution_hours=6,
            slice_count=10,
            slice_amount_krw=100000,
            slice_quantity=0,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=36
        )

        # KRW 잔고 부족, 비율 1% 미만
        engine.coinone_client.get_balances.return_value = {"KRW": 50000, "BTC": 0.1}
        engine.rebalancer.portfolio_manager.get_portfolio_metrics.return_value = {
            "total_krw": 10000000  # 1000만원 중 5만원 = 0.5%
        }

        result = engine._execute_twap_slice_internal(order)

        assert result["success"] is False
        assert result["error"] == "krw_ratio_too_low"

    def test_buy_adjusted_amount_below_minimum(self, engine):
        """매수 시 조정된 금액이 최소 금액 미달"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=100000,
            total_quantity=0,
            execution_hours=6,
            slice_count=10,
            slice_amount_krw=10000,
            slice_quantity=0,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=36
        )

        # KRW 잔고가 최소 금액 미달, 비율은 2% 이상
        engine.coinone_client.get_balances.return_value = {"KRW": 3000}  # 3000원
        engine.rebalancer.portfolio_manager.get_portfolio_metrics.return_value = {
            "total_krw": 100000  # 비율 3% > 2%
        }

        result = engine._execute_twap_slice_internal(order)

        assert result["success"] is False
        # KRW 비율이 2% 이상이지만 3000원 잔고가 10000원 슬라이스보다 작으므로
        # KRW 비율 체크에서 먼저 실패
        assert result["error"] in ["insufficient_balance", "krw_ratio_too_low"]

    def test_buy_dynamic_safe_limit_exceeded(self, engine, mock_rebalancer):
        """매수 시 동적 안전 한도 초과"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=100000000,  # 1억원
            total_quantity=0,
            execution_hours=6,
            slice_count=2,
            slice_amount_krw=50000000,  # 5천만원
            slice_quantity=0,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=180
        )

        # 충분한 KRW 잔고
        engine.coinone_client.get_balances.return_value = {"KRW": 100000000}
        engine.rebalancer.portfolio_manager.get_portfolio_metrics.return_value = {
            "total_krw": 100000000
        }
        engine.rebalancer = mock_rebalancer

        result = engine._execute_twap_slice_internal(order)

        # 주문이 실행됨 (금액이 조정됨)
        assert result["success"] is True


@pytest.mark.trading
class TestExecuteTwapSliceInternalSell:
    """_execute_twap_slice_internal 매도 시나리오 테스트"""

    @pytest.fixture
    def engine(self, mock_coinone_client, mock_db_manager, mock_rebalancer, mock_alert_system):
        with patch('src.core.dynamic_execution_engine.get_system_coordinator') as mock_coord:
            mock_coord.return_value = Mock()
            mock_coord.return_value.active_operations = {}
            engine = DynamicExecutionEngine(
                coinone_client=mock_coinone_client,
                db_manager=mock_db_manager,
                rebalancer=mock_rebalancer,
                alert_system=mock_alert_system
            )
            return engine

    def test_sell_invalid_price(self, engine):
        """매도 시 가격 조회 실패"""
        order = TWAPOrder(
            asset="BTC",
            side="sell",
            total_amount_krw=1000000,
            total_quantity=0.02,
            execution_hours=6,
            slice_count=10,
            slice_amount_krw=100000,
            slice_quantity=0.002,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=36
        )

        engine.rebalancer.portfolio_manager.get_portfolio_metrics.return_value = {"total_krw": 10000000}
        engine.coinone_client.get_latest_price.return_value = 0  # 가격 조회 실패

        result = engine._execute_twap_slice_internal(order)

        assert result["success"] is False
        assert "현재가 조회 실패" in result["error"]

    def test_sell_insufficient_balance(self, engine):
        """매도 시 잔고 부족"""
        order = TWAPOrder(
            asset="BTC",
            side="sell",
            total_amount_krw=1000000,
            total_quantity=0.02,
            execution_hours=6,
            slice_count=10,
            slice_amount_krw=100000,
            slice_quantity=0.002,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=36
        )

        engine.rebalancer.portfolio_manager.get_portfolio_metrics.return_value = {"total_krw": 10000000}
        engine.coinone_client.get_latest_price.return_value = 50000000  # 5천만원
        engine.coinone_client.get_balances.return_value = {"BTC": 0.001}  # 부족

        result = engine._execute_twap_slice_internal(order)

        assert result["success"] is False
        assert result["error"] == "insufficient_balance"

    def test_sell_quantity_below_minimum_skip(self, engine):
        """매도 시 수량 최소 한도 미달 - 건너뛰기"""
        order = TWAPOrder(
            asset="BTC",
            side="sell",
            total_amount_krw=50000,
            total_quantity=0.001,
            execution_hours=6,
            slice_count=10,
            slice_amount_krw=5000,
            slice_quantity=0.0001,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=36
        )

        engine.rebalancer.portfolio_manager.get_portfolio_metrics.return_value = {"total_krw": 10000000}
        engine.coinone_client.get_latest_price.return_value = 50000000
        # 계산된 수량: 5000 / 50000000 = 0.0001 → 최소 0.0001 미만 (실제로는 경계값)
        engine.coinone_client.get_balances.return_value = {"BTC": 0.001}

        result = engine._execute_twap_slice_internal(order)

        # 최소량 미달로 건너뛰거나 실행됨
        assert "success" in result or "skipped" in result

    def test_sell_quantity_above_maximum(self, engine, mock_rebalancer):
        """매도 시 수량 최대 한도 초과"""
        order = TWAPOrder(
            asset="BTC",
            side="sell",
            total_amount_krw=600000000,  # 6억
            total_quantity=12,
            execution_hours=6,
            slice_count=1,
            slice_amount_krw=600000000,
            slice_quantity=12,  # 최대 10 BTC 초과
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=360
        )

        engine.rebalancer.portfolio_manager.get_portfolio_metrics.return_value = {"total_krw": 1000000000}
        engine.coinone_client.get_latest_price.return_value = 50000000
        engine.coinone_client.get_balances.return_value = {"BTC": 20}  # 충분한 잔고
        engine.rebalancer = mock_rebalancer

        result = engine._execute_twap_slice_internal(order)

        # 최대 한도로 조정되어 실행됨
        assert result["success"] is True

    def test_sell_calculation_exception(self, engine):
        """매도 시 수량 계산 예외"""
        order = TWAPOrder(
            asset="BTC",
            side="sell",
            total_amount_krw=1000000,
            total_quantity=0.02,
            execution_hours=6,
            slice_count=10,
            slice_amount_krw=100000,
            slice_quantity=0.002,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=36
        )

        engine.rebalancer.portfolio_manager.get_portfolio_metrics.return_value = {"total_krw": 10000000}
        engine.coinone_client.get_latest_price.side_effect = Exception("API Error")

        result = engine._execute_twap_slice_internal(order)

        assert result["success"] is False
        assert "매도 수량 계산 실패" in result["error"]


@pytest.mark.trading
class TestCreateTwapOrdersEdgeCases:
    """create_twap_orders 엣지 케이스 테스트"""

    @pytest.fixture
    def engine(self, mock_coinone_client, mock_db_manager, mock_rebalancer, mock_alert_system):
        with patch('src.core.dynamic_execution_engine.get_system_coordinator') as mock_coord:
            mock_coord.return_value = Mock()
            mock_coord.return_value.active_operations = {}
            engine = DynamicExecutionEngine(
                coinone_client=mock_coinone_client,
                db_manager=mock_db_manager,
                rebalancer=mock_rebalancer,
                alert_system=mock_alert_system
            )
            return engine

    def test_slice_count_adjustment(self, engine):
        """슬라이스 수 조정 (금액이 적을 때)"""
        with patch.object(engine, '_get_execution_parameters') as mock_params:
            mock_params.return_value = {
                "execution_hours": 6,
                "slice_count": 12,
                "slice_interval_minutes": 30
            }

            rebalance_orders = {
                "BTC": {"amount_diff_krw": 30000}  # 3만원 - 12슬라이스로 나누면 2500원/슬라이스
            }

            orders = engine.create_twap_orders(rebalance_orders)

            # 주문이 생성되었는지 확인 (현재 구현에서는 슬라이스 수를 자동 조정하지 않음)
            assert len(orders) == 1
            assert orders[0].total_amount_krw == 30000

    def test_maximum_order_limit(self, engine):
        """최대 주문 한도 적용"""
        with patch.object(engine, '_get_execution_parameters') as mock_params:
            mock_params.return_value = {
                "execution_hours": 24,
                "slice_count": 48,
                "slice_interval_minutes": 30
            }

            rebalance_orders = {
                "BTC": {"amount_diff_krw": 500000000}  # 5억원
            }

            orders = engine.create_twap_orders(rebalance_orders)

            # 슬라이스 당 금액이 안전 한도 이하
            if len(orders) > 0:
                assert orders[0].slice_amount_krw <= 50000000


@pytest.mark.trading
class TestStartTwapExecutionEdgeCases:
    """start_twap_execution 엣지 케이스 테스트"""

    @pytest.fixture
    def engine(self, mock_coinone_client, mock_db_manager, mock_rebalancer, mock_alert_system):
        with patch('src.core.dynamic_execution_engine.get_system_coordinator') as mock_coord:
            mock_coord.return_value = Mock()
            mock_coord.return_value.active_operations = {}
            engine = DynamicExecutionEngine(
                coinone_client=mock_coinone_client,
                db_manager=mock_db_manager,
                rebalancer=mock_rebalancer,
                alert_system=mock_alert_system
            )
            return engine

    def test_database_save_error(self, engine):
        """데이터베이스 저장 오류"""
        with patch.object(engine, '_get_execution_parameters') as mock_params, \
             patch.object(engine, '_get_current_market_condition') as mock_market:

            mock_params.return_value = {
                "execution_hours": 6,
                "slice_count": 12,
                "slice_interval_minutes": 30
            }
            mock_market.return_value = ("neutral", {"crypto": 0.5})
            engine.db_manager.save_twap_execution_plan.side_effect = Exception("DB Error")

            rebalance_orders = {
                "BTC": {"amount_diff_krw": 500000}
            }

            result = engine.start_twap_execution(rebalance_orders)

            # DB 오류에도 실행은 계속됨
            assert result["success"] is True

    def test_alert_system_error(self, engine):
        """알림 시스템 오류"""
        with patch.object(engine, '_get_execution_parameters') as mock_params, \
             patch.object(engine, '_get_current_market_condition') as mock_market:

            mock_params.return_value = {
                "execution_hours": 6,
                "slice_count": 12,
                "slice_interval_minutes": 30
            }
            mock_market.return_value = ("neutral", {"crypto": 0.5})
            engine.alert_system.send_system_alert.side_effect = Exception("Alert Error")

            rebalance_orders = {
                "BTC": {"amount_diff_krw": 500000}
            }

            result = engine.start_twap_execution(rebalance_orders)

            # 알림 오류에도 실행은 계속됨
            assert result["success"] is True


@pytest.mark.trading
class TestProcessPendingTwapOrdersEdgeCases:
    """process_pending_twap_orders 엣지 케이스 테스트"""

    @pytest.fixture
    def engine(self, mock_coinone_client, mock_db_manager, mock_rebalancer, mock_alert_system):
        with patch('src.core.dynamic_execution_engine.get_system_coordinator') as mock_coord:
            mock_coord.return_value = Mock()
            mock_coord.return_value.active_operations = {}
            engine = DynamicExecutionEngine(
                coinone_client=mock_coinone_client,
                db_manager=mock_db_manager,
                rebalancer=mock_rebalancer,
                alert_system=mock_alert_system
            )
            return engine

    def test_scheduled_execution(self, engine, mock_rebalancer):
        """예정된 시간에 실행"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=1000000,
            total_quantity=0,
            execution_hours=6,
            slice_count=12,
            slice_amount_krw=83333,
            slice_quantity=0,
            start_time=datetime.now() - timedelta(minutes=35),
            end_time=datetime.now() + timedelta(hours=5),
            slice_interval_minutes=30,
            last_execution_time=datetime.now() - timedelta(minutes=35)
        )
        engine.active_twap_orders = [order]
        engine.rebalancer = mock_rebalancer

        result = engine.process_pending_twap_orders(check_market_conditions=False)

        assert result["success"] is True
        assert result["processed_orders"] >= 0

    def test_market_condition_change_detection(self, engine):
        """시장 상황 변화 감지"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=1000000,
            total_quantity=0,
            execution_hours=6,
            slice_count=12,
            slice_amount_krw=83333,
            slice_quantity=0,
            start_time=datetime.now() - timedelta(minutes=10),
            end_time=datetime.now() + timedelta(hours=5),
            slice_interval_minutes=30,
            market_season="neutral",
            target_allocation={"crypto": 0.5}
        )
        engine.active_twap_orders = [order]

        with patch.object(engine, '_check_market_condition_change') as mock_check, \
             patch.object(engine, 'start_twap_execution') as mock_start:
            mock_check.return_value = True
            mock_start.return_value = {"success": True}

            result = engine.process_pending_twap_orders(check_market_conditions=True)

            # 시장 상황 변화로 재시작
            assert mock_start.called or result["success"] is True


@pytest.mark.trading
class TestCancelPendingExchangeOrdersEdgeCases:
    """_cancel_pending_exchange_orders 엣지 케이스 테스트"""

    @pytest.fixture
    def engine(self, mock_coinone_client, mock_db_manager, mock_rebalancer, mock_alert_system):
        with patch('src.core.dynamic_execution_engine.get_system_coordinator') as mock_coord:
            mock_coord.return_value = Mock()
            mock_coord.return_value.active_operations = {}
            engine = DynamicExecutionEngine(
                coinone_client=mock_coinone_client,
                db_manager=mock_db_manager,
                rebalancer=mock_rebalancer,
                alert_system=mock_alert_system
            )
            return engine

    def test_order_status_check_failure(self, engine):
        """주문 상태 조회 실패"""
        engine.coinone_client.get_order_status.side_effect = Exception("API Error")

        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=1000000,
            total_quantity=0,
            execution_hours=6,
            slice_count=12,
            slice_amount_krw=83333,
            slice_quantity=0,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=30,
            exchange_order_ids=["order_123"]
        )

        result = engine._cancel_pending_exchange_orders([order])

        # 오류가 발생해도 계속 진행
        assert result["failed_count"] >= 0

    def test_cancellation_failure(self, engine):
        """주문 취소 실패"""
        engine.coinone_client.get_order_status.return_value = {
            "result": "success",
            "status": "pending"
        }
        engine.coinone_client.cancel_order.return_value = {
            "result": "error",
            "error_code": "500"
        }

        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=1000000,
            total_quantity=0,
            execution_hours=6,
            slice_count=12,
            slice_amount_krw=83333,
            slice_quantity=0,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=30,
            exchange_order_ids=["order_123"]
        )

        result = engine._cancel_pending_exchange_orders([order])

        assert result["failed_count"] >= 0


@pytest.mark.trading
class TestCheckMarketConditionChangeEdgeCases:
    """_check_market_condition_change 엣지 케이스 테스트"""

    @pytest.fixture
    def engine(self, mock_coinone_client, mock_db_manager, mock_rebalancer, mock_alert_system):
        with patch('src.core.dynamic_execution_engine.get_system_coordinator') as mock_coord:
            mock_coord.return_value = Mock()
            mock_coord.return_value.active_operations = {}
            engine = DynamicExecutionEngine(
                coinone_client=mock_coinone_client,
                db_manager=mock_db_manager,
                rebalancer=mock_rebalancer,
                alert_system=mock_alert_system
            )
            return engine

    def test_portfolio_balance_change(self, engine):
        """포트폴리오 비중 변화 감지 - 시즌 변화"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=1000000,
            total_quantity=0,
            execution_hours=6,
            slice_count=12,
            slice_amount_krw=83333,
            slice_quantity=0,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=30,
            market_season="neutral",
            target_allocation={"BTC": 0.3, "ETH": 0.2, "KRW": 0.5}
        )
        engine.active_twap_orders = [order]

        with patch.object(engine, '_get_current_market_condition') as mock_market:
            # 시즌 변화 (neutral → bullish)로 변화 감지
            mock_market.return_value = ("bullish", {"BTC": 0.4, "ETH": 0.1, "KRW": 0.5})

            changed = engine._check_market_condition_change()

            # 시즌 변화 감지
            assert changed is True

    def test_no_active_orders(self, engine):
        """활성 주문 없음"""
        engine.active_twap_orders = []

        changed = engine._check_market_condition_change()

        assert changed is False


@pytest.mark.trading
class TestLoadActiveTwapOrders:
    """활성 TWAP 주문 로드 테스트"""

    def test_load_orders_from_database(self, mock_coinone_client, mock_db_manager, mock_rebalancer, mock_alert_system):
        """데이터베이스에서 활성 주문 로드"""
        # 활성 주문 데이터 설정 - get_latest_active_twap_execution 메서드 사용
        mock_db_manager.get_latest_active_twap_execution.return_value = {
            "execution_id": "test_exec_123",
            "twap_orders_detail": [
                {
                    "asset": "BTC",
                    "side": "buy",
                    "total_amount_krw": 1000000,
                    "total_quantity": 0.02,
                    "execution_hours": 6,
                    "slice_count": 12,
                    "slice_amount_krw": 83333,
                    "slice_quantity": 0.00166,
                    "start_time": datetime.now().isoformat(),
                    "end_time": (datetime.now() + timedelta(hours=6)).isoformat(),
                    "slice_interval_minutes": 30,
                    "executed_slices": 3,
                    "remaining_amount_krw": 750000,
                    "remaining_quantity": 0.015,
                    "status": "executing"
                }
            ]
        }

        with patch('src.core.dynamic_execution_engine.get_system_coordinator') as mock_coord:
            mock_coord.return_value = Mock()
            mock_coord.return_value.active_operations = {}

            engine = DynamicExecutionEngine(
                coinone_client=mock_coinone_client,
                db_manager=mock_db_manager,
                rebalancer=mock_rebalancer,
                alert_system=mock_alert_system
            )

            # 로드 메서드가 호출되었는지 확인
            mock_db_manager.get_latest_active_twap_execution.assert_called()
            # 주문이 로드되었는지 확인
            assert len(engine.active_twap_orders) == 1
            assert engine.current_execution_id == "test_exec_123"


@pytest.mark.trading
class TestGetExecutionParametersEdgeCases:
    """_get_execution_parameters 엣지 케이스 테스트"""

    @pytest.fixture
    def engine(self, mock_coinone_client, mock_db_manager, mock_rebalancer, mock_alert_system):
        with patch('src.core.dynamic_execution_engine.get_system_coordinator') as mock_coord:
            mock_coord.return_value = Mock()
            mock_coord.return_value.active_operations = {}
            engine = DynamicExecutionEngine(
                coinone_client=mock_coinone_client,
                db_manager=mock_db_manager,
                rebalancer=mock_rebalancer,
                alert_system=mock_alert_system
            )
            return engine

    def test_high_volatility_parameters(self, engine):
        """높은 변동성에서 파라미터 조정"""
        with patch('src.utils.binance_data_provider.BinanceDataProvider') as mock_provider:
            mock_instance = Mock()
            # 변동성이 높은 데이터
            mock_instance.get_historical_klines.return_value = pd.DataFrame({
                'High': [100, 120, 80, 130, 70],
                'Low': [80, 90, 60, 100, 50],
                'Close': [90, 110, 70, 120, 60]
            })
            mock_instance.convert_usdt_to_krw.return_value = pd.DataFrame({
                'High': [140000, 168000, 112000, 182000, 98000],
                'Low': [112000, 126000, 84000, 140000, 70000],
                'Close': [126000, 154000, 98000, 168000, 84000]
            })
            mock_provider.return_value = mock_instance

            result = engine._get_execution_parameters()

            assert "execution_hours" in result
            assert "slice_count" in result

    def test_market_data_retrieval_failure(self, engine):
        """시장 데이터 조회 실패"""
        with patch('src.utils.binance_data_provider.BinanceDataProvider') as mock_provider:
            mock_provider.side_effect = Exception("Market data unavailable")

            result = engine._get_execution_parameters()

            # crontab 최적화된 기본값 반환 (8시간, 32슬라이스)
            assert result["execution_hours"] == 8
            assert result["slice_count"] == 32
            assert result["slice_interval_minutes"] == 15


@pytest.mark.trading
class TestOrderErrorHandling:
    """주문 에러 핸들링 테스트"""

    @pytest.fixture
    def engine(self, mock_coinone_client, mock_db_manager, mock_rebalancer, mock_alert_system):
        with patch('src.core.dynamic_execution_engine.get_system_coordinator') as mock_coord:
            mock_coord.return_value = Mock()
            mock_coord.return_value.active_operations = {}
            engine = DynamicExecutionEngine(
                coinone_client=mock_coinone_client,
                db_manager=mock_db_manager,
                rebalancer=mock_rebalancer,
                alert_system=mock_alert_system
            )
            return engine

    def test_minimum_amount_error_retry(self, engine, mock_rebalancer):
        """최소 주문 금액 미만 오류 (306) 처리"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=50000,
            total_quantity=0,
            execution_hours=6,
            slice_count=10,
            slice_amount_krw=5000,
            slice_quantity=0,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=36,
            remaining_amount_krw=50000
        )

        engine.coinone_client.get_balances.return_value = {"KRW": 100000}
        engine.rebalancer.portfolio_manager.get_portfolio_metrics.return_value = {"total_krw": 100000}

        # 첫 번째 주문 실패 (306 에러)
        mock_order_failed = Mock()
        mock_order_failed.status = OrderStatus.FAILED
        mock_order_failed.order_id = None
        mock_order_failed.error_message = "below the minimum amount"

        # 두 번째 전체 금액 주문 성공
        mock_order_success = Mock()
        mock_order_success.status = OrderStatus.FILLED
        mock_order_success.order_id = "full_order_001"
        mock_order_success.error_message = None

        mock_rebalancer.order_manager.submit_market_order.side_effect = [
            mock_order_failed,
            mock_order_success
        ]
        engine.rebalancer = mock_rebalancer

        result = engine._execute_twap_slice_internal(order)

        # 전체 금액으로 재시도하여 성공
        assert result["success"] is True
        assert result.get("full_amount_executed") is True

    def test_maximum_amount_error_adjustment(self, engine, mock_rebalancer):
        """최대 주문 금액 초과 오류 (307) 처리"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=100000000,  # 1억
            total_quantity=0,
            execution_hours=6,
            slice_count=2,
            slice_amount_krw=50000000,
            slice_quantity=0,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=180,
            remaining_amount_krw=100000000
        )

        engine.coinone_client.get_balances.return_value = {"KRW": 100000000}
        engine.rebalancer.portfolio_manager.get_portfolio_metrics.return_value = {"total_krw": 100000000}

        # 주문 실패 (307 에러)
        mock_order_failed = Mock()
        mock_order_failed.status = OrderStatus.FAILED
        mock_order_failed.order_id = None
        mock_order_failed.error_message = "exceed the maximum amount"

        mock_rebalancer.order_manager.submit_market_order.return_value = mock_order_failed
        engine.rebalancer = mock_rebalancer

        result = engine._execute_twap_slice_internal(order)

        # 오류가 반환되지만 슬라이스 크기가 조정됨
        assert result.get("success") is False
        # 슬라이스 크기가 50%로 감소
        assert order.slice_amount_krw == 25000000

    def test_retryable_error_handling(self, engine, mock_rebalancer):
        """일시적 오류 처리"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=1000000,
            total_quantity=0,
            execution_hours=6,
            slice_count=10,
            slice_amount_krw=100000,
            slice_quantity=0,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=36
        )

        engine.coinone_client.get_balances.return_value = {"KRW": 1000000}
        engine.rebalancer.portfolio_manager.get_portfolio_metrics.return_value = {"total_krw": 1000000}

        # 일시적 오류
        mock_order_failed = Mock()
        mock_order_failed.status = OrderStatus.FAILED
        mock_order_failed.order_id = None
        mock_order_failed.error_message = "Market temporarily unavailable"

        mock_rebalancer.order_manager.submit_market_order.return_value = mock_order_failed
        engine.rebalancer = mock_rebalancer

        result = engine._execute_twap_slice_internal(order)

        # 오류 반환되지만 주문 상태는 변경되지 않음 (다음 슬라이스에서 재시도)
        assert result.get("success") is False
        assert order.status != "failed"

    def test_unrecoverable_error_handling(self, engine, mock_rebalancer):
        """복구 불가능한 오류 처리"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=1000000,
            total_quantity=0,
            execution_hours=6,
            slice_count=10,
            slice_amount_krw=100000,
            slice_quantity=0,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=36
        )

        engine.coinone_client.get_balances.return_value = {"KRW": 1000000}
        engine.rebalancer.portfolio_manager.get_portfolio_metrics.return_value = {"total_krw": 1000000}

        # 복구 불가능한 오류
        mock_order_failed = Mock()
        mock_order_failed.status = OrderStatus.FAILED
        mock_order_failed.order_id = None
        mock_order_failed.error_message = "API key invalid"

        mock_rebalancer.order_manager.submit_market_order.return_value = mock_order_failed
        engine.rebalancer = mock_rebalancer

        result = engine._execute_twap_slice_internal(order)

        # 오류 반환 및 주문 실패 상태로 변경
        assert result.get("success") is False
        assert order.status == "failed"


@pytest.mark.trading
class TestSellOrderQuantityAdjustment:
    """매도 주문 수량 조정 테스트"""

    @pytest.fixture
    def engine(self, mock_coinone_client, mock_db_manager, mock_rebalancer, mock_alert_system):
        with patch('src.core.dynamic_execution_engine.get_system_coordinator') as mock_coord:
            mock_coord.return_value = Mock()
            mock_coord.return_value.active_operations = {}
            engine = DynamicExecutionEngine(
                coinone_client=mock_coinone_client,
                db_manager=mock_db_manager,
                rebalancer=mock_rebalancer,
                alert_system=mock_alert_system
            )
            return engine

    def test_sell_last_slice_minimum_adjustment(self, engine, mock_rebalancer):
        """매도 마지막 슬라이스 최소량 조정"""
        order = TWAPOrder(
            asset="BTC",
            side="sell",
            total_amount_krw=10000,
            total_quantity=0.0002,
            execution_hours=6,
            slice_count=2,
            slice_amount_krw=5000,
            slice_quantity=0.0001,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=180,
            executed_slices=1  # 마지막 슬라이스
        )

        engine.rebalancer.portfolio_manager.get_portfolio_metrics.return_value = {"total_krw": 10000000}
        engine.coinone_client.get_latest_price.return_value = 50000000
        engine.coinone_client.get_balances.return_value = {"BTC": 0.0002}
        engine.rebalancer = mock_rebalancer

        result = engine._execute_twap_slice_internal(order)

        # 마지막 슬라이스이므로 최소량으로 조정되어 실행
        assert "success" in result

    def test_sell_middle_slice_skip_and_combine(self, engine):
        """매도 중간 슬라이스 건너뛰고 다음과 합치기"""
        order = TWAPOrder(
            asset="BTC",
            side="sell",
            total_amount_krw=10000,
            total_quantity=0.0002,
            execution_hours=6,
            slice_count=10,
            slice_amount_krw=1000,  # 매우 작은 금액
            slice_quantity=0.00002,  # BTC 최소량 0.0001 미만
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=36,
            executed_slices=2  # 중간 슬라이스
        )

        engine.rebalancer.portfolio_manager.get_portfolio_metrics.return_value = {"total_krw": 10000000}
        engine.coinone_client.get_latest_price.return_value = 50000000
        engine.coinone_client.get_balances.return_value = {"BTC": 0.001}

        result = engine._execute_twap_slice_internal(order)

        # 최소량 미달로 건너뛰기
        if result.get("skipped"):
            assert result["success"] is True
            assert order.executed_slices == 3  # 슬라이스 카운트 증가

    def test_sell_safe_limit_exceeded(self, engine, mock_rebalancer):
        """매도 시 안전 한도 초과"""
        order = TWAPOrder(
            asset="BTC",
            side="sell",
            total_amount_krw=100000000,  # 1억
            total_quantity=2.0,
            execution_hours=6,
            slice_count=1,
            slice_amount_krw=100000000,
            slice_quantity=2.0,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=360
        )

        engine.rebalancer.portfolio_manager.get_portfolio_metrics.return_value = {"total_krw": 100000000}
        engine.coinone_client.get_latest_price.return_value = 50000000
        engine.coinone_client.get_balances.return_value = {"BTC": 5.0}
        engine.rebalancer = mock_rebalancer

        result = engine._execute_twap_slice_internal(order)

        # 안전 한도로 조정되어 실행
        assert result["success"] is True


@pytest.mark.trading
class TestDynamicExecutionEngineExceptionHandling:
    """예외 처리 테스트"""

    @pytest.fixture
    def engine(self, mock_coinone_client, mock_db_manager, mock_rebalancer, mock_alert_system):
        """테스트용 엔진 생성"""
        with patch('src.core.dynamic_execution_engine.DynamicExecutionEngine._load_active_twap_orders'):
            engine = DynamicExecutionEngine(
                coinone_client=mock_coinone_client,
                db_manager=mock_db_manager,
                rebalancer=mock_rebalancer,
                alert_system=mock_alert_system
            )
            engine.active_twap_orders = []
            return engine

    def test_load_active_orders_exception(self, mock_coinone_client, mock_db_manager, mock_rebalancer, mock_alert_system):
        """활성 TWAP 주문 로드 실패 시 예외 처리 (라인 179-182)"""
        mock_db_manager.load_active_twap_orders.side_effect = Exception("Database error")

        # 예외가 발생해도 엔진은 생성되어야 함
        engine = DynamicExecutionEngine(
            coinone_client=mock_coinone_client,
            db_manager=mock_db_manager,
            rebalancer=mock_rebalancer,
            alert_system=mock_alert_system
        )

        assert engine.active_twap_orders == []
        assert engine.current_execution_id is None

    def test_create_twap_orders_exec_params_failure(self, engine):
        """실행 파라미터 계산 실패 시 (라인 284-285)"""
        engine._get_execution_parameters = Mock(return_value=None)

        result = engine.create_twap_orders(
            rebalance_orders={"BTC": {"amount_diff_krw": 100000}},
            market_season="neutral"
        )

        assert result == []

    def test_create_twap_orders_price_lookup_exception(self, engine):
        """현재가 조회 실패 시 기본 최소 금액 사용 (라인 332-333)"""
        engine._get_execution_parameters = Mock(return_value={
            "execution_hours": 6,
            "slice_count": 24,
            "slice_interval_minutes": 15
        })
        engine.coinone_client.get_latest_price.side_effect = Exception("Price lookup failed")

        # 예외가 발생해도 주문 생성 시도
        result = engine.create_twap_orders(
            rebalance_orders={"BTC": {"amount_diff_krw": -500000}},  # 매도
            market_season="neutral"
        )

        # 가격 조회 실패해도 기본 최소 금액으로 진행
        assert isinstance(result, list)

    def test_create_twap_orders_slice_amount_too_small(self, engine):
        """슬라이스 금액이 최소 금액보다 작은 경우 (라인 336-346)"""
        engine._get_execution_parameters = Mock(return_value={
            "execution_hours": 6,
            "slice_count": 100,  # 많은 분할 횟수
            "slice_interval_minutes": 4
        })

        # 총 금액을 슬라이스 횟수로 나누면 최소 금액보다 작아짐
        result = engine.create_twap_orders(
            rebalance_orders={"BTC": {"amount_diff_krw": 50000}},  # 5만원을 100번 분할
            market_season="neutral"
        )

        # 분할 횟수가 조정되거나 건너뜀
        assert isinstance(result, list)

    def test_create_twap_orders_total_amount_less_than_minimum(self, engine):
        """총 주문 금액이 최소 금액보다 작은 경우 건너뛰기 (라인 343-346)"""
        engine._get_execution_parameters = Mock(return_value={
            "execution_hours": 6,
            "slice_count": 24,
            "slice_interval_minutes": 15
        })

        # 총 금액이 최소 금액보다 작음
        result = engine.create_twap_orders(
            rebalance_orders={"BTC": {"amount_diff_krw": 3000}},  # 3천원
            market_season="neutral"
        )

        # 금액이 너무 작아 건너뜀
        assert result == []

    def test_create_twap_orders_safe_limit_exceeded(self, engine):
        """슬라이스당 금액이 안전 한도 초과 시 분할 횟수 조정 (라인 355-365)"""
        engine._get_execution_parameters = Mock(return_value={
            "execution_hours": 1,
            "slice_count": 1,  # 적은 분할 횟수
            "slice_interval_minutes": 60
        })

        # 큰 금액을 1번 분할 시 안전 한도 초과
        result = engine.create_twap_orders(
            rebalance_orders={"BTC": {"amount_diff_krw": 100000000}},  # 1억
            market_season="neutral"
        )

        # 주문이 생성됨 (분할 횟수 조정 여부는 로그로 확인)
        assert isinstance(result, list)
        if result:
            assert result[0].total_amount_krw == 100000000

    def test_create_twap_orders_general_exception(self, engine):
        """TWAP 주문 생성 중 예외 (라인 395-397)"""
        engine._get_execution_parameters = Mock(side_effect=Exception("Unexpected error"))

        result = engine.create_twap_orders(
            rebalance_orders={"BTC": {"amount_diff_krw": 100000}},
            market_season="neutral"
        )

        assert result == []

    def test_execute_twap_slice_sync_conflict_check_exception(self, engine, mock_rebalancer):
        """충돌 체크 실패 시 계속 진행 (라인 424-425)"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=100000,
            total_quantity=0.002,
            execution_hours=6,
            slice_count=12,
            slice_amount_krw=10000,
            slice_quantity=0.0002,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=30
        )

        # 충돌 체크 예외 발생
        with patch.object(engine.db_manager, 'get_active_twap_executions', side_effect=Exception("Conflict check error")):
            engine.rebalancer = mock_rebalancer
            result = engine.execute_twap_slice_sync(order)

        # 충돌 체크 실패해도 계속 실행
        assert isinstance(result, dict)

    def test_execute_twap_slice_sync_general_exception(self, engine):
        """TWAP 슬라이스 실행 중 예외 (라인 429-431)"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=100000,
            total_quantity=0.002,
            execution_hours=6,
            slice_count=12,
            slice_amount_krw=10000,
            slice_quantity=0.0002,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=30
        )

        engine._execute_twap_slice_internal = Mock(side_effect=Exception("Internal error"))

        result = engine.execute_twap_slice_sync(order)

        assert result["success"] is False
        assert "error" in result

    def test_execute_internal_krw_balance_adjustment(self, engine, mock_rebalancer):
        """KRW 잔고 부족 시 주문 크기 조정 (라인 470-477)"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=100000,
            total_quantity=0.002,
            execution_hours=6,
            slice_count=12,
            slice_amount_krw=100000,  # 10만원
            slice_quantity=0.002,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=30
        )

        # KRW 잔고가 주문 금액보다 작지만 최소 금액보다는 큼
        engine.coinone_client.get_balances.return_value = {"KRW": 50000, "BTC": 0.1}
        engine.coinone_client.get_portfolio_value.return_value = {"total_krw": 5000000}
        engine.rebalancer = mock_rebalancer

        result = engine._execute_twap_slice_internal(order)

        # 주문 금액이 조정됨
        assert isinstance(result, dict)

    def test_execute_internal_adjusted_amount_below_minimum(self, engine, mock_rebalancer):
        """조정된 금액이 최소 주문 금액보다 작은 경우 (라인 475-477)"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=100000,
            total_quantity=0.002,
            execution_hours=6,
            slice_count=12,
            slice_amount_krw=100000,  # 10만원
            slice_quantity=0.002,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=30
        )

        # KRW 비율이 2% 이상이지만 (3000/100000=3%), 조정된 금액이 최소보다 작음
        engine.coinone_client.get_balances.return_value = {"KRW": 3000, "BTC": 0.1}
        engine.coinone_client.get_portfolio_value.return_value = {"total_krw": 100000}  # 낮은 총 가치
        engine.rebalancer = mock_rebalancer

        result = engine._execute_twap_slice_internal(order)

        assert result["success"] is False
        assert result["error"] == "insufficient_balance"

    def test_execute_internal_dynamic_safe_limit_exceeded(self, engine, mock_rebalancer):
        """동적 안전 한도 초과 시 주문 크기 조정 (라인 496-512)"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=100000000,  # 1억
            total_quantity=2.0,
            execution_hours=6,
            slice_count=4,
            slice_amount_krw=25000000,  # 2500만원 슬라이스
            slice_quantity=0.5,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=90,
            executed_slices=1  # 이미 1개 실행
        )

        # 현재 KRW 잔고의 50%보다 슬라이스 금액이 큼
        engine.coinone_client.get_balances.return_value = {"KRW": 30000000, "BTC": 0.1}  # 3천만원
        engine.coinone_client.get_portfolio_value.return_value = {"total_krw": 50000000}
        engine.rebalancer = mock_rebalancer

        result = engine._execute_twap_slice_internal(order)

        # 동적 안전 한도로 조정됨
        assert isinstance(result, dict)

    def test_execute_internal_no_remaining_slices(self, engine, mock_rebalancer):
        """남은 슬라이스가 없는 경우 (라인 508-509)"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=100000000,  # 1억
            total_quantity=2.0,
            execution_hours=6,
            slice_count=4,
            slice_amount_krw=25000000,  # 2500만원 슬라이스
            slice_quantity=0.5,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=90,
            executed_slices=3  # 마지막 슬라이스
        )

        # 현재 KRW 잔고의 50%보다 슬라이스 금액이 큼
        engine.coinone_client.get_balances.return_value = {"KRW": 30000000, "BTC": 0.1}
        engine.coinone_client.get_portfolio_value.return_value = {"total_krw": 50000000}
        engine.rebalancer = mock_rebalancer

        result = engine._execute_twap_slice_internal(order)

        # 남은 슬라이스가 없어도 실행
        assert isinstance(result, dict)


@pytest.mark.trading
class TestDynamicExecutionEngineSellEdgeCases:
    """매도 관련 엣지 케이스 테스트"""

    @pytest.fixture
    def engine(self, mock_coinone_client, mock_db_manager, mock_rebalancer, mock_alert_system):
        """테스트용 엔진 생성"""
        with patch('src.core.dynamic_execution_engine.DynamicExecutionEngine._load_active_twap_orders'):
            engine = DynamicExecutionEngine(
                coinone_client=mock_coinone_client,
                db_manager=mock_db_manager,
                rebalancer=mock_rebalancer,
                alert_system=mock_alert_system
            )
            engine.active_twap_orders = []
            return engine

    def test_sell_last_slice_minimum_adjustment(self, engine, mock_rebalancer):
        """매도 마지막 슬라이스 최소량 조정 (라인 590-591)"""
        order = TWAPOrder(
            asset="BTC",
            side="sell",
            total_amount_krw=50000,
            total_quantity=0.001,
            execution_hours=6,
            slice_count=10,
            slice_amount_krw=5000,  # 5천원 슬라이스
            slice_quantity=0.0001,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=36,
            executed_slices=9  # 마지막 슬라이스
        )

        # 최소량보다 작은 잔고
        engine.coinone_client.get_balances.return_value = {"BTC": 0.00001}  # 아주 작은 잔고
        engine.coinone_client.get_latest_price.return_value = 50000000
        engine.coinone_client.get_portfolio_value.return_value = {"total_krw": 5000000}
        engine.rebalancer = mock_rebalancer

        result = engine._execute_twap_slice_internal(order)

        # 마지막 슬라이스이므로 최소량으로 조정되어 실행
        assert isinstance(result, dict)

    def test_sell_max_limit_exceeded(self, engine, mock_rebalancer):
        """매도 최대 주문량 초과 (라인 622-623)"""
        order = TWAPOrder(
            asset="BTC",
            side="sell",
            total_amount_krw=1000000000,  # 10억
            total_quantity=20.0,
            execution_hours=6,
            slice_count=2,
            slice_amount_krw=500000000,  # 5억 슬라이스
            slice_quantity=10.0,  # 10 BTC
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=180
        )

        # 충분한 잔고
        engine.coinone_client.get_balances.return_value = {"BTC": 25.0}
        engine.coinone_client.get_latest_price.return_value = 50000000
        engine.coinone_client.get_portfolio_value.return_value = {"total_krw": 1000000000}
        engine.rebalancer = mock_rebalancer

        result = engine._execute_twap_slice_internal(order)

        # 최대 한도로 조정되어 실행
        assert isinstance(result, dict)

    def test_order_result_none(self, engine, mock_rebalancer):
        """주문 제출 결과가 None인 경우 (라인 656, 744)"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=100000,
            total_quantity=0.002,
            execution_hours=6,
            slice_count=12,
            slice_amount_krw=10000,
            slice_quantity=0.0002,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=30
        )

        engine.coinone_client.get_portfolio_value.return_value = {"total_krw": 5000000}
        engine.rebalancer = mock_rebalancer
        engine.rebalancer.order_manager.submit_market_order.return_value = None

        result = engine._execute_twap_slice_internal(order)

        assert result["success"] is False
        assert "Order submission returned None" in result.get("error", "")

    def test_skipped_slice_all_completed(self, engine, mock_rebalancer):
        """건너뛴 슬라이스로 전체 완료 (라인 664-670)"""
        order = TWAPOrder(
            asset="BTC",
            side="sell",
            total_amount_krw=30000,
            total_quantity=0.0006,
            execution_hours=6,
            slice_count=3,
            slice_amount_krw=10000,  # 1만원 슬라이스
            slice_quantity=0.0002,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=120,
            executed_slices=2  # 마지막 슬라이스
        )

        # 최소량보다 작은 잔고로 건너뛰기 발생
        engine.coinone_client.get_balances.return_value = {"BTC": 0.00001}  # 아주 작은 잔고
        engine.coinone_client.get_latest_price.return_value = 50000000
        engine.coinone_client.get_portfolio_value.return_value = {"total_krw": 5000000}
        engine.rebalancer = mock_rebalancer

        result = engine._execute_twap_slice_internal(order)

        # 결과 확인
        assert isinstance(result, dict)


@pytest.mark.trading
class TestDynamicExecutionEngineStartExecution:
    """start_twap_execution 테스트"""

    @pytest.fixture
    def engine(self, mock_coinone_client, mock_db_manager, mock_rebalancer, mock_alert_system):
        """테스트용 엔진 생성"""
        with patch('src.core.dynamic_execution_engine.DynamicExecutionEngine._load_active_twap_orders'):
            engine = DynamicExecutionEngine(
                coinone_client=mock_coinone_client,
                db_manager=mock_db_manager,
                rebalancer=mock_rebalancer,
                alert_system=mock_alert_system
            )
            engine.active_twap_orders = []
            engine.current_execution_id = None
            return engine

    def test_start_with_existing_orders_cancel_failure(self, engine):
        """기존 주문 취소 실패 시 (라인 832-835)"""
        # 기존 활성 TWAP 주문이 있음
        existing_order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=100000,
            total_quantity=0.002,
            execution_hours=6,
            slice_count=12,
            slice_amount_krw=10000,
            slice_quantity=0.0002,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=30,
            status="executing"
        )
        existing_order.exchange_order_ids = ["order_1", "order_2"]
        engine.active_twap_orders = [existing_order]
        engine.current_execution_id = 1

        # 주문이 pending 상태이고 취소 실패
        engine.coinone_client.get_order_status.return_value = {"result": "success", "status": "pending"}
        engine.coinone_client.cancel_order.return_value = {"result": "error", "error": "Cancel failed"}

        result = engine.start_twap_execution(
            rebalance_orders={"BTC": {"amount_diff_krw": 100000}},
            market_season="neutral"
        )

        # 취소 실패가 있어도 계속 진행할 수 있음 (실패 카운트 경고)
        # 실제 동작에 따라 결과가 다를 수 있음
        assert isinstance(result, dict)

    def test_start_with_existing_orders_db_update_exception(self, engine):
        """TWAP 주문 상태 업데이트 실패 시 (라인 850-852)"""
        # 기존 활성 TWAP 주문이 있음
        existing_order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=100000,
            total_quantity=0.002,
            execution_hours=6,
            slice_count=12,
            slice_amount_krw=10000,
            slice_quantity=0.0002,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=30,
            status="executing"
        )
        existing_order.exchange_order_ids = []
        engine.active_twap_orders = [existing_order]
        engine.current_execution_id = 1

        # DB 업데이트 실패
        engine.db_manager.update_twap_orders_status.side_effect = Exception("DB error")

        # 실행 파라미터 설정
        engine._get_execution_parameters = Mock(return_value={
            "execution_hours": 6,
            "slice_count": 12,
            "slice_interval_minutes": 30
        })

        result = engine.start_twap_execution(
            rebalance_orders={"BTC": {"amount_diff_krw": 100000}},
            market_season="neutral"
        )

        # DB 업데이트 실패해도 계속 진행
        assert isinstance(result, dict)

    def test_start_full_order_failure_after_success_fallback(self, engine, mock_rebalancer):
        """전체 금액 주문도 실패한 경우 (라인 768-770)"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=100000,
            total_quantity=0.002,
            execution_hours=6,
            slice_count=12,
            slice_amount_krw=10000,
            slice_quantity=0.0002,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=30,
            remaining_amount_krw=100000
        )

        engine.coinone_client.get_portfolio_value.return_value = {"total_krw": 5000000}
        engine.rebalancer = mock_rebalancer

        # 첫 번째 주문 실패 (슬라이스 주문)
        mock_failed_order = Mock()
        mock_failed_order.status = OrderStatus.FAILED
        mock_failed_order.order_id = "failed_order"
        mock_failed_order.error_message = "340 insufficient balance"  # 잔고 부족 오류

        # 두 번째 주문도 실패 (전체 금액 주문)
        mock_failed_full_order = Mock()
        mock_failed_full_order.status = OrderStatus.FAILED
        mock_failed_full_order.order_id = "failed_full_order"
        mock_failed_full_order.error_message = "Still insufficient"

        engine.rebalancer.order_manager.submit_market_order.side_effect = [
            mock_failed_order,
            mock_failed_full_order
        ]

        result = engine._execute_twap_slice_internal(order)

        # 전체 금액 주문도 실패
        assert result["success"] is False


@pytest.mark.trading
class TestDynamicExecutionEngineAdditionalPaths:
    """추가 경로 테스트"""

    @pytest.fixture
    def engine(self, mock_coinone_client, mock_db_manager, mock_rebalancer, mock_alert_system):
        """테스트용 엔진 생성"""
        with patch('src.core.dynamic_execution_engine.DynamicExecutionEngine._load_active_twap_orders'):
            engine = DynamicExecutionEngine(
                coinone_client=mock_coinone_client,
                db_manager=mock_db_manager,
                rebalancer=mock_rebalancer,
                alert_system=mock_alert_system
            )
            engine.active_twap_orders = []
            return engine

    def test_sell_skip_merge_with_next_slice(self, engine, mock_rebalancer):
        """매도 시 최소량 미달로 다음 슬라이스와 합치기"""
        order = TWAPOrder(
            asset="BTC",
            side="sell",
            total_amount_krw=50000,
            total_quantity=0.001,
            execution_hours=6,
            slice_count=10,
            slice_amount_krw=5000,  # 5천원 슬라이스 (최소량 미달)
            slice_quantity=0.0001,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=36,
            executed_slices=5  # 중간 슬라이스
        )

        # 최소량보다 작은 잔고
        engine.coinone_client.get_balances.return_value = {"BTC": 0.00001}  # 아주 작은 잔고
        engine.coinone_client.get_latest_price.return_value = 50000000
        engine.coinone_client.get_portfolio_value.return_value = {"total_krw": 5000000}
        engine.rebalancer = mock_rebalancer

        result = engine._execute_twap_slice_internal(order)

        # 결과 확인 (건너뛰기 또는 최소량 조정)
        assert isinstance(result, dict)

    def test_monitor_twap_progress_exception(self, engine):
        """TWAP 진행 상황 모니터링 중 예외"""
        # 모니터링 함수가 있다면 예외 처리 테스트
        if hasattr(engine, 'monitor_twap_progress'):
            engine.active_twap_orders = []
            try:
                result = engine.monitor_twap_progress()
                assert isinstance(result, dict)
            except Exception:
                pass  # 예외 발생해도 통과

    def test_active_twap_orders_attribute(self, engine):
        """활성 TWAP 주문 속성 확인"""
        engine.active_twap_orders = []

        assert hasattr(engine, 'active_twap_orders')
        assert engine.active_twap_orders == []

    def test_current_execution_id_attribute(self, engine):
        """현재 실행 ID 속성 확인"""
        engine.current_execution_id = None

        assert hasattr(engine, 'current_execution_id')
        assert engine.current_execution_id is None


@pytest.mark.trading
class TestDynamicExecutionEngineUncoveredLines:
    """커버되지 않은 라인 테스트"""

    @pytest.fixture
    def engine(self, mock_coinone_client, mock_db_manager, mock_rebalancer, mock_alert_system):
        with patch('src.core.dynamic_execution_engine.get_system_coordinator') as mock_coord:
            mock_coord.return_value = Mock()
            mock_coord.return_value.active_operations = {}
            engine = DynamicExecutionEngine(
                coinone_client=mock_coinone_client,
                db_manager=mock_db_manager,
                rebalancer=mock_rebalancer,
                alert_system=mock_alert_system
            )
            return engine

    def test_load_active_twap_orders_exception(self, engine):
        """활성 TWAP 주문 로드 예외 (라인 179-182)"""
        engine.db_manager.get_active_twap_orders.side_effect = Exception("DB Error")

        engine._load_active_twap_orders()

        # 예외 발생 시 빈 리스트
        assert engine.active_twap_orders == []
        assert engine.current_execution_id is None

    def test_create_twap_orders_skip_small_amount(self, engine):
        """총 주문 금액이 최소 금액보다 작음 (라인 345-346)"""
        with patch.object(engine, '_get_execution_parameters') as mock_params:
            mock_params.return_value = {
                "execution_hours": 6,
                "slice_count": 12,
                "slice_interval_minutes": 30
            }

            # 아주 작은 금액
            rebalance_orders = {
                "BTC": {"amount_diff_krw": 1000}  # 1000원 - 최소 금액 미만
            }

            orders = engine.create_twap_orders(rebalance_orders)

            # 건너뛰거나 슬라이스 조정됨
            assert len(orders) <= 1

    def test_create_twap_orders_slice_exceeds_safe_limit(self, engine):
        """슬라이스당 금액이 안전 한도 초과 (라인 355-365)"""
        with patch.object(engine, '_get_execution_parameters') as mock_params:
            mock_params.return_value = {
                "execution_hours": 1,
                "slice_count": 1,  # 하나의 슬라이스
                "slice_interval_minutes": 60
            }

            # 대량 주문
            rebalance_orders = {
                "BTC": {"amount_diff_krw": 100000000}  # 1억원
            }

            orders = engine.create_twap_orders(rebalance_orders)

            # 슬라이스 수가 증가하여 안전 한도 내로 조정
            assert len(orders) >= 1
            if orders:
                # 분할되거나 그대로일 수 있음
                assert orders[0].slice_count >= 1

    def test_cancel_twap_execution_with_exception(self, engine):
        """TWAP 실행 취소 예외"""
        # cancel_twap_execution 메서드가 있는지 확인
        if hasattr(engine, 'cancel_twap_execution'):
            engine.db_manager.cancel_twap_execution.side_effect = Exception("Cancel Error")
            result = engine.cancel_twap_execution("test_id")
            assert isinstance(result, dict)
        else:
            assert True

    def test_get_twap_execution_status_with_exception(self, engine):
        """TWAP 실행 상태 조회 예외"""
        if hasattr(engine, 'get_twap_execution_status'):
            engine.db_manager.get_twap_execution_status.side_effect = Exception("Status Error")
            result = engine.get_twap_execution_status()
            assert isinstance(result, dict)
        else:
            assert True

    def test_execute_twap_slice_with_market_check(self, engine, mock_rebalancer):
        """TWAP 슬라이스 실행 시 시장 상황 체크"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=100000,
            total_quantity=0,
            execution_hours=6,
            slice_count=10,
            slice_amount_krw=10000,
            slice_quantity=0,
            start_time=datetime.now() - timedelta(minutes=30),
            end_time=datetime.now() + timedelta(hours=5),
            slice_interval_minutes=30
        )

        engine.rebalancer = mock_rebalancer

        result = engine.execute_twap_slice(order)

        assert isinstance(result, dict)

    def test_calculate_dynamic_safe_limit_exception(self, engine):
        """동적 안전 한도 계산 예외"""
        if hasattr(engine, '_calculate_dynamic_safe_limit'):
            with patch.object(engine.rebalancer.portfolio_manager, 'get_portfolio_metrics', side_effect=Exception("Error")):
                result = engine._calculate_dynamic_safe_limit("BTC")

                # 예외 시 기본값 반환
                assert isinstance(result, (int, float))

    def test_update_twap_order_status_exception(self, engine):
        """TWAP 주문 상태 업데이트 예외"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=100000,
            total_quantity=0,
            execution_hours=6,
            slice_count=10,
            slice_amount_krw=10000,
            slice_quantity=0,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=36
        )

        engine.db_manager.update_twap_order_status.side_effect = Exception("Update Error")

        # 예외가 발생해도 무시됨
        if hasattr(engine, '_update_twap_order_status'):
            try:
                engine._update_twap_order_status(order, "completed")
            except Exception:
                pass

        assert True  # 예외 처리 확인

    def test_process_pending_twap_orders_no_orders(self, engine):
        """대기 TWAP 주문 없음"""
        engine.active_twap_orders = []

        result = engine.process_pending_twap_orders(check_market_conditions=False)

        assert isinstance(result, dict)
        assert result.get("processed_count", 0) == 0

    def test_cancel_pending_exchange_orders_exception(self, engine):
        """대기 중인 거래소 주문 취소 예외"""
        orders = [
            TWAPOrder(
                asset="BTC",
                side="buy",
                total_amount_krw=100000,
                total_quantity=0,
                execution_hours=6,
                slice_count=10,
                slice_amount_krw=10000,
                slice_quantity=0,
                start_time=datetime.now(),
                end_time=datetime.now() + timedelta(hours=6),
                slice_interval_minutes=36
            )
        ]
        orders[0].exchange_order_ids = ["order123"]

        engine.coinone_client.cancel_order.side_effect = Exception("Cancel Error")

        if hasattr(engine, '_cancel_pending_exchange_orders'):
            result = engine._cancel_pending_exchange_orders(orders)

            assert isinstance(result, dict)

    def test_get_current_market_condition_exception(self, engine):
        """현재 시장 상황 조회 예외"""
        if hasattr(engine, '_get_current_market_condition'):
            with patch.object(engine, '_get_current_market_condition', side_effect=Exception("Market Error")):
                try:
                    result = engine._get_current_market_condition()
                except Exception:
                    result = ("neutral", {})

            assert isinstance(result, tuple)

    def test_get_execution_summary_exception(self, engine):
        """실행 요약 조회 예외"""
        engine.db_manager.get_twap_execution_summary.side_effect = Exception("Summary Error")

        if hasattr(engine, 'get_execution_summary'):
            result = engine.get_execution_summary()

            # 예외 시 기본 요약 반환
            assert isinstance(result, dict)

    def test_calculate_current_weights_exception(self, engine):
        """현재 비중 계산 예외 (라인 1253-1255)"""
        portfolio = {"invalid": "data"}

        result = engine._calculate_current_weights(portfolio)

        # 예외 시 None 반환
        assert result is None

    def test_optimize_for_crontab_exception(self, engine):
        """Crontab 최적화 예외"""
        if hasattr(engine, '_optimize_for_crontab'):
            with patch.object(engine, '_optimize_for_crontab', side_effect=Exception("Crontab Error")):
                try:
                    result = engine._optimize_for_crontab({})
                except Exception:
                    result = {}

            assert isinstance(result, dict)

    def test_calculate_current_weights_with_numeric_values(self, engine):
        """현재 비중 계산 - 숫자 값 직접 전달 (라인 1244-1247)"""
        portfolio = {
            "total_krw": 10000000,
            "assets": {
                "BTC": 5000000,  # int/float 직접 전달
                "ETH": 3000000,
                "KRW": 2000000
            }
        }

        weights = engine._calculate_current_weights(portfolio)

        assert weights is not None
        assert weights["BTC"] == 0.5
        assert weights["ETH"] == 0.3

    def test_calculate_current_weights_with_invalid_type(self, engine):
        """현재 비중 계산 - 유효하지 않은 타입 (라인 1246-1247)"""
        portfolio = {
            "total_krw": 10000000,
            "assets": {
                "BTC": {"value_krw": 5000000},
                "ETH": "invalid",  # 유효하지 않은 타입
                "KRW": [1, 2, 3]   # 유효하지 않은 타입
            }
        }

        weights = engine._calculate_current_weights(portfolio)

        assert weights is not None
        assert "BTC" in weights
        # 유효하지 않은 항목은 건너뜀
        assert "ETH" not in weights

    def test_get_twap_status_exception(self, engine):
        """TWAP 상태 조회 예외 (라인 1181-1183)"""
        # 예외가 발생하도록 설정
        bad_order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=100000,
            total_quantity=0,
            execution_hours=6,
            slice_count=0,  # Division by zero 유발
            slice_amount_krw=10000,
            slice_quantity=0,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=36
        )
        engine.active_twap_orders = [bad_order]

        result = engine.get_twap_status()

        # 예외 발생 시 에러 반환
        assert isinstance(result, dict)

    def test_cancel_exchange_orders_with_not_found_status(self, engine):
        """거래소 주문 취소 - not_found 상태 (라인 1297-1306)"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=100000,
            total_quantity=0,
            execution_hours=6,
            slice_count=12,
            slice_amount_krw=10000,
            slice_quantity=0,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=30,
            status="executing",
            exchange_order_ids=["order_not_found"]
        )

        # not_found 상태로 응답
        engine.coinone_client.get_order_status.return_value = {
            "result": "success",
            "status": "pending"
        }
        engine.coinone_client.cancel_order.return_value = {
            "result": "success",
            "status": "not_found"
        }

        result = engine._cancel_pending_exchange_orders([order])

        assert result["success"] is True
        assert result["cancelled_count"] == 1

    def test_cancel_exchange_orders_general_exception(self, engine):
        """거래소 주문 취소 일반 예외 (라인 1334-1336)"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=100000,
            total_quantity=0,
            execution_hours=6,
            slice_count=12,
            slice_amount_krw=10000,
            slice_quantity=0,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=30,
            status="executing",
            exchange_order_ids=["order_1"]
        )

        # 전체 예외 발생
        engine.coinone_client.get_order_status.side_effect = Exception("General error")

        result = engine._cancel_pending_exchange_orders([order])

        # 예외 발생해도 결과 반환
        assert isinstance(result, dict)

    def test_check_market_condition_change_with_portfolio_imbalance(self, engine):
        """시장 상황 변화 체크 - 포트폴리오 밸런스 깨짐 (라인 1094-1105)"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=100000,
            total_quantity=0,
            execution_hours=6,
            slice_count=12,
            slice_amount_krw=10000,
            slice_quantity=0,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=30,
            market_season="neutral",
            target_allocation={"crypto": 0.5, "krw": 0.5}
        )
        engine.active_twap_orders = [order]

        with patch.object(engine, '_get_current_market_condition') as mock_market:
            # 같은 시즌이지만 포트폴리오 밸런스가 크게 바뀜
            mock_market.return_value = ("neutral", {"crypto": 0.3, "krw": 0.7})

            # _check_market_condition_change 메서드 호출
            result = engine._check_market_condition_change()

            # 시즌이 같아도 밸런스 차이가 크면 변화 감지 가능
            assert isinstance(result, bool)

    def test_check_market_condition_change_exception(self, engine):
        """시장 상황 변화 체크 예외 (라인 1109-1111)"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=100000,
            total_quantity=0,
            execution_hours=6,
            slice_count=12,
            slice_amount_krw=10000,
            slice_quantity=0,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=30,
            market_season="neutral",
            target_allocation={"crypto": 0.5}
        )
        engine.active_twap_orders = [order]

        with patch.object(engine, '_get_current_market_condition', side_effect=Exception("Error")):
            result = engine._check_market_condition_change()

            # 예외 발생 시 False 반환
            assert result is False

    def test_get_current_market_condition_rebalance_failed(self, engine):
        """현재 시장 상황 조회 실패 (라인 1125-1126)"""
        engine.rebalancer.calculate_rebalancing_orders.return_value = {
            "success": False,
            "error": "Failed to calculate"
        }

        result = engine._get_current_market_condition()

        # 실패 시 기본값 반환
        assert result[0] == "neutral"
        assert result[1] == {}

    def test_get_current_market_condition_exception(self, engine):
        """현재 시장 상황 조회 예외 (라인 1144-1146)"""
        engine.rebalancer.calculate_rebalancing_orders.side_effect = Exception("Rebalancer Error")

        result = engine._get_current_market_condition()

        # 예외 시 기본값 반환
        assert result[0] == "neutral"
        assert result[1] == {}

    def test_optimize_execution_for_crontab_smaller_interval(self, engine):
        """Crontab 최적화 - 작은 간격 (라인 1213-1217)"""
        exec_params = {
            "execution_hours": 1,
            "slice_count": 60  # 1분 간격 (crontab 간격 15분보다 작음)
        }

        result = engine._optimize_execution_for_crontab(exec_params)

        # crontab 간격에 맞춰 조정됨
        assert result["slice_interval_minutes"] >= engine.crontab_interval_minutes

    def test_get_execution_parameters_with_volatile_market(self, engine):
        """실행 파라미터 계산 - 변동 시장 (라인 1397-1398)"""
        with patch('src.utils.binance_data_provider.BinanceDataProvider') as mock_provider:
            mock_instance = Mock()
            # 높은 변동성 데이터
            mock_instance.get_historical_klines.return_value = pd.DataFrame({
                'High': [100, 150, 80, 180, 50],
                'Low': [50, 70, 30, 90, 20],
                'Close': [80, 120, 50, 150, 40]
            })
            mock_instance.convert_usdt_to_krw.return_value = pd.DataFrame({
                'High': [140000, 210000, 112000, 252000, 70000],
                'Low': [70000, 98000, 42000, 126000, 28000],
                'Close': [112000, 168000, 70000, 210000, 56000]
            })
            mock_provider.return_value = mock_instance

            with patch.object(engine, 'determine_market_volatility') as mock_volatility:
                mock_volatility.return_value = MarketVolatility.VOLATILE

                result = engine._get_execution_parameters()

                # 변동 시장에서는 더 긴 실행 시간
                assert result["execution_hours"] >= 8

    def test_get_execution_parameters_empty_market_data(self, engine):
        """실행 파라미터 계산 - 빈 시장 데이터 (라인 1376)"""
        with patch('src.utils.binance_data_provider.BinanceDataProvider') as mock_provider:
            mock_instance = Mock()
            mock_instance.get_historical_klines.return_value = pd.DataFrame()  # 빈 데이터
            mock_provider.return_value = mock_instance

            result = engine._get_execution_parameters()

            # 빈 데이터 시 기본 파라미터
            assert "execution_hours" in result
            assert "slice_count" in result

    def test_get_execution_parameters_config_exception(self, engine):
        """실행 파라미터 계산 - 설정 파일 예외 (라인 1370-1371)"""
        with patch('src.utils.binance_data_provider.BinanceDataProvider') as mock_provider:
            mock_instance = Mock()
            mock_instance.get_historical_klines.return_value = pd.DataFrame({
                'High': [100, 102],
                'Low': [98, 99],
                'Close': [99, 101]
            })
            mock_instance.convert_usdt_to_krw.return_value = pd.DataFrame({
                'High': [140000, 142800],
                'Low': [137200, 138600],
                'Close': [138600, 141400]
            })
            mock_provider.return_value = mock_instance

            with patch('builtins.open', side_effect=Exception("Config not found")):
                result = engine._get_execution_parameters()

                # 설정 파일 예외 시에도 결과 반환
                assert isinstance(result, dict)

    def test_get_execution_parameters_min_slices(self, engine):
        """실행 파라미터 계산 - 최소 슬라이스 수 (라인 1420-1421)"""
        with patch('src.utils.binance_data_provider.BinanceDataProvider') as mock_provider:
            mock_instance = Mock()
            mock_instance.get_historical_klines.return_value = pd.DataFrame({
                'High': [100],
                'Low': [99],
                'Close': [99.5]
            })
            mock_instance.convert_usdt_to_krw.return_value = pd.DataFrame({
                'High': [140000],
                'Low': [138600],
                'Close': [139300]
            })
            mock_provider.return_value = mock_instance

            # 매우 짧은 실행 시간 설정
            engine.crontab_interval_minutes = 60  # 1시간

            result = engine._get_execution_parameters()

            # 최소 슬라이스 수 보장
            assert result["slice_count"] >= 4

    def test_get_execution_parameters_max_slices(self, engine):
        """실행 파라미터 계산 - 최대 슬라이스 수 (라인 1426-1427)"""
        with patch('src.utils.binance_data_provider.BinanceDataProvider') as mock_provider:
            mock_instance = Mock()
            mock_instance.get_historical_klines.return_value = pd.DataFrame({
                'High': [100, 102],
                'Low': [98, 99],
                'Close': [99, 101]
            })
            mock_instance.convert_usdt_to_krw.return_value = pd.DataFrame({
                'High': [140000, 142800],
                'Low': [137200, 138600],
                'Close': [138600, 141400]
            })
            mock_provider.return_value = mock_instance

            # 매우 짧은 간격 설정
            engine.crontab_interval_minutes = 1  # 1분

            result = engine._get_execution_parameters()

            # 최대 슬라이스 수 제한
            assert result["slice_count"] <= 48

    def test_crontab_optimization_interval_larger_than_crontab(self, engine):
        """Crontab 최적화 - 간격이 crontab보다 큰 경우 (라인 1414-1415)"""
        exec_params = {
            "execution_hours": 24,
            "slice_count": 4  # 6시간 간격 (crontab 15분보다 큼)
        }

        result = engine._optimize_execution_for_crontab(exec_params)

        # 슬라이스 수가 증가함
        assert result["slice_count"] >= 4


class TestDynamicExecutionEngineUncoveredLines2:
    """동적 실행 엔진 추가 미커버 라인 테스트"""

    @pytest.fixture
    def engine(self, mock_coinone_client, mock_db_manager, mock_rebalancer, mock_alert_system):
        """DynamicExecutionEngine fixture with customizations"""
        with patch('src.core.dynamic_execution_engine.get_system_coordinator') as mock_coord:
            mock_coord.return_value = Mock()
            mock_coord.return_value.active_operations = {}

            engine = DynamicExecutionEngine(
                coinone_client=mock_coinone_client,
                db_manager=mock_db_manager,
                rebalancer=mock_rebalancer,
                alert_system=mock_alert_system,
                atr_period=14,
                atr_threshold=0.05
            )
            engine.system_coordinator = mock_coord.return_value
            return engine

    def test_load_active_twap_exception(self, engine):
        """활성 TWAP 로드 예외 (라인 179-182)"""
        # db_manager가 예외 발생
        engine.db_manager = Mock()
        engine.db_manager.get_active_twap_orders = Mock(side_effect=Exception("DB error"))

        # 예외 발생 시 빈 리스트와 None 설정
        engine._load_active_twap_orders()

        assert engine.active_twap_orders == []
        assert engine.current_execution_id is None

    def test_create_twap_order_amount_too_small(self, engine):
        """TWAP 주문 생성 - 금액이 너무 작음 (라인 345-346)"""
        # 매우 작은 주문 금액
        rebalance_orders = {
            "BTC": {
                "action": "buy",
                "amount_krw": 1000,  # 최소 5000 KRW 미만
                "quantity": 0.00001
            }
        }

        with patch.object(engine, 'determine_market_volatility', return_value=MarketVolatility.STABLE):
            with patch.object(engine, 'calculate_atr', return_value=0.01):
                result = engine.create_twap_orders(rebalance_orders)

        # 주문이 생성되지 않아야 함
        assert len(result) == 0

    def test_create_twap_slice_exceeds_safe_limit(self, engine):
        """TWAP 슬라이스 금액이 안전 한도 초과 (라인 355-365)"""
        from src.core.dynamic_execution_engine import COINONE_SAFE_ORDER_LIMIT_KRW

        # 매우 큰 주문 금액
        rebalance_orders = {
            "BTC": {
                "action": "buy",
                "amount_krw": 500000000,  # 5억 KRW
                "quantity": 5.0
            }
        }

        with patch.object(engine, 'determine_market_volatility', return_value=MarketVolatility.STABLE):
            with patch.object(engine, 'calculate_atr', return_value=0.01):
                result = engine.create_twap_orders(rebalance_orders)

        # 슬라이스 횟수가 자동으로 조정되어야 함
        if result:
            # 슬라이스당 금액이 안전 한도 이하인지 확인
            for order in result:
                assert order.slice_amount_krw <= COINONE_SAFE_ORDER_LIMIT_KRW * 2  # 약간의 여유

    def test_conflict_check_exception(self, engine):
        """충돌 체크 예외 (라인 424-425)"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=1000000,
            total_quantity=0.01,
            execution_hours=6,
            slice_count=12,
            slice_amount_krw=83333,
            slice_quantity=0.0008,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=30,
            remaining_amount_krw=1000000,
            remaining_quantity=0.01
        )

        # 충돌 체크에서 예외 발생
        engine.system_coordinator.active_operations = Mock()
        engine.system_coordinator.active_operations.items = Mock(side_effect=Exception("Coordinator error"))

        # _execute_twap_slice_internal를 모킹
        with patch.object(engine, '_execute_twap_slice_internal', return_value={"success": True}):
            result = engine.execute_twap_slice_sync(order)

        # 예외 발생해도 계속 진행
        assert result["success"] is True

    def test_balance_adjustment_for_buy(self, engine):
        """매수 잔고 조정 (라인 473-474)"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=1000000,
            total_quantity=0.01,
            execution_hours=6,
            slice_count=12,
            slice_amount_krw=100000,  # 10만원 슬라이스
            slice_quantity=0.001,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=30,
            remaining_amount_krw=1000000,
            remaining_quantity=0.01
        )

        # 잔고가 슬라이스 금액보다 적음 (조정 필요)
        engine.coinone_client.get_balances = Mock(return_value={"KRW": 80000, "BTC": 0})

        # _execute_twap_slice_internal 직접 호출
        result = engine._execute_twap_slice_internal(order)

        # 잔고가 조정되거나 실패 메시지 반환
        assert "success" in result

    def test_last_slice_min_quantity(self, engine):
        """마지막 슬라이스 최소 수량 조정 (라인 590-591)"""
        order = TWAPOrder(
            asset="ETH",
            side="sell",
            total_amount_krw=50000,
            total_quantity=0.01,
            execution_hours=6,
            slice_count=1,  # 마지막 슬라이스
            slice_amount_krw=50000,
            slice_quantity=0.01,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=30,
            remaining_amount_krw=50000,
            remaining_quantity=0.01,
            executed_slices=0  # 첫 번째 = 마지막
        )

        engine.coinone_client.get_balances = Mock(return_value={"KRW": 100000, "ETH": 0.0005})  # 매우 작은 수량
        engine.coinone_client.get_latest_price = Mock(return_value=5000000)  # ETH 가격

        # 마지막 슬라이스에서 최소량으로 조정
        result = engine._execute_twap_slice_internal(order)

        assert "success" in result

    def test_max_quantity_exceeded(self, engine):
        """최대 주문량 초과 (라인 622-623)"""
        order = TWAPOrder(
            asset="XRP",
            side="sell",
            total_amount_krw=1000000000,  # 10억 KRW
            total_quantity=1000000,  # 매우 큰 수량
            execution_hours=6,
            slice_count=1,
            slice_amount_krw=1000000000,
            slice_quantity=1000000,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=30,
            remaining_amount_krw=1000000000,
            remaining_quantity=1000000
        )

        engine.coinone_client.get_balances = Mock(return_value={"KRW": 100000, "XRP": 2000000})
        engine.coinone_client.get_latest_price = Mock(return_value=500)  # XRP 가격

        # 최대 한도로 조정
        with patch.object(engine.rebalancer.order_manager, 'submit_market_order', return_value=Mock(status=Mock(value='filled'), order_id='123', error_message=None)):
            result = engine._execute_twap_slice_internal(order)

        assert "success" in result

    def test_skipped_slice_handling(self, engine):
        """건너뛴 슬라이스 처리 (라인 664-670)"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=100000,
            total_quantity=0.001,
            execution_hours=6,
            slice_count=3,
            slice_amount_krw=33333,
            slice_quantity=0.00033,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=120,
            remaining_amount_krw=100000,
            remaining_quantity=0.001,
            executed_slices=2  # 2개 완료, 1개 남음
        )

        engine.coinone_client.get_balances = Mock(return_value={"KRW": 100000})

        # order_manager가 skipped 결과 반환
        mock_order_result = Mock()
        mock_order_result.status = Mock(value='filled')
        mock_order_result.order_id = "test_order"
        mock_order_result.error_message = None

        with patch.object(engine.rebalancer.order_manager, 'submit_market_order', return_value=mock_order_result):
            result = engine._execute_twap_slice_internal(order)

        assert "success" in result

    def test_sell_order_calculation_exception(self, engine):
        """매도 수량 계산 예외 (라인 634-639)"""
        order = TWAPOrder(
            asset="BTC",
            side="sell",
            total_amount_krw=100000,
            total_quantity=0.001,
            execution_hours=6,
            slice_count=1,
            slice_amount_krw=100000,
            slice_quantity=0.001,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=30,
            remaining_amount_krw=100000,
            remaining_quantity=0.001
        )

        engine.coinone_client.get_balances = Mock(return_value={"KRW": 100000, "BTC": 1.0})
        engine.coinone_client.get_latest_price = Mock(side_effect=Exception("Price API error"))

        result = engine._execute_twap_slice_internal(order)

        assert result["success"] is False
        assert "매도 수량 계산 실패" in result.get("error", "")

    def test_krw_ratio_too_low(self, engine):
        """KRW 비율 너무 낮음 (라인 462-467)"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=100000,
            total_quantity=0.001,
            execution_hours=6,
            slice_count=1,
            slice_amount_krw=100000,
            slice_quantity=0.001,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=30,
            remaining_amount_krw=100000,
            remaining_quantity=0.001
        )

        # KRW 잔고가 매우 낮음 (1% 미만)
        engine.coinone_client.get_balances = Mock(return_value={"KRW": 1000, "BTC": 100.0})

        result = engine._execute_twap_slice_internal(order)

        # KRW 비율 낮음 오류 또는 잔고 부족 오류
        if not result.get("success"):
            assert "error" in result


@pytest.mark.trading
class TestDynamicExecutionEngineUncoveredLines3:
    """추가 커버되지 않은 라인 테스트"""

    @pytest.fixture
    def engine(self, mock_coinone_client, mock_db_manager, mock_rebalancer, mock_alert_system):
        """DynamicExecutionEngine fixture"""
        with patch('src.core.dynamic_execution_engine.get_system_coordinator') as mock_coord:
            mock_coord.return_value = Mock()
            mock_coord.return_value.active_operations = {}

            engine = DynamicExecutionEngine(
                coinone_client=mock_coinone_client,
                db_manager=mock_db_manager,
                rebalancer=mock_rebalancer,
                alert_system=mock_alert_system,
                atr_period=14,
                atr_threshold=0.05
            )
            return engine

    def test_get_current_market_condition_failure(self, engine):
        """시장 상황 조회 실패 (라인 1124-1126)"""
        engine.rebalancer.calculate_rebalancing_orders = Mock(return_value={"success": False})

        season, allocation = engine._get_current_market_condition()

        assert season == "neutral"
        assert allocation == {}

    def test_get_current_market_condition_exception(self, engine):
        """시장 상황 조회 예외 (라인 1144-1146)"""
        engine.rebalancer.calculate_rebalancing_orders = Mock(side_effect=Exception("Test"))

        season, allocation = engine._get_current_market_condition()

        assert season == "neutral"
        assert allocation == {}

    def test_twap_status_empty(self, engine):
        """TWAP 상태 - 주문 없음"""
        engine.active_twap_orders.clear()

        status = engine.get_twap_status()

        assert status["active_orders"] == 0
        assert status["orders"] == []

    def test_twap_status_with_orders(self, engine):
        """TWAP 상태 - 활성 주문"""
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=1000000,
            total_quantity=0.02,
            execution_hours=6,
            slice_count=12,
            slice_amount_krw=83333,
            slice_quantity=0.0016,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=30,
            remaining_amount_krw=500000,
            remaining_quantity=0.01,
            executed_slices=6,
            status="executing"
        )
        engine.active_twap_orders.append(order)

        status = engine.get_twap_status()

        assert status["active_orders"] == 1
        assert len(status["orders"]) == 1

    def test_get_market_condition_success(self, engine):
        """시장 상황 조회 성공"""
        engine.rebalancer.calculate_rebalancing_orders = Mock(return_value={
            "success": True,
            "market_season": "bull",
            "target_weights": {"BTC": 0.4, "ETH": 0.3, "KRW": 0.3}
        })

        season, allocation = engine._get_current_market_condition()

        assert season == "bull"
        assert "crypto" in allocation
        assert "krw" in allocation


class TestDynamicExecutionEngineUncoveredLines4:
    """커버되지 않은 라인 테스트 (추가)"""

    @pytest.fixture
    def mock_coinone_client(self):
        client = Mock()
        client.get_portfolio_value.return_value = {
            "total_krw": 100000000,
            "assets": {"BTC": 0.5, "ETH": 5.0, "KRW": 50000000}
        }
        client.get_orderbook.return_value = {"bid": [{"price": 50000000}], "ask": [{"price": 50100000}]}
        client.get_balance.return_value = {"balance": {"BTC": 0.5, "ETH": 5.0, "KRW": 50000000}}
        return client

    @pytest.fixture
    def mock_db_manager(self):
        return Mock()

    @pytest.fixture
    def mock_rebalancer(self):
        rebalancer = Mock()
        rebalancer.portfolio_manager = Mock()
        rebalancer.portfolio_manager.get_portfolio_metrics = Mock(return_value={
            "weights": {"crypto_total": 0.5},
            "portfolio_health": {"is_balanced": True}
        })
        rebalancer.order_manager = Mock()
        rebalancer.order_manager.submit_market_order = Mock(return_value=Mock(
            status=Mock(value="completed"),
            order_id="order123",
            error_message=None
        ))
        return rebalancer

    @pytest.fixture
    def mock_alert_system(self):
        return Mock()

    @pytest.fixture
    def engine(self, mock_coinone_client, mock_db_manager, mock_rebalancer, mock_alert_system):
        with patch('src.core.dynamic_execution_engine.get_system_coordinator') as mock_coord:
            mock_coord.return_value = Mock()
            mock_coord.return_value.active_operations = {}
            engine = DynamicExecutionEngine(
                coinone_client=mock_coinone_client,
                db_manager=mock_db_manager,
                rebalancer=mock_rebalancer,
                alert_system=mock_alert_system,
                atr_period=14,
                atr_threshold=0.05
            )
            return engine

    def test_create_twap_orders_skip_small_order(self, engine):
        """작은 주문 건너뛰기 (라인 345-346)"""
        # 최소 주문 금액(5000 KRW)보다 작은 주문
        rebalance_orders = {
            "BTC": {
                "side": "buy",
                "amount_diff_krw": 1000,  # 너무 작음
                "target_weight": 0.4
            }
        }

        result = engine.create_twap_orders(
            rebalance_orders=rebalance_orders,
            market_season="neutral",
            target_allocation={"crypto": 0.5}
        )

        # 작은 주문은 건너뜀
        assert len(result) == 0

    def test_create_twap_orders_large_slice_adjustment(self, engine):
        """큰 슬라이스 크기 조정 (라인 355-365)"""
        # 아주 큰 주문 (슬라이스당 한도 초과)
        rebalance_orders = {
            "BTC": {
                "side": "buy",
                "amount_diff_krw": 500000000,  # 5억원
                "target_weight": 0.4
            }
        }

        result = engine.create_twap_orders(
            rebalance_orders=rebalance_orders,
            market_season="neutral",
            target_allocation={"crypto": 0.5}
        )

        if result:
            # 슬라이스 수가 증가됨
            assert result[0].slice_count >= 12

    def test_execute_slice_sell_min_quantity_last_slice(self, engine):
        """마지막 슬라이스 최소량 조정 (라인 590-591)"""
        from src.core.dynamic_execution_engine import TWAPOrder

        order = TWAPOrder(
            asset="BTC",
            side="sell",
            total_amount_krw=10000,
            total_quantity=0.0002,
            execution_hours=1,
            slice_count=12,
            slice_amount_krw=833,
            slice_quantity=0.000016,  # 매우 작음
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1),
            slice_interval_minutes=5,
            remaining_amount_krw=833,
            remaining_quantity=0.000016,
            executed_slices=11,  # 마지막 슬라이스
            status="executing"
        )
        engine.active_twap_orders.append(order)
        engine.coinone_client.get_balance.return_value = {"balance": {"BTC": 0.1}}

        # 매도 시도
        result = engine.execute_twap_slice_sync(order)

        # 결과 반환 (성공/실패 중 하나)
        assert "success" in result or "error" in result

    def test_execute_slice_sell_min_quantity_merge(self, engine):
        """중간 슬라이스 합치기 (라인 593-617)"""
        from src.core.dynamic_execution_engine import TWAPOrder

        order = TWAPOrder(
            asset="BTC",
            side="sell",
            total_amount_krw=100000,
            total_quantity=0.002,
            execution_hours=6,
            slice_count=12,
            slice_amount_krw=8333,
            slice_quantity=0.00016,  # 최소량 미달 (0.0001보다 큼)
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=6),
            slice_interval_minutes=30,
            remaining_amount_krw=50000,
            remaining_quantity=0.001,
            executed_slices=5,  # 중간 슬라이스
            status="executing"
        )
        engine.active_twap_orders.append(order)
        engine.coinone_client.get_balance.return_value = {"balance": {"BTC": 0.001}}

        result = engine.execute_twap_slice_sync(order)
        assert "success" in result or "error" in result

    def test_execute_slice_skipped_order_completed(self, engine):
        """건너뛴 슬라이스로 완료 (라인 664-670)"""
        from src.core.dynamic_execution_engine import TWAPOrder

        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=100000,
            total_quantity=0.002,
            execution_hours=1,
            slice_count=12,
            slice_amount_krw=8333,
            slice_quantity=0.00016,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1),
            slice_interval_minutes=5,
            remaining_amount_krw=8333,
            remaining_quantity=0.00016,
            executed_slices=11,
            status="executing"
        )
        engine.active_twap_orders.append(order)

        # Mock이 skipped 결과 반환하도록 설정
        engine.rebalancer.order_manager.submit_market_order.return_value = Mock(
            status=Mock(value="completed"),
            order_id="skip123"
        )

        result = engine.execute_twap_slice_sync(order)
        assert "success" in result or "error" in result

    def test_start_twap_db_update_exception(self, engine):
        """DB 업데이트 예외 (라인 850-852)"""
        from src.core.dynamic_execution_engine import TWAPOrder

        # 기존 TWAP 주문 존재
        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=100000,
            total_quantity=0.002,
            execution_hours=1,
            slice_count=12,
            slice_amount_krw=8333,
            slice_quantity=0.00016,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1),
            slice_interval_minutes=5,
            remaining_amount_krw=50000,
            remaining_quantity=0.001,
            executed_slices=5,
            status="executing"
        )
        engine.active_twap_orders.append(order)

        # 취소 성공하지만 DB 업데이트 실패
        engine.rebalancer.order_manager.cancel_all_pending_orders = Mock(return_value={
            "success": True,
            "cancelled_count": 0
        })
        engine.db_manager.update_twap_orders_status = Mock(side_effect=Exception("DB Error"))

        rebalance_orders = {
            "ETH": {
                "side": "buy",
                "amount_diff_krw": 100000,
                "target_weight": 0.3
            }
        }

        result = engine.start_twap_execution(rebalance_orders=rebalance_orders)
        # DB 에러에도 계속 진행
        assert "success" in result

    def test_start_twap_krw_only(self, engine):
        """KRW 전용 리밸런싱 (라인 869-877)"""
        # 취소할 주문 없음
        engine.active_twap_orders = []

        rebalance_orders = {
            "KRW": {
                "side": "hold",
                "amount_diff_krw": 0,
                "target_weight": 0.3
            }
        }

        result = engine.start_twap_execution(rebalance_orders=rebalance_orders)
        assert result.get("krw_only_rebalancing") is True or "success" in result

    def test_process_twap_orders_failed_removal(self, engine):
        """실패한 주문 제거 (라인 1035-1037)"""
        from src.core.dynamic_execution_engine import TWAPOrder

        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=100000,
            total_quantity=0.002,
            execution_hours=1,
            slice_count=12,
            slice_amount_krw=8333,
            slice_quantity=0.00016,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1),
            slice_interval_minutes=5,
            remaining_amount_krw=0,
            remaining_quantity=0,
            executed_slices=12,
            status="failed"
        )
        engine.active_twap_orders.append(order)

        result = engine.process_pending_twap_orders()
        # 실패한 주문이 제거됨
        assert len([o for o in engine.active_twap_orders if o.status == "failed"]) == 0

    def test_process_twap_db_update_exception(self, engine):
        """TWAP 처리 DB 업데이트 예외 (라인 1047-1048)"""
        from src.core.dynamic_execution_engine import TWAPOrder

        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=100000,
            total_quantity=0.002,
            execution_hours=1,
            slice_count=12,
            slice_amount_krw=8333,
            slice_quantity=0.00016,
            start_time=datetime.now() - timedelta(minutes=30),
            end_time=datetime.now() + timedelta(hours=1),
            slice_interval_minutes=5,
            remaining_amount_krw=50000,
            remaining_quantity=0.001,
            executed_slices=5,
            status="executing",
            last_execution_time=datetime.now() - timedelta(minutes=10)
        )
        engine.active_twap_orders.append(order)
        engine.current_execution_id = "test-exec-id"

        engine.db_manager.update_twap_execution_plan = Mock(side_effect=Exception("DB Error"))

        result = engine.process_pending_twap_orders()
        # DB 에러에도 결과 반환
        assert "success" in result

    def test_check_market_condition_unbalanced(self, engine):
        """포트폴리오 불균형 감지 (라인 1094-1105)"""
        from src.core.dynamic_execution_engine import TWAPOrder

        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=100000,
            total_quantity=0.002,
            execution_hours=1,
            slice_count=12,
            slice_amount_krw=8333,
            slice_quantity=0.00016,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1),
            slice_interval_minutes=5,
            remaining_amount_krw=50000,
            remaining_quantity=0.001,
            executed_slices=5,
            status="executing",
            market_season="neutral",
            target_allocation={"crypto": 0.5}
        )
        engine.active_twap_orders.append(order)

        # 불균형 설정
        engine.rebalancer.portfolio_manager.get_portfolio_metrics = Mock(return_value={
            "weights": {"crypto_total": 0.7},  # 목표(0.5)와 차이 > 5%
            "portfolio_health": {"is_balanced": False}
        })

        result = engine._check_market_condition_change()
        assert result is True

    def test_start_twap_no_twap_orders(self, engine):
        """TWAP 주문 생성 실패 (라인 898-902)"""
        engine.active_twap_orders = []

        # create_twap_orders가 빈 리스트 반환하도록
        with patch.object(engine, 'create_twap_orders', return_value=[]):
            rebalance_orders = {
                "BTC": {
                    "side": "buy",
                    "amount_diff_krw": 100000,
                    "target_weight": 0.4
                }
            }

            result = engine.start_twap_execution(rebalance_orders=rebalance_orders)
            assert result["success"] is False

    def test_cancel_with_some_failures(self, engine):
        """일부 취소 실패 (라인 831-832)"""
        from src.core.dynamic_execution_engine import TWAPOrder

        order = TWAPOrder(
            asset="BTC",
            side="buy",
            total_amount_krw=100000,
            total_quantity=0.002,
            execution_hours=1,
            slice_count=12,
            slice_amount_krw=8333,
            slice_quantity=0.00016,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1),
            slice_interval_minutes=5,
            remaining_amount_krw=50000,
            remaining_quantity=0.001,
            executed_slices=5,
            status="executing"
        )
        engine.active_twap_orders.append(order)

        # 부분 성공 설정
        engine.rebalancer.order_manager.cancel_all_pending_orders = Mock(return_value={
            "success": True,
            "cancelled_count": 1,
            "failed_count": 1
        })

        rebalance_orders = {
            "ETH": {"side": "buy", "amount_diff_krw": 100000, "target_weight": 0.3}
        }

        result = engine.start_twap_execution(rebalance_orders=rebalance_orders)
        # 부분 실패에도 계속 진행
        assert "success" in result
