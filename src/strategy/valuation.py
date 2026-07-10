"""시장 밸류에이션 순수 함수.

철학: 싸질수록(공포·200주MA 아래) 승수를 키우고,
비싸질수록(탐욕·MA 대비 과열) 승수를 줄인다.
"""
from dataclasses import dataclass

import pandas as pd

from src.core.exceptions import InsufficientDataError

MIN_WEEKS = 200
MULTIPLIER_FLOOR = 0.3
MULTIPLIER_CAP = 3.0

# (상한 경계, 승수) — 경계는 "이하"
_FG_BANDS = [(24, 2.0), (44, 1.5), (55, 1.0), (74, 0.7), (100, 0.3)]
# (상한 경계, 승수) — 경계는 "미만"
_MAYER_BANDS = [(1.0, 1.5), (2.0, 1.0), (3.0, 0.7)]
_MAYER_OVERHEATED = 0.5


@dataclass(frozen=True)
class MarketValuation:
    fear_greed: int      # 0-100
    mayer_ratio: float   # 현재가 / 200주MA


def fg_multiplier(fear_greed: int) -> float:
    if not 0 <= fear_greed <= 100:
        raise ValueError(f"Fear&Greed 범위 오류: {fear_greed}")
    for upper, mult in _FG_BANDS:
        if fear_greed <= upper:
            return mult
    raise AssertionError("unreachable")


def valuation_multiplier(mayer_ratio: float) -> float:
    if mayer_ratio <= 0:
        raise ValueError(f"Mayer ratio는 양수여야 함: {mayer_ratio}")
    for upper, mult in _MAYER_BANDS:
        if mayer_ratio < upper:
            return mult
    return _MAYER_OVERHEATED


def dca_multiplier(valuation: MarketValuation) -> float:
    raw = fg_multiplier(valuation.fear_greed) * valuation_multiplier(valuation.mayer_ratio)
    return max(MULTIPLIER_FLOOR, min(MULTIPLIER_CAP, raw))


# (상한 경계, 기본 목표 대비 오프셋) — 경계는 "미만", Mayer 밴드와 동일 경계
_TARGET_TILT_BANDS = [(1.0, +0.10), (2.0, 0.0), (3.0, -0.10)]
_TARGET_TILT_OVERHEATED = -0.20


def contrarian_crypto_target(mayer_ratio: float, base_target: float) -> float:
    """역발상 목표 비중: 바닥권(MA 아래)에 비중을 올리고 과열에 내린다.

    DCA 승수는 포트폴리오 대비 주간 매수액이 작아 효과가 2차적이므로,
    역발상 레버를 자산배분(리밸런싱 목표)에 직접 건다.
    465주 32개 시작점 스윕에서 고정 목표 대비 전 구간 동등 이상 검증됨.
    """
    if mayer_ratio <= 0:
        raise ValueError(f"Mayer ratio는 양수여야 함: {mayer_ratio}")
    for upper, offset in _TARGET_TILT_BANDS:
        if mayer_ratio < upper:
            return min(1.0, max(0.0, base_target + offset))
    return min(1.0, max(0.0, base_target + _TARGET_TILT_OVERHEATED))


def ma_200w(weekly_closes: pd.Series) -> float:
    valid = weekly_closes.dropna()
    if len(valid) < MIN_WEEKS:
        raise InsufficientDataError(
            f"200주MA 계산 불가: 유효 주봉 {len(valid)}개 < {MIN_WEEKS}개"
        )
    window = weekly_closes.iloc[-MIN_WEEKS:]
    if window.isna().any():
        raise InsufficientDataError("200주MA 윈도우에 NaN 포함 — 데이터 오염")
    return float(window.mean())
