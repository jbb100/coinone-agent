"""
Multi Account Feature Manager Tests
multi_account_feature_manager.py 모듈의 테스트
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timedelta

from src.core.multi_account_feature_manager import (
    MultiAccountFeatureManager,
    MultiAccountOperationResult,
    get_multi_account_feature_manager
)
from src.core.types import AccountID
from src.core.exceptions import KairosException, ConfigurationException


class TestMultiAccountOperationResult:
    """MultiAccountOperationResult 테스트"""

    def test_success_rate_with_accounts(self):
        """성공률 계산 - 계정 있음"""
        result = MultiAccountOperationResult(
            total_accounts=4,
            successful_accounts=[AccountID("acc1"), AccountID("acc2"), AccountID("acc3")],
            failed_accounts=[AccountID("acc4")],
            results={},
            errors={},
            execution_time=1.5,
            started_at=datetime.now(),
            completed_at=datetime.now()
        )

        assert result.success_rate == 0.75

    def test_success_rate_no_accounts(self):
        """성공률 계산 - 계정 없음"""
        result = MultiAccountOperationResult(
            total_accounts=0,
            successful_accounts=[],
            failed_accounts=[],
            results={},
            errors={},
            execution_time=0,
            started_at=datetime.now(),
            completed_at=datetime.now()
        )

        assert result.success_rate == 0.0

    def test_is_fully_successful_true(self):
        """전체 성공 - 실패 없음"""
        result = MultiAccountOperationResult(
            total_accounts=2,
            successful_accounts=[AccountID("acc1"), AccountID("acc2")],
            failed_accounts=[],
            results={},
            errors={},
            execution_time=1.0,
            started_at=datetime.now(),
            completed_at=datetime.now()
        )

        assert result.is_fully_successful is True

    def test_is_fully_successful_false(self):
        """전체 성공 아님 - 실패 있음"""
        result = MultiAccountOperationResult(
            total_accounts=2,
            successful_accounts=[AccountID("acc1")],
            failed_accounts=[AccountID("acc2")],
            results={},
            errors={},
            execution_time=1.0,
            started_at=datetime.now(),
            completed_at=datetime.now()
        )

        assert result.is_fully_successful is False


class TestMultiAccountFeatureManagerInit:
    """MultiAccountFeatureManager 초기화 테스트"""

    @pytest.fixture
    def mock_dependencies(self):
        """의존성 Mock"""
        with patch('src.core.multi_account_feature_manager.get_multi_account_manager') as mock_mam, \
             patch('src.core.multi_account_feature_manager.get_system_coordinator') as mock_coord, \
             patch('src.core.multi_account_feature_manager.MacroEconomicAnalyzer') as mock_macro, \
             patch('src.core.multi_account_feature_manager.OnchainDataAnalyzer') as mock_onchain, \
             patch('src.core.multi_account_feature_manager.ScenarioResponseSystem') as mock_scenario, \
             patch('src.core.multi_account_feature_manager.BehavioralBiasPrevention') as mock_bias:
            mock_mam.return_value = Mock()
            mock_coord.return_value = Mock()
            yield {
                'multi_account_manager': mock_mam,
                'system_coordinator': mock_coord,
                'macro_analyzer': mock_macro,
                'onchain_analyzer': mock_onchain,
                'scenario_system': mock_scenario,
                'bias_prevention': mock_bias
            }

    def test_init_without_dependencies(self, mock_dependencies):
        """의존성 없이 초기화"""
        manager = MultiAccountFeatureManager()

        assert manager.db_manager is None
        assert manager.market_season_filter is None

    def test_init_with_dependencies(self, mock_dependencies):
        """의존성과 함께 초기화"""
        mock_db = Mock()
        mock_filter = Mock()

        manager = MultiAccountFeatureManager(
            db_manager=mock_db,
            market_season_filter=mock_filter
        )

        assert manager.db_manager is mock_db
        assert manager.market_season_filter is mock_filter

    def test_init_feature_caches_empty(self, mock_dependencies):
        """초기화 시 캐시가 비어있음"""
        manager = MultiAccountFeatureManager()

        assert manager.portfolio_managers == {}
        assert manager.rebalancers == {}
        assert manager.risk_managers == {}
        assert manager.order_managers == {}
        assert manager.adaptive_managers == {}


class TestMultiAccountFeatureManagerInitialize:
    """initialize 메서드 테스트"""

    @pytest.fixture
    def manager(self):
        with patch('src.core.multi_account_feature_manager.get_multi_account_manager') as mock_mam, \
             patch('src.core.multi_account_feature_manager.get_system_coordinator'), \
             patch('src.core.multi_account_feature_manager.MacroEconomicAnalyzer'), \
             patch('src.core.multi_account_feature_manager.OnchainDataAnalyzer'), \
             patch('src.core.multi_account_feature_manager.ScenarioResponseSystem'), \
             patch('src.core.multi_account_feature_manager.BehavioralBiasPrevention'):
            mock_mam.return_value = AsyncMock()
            mock_mam.return_value._initialized = False
            mock_mam.return_value.initialize = AsyncMock()
            mock_mam.return_value.get_all_accounts = AsyncMock(return_value=[])
            mock_mam.return_value.clients = {}
            return MultiAccountFeatureManager()

    @pytest.mark.asyncio
    async def test_initialize_success(self, manager):
        """초기화 성공"""
        await manager.initialize()

        manager.multi_account_manager.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_with_accounts(self, manager):
        """계정이 있는 경우 초기화"""
        mock_client = Mock()
        manager.multi_account_manager.get_all_accounts = AsyncMock(return_value=[
            {"account_id": AccountID("acc1"), "status": Mock(value="active")}
        ])
        manager.multi_account_manager.clients = {AccountID("acc1"): mock_client}

        with patch('src.core.multi_account_feature_manager.PortfolioManager'), \
             patch('src.core.multi_account_feature_manager.OrderManager'), \
             patch('src.core.multi_account_feature_manager.AdaptivePortfolioManager'), \
             patch('src.core.multi_account_feature_manager.DCAPlus'), \
             patch('src.core.multi_account_feature_manager.RiskParityModel'), \
             patch('src.core.multi_account_feature_manager.TaxOptimizationSystem'):
            await manager.initialize()

        assert AccountID("acc1") in manager.portfolio_managers

    @pytest.mark.asyncio
    async def test_initialize_account_no_client(self, manager):
        """클라이언트 없는 계정"""
        manager.multi_account_manager.get_all_accounts = AsyncMock(return_value=[
            {"account_id": AccountID("acc1"), "status": Mock(value="active")}
        ])
        manager.multi_account_manager.clients = {}  # 클라이언트 없음

        await manager.initialize()

        # 클라이언트 없는 계정은 건너뜀
        assert AccountID("acc1") not in manager.portfolio_managers

    @pytest.mark.asyncio
    async def test_initialize_failure(self, manager):
        """초기화 실패"""
        manager.multi_account_manager.initialize = AsyncMock(
            side_effect=Exception("Init failed")
        )

        with pytest.raises(ConfigurationException):
            await manager.initialize()

    @pytest.mark.asyncio
    async def test_initialize_account_feature_failure(self, manager):
        """계정 기능 초기화 실패"""
        mock_client = Mock()
        manager.multi_account_manager.get_all_accounts = AsyncMock(return_value=[
            {"account_id": AccountID("acc1"), "status": Mock(value="active")}
        ])
        manager.multi_account_manager.clients = {AccountID("acc1"): mock_client}

        with patch('src.core.multi_account_feature_manager.PortfolioManager',
                   side_effect=Exception("Portfolio init failed")):
            await manager.initialize()

        # 에러 발생해도 계속 진행
        assert AccountID("acc1") not in manager.portfolio_managers


class TestMultiAccountFeatureManagerOperations:
    """작업 실행 테스트"""

    @pytest.fixture
    def manager(self):
        with patch('src.core.multi_account_feature_manager.get_multi_account_manager') as mock_mam, \
             patch('src.core.multi_account_feature_manager.get_system_coordinator'), \
             patch('src.core.multi_account_feature_manager.MacroEconomicAnalyzer'), \
             patch('src.core.multi_account_feature_manager.OnchainDataAnalyzer'), \
             patch('src.core.multi_account_feature_manager.ScenarioResponseSystem'), \
             patch('src.core.multi_account_feature_manager.BehavioralBiasPrevention'):
            mock_mam.return_value = AsyncMock()
            mock_mam.return_value.get_all_accounts = AsyncMock(return_value=[
                {"account_id": AccountID("acc1"), "status": Mock(value="active")},
                {"account_id": AccountID("acc2"), "status": Mock(value="active")}
            ])
            return MultiAccountFeatureManager()

    @pytest.mark.asyncio
    async def test_run_portfolio_optimization_for_all(self, manager):
        """포트폴리오 최적화 실행"""
        mock_portfolio_manager = Mock()
        mock_portfolio_manager.get_current_portfolio.return_value = {"BTC": 0.5}
        mock_portfolio_manager.get_optimal_allocation.return_value = {"BTC": 0.6}
        manager.portfolio_managers = {
            AccountID("acc1"): mock_portfolio_manager,
            AccountID("acc2"): mock_portfolio_manager
        }

        result = await manager.run_portfolio_optimization_for_all()

        assert result.total_accounts == 2
        assert len(result.successful_accounts) == 2

    @pytest.mark.asyncio
    async def test_run_portfolio_optimization_no_manager(self, manager):
        """포트폴리오 매니저 없는 경우"""
        manager.portfolio_managers = {}

        result = await manager.run_portfolio_optimization_for_all()

        assert result.total_accounts == 2
        assert len(result.failed_accounts) == 2

    @pytest.mark.asyncio
    async def test_execute_rebalancing_for_all(self, manager):
        """리밸런싱 실행"""
        mock_rebalancer = Mock()
        mock_rebalancer.execute_rebalancing.return_value = {"action": "completed"}
        manager.rebalancers = {
            AccountID("acc1"): mock_rebalancer
        }

        result = await manager.execute_rebalancing_for_all(
            target_accounts=[AccountID("acc1")],
            dry_run=True
        )

        assert result.total_accounts == 1
        assert len(result.successful_accounts) == 1

    @pytest.mark.asyncio
    async def test_execute_rebalancing_no_rebalancer(self, manager):
        """리밸런서 없는 경우"""
        manager.rebalancers = {}

        result = await manager.execute_rebalancing_for_all(
            target_accounts=[AccountID("acc1")]
        )

        assert len(result.failed_accounts) == 1

    @pytest.mark.asyncio
    async def test_run_risk_analysis_no_manager(self, manager):
        """리스크 매니저 없는 경우"""
        manager.risk_managers = {}

        result = await manager.run_risk_analysis_for_all(
            target_accounts=[AccountID("acc1")]
        )

        # 리스크 매니저 없어도 기본 결과 반환
        assert len(result.successful_accounts) == 1
        assert result.results[AccountID("acc1")]["risk_metrics"]["status"] == "unavailable"

    @pytest.mark.asyncio
    async def test_run_risk_analysis_with_manager(self, manager):
        """리스크 매니저 있는 경우"""
        mock_risk_manager = Mock()
        mock_risk_manager.calculate_portfolio_risk.return_value = {"risk_level": "medium"}
        mock_risk_manager.calculate_volatility.return_value = 0.15
        mock_risk_manager.calculate_var.return_value = 0.05
        manager.risk_managers = {AccountID("acc1"): mock_risk_manager}

        result = await manager.run_risk_analysis_for_all(
            target_accounts=[AccountID("acc1")]
        )

        assert result.results[AccountID("acc1")]["volatility"] == 0.15

    @pytest.mark.asyncio
    async def test_run_performance_analysis_no_tracker(self, manager):
        """성과 추적기 없는 경우"""
        manager.performance_trackers = {}

        result = await manager.run_performance_analysis_for_all(
            target_accounts=[AccountID("acc1")]
        )

        assert result.results[AccountID("acc1")]["performance_metrics"]["status"] == "unavailable"

    @pytest.mark.asyncio
    async def test_run_performance_analysis_with_tracker(self, manager):
        """성과 추적기 있는 경우"""
        mock_tracker = Mock()
        mock_tracker.generate_performance_report.return_value = {
            "total_return": 0.15,
            "sharpe_ratio": 1.2
        }
        manager.performance_trackers = {AccountID("acc1"): mock_tracker}

        result = await manager.run_performance_analysis_for_all(
            target_accounts=[AccountID("acc1")]
        )

        assert result.results[AccountID("acc1")]["total_return"] == 0.15

    @pytest.mark.asyncio
    async def test_run_dca_strategy_for_all(self, manager):
        """DCA 전략 실행"""
        mock_dca = Mock()
        mock_dca.execute_dca_plus.return_value = {"action": "buy"}
        manager.dca_strategies = {AccountID("acc1"): mock_dca}

        result = await manager.run_dca_strategy_for_all(
            target_accounts=[AccountID("acc1")],
            amount_krw=100000
        )

        assert len(result.successful_accounts) == 1

    @pytest.mark.asyncio
    async def test_run_dca_strategy_no_strategy(self, manager):
        """DCA 전략 없는 경우"""
        manager.dca_strategies = {}

        result = await manager.run_dca_strategy_for_all(
            target_accounts=[AccountID("acc1")]
        )

        assert len(result.failed_accounts) == 1

    @pytest.mark.asyncio
    async def test_run_tax_optimization_for_all(self, manager):
        """세금 최적화 실행"""
        mock_tax = Mock()
        mock_tax.analyze_tax_efficiency.return_value = {"tax_saved": 100000}
        manager.tax_optimizers = {AccountID("acc1"): mock_tax}

        result = await manager.run_tax_optimization_for_all(
            target_accounts=[AccountID("acc1")]
        )

        assert len(result.successful_accounts) == 1

    @pytest.mark.asyncio
    async def test_run_tax_optimization_no_optimizer(self, manager):
        """세금 최적화기 없는 경우"""
        manager.tax_optimizers = {}

        result = await manager.run_tax_optimization_for_all(
            target_accounts=[AccountID("acc1")]
        )

        assert len(result.failed_accounts) == 1


class TestMultiAccountFeatureManagerExecuteForAll:
    """_execute_for_all_accounts 테스트"""

    @pytest.fixture
    def manager(self):
        with patch('src.core.multi_account_feature_manager.get_multi_account_manager') as mock_mam, \
             patch('src.core.multi_account_feature_manager.get_system_coordinator'), \
             patch('src.core.multi_account_feature_manager.MacroEconomicAnalyzer'), \
             patch('src.core.multi_account_feature_manager.OnchainDataAnalyzer'), \
             patch('src.core.multi_account_feature_manager.ScenarioResponseSystem'), \
             patch('src.core.multi_account_feature_manager.BehavioralBiasPrevention'):
            mock_mam.return_value = AsyncMock()
            mock_mam.return_value.get_all_accounts = AsyncMock(return_value=[
                {"account_id": AccountID("acc1"), "status": Mock(value="active")},
                {"account_id": AccountID("acc2"), "status": Mock(value="inactive")}
            ])
            return MultiAccountFeatureManager()

    @pytest.mark.asyncio
    async def test_execute_filters_inactive_accounts(self, manager):
        """비활성 계정 필터링"""
        async def mock_operation(account_id):
            return {"result": "success"}

        result = await manager._execute_for_all_accounts(
            "test_operation",
            mock_operation
        )

        # 활성 계정만 실행
        assert result.total_accounts == 1
        assert AccountID("acc1") in result.successful_accounts

    @pytest.mark.asyncio
    async def test_execute_with_target_accounts(self, manager):
        """대상 계정 지정"""
        async def mock_operation(account_id):
            return {"result": "success"}

        result = await manager._execute_for_all_accounts(
            "test_operation",
            mock_operation,
            target_accounts=[AccountID("acc1"), AccountID("acc2")]
        )

        # 지정된 계정 모두 실행
        assert result.total_accounts == 2

    @pytest.mark.asyncio
    async def test_execute_with_concurrent_limit(self, manager):
        """동시 실행 제한"""
        execution_times = []

        async def mock_operation(account_id):
            execution_times.append(datetime.now())
            await asyncio.sleep(0.1)
            return {"result": "success"}

        manager.max_concurrent_operations = 2
        target = [AccountID(f"acc{i}") for i in range(5)]

        result = await manager._execute_for_all_accounts(
            "test_operation",
            mock_operation,
            target_accounts=target
        )

        assert result.total_accounts == 5
        assert len(result.successful_accounts) == 5


class TestMultiAccountFeatureManagerAnalytics:
    """통합 분석 테스트"""

    @pytest.fixture
    def manager(self):
        with patch('src.core.multi_account_feature_manager.get_multi_account_manager') as mock_mam, \
             patch('src.core.multi_account_feature_manager.get_system_coordinator'), \
             patch('src.core.multi_account_feature_manager.MacroEconomicAnalyzer') as mock_macro, \
             patch('src.core.multi_account_feature_manager.OnchainDataAnalyzer') as mock_onchain, \
             patch('src.core.multi_account_feature_manager.ScenarioResponseSystem'), \
             patch('src.core.multi_account_feature_manager.BehavioralBiasPrevention'):
            mock_mam.return_value = AsyncMock()
            mock_mam.return_value.get_all_accounts = AsyncMock(return_value=[])
            mock_mam.return_value.get_aggregate_portfolio = AsyncMock(return_value={
                "total_value": 10000000
            })

            mock_macro_instance = Mock()
            mock_macro_instance.get_market_sentiment.return_value = {"sentiment": "bullish"}
            mock_macro.return_value = mock_macro_instance

            mock_onchain_instance = Mock()
            mock_onchain_instance.get_network_health.return_value = {"health": "good"}
            mock_onchain.return_value = mock_onchain_instance

            return MultiAccountFeatureManager()

    @pytest.mark.asyncio
    async def test_get_aggregate_analytics_success(self, manager):
        """통합 분석 성공"""
        result = await manager.get_aggregate_analytics()

        assert "portfolio_overview" in result
        assert "macro_analysis" in result
        assert "onchain_analysis" in result
        assert "generated_at" in result

    @pytest.mark.asyncio
    async def test_get_aggregate_analytics_failure(self, manager):
        """통합 분석 실패"""
        manager.multi_account_manager.get_aggregate_portfolio = AsyncMock(
            side_effect=Exception("Analysis failed")
        )

        result = await manager.get_aggregate_analytics()

        assert result is None


class TestMultiAccountFeatureManagerService:
    """서비스 메서드 테스트"""

    @pytest.fixture
    def manager(self):
        with patch('src.core.multi_account_feature_manager.get_multi_account_manager') as mock_mam, \
             patch('src.core.multi_account_feature_manager.get_system_coordinator'), \
             patch('src.core.multi_account_feature_manager.MacroEconomicAnalyzer'), \
             patch('src.core.multi_account_feature_manager.OnchainDataAnalyzer'), \
             patch('src.core.multi_account_feature_manager.ScenarioResponseSystem'), \
             patch('src.core.multi_account_feature_manager.BehavioralBiasPrevention'):
            mock_mam.return_value = AsyncMock()
            mock_mam.return_value._initialized = True
            mock_mam.return_value.get_all_accounts = AsyncMock(return_value=[])
            mock_mam.return_value.health_check = AsyncMock(return_value={
                "active_accounts": 2
            })
            return MultiAccountFeatureManager()

    @pytest.mark.asyncio
    async def test_start(self, manager):
        """서비스 시작"""
        with patch.object(manager, 'initialize', new_callable=AsyncMock):
            await manager.start()

            manager.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop(self, manager):
        """서비스 중지"""
        manager.operation_locks = {"key1": asyncio.Lock()}

        await manager.stop()

        assert len(manager.operation_locks) == 0

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, manager):
        """헬스체크 - 정상"""
        manager.portfolio_managers = {AccountID("acc1"): Mock()}
        manager.rebalancers = {AccountID("acc1"): Mock()}
        manager.risk_managers = {}
        manager.order_managers = {AccountID("acc1"): Mock()}

        result = await manager.health_check()

        assert result["status"] == "healthy"
        assert result["total_feature_instances"] == 3

    @pytest.mark.asyncio
    async def test_health_check_degraded(self, manager):
        """헬스체크 - 저하됨"""
        manager.multi_account_manager.health_check = AsyncMock(return_value={
            "active_accounts": 0
        })

        result = await manager.health_check()

        assert result["status"] == "degraded"


class TestGetMultiAccountFeatureManager:
    """get_multi_account_feature_manager 함수 테스트"""

    def test_singleton_pattern(self):
        """싱글톤 패턴"""
        import src.core.multi_account_feature_manager as mafm
        mafm._multi_account_feature_manager = None

        with patch('src.core.multi_account_feature_manager.get_multi_account_manager'), \
             patch('src.core.multi_account_feature_manager.get_system_coordinator'), \
             patch('src.core.multi_account_feature_manager.MacroEconomicAnalyzer'), \
             patch('src.core.multi_account_feature_manager.OnchainDataAnalyzer'), \
             patch('src.core.multi_account_feature_manager.ScenarioResponseSystem'), \
             patch('src.core.multi_account_feature_manager.BehavioralBiasPrevention'):
            manager1 = get_multi_account_feature_manager()
            manager2 = get_multi_account_feature_manager()

            assert manager1 is manager2

        # 정리
        mafm._multi_account_feature_manager = None


class TestInitializeSharedAnalyzers:
    """공통 분석 도구 초기화 테스트"""

    @pytest.fixture
    def manager(self):
        with patch('src.core.multi_account_feature_manager.get_multi_account_manager') as mock_mam, \
             patch('src.core.multi_account_feature_manager.get_system_coordinator'), \
             patch('src.core.multi_account_feature_manager.MacroEconomicAnalyzer'), \
             patch('src.core.multi_account_feature_manager.OnchainDataAnalyzer'), \
             patch('src.core.multi_account_feature_manager.ScenarioResponseSystem'), \
             patch('src.core.multi_account_feature_manager.BehavioralBiasPrevention'):
            mock_mam.return_value = Mock()
            return MultiAccountFeatureManager()

    @pytest.mark.asyncio
    async def test_initialize_shared_analyzers_success(self, manager):
        """공통 분석 도구 초기화 성공"""
        await manager._initialize_shared_analyzers()
        # 예외 없이 완료

    @pytest.mark.asyncio
    async def test_initialize_shared_analyzers_exception(self, manager):
        """공통 분석 도구 초기화 예외"""
        # 내부에서 예외가 발생해도 로그만 출력
        with patch.object(manager, 'macro_analyzer', None):
            await manager._initialize_shared_analyzers()
