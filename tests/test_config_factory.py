"""
Config Factory 테스트 모듈

설정 팩토리 함수 테스트
"""

import pytest

from src.utils.config_factory import (
    get_default_rebalancer_config,
    get_default_portfolio_config,
    get_default_risk_config,
    get_default_execution_config
)
from src.utils.constants import (
    REBALANCE_THRESHOLD, MAX_SLIPPAGE, ORDER_TIMEOUT_SECONDS,
    SAFETY_MARGIN, MIN_TRADE_AMOUNT_KRW, MAX_RETRIES,
    MAX_POSITION_SIZE, MAX_DAILY_LOSS_THRESHOLD,
    CORE_WEIGHT, SATELLITE_WEIGHT,
    SUPPORTED_CRYPTOCURRENCIES, CORE_ASSETS, SATELLITE_ASSETS
)


class TestGetDefaultRebalancerConfig:
    """get_default_rebalancer_config 테스트"""

    def test_returns_dict(self):
        """딕셔너리 반환 확인"""
        config = get_default_rebalancer_config()
        assert isinstance(config, dict)

    def test_has_strategy_section(self):
        """strategy 섹션 존재 확인"""
        config = get_default_rebalancer_config()
        assert 'strategy' in config
        assert 'rebalancing' in config['strategy']
        assert 'portfolio' in config['strategy']

    def test_has_risk_management_section(self):
        """risk_management 섹션 존재 확인"""
        config = get_default_rebalancer_config()
        assert 'risk_management' in config
        assert 'max_position_size' in config['risk_management']

    def test_has_execution_section(self):
        """execution 섹션 존재 확인"""
        config = get_default_rebalancer_config()
        assert 'execution' in config
        assert 'order_timeout' in config['execution']

    def test_uses_constants_values(self):
        """constants 값 사용 확인"""
        config = get_default_rebalancer_config()

        assert config['risk_management']['max_position_size'] == MAX_POSITION_SIZE
        assert config['risk_management']['max_slippage'] == MAX_SLIPPAGE
        assert config['risk_management']['max_daily_loss'] == MAX_DAILY_LOSS_THRESHOLD

        assert config['execution']['order_timeout'] == ORDER_TIMEOUT_SECONDS
        assert config['execution']['retry_attempts'] == MAX_RETRIES
        assert config['execution']['safety_margin'] == SAFETY_MARGIN

    def test_rebalancing_threshold_converted(self):
        """리밸런싱 임계값 변환 확인 (소수 -> 퍼센트)"""
        config = get_default_rebalancer_config()

        # REBALANCE_THRESHOLD가 0.01이면 1.0으로 변환
        assert config['strategy']['rebalancing']['threshold'] == REBALANCE_THRESHOLD * 100

    def test_portfolio_core_allocation(self):
        """포트폴리오 코어 배분 확인"""
        config = get_default_rebalancer_config()
        core = config['strategy']['portfolio']['core']

        assert 'BTC' in core
        assert 'ETH' in core
        assert sum(core.values()) == 100  # 총 100%


class TestGetDefaultPortfolioConfig:
    """get_default_portfolio_config 테스트"""

    def test_returns_dict(self):
        """딕셔너리 반환 확인"""
        config = get_default_portfolio_config()
        assert isinstance(config, dict)

    def test_has_strategy_section(self):
        """strategy 섹션 존재 확인"""
        config = get_default_portfolio_config()
        assert 'strategy' in config
        assert 'portfolio' in config['strategy']

    def test_has_assets_section(self):
        """assets 섹션 존재 확인"""
        config = get_default_portfolio_config()
        assert 'assets' in config
        assert 'supported' in config['assets']
        assert 'core' in config['assets']
        assert 'satellite' in config['assets']

    def test_uses_constants_values(self):
        """constants 값 사용 확인"""
        config = get_default_portfolio_config()

        assert config['strategy']['portfolio']['core_weight'] == CORE_WEIGHT
        assert config['strategy']['portfolio']['satellite_weight'] == SATELLITE_WEIGHT
        assert config['assets']['supported'] == SUPPORTED_CRYPTOCURRENCIES
        assert config['assets']['core'] == CORE_ASSETS
        assert config['assets']['satellite'] == SATELLITE_ASSETS

    def test_risk_management_values(self):
        """리스크 관리 값 확인"""
        config = get_default_portfolio_config()

        assert config['risk_management']['max_position_size'] == MAX_POSITION_SIZE
        assert config['risk_management']['stop_loss'] < 0  # 음수여야 함


