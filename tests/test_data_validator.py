"""
Tests for Data Validator Module - TDD Phase 5

데이터 품질 검증 (결측치, 갭, 이상치) 테스트
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))


# ============================================================================
# TestMissingData - 결측치 검사 테스트
# ============================================================================

class TestMissingData:
    """결측치 검사 테스트 클래스"""

    def test_detect_missing_values(self):
        """결측치 감지"""
        from src.utils.data_validator import DataValidator

        validator = DataValidator()
        df = pd.DataFrame({
            "Close": [100, None, 102, None, 104],
            "Volume": [1000, 1000, 1000, 1000, 1000]
        })

        report = validator.validate(df)

        assert report.missing_records == 2
        assert report.missing_columns["Close"] == 2

    def test_no_missing_values(self):
        """결측치 없음"""
        from src.utils.data_validator import DataValidator

        validator = DataValidator()
        df = pd.DataFrame({
            "Close": [100, 101, 102, 103, 104],
            "Volume": [1000, 1000, 1000, 1000, 1000]
        })

        report = validator.validate(df)

        assert report.missing_records == 0

    def test_interpolate_missing(self):
        """결측치 보간"""
        from src.utils.data_validator import DataValidator

        validator = DataValidator()
        df = pd.DataFrame({
            "Close": [100.0, None, 104.0],
            "Volume": [1000, 1000, 1000]
        })

        cleaned = validator.clean_and_interpolate(df)

        assert cleaned["Close"].iloc[1] == 102.0  # 선형 보간

    def test_interpolate_multiple_missing(self):
        """여러 결측치 보간"""
        from src.utils.data_validator import DataValidator

        validator = DataValidator()
        df = pd.DataFrame({
            "Close": [100.0, None, None, 106.0],
            "Volume": [1000, 1000, 1000, 1000]
        })

        cleaned = validator.clean_and_interpolate(df)

        assert cleaned["Close"].iloc[1] == 102.0
        assert cleaned["Close"].iloc[2] == 104.0


# ============================================================================
# TestDataGaps - 데이터 갭 검사 테스트
# ============================================================================

class TestDataGaps:
    """데이터 갭 검사 테스트 클래스"""

    def test_detect_gap(self):
        """데이터 갭 감지"""
        from src.utils.data_validator import DataValidator

        validator = DataValidator()

        # 5일 이상 갭 데이터 생성
        dates = pd.date_range("2024-01-01", periods=10, freq="D").tolist()
        # 중간에 제거 (indices 3-7 제거하면 6일 갭 발생)
        dates = dates[:3] + dates[8:]

        df = pd.DataFrame({
            "Date": dates,
            "Close": [100] * len(dates),
            "Volume": [1000] * len(dates)
        })
        df.set_index("Date", inplace=True)

        report = validator.validate(df)

        assert report.max_gap_days >= 5  # 5일 이상 갭
        assert "데이터 갭" in str(report.warnings) or report.has_gap

    def test_acceptable_gap(self):
        """허용 범위 내 갭 (3일 이하)"""
        from src.utils.data_validator import DataValidator

        validator = DataValidator()

        # 2일 갭 데이터 생성
        dates = pd.date_range("2024-01-01", periods=10, freq="D").tolist()
        dates = dates[:3] + dates[5:]  # 2일 갭

        df = pd.DataFrame({
            "Date": dates,
            "Close": [100] * len(dates),
            "Volume": [1000] * len(dates)
        })
        df.set_index("Date", inplace=True)

        report = validator.validate(df)

        assert report.max_gap_days <= 3
        assert report.is_valid or report.max_gap_days <= 3

    def test_no_gap(self):
        """갭 없음"""
        from src.utils.data_validator import DataValidator

        validator = DataValidator()

        dates = pd.date_range("2024-01-01", periods=10, freq="D")
        df = pd.DataFrame({
            "Date": dates,
            "Close": [100] * 10,
            "Volume": [1000] * 10
        })
        df.set_index("Date", inplace=True)

        report = validator.validate(df)

        assert report.max_gap_days <= 1


# ============================================================================
# TestAnomalies - 이상치 검사 테스트
# ============================================================================

class TestAnomalies:
    """이상치 검사 테스트 클래스"""

    def test_price_anomaly_spike(self):
        """가격 이상치 감지 (50% 급등)"""
        from src.utils.data_validator import DataValidator

        validator = DataValidator()
        df = pd.DataFrame({
            "Close": [100, 100, 160, 100],  # 60% 급등
            "Volume": [1000, 1000, 1000, 1000]
        })

        report = validator.validate(df)

        assert report.price_anomalies > 0

    def test_price_anomaly_crash(self):
        """가격 이상치 감지 (50% 급락)"""
        from src.utils.data_validator import DataValidator

        validator = DataValidator()
        df = pd.DataFrame({
            "Close": [100, 100, 40, 100],  # 60% 급락
            "Volume": [1000, 1000, 1000, 1000]
        })

        report = validator.validate(df)

        assert report.price_anomalies > 0

    def test_no_price_anomaly(self):
        """정상 가격 변동 (이상치 없음)"""
        from src.utils.data_validator import DataValidator

        validator = DataValidator()
        df = pd.DataFrame({
            "Close": [100, 102, 101, 103, 102],  # 정상 변동
            "Volume": [1000, 1000, 1000, 1000, 1000]
        })

        report = validator.validate(df)

        assert report.price_anomalies == 0

    def test_volume_anomaly_zero(self):
        """거래량 이상치 감지 (0 거래량)"""
        from src.utils.data_validator import DataValidator

        validator = DataValidator()
        df = pd.DataFrame({
            "Close": [100, 100, 100, 100, 100],
            "Volume": [1000, 0, 1000, 0, 1000]
        })

        report = validator.validate(df)

        assert report.volume_anomalies == 2

    def test_volume_anomaly_spike(self):
        """거래량 이상치 감지 (100배 급증)"""
        from src.utils.data_validator import DataValidator

        # 더 낮은 임계값으로 테스트 (5배)
        validator = DataValidator(volume_spike_threshold=5)
        df = pd.DataFrame({
            "Close": [100] * 10,
            "Volume": [1000, 1000, 1000, 100000, 1000, 1000, 1000, 1000, 1000, 1000]
        })

        report = validator.validate(df)

        assert report.volume_anomalies >= 1


# ============================================================================
# TestDataQualityReport - 품질 리포트 테스트
# ============================================================================

class TestDataQualityReport:
    """데이터 품질 리포트 테스트 클래스"""

    def test_valid_data(self):
        """정상 데이터 검증 통과"""
        from src.utils.data_validator import DataValidator

        validator = DataValidator()

        dates = pd.date_range("2024-01-01", periods=30, freq="D")
        df = pd.DataFrame({
            "Date": dates,
            "Close": [100 + i * 0.5 for i in range(30)],
            "Volume": [1000] * 30
        })
        df.set_index("Date", inplace=True)

        report = validator.validate(df)

        assert report.is_valid

    def test_invalid_data(self):
        """불량 데이터 검증 실패"""
        from src.utils.data_validator import DataValidator

        validator = DataValidator()
        df = pd.DataFrame({
            "Close": [100, None, None, None, 200],  # 많은 결측치 + 급등
            "Volume": [1000, 0, 0, 0, 1000]  # 0 거래량
        })

        report = validator.validate(df)

        assert not report.is_valid
        assert len(report.recommendations) > 0

    def test_report_contains_summary(self):
        """리포트에 요약 정보 포함"""
        from src.utils.data_validator import DataValidator

        validator = DataValidator()
        df = pd.DataFrame({
            "Close": [100, 101, 102, 103, 104],
            "Volume": [1000, 1000, 1000, 1000, 1000]
        })

        report = validator.validate(df)

        assert hasattr(report, "missing_records")
        assert hasattr(report, "price_anomalies")
        assert hasattr(report, "volume_anomalies")
        assert hasattr(report, "is_valid")
        assert hasattr(report, "recommendations")

    def test_report_to_dict(self):
        """리포트를 딕셔너리로 변환"""
        from src.utils.data_validator import DataValidator

        validator = DataValidator()
        df = pd.DataFrame({
            "Close": [100, 101, 102],
            "Volume": [1000, 1000, 1000]
        })

        report = validator.validate(df)
        report_dict = report.to_dict()

        assert isinstance(report_dict, dict)
        assert "missing_records" in report_dict
        assert "is_valid" in report_dict


# ============================================================================
# TestDataValidatorEdgeCases - 엣지 케이스 테스트
# ============================================================================

class TestDataValidatorEdgeCases:
    """엣지 케이스 테스트 클래스"""

    def test_empty_dataframe(self):
        """빈 데이터프레임 처리"""
        from src.utils.data_validator import DataValidator

        validator = DataValidator()
        df = pd.DataFrame()

        report = validator.validate(df)

        assert not report.is_valid
        assert "데이터 없음" in str(report.warnings) or len(report.recommendations) > 0

    def test_single_row(self):
        """단일 행 데이터 처리"""
        from src.utils.data_validator import DataValidator

        validator = DataValidator()
        df = pd.DataFrame({
            "Close": [100],
            "Volume": [1000]
        })

        report = validator.validate(df)

        # 단일 행도 처리 가능해야 함
        assert report is not None

    def test_all_nan(self):
        """모든 값이 NaN인 경우"""
        from src.utils.data_validator import DataValidator

        validator = DataValidator()
        df = pd.DataFrame({
            "Close": [None, None, None],
            "Volume": [None, None, None]
        })

        report = validator.validate(df)

        assert not report.is_valid
        assert report.missing_records == 3

    def test_negative_prices(self):
        """음수 가격 감지"""
        from src.utils.data_validator import DataValidator

        validator = DataValidator()
        df = pd.DataFrame({
            "Close": [100, -50, 100],  # 음수 가격
            "Volume": [1000, 1000, 1000]
        })

        report = validator.validate(df)

        assert report.price_anomalies > 0 or not report.is_valid

    def test_mixed_dtypes(self):
        """혼합 데이터 타입 처리"""
        from src.utils.data_validator import DataValidator

        validator = DataValidator()
        df = pd.DataFrame({
            "Close": ["100", 101, 102],  # 문자열 혼합
            "Volume": [1000, 1000, 1000]
        })

        # 에러 없이 처리되어야 함
        report = validator.validate(df)
        assert report is not None


# ============================================================================
# TestDataValidatorConfig - 설정 테스트
# ============================================================================

class TestDataValidatorConfig:
    """설정 테스트 클래스"""

    def test_custom_thresholds(self):
        """커스텀 임계값 설정"""
        from src.utils.data_validator import DataValidator

        validator = DataValidator(
            max_gap_days=5,
            price_change_threshold=0.3,  # 30%
            volume_spike_threshold=50  # 50배
        )

        assert validator.max_gap_days == 5
        assert validator.price_change_threshold == 0.3
        assert validator.volume_spike_threshold == 50

    def test_default_thresholds(self):
        """기본 임계값"""
        from src.utils.data_validator import DataValidator

        validator = DataValidator()

        assert validator.max_gap_days == 3
        assert validator.price_change_threshold == 0.5  # 50%
