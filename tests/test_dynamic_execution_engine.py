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

        assert weights == {}


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
