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
