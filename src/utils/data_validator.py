"""
Data Validator Module

데이터 품질 검증 모듈 (결측치, 갭, 이상치 검사)
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np
from loguru import logger


@dataclass
class DataQualityReport:
    """데이터 품질 리포트"""

    # 결측치 정보
    missing_records: int = 0
    missing_columns: Dict[str, int] = field(default_factory=dict)

    # 갭 정보
    max_gap_days: int = 0
    has_gap: bool = False
    gap_periods: List[tuple] = field(default_factory=list)

    # 이상치 정보
    price_anomalies: int = 0
    volume_anomalies: int = 0
    anomaly_indices: List[int] = field(default_factory=list)

    # 검증 결과
    is_valid: bool = True
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    # 메타데이터
    total_records: int = 0
    validated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "missing_records": self.missing_records,
            "missing_columns": self.missing_columns,
            "max_gap_days": self.max_gap_days,
            "has_gap": self.has_gap,
            "price_anomalies": self.price_anomalies,
            "volume_anomalies": self.volume_anomalies,
            "is_valid": self.is_valid,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
            "total_records": self.total_records,
            "validated_at": self.validated_at.isoformat()
        }


class DataValidator:
    """
    데이터 품질 검증기

    결측치, 데이터 갭, 가격/거래량 이상치를 검사합니다.
    """

    def __init__(
        self,
        max_gap_days: int = 3,
        price_change_threshold: float = 0.5,  # 50%
        volume_spike_threshold: float = 10.0  # 10배
    ):
        """
        Args:
            max_gap_days: 허용 최대 갭 일수
            price_change_threshold: 가격 변동 이상치 임계값 (비율)
            volume_spike_threshold: 거래량 급증 이상치 임계값 (배수)
        """
        self.max_gap_days = max_gap_days
        self.price_change_threshold = price_change_threshold
        self.volume_spike_threshold = volume_spike_threshold

        logger.info("DataValidator 초기화 완료")

    def validate(self, df: pd.DataFrame) -> DataQualityReport:
        """
        데이터 품질 검증

        Args:
            df: 검증할 데이터프레임

        Returns:
            DataQualityReport
        """
        report = DataQualityReport()

        # 빈 데이터프레임 처리
        if df is None or df.empty:
            report.is_valid = False
            report.warnings.append("데이터 없음")
            report.recommendations.append("유효한 데이터를 제공하세요")
            return report

        report.total_records = len(df)

        # 데이터 타입 변환 시도
        df = self._convert_dtypes(df)

        # 1. 결측치 검사
        self._check_missing_values(df, report)

        # 2. 데이터 갭 검사
        self._check_data_gaps(df, report)

        # 3. 가격 이상치 검사
        self._check_price_anomalies(df, report)

        # 4. 거래량 이상치 검사
        self._check_volume_anomalies(df, report)

        # 5. 최종 유효성 판단
        self._determine_validity(report)

        return report

    def clean_and_interpolate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        결측치 보간 및 데이터 정리

        Args:
            df: 정리할 데이터프레임

        Returns:
            정리된 데이터프레임
        """
        if df is None or df.empty:
            return df

        # 복사본 생성
        cleaned = df.copy()

        # 데이터 타입 변환
        cleaned = self._convert_dtypes(cleaned)

        # 결측치 선형 보간
        numeric_cols = cleaned.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            if cleaned[col].isna().any():
                cleaned[col] = cleaned[col].interpolate(method='linear')

        # 남은 결측치 제거 (보간 불가능한 첫/마지막 값)
        cleaned = cleaned.dropna(subset=numeric_cols)

        logger.debug(f"데이터 정리 완료: {len(df)} -> {len(cleaned)} 레코드")
        return cleaned

    def _convert_dtypes(self, df: pd.DataFrame) -> pd.DataFrame:
        """데이터 타입 변환"""
        cleaned = df.copy()

        for col in cleaned.columns:
            if col in ['Close', 'Open', 'High', 'Low', 'Volume']:
                try:
                    cleaned[col] = pd.to_numeric(cleaned[col], errors='coerce')
                except Exception:
                    pass

        return cleaned

    def _check_missing_values(self, df: pd.DataFrame, report: DataQualityReport):
        """결측치 검사"""
        # 각 컬럼별 결측치 수
        for col in df.columns:
            missing_count = df[col].isna().sum()
            if missing_count > 0:
                report.missing_columns[col] = int(missing_count)

        # 전체 결측치 레코드 수 (Close 컬럼 기준)
        if 'Close' in df.columns:
            report.missing_records = int(df['Close'].isna().sum())
        else:
            # Close 컬럼이 없으면 첫 번째 컬럼 기준
            report.missing_records = int(df.iloc[:, 0].isna().sum())

        if report.missing_records > 0:
            report.warnings.append(f"결측치 {report.missing_records}개 발견")
            report.recommendations.append("결측치 보간 또는 제거 권장")

    def _check_data_gaps(self, df: pd.DataFrame, report: DataQualityReport):
        """데이터 갭 검사"""
        # 인덱스가 DatetimeIndex인 경우만 검사
        if not isinstance(df.index, pd.DatetimeIndex):
            return

        if len(df) < 2:
            return

        # 날짜 간격 계산
        date_diffs = df.index.to_series().diff()

        # 1일 이상 갭 찾기
        for i, diff in enumerate(date_diffs):
            if pd.isna(diff):
                continue

            gap_days = diff.days
            if gap_days > 1:
                report.gap_periods.append((
                    df.index[i-1] if i > 0 else df.index[0],
                    df.index[i],
                    gap_days
                ))
                report.max_gap_days = max(report.max_gap_days, gap_days)

        if report.max_gap_days > self.max_gap_days:
            report.has_gap = True
            report.warnings.append(f"데이터 갭 {report.max_gap_days}일 발견")
            report.recommendations.append("누락된 데이터 보충 권장")

    def _check_price_anomalies(self, df: pd.DataFrame, report: DataQualityReport):
        """가격 이상치 검사"""
        if 'Close' not in df.columns:
            return

        prices = df['Close'].dropna()

        if len(prices) < 2:
            return

        # 음수 가격 검사
        negative_count = (prices < 0).sum()
        if negative_count > 0:
            report.price_anomalies += int(negative_count)
            report.warnings.append(f"음수 가격 {negative_count}개 발견")

        # 급등/급락 검사 (전일 대비)
        pct_change = prices.pct_change().abs()
        anomalies = pct_change > self.price_change_threshold

        anomaly_count = int(anomalies.sum())
        if anomaly_count > 0:
            report.price_anomalies += anomaly_count
            report.anomaly_indices.extend(prices.index[anomalies].tolist())
            report.warnings.append(f"가격 급변동 {anomaly_count}건 발견")

    def _check_volume_anomalies(self, df: pd.DataFrame, report: DataQualityReport):
        """거래량 이상치 검사"""
        if 'Volume' not in df.columns:
            return

        volumes = df['Volume'].dropna()

        if len(volumes) < 2:
            return

        # 0 거래량 검사
        zero_count = (volumes == 0).sum()
        if zero_count > 0:
            report.volume_anomalies += int(zero_count)
            report.warnings.append(f"0 거래량 {zero_count}건 발견")

        # 거래량 급증 검사
        avg_volume = volumes.mean()
        if avg_volume > 0:
            spike_threshold = avg_volume * self.volume_spike_threshold
            spikes = volumes > spike_threshold
            spike_count = int(spikes.sum())

            if spike_count > 0:
                report.volume_anomalies += spike_count
                report.warnings.append(f"거래량 급증 {spike_count}건 발견")

    def _determine_validity(self, report: DataQualityReport):
        """최종 유효성 판단"""
        # 유효성 기준
        invalid_conditions = [
            report.missing_records > report.total_records * 0.1,  # 10% 이상 결측치
            report.max_gap_days > self.max_gap_days,  # 허용 갭 초과
            report.price_anomalies > report.total_records * 0.05,  # 5% 이상 가격 이상치
            report.total_records == 0  # 데이터 없음
        ]

        if any(invalid_conditions):
            report.is_valid = False
            report.recommendations.append("데이터 품질 개선 필요")
        else:
            report.is_valid = True
