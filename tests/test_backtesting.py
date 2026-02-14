"""
Tests for Backtesting Improvements - TDD Phase 6

Look-ahead bias 검증, 과적합 경고, Out-of-sample 테스트
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))


# ============================================================================
# TestLookAheadBias - Look-ahead Bias 검증 테스트
# ============================================================================

class TestLookAheadBias:
    """Look-ahead Bias 검증 테스트 클래스"""

    def test_no_future_data_used(self):
        """미래 데이터 사용 없음 검증"""
        from src.backtesting.backtest_validator import BacktestValidator

        validator = BacktestValidator()

        # 정상적인 백테스트 결과 (과거 데이터만 사용)
        trades = [
            {"date": "2024-01-10", "signal_date": "2024-01-09"},
            {"date": "2024-01-15", "signal_date": "2024-01-14"},
            {"date": "2024-01-20", "signal_date": "2024-01-19"},
        ]

        violations = validator.check_lookahead_bias(trades)

        assert len(violations) == 0

    def test_detect_lookahead_bias(self):
        """Look-ahead bias 감지"""
        from src.backtesting.backtest_validator import BacktestValidator

        validator = BacktestValidator()

        # 비정상적인 백테스트 결과 (미래 데이터 사용)
        trades = [
            {"date": "2024-01-10", "signal_date": "2024-01-11"},  # 미래 신호!
            {"date": "2024-01-15", "signal_date": "2024-01-14"},
        ]

        violations = validator.check_lookahead_bias(trades)

        assert len(violations) > 0
        assert "2024-01-10" in str(violations)

    def test_data_availability_check(self):
        """데이터 사용 가능 시점 확인"""
        from src.backtesting.backtest_validator import BacktestValidator

        validator = BacktestValidator()

        # 지표 계산에 필요한 데이터 기간 검증
        config = {
            "start_date": "2024-01-01",
            "lookback_period": 30,  # 30일 룩백
            "data_start_date": "2024-01-01"  # 데이터 시작일이 같음 = 문제
        }

        is_valid, message = validator.validate_data_availability(config)

        assert not is_valid
        assert "lookback" in message.lower() or "데이터" in message


# ============================================================================
# TestOverfittingWarnings - 과적합 경고 테스트
# ============================================================================

class TestOverfittingWarnings:
    """과적합 경고 테스트 클래스"""

    def test_high_sharpe_warning(self):
        """Sharpe > 3.0 경고"""
        from src.backtesting.backtest_validator import BacktestValidator

        validator = BacktestValidator()

        metrics = {
            "sharpe_ratio": 3.5,  # 비현실적으로 높은 Sharpe
            "total_return": 0.50,
            "max_drawdown": 0.05
        }

        warnings = validator.check_overfitting_warnings(metrics)

        assert any("과적합" in w or "Sharpe" in w for w in warnings)

    def test_normal_sharpe_no_warning(self):
        """정상 Sharpe ratio 경고 없음"""
        from src.backtesting.backtest_validator import BacktestValidator

        validator = BacktestValidator()

        metrics = {
            "sharpe_ratio": 1.5,  # 합리적인 Sharpe
            "total_return": 0.20,
            "max_drawdown": 0.10
        }

        warnings = validator.check_overfitting_warnings(metrics)

        # Sharpe 관련 경고 없어야 함
        sharpe_warnings = [w for w in warnings if "Sharpe" in w]
        assert len(sharpe_warnings) == 0

    def test_too_many_params_warning(self):
        """파라미터 5개 초과 경고"""
        from src.backtesting.backtest_validator import BacktestValidator

        validator = BacktestValidator()

        strategy_params = {
            "param1": 1,
            "param2": 2,
            "param3": 3,
            "param4": 4,
            "param5": 5,
            "param6": 6  # 6개 파라미터
        }

        warnings = validator.check_parameter_warnings(strategy_params)

        assert any("파라미터" in w for w in warnings)

    def test_acceptable_params_no_warning(self):
        """적정 파라미터 수 경고 없음"""
        from src.backtesting.backtest_validator import BacktestValidator

        validator = BacktestValidator()

        strategy_params = {
            "param1": 1,
            "param2": 2,
            "param3": 3
        }

        warnings = validator.check_parameter_warnings(strategy_params)

        assert len(warnings) == 0

    def test_unrealistic_win_rate_warning(self):
        """비현실적 승률 경고"""
        from src.backtesting.backtest_validator import BacktestValidator

        validator = BacktestValidator()

        metrics = {
            "sharpe_ratio": 2.0,
            "win_rate": 0.95,  # 95% 승률은 비현실적
            "total_return": 0.80
        }

        warnings = validator.check_overfitting_warnings(metrics)

        assert any("승률" in w or "win" in w.lower() for w in warnings)


# ============================================================================
# TestOutOfSample - Out-of-Sample 테스트
# ============================================================================

class TestOutOfSample:
    """Out-of-Sample 테스트 클래스"""

    def test_oos_performance_comparison(self):
        """In-sample vs Out-of-sample 비교"""
        from src.backtesting.backtest_validator import BacktestValidator

        validator = BacktestValidator()

        in_sample_metrics = {
            "total_return": 0.50,
            "sharpe_ratio": 2.0,
            "max_drawdown": 0.10
        }

        out_of_sample_metrics = {
            "total_return": 0.40,
            "sharpe_ratio": 1.8,
            "max_drawdown": 0.12
        }

        result = validator.compare_is_oos(in_sample_metrics, out_of_sample_metrics)

        assert "in_sample" in result
        assert "out_of_sample" in result
        assert "performance_drop" in result

    def test_oos_overfitting_detection(self):
        """OOS 성능 하락 30% 초과 시 과적합 판정"""
        from src.backtesting.backtest_validator import BacktestValidator

        validator = BacktestValidator()

        in_sample_metrics = {
            "total_return": 0.50,
            "sharpe_ratio": 2.5
        }

        out_of_sample_metrics = {
            "total_return": 0.20,  # 60% 하락
            "sharpe_ratio": 1.0
        }

        result = validator.compare_is_oos(in_sample_metrics, out_of_sample_metrics)

        assert result["is_overfitted"] == True
        assert result["performance_drop"] > 0.30

    def test_oos_acceptable_performance(self):
        """OOS 성능 하락 30% 이내 = 과적합 아님"""
        from src.backtesting.backtest_validator import BacktestValidator

        validator = BacktestValidator()

        in_sample_metrics = {
            "total_return": 0.50,
            "sharpe_ratio": 2.0
        }

        out_of_sample_metrics = {
            "total_return": 0.40,  # 20% 하락
            "sharpe_ratio": 1.6
        }

        result = validator.compare_is_oos(in_sample_metrics, out_of_sample_metrics)

        assert result["is_overfitted"] == False
        assert result["performance_drop"] <= 0.30


# ============================================================================
# TestBacktestValidatorIntegration - 통합 테스트
# ============================================================================

class TestBacktestValidatorIntegration:
    """통합 테스트 클래스"""

    def test_validator_initialization(self):
        """검증기 초기화"""
        from src.backtesting.backtest_validator import BacktestValidator

        validator = BacktestValidator()

        assert validator is not None
        assert hasattr(validator, 'check_lookahead_bias')
        assert hasattr(validator, 'check_overfitting_warnings')
        assert hasattr(validator, 'compare_is_oos')

    def test_full_validation_report(self):
        """전체 검증 리포트 생성"""
        from src.backtesting.backtest_validator import BacktestValidator

        validator = BacktestValidator()

        backtest_result = {
            "trades": [
                {"date": "2024-01-10", "signal_date": "2024-01-09"},
                {"date": "2024-01-15", "signal_date": "2024-01-14"},
            ],
            "metrics": {
                "sharpe_ratio": 1.5,
                "total_return": 0.25,
                "max_drawdown": 0.08,
                "win_rate": 0.55
            },
            "strategy_params": {
                "rsi_period": 14,
                "macd_fast": 12,
                "macd_slow": 26
            }
        }

        report = validator.generate_validation_report(backtest_result)

        assert "lookahead_violations" in report
        assert "overfitting_warnings" in report
        assert "parameter_warnings" in report
        assert "is_valid" in report

    def test_validation_with_issues(self):
        """문제가 있는 백테스트 검증"""
        from src.backtesting.backtest_validator import BacktestValidator

        validator = BacktestValidator()

        # 여러 문제가 있는 백테스트
        backtest_result = {
            "trades": [
                {"date": "2024-01-10", "signal_date": "2024-01-11"},  # 미래 데이터!
            ],
            "metrics": {
                "sharpe_ratio": 4.0,  # 비현실적 Sharpe
                "total_return": 1.0,
                "win_rate": 0.90  # 비현실적 승률
            },
            "strategy_params": {
                "p1": 1, "p2": 2, "p3": 3, "p4": 4,
                "p5": 5, "p6": 6, "p7": 7  # 너무 많은 파라미터
            }
        }

        report = validator.generate_validation_report(backtest_result)

        assert report["is_valid"] == False
        assert len(report["lookahead_violations"]) > 0
        assert len(report["overfitting_warnings"]) > 0
        assert len(report["parameter_warnings"]) > 0


# ============================================================================
# TestBacktestValidatorConfig - 설정 테스트
# ============================================================================

class TestBacktestValidatorConfig:
    """설정 테스트 클래스"""

    def test_custom_thresholds(self):
        """커스텀 임계값 설정"""
        from src.backtesting.backtest_validator import BacktestValidator

        validator = BacktestValidator(
            sharpe_threshold=2.5,
            max_params=10,
            oos_drop_threshold=0.40
        )

        assert validator.sharpe_threshold == 2.5
        assert validator.max_params == 10
        assert validator.oos_drop_threshold == 0.40

    def test_default_thresholds(self):
        """기본 임계값"""
        from src.backtesting.backtest_validator import BacktestValidator

        validator = BacktestValidator()

        assert validator.sharpe_threshold == 3.0
        assert validator.max_params == 5
        assert validator.oos_drop_threshold == 0.30


# ============================================================================
# BacktestingEngine Tests - 백테스팅 엔진 테스트
# ============================================================================

class TestBacktestMode:
    """BacktestMode Enum 테스트"""

    def test_mode_values(self):
        """모드 값 확인"""
        from src.backtesting.backtesting_engine import BacktestMode

        assert BacktestMode.SIMPLE.value == "simple"
        assert BacktestMode.ADVANCED.value == "advanced"
        assert BacktestMode.COMPARISON.value == "comparison"

    def test_mode_count(self):
        """모드 개수 확인"""
        from src.backtesting.backtesting_engine import BacktestMode

        assert len(BacktestMode) == 3


class TestBacktestConfig:
    """BacktestConfig 테스트"""

    def test_basic_config(self):
        """기본 설정 생성"""
        from src.backtesting.backtesting_engine import BacktestConfig, BacktestMode

        config = BacktestConfig(
            start_date="2024-01-01",
            end_date="2024-06-30",
            initial_capital=10000000,
            rebalance_frequency="monthly",
            mode=BacktestMode.SIMPLE
        )

        assert config.start_date == "2024-01-01"
        assert config.end_date == "2024-06-30"
        assert config.initial_capital == 10000000
        assert config.rebalance_frequency == "monthly"
        assert config.mode == BacktestMode.SIMPLE

    def test_default_values(self):
        """기본값 확인"""
        from src.backtesting.backtesting_engine import BacktestConfig, BacktestMode

        config = BacktestConfig(
            start_date="2024-01-01",
            end_date="2024-06-30",
            initial_capital=10000000,
            rebalance_frequency="monthly",
            mode=BacktestMode.SIMPLE
        )

        assert config.risk_level == "moderate"
        assert config.transaction_cost == 0.001
        assert config.slippage == 0.0005
        assert config.use_dynamic_optimization is False
        assert config.max_drawdown_threshold == 0.20

    def test_advanced_config(self):
        """고급 설정"""
        from src.backtesting.backtesting_engine import BacktestConfig, BacktestMode

        config = BacktestConfig(
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=50000000,
            rebalance_frequency="weekly",
            mode=BacktestMode.ADVANCED,
            risk_level="aggressive",
            transaction_cost=0.002,
            slippage=0.001,
            use_dynamic_optimization=True,
            stop_loss=0.05,
            take_profit=0.10
        )

        assert config.risk_level == "aggressive"
        assert config.transaction_cost == 0.002
        assert config.use_dynamic_optimization is True
        assert config.stop_loss == 0.05
        assert config.take_profit == 0.10


class TestTrade:
    """Trade 데이터클래스 테스트"""

    def test_trade_creation(self):
        """거래 기록 생성"""
        from src.backtesting.backtesting_engine import Trade
        from datetime import datetime

        trade = Trade(
            timestamp=datetime(2024, 1, 15),
            asset="BTC",
            side="buy",
            quantity=0.01,
            price=50000000,
            amount_krw=500000,
            fee=500,
            portfolio_value=10000000,
            reason="Rebalance"
        )

        assert trade.asset == "BTC"
        assert trade.side == "buy"
        assert trade.quantity == 0.01
        assert trade.price == 50000000
        assert trade.amount_krw == 500000
        assert trade.fee == 500


class TestPerformanceMetrics:
    """PerformanceMetrics 테스트"""

    def test_metrics_creation(self):
        """성과 지표 생성"""
        from src.backtesting.backtesting_engine import PerformanceMetrics

        metrics = PerformanceMetrics(
            total_return=0.25,
            annualized_return=0.50,
            volatility=0.20,
            sharpe_ratio=1.5,
            max_drawdown=0.15,
            win_rate=0.55,
            profit_factor=1.8,
            total_trades=100,
            winning_trades=55,
            losing_trades=45,
            avg_win=10000,
            avg_loss=8000,
            largest_win=50000,
            largest_loss=30000
        )

        assert metrics.total_return == 0.25
        assert metrics.sharpe_ratio == 1.5
        assert metrics.win_rate == 0.55
        assert metrics.total_trades == 100


class TestBacktestingEngineInit:
    """BacktestingEngine 초기화 테스트"""

    def test_engine_initialization(self):
        """엔진 초기화"""
        from src.backtesting.backtesting_engine import BacktestingEngine, BacktestConfig, BacktestMode

        config = BacktestConfig(
            start_date="2024-01-01",
            end_date="2024-03-31",
            initial_capital=10000000,
            rebalance_frequency="monthly",
            mode=BacktestMode.SIMPLE
        )

        engine = BacktestingEngine(config)

        assert engine.config == config
        assert engine.current_portfolio['total_krw'] == 10000000
        assert engine.current_portfolio['assets']['KRW'] == 10000000
        assert len(engine.trade_history) == 0

    def test_engine_with_historical_data(self):
        """역사적 데이터로 초기화"""
        from src.backtesting.backtesting_engine import BacktestingEngine, BacktestConfig, BacktestMode

        config = BacktestConfig(
            start_date="2024-01-01",
            end_date="2024-03-31",
            initial_capital=10000000,
            rebalance_frequency="monthly",
            mode=BacktestMode.SIMPLE
        )

        historical_data = {
            'BTC': pd.DataFrame({
                'Close': [50000000, 51000000, 52000000],
                'Volume': [1e9, 1.1e9, 1.2e9]
            }, index=pd.date_range('2024-01-01', periods=3))
        }

        engine = BacktestingEngine(config, historical_data)

        assert 'BTC' in engine.historical_data
        assert len(engine.historical_data['BTC']) == 3


class TestBacktestingEngineDataLoading:
    """데이터 로딩 테스트"""

    def test_load_demo_data(self):
        """데모 데이터 로드"""
        from src.backtesting.backtesting_engine import BacktestingEngine, BacktestConfig, BacktestMode

        config = BacktestConfig(
            start_date="2024-01-01",
            end_date="2024-03-31",
            initial_capital=10000000,
            rebalance_frequency="monthly",
            mode=BacktestMode.SIMPLE
        )

        engine = BacktestingEngine(config)
        result = engine.load_historical_data("demo")

        assert result is True
        assert len(engine.historical_data) > 0
        assert 'BTC' in engine.historical_data
        assert 'ETH' in engine.historical_data

    def test_unsupported_data_source(self):
        """지원하지 않는 데이터 소스"""
        from src.backtesting.backtesting_engine import BacktestingEngine, BacktestConfig, BacktestMode

        config = BacktestConfig(
            start_date="2024-01-01",
            end_date="2024-03-31",
            initial_capital=10000000,
            rebalance_frequency="monthly",
            mode=BacktestMode.SIMPLE
        )

        engine = BacktestingEngine(config)
        result = engine.load_historical_data("unsupported_source")

        assert result is False


class TestRebalanceDates:
    """리밸런싱 날짜 테스트"""

    def test_daily_rebalance(self):
        """일별 리밸런싱"""
        from src.backtesting.backtesting_engine import BacktestingEngine, BacktestConfig, BacktestMode

        config = BacktestConfig(
            start_date="2024-01-01",
            end_date="2024-01-10",
            initial_capital=10000000,
            rebalance_frequency="daily",
            mode=BacktestMode.SIMPLE
        )

        engine = BacktestingEngine(config)
        dates = engine._get_rebalance_dates(
            pd.to_datetime("2024-01-01"),
            pd.to_datetime("2024-01-10")
        )

        assert len(dates) == 10

    def test_weekly_rebalance(self):
        """주별 리밸런싱"""
        from src.backtesting.backtesting_engine import BacktestingEngine, BacktestConfig, BacktestMode

        config = BacktestConfig(
            start_date="2024-01-01",
            end_date="2024-02-29",
            initial_capital=10000000,
            rebalance_frequency="weekly",
            mode=BacktestMode.SIMPLE
        )

        engine = BacktestingEngine(config)
        dates = engine._get_rebalance_dates(
            pd.to_datetime("2024-01-01"),
            pd.to_datetime("2024-02-29")
        )

        # 약 8-9주
        assert 8 <= len(dates) <= 10

    def test_monthly_rebalance(self):
        """월별 리밸런싱"""
        from src.backtesting.backtesting_engine import BacktestingEngine, BacktestConfig, BacktestMode

        config = BacktestConfig(
            start_date="2024-01-01",
            end_date="2024-06-30",
            initial_capital=10000000,
            rebalance_frequency="monthly",
            mode=BacktestMode.SIMPLE
        )

        engine = BacktestingEngine(config)
        dates = engine._get_rebalance_dates(
            pd.to_datetime("2024-01-01"),
            pd.to_datetime("2024-06-30")
        )

        assert len(dates) == 6


class TestPortfolioOperations:
    """포트폴리오 연산 테스트"""

    def test_update_portfolio_value(self):
        """포트폴리오 가치 업데이트"""
        from src.backtesting.backtesting_engine import BacktestingEngine, BacktestConfig, BacktestMode

        config = BacktestConfig(
            start_date="2024-01-01",
            end_date="2024-03-31",
            initial_capital=10000000,
            rebalance_frequency="monthly",
            mode=BacktestMode.SIMPLE
        )

        engine = BacktestingEngine(config)

        # 수동으로 포트폴리오 설정
        engine.current_portfolio = {
            'total_krw': 10000000,
            'assets': {'KRW': 5000000, 'BTC': 0.1}
        }

        prices = {'BTC': 50000000}  # 0.1 BTC = 5,000,000 KRW

        engine._update_portfolio_value(prices)

        assert engine.current_portfolio['total_krw'] == 10000000  # 5M KRW + 5M BTC

    def test_get_daily_prices(self):
        """일별 가격 조회"""
        from src.backtesting.backtesting_engine import BacktestingEngine, BacktestConfig, BacktestMode

        config = BacktestConfig(
            start_date="2024-01-01",
            end_date="2024-03-31",
            initial_capital=10000000,
            rebalance_frequency="monthly",
            mode=BacktestMode.SIMPLE
        )

        historical_data = {
            'BTC': pd.DataFrame({
                'Close': [50000000, 51000000, 52000000],
                'Volume': [1e9, 1.1e9, 1.2e9]
            }, index=pd.date_range('2024-01-01', periods=3))
        }

        engine = BacktestingEngine(config, historical_data)
        prices = engine._get_daily_prices(pd.to_datetime('2024-01-02'))

        assert 'BTC' in prices
        assert prices['BTC'] == 51000000


class TestBacktestExecution:
    """백테스트 실행 테스트"""

    def test_run_backtest_with_demo_data(self):
        """데모 데이터로 백테스트 실행"""
        from src.backtesting.backtesting_engine import BacktestingEngine, BacktestConfig, BacktestMode

        config = BacktestConfig(
            start_date="2024-01-01",
            end_date="2024-03-31",
            initial_capital=10000000,
            rebalance_frequency="monthly",
            mode=BacktestMode.SIMPLE
        )

        engine = BacktestingEngine(config)
        engine.load_historical_data("demo")

        result = engine.run_backtest(calculate_benchmarks=False)

        assert result is not None
        assert hasattr(result, 'total_return')
        assert hasattr(result, 'sharpe_ratio')
        assert hasattr(result, 'max_drawdown')

    def test_run_backtest_no_data(self):
        """데이터 없이 백테스트 실행 시 오류"""
        from src.backtesting.backtesting_engine import BacktestingEngine, BacktestConfig, BacktestMode

        config = BacktestConfig(
            start_date="2024-01-01",
            end_date="2024-03-31",
            initial_capital=10000000,
            rebalance_frequency="monthly",
            mode=BacktestMode.SIMPLE
        )

        engine = BacktestingEngine(config)

        with pytest.raises(ValueError, match="역사적 데이터"):
            engine.run_backtest()


class TestMarketSeasonDetermination:
    """시장 계절 판단 테스트"""

    def test_risk_on_season(self):
        """상승장 (Risk On) 판단"""
        from src.backtesting.backtesting_engine import BacktestingEngine, BacktestConfig, BacktestMode
        from src.core.market_season_filter import MarketSeason

        config = BacktestConfig(
            start_date="2024-01-01",
            end_date="2024-03-31",
            initial_capital=10000000,
            rebalance_frequency="monthly",
            mode=BacktestMode.SIMPLE
        )

        # 상승 추세 데이터 생성
        dates = pd.date_range('2023-12-01', periods=60)
        prices = [50000000 * (1 + 0.01 * i) for i in range(60)]  # 지속 상승

        historical_data = {
            'BTC': pd.DataFrame({
                'Close': prices,
                'Volume': [1e9] * 60
            }, index=dates)
        }

        engine = BacktestingEngine(config, historical_data)
        season = engine._determine_market_season(pd.to_datetime('2024-01-15'))

        assert season == MarketSeason.RISK_ON

    def test_risk_off_season(self):
        """하락장 (Risk Off) 판단"""
        from src.backtesting.backtesting_engine import BacktestingEngine, BacktestConfig, BacktestMode
        from src.core.market_season_filter import MarketSeason

        config = BacktestConfig(
            start_date="2024-01-01",
            end_date="2024-03-31",
            initial_capital=10000000,
            rebalance_frequency="monthly",
            mode=BacktestMode.SIMPLE
        )

        # 하락 추세 데이터 생성
        dates = pd.date_range('2023-12-01', periods=60)
        prices = [50000000 * (1 - 0.01 * i) for i in range(60)]  # 지속 하락

        historical_data = {
            'BTC': pd.DataFrame({
                'Close': prices,
                'Volume': [1e9] * 60
            }, index=dates)
        }

        engine = BacktestingEngine(config, historical_data)
        season = engine._determine_market_season(pd.to_datetime('2024-01-15'))

        assert season == MarketSeason.RISK_OFF


class TestHistoryRetrieval:
    """히스토리 조회 테스트"""

    def test_get_portfolio_history(self):
        """포트폴리오 히스토리 조회"""
        from src.backtesting.backtesting_engine import BacktestingEngine, BacktestConfig, BacktestMode

        config = BacktestConfig(
            start_date="2024-01-01",
            end_date="2024-01-31",
            initial_capital=10000000,
            rebalance_frequency="weekly",
            mode=BacktestMode.SIMPLE
        )

        engine = BacktestingEngine(config)
        engine.load_historical_data("demo")
        engine.run_backtest(calculate_benchmarks=False)

        history = engine.get_portfolio_history()

        assert isinstance(history, pd.DataFrame)
        assert 'date' in history.columns
        assert 'total_value' in history.columns
        assert len(history) > 0

    def test_get_trade_history(self):
        """거래 히스토리 조회"""
        from src.backtesting.backtesting_engine import BacktestingEngine, BacktestConfig, BacktestMode

        config = BacktestConfig(
            start_date="2024-01-01",
            end_date="2024-02-29",
            initial_capital=10000000,
            rebalance_frequency="weekly",
            mode=BacktestMode.SIMPLE
        )

        engine = BacktestingEngine(config)
        engine.load_historical_data("demo")
        engine.run_backtest(calculate_benchmarks=False)

        trades = engine.get_trade_history()

        assert isinstance(trades, pd.DataFrame)

    def test_empty_trade_history(self):
        """빈 거래 히스토리"""
        from src.backtesting.backtesting_engine import BacktestingEngine, BacktestConfig, BacktestMode

        config = BacktestConfig(
            start_date="2024-01-01",
            end_date="2024-03-31",
            initial_capital=10000000,
            rebalance_frequency="monthly",
            mode=BacktestMode.SIMPLE
        )

        engine = BacktestingEngine(config)
        trades = engine.get_trade_history()

        assert isinstance(trades, pd.DataFrame)
        assert len(trades) == 0


class TestRiskLevelStrategies:
    """리스크 수준별 전략 테스트"""

    def test_conservative_strategy(self):
        """보수적 전략"""
        from src.backtesting.backtesting_engine import BacktestingEngine, BacktestConfig, BacktestMode

        config = BacktestConfig(
            start_date="2024-01-01",
            end_date="2024-02-29",
            initial_capital=10000000,
            rebalance_frequency="monthly",
            mode=BacktestMode.SIMPLE,
            risk_level="conservative"
        )

        engine = BacktestingEngine(config)
        engine.load_historical_data("demo")
        result = engine.run_backtest(calculate_benchmarks=False)

        # 보수적 전략은 낮은 변동성을 목표로 함
        assert result is not None

    def test_aggressive_strategy(self):
        """공격적 전략"""
        from src.backtesting.backtesting_engine import BacktestingEngine, BacktestConfig, BacktestMode

        config = BacktestConfig(
            start_date="2024-01-01",
            end_date="2024-02-29",
            initial_capital=10000000,
            rebalance_frequency="monthly",
            mode=BacktestMode.SIMPLE,
            risk_level="aggressive"
        )

        engine = BacktestingEngine(config)
        engine.load_historical_data("demo")
        result = engine.run_backtest(calculate_benchmarks=False)

        assert result is not None


class TestBenchmarkCalculation:
    """벤치마크 계산 테스트"""

    def test_buy_and_hold_benchmarks(self):
        """Buy-and-Hold 벤치마크 계산"""
        from src.backtesting.backtesting_engine import BacktestingEngine, BacktestConfig, BacktestMode

        config = BacktestConfig(
            start_date="2024-01-01",
            end_date="2024-02-29",
            initial_capital=10000000,
            rebalance_frequency="monthly",
            mode=BacktestMode.SIMPLE
        )

        engine = BacktestingEngine(config)
        engine.load_historical_data("demo")
        engine.run_backtest(calculate_benchmarks=True)

        assert hasattr(engine, 'benchmarks')
        assert 'BTC' in engine.benchmarks
        assert 'total_return' in engine.benchmarks['BTC']
        assert 'annualized_return' in engine.benchmarks['BTC']


class TestTransactionCosts:
    """거래 비용 테스트"""

    def test_high_transaction_costs(self):
        """높은 거래 비용"""
        from src.backtesting.backtesting_engine import BacktestingEngine, BacktestConfig, BacktestMode

        config = BacktestConfig(
            start_date="2024-01-01",
            end_date="2024-02-29",
            initial_capital=10000000,
            rebalance_frequency="weekly",
            mode=BacktestMode.SIMPLE,
            transaction_cost=0.01,  # 1%
            slippage=0.005  # 0.5%
        )

        engine = BacktestingEngine(config)
        engine.load_historical_data("demo")
        result = engine.run_backtest(calculate_benchmarks=False)

        # 높은 거래 비용은 수익률에 영향
        assert result is not None

    def test_zero_transaction_costs(self):
        """거래 비용 없음"""
        from src.backtesting.backtesting_engine import BacktestingEngine, BacktestConfig, BacktestMode

        config = BacktestConfig(
            start_date="2024-01-01",
            end_date="2024-02-29",
            initial_capital=10000000,
            rebalance_frequency="weekly",
            mode=BacktestMode.SIMPLE,
            transaction_cost=0.0,
            slippage=0.0
        )

        engine = BacktestingEngine(config)
        engine.load_historical_data("demo")
        result = engine.run_backtest(calculate_benchmarks=False)

        assert result is not None