class TestGetDefaultRiskConfig:
    """get_default_risk_config 테스트"""

    def test_returns_dict(self):
        """딕셔너리 반환 확인"""
        config = get_default_risk_config()
        assert isinstance(config, dict)

    def test_has_trading_limits(self):
        """trading_limits 섹션 존재 확인"""
        config = get_default_risk_config()
        assert 'trading_limits' in config
        assert 'max_single_trade' in config['trading_limits']
        assert 'max_daily_volume' in config['trading_limits']

    def test_has_loss_limits(self):
        """loss_limits 섹션 존재 확인"""
        config = get_default_risk_config()
        assert 'loss_limits' in config
        assert 'max_daily_loss' in config['loss_limits']
        assert 'max_monthly_loss' in config['loss_limits']
        assert 'drawdown_threshold' in config['loss_limits']

    def test_uses_constants_values(self):
        """constants 값 사용 확인"""
        config = get_default_risk_config()

        assert config['trading_limits']['max_position_size'] == MAX_POSITION_SIZE
        assert config['loss_limits']['max_daily_loss'] == MAX_DAILY_LOSS_THRESHOLD

    def test_loss_limits_are_reasonable(self):
        """손실 한도가 합리적인 범위인지 확인"""
        config = get_default_risk_config()

        assert 0 < config['loss_limits']['max_daily_loss'] <= 0.10
        assert 0 < config['loss_limits']['max_monthly_loss'] <= 0.30
        assert 0 < config['loss_limits']['drawdown_threshold'] <= 0.50


class TestGetDefaultExecutionConfig:
    """get_default_execution_config 테스트"""

    def test_returns_dict(self):
        """딕셔너리 반환 확인"""
        config = get_default_execution_config()
        assert isinstance(config, dict)

    def test_has_all_keys(self):
        """모든 키 존재 확인"""
        config = get_default_execution_config()

        expected_keys = ['order_timeout', 'retry_attempts', 'safety_margin',
                        'max_slippage', 'min_trade_amount']
        for key in expected_keys:
            assert key in config, f"Missing key: {key}"

    def test_uses_constants_values(self):
        """constants 값 사용 확인"""
        config = get_default_execution_config()

        assert config['order_timeout'] == ORDER_TIMEOUT_SECONDS
        assert config['retry_attempts'] == MAX_RETRIES
        assert config['safety_margin'] == SAFETY_MARGIN
        assert config['max_slippage'] == MAX_SLIPPAGE
        assert config['min_trade_amount'] == MIN_TRADE_AMOUNT_KRW

    def test_timeout_positive(self):
        """타임아웃 양수 확인"""
        config = get_default_execution_config()
        assert config['order_timeout'] > 0

    def test_retry_attempts_reasonable(self):
        """재시도 횟수가 합리적인지 확인"""
        config = get_default_execution_config()
        assert 1 <= config['retry_attempts'] <= 10


class TestConfigConsistency:
    """설정 간 일관성 테스트"""

    def test_max_position_size_consistent(self):
        """MAX_POSITION_SIZE가 모든 설정에서 일관되게 사용되는지"""
        rebalancer_config = get_default_rebalancer_config()
        portfolio_config = get_default_portfolio_config()
        risk_config = get_default_risk_config()

        assert rebalancer_config['risk_management']['max_position_size'] == MAX_POSITION_SIZE
        assert portfolio_config['risk_management']['max_position_size'] == MAX_POSITION_SIZE
        assert risk_config['trading_limits']['max_position_size'] == MAX_POSITION_SIZE

    def test_min_trade_amount_consistent(self):
        """MIN_TRADE_AMOUNT_KRW가 일관되게 사용되는지"""
        rebalancer_config = get_default_rebalancer_config()
        portfolio_config = get_default_portfolio_config()
        execution_config = get_default_execution_config()

        assert rebalancer_config['strategy']['rebalancing']['min_trade_amount'] == MIN_TRADE_AMOUNT_KRW
        assert portfolio_config['strategy']['rebalancing']['min_trade_amount'] == MIN_TRADE_AMOUNT_KRW
        assert execution_config['min_trade_amount'] == MIN_TRADE_AMOUNT_KRW

    def test_configs_are_independent(self):
        """각 설정이 독립적인 딕셔너리인지"""
        config1 = get_default_rebalancer_config()
        config2 = get_default_rebalancer_config()

        # 하나를 수정해도 다른 것에 영향 없음
        config1['strategy']['rebalancing']['threshold'] = 999

        config3 = get_default_rebalancer_config()
        assert config3['strategy']['rebalancing']['threshold'] != 999
