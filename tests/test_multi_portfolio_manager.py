"""
Multi-Portfolio Manager 테스트 모듈

멀티 계정 포트폴리오 통합 관리 테스트
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, MagicMock, AsyncMock, patch

from src.core.multi_portfolio_manager import (
    AccountPortfolioManager,
    MultiPortfolioManager,
    get_multi_portfolio_manager
)
from src.core.types import (
    AccountID, AssetSymbol, KRWAmount, Percentage,
    MarketSeason, RiskLevel, PortfolioSnapshot
)
from src.core.multi_account_manager import AccountConfig
from src.core.exceptions import TradingException, KairosException


class TestAccountPortfolioManager:
    """AccountPortfolioManager 클래스 테스트"""

    @pytest.fixture
    def mock_client(self):
        """Coinone 클라이언트 Mock"""
        client = Mock()
        client.get_balances.return_value = {
            'KRW': 5000000.0,
            'BTC': 0.05,
            'ETH': 1.0
        }
        client.get_ticker.return_value = {'last': 50000000}
        return client

    @pytest.fixture
    def mock_config(self):
        """계정 설정 Mock"""
        config = Mock(spec=AccountConfig)
        config.account_name = "test_account"
        config.risk_level = RiskLevel.MODERATE
        config.core_allocation = 0.7
        config.satellite_allocation = 0.3
        config.max_position_size = 0.25
        config.initial_capital = Decimal('10000000')
        config.dry_run = True
        return config

    @pytest.fixture
    def manager(self, mock_client, mock_config):
        """AccountPortfolioManager 인스턴스"""
        return AccountPortfolioManager(
            account_id=AccountID("test_acc_1"),
            config=mock_config,
            client=mock_client
        )

    def test_init(self, manager):
        """초기화 테스트"""
        assert manager.account_id == AccountID("test_acc_1")
        assert manager.last_rebalance is None
        assert manager.performance_metrics == {}

    @pytest.mark.asyncio
    async def test_calculate_target_weights_conservative(self, mock_client, mock_config):
        """보수적 리스크 레벨 목표 비중 계산"""
        mock_config.risk_level = RiskLevel.CONSERVATIVE
        manager = AccountPortfolioManager(
            account_id=AccountID("test"),
            config=mock_config,
            client=mock_client
        )

        weights = await manager.calculate_target_weights(MarketSeason.NEUTRAL)

        # 보수적: 현금 70%, 암호화폐 30%
        assert AssetSymbol('KRW') in weights
        assert weights[AssetSymbol('KRW')] >= 0.5  # 현금 비중이 높아야 함

    @pytest.mark.asyncio
    async def test_calculate_target_weights_aggressive(self, mock_client, mock_config):
        """공격적 리스크 레벨 목표 비중 계산"""
        mock_config.risk_level = RiskLevel.AGGRESSIVE
        manager = AccountPortfolioManager(
            account_id=AccountID("test"),
            config=mock_config,
            client=mock_client
        )

        weights = await manager.calculate_target_weights(MarketSeason.NEUTRAL)

        # 공격적: 암호화폐 70%, 현금 30%
        assert AssetSymbol('KRW') in weights
        assert weights[AssetSymbol('KRW')] <= 0.5  # 현금 비중이 낮아야 함

    @pytest.mark.asyncio
    async def test_calculate_target_weights_risk_on(self, mock_client, mock_config):
        """RISK_ON 시장 시즌 목표 비중 계산"""
        mock_config.risk_level = RiskLevel.MODERATE
        manager = AccountPortfolioManager(
            account_id=AccountID("test"),
            config=mock_config,
            client=mock_client
        )

        weights_neutral = await manager.calculate_target_weights(MarketSeason.NEUTRAL)
        weights_risk_on = await manager.calculate_target_weights(MarketSeason.RISK_ON)

        # RISK_ON에서는 암호화폐 비중이 더 높아야 함
        crypto_neutral = sum(v for k, v in weights_neutral.items() if k != AssetSymbol('KRW'))
        crypto_risk_on = sum(v for k, v in weights_risk_on.items() if k != AssetSymbol('KRW'))

        assert crypto_risk_on >= crypto_neutral

    @pytest.mark.asyncio
    async def test_calculate_target_weights_risk_off(self, mock_client, mock_config):
        """RISK_OFF 시장 시즌 목표 비중 계산"""
        mock_config.risk_level = RiskLevel.MODERATE
        manager = AccountPortfolioManager(
            account_id=AccountID("test"),
            config=mock_config,
            client=mock_client
        )

        weights_neutral = await manager.calculate_target_weights(MarketSeason.NEUTRAL)
        weights_risk_off = await manager.calculate_target_weights(MarketSeason.RISK_OFF)

        # RISK_OFF에서는 현금 비중이 더 높아야 함
        cash_neutral = weights_neutral.get(AssetSymbol('KRW'), Percentage(0))
        cash_risk_off = weights_risk_off.get(AssetSymbol('KRW'), Percentage(0))

        assert cash_risk_off >= cash_neutral

    @pytest.mark.asyncio
    async def test_calculate_target_weights_max_position_limit(self, mock_client, mock_config):
        """최대 포지션 크기 제한 테스트"""
        mock_config.risk_level = RiskLevel.AGGRESSIVE
        mock_config.max_position_size = 0.20  # 20% 제한
        mock_config.core_allocation = 0.9
        mock_config.satellite_allocation = 0.1

        manager = AccountPortfolioManager(
            account_id=AccountID("test"),
            config=mock_config,
            client=mock_client
        )

        weights = await manager.calculate_target_weights(MarketSeason.RISK_ON)

        # 모든 암호화폐 비중이 max_position_size 이하여야 함
        for asset, weight in weights.items():
            if asset != AssetSymbol('KRW'):
                assert weight <= 0.20

    @pytest.mark.asyncio
    async def test_get_current_portfolio(self, manager, mock_client):
        """현재 포트폴리오 조회 테스트"""
        mock_client.get_ticker.side_effect = lambda currency: {
            'last': 50000000 if currency == 'BTC' else 3000000
        }

        portfolio = await manager.get_current_portfolio()

        assert 'timestamp' in portfolio
        assert 'total_value_krw' in portfolio
        assert 'assets' in portfolio
        assert 'weights' in portfolio

    @pytest.mark.asyncio
    async def test_get_current_portfolio_calculates_weights(self, manager, mock_client):
        """포트폴리오 비중 계산 테스트"""
        mock_client.get_balances.return_value = {
            'KRW': 5000000.0,
            'BTC': 0.1  # 500만원 가치
        }
        mock_client.get_ticker.return_value = {'last': 50000000}

        portfolio = await manager.get_current_portfolio()

        # 총 가치: KRW 500만 + BTC 500만 = 1000만
        weights = portfolio['weights']

        # 비중 합은 1이어야 함
        total_weight = sum(weights.values())
        assert abs(total_weight - 1.0) < 0.01

    @pytest.mark.asyncio
    async def test_needs_rebalancing_true(self, manager, mock_client):
        """리밸런싱 필요 - 임계값 초과"""
        mock_client.get_balances.return_value = {
            'KRW': 9000000.0,  # 90%
            'BTC': 0.02  # 10%
        }
        mock_client.get_ticker.return_value = {'last': 50000000}

        target_weights = {
            AssetSymbol('KRW'): Percentage(0.5),  # 50% 목표
            AssetSymbol('BTC'): Percentage(0.5)   # 50% 목표
        }

        needs_rebalance = await manager.needs_rebalancing(target_weights, threshold=0.05)

        # 현재 KRW 90%, 목표 50% -> 40% 차이 > 5% 임계값
        assert needs_rebalance is True

    @pytest.mark.asyncio
    async def test_needs_rebalancing_false(self, manager, mock_client):
        """리밸런싱 불필요 - 임계값 이하"""
        mock_client.get_balances.return_value = {
            'KRW': 5100000.0,  # ~51%
            'BTC': 0.098  # ~49%
        }
        mock_client.get_ticker.return_value = {'last': 50000000}

        target_weights = {
            AssetSymbol('KRW'): Percentage(0.5),  # 50% 목표
            AssetSymbol('BTC'): Percentage(0.5)   # 50% 목표
        }

        needs_rebalance = await manager.needs_rebalancing(target_weights, threshold=0.05)

        # 1% 차이 < 5% 임계값
        assert needs_rebalance is False

    @pytest.mark.asyncio
    async def test_execute_rebalancing_dry_run(self, manager, mock_client, mock_config):
        """드라이런 모드 리밸런싱"""
        mock_config.dry_run = True

        target_weights = {
            AssetSymbol('KRW'): Percentage(0.5),
            AssetSymbol('BTC'): Percentage(0.3),
            AssetSymbol('ETH'): Percentage(0.2)
        }

        orders = await manager.execute_rebalancing(target_weights)

        # 드라이런에서는 주문이 없어야 함
        assert orders == []

    @pytest.mark.asyncio
    async def test_execute_rebalancing_dry_run_no_timestamp(self, manager, mock_client, mock_config):
        """드라이런 모드에서는 타임스탬프 업데이트 없음"""
        mock_config.dry_run = True

        target_weights = {AssetSymbol('KRW'): Percentage(1.0)}

        await manager.execute_rebalancing(target_weights)

        # 드라이런에서는 타임스탬프 업데이트 없음
        assert manager.last_rebalance is None


class TestMultiPortfolioManager:
    """MultiPortfolioManager 클래스 테스트"""

    @pytest.fixture
    def manager(self):
        """MultiPortfolioManager 인스턴스"""
        return MultiPortfolioManager()

    def test_init(self, manager):
        """초기화 테스트"""
        assert manager.rebalance_threshold == 0.05
        assert manager.max_concurrent_rebalancing == 2
        assert manager.account_managers == {}

    @pytest.mark.asyncio
    async def test_get_market_season(self, manager):
        """시장 시즌 조회 테스트"""
        season = await manager.get_market_season()

        # 기본적으로 NEUTRAL 반환
        assert season == MarketSeason.NEUTRAL

    @pytest.mark.asyncio
    async def test_rebalance_account_not_found(self, manager):
        """존재하지 않는 계정 리밸런싱"""
        result = await manager.rebalance_account(AccountID("nonexistent"))

        assert result['action'] == 'failed'
        assert 'error' in result

    @pytest.mark.asyncio
    async def test_rebalance_account_skipped(self, manager):
        """리밸런싱 불필요 시 스킵"""
        # Mock 계정 관리자 설정
        mock_account_manager = AsyncMock()
        mock_account_manager.calculate_target_weights.return_value = {
            AssetSymbol('KRW'): Percentage(0.5),
            AssetSymbol('BTC'): Percentage(0.5)
        }
        mock_account_manager.needs_rebalancing.return_value = False
        mock_account_manager.config = Mock(dry_run=True)

        manager.account_managers[AccountID("test_acc")] = mock_account_manager

        result = await manager.rebalance_account(AccountID("test_acc"), force=False)

        assert result['action'] == 'skipped'
        assert '임계값' in result.get('reason', '')

    @pytest.mark.asyncio
    async def test_rebalance_account_force(self, manager):
        """강제 리밸런싱"""
        mock_account_manager = AsyncMock()
        mock_account_manager.calculate_target_weights.return_value = {
            AssetSymbol('KRW'): Percentage(0.5),
            AssetSymbol('BTC'): Percentage(0.5)
        }
        mock_account_manager.execute_rebalancing.return_value = []
        mock_account_manager.config = Mock(dry_run=True)

        manager.account_managers[AccountID("test_acc")] = mock_account_manager

        result = await manager.rebalance_account(AccountID("test_acc"), force=True)

        # 강제 리밸런싱은 needs_rebalancing 확인 없이 실행
        assert result['action'] == 'completed'
        mock_account_manager.execute_rebalancing.assert_called_once()

    @pytest.mark.asyncio
    async def test_rebalance_all_accounts_no_active(self, manager):
        """활성 계정 없을 때 전체 리밸런싱"""
        manager.multi_account_manager = Mock()
        manager.multi_account_manager.account_status = {}

        results = await manager.rebalance_all_accounts()

        assert results == []

    @pytest.mark.asyncio
    async def test_health_check_no_accounts(self, manager):
        """계정 없을 때 헬스체크"""
        health = await manager.health_check()

        assert health['service'] == 'multi_portfolio_manager'
        assert health['total_accounts'] == 0

    @pytest.mark.asyncio
    async def test_health_check_with_accounts(self, manager):
        """계정 있을 때 헬스체크"""
        mock_account_manager = AsyncMock()
        mock_account_manager.get_current_portfolio.return_value = {
            'total_value_krw': KRWAmount(Decimal('10000000')),
            'assets': {},
            'weights': {}
        }

        manager.account_managers[AccountID("test_acc")] = mock_account_manager

        health = await manager.health_check()

        assert health['total_accounts'] == 1
        assert health['healthy_accounts'] == 1
        assert health['status'] == 'healthy'

    @pytest.mark.asyncio
    async def test_health_check_degraded(self, manager):
        """헬스체크 - degraded 상태"""
        mock_account_manager = AsyncMock()
        mock_account_manager.get_current_portfolio.side_effect = Exception("Connection failed")

        manager.account_managers[AccountID("test_acc")] = mock_account_manager

        health = await manager.health_check()

        assert health['total_accounts'] == 1
        assert health['healthy_accounts'] == 0
        assert health['status'] == 'degraded'

    @pytest.mark.asyncio
    async def test_start_stop(self, manager):
        """서비스 시작/중지 테스트"""
        with patch.object(manager, 'initialize', new_callable=AsyncMock):
            await manager.start()

        # 중지 테스트
        manager.account_managers[AccountID("test")] = Mock()
        await manager.stop()

        assert manager.account_managers == {}

    @pytest.mark.asyncio
    async def test_get_aggregate_performance_empty(self, manager):
        """계정 없을 때 통합 성과"""
        performance = await manager.get_aggregate_performance()

        assert performance.get('active_accounts', 0) == 0
        assert performance.get('overall_return', 0) == 0

    @pytest.mark.asyncio
    async def test_get_aggregate_performance_with_accounts(self, manager):
        """계정 있을 때 통합 성과"""
        mock_account_manager = AsyncMock()
        mock_config = Mock()
        mock_config.account_name = "Test Account"
        mock_config.initial_capital = Decimal('10000000')
        mock_config.risk_level = RiskLevel.MODERATE

        mock_account_manager.config = mock_config
        mock_account_manager.get_current_portfolio.return_value = {
            'total_value_krw': KRWAmount(Decimal('12000000')),  # 20% 수익
            'assets': {},
            'weights': {}
        }

        manager.account_managers[AccountID("test_acc")] = mock_account_manager

        performance = await manager.get_aggregate_performance()

        assert performance['active_accounts'] == 1
        assert performance['overall_return'] > 0  # 수익 발생


class TestGetMultiPortfolioManager:
    """get_multi_portfolio_manager 함수 테스트"""

    def test_singleton_pattern(self):
        """싱글톤 패턴 테스트"""
        # 전역 변수 리셋
        import src.core.multi_portfolio_manager as mpm
        mpm._multi_portfolio_manager = None

        manager1 = get_multi_portfolio_manager()
        manager2 = get_multi_portfolio_manager()

        assert manager1 is manager2

    def test_creates_instance(self):
        """인스턴스 생성 테스트"""
        import src.core.multi_portfolio_manager as mpm
        mpm._multi_portfolio_manager = None

        manager = get_multi_portfolio_manager()

        assert isinstance(manager, MultiPortfolioManager)


class TestAccountPortfolioManagerEdgeCases:
    """AccountPortfolioManager 엣지 케이스 테스트"""

    @pytest.fixture
    def mock_client(self):
        client = Mock()
        client.get_balances.return_value = {}
        client.get_ticker.return_value = {'last': 0}
        return client

    @pytest.fixture
    def mock_config(self):
        config = Mock(spec=AccountConfig)
        config.account_name = "test"
        config.risk_level = RiskLevel.MODERATE
        config.core_allocation = 0.7
        config.satellite_allocation = 0.3
        config.max_position_size = 0.25
        config.initial_capital = Decimal('10000000')
        config.dry_run = True
        return config

    @pytest.mark.asyncio
    async def test_empty_portfolio(self, mock_client, mock_config):
        """빈 포트폴리오 조회"""
        mock_client.get_balances.return_value = {}

        manager = AccountPortfolioManager(
            account_id=AccountID("test"),
            config=mock_config,
            client=mock_client
        )

        portfolio = await manager.get_current_portfolio()

        assert portfolio['total_value_krw'] == KRWAmount(Decimal('0'))

    @pytest.mark.asyncio
    async def test_zero_balance_excluded(self, mock_client, mock_config):
        """잔고 0인 자산 제외"""
        mock_client.get_balances.return_value = {
            'KRW': 1000000.0,
            'BTC': 0.0,  # 잔고 0
            'ETH': 0.5
        }
        mock_client.get_ticker.return_value = {'last': 3000000}

        manager = AccountPortfolioManager(
            account_id=AccountID("test"),
            config=mock_config,
            client=mock_client
        )

        portfolio = await manager.get_current_portfolio()

        # BTC는 잔고 0이므로 제외되어야 함
        assert AssetSymbol('BTC') not in portfolio['assets']

    @pytest.mark.asyncio
    async def test_needs_rebalancing_error_handling(self, mock_client, mock_config):
        """리밸런싱 필요 확인 중 에러 처리"""
        mock_client.get_balances.side_effect = Exception("API Error")

        manager = AccountPortfolioManager(
            account_id=AccountID("test"),
            config=mock_config,
            client=mock_client
        )

        target_weights = {AssetSymbol('KRW'): Percentage(0.5)}

        # 에러 시 False 반환
        result = await manager.needs_rebalancing(target_weights)
        assert result is False

    @pytest.mark.asyncio
    async def test_calculate_target_weights_all_risk_levels(self, mock_client, mock_config):
        """모든 리스크 레벨 테스트"""
        for risk_level in [RiskLevel.CONSERVATIVE, RiskLevel.MODERATE, RiskLevel.AGGRESSIVE]:
            mock_config.risk_level = risk_level
            manager = AccountPortfolioManager(
                account_id=AccountID("test"),
                config=mock_config,
                client=mock_client
            )

            weights = await manager.calculate_target_weights(MarketSeason.NEUTRAL)

            # 비중 합은 1이어야 함
            total = sum(weights.values())
            assert abs(total - 1.0) < 0.01, f"Risk level {risk_level}: total weight = {total}"

    @pytest.mark.asyncio
    async def test_calculate_target_weights_all_seasons(self, mock_client, mock_config):
        """모든 시장 시즌 테스트"""
        for season in [MarketSeason.RISK_ON, MarketSeason.RISK_OFF, MarketSeason.NEUTRAL]:
            manager = AccountPortfolioManager(
                account_id=AccountID("test"),
                config=mock_config,
                client=mock_client
            )

            weights = await manager.calculate_target_weights(season)

            # 비중 합은 1이어야 함
            total = sum(weights.values())
            assert abs(total - 1.0) < 0.01, f"Season {season}: total weight = {total}"
