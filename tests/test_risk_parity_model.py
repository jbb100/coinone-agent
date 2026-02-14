"""
Risk Parity Model Tests

리스크 패리티 모델 테스트
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.core.risk_parity_model import (
    RiskParityModel,
    RiskMetrics,
    RiskContribution,
    RiskParityAllocation,
    calculate_diversification_ratio,
    calculate_maximum_diversification_weights
)


@pytest.mark.trading
class TestRiskMetrics:
    """RiskMetrics 데이터클래스 테스트"""

    def test_risk_metrics_creation(self):
        """리스크 지표 생성"""
        metrics = RiskMetrics(
            volatility=0.20,
            var_95=-0.05,
            expected_shortfall=-0.08,
            max_drawdown=-0.15,
            sharpe_ratio=1.5,
            sortino_ratio=2.0,
            calmar_ratio=1.2
        )

        assert metrics.volatility == 0.20
        assert metrics.var_95 == -0.05
        assert metrics.sharpe_ratio == 1.5
        assert metrics.sortino_ratio == 2.0

    def test_risk_metrics_negative_values(self):
        """음수 값 처리"""
        metrics = RiskMetrics(
            volatility=0.25,
            var_95=-0.10,
            expected_shortfall=-0.15,
            max_drawdown=-0.30,
            sharpe_ratio=-0.5,
            sortino_ratio=-0.3,
            calmar_ratio=0.0
        )

        assert metrics.max_drawdown == -0.30
        assert metrics.sharpe_ratio == -0.5


@pytest.mark.trading
class TestRiskContribution:
    """RiskContribution 데이터클래스 테스트"""

    def test_risk_contribution_creation(self):
        """리스크 기여도 생성"""
        contribution = RiskContribution(
            asset="BTC",
            weight=0.30,
            volatility=0.50,
            risk_contribution=33.3,
            marginal_risk=0.15,
            component_risk=0.045
        )

        assert contribution.asset == "BTC"
        assert contribution.weight == 0.30
        assert contribution.volatility == 0.50
        assert contribution.risk_contribution == 33.3


@pytest.mark.trading
class TestRiskParityAllocation:
    """RiskParityAllocation 테스트"""

    def test_allocation_creation(self):
        """배분 결과 생성"""
        contributions = [
            RiskContribution(
                asset="BTC",
                weight=0.50,
                volatility=0.50,
                risk_contribution=50.0,
                marginal_risk=0.1,
                component_risk=0.05
            ),
            RiskContribution(
                asset="ETH",
                weight=0.50,
                volatility=0.60,
                risk_contribution=50.0,
                marginal_risk=0.12,
                component_risk=0.06
            )
        ]

        allocation = RiskParityAllocation(
            weights={"BTC": 0.50, "ETH": 0.50},
            risk_contributions=contributions,
            portfolio_volatility=0.40,
            total_risk=100.0,
            optimization_success=True,
            convergence_error=0.001,
            created_at=datetime.now()
        )

        assert allocation.weights["BTC"] == 0.50
        assert allocation.portfolio_volatility == 0.40
        assert allocation.optimization_success is True


@pytest.fixture
def sample_price_data():
    """샘플 가격 데이터"""
    np.random.seed(42)
    dates = pd.date_range(start='2023-01-01', periods=300, freq='D')

    btc_prices = 50000000 * np.exp(np.cumsum(np.random.normal(0.001, 0.03, 300)))
    eth_prices = 2500000 * np.exp(np.cumsum(np.random.normal(0.0012, 0.035, 300)))
    xrp_prices = 600 * np.exp(np.cumsum(np.random.normal(0.0008, 0.04, 300)))

    return {
        'BTC': pd.DataFrame({'Close': btc_prices}, index=dates),
        'ETH': pd.DataFrame({'Close': eth_prices}, index=dates),
        'XRP': pd.DataFrame({'Close': xrp_prices}, index=dates)
    }


@pytest.fixture
def risk_parity_model():
    """RiskParityModel fixture"""
    return RiskParityModel(lookback_period=252)


@pytest.mark.trading
class TestRiskParityModelInit:
    """RiskParityModel 초기화 테스트"""

    def test_default_initialization(self):
        """기본 초기화"""
        model = RiskParityModel()

        assert model.lookback_period == 252
        assert model.min_weight == 0.05
        assert model.max_weight == 0.50
        assert model.max_iterations == 1000

    def test_custom_initialization(self):
        """커스텀 초기화"""
        model = RiskParityModel(lookback_period=126)

        assert model.lookback_period == 126


@pytest.mark.trading
class TestRiskParityWeightCalculation:
    """리스크 패리티 가중치 계산 테스트"""

    def test_calculate_risk_parity_weights(self, risk_parity_model, sample_price_data):
        """기본 가중치 계산"""
        target_assets = ['BTC', 'ETH', 'XRP']

        allocation = risk_parity_model.calculate_risk_parity_weights(
            sample_price_data, target_assets
        )

        assert isinstance(allocation, RiskParityAllocation)
        assert len(allocation.weights) == 3
        assert sum(allocation.weights.values()) == pytest.approx(1.0, abs=0.01)

    def test_weights_sum_to_one(self, risk_parity_model, sample_price_data):
        """가중치 합계 = 1"""
        target_assets = ['BTC', 'ETH']

        allocation = risk_parity_model.calculate_risk_parity_weights(
            sample_price_data, target_assets
        )

        total_weight = sum(allocation.weights.values())
        assert total_weight == pytest.approx(1.0, abs=0.01)

    def test_weights_within_bounds(self, risk_parity_model, sample_price_data):
        """가중치 경계 확인"""
        target_assets = ['BTC', 'ETH', 'XRP']

        allocation = risk_parity_model.calculate_risk_parity_weights(
            sample_price_data, target_assets
        )

        for asset, weight in allocation.weights.items():
            assert weight >= risk_parity_model.min_weight
            assert weight <= risk_parity_model.max_weight

    def test_empty_price_data(self, risk_parity_model):
        """빈 가격 데이터"""
        target_assets = ['BTC', 'ETH']

        allocation = risk_parity_model.calculate_risk_parity_weights(
            {}, target_assets
        )

        # 동일 가중치 폴백
        assert allocation.optimization_success is False
        assert len(allocation.weights) == 2


@pytest.mark.trading
class TestReturnsDataPreparation:
    """수익률 데이터 준비 테스트"""

    def test_prepare_returns_data(self, risk_parity_model, sample_price_data):
        """수익률 데이터 준비"""
        assets = ['BTC', 'ETH']

        returns_df = risk_parity_model._prepare_returns_data(sample_price_data, assets)

        assert isinstance(returns_df, pd.DataFrame)
        assert len(returns_df.columns) == 2
        assert 'BTC' in returns_df.columns
        assert 'ETH' in returns_df.columns

    def test_prepare_returns_insufficient_data(self, risk_parity_model):
        """데이터 부족"""
        # 50일 미만 데이터
        dates = pd.date_range(start='2024-01-01', periods=30)
        price_data = {
            'BTC': pd.DataFrame({'Close': np.random.uniform(40000000, 60000000, 30)}, index=dates)
        }

        returns_df = risk_parity_model._prepare_returns_data(price_data, ['BTC'])

        assert returns_df.empty


@pytest.mark.trading
class TestRiskParityOptimization:
    """리스크 패리티 최적화 테스트"""

    def test_optimize_risk_parity(self, risk_parity_model):
        """최적화 실행"""
        # 간단한 공분산 행렬
        cov_matrix = np.array([
            [0.04, 0.02],  # 20% 변동성, 상관계수 0.5
            [0.02, 0.06]   # 24.5% 변동성
        ])

        initial_weights = np.array([0.5, 0.5])

        optimal_weights = risk_parity_model._optimize_risk_parity(cov_matrix, initial_weights)

        assert optimal_weights is not None
        assert len(optimal_weights) == 2
        assert np.sum(optimal_weights) == pytest.approx(1.0, abs=0.01)

    def test_risk_parity_objective(self, risk_parity_model):
        """목적 함수 테스트"""
        cov_matrix = np.array([
            [0.04, 0.01],
            [0.01, 0.09]
        ])

        # 동일 가중치
        equal_weights = np.array([0.5, 0.5])
        objective_value = risk_parity_model._risk_parity_objective(equal_weights, cov_matrix)

        assert objective_value >= 0  # 항상 양수


@pytest.mark.trading
class TestRiskContributions:
    """리스크 기여도 계산 테스트"""

    def test_calculate_risk_contributions(self, risk_parity_model):
        """리스크 기여도 계산"""
        weights = {'BTC': 0.4, 'ETH': 0.6}
        cov_matrix = np.array([
            [0.04, 0.02],
            [0.02, 0.06]
        ])
        assets = ['BTC', 'ETH']

        contributions = risk_parity_model._calculate_risk_contributions(weights, cov_matrix, assets)

        assert len(contributions) == 2
        assert all(isinstance(c, RiskContribution) for c in contributions)

    def test_risk_contributions_total(self, risk_parity_model):
        """리스크 기여도 합계"""
        weights = {'BTC': 0.5, 'ETH': 0.5}
        cov_matrix = np.array([
            [0.04, 0.01],
            [0.01, 0.04]
        ])
        assets = ['BTC', 'ETH']

        contributions = risk_parity_model._calculate_risk_contributions(weights, cov_matrix, assets)

        total_contribution = sum(c.risk_contribution for c in contributions)
        assert total_contribution == pytest.approx(100.0, abs=5.0)


@pytest.mark.trading
class TestPortfolioRiskMetrics:
    """포트폴리오 리스크 지표 테스트"""

    def test_calculate_portfolio_risk_metrics(self, risk_parity_model):
        """포트폴리오 리스크 지표 계산"""
        np.random.seed(42)
        dates = pd.date_range(start='2024-01-01', periods=100)
        returns_data = pd.DataFrame({
            'BTC': np.random.normal(0.001, 0.03, 100),
            'ETH': np.random.normal(0.0012, 0.035, 100)
        }, index=dates)

        weights = {'BTC': 0.5, 'ETH': 0.5}

        metrics = risk_parity_model.calculate_portfolio_risk_metrics(returns_data, weights)

        assert isinstance(metrics, RiskMetrics)
        assert metrics.volatility > 0
        assert metrics.var_95 < 0  # VaR는 음수

    def test_empty_returns_data(self, risk_parity_model):
        """빈 수익률 데이터"""
        returns_data = pd.DataFrame()
        weights = {'BTC': 0.5, 'ETH': 0.5}

        metrics = risk_parity_model.calculate_portfolio_risk_metrics(returns_data, weights)

        # 기본 지표 반환
        assert metrics.volatility == 0.0


@pytest.mark.trading
class TestEqualWeightFallback:
    """동일 가중치 폴백 테스트"""

    def test_equal_weight_fallback(self, risk_parity_model):
        """동일 가중치 폴백"""
        assets = ['BTC', 'ETH', 'XRP']

        allocation = risk_parity_model._get_equal_weight_fallback(assets)

        assert len(allocation.weights) == 3
        for asset in assets:
            assert allocation.weights[asset] == pytest.approx(1/3, abs=0.01)
        assert allocation.optimization_success is False


@pytest.mark.trading
class TestRebalancingSignals:
    """리밸런싱 신호 테스트"""

    def test_generate_rebalancing_signals_needed(self, risk_parity_model):
        """리밸런싱 필요"""
        current_weights = {'BTC': 0.40, 'ETH': 0.60}
        target_weights = {'BTC': 0.50, 'ETH': 0.50}  # 10% 편차

        signals = risk_parity_model.generate_rebalancing_signals(
            current_weights, target_weights, threshold=0.05
        )

        assert signals["rebalance_needed"] is True
        assert "BTC" in signals["suggested_trades"]

    def test_generate_rebalancing_signals_not_needed(self, risk_parity_model):
        """리밸런싱 불필요"""
        current_weights = {'BTC': 0.49, 'ETH': 0.51}
        target_weights = {'BTC': 0.50, 'ETH': 0.50}  # 1% 편차

        signals = risk_parity_model.generate_rebalancing_signals(
            current_weights, target_weights, threshold=0.05
        )

        assert signals["rebalance_needed"] is False

    def test_urgency_levels(self, risk_parity_model):
        """긴급도 수준"""
        # 높은 편차
        current_weights = {'BTC': 0.30, 'ETH': 0.70}
        target_weights = {'BTC': 0.50, 'ETH': 0.50}  # 20% 편차

        signals = risk_parity_model.generate_rebalancing_signals(
            current_weights, target_weights, threshold=0.05
        )

        assert signals["urgency"] == "high"

    def test_turnover_calculation(self, risk_parity_model):
        """회전율 계산"""
        current_weights = {'BTC': 0.40, 'ETH': 0.60}
        target_weights = {'BTC': 0.50, 'ETH': 0.50}

        signals = risk_parity_model.generate_rebalancing_signals(
            current_weights, target_weights, threshold=0.05
        )

        # 총 변화: |0.40-0.50| + |0.60-0.50| = 0.20, turnover = 0.10
        assert signals["total_turnover"] == pytest.approx(0.10, abs=0.01)


@pytest.mark.trading
class TestPortfolioComparison:
    """포트폴리오 비교 테스트"""

    def test_compare_with_market_cap_weights(self, risk_parity_model):
        """시가총액 가중과 비교"""
        np.random.seed(42)
        dates = pd.date_range(start='2024-01-01', periods=100)
        returns_data = pd.DataFrame({
            'BTC': np.random.normal(0.001, 0.03, 100),
            'ETH': np.random.normal(0.0012, 0.035, 100)
        }, index=dates)

        rp_weights = {'BTC': 0.55, 'ETH': 0.45}
        mc_weights = {'BTC': 0.70, 'ETH': 0.30}

        comparison = risk_parity_model.compare_with_market_cap_weights(
            rp_weights, mc_weights, returns_data
        )

        assert "risk_parity" in comparison
        assert "market_cap" in comparison
        assert "improvement" in comparison


@pytest.mark.trading
class TestRiskAdjustedReturns:
    """리스크 조정 수익률 테스트"""

    def test_calculate_risk_adjusted_returns(self, risk_parity_model):
        """리스크 조정 수익률 계산"""
        np.random.seed(42)
        dates = pd.date_range(start='2024-01-01', periods=100)
        returns_data = pd.DataFrame({
            'BTC': np.random.normal(0.001, 0.03, 100),
            'ETH': np.random.normal(0.0012, 0.035, 100)
        }, index=dates)

        weights = {'BTC': 0.5, 'ETH': 0.5}

        metrics = risk_parity_model.calculate_risk_adjusted_returns(returns_data, weights)

        assert "annual_return" in metrics
        assert "annual_volatility" in metrics
        assert "sharpe_ratio" in metrics

    def test_with_benchmark(self, risk_parity_model):
        """벤치마크 비교"""
        np.random.seed(42)
        dates = pd.date_range(start='2024-01-01', periods=100)
        returns_data = pd.DataFrame({
            'BTC': np.random.normal(0.001, 0.03, 100),
            'ETH': np.random.normal(0.0012, 0.035, 100)
        }, index=dates)

        benchmark_returns = pd.Series(np.random.normal(0.0008, 0.025, 100), index=dates)
        weights = {'BTC': 0.5, 'ETH': 0.5}

        metrics = risk_parity_model.calculate_risk_adjusted_returns(
            returns_data, weights, benchmark_returns
        )

        assert "annual_excess_return" in metrics
        assert "tracking_error" in metrics
        assert "information_ratio" in metrics


@pytest.mark.trading
class TestUtilityFunctions:
    """유틸리티 함수 테스트"""

    def test_calculate_diversification_ratio(self):
        """다각화 비율 계산"""
        weights = np.array([0.5, 0.5])
        cov_matrix = np.array([
            [0.04, 0.01],  # 낮은 상관관계
            [0.01, 0.04]
        ])

        ratio = calculate_diversification_ratio(weights, cov_matrix)

        # 다각화 비율 > 1 (분산 효과)
        assert ratio > 1.0

    def test_diversification_ratio_high_correlation(self):
        """높은 상관관계의 다각화 비율"""
        weights = np.array([0.5, 0.5])
        cov_matrix = np.array([
            [0.04, 0.038],  # 높은 상관관계 (0.95)
            [0.038, 0.04]
        ])

        ratio = calculate_diversification_ratio(weights, cov_matrix)

        # 높은 상관관계: 다각화 효과 낮음
        assert ratio < 1.2

    def test_calculate_maximum_diversification_weights(self):
        """최대 다각화 가중치"""
        cov_matrix = np.array([
            [0.04, 0.01],  # 20% 변동성
            [0.01, 0.09]   # 30% 변동성
        ])

        weights = calculate_maximum_diversification_weights(cov_matrix)

        assert weights is not None
        assert len(weights) == 2
        # 낮은 변동성 자산에 더 높은 가중치
        assert weights[0] > weights[1]


@pytest.mark.trading
class TestEdgeCases:
    """엣지 케이스 테스트"""

    def test_single_asset(self, risk_parity_model):
        """단일 자산"""
        np.random.seed(42)
        dates = pd.date_range(start='2023-01-01', periods=300)
        price_data = {
            'BTC': pd.DataFrame({
                'Close': 50000000 * np.exp(np.cumsum(np.random.normal(0.001, 0.03, 300)))
            }, index=dates)
        }

        allocation = risk_parity_model.calculate_risk_parity_weights(price_data, ['BTC'])

        assert allocation.weights['BTC'] == 1.0

    def test_zero_volatility_asset(self, risk_parity_model):
        """변동성 0 자산"""
        # 이 케이스는 실제로 발생하기 어려움 (상수 가격)
        # 폴백으로 동일 가중치 사용
        dates = pd.date_range(start='2023-01-01', periods=300)
        price_data = {
            'STABLE': pd.DataFrame({
                'Close': [1000000] * 300  # 변동 없음
            }, index=dates),
            'BTC': pd.DataFrame({
                'Close': 50000000 * np.exp(np.cumsum(np.random.normal(0.001, 0.03, 300)))
            }, index=dates)
        }

        # 변동성 0인 자산은 제외되거나 폴백 사용
        allocation = risk_parity_model.calculate_risk_parity_weights(
            price_data, ['STABLE', 'BTC']
        )

        assert allocation is not None

    def test_missing_asset_in_price_data(self, risk_parity_model, sample_price_data):
        """가격 데이터에 없는 자산"""
        target_assets = ['BTC', 'ETH', 'MISSING']

        allocation = risk_parity_model.calculate_risk_parity_weights(
            sample_price_data, target_assets
        )

        # MISSING 자산은 제외됨
        assert 'BTC' in allocation.weights
        assert 'ETH' in allocation.weights


@pytest.mark.trading
class TestRiskParityConvergence:
    """수렴 테스트"""

    def test_convergence_with_similar_volatilities(self, risk_parity_model):
        """유사한 변동성의 수렴"""
        np.random.seed(42)
        dates = pd.date_range(start='2023-01-01', periods=300)

        # 유사한 변동성 (3%)
        price_data = {
            'A': pd.DataFrame({
                'Close': 1000 * np.exp(np.cumsum(np.random.normal(0.001, 0.03, 300)))
            }, index=dates),
            'B': pd.DataFrame({
                'Close': 1000 * np.exp(np.cumsum(np.random.normal(0.001, 0.031, 300)))
            }, index=dates)
        }

        allocation = risk_parity_model.calculate_risk_parity_weights(price_data, ['A', 'B'])

        # 유사한 변동성이면 비슷한 가중치
        assert abs(allocation.weights['A'] - allocation.weights['B']) < 0.1

    def test_convergence_with_different_volatilities(self, risk_parity_model):
        """다른 변동성의 수렴"""
        np.random.seed(42)
        dates = pd.date_range(start='2023-01-01', periods=300)

        # 다른 변동성 (2% vs 6%)
        price_data = {
            'LOW_VOL': pd.DataFrame({
                'Close': 1000 * np.exp(np.cumsum(np.random.normal(0.001, 0.02, 300)))
            }, index=dates),
            'HIGH_VOL': pd.DataFrame({
                'Close': 1000 * np.exp(np.cumsum(np.random.normal(0.001, 0.06, 300)))
            }, index=dates)
        }

        allocation = risk_parity_model.calculate_risk_parity_weights(
            price_data, ['LOW_VOL', 'HIGH_VOL']
        )

        # 가중치가 경계값(0.05~0.50)에 제한되므로 둘 다 비슷할 수 있음
        # 대신 최적화가 성공했는지 확인
        assert allocation.optimization_success is True
        # 두 가중치 합이 1인지 확인
        assert sum(allocation.weights.values()) == pytest.approx(1.0, abs=0.01)
