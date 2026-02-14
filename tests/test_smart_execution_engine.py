"""
Smart Execution Engine Tests

스마트 실행 엔진 테스트
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch

from src.core.smart_execution_engine import (
    SmartExecutionEngine,
    SmartOrderParams,
    ExecutionResult,
    ExecutionStrategy,
    MarketCondition
)
from src.trading.order_manager import OrderStatus


@pytest.mark.trading
class TestExecutionStrategy:
    """ExecutionStrategy Enum 테스트"""

    def test_strategy_values(self):
        """전략 값 확인"""
        assert ExecutionStrategy.MARKET.value == "market"
        assert ExecutionStrategy.LIMIT_AGGRESSIVE.value == "limit_aggressive"
        assert ExecutionStrategy.LIMIT_CONSERVATIVE.value == "limit_conservative"
        assert ExecutionStrategy.TWAP_SMART.value == "twap_smart"

    def test_strategy_count(self):
        """전략 개수 확인"""
        assert len(ExecutionStrategy) == 4


@pytest.mark.trading
class TestMarketCondition:
    """MarketCondition Enum 테스트"""

    def test_condition_values(self):
        """시장 상황 값 확인"""
        assert MarketCondition.VERY_BULLISH.value == "very_bullish"
        assert MarketCondition.BULLISH.value == "bullish"
        assert MarketCondition.NEUTRAL.value == "neutral"
        assert MarketCondition.BEARISH.value == "bearish"
        assert MarketCondition.VERY_BEARISH.value == "very_bearish"

    def test_condition_count(self):
        """시장 상황 개수 확인"""
        assert len(MarketCondition) == 5


@pytest.mark.trading
class TestSmartOrderParams:
    """SmartOrderParams 데이터클래스 테스트"""

    def test_basic_params(self):
        """기본 파라미터 생성"""
        params = SmartOrderParams(
            asset="BTC",
            side="buy",
            amount_krw=100000,
            strategy=ExecutionStrategy.MARKET,
            market_condition=MarketCondition.NEUTRAL,
            urgency_score=0.5,
            confidence_score=0.8
        )

        assert params.asset == "BTC"
        assert params.side == "buy"
        assert params.amount_krw == 100000
        assert params.strategy == ExecutionStrategy.MARKET
        assert params.urgency_score == 0.5
        assert params.confidence_score == 0.8

    def test_default_values(self):
        """기본값 확인"""
        params = SmartOrderParams(
            asset="ETH",
            side="sell",
            amount_krw=50000,
            strategy=ExecutionStrategy.LIMIT_AGGRESSIVE,
            market_condition=MarketCondition.BULLISH,
            urgency_score=0.3,
            confidence_score=0.7
        )

        assert params.max_slippage == 0.005
        assert params.timeout_minutes == 30
        assert params.multi_timeframe_signal == 0
        assert params.onchain_signal == 0
        assert params.macro_signal == 0
        assert params.sentiment_signal == 0
        assert params.max_position_size == 0.1
        assert params.stop_loss is None
        assert params.take_profit is None

    def test_full_params(self):
        """전체 파라미터 포함"""
        params = SmartOrderParams(
            asset="BTC",
            side="buy",
            amount_krw=1000000,
            strategy=ExecutionStrategy.TWAP_SMART,
            market_condition=MarketCondition.VERY_BULLISH,
            urgency_score=0.9,
            confidence_score=0.95,
            max_slippage=0.01,
            timeout_minutes=60,
            multi_timeframe_signal=0.8,
            onchain_signal=0.6,
            macro_signal=0.4,
            sentiment_signal=0.7,
            max_position_size=0.15,
            stop_loss=45000000,
            take_profit=55000000
        )

        assert params.max_slippage == 0.01
        assert params.multi_timeframe_signal == 0.8
        assert params.stop_loss == 45000000


@pytest.mark.trading
class TestExecutionResult:
    """ExecutionResult 데이터클래스 테스트"""

    def test_success_result(self):
        """성공 결과 생성"""
        result = ExecutionResult(
            success=True,
            asset="BTC",
            side="buy",
            requested_amount_krw=100000,
            executed_amount_krw=99500,
            executed_quantity=0.002,
            average_price=49750000,
            slippage=0.001,
            fees=50,
            order_ids=["order_001"]
        )

        assert result.success is True
        assert result.executed_amount_krw == 99500
        assert result.slippage == 0.001
        assert len(result.order_ids) == 1

    def test_failure_result(self):
        """실패 결과 생성"""
        result = ExecutionResult(
            success=False,
            asset="ETH",
            side="sell",
            requested_amount_krw=50000,
            error_message="잔고 부족"
        )

        assert result.success is False
        assert result.error_message == "잔고 부족"
        assert result.executed_amount_krw == 0

    def test_post_init_defaults(self):
        """post_init 기본값 확인"""
        result = ExecutionResult(
            success=True,
            asset="BTC",
            side="buy",
            requested_amount_krw=100000
        )

        assert isinstance(result.execution_time, datetime)
        assert result.order_ids == []


@pytest.mark.trading
class TestSmartExecutionEngineInit:
    """SmartExecutionEngine 초기화 테스트"""

    @pytest.fixture
    def mock_client(self):
        """Mock Coinone 클라이언트"""
        return Mock()

    @pytest.fixture
    def mock_order_manager(self):
        """Mock 주문 관리자"""
        return Mock()

    def test_init_basic(self, mock_client, mock_order_manager):
        """기본 초기화"""
        engine = SmartExecutionEngine(mock_client, mock_order_manager)

        assert engine.coinone_client == mock_client
        assert engine.order_manager == mock_order_manager
        assert engine.multi_timeframe_analyzer is None
        assert engine.onchain_analyzer is None

    def test_init_with_analyzers(self, mock_client, mock_order_manager):
        """분석기 포함 초기화"""
        mock_mtf = Mock()
        mock_onchain = Mock()

        engine = SmartExecutionEngine(
            mock_client,
            mock_order_manager,
            multi_timeframe_analyzer=mock_mtf,
            onchain_analyzer=mock_onchain
        )

        assert engine.multi_timeframe_analyzer == mock_mtf
        assert engine.onchain_analyzer == mock_onchain

    def test_init_execution_stats(self, mock_client, mock_order_manager):
        """실행 통계 초기화"""
        engine = SmartExecutionEngine(mock_client, mock_order_manager)

        stats = engine.execution_stats
        assert stats["total_orders"] == 0
        assert stats["successful_orders"] == 0
        assert stats["failed_orders"] == 0
        assert stats["average_slippage"] == 0
        assert stats["total_fees"] == 0


@pytest.mark.trading
class TestCalculateCombinedSignal:
    """종합 신호 계산 테스트"""

    @pytest.fixture
    def engine(self):
        """SmartExecutionEngine 인스턴스"""
        return SmartExecutionEngine(Mock(), Mock())

    def test_no_signals(self, engine):
        """신호 없음"""
        params = SmartOrderParams(
            asset="BTC", side="buy", amount_krw=100000,
            strategy=ExecutionStrategy.MARKET,
            market_condition=MarketCondition.NEUTRAL,
            urgency_score=0.5, confidence_score=0.8
        )

        signal = engine._calculate_combined_signal(params)

        assert signal == 0.0

    def test_single_signal(self, engine):
        """단일 신호"""
        params = SmartOrderParams(
            asset="BTC", side="buy", amount_krw=100000,
            strategy=ExecutionStrategy.MARKET,
            market_condition=MarketCondition.NEUTRAL,
            urgency_score=0.5, confidence_score=1.0,
            multi_timeframe_signal=0.8
        )

        signal = engine._calculate_combined_signal(params)

        assert signal == pytest.approx(0.8, rel=0.01)

    def test_multiple_signals(self, engine):
        """여러 신호 종합"""
        params = SmartOrderParams(
            asset="BTC", side="buy", amount_krw=100000,
            strategy=ExecutionStrategy.MARKET,
            market_condition=MarketCondition.NEUTRAL,
            urgency_score=0.5, confidence_score=1.0,
            multi_timeframe_signal=0.6,
            onchain_signal=0.4,
            macro_signal=0.2,
            sentiment_signal=0.8
        )

        signal = engine._calculate_combined_signal(params)

        # 가중 평균 계산: (0.6*0.3 + 0.4*0.25 + 0.2*0.2 + 0.8*0.25) / 1.0 = 0.52
        assert signal > 0
        assert signal <= 1.0

    def test_confidence_score_effect(self, engine):
        """신뢰도 점수 영향"""
        params = SmartOrderParams(
            asset="BTC", side="buy", amount_krw=100000,
            strategy=ExecutionStrategy.MARKET,
            market_condition=MarketCondition.NEUTRAL,
            urgency_score=0.5, confidence_score=0.5,  # 50% 신뢰도
            multi_timeframe_signal=1.0
        )

        signal = engine._calculate_combined_signal(params)

        assert signal == pytest.approx(0.5, rel=0.01)  # 1.0 * 0.5


@pytest.mark.trading
class TestCheckPsychologicalBias:
    """심리적 편향 검사 테스트"""

    @pytest.fixture
    def engine_no_bias(self):
        """편향 방지 시스템 없는 엔진"""
        return SmartExecutionEngine(Mock(), Mock())

    def test_no_bias_system(self, engine_no_bias):
        """편향 방지 시스템 없을 때"""
        params = SmartOrderParams(
            asset="BTC", side="buy", amount_krw=100000,
            strategy=ExecutionStrategy.MARKET,
            market_condition=MarketCondition.NEUTRAL,
            urgency_score=0.9, confidence_score=0.8
        )

        result = engine_no_bias._check_psychological_bias(params)

        assert result["allowed"] is True


@pytest.mark.trading
class TestCheckScenarioResponse:
    """시나리오 대응 확인 테스트"""

    @pytest.fixture
    def engine_no_scenario(self):
        """시나리오 시스템 없는 엔진"""
        return SmartExecutionEngine(Mock(), Mock())

    def test_no_scenario_system(self, engine_no_scenario):
        """시나리오 시스템 없을 때"""
        params = SmartOrderParams(
            asset="BTC", side="buy", amount_krw=100000,
            strategy=ExecutionStrategy.MARKET,
            market_condition=MarketCondition.NEUTRAL,
            urgency_score=0.5, confidence_score=0.8
        )

        result = engine_no_scenario._check_scenario_response(params)

        assert result["allowed"] is True

    def test_large_order_check(self, engine_no_scenario):
        """대량 주문 검사"""
        params = SmartOrderParams(
            asset="BTC", side="buy", amount_krw=20000000,  # 2천만원
            strategy=ExecutionStrategy.MARKET,
            market_condition=MarketCondition.NEUTRAL,
            urgency_score=0.5, confidence_score=0.8
        )

        result = engine_no_scenario._check_scenario_response(params)

        assert result["allowed"] is True  # 시스템 없으면 허용


@pytest.mark.trading
class TestValidateOrderParameters:
    """주문 파라미터 검증 테스트"""

    @pytest.fixture
    def engine_with_mocks(self):
        """Mock이 설정된 엔진"""
        mock_client = Mock()
        mock_client.supported_coins = ["BTC", "ETH", "XRP"]
        mock_client.get_balances.return_value = {"KRW": 1000000, "BTC": 0.1}
        mock_client.get_latest_price.return_value = 50000000
        mock_client.get_ticker.return_value = {"success": True}

        return SmartExecutionEngine(mock_client, Mock())

    def test_valid_buy_order(self, engine_with_mocks):
        """유효한 매수 주문"""
        params = SmartOrderParams(
            asset="BTC", side="buy", amount_krw=100000,
            strategy=ExecutionStrategy.MARKET,
            market_condition=MarketCondition.NEUTRAL,
            urgency_score=0.5, confidence_score=0.8
        )

        result = engine_with_mocks._validate_order_parameters(params)

        assert result["valid"] is True

    def test_amount_too_small(self, engine_with_mocks):
        """주문 금액 너무 작음"""
        params = SmartOrderParams(
            asset="BTC", side="buy", amount_krw=500,  # 500원
            strategy=ExecutionStrategy.MARKET,
            market_condition=MarketCondition.NEUTRAL,
            urgency_score=0.5, confidence_score=0.8
        )

        result = engine_with_mocks._validate_order_parameters(params)

        assert result["valid"] is False
        assert "너무 작습니다" in result["error"]

    def test_unsupported_coin(self, engine_with_mocks):
        """지원하지 않는 코인"""
        params = SmartOrderParams(
            asset="UNKNOWN", side="buy", amount_krw=100000,
            strategy=ExecutionStrategy.MARKET,
            market_condition=MarketCondition.NEUTRAL,
            urgency_score=0.5, confidence_score=0.8
        )

        result = engine_with_mocks._validate_order_parameters(params)

        assert result["valid"] is False
        assert "지원하지 않는 코인" in result["error"]

    def test_insufficient_krw_balance(self, engine_with_mocks):
        """KRW 잔고 부족"""
        params = SmartOrderParams(
            asset="BTC", side="buy", amount_krw=2000000,  # 잔고보다 많음
            strategy=ExecutionStrategy.MARKET,
            market_condition=MarketCondition.NEUTRAL,
            urgency_score=0.5, confidence_score=0.8
        )

        result = engine_with_mocks._validate_order_parameters(params)

        assert result["valid"] is False
        assert "잔고 부족" in result["error"]


@pytest.mark.trading
class TestUpdateExecutionStats:
    """실행 통계 업데이트 테스트"""

    @pytest.fixture
    def engine(self):
        """SmartExecutionEngine 인스턴스"""
        return SmartExecutionEngine(Mock(), Mock())

    def test_successful_order_stats(self, engine):
        """성공 주문 통계"""
        result = ExecutionResult(
            success=True,
            asset="BTC", side="buy",
            requested_amount_krw=100000,
            executed_amount_krw=99500,
            slippage=0.005,
            fees=50
        )

        engine._update_execution_stats(result)

        assert engine.execution_stats["total_orders"] == 1
        assert engine.execution_stats["successful_orders"] == 1
        assert engine.execution_stats["failed_orders"] == 0
        assert engine.execution_stats["total_fees"] == 50
        assert engine.execution_stats["average_slippage"] == 0.005

    def test_failed_order_stats(self, engine):
        """실패 주문 통계"""
        result = ExecutionResult(
            success=False,
            asset="BTC", side="buy",
            requested_amount_krw=100000,
            error_message="Error"
        )

        engine._update_execution_stats(result)

        assert engine.execution_stats["total_orders"] == 1
        assert engine.execution_stats["successful_orders"] == 0
        assert engine.execution_stats["failed_orders"] == 1

    def test_multiple_orders_stats(self, engine):
        """여러 주문 통계"""
        result1 = ExecutionResult(
            success=True, asset="BTC", side="buy",
            requested_amount_krw=100000, slippage=0.004, fees=50
        )
        result2 = ExecutionResult(
            success=True, asset="ETH", side="buy",
            requested_amount_krw=50000, slippage=0.006, fees=30
        )

        engine._update_execution_stats(result1)
        engine._update_execution_stats(result2)

        assert engine.execution_stats["total_orders"] == 2
        assert engine.execution_stats["successful_orders"] == 2
        assert engine.execution_stats["total_fees"] == 80
        # 평균 슬리피지: (0.004 + 0.006) / 2 = 0.005
        assert engine.execution_stats["average_slippage"] == pytest.approx(0.005, rel=0.01)


@pytest.mark.trading
class TestGetExecutionStats:
    """실행 통계 조회 테스트"""

    @pytest.fixture
    def engine(self):
        """SmartExecutionEngine 인스턴스"""
        return SmartExecutionEngine(Mock(), Mock())

    def test_get_stats_copy(self, engine):
        """통계 복사본 반환"""
        stats = engine.get_execution_stats()

        assert stats["total_orders"] == 0
        assert stats is not engine.execution_stats  # 복사본

    def test_stats_modification_isolation(self, engine):
        """통계 수정 격리"""
        stats = engine.get_execution_stats()
        stats["total_orders"] = 100

        assert engine.execution_stats["total_orders"] == 0


@pytest.mark.trading
class TestGetOptimalStrategy:
    """최적 전략 추천 테스트"""

    @pytest.fixture
    def engine(self):
        """SmartExecutionEngine 인스턴스"""
        return SmartExecutionEngine(Mock(), Mock())

    def test_small_order_market(self, engine):
        """소액 주문 -> 시장가"""
        strategy = engine.get_optimal_strategy("BTC", "buy", 50000)

        assert strategy == ExecutionStrategy.MARKET

    def test_medium_order_limit(self, engine):
        """중간 주문 -> 지정가"""
        strategy = engine.get_optimal_strategy("BTC", "buy", 500000)

        assert strategy == ExecutionStrategy.LIMIT_AGGRESSIVE

    def test_large_order_twap(self, engine):
        """대량 주문 -> TWAP"""
        strategy = engine.get_optimal_strategy("BTC", "buy", 5000000)

        assert strategy == ExecutionStrategy.TWAP_SMART


@pytest.mark.trading
class TestPostExecutionAnalysis:
    """실행 후 분석 테스트"""

    @pytest.fixture
    def engine(self):
        """SmartExecutionEngine 인스턴스"""
        return SmartExecutionEngine(Mock(), Mock())

    def test_failed_result_skip(self, engine):
        """실패 결과 스킵"""
        params = SmartOrderParams(
            asset="BTC", side="buy", amount_krw=100000,
            strategy=ExecutionStrategy.MARKET,
            market_condition=MarketCondition.NEUTRAL,
            urgency_score=0.5, confidence_score=0.8
        )
        result = ExecutionResult(
            success=False, asset="BTC", side="buy",
            requested_amount_krw=100000
        )

        # 예외 없이 완료되어야 함
        engine._post_execution_analysis(params, result)

    def test_high_slippage_warning(self, engine):
        """높은 슬리피지 경고"""
        params = SmartOrderParams(
            asset="BTC", side="buy", amount_krw=100000,
            strategy=ExecutionStrategy.MARKET,
            market_condition=MarketCondition.NEUTRAL,
            urgency_score=0.5, confidence_score=0.8,
            max_slippage=0.005  # 0.5%
        )
        result = ExecutionResult(
            success=True, asset="BTC", side="buy",
            requested_amount_krw=100000,
            executed_amount_krw=99000,
            slippage=0.01  # 1% - 허용치 초과
        )

        # 예외 없이 완료되어야 함
        engine._post_execution_analysis(params, result)


@pytest.mark.trading
class TestExecuteSmartOrder:
    """스마트 주문 실행 통합 테스트"""

    @pytest.fixture
    def mock_client(self):
        """Mock Coinone 클라이언트"""
        client = Mock()
        client.supported_coins = ["BTC", "ETH"]
        client.get_balances.return_value = {"KRW": 1000000, "BTC": 0.1}
        client.get_latest_price.return_value = 50000000
        client.get_ticker.return_value = {"success": True}
        client.get_portfolio_value.return_value = {
            "total_krw": 10000000,
            "assets": {"BTC": {"value_krw": 5000000}}
        }
        return client

    @pytest.fixture
    def mock_order_manager(self):
        """Mock 주문 관리자"""
        manager = Mock()
        order = Mock()
        order.status = OrderStatus.SUBMITTED
        order.order_id = "order_001"
        order.filled_amount = 0.002
        order.average_price = 50000000
        order.fee = 50
        manager.submit_market_order.return_value = order
        manager.check_order_status.return_value = OrderStatus.FILLED
        return manager

    def test_successful_market_order(self, mock_client, mock_order_manager):
        """성공적인 시장가 주문"""
        engine = SmartExecutionEngine(mock_client, mock_order_manager)

        params = SmartOrderParams(
            asset="BTC", side="buy", amount_krw=100000,
            strategy=ExecutionStrategy.MARKET,
            market_condition=MarketCondition.NEUTRAL,
            urgency_score=0.5, confidence_score=0.8
        )

        result = engine.execute_smart_order(params)

        assert result.asset == "BTC"
        assert result.side == "buy"
        # 주문이 제출됐는지 확인
        mock_order_manager.submit_market_order.assert_called()

    def test_validation_failure(self, mock_client, mock_order_manager):
        """검증 실패"""
        engine = SmartExecutionEngine(mock_client, mock_order_manager)

        params = SmartOrderParams(
            asset="UNKNOWN", side="buy", amount_krw=100000,
            strategy=ExecutionStrategy.MARKET,
            market_condition=MarketCondition.NEUTRAL,
            urgency_score=0.5, confidence_score=0.8
        )

        result = engine.execute_smart_order(params)

        assert result.success is False
        assert "지원하지 않는 코인" in result.error_message

    def test_exception_handling(self, mock_client, mock_order_manager):
        """예외 처리"""
        mock_order_manager.submit_market_order.side_effect = Exception("Network error")
        engine = SmartExecutionEngine(mock_client, mock_order_manager)

        params = SmartOrderParams(
            asset="BTC", side="buy", amount_krw=100000,
            strategy=ExecutionStrategy.MARKET,
            market_condition=MarketCondition.NEUTRAL,
            urgency_score=0.5, confidence_score=0.8
        )

        result = engine.execute_smart_order(params)

        assert result.success is False
        assert "Network error" in result.error_message


@pytest.mark.trading
class TestEdgeCases:
    """엣지 케이스 테스트"""

    @pytest.fixture
    def engine(self):
        """SmartExecutionEngine 인스턴스"""
        mock_client = Mock()
        mock_client.supported_coins = ["BTC"]
        mock_client.get_portfolio_value.return_value = {"total_krw": 0, "assets": {}}
        return SmartExecutionEngine(mock_client, Mock())

    def test_zero_portfolio_value(self, engine):
        """포트폴리오 가치 0"""
        params = SmartOrderParams(
            asset="BTC", side="buy", amount_krw=100000,
            strategy=ExecutionStrategy.MARKET,
            market_condition=MarketCondition.NEUTRAL,
            urgency_score=0.5, confidence_score=0.8
        )

        # _optimize_order_size 메서드는 0 포트폴리오에서도 동작해야 함
        result = engine._optimize_order_size(params, 0.5)

        assert result.amount_krw >= 10000  # 최소 주문 크기

    def test_negative_signal_buy(self):
        """매수 시 부정적 신호"""
        mock_client = Mock()
        mock_client.supported_coins = ["BTC"]
        # 포트폴리오 가치가 있어야 최적화 로직이 실행됨
        mock_client.get_portfolio_value.return_value = {"total_krw": 10000000, "assets": {}}
        engine = SmartExecutionEngine(mock_client, Mock())

        params = SmartOrderParams(
            asset="BTC", side="buy", amount_krw=100000,
            strategy=ExecutionStrategy.MARKET,
            market_condition=MarketCondition.NEUTRAL,
            urgency_score=0.5, confidence_score=0.8
        )

        result = engine._optimize_order_size(params, -0.5)

        # 부정적 신호 시 주문 크기 감소 (0.7배)
        assert result.amount_krw == pytest.approx(70000, rel=0.01)

    def test_empty_signals_combined(self, engine):
        """모든 신호가 0일 때"""
        params = SmartOrderParams(
            asset="BTC", side="buy", amount_krw=100000,
            strategy=ExecutionStrategy.MARKET,
            market_condition=MarketCondition.NEUTRAL,
            urgency_score=0.5, confidence_score=0.8,
            multi_timeframe_signal=0,
            onchain_signal=0,
            macro_signal=0,
            sentiment_signal=0
        )

        signal = engine._calculate_combined_signal(params)

        assert signal == 0.0
