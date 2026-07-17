"""
Performance Tracker Tests

성과 추적기 테스트
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from src.monitoring.performance_tracker import (
    PerformanceTracker,
    PerformanceMetrics,
    DEFAULT_RISK_FREE_RATE,
    PERFORMANCE_CALCULATION_PERIODS
)


@pytest.mark.monitoring
class TestPerformanceMetrics:
    """PerformanceMetrics 데이터클래스 테스트"""

    def test_basic_metrics_creation(self):
        """기본 성과 지표 생성"""
        metrics = PerformanceMetrics(
            period_days=30,
            total_return=0.05,
            annualized_return=0.80,
            volatility=0.20,
            sharpe_ratio=1.5,
            max_drawdown=-0.10,
            benchmark_return=0.03,
            tracking_error=0.02
        )

        assert metrics.period_days == 30
        assert metrics.total_return == 0.05
        assert metrics.annualized_return == 0.80
        assert metrics.volatility == 0.20
        assert metrics.sharpe_ratio == 1.5
        assert metrics.max_drawdown == -0.10
        assert metrics.benchmark_return == 0.03
        assert metrics.tracking_error == 0.02

    def test_default_values(self):
        """기본값 확인"""
        metrics = PerformanceMetrics(
            period_days=7,
            total_return=0.01,
            annualized_return=0.5,
            volatility=0.15,
            sharpe_ratio=1.0,
            max_drawdown=-0.05,
            benchmark_return=0.02,
            tracking_error=0.01
        )

        assert metrics.win_rate == 0.0
        assert metrics.avg_win == 0.0
        assert metrics.avg_loss == 0.0
        assert metrics.calmar_ratio == 0.0
        assert metrics.sortino_ratio == 0.0

    def test_full_metrics_creation(self):
        """전체 필드 포함 생성"""
        metrics = PerformanceMetrics(
            period_days=90,
            total_return=0.15,
            annualized_return=0.60,
            volatility=0.25,
            sharpe_ratio=2.0,
            max_drawdown=-0.15,
            benchmark_return=0.10,
            tracking_error=0.05,
            win_rate=0.55,
            avg_win=0.03,
            avg_loss=-0.02,
            calmar_ratio=4.0,
            sortino_ratio=2.5
        )

        assert metrics.win_rate == 0.55
        assert metrics.avg_win == 0.03
        assert metrics.avg_loss == -0.02
        assert metrics.calmar_ratio == 4.0
        assert metrics.sortino_ratio == 2.5


@pytest.mark.monitoring
class TestPerformanceTrackerInit:
    """PerformanceTracker 초기화 테스트"""

    @pytest.fixture
    def mock_config(self):
        """Mock 설정"""
        config = Mock()
        config.get_risk_config.return_value = {
            "three_line_check": {
                "benchmark": "BTC",
                "performance_period": 30
            }
        }
        return config

    @pytest.fixture
    def mock_db_manager(self):
        """Mock DB 관리자"""
        return Mock()

    def test_init(self, mock_config, mock_db_manager):
        """초기화"""
        tracker = PerformanceTracker(mock_config, mock_db_manager)

        assert tracker.config == mock_config
        assert tracker.db_manager == mock_db_manager
        assert tracker.benchmark == "BTC"
        assert tracker.performance_period == 30
        assert tracker.risk_free_rate == 0.02

    def test_init_default_benchmark(self, mock_db_manager):
        """기본 벤치마크 설정"""
        config = Mock()
        config.get_risk_config.return_value = {"three_line_check": {}}

        tracker = PerformanceTracker(config, mock_db_manager)

        assert tracker.benchmark == "BTC"
        assert tracker.performance_period == 30


@pytest.mark.monitoring
class TestCalculateReturns:
    """수익률 계산 테스트"""

    @pytest.fixture
    def tracker(self):
        """PerformanceTracker 인스턴스"""
        config = Mock()
        config.get_risk_config.return_value = {"three_line_check": {}}
        db_manager = Mock()
        return PerformanceTracker(config, db_manager)

    def test_calculate_returns_simple(self, tracker):
        """간단한 수익률 계산"""
        values = [100, 110, 105, 115]
        returns = tracker._calculate_returns(values)

        assert len(returns) == 3
        assert returns[0] == pytest.approx(0.10, rel=0.01)  # 100 -> 110
        assert returns[1] == pytest.approx(-0.0454, rel=0.01)  # 110 -> 105
        assert returns[2] == pytest.approx(0.0952, rel=0.01)  # 105 -> 115

    def test_calculate_returns_constant(self, tracker):
        """변동 없는 수익률"""
        values = [100, 100, 100]
        returns = tracker._calculate_returns(values)

        assert len(returns) == 2
        assert all(r == 0.0 for r in returns)

    def test_calculate_returns_increasing(self, tracker):
        """꾸준한 상승"""
        values = [100, 120, 144]  # 20% 연속 상승
        returns = tracker._calculate_returns(values)

        assert len(returns) == 2
        assert returns[0] == pytest.approx(0.20, rel=0.01)
        assert returns[1] == pytest.approx(0.20, rel=0.01)


@pytest.mark.monitoring
class TestCalculateMaxDrawdown:
    """최대 드로우다운 계산 테스트"""

    @pytest.fixture
    def tracker(self):
        """PerformanceTracker 인스턴스"""
        config = Mock()
        config.get_risk_config.return_value = {"three_line_check": {}}
        db_manager = Mock()
        return PerformanceTracker(config, db_manager)

    def test_no_drawdown(self, tracker):
        """드로우다운 없음 (계속 상승)"""
        values = [100, 110, 120, 130]
        mdd = tracker._calculate_max_drawdown(values)

        assert mdd == 0.0

    def test_simple_drawdown(self, tracker):
        """단순 드로우다운"""
        values = [100, 120, 90, 100]  # 120에서 90으로 하락 = -25%
        mdd = tracker._calculate_max_drawdown(values)

        assert mdd == pytest.approx(-0.25, rel=0.01)

    def test_multiple_drawdowns(self, tracker):
        """여러 드로우다운 중 최대값"""
        values = [100, 110, 100, 120, 96]  # 120에서 96으로 하락 = -20%
        mdd = tracker._calculate_max_drawdown(values)

        assert mdd == pytest.approx(-0.20, rel=0.01)

    def test_deep_drawdown(self, tracker):
        """큰 드로우다운"""
        values = [100, 150, 75]  # 150에서 75로 하락 = -50%
        mdd = tracker._calculate_max_drawdown(values)

        assert mdd == pytest.approx(-0.50, rel=0.01)


@pytest.mark.monitoring
class TestCalculateWinLossStats:
    """승률 및 손익 통계 계산 테스트"""

    @pytest.fixture
    def tracker(self):
        """PerformanceTracker 인스턴스"""
        config = Mock()
        config.get_risk_config.return_value = {"three_line_check": {}}
        db_manager = Mock()
        return PerformanceTracker(config, db_manager)

    def test_empty_returns(self, tracker):
        """빈 수익률"""
        returns = np.array([])
        win_rate, avg_win, avg_loss = tracker._calculate_win_loss_stats(returns)

        assert win_rate == 0.0
        assert avg_win == 0.0
        assert avg_loss == 0.0

    def test_all_wins(self, tracker):
        """모두 이익"""
        returns = np.array([0.01, 0.02, 0.03, 0.04])
        win_rate, avg_win, avg_loss = tracker._calculate_win_loss_stats(returns)

        assert win_rate == 1.0
        assert avg_win == pytest.approx(0.025, rel=0.01)
        assert avg_loss == 0.0

    def test_all_losses(self, tracker):
        """모두 손실"""
        returns = np.array([-0.01, -0.02, -0.03, -0.04])
        win_rate, avg_win, avg_loss = tracker._calculate_win_loss_stats(returns)

        assert win_rate == 0.0
        assert avg_win == 0.0
        assert avg_loss == pytest.approx(-0.025, rel=0.01)

    def test_mixed_returns(self, tracker):
        """혼합 수익률"""
        returns = np.array([0.05, -0.02, 0.03, -0.01])  # 2 wins, 2 losses
        win_rate, avg_win, avg_loss = tracker._calculate_win_loss_stats(returns)

        assert win_rate == 0.5
        assert avg_win == pytest.approx(0.04, rel=0.01)  # (0.05 + 0.03) / 2
        assert avg_loss == pytest.approx(-0.015, rel=0.01)  # (-0.02 + -0.01) / 2


@pytest.mark.monitoring
class TestCalculateSortinoRatio:
    """소르티노 비율 계산 테스트"""

    @pytest.fixture
    def tracker(self):
        """PerformanceTracker 인스턴스"""
        config = Mock()
        config.get_risk_config.return_value = {"three_line_check": {}}
        db_manager = Mock()
        return PerformanceTracker(config, db_manager)

    def test_no_negative_returns_positive_annualized(self, tracker):
        """음의 수익률 없고 양의 연환산 수익률"""
        returns = np.array([0.01, 0.02, 0.01])
        annualized_return = 0.50

        sortino = tracker._calculate_sortino_ratio(returns, annualized_return)

        assert sortino == float('inf')

    def test_no_negative_returns_zero_annualized(self, tracker):
        """음의 수익률 없고 0 연환산 수익률"""
        returns = np.array([0.01, 0.02, 0.01])
        annualized_return = 0.0

        sortino = tracker._calculate_sortino_ratio(returns, annualized_return)

        assert sortino == 0.0

    def test_with_negative_returns(self, tracker):
        """음의 수익률 포함"""
        returns = np.array([0.02, -0.01, 0.03, -0.02])
        annualized_return = 0.30

        sortino = tracker._calculate_sortino_ratio(returns, annualized_return)

        assert sortino > 0  # 양의 초과수익률


@pytest.mark.monitoring
class TestCreateEmptyMetrics:
    """빈 성과 지표 생성 테스트"""

    @pytest.fixture
    def tracker(self):
        """PerformanceTracker 인스턴스"""
        config = Mock()
        config.get_risk_config.return_value = {"three_line_check": {}}
        db_manager = Mock()
        return PerformanceTracker(config, db_manager)

    def test_create_empty_metrics(self, tracker):
        """빈 지표 생성"""
        metrics = tracker._create_empty_metrics(30)

        assert metrics.period_days == 30
        assert metrics.total_return == 0.0
        assert metrics.annualized_return == 0.0
        assert metrics.volatility == 0.0
        assert metrics.sharpe_ratio == 0.0
        assert metrics.max_drawdown == 0.0
        assert metrics.benchmark_return == 0.0
        assert metrics.tracking_error == 0.0


@pytest.mark.monitoring
class TestCalculateTradeStatistics:
    """거래 통계 계산 테스트"""

    @pytest.fixture
    def tracker(self):
        """PerformanceTracker 인스턴스"""
        config = Mock()
        config.get_risk_config.return_value = {"three_line_check": {}}
        db_manager = Mock()
        return PerformanceTracker(config, db_manager)

    def test_empty_trade_history(self, tracker):
        """빈 거래 내역"""
        stats = tracker._calculate_trade_statistics([])

        assert stats["total_trades"] == 0
        assert stats["successful_trades"] == 0
        assert stats["success_rate"] == 0.0
        assert stats["total_fees"] == 0.0
        assert stats["avg_trade_size"] == 0.0

    def test_all_successful_trades(self, tracker):
        """trade_history 실제 컬럼(fee_krw/amount_krw) 기반 집계 —
        기록되는 거래는 체결분뿐이므로 전 행이 성공 거래"""
        trades = [
            {"side": "buy", "fee_krw": 100, "amount_krw": 10000},
            {"side": "buy", "fee_krw": 150, "amount_krw": 15000},
            {"side": "sell", "fee_krw": 200, "amount_krw": 20000}
        ]

        stats = tracker._calculate_trade_statistics(trades)

        assert stats["total_trades"] == 3
        assert stats["successful_trades"] == 3
        assert stats["success_rate"] == 1.0
        assert stats["total_fees"] == 450
        assert stats["avg_trade_size"] == pytest.approx(15000, rel=0.01)


@pytest.mark.monitoring
class TestGetCurrentAllocation:
    """현재 자산 배분 계산 테스트"""

    @pytest.fixture
    def tracker(self):
        """PerformanceTracker 인스턴스"""
        config = Mock()
        config.get_risk_config.return_value = {"three_line_check": {}}
        db_manager = Mock()
        return PerformanceTracker(config, db_manager)

    def test_empty_portfolio(self, tracker):
        """빈 포트폴리오"""
        allocation = tracker._get_current_allocation({})

        assert allocation is None

    def test_zero_total_value(self, tracker):
        """총 가치 0"""
        snapshot = {"total_value_krw": 0}
        allocation = tracker._get_current_allocation(snapshot)

        assert allocation is None

    def test_krw_only(self, tracker):
        """KRW만 보유 — 자산 상세는 portfolio_detail JSON에서 복원"""
        import json as _json
        snapshot = {
            "total_value_krw": 1000000,
            "portfolio_detail": _json.dumps({"assets": {"KRW": 1000000}}),
        }
        allocation = tracker._get_current_allocation(snapshot)

        assert allocation["KRW"] == 1.0


@pytest.mark.monitoring
class TestAssessRiskLevel:
    """리스크 수준 평가 테스트"""

    @pytest.fixture
    def tracker(self):
        """PerformanceTracker 인스턴스"""
        config = Mock()
        config.get_risk_config.return_value = {"three_line_check": {}}
        db_manager = Mock()
        return PerformanceTracker(config, db_manager)

    def test_low_risk(self, tracker):
        """낮은 리스크"""
        metrics = PerformanceMetrics(
            period_days=30,
            total_return=0.10,
            annualized_return=1.0,
            volatility=0.15,  # 낮은 변동성
            sharpe_ratio=2.0,  # 높은 샤프
            max_drawdown=-0.05,  # 작은 드로우다운
            benchmark_return=0.05,
            tracking_error=0.02
        )

        risk_level = tracker._assess_risk_level(metrics)

        assert risk_level == "low"

    def test_medium_risk(self, tracker):
        """중간 리스크"""
        metrics = PerformanceMetrics(
            period_days=30,
            total_return=0.05,
            annualized_return=0.5,
            volatility=0.22,  # 중간 변동성
            sharpe_ratio=0.8,
            max_drawdown=-0.12,  # 중간 드로우다운
            benchmark_return=0.05,
            tracking_error=0.03
        )

        risk_level = tracker._assess_risk_level(metrics)

        assert risk_level == "medium"

    def test_high_risk(self, tracker):
        """높은 리스크"""
        metrics = PerformanceMetrics(
            period_days=30,
            total_return=-0.15,
            annualized_return=-0.5,
            volatility=0.35,  # 높은 변동성
            sharpe_ratio=-0.5,  # 음의 샤프
            max_drawdown=-0.25,  # 큰 드로우다운
            benchmark_return=0.05,
            tracking_error=0.10
        )

        risk_level = tracker._assess_risk_level(metrics)

        assert risk_level == "high"


@pytest.mark.monitoring
class TestGenerateRecommendations:
    """권장사항 생성 테스트"""

    @pytest.fixture
    def tracker(self):
        """PerformanceTracker 인스턴스"""
        config = Mock()
        config.get_risk_config.return_value = {"three_line_check": {}}
        db_manager = Mock()
        return PerformanceTracker(config, db_manager)

    def test_good_performance_no_issues(self, tracker):
        """양호한 성과"""
        metrics = PerformanceMetrics(
            period_days=30,
            total_return=0.10,
            annualized_return=1.0,
            volatility=0.15,
            sharpe_ratio=2.0,
            max_drawdown=-0.05,
            benchmark_return=0.05,
            tracking_error=0.02
        )

        recommendations = tracker._generate_recommendations(metrics)

        assert len(recommendations) == 1
        assert "안정적" in recommendations[0]

    def test_high_loss_recommendation(self, tracker):
        """큰 손실 권장사항"""
        metrics = PerformanceMetrics(
            period_days=30,
            total_return=-0.15,  # 15% 손실
            annualized_return=-0.5,
            volatility=0.15,
            sharpe_ratio=0.8,
            max_drawdown=-0.05,
            benchmark_return=0.05,
            tracking_error=0.02
        )

        recommendations = tracker._generate_recommendations(metrics)

        assert any("손실" in rec for rec in recommendations)

    def test_high_volatility_recommendation(self, tracker):
        """높은 변동성 권장사항"""
        metrics = PerformanceMetrics(
            period_days=30,
            total_return=0.05,
            annualized_return=0.5,
            volatility=0.30,  # 30% 변동성
            sharpe_ratio=0.8,
            max_drawdown=-0.05,
            benchmark_return=0.05,
            tracking_error=0.02
        )

        recommendations = tracker._generate_recommendations(metrics)

        assert any("변동성" in rec for rec in recommendations)

    def test_high_drawdown_recommendation(self, tracker):
        """큰 드로우다운 권장사항"""
        metrics = PerformanceMetrics(
            period_days=30,
            total_return=0.05,
            annualized_return=0.5,
            volatility=0.15,
            sharpe_ratio=0.8,
            max_drawdown=-0.20,  # 20% 드로우다운
            benchmark_return=0.05,
            tracking_error=0.02
        )

        recommendations = tracker._generate_recommendations(metrics)

        assert any("드로우다운" in rec for rec in recommendations)

    def test_low_sharpe_recommendation(self, tracker):
        """낮은 샤프 비율 권장사항"""
        metrics = PerformanceMetrics(
            period_days=30,
            total_return=0.05,
            annualized_return=0.5,
            volatility=0.15,
            sharpe_ratio=0.3,  # 낮은 샤프
            max_drawdown=-0.05,
            benchmark_return=0.05,
            tracking_error=0.02
        )

        recommendations = tracker._generate_recommendations(metrics)

        assert any("수익률" in rec for rec in recommendations)


@pytest.mark.monitoring
class TestCalculatePerformanceMetrics:
    """성과 지표 계산 통합 테스트"""

    @pytest.fixture
    def mock_db_with_data(self):
        """데이터가 있는 Mock DB"""
        db = Mock()
        db.get_portfolio_history.return_value = [
            {"snapshot_date": (datetime.now() - timedelta(days=25)).isoformat(), "total_value_krw": 1000000},
            {"snapshot_date": (datetime.now() - timedelta(days=20)).isoformat(), "total_value_krw": 1050000},
            {"snapshot_date": (datetime.now() - timedelta(days=15)).isoformat(), "total_value_krw": 1020000},
            {"snapshot_date": (datetime.now() - timedelta(days=10)).isoformat(), "total_value_krw": 1100000},
            {"snapshot_date": (datetime.now() - timedelta(days=5)).isoformat(), "total_value_krw": 1080000},
            {"snapshot_date": datetime.now().isoformat(), "total_value_krw": 1150000}
        ]
        return db

    @pytest.fixture
    def tracker_with_data(self, mock_db_with_data):
        """데이터가 있는 Tracker"""
        config = Mock()
        config.get_risk_config.return_value = {"three_line_check": {}}
        return PerformanceTracker(config, mock_db_with_data)

    def test_calculate_metrics_success(self, tracker_with_data):
        """성과 지표 계산 성공"""
        metrics = tracker_with_data.calculate_performance_metrics(30)

        assert metrics.period_days == 30
        assert metrics.total_return > 0  # 1,000,000 -> 1,150,000
        assert metrics.max_drawdown < 0  # 드로우다운 있음

    def test_insufficient_data(self):
        """데이터 부족"""
        db = Mock()
        db.get_portfolio_history.return_value = [
            {"snapshot_date": datetime.now().isoformat(), "total_value_krw": 1000000}
        ]

        config = Mock()
        config.get_risk_config.return_value = {"three_line_check": {}}
        tracker = PerformanceTracker(config, db)

        metrics = tracker.calculate_performance_metrics(30)

        assert metrics.total_return == 0.0  # 빈 메트릭

    def test_exception_handling(self):
        """예외 처리"""
        db = Mock()
        db.get_portfolio_history.side_effect = Exception("DB error")

        config = Mock()
        config.get_risk_config.return_value = {"three_line_check": {}}
        tracker = PerformanceTracker(config, db)

        metrics = tracker.calculate_performance_metrics(30)

        assert metrics.total_return == 0.0  # 빈 메트릭


@pytest.mark.monitoring
class TestCompareWithBenchmark:
    """벤치마크 비교 테스트"""

    @pytest.fixture
    def tracker_with_data(self):
        """데이터가 있는 Tracker"""
        db = Mock()
        db.get_portfolio_history.return_value = [
            {"snapshot_date": (datetime.now() - timedelta(days=25)).isoformat(), "total_value_krw": 1000000},
            {"snapshot_date": datetime.now().isoformat(), "total_value_krw": 1100000}
        ]

        config = Mock()
        config.get_risk_config.return_value = {"three_line_check": {}}
        return PerformanceTracker(config, db)

    def test_outperformed_benchmark(self, tracker_with_data):
        """벤치마크 초과 수익"""
        comparison = tracker_with_data.compare_with_benchmark(30)

        assert "portfolio_return" in comparison
        assert "benchmark_return" in comparison
        assert "excess_return" in comparison
        assert "outperformed" in comparison

    def test_comparison_with_empty_data(self):
        """데이터 부족 시 비교"""
        db = Mock()
        db.get_portfolio_history.return_value = []

        config = Mock()
        config.get_risk_config.return_value = {"three_line_check": {}}
        tracker = PerformanceTracker(config, db)

        comparison = tracker.compare_with_benchmark(30)

        # 빈 데이터는 0 수익률로 처리
        assert comparison["portfolio_return"] == 0.0
        assert comparison["excess_return"] == 0.0
        assert comparison["outperformed"] is False


@pytest.mark.monitoring
class TestGeneratePerformanceReport:
    """성과 보고서 생성 테스트"""

    @pytest.fixture
    def tracker_with_full_data(self):
        """전체 데이터가 있는 Tracker"""
        db = Mock()
        db.get_portfolio_history.return_value = [
            {"snapshot_date": (datetime.now() - timedelta(days=25)).isoformat(), "total_value_krw": 1000000, "krw_balance": 500000},
            {"snapshot_date": datetime.now().isoformat(), "total_value_krw": 1100000, "krw_balance": 550000}
        ]
        db.get_trade_history.return_value = [
            {"status": "filled", "fee": 100, "amount": 10000},
            {"status": "filled", "fee": 150, "amount": 15000}
        ]

        config = Mock()
        config.get_risk_config.return_value = {"three_line_check": {}}
        return PerformanceTracker(config, db)

    def test_generate_report_success(self, tracker_with_full_data):
        """보고서 생성 성공"""
        report = tracker_with_full_data.generate_performance_report(30)

        assert "report_date" in report
        assert "analysis_period" in report
        assert "performance_metrics" in report
        assert "trading_statistics" in report
        assert "risk_assessment" in report
        assert "recommendations" in report

    def test_generate_report_error(self):
        """보고서 생성 오류"""
        db = Mock()
        db.get_portfolio_history.side_effect = Exception("Error")

        config = Mock()
        config.get_risk_config.return_value = {"three_line_check": {}}
        tracker = PerformanceTracker(config, db)

        report = tracker.generate_performance_report(30)

        assert "error" in report


@pytest.mark.monitoring
class TestSavePerformanceMetrics:
    """성과 지표 저장 테스트"""

    @pytest.fixture
    def tracker(self):
        """PerformanceTracker 인스턴스"""
        config = Mock()
        config.get_risk_config.return_value = {"three_line_check": {}}
        db_manager = Mock()
        return PerformanceTracker(config, db_manager)

    def test_save_metrics_success(self, tracker):
        """지표 저장 성공"""
        metrics = PerformanceMetrics(
            period_days=30,
            total_return=0.10,
            annualized_return=1.0,
            volatility=0.20,
            sharpe_ratio=1.5,
            max_drawdown=-0.10,
            benchmark_return=0.05,
            tracking_error=0.02,
            win_rate=0.6,
            avg_win=0.03,
            avg_loss=-0.02,
            calmar_ratio=10.0,
            sortino_ratio=2.0
        )

        record_id = tracker.save_performance_metrics(metrics)

        assert record_id == 1  # 임시 반환값


@pytest.mark.monitoring
class TestConstants:
    """상수 테스트"""

    def test_default_risk_free_rate(self):
        """기본 무위험 수익률"""
        assert DEFAULT_RISK_FREE_RATE == 0.02

    def test_performance_calculation_periods(self):
        """성과 계산 기간"""
        assert 7 in PERFORMANCE_CALCULATION_PERIODS
        assert 30 in PERFORMANCE_CALCULATION_PERIODS
        assert 90 in PERFORMANCE_CALCULATION_PERIODS
        assert 365 in PERFORMANCE_CALCULATION_PERIODS


@pytest.mark.monitoring
class TestEdgeCases:
    """엣지 케이스 테스트"""

    @pytest.fixture
    def tracker(self):
        """PerformanceTracker 인스턴스"""
        config = Mock()
        config.get_risk_config.return_value = {"three_line_check": {}}
        db_manager = Mock()
        return PerformanceTracker(config, db_manager)

    def test_calculate_returns_two_values(self, tracker):
        """두 개의 값만 있는 경우"""
        values = [100, 110]
        returns = tracker._calculate_returns(values)

        assert len(returns) == 1
        assert returns[0] == pytest.approx(0.10, rel=0.01)

    def test_zero_volatility_sharpe(self, tracker):
        """변동성이 0인 경우 샤프 비율"""
        returns = np.array([0.01, 0.01, 0.01])  # 동일한 수익률
        portfolio_values = [100, 101, 102.01, 103.0301]

        metrics = tracker._calculate_metrics(returns, 30, 0.05, portfolio_values)

        # 변동성이 0에 가까우면 샤프 비율도 처리 필요
        assert isinstance(metrics.sharpe_ratio, float)

    def test_calmar_ratio_zero_drawdown(self, tracker):
        """드로우다운이 0인 경우 칼마 비율"""
        returns = np.array([0.01, 0.02, 0.03])
        portfolio_values = [100, 101, 103.02, 106.11]  # 계속 상승

        metrics = tracker._calculate_metrics(returns, 30, 0.05, portfolio_values)

        # max_drawdown이 0이면 calmar_ratio도 0 또는 무한대 처리
        assert isinstance(metrics.calmar_ratio, float)


@pytest.mark.monitoring
class TestBenchmarkReturnRealData:
    """벤치마크 수익률 — 하드코딩 5% 금지, 실제 BTC 가격 기반 (스펙 fail-loud)"""

    @pytest.fixture
    def tracker_with_binance(self):
        config = Mock()
        config.get_risk_config.return_value = {"three_line_check": {}}
        binance = Mock()
        tracker = PerformanceTracker(config, Mock(), binance_provider=binance)
        return tracker, binance

    def test_benchmark_from_real_btc_prices(self, tracker_with_binance):
        import pandas as pd
        tracker, binance = tracker_with_binance
        binance.get_historical_klines.return_value = pd.DataFrame(
            {"Close": [100.0, 105.0, 120.0]}
        )
        result = tracker._calculate_benchmark_return(
            datetime(2026, 6, 1), datetime(2026, 7, 1)
        )
        assert result == pytest.approx(0.20)

    def test_benchmark_empty_data_raises(self, tracker_with_binance):
        import pandas as pd
        from src.core.exceptions import DataUnavailableError
        tracker, binance = tracker_with_binance
        binance.get_historical_klines.return_value = pd.DataFrame()
        with pytest.raises(DataUnavailableError):
            tracker._calculate_benchmark_return(
                datetime(2026, 6, 1), datetime(2026, 7, 1)
            )


@pytest.mark.monitoring
class TestTradeStatisticsColumns:
    """trade_history 실제 컬럼(side/fee_krw/amount_krw) 사용 — 존재하지 않는
    status/fee/amount 키를 읽어 수수료·평균 거래액이 항상 0이던 버그"""

    @pytest.fixture
    def tracker(self):
        config = Mock()
        config.get_risk_config.return_value = {"three_line_check": {}}
        return PerformanceTracker(config, Mock())

    def test_statistics_from_actual_columns(self, tracker):
        rows = [
            {"side": "buy", "amount_krw": 100_000.0, "fee_krw": 200.0},
            {"side": "sell", "amount_krw": 300_000.0, "fee_krw": None},
        ]
        stats = tracker._calculate_trade_statistics(rows)
        assert stats["total_trades"] == 2
        assert stats["total_fees"] == pytest.approx(200.0)
        assert stats["avg_trade_size"] == pytest.approx(200_000.0)

    def test_returns_skip_corrupt_zero_values(self, tracker):
        """과거 버그로 0이 저장된 스냅샷이 섞여도 inf가 나오면 안 됨"""
        import numpy as np
        returns = tracker._calculate_returns([100.0, 0.0, 110.0])
        assert np.isfinite(returns).all()

    def test_allocation_parsed_from_portfolio_detail_json(self, tracker):
        """스냅샷 자산 배분은 portfolio_detail JSON에서 복원 — 자산별
        컬럼은 현 스키마에 존재하지 않는다"""
        import json as _json
        snapshot = {
            "total_value_krw": 100_000.0,
            "portfolio_detail": _json.dumps({
                "assets": {
                    "KRW": 40_000.0,
                    "BTC": {"balance": 0.001, "value_krw": 60_000.0},
                }
            }),
        }
        allocation = tracker._get_current_allocation(snapshot)
        assert allocation["KRW"] == pytest.approx(0.4)
        assert allocation["BTC"] == pytest.approx(0.6)
