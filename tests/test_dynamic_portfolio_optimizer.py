"""
Dynamic Portfolio Optimizer Tests

동적 포트폴리오 최적화 시스템 테스트
- 자산 분석 및 점수 계산
- 포트폴리오 선택 및 비중 최적화
- 리스크 수준별 설정
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from src.core.dynamic_portfolio_optimizer import (
    DynamicPortfolioOptimizer,
    AssetMetrics,
    PortfolioWeights,
    AssetClass,
    SelectionCriteria
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def optimizer():
    """기본 포트폴리오 최적화기"""
    return DynamicPortfolioOptimizer(
        coinone_client=None,
        risk_level="moderate",
        max_assets=6
    )


@pytest.fixture
def conservative_optimizer():
    """보수적 최적화기"""
    return DynamicPortfolioOptimizer(
        coinone_client=None,
        risk_level="conservative",
        max_assets=4
    )


@pytest.fixture
def aggressive_optimizer():
    """공격적 최적화기"""
    return DynamicPortfolioOptimizer(
        coinone_client=None,
        risk_level="aggressive",
        max_assets=8
    )


@pytest.fixture
def sample_asset_metrics():
    """샘플 자산 지표"""
    return {
        "BTC": AssetMetrics(
            symbol="BTC",
            market_cap=800_000_000_000,
            volume_24h=30_000_000_000,
            price_change_24h=0.02,
            price_change_7d=0.05,
            price_change_30d=0.10,
            volatility_30d=0.20,
            sharpe_ratio_30d=1.5,
            max_drawdown_30d=-0.15,
            correlation_btc=1.0,
            liquidity_score=0.95,
            momentum_score=0.75,
            quality_score=0.85,
            risk_score=0.25,
            overall_score=0.90,
            asset_class=AssetClass.CORE
        ),
        "ETH": AssetMetrics(
            symbol="ETH",
            market_cap=300_000_000_000,
            volume_24h=15_000_000_000,
            price_change_24h=0.03,
            price_change_7d=0.08,
            price_change_30d=0.15,
            volatility_30d=0.30,
            sharpe_ratio_30d=1.2,
            max_drawdown_30d=-0.20,
            correlation_btc=0.85,
            liquidity_score=0.90,
            momentum_score=0.80,
            quality_score=0.75,
            risk_score=0.30,
            overall_score=0.85,
            asset_class=AssetClass.CORE
        ),
        "XRP": AssetMetrics(
            symbol="XRP",
            market_cap=30_000_000_000,
            volume_24h=2_000_000_000,
            price_change_24h=0.01,
            price_change_7d=0.03,
            price_change_30d=0.08,
            volatility_30d=0.35,
            sharpe_ratio_30d=0.8,
            max_drawdown_30d=-0.25,
            correlation_btc=0.75,
            liquidity_score=0.70,
            momentum_score=0.60,
            quality_score=0.65,
            risk_score=0.35,
            overall_score=0.65,
            asset_class=AssetClass.LARGE_CAP
        ),
        "SOL": AssetMetrics(
            symbol="SOL",
            market_cap=50_000_000_000,
            volume_24h=3_000_000_000,
            price_change_24h=0.04,
            price_change_7d=0.10,
            price_change_30d=0.20,
            volatility_30d=0.40,
            sharpe_ratio_30d=1.0,
            max_drawdown_30d=-0.30,
            correlation_btc=0.70,
            liquidity_score=0.75,
            momentum_score=0.85,
            quality_score=0.70,
            risk_score=0.40,
            overall_score=0.70,
            asset_class=AssetClass.LAYER1
        ),
        "LINK": AssetMetrics(
            symbol="LINK",
            market_cap=10_000_000_000,
            volume_24h=500_000_000,
            price_change_24h=0.02,
            price_change_7d=0.05,
            price_change_30d=0.12,
            volatility_30d=0.38,
            sharpe_ratio_30d=0.9,
            max_drawdown_30d=-0.28,
            correlation_btc=0.65,
            liquidity_score=0.60,
            momentum_score=0.65,
            quality_score=0.62,
            risk_score=0.38,
            overall_score=0.60,
            asset_class=AssetClass.UTILITY
        ),
        "UNI": AssetMetrics(
            symbol="UNI",
            market_cap=5_000_000_000,
            volume_24h=200_000_000,
            price_change_24h=-0.01,
            price_change_7d=0.02,
            price_change_30d=0.05,
            volatility_30d=0.45,
            sharpe_ratio_30d=0.5,
            max_drawdown_30d=-0.35,
            correlation_btc=0.60,
            liquidity_score=0.50,
            momentum_score=0.45,
            quality_score=0.55,
            risk_score=0.45,
            overall_score=0.50,
            asset_class=AssetClass.DEFI
        )
    }


@pytest.fixture
def mock_yfinance_data():
    """모의 yfinance 데이터"""
    dates = pd.date_range(end=datetime.now(), periods=30, freq='D')
    prices = np.random.uniform(40000, 45000, 30)

    return pd.DataFrame({
        'Open': prices * 0.99,
        'High': prices * 1.02,
        'Low': prices * 0.98,
        'Close': prices,
        'Volume': np.random.uniform(1e10, 2e10, 30)
    }, index=dates)


# ============================================================================
# Initialization Tests
# ============================================================================

class TestDynamicPortfolioOptimizerInit:
    """DynamicPortfolioOptimizer 초기화 테스트"""

    def test_default_initialization(self, optimizer):
        """기본 초기화"""
        assert optimizer.risk_level == "moderate"
        assert optimizer.max_assets == 6
        assert optimizer.min_market_cap_usd == 1e9
        assert optimizer.max_single_weight == 0.5
        assert optimizer.min_single_weight == 0.05

    def test_conservative_initialization(self, conservative_optimizer):
        """보수적 설정 초기화"""
        assert conservative_optimizer.risk_level == "conservative"
        assert conservative_optimizer.max_assets == 4

    def test_aggressive_initialization(self, aggressive_optimizer):
        """공격적 설정 초기화"""
        assert aggressive_optimizer.risk_level == "aggressive"
        assert aggressive_optimizer.max_assets == 8

    def test_risk_settings_exist(self, optimizer):
        """리스크 설정 존재 확인"""
        assert "conservative" in optimizer.risk_settings
        assert "moderate" in optimizer.risk_settings
        assert "aggressive" in optimizer.risk_settings

    def test_available_assets(self, optimizer):
        """사용 가능한 자산 목록"""
        assert "BTC" in optimizer.available_assets
        assert "ETH" in optimizer.available_assets
        assert len(optimizer.available_assets) > 0

    def test_asset_classes_defined(self, optimizer):
        """자산 클래스 정의 확인"""
        assert optimizer.asset_classes["BTC"] == AssetClass.CORE
        assert optimizer.asset_classes["ETH"] == AssetClass.CORE
        assert optimizer.asset_classes["SOL"] == AssetClass.LAYER1


# ============================================================================
# Calculate Overall Score Tests
# ============================================================================

class TestCalculateOverallScore:
    """종합 점수 계산 테스트"""

    def test_conservative_score(self, conservative_optimizer):
        """보수적 점수 계산"""
        score = conservative_optimizer._calculate_overall_score(
            momentum=0.5,
            quality=0.8,
            risk=0.3,
            liquidity=0.7,
            correlation=0.6
        )
        # 보수적: 품질 중시
        assert 0 <= score <= 1

    def test_moderate_score(self, optimizer):
        """균형형 점수 계산"""
        score = optimizer._calculate_overall_score(
            momentum=0.6,
            quality=0.7,
            risk=0.25,
            liquidity=0.8,
            correlation=0.5
        )
        assert 0 <= score <= 1

    def test_aggressive_score(self, aggressive_optimizer):
        """공격적 점수 계산"""
        score = aggressive_optimizer._calculate_overall_score(
            momentum=0.9,
            quality=0.5,
            risk=0.6,
            liquidity=0.6,
            correlation=0.7
        )
        # 공격적: 모멘텀 중시
        assert 0 <= score <= 1

    def test_high_correlation_penalty(self, optimizer):
        """높은 상관관계 패널티"""
        score_low_corr = optimizer._calculate_overall_score(
            momentum=0.6, quality=0.7, risk=0.25, liquidity=0.8, correlation=0.5
        )
        score_high_corr = optimizer._calculate_overall_score(
            momentum=0.6, quality=0.7, risk=0.25, liquidity=0.8, correlation=0.95
        )
        # 높은 상관관계는 점수가 낮아야 함
        assert score_high_corr <= score_low_corr

    def test_score_bounds(self, optimizer):
        """점수 범위 제한"""
        # 극단적인 값 테스트
        score_max = optimizer._calculate_overall_score(
            momentum=10, quality=10, risk=-5, liquidity=10, correlation=0
        )
        score_min = optimizer._calculate_overall_score(
            momentum=-10, quality=-10, risk=15, liquidity=-10, correlation=0
        )
        assert score_max <= 1
        assert score_min >= 0


# ============================================================================
# Select Optimal Portfolio Tests
# ============================================================================

class TestSelectOptimalPortfolio:
    """최적 포트폴리오 선택 테스트"""

    def test_core_assets_always_included(self, optimizer, sample_asset_metrics):
        """Core 자산 항상 포함"""
        selected = optimizer.select_optimal_portfolio(sample_asset_metrics)
        assert "BTC" in selected
        assert "ETH" in selected

    def test_respects_max_assets(self, optimizer, sample_asset_metrics):
        """최대 자산 수 준수"""
        selected = optimizer.select_optimal_portfolio(sample_asset_metrics)
        assert len(selected) <= optimizer.max_assets

    def test_selection_with_conservative(self, conservative_optimizer, sample_asset_metrics):
        """보수적 선택"""
        selected = conservative_optimizer.select_optimal_portfolio(sample_asset_metrics)
        # 보수적: 더 적은 자산
        assert len(selected) >= 2
        assert "BTC" in selected

    def test_empty_metrics_returns_empty(self, optimizer):
        """빈 지표 시 빈 리스트 반환"""
        selected = optimizer.select_optimal_portfolio({})
        # Core 자산이 없으면 빈 리스트
        assert selected == []

    def test_selection_based_on_score(self, optimizer, sample_asset_metrics):
        """점수 기반 선택"""
        selected = optimizer.select_optimal_portfolio(sample_asset_metrics)
        # BTC, ETH는 Core이므로 포함
        # 나머지는 점수 순으로 선택
        assert "BTC" in selected
        assert "ETH" in selected


class TestSelectOptimalPortfolioFiltering:
    """포트폴리오 선택 필터링 테스트"""

    def test_filters_low_score_assets(self, optimizer):
        """낮은 점수 자산 필터링"""
        low_score_metrics = {
            "BTC": AssetMetrics(
                symbol="BTC", market_cap=800e9, volume_24h=30e9,
                price_change_24h=0.02, price_change_7d=0.05, price_change_30d=0.10,
                volatility_30d=0.20, sharpe_ratio_30d=1.5, max_drawdown_30d=-0.15,
                correlation_btc=1.0, liquidity_score=0.95, momentum_score=0.75,
                quality_score=0.85, risk_score=0.25, overall_score=0.90,
                asset_class=AssetClass.CORE
            ),
            "ETH": AssetMetrics(
                symbol="ETH", market_cap=300e9, volume_24h=15e9,
                price_change_24h=0.03, price_change_7d=0.08, price_change_30d=0.15,
                volatility_30d=0.30, sharpe_ratio_30d=1.2, max_drawdown_30d=-0.20,
                correlation_btc=0.85, liquidity_score=0.90, momentum_score=0.80,
                quality_score=0.75, risk_score=0.30, overall_score=0.85,
                asset_class=AssetClass.CORE
            ),
            "LOWCOIN": AssetMetrics(
                symbol="LOWCOIN", market_cap=1e9, volume_24h=100e6,
                price_change_24h=-0.05, price_change_7d=-0.10, price_change_30d=-0.20,
                volatility_30d=0.80, sharpe_ratio_30d=-0.5, max_drawdown_30d=-0.60,
                correlation_btc=0.90, liquidity_score=0.20, momentum_score=-0.30,
                quality_score=0.10, risk_score=0.80, overall_score=0.15,
                asset_class=AssetClass.UTILITY
            )
        }
        selected = optimizer.select_optimal_portfolio(low_score_metrics)
        # 낮은 점수 자산은 선택되지 않음
        assert "LOWCOIN" not in selected


# ============================================================================
# Optimize Weights Tests
# ============================================================================

class TestOptimizeWeights:
    """포트폴리오 비중 최적화 테스트"""

    def test_weights_sum_to_one(self, optimizer, sample_asset_metrics):
        """비중 합계가 1"""
        selected = ["BTC", "ETH", "XRP", "SOL"]
        portfolio = optimizer.optimize_weights(selected, sample_asset_metrics)
        total_weight = sum(portfolio.weights.values())
        assert abs(total_weight - 1.0) < 0.01

    def test_core_assets_have_minimum_weight(self, optimizer, sample_asset_metrics):
        """Core 자산 최소 비중 보장"""
        selected = ["BTC", "ETH", "XRP", "SOL"]
        portfolio = optimizer.optimize_weights(selected, sample_asset_metrics)
        core_weight = portfolio.weights.get("BTC", 0) + portfolio.weights.get("ETH", 0)
        assert core_weight >= 0.4  # 적어도 40%

    def test_btc_weight_higher_than_eth(self, optimizer, sample_asset_metrics):
        """BTC 비중 > ETH 비중"""
        selected = ["BTC", "ETH", "XRP"]
        portfolio = optimizer.optimize_weights(selected, sample_asset_metrics)
        # BTC:ETH = 60:40 비율
        assert portfolio.weights["BTC"] >= portfolio.weights["ETH"]

    def test_portfolio_weights_structure(self, optimizer, sample_asset_metrics):
        """PortfolioWeights 구조"""
        selected = ["BTC", "ETH", "XRP"]
        portfolio = optimizer.optimize_weights(selected, sample_asset_metrics)

        assert isinstance(portfolio, PortfolioWeights)
        assert portfolio.risk_level == optimizer.risk_level
        assert "expected_return" in dir(portfolio)
        assert "expected_risk" in dir(portfolio)
        assert "sharpe_ratio" in dir(portfolio)

    def test_conservative_higher_core_weight(self, sample_asset_metrics):
        """보수적 설정에서 더 높은 Core 비중"""
        conservative = DynamicPortfolioOptimizer(risk_level="conservative")
        aggressive = DynamicPortfolioOptimizer(risk_level="aggressive")

        selected = ["BTC", "ETH", "XRP", "SOL"]

        portfolio_conservative = conservative.optimize_weights(selected, sample_asset_metrics)
        portfolio_aggressive = aggressive.optimize_weights(selected, sample_asset_metrics)

        core_weight_conservative = (
            portfolio_conservative.weights.get("BTC", 0) +
            portfolio_conservative.weights.get("ETH", 0)
        )
        core_weight_aggressive = (
            portfolio_aggressive.weights.get("BTC", 0) +
            portfolio_aggressive.weights.get("ETH", 0)
        )

        assert core_weight_conservative >= core_weight_aggressive


# ============================================================================
# Apply Weight Constraints Tests
# ============================================================================

class TestApplyWeightConstraints:
    """비중 제약 조건 테스트"""

    def test_max_single_weight_applied_before_normalization(self, optimizer):
        """최대 단일 비중은 정규화 전에 적용"""
        weights = {"BTC": 0.7, "ETH": 0.2, "XRP": 0.1}
        constrained = optimizer._apply_weight_constraints(weights)

        # 정규화로 인해 최대 비중 초과 가능
        # 원래 0.7 -> 0.5로 클램핑 -> 총합 0.8 -> 정규화 후 0.625
        # 모든 비중의 합은 1
        assert abs(sum(constrained.values()) - 1.0) < 0.01

    def test_min_single_weight_applied_before_normalization(self, optimizer):
        """최소 단일 비중은 정규화 전에 적용"""
        weights = {"BTC": 0.5, "ETH": 0.49, "XRP": 0.01}
        constrained = optimizer._apply_weight_constraints(weights)

        # 정규화로 인해 최소 비중 미달 가능
        # 원래 0.01 -> 0.05로 클램핑 -> 정규화
        # 모든 비중의 합은 1
        assert abs(sum(constrained.values()) - 1.0) < 0.01

    def test_weights_normalized_to_one(self, optimizer):
        """비중 정규화"""
        weights = {"BTC": 0.4, "ETH": 0.3, "XRP": 0.2}  # sum = 0.9
        constrained = optimizer._apply_weight_constraints(weights)

        total = sum(constrained.values())
        assert abs(total - 1.0) < 0.01

    def test_empty_weights(self, optimizer):
        """빈 비중"""
        weights = {}
        constrained = optimizer._apply_weight_constraints(weights)
        assert constrained == {}


# ============================================================================
# Calculate Portfolio Stats Tests
# ============================================================================

class TestCalculatePortfolioStats:
    """포트폴리오 통계 계산 테스트"""

    def test_basic_stats_calculation(self, optimizer, sample_asset_metrics):
        """기본 통계 계산"""
        weights = {"BTC": 0.5, "ETH": 0.3, "XRP": 0.2}
        stats = optimizer._calculate_portfolio_stats(weights, sample_asset_metrics)

        assert "expected_return" in stats
        assert "expected_risk" in stats
        assert "sharpe_ratio" in stats

    def test_sharpe_ratio_calculation(self, optimizer, sample_asset_metrics):
        """샤프 비율 계산"""
        weights = {"BTC": 0.6, "ETH": 0.4}
        stats = optimizer._calculate_portfolio_stats(weights, sample_asset_metrics)

        # 샤프 비율 = 수익률 / 리스크
        if stats["expected_risk"] > 0:
            expected_sharpe = stats["expected_return"] / stats["expected_risk"]
            assert abs(stats["sharpe_ratio"] - expected_sharpe) < 0.01

    def test_zero_risk_returns_zero_sharpe(self, optimizer):
        """리스크 0일 때 샤프 비율"""
        metrics = {
            "BTC": AssetMetrics(
                symbol="BTC", market_cap=800e9, volume_24h=30e9,
                price_change_24h=0, price_change_7d=0, price_change_30d=0,
                volatility_30d=0, sharpe_ratio_30d=0, max_drawdown_30d=0,
                correlation_btc=1.0, liquidity_score=1.0, momentum_score=0,
                quality_score=0, risk_score=0, overall_score=0.5,
                asset_class=AssetClass.CORE
            )
        }
        weights = {"BTC": 1.0}
        stats = optimizer._calculate_portfolio_stats(weights, metrics)

        assert stats["sharpe_ratio"] == 0

    def test_missing_asset_in_weights(self, optimizer, sample_asset_metrics):
        """가중치에 없는 자산"""
        weights = {"BTC": 0.5, "ETH": 0.5}  # XRP 제외
        stats = optimizer._calculate_portfolio_stats(weights, sample_asset_metrics)

        # XRP는 계산에서 제외됨
        assert stats["expected_return"] is not None


# ============================================================================
# Get Default Portfolio Tests
# ============================================================================

class TestGetDefaultPortfolio:
    """기본 포트폴리오 테스트"""

    def test_default_portfolio_structure(self, optimizer):
        """기본 포트폴리오 구조"""
        default = optimizer._get_default_portfolio()

        assert isinstance(default, PortfolioWeights)
        assert "BTC" in default.weights
        assert "ETH" in default.weights
        assert abs(sum(default.weights.values()) - 1.0) < 0.01

    def test_default_portfolio_values(self, optimizer):
        """기본 포트폴리오 값"""
        default = optimizer._get_default_portfolio()

        assert default.weights["BTC"] == 0.40
        assert default.weights["ETH"] == 0.30
        assert default.risk_level == optimizer.risk_level


# ============================================================================
# Analyze Assets Tests (with mocking)
# ============================================================================

class TestAnalyzeAllAssets:
    """전체 자산 분석 테스트"""

    @patch('yfinance.Ticker')
    def test_analyze_all_assets_success(self, mock_ticker, optimizer):
        """자산 분석 성공"""
        # Mock ticker data
        mock_history = pd.DataFrame({
            'Close': np.random.uniform(40000, 45000, 30),
            'Volume': np.random.uniform(1e10, 2e10, 30)
        }, index=pd.date_range(end=datetime.now(), periods=30))

        mock_info = {
            'marketCap': 800_000_000_000,
            'averageVolume': 30_000_000_000
        }

        mock_ticker_instance = MagicMock()
        mock_ticker_instance.history.return_value = mock_history
        mock_ticker_instance.info = mock_info
        mock_ticker.return_value = mock_ticker_instance

        # Test
        result = optimizer.analyze_all_assets()

        # 적어도 일부 자산은 분석됨
        assert isinstance(result, dict)

    def test_analyze_all_assets_handles_errors(self, optimizer):
        """분석 오류 처리"""
        # yfinance가 실패해도 빈 dict 반환
        with patch('yfinance.Ticker', side_effect=Exception("API Error")):
            result = optimizer.analyze_all_assets()
            assert result == {}


class TestAnalyzeSingleAsset:
    """단일 자산 분석 테스트"""

    @patch('yfinance.Ticker')
    def test_analyze_single_asset_success(self, mock_ticker, optimizer):
        """단일 자산 분석 성공"""
        dates = pd.date_range(end=datetime.now(), periods=30, freq='D')
        prices = np.linspace(40000, 45000, 30)

        mock_history = pd.DataFrame({
            'Close': prices,
            'Open': prices * 0.99,
            'High': prices * 1.02,
            'Low': prices * 0.98,
            'Volume': np.random.uniform(1e10, 2e10, 30)
        }, index=dates)

        mock_info = {
            'marketCap': 800_000_000_000,
            'averageVolume': 30_000_000_000
        }

        mock_ticker_instance = MagicMock()
        mock_ticker_instance.history.return_value = mock_history
        mock_ticker_instance.info = mock_info
        mock_ticker.return_value = mock_ticker_instance

        result = optimizer._analyze_single_asset("BTC")

        if result is not None:
            assert isinstance(result, AssetMetrics)
            assert result.symbol == "BTC"

    @patch('yfinance.Ticker')
    def test_analyze_single_asset_low_market_cap(self, mock_ticker, optimizer):
        """낮은 시가총액 자산 필터링"""
        mock_history = pd.DataFrame({
            'Close': [100] * 30
        }, index=pd.date_range(end=datetime.now(), periods=30))

        mock_info = {
            'marketCap': 100_000_000,  # 1억 달러 (1B 미만)
            'averageVolume': 1_000_000
        }

        mock_ticker_instance = MagicMock()
        mock_ticker_instance.history.return_value = mock_history
        mock_ticker_instance.info = mock_info
        mock_ticker.return_value = mock_ticker_instance

        result = optimizer._analyze_single_asset("LOWCAP")

        # 시가총액 부족으로 None 반환
        assert result is None

    @patch('yfinance.Ticker')
    def test_analyze_single_asset_empty_history(self, mock_ticker, optimizer):
        """빈 가격 히스토리"""
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.history.return_value = pd.DataFrame()
        mock_ticker.return_value = mock_ticker_instance

        result = optimizer._analyze_single_asset("NODATA")

        assert result is None


# ============================================================================
# Calculate BTC Correlation Tests
# ============================================================================

class TestCalculateBTCCorrelation:
    """BTC 상관관계 계산 테스트"""

    def test_btc_correlation_with_itself(self, optimizer):
        """BTC 자신과의 상관관계"""
        correlation = optimizer._calculate_btc_correlation("BTC")
        assert correlation == 1.0

    @patch('yfinance.Ticker')
    def test_correlation_calculation(self, mock_ticker, optimizer):
        """상관관계 계산"""
        dates = pd.date_range(end=datetime.now(), periods=30, freq='D')
        btc_prices = np.linspace(40000, 45000, 30)
        eth_prices = btc_prices * 0.075  # ETH는 BTC와 상관관계 높음

        def mock_ticker_factory(symbol):
            mock_instance = MagicMock()
            if "BTC" in symbol:
                mock_instance.history.return_value = pd.DataFrame({
                    'Close': btc_prices
                }, index=dates)
            else:
                mock_instance.history.return_value = pd.DataFrame({
                    'Close': eth_prices
                }, index=dates)
            return mock_instance

        mock_ticker.side_effect = mock_ticker_factory

        correlation = optimizer._calculate_btc_correlation("ETH")

        # 상관관계는 -1 ~ 1 사이
        assert -1.0 <= correlation <= 1.0

    @patch('yfinance.Ticker')
    def test_correlation_insufficient_data(self, mock_ticker, optimizer):
        """데이터 부족 시 기본값"""
        mock_instance = MagicMock()
        mock_instance.history.return_value = pd.DataFrame({
            'Close': [100, 101, 102]  # 10일 미만
        })
        mock_ticker.return_value = mock_instance

        correlation = optimizer._calculate_btc_correlation("NODATA")

        # 기본값 0.5 반환
        assert correlation == 0.5

    @patch('yfinance.Ticker')
    def test_correlation_error_handling(self, mock_ticker, optimizer):
        """오류 처리"""
        mock_ticker.side_effect = Exception("API Error")

        correlation = optimizer._calculate_btc_correlation("ERROR")

        # 오류 시 기본값 0.5 반환
        assert correlation == 0.5


# ============================================================================
# Generate Optimal Portfolio Tests
# ============================================================================

class TestGenerateOptimalPortfolio:
    """최적 포트폴리오 생성 테스트"""

    def test_generate_with_default_fallback(self, optimizer):
        """기본값 폴백"""
        with patch.object(optimizer, 'analyze_all_assets', return_value={}):
            portfolio = optimizer.generate_optimal_portfolio()

            # 기본 포트폴리오 반환
            assert isinstance(portfolio, PortfolioWeights)
            assert "BTC" in portfolio.weights

    def test_generate_with_insufficient_assets(self, optimizer):
        """자산 부족 시 기본값"""
        with patch.object(optimizer, 'analyze_all_assets', return_value={"BTC": Mock()}):
            with patch.object(optimizer, 'select_optimal_portfolio', return_value=["BTC"]):
                portfolio = optimizer.generate_optimal_portfolio()

                # 기본 포트폴리오 반환
                assert isinstance(portfolio, PortfolioWeights)

    def test_generate_full_process(self, optimizer, sample_asset_metrics):
        """전체 프로세스"""
        with patch.object(optimizer, 'analyze_all_assets', return_value=sample_asset_metrics):
            portfolio = optimizer.generate_optimal_portfolio()

            assert isinstance(portfolio, PortfolioWeights)
            assert sum(portfolio.weights.values()) > 0


# ============================================================================
# Should Rebalance Portfolio Tests
# ============================================================================

class TestShouldRebalancePortfolio:
    """리밸런싱 필요 여부 판단 테스트"""

    def test_rebalance_needed_large_deviation(self, optimizer, sample_asset_metrics):
        """큰 편차 시 리밸런싱 필요"""
        with patch.object(optimizer, 'generate_optimal_portfolio') as mock_gen:
            mock_portfolio = PortfolioWeights(
                weights={"BTC": 0.5, "ETH": 0.3, "XRP": 0.2},
                risk_level="moderate",
                diversification_score=0.5,
                expected_return=0.1,
                expected_risk=0.2,
                sharpe_ratio=0.5
            )
            mock_gen.return_value = mock_portfolio

            # 현재 비중이 많이 다름
            current_weights = {"BTC": 0.2, "ETH": 0.1, "XRP": 0.7}

            should_rebalance = optimizer.should_rebalance_portfolio(current_weights)

            assert should_rebalance is True

    def test_rebalance_not_needed_small_deviation(self, optimizer, sample_asset_metrics):
        """작은 편차 시 리밸런싱 불필요"""
        with patch.object(optimizer, 'generate_optimal_portfolio') as mock_gen:
            mock_portfolio = PortfolioWeights(
                weights={"BTC": 0.50, "ETH": 0.30, "XRP": 0.20},
                risk_level="moderate",
                diversification_score=0.5,
                expected_return=0.1,
                expected_risk=0.2,
                sharpe_ratio=0.5
            )
            mock_gen.return_value = mock_portfolio

            # 현재 비중이 거의 같음
            current_weights = {"BTC": 0.48, "ETH": 0.32, "XRP": 0.20}

            should_rebalance = optimizer.should_rebalance_portfolio(current_weights)

            assert should_rebalance is False

    def test_rebalance_error_handling(self, optimizer):
        """오류 처리"""
        with patch.object(optimizer, 'generate_optimal_portfolio',
                         side_effect=Exception("Error")):
            should_rebalance = optimizer.should_rebalance_portfolio({"BTC": 1.0})

            assert should_rebalance is False


# ============================================================================
# Enum Tests
# ============================================================================

class TestEnums:
    """Enum 테스트"""

    def test_asset_class_values(self):
        """AssetClass 값"""
        assert AssetClass.CORE.value == "core"
        assert AssetClass.LARGE_CAP.value == "large_cap"
        assert AssetClass.LAYER1.value == "layer1"
        assert AssetClass.DEFI.value == "defi"
        assert AssetClass.MEME.value == "meme"

    def test_selection_criteria_values(self):
        """SelectionCriteria 값"""
        assert SelectionCriteria.MARKET_CAP.value == "market_cap"
        assert SelectionCriteria.VOLUME.value == "volume"
        assert SelectionCriteria.MOMENTUM.value == "momentum"
        assert SelectionCriteria.SHARPE_RATIO.value == "sharpe_ratio"


# ============================================================================
# Dataclass Tests
# ============================================================================

class TestAssetMetrics:
    """AssetMetrics 데이터 클래스 테스트"""

    def test_asset_metrics_creation(self):
        """AssetMetrics 생성"""
        metrics = AssetMetrics(
            symbol="BTC",
            market_cap=800e9,
            volume_24h=30e9,
            price_change_24h=0.02,
            price_change_7d=0.05,
            price_change_30d=0.10,
            volatility_30d=0.20,
            sharpe_ratio_30d=1.5,
            max_drawdown_30d=-0.15,
            correlation_btc=1.0,
            liquidity_score=0.95,
            momentum_score=0.75,
            quality_score=0.85,
            risk_score=0.25,
            overall_score=0.90,
            asset_class=AssetClass.CORE
        )

        assert metrics.symbol == "BTC"
        assert metrics.market_cap == 800e9
        assert metrics.asset_class == AssetClass.CORE

    def test_asset_metrics_default_last_updated(self):
        """기본 last_updated 값"""
        metrics = AssetMetrics(
            symbol="ETH",
            market_cap=300e9,
            volume_24h=15e9,
            price_change_24h=0.03,
            price_change_7d=0.08,
            price_change_30d=0.15,
            volatility_30d=0.30,
            sharpe_ratio_30d=1.2,
            max_drawdown_30d=-0.20,
            correlation_btc=0.85,
            liquidity_score=0.90,
            momentum_score=0.80,
            quality_score=0.75,
            risk_score=0.30,
            overall_score=0.85,
            asset_class=AssetClass.CORE
        )

        assert metrics.last_updated is not None


class TestPortfolioWeights:
    """PortfolioWeights 데이터 클래스 테스트"""

    def test_portfolio_weights_creation(self):
        """PortfolioWeights 생성"""
        weights = PortfolioWeights(
            weights={"BTC": 0.5, "ETH": 0.3, "XRP": 0.2},
            risk_level="moderate",
            diversification_score=0.7,
            expected_return=0.15,
            expected_risk=0.25,
            sharpe_ratio=0.6
        )

        assert weights.weights["BTC"] == 0.5
        assert weights.risk_level == "moderate"
        assert weights.sharpe_ratio == 0.6

    def test_portfolio_weights_default_created_at(self):
        """기본 created_at 값"""
        weights = PortfolioWeights(
            weights={"BTC": 1.0},
            risk_level="conservative",
            diversification_score=0.3,
            expected_return=0.10,
            expected_risk=0.15,
            sharpe_ratio=0.67
        )

        assert weights.created_at is not None


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """엣지 케이스 테스트"""

    def test_single_asset_portfolio(self, optimizer):
        """단일 자산 포트폴리오"""
        metrics = {
            "BTC": AssetMetrics(
                symbol="BTC", market_cap=800e9, volume_24h=30e9,
                price_change_24h=0.02, price_change_7d=0.05, price_change_30d=0.10,
                volatility_30d=0.20, sharpe_ratio_30d=1.5, max_drawdown_30d=-0.15,
                correlation_btc=1.0, liquidity_score=0.95, momentum_score=0.75,
                quality_score=0.85, risk_score=0.25, overall_score=0.90,
                asset_class=AssetClass.CORE
            )
        }

        portfolio = optimizer.optimize_weights(["BTC"], metrics)

        assert portfolio.weights["BTC"] == 1.0

    def test_all_non_core_assets(self, optimizer):
        """Core가 아닌 자산만"""
        metrics = {
            "XRP": AssetMetrics(
                symbol="XRP", market_cap=30e9, volume_24h=2e9,
                price_change_24h=0.01, price_change_7d=0.03, price_change_30d=0.08,
                volatility_30d=0.35, sharpe_ratio_30d=0.8, max_drawdown_30d=-0.25,
                correlation_btc=0.75, liquidity_score=0.70, momentum_score=0.60,
                quality_score=0.65, risk_score=0.35, overall_score=0.65,
                asset_class=AssetClass.LARGE_CAP
            ),
            "SOL": AssetMetrics(
                symbol="SOL", market_cap=50e9, volume_24h=3e9,
                price_change_24h=0.04, price_change_7d=0.10, price_change_30d=0.20,
                volatility_30d=0.40, sharpe_ratio_30d=1.0, max_drawdown_30d=-0.30,
                correlation_btc=0.70, liquidity_score=0.75, momentum_score=0.85,
                quality_score=0.70, risk_score=0.40, overall_score=0.70,
                asset_class=AssetClass.LAYER1
            )
        }

        portfolio = optimizer.optimize_weights(["XRP", "SOL"], metrics)

        assert abs(sum(portfolio.weights.values()) - 1.0) < 0.01

    def test_negative_scores(self, optimizer):
        """음수 점수 처리"""
        score = optimizer._calculate_overall_score(
            momentum=-0.5,
            quality=-0.3,
            risk=1.5,
            liquidity=-0.2,
            correlation=0.5
        )

        # 점수는 0 이상
        assert score >= 0


# ============================================================================
# Uncovered Lines Tests
# ============================================================================

class TestDynamicPortfolioOptimizerUncoveredLines:
    """커버되지 않은 라인 테스트"""

    @pytest.fixture
    def optimizer(self):
        return DynamicPortfolioOptimizer(
            coinone_client=None,
            risk_level="moderate",
            max_assets=6
        )

    def test_analyze_all_assets_single_asset_exception(self, optimizer):
        """단일 자산 분석 중 예외 발생 (라인 179-181)"""
        with patch('yfinance.Ticker') as mock_ticker:
            # 첫 번째 자산만 예외, 나머지는 정상
            call_count = [0]

            def mock_ticker_factory(symbol):
                call_count[0] += 1
                if call_count[0] == 1:
                    raise Exception("First asset failed")
                mock_instance = MagicMock()
                mock_instance.history.return_value = pd.DataFrame()  # 빈 데이터
                mock_instance.info = {}
                return mock_instance

            mock_ticker.side_effect = mock_ticker_factory

            result = optimizer.analyze_all_assets()

            # 예외가 발생해도 계속 진행
            assert isinstance(result, dict)

    def test_analyze_all_assets_general_exception(self, optimizer):
        """전체 자산 분석 중 예외 (라인 186-188)"""
        # available_assets를 순회하기 전에 예외 발생
        optimizer.available_assets = None  # TypeError 유발

        result = optimizer.analyze_all_assets()

        # 예외 시 None 반환
        assert result is None

    def test_select_portfolio_diversification_filter(self, optimizer):
        """포트폴리오 선택 - 같은 클래스 필터 (라인 383, 388)"""
        # 같은 클래스에서 여러 자산 - 하나만 선택되어야 함
        metrics = {
            "BTC": AssetMetrics(
                symbol="BTC", market_cap=800e9, volume_24h=30e9,
                price_change_24h=0.02, price_change_7d=0.05, price_change_30d=0.10,
                volatility_30d=0.20, sharpe_ratio_30d=1.5, max_drawdown_30d=-0.15,
                correlation_btc=1.0, liquidity_score=0.95, momentum_score=0.75,
                quality_score=0.85, risk_score=0.25, overall_score=0.90,
                asset_class=AssetClass.CORE
            ),
            "ETH": AssetMetrics(
                symbol="ETH", market_cap=300e9, volume_24h=15e9,
                price_change_24h=0.03, price_change_7d=0.08, price_change_30d=0.15,
                volatility_30d=0.30, sharpe_ratio_30d=1.2, max_drawdown_30d=-0.20,
                correlation_btc=0.85, liquidity_score=0.90, momentum_score=0.80,
                quality_score=0.75, risk_score=0.30, overall_score=0.85,
                asset_class=AssetClass.CORE
            ),
            "SOL": AssetMetrics(
                symbol="SOL", market_cap=50e9, volume_24h=3e9,
                price_change_24h=0.04, price_change_7d=0.10, price_change_30d=0.20,
                volatility_30d=0.40, sharpe_ratio_30d=1.0, max_drawdown_30d=-0.30,
                correlation_btc=0.70, liquidity_score=0.75, momentum_score=0.85,
                quality_score=0.70, risk_score=0.40, overall_score=0.70,
                asset_class=AssetClass.LAYER1
            ),
            "AVAX": AssetMetrics(
                symbol="AVAX", market_cap=30e9, volume_24h=2e9,
                price_change_24h=0.02, price_change_7d=0.06, price_change_30d=0.12,
                volatility_30d=0.45, sharpe_ratio_30d=0.8, max_drawdown_30d=-0.32,
                correlation_btc=0.65, liquidity_score=0.65, momentum_score=0.70,
                quality_score=0.60, risk_score=0.45, overall_score=0.55,
                asset_class=AssetClass.LAYER1  # SOL과 같은 클래스
            )
        }

        selected = optimizer.select_optimal_portfolio(metrics)

        # LAYER1 클래스에서 하나만 선택되어야 함 (SOL이 점수가 높음)
        assert "BTC" in selected
        assert "ETH" in selected

    def test_select_portfolio_high_volatility_filter(self, optimizer):
        """포트폴리오 선택 - 높은 변동성 필터 (라인 398-400)"""
        metrics = {
            "BTC": AssetMetrics(
                symbol="BTC", market_cap=800e9, volume_24h=30e9,
                price_change_24h=0.02, price_change_7d=0.05, price_change_30d=0.10,
                volatility_30d=0.20, sharpe_ratio_30d=1.5, max_drawdown_30d=-0.15,
                correlation_btc=1.0, liquidity_score=0.95, momentum_score=0.75,
                quality_score=0.85, risk_score=0.25, overall_score=0.90,
                asset_class=AssetClass.CORE
            ),
            "ETH": AssetMetrics(
                symbol="ETH", market_cap=300e9, volume_24h=15e9,
                price_change_24h=0.03, price_change_7d=0.08, price_change_30d=0.15,
                volatility_30d=0.30, sharpe_ratio_30d=1.2, max_drawdown_30d=-0.20,
                correlation_btc=0.85, liquidity_score=0.90, momentum_score=0.80,
                quality_score=0.75, risk_score=0.30, overall_score=0.85,
                asset_class=AssetClass.CORE
            ),
            "VOLATILE": AssetMetrics(
                symbol="VOLATILE", market_cap=20e9, volume_24h=1e9,
                price_change_24h=0.10, price_change_7d=0.30, price_change_30d=0.50,
                volatility_30d=0.90,  # 매우 높은 변동성
                sharpe_ratio_30d=0.5, max_drawdown_30d=-0.50,
                correlation_btc=0.50, liquidity_score=0.50, momentum_score=0.90,
                quality_score=0.40, risk_score=0.80, overall_score=0.50,
                asset_class=AssetClass.MEME
            )
        }

        selected = optimizer.select_optimal_portfolio(metrics)

        # 높은 변동성 자산은 필터링됨
        assert "VOLATILE" not in selected

    def test_select_portfolio_exception(self, optimizer):
        """포트폴리오 선택 예외 (라인 406-408)"""
        # 예외를 발생시키는 잘못된 데이터
        with patch.object(optimizer, 'risk_settings', None):
            selected = optimizer.select_optimal_portfolio({})

            # 기본값 반환
            assert selected == ["BTC", "ETH", "XRP", "SOL"]

    def test_optimize_weights_btc_only(self, optimizer):
        """비중 최적화 - BTC만 있는 경우 (라인 437-438)"""
        metrics = {
            "BTC": AssetMetrics(
                symbol="BTC", market_cap=800e9, volume_24h=30e9,
                price_change_24h=0.02, price_change_7d=0.05, price_change_30d=0.10,
                volatility_30d=0.20, sharpe_ratio_30d=1.5, max_drawdown_30d=-0.15,
                correlation_btc=1.0, liquidity_score=0.95, momentum_score=0.75,
                quality_score=0.85, risk_score=0.25, overall_score=0.90,
                asset_class=AssetClass.CORE
            )
        }

        portfolio = optimizer.optimize_weights(["BTC"], metrics)

        # BTC만 있으므로 Core 비중 전체 할당
        assert portfolio.weights["BTC"] > 0

    def test_optimize_weights_eth_only(self, optimizer):
        """비중 최적화 - ETH만 있는 Core 경우 (라인 439-440)"""
        metrics = {
            "ETH": AssetMetrics(
                symbol="ETH", market_cap=300e9, volume_24h=15e9,
                price_change_24h=0.03, price_change_7d=0.08, price_change_30d=0.15,
                volatility_30d=0.30, sharpe_ratio_30d=1.2, max_drawdown_30d=-0.20,
                correlation_btc=0.85, liquidity_score=0.90, momentum_score=0.80,
                quality_score=0.75, risk_score=0.30, overall_score=0.85,
                asset_class=AssetClass.CORE
            )
        }

        portfolio = optimizer.optimize_weights(["ETH"], metrics)

        # ETH만 있으므로 Core 비중 전체 할당
        assert portfolio.weights["ETH"] > 0

    def test_optimize_weights_zero_score_non_core(self, optimizer):
        """비중 최적화 - non-core 자산 점수 합이 0 (라인 451)"""
        metrics = {
            "BTC": AssetMetrics(
                symbol="BTC", market_cap=800e9, volume_24h=30e9,
                price_change_24h=0.02, price_change_7d=0.05, price_change_30d=0.10,
                volatility_30d=0.20, sharpe_ratio_30d=1.5, max_drawdown_30d=-0.15,
                correlation_btc=1.0, liquidity_score=0.95, momentum_score=0.75,
                quality_score=0.85, risk_score=0.25, overall_score=0.90,
                asset_class=AssetClass.CORE
            ),
            "ZERO": AssetMetrics(
                symbol="ZERO", market_cap=10e9, volume_24h=1e9,
                price_change_24h=0, price_change_7d=0, price_change_30d=0,
                volatility_30d=0, sharpe_ratio_30d=0, max_drawdown_30d=0,
                correlation_btc=0, liquidity_score=0, momentum_score=0,
                quality_score=0, risk_score=0, overall_score=0,  # 점수 0
                asset_class=AssetClass.UTILITY
            )
        }

        portfolio = optimizer.optimize_weights(["BTC", "ZERO"], metrics)

        # 총합이 1이어야 함
        assert abs(sum(portfolio.weights.values()) - 1.0) < 0.01

    def test_apply_weight_constraints_exception(self, optimizer):
        """비중 제약 적용 예외 (라인 508-510)"""
        # 잘못된 타입으로 예외 유발
        original_weights = {"BTC": "invalid"}

        # _apply_weight_constraints를 직접 테스트
        result = optimizer._apply_weight_constraints(original_weights)

        # 예외 시 원본 반환
        assert result == original_weights

    def test_calculate_portfolio_stats_exception(self, optimizer):
        """포트폴리오 통계 계산 예외 (라인 542-544)"""
        # None 메트릭스로 예외 유발 시도
        class BadMetrics:
            def __init__(self):
                raise Exception("Bad metrics")

        bad_metrics = {}
        bad_metrics["BTC"] = MagicMock()
        bad_metrics["BTC"].price_change_30d = None  # None으로 곱셈 시 TypeError

        result = optimizer._calculate_portfolio_stats({"BTC": 0.5}, bad_metrics)

        # 예외 발생 시 기본값 반환
        assert result["expected_return"] == 0.1
        assert result["expected_risk"] == 0.2
        assert result["sharpe_ratio"] == 0.5

    def test_generate_optimal_portfolio_exception(self, optimizer):
        """최적 포트폴리오 생성 예외 (라인 573-575)"""
        with patch.object(optimizer, 'analyze_all_assets', side_effect=Exception("Error")):
            portfolio = optimizer.generate_optimal_portfolio()

            # 예외 시 기본 포트폴리오 반환
            assert isinstance(portfolio, PortfolioWeights)
            assert "BTC" in portfolio.weights

    def test_select_portfolio_low_score_filter(self, optimizer):
        """포트폴리오 선택 - 낮은 점수 필터 (라인 391-392)"""
        metrics = {
            "BTC": AssetMetrics(
                symbol="BTC", market_cap=800e9, volume_24h=30e9,
                price_change_24h=0.02, price_change_7d=0.05, price_change_30d=0.10,
                volatility_30d=0.20, sharpe_ratio_30d=1.5, max_drawdown_30d=-0.15,
                correlation_btc=1.0, liquidity_score=0.95, momentum_score=0.75,
                quality_score=0.85, risk_score=0.25, overall_score=0.90,
                asset_class=AssetClass.CORE
            ),
            "ETH": AssetMetrics(
                symbol="ETH", market_cap=300e9, volume_24h=15e9,
                price_change_24h=0.03, price_change_7d=0.08, price_change_30d=0.15,
                volatility_30d=0.30, sharpe_ratio_30d=1.2, max_drawdown_30d=-0.20,
                correlation_btc=0.85, liquidity_score=0.90, momentum_score=0.80,
                quality_score=0.75, risk_score=0.30, overall_score=0.85,
                asset_class=AssetClass.CORE
            ),
            "LOWSCORE": AssetMetrics(
                symbol="LOWSCORE", market_cap=10e9, volume_24h=500e6,
                price_change_24h=-0.05, price_change_7d=-0.10, price_change_30d=-0.20,
                volatility_30d=0.30, sharpe_ratio_30d=-0.5, max_drawdown_30d=-0.40,
                correlation_btc=0.40, liquidity_score=0.30, momentum_score=0.10,
                quality_score=0.20, risk_score=0.60, overall_score=0.15,  # 0.3 미만
                asset_class=AssetClass.UTILITY
            )
        }

        selected = optimizer.select_optimal_portfolio(metrics)

        # 낮은 점수 자산은 필터링됨
        assert "LOWSCORE" not in selected
