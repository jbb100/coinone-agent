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
