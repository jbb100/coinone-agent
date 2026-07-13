"""시장 밸류에이션 순수 함수.

철학: 싸질수록(공포·200주MA 아래) 승수를 키우고,
비싸질수록(탐욕·MA 대비 과열) 승수를 줄인다.
"""
from dataclasses import dataclass
from typing import Dict

import numpy as np
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


# 구간 선형 보간 앵커 — Mayer 밴드 경계(1.0/2.0/3.0) ±0.1 전이 구간.
# 계단식 대신 연속 함수: 경계에서 목표가 ±10%p 점프하는 절벽 효과
# (Mayer 노이즈 → 대규모 왕복 매매)를 제거한다.
# 매수측 피라미드: 바닥이 깊어질수록 목표를 더 올린다 (0.9→+10%p,
# 0.7→+15%p, 0.5→+20%p). 57개 시작점 검증에서 MDD·Sharpe 동일,
# 수익만 개선 — 폭락장 매집을 밸류에이션(Mayer)에 앵커한 피라미드.
_TILT_MAYER_ANCHORS = (0.5, 0.7, 0.9, 1.1, 1.9, 2.1, 2.9, 3.1)
_TILT_OFFSET_ANCHORS = (+0.20, +0.15, +0.10, 0.0, 0.0, -0.10, -0.10, -0.20)


def contrarian_crypto_target(mayer_ratio: float, base_target: float) -> float:
    """역발상 목표 비중: 바닥권(MA 아래)에 비중을 올리고 과열에 내린다.

    DCA 승수는 포트폴리오 대비 주간 매수액이 작아 효과가 2차적이므로,
    역발상 레버를 자산배분(리밸런싱 목표)에 직접 건다.
    구간 선형 보간(경계 ±0.1)이라 목표가 Mayer에 연속으로 반응 — 경계
    노이즈가 대규모 거래를 유발하지 않는다. 앵커는 기존 Mayer 밴드 재사용.
    """
    if mayer_ratio <= 0:
        raise ValueError(f"Mayer ratio는 양수여야 함: {mayer_ratio}")
    offset = float(
        np.interp(mayer_ratio, _TILT_MAYER_ANCHORS, _TILT_OFFSET_ANCHORS)
    )
    return min(1.0, max(0.0, base_target + offset))


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


# 상대강도 편출 앵커 — 26주 BTC 대비 상대수익 기준 구간 선형.
# -30%까지는 유지, -50%에서 완전 편출. 연속 함수라 경계 노이즈가
# 급격한 편출입 매매를 만들지 않는다 (틸트와 동일한 설계 원칙).
_RS_REL_ANCHORS = (-0.5, -0.3)
_RS_FACTOR_ANCHORS = (0.0, 1.0)


def relative_weight_factor(rel_return: float) -> float:
    """BTC 대비 상대수익 → 목표 가중치 유지 비율 (0~1)."""
    return float(np.interp(rel_return, _RS_REL_ANCHORS, _RS_FACTOR_ANCHORS))


def apply_relative_strength(
    weights: Dict[str, float],
    rel_returns: Dict[str, float],
    anchor: str = "BTC",
) -> Dict[str, float]:
    """장기 열위 알트의 목표 가중치를 연속 감축하고, 감축분을 앵커(BTC)로.

    "싸질수록 산다"는 사이클 자산에만 유효하다 — BTC 대비 구조적으로
    우하향하는 알트를 목표 비중대로 계속 사주는 것을 막는 편출 규칙.
    가중치 합은 항상 보존된다.
    """
    if anchor not in weights:
        raise ValueError(f"앵커 자산 {anchor}이 가중치에 없음: {weights}")
    missing = [a for a in weights if a != anchor and a not in rel_returns]
    if missing:
        raise ValueError(f"상대수익 데이터 누락: {missing}")
    out = {}
    freed = 0.0
    for asset, weight in weights.items():
        if asset == anchor:
            continue
        factor = relative_weight_factor(rel_returns[asset])
        out[asset] = weight * factor
        freed += weight * (1.0 - factor)
    out[anchor] = weights[anchor] + freed
    return out
