"""
Market Valuation Filter (Phase 2)

200주 이동평균을 "추세 이탈 매도선"이 아닌 "가치 앵커"로 사용하는 국면 모델.

핵심 철학: 하락장(저평가)에 매집하고, 상승장(고평가)에 분배한다.
  R = BTC 현재가 / 200주 이동평균

| 국면          | 조건 (R)      | 목표 crypto 비중 |
|---------------|---------------|------------------|
| DEEP_VALUE    | R < 1.0       | 75% (최대 매집)  |
| ACCUMULATION  | 1.0 ≤ R < 1.4 | 65%              |
| NEUTRAL       | 1.4 ≤ R < 2.0 | 50%              |
| DISTRIBUTION  | 2.0 ≤ R < 2.8 | 35%              |
| EUPHORIA      | R ≥ 2.8       | 25% (최대 분배)  |

안전장치:
- 경계 ±5% 히스테리시스: 직전 국면에서 경계를 확실히 돌파해야 전환 (휩쏘 방지)
- 국면 전환 시 목표 비중으로 한 번에 점프하지 않고 회당 최대 10%p씩 이동
- R 계산 불가(실데이터 없음) 시 판단하지 않음 (None 반환 — fail-safe)

이 모델은 config의 strategy.regime_model = "valuation" 일 때만 사용된다
(기본값 "legacy"는 기존 MarketSeasonFilter 유지 — 백테스트 검증 후 전환).
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple

from loguru import logger


class ValuationPhase(Enum):
    """가치 기반 시장 국면 (저평가 → 고평가 순)"""
    DEEP_VALUE = "deep_value"        # 사이클 바닥권 — 최대 매집
    ACCUMULATION = "accumulation"    # 저평가 — 적극 매집
    NEUTRAL = "neutral"              # 중립
    DISTRIBUTION = "distribution"    # 고평가 — 단계적 분배
    EUPHORIA = "euphoria"            # 과열 — 최대 분배


# 국면 순서 (인덱스가 클수록 고평가)
PHASE_ORDER: List[ValuationPhase] = [
    ValuationPhase.DEEP_VALUE,
    ValuationPhase.ACCUMULATION,
    ValuationPhase.NEUTRAL,
    ValuationPhase.DISTRIBUTION,
    ValuationPhase.EUPHORIA,
]

DEFAULT_BOUNDARIES = [1.0, 1.4, 2.0, 2.8]  # R 기준 국면 경계

DEFAULT_ALLOCATIONS = {
    ValuationPhase.DEEP_VALUE: 0.75,
    ValuationPhase.ACCUMULATION: 0.65,
    ValuationPhase.NEUTRAL: 0.50,
    ValuationPhase.DISTRIBUTION: 0.35,
    ValuationPhase.EUPHORIA: 0.25,
}


def phase_from_string(value: Optional[str]) -> Optional[ValuationPhase]:
    """저장된 문자열을 ValuationPhase로 변환 (알 수 없으면 None)"""
    if not value:
        return None
    try:
        return ValuationPhase(str(value).lower())
    except ValueError:
        return None


class MarketValuationFilter:
    """
    가치 기반 시장 국면 필터

    200주 MA 대비 가격 비율(R)로 저평가/고평가 국면을 판단하고,
    "저평가에 매집, 고평가에 분배" 방향의 목표 crypto 비중을 산출한다.
    """

    def __init__(
        self,
        boundaries: Optional[List[float]] = None,
        allocations: Optional[Dict[ValuationPhase, float]] = None,
        hysteresis: float = 0.05,
        max_allocation_step: float = 0.10,
    ):
        """
        Args:
            boundaries: R 기준 국면 경계 4개 (오름차순)
            allocations: 국면별 목표 crypto 비중
            hysteresis: 경계 히스테리시스 비율 (±5%)
            max_allocation_step: 회당 최대 비중 이동폭 (10%p)
        """
        self.boundaries = boundaries or list(DEFAULT_BOUNDARIES)
        self.allocations = allocations or dict(DEFAULT_ALLOCATIONS)
        self.hysteresis = hysteresis
        self.max_allocation_step = max_allocation_step

        if len(self.boundaries) != len(PHASE_ORDER) - 1:
            raise ValueError(f"경계는 {len(PHASE_ORDER) - 1}개여야 합니다: {self.boundaries}")
        if sorted(self.boundaries) != self.boundaries:
            raise ValueError(f"경계는 오름차순이어야 합니다: {self.boundaries}")

        logger.info(f"MarketValuationFilter 초기화: 경계={self.boundaries}, "
                    f"히스테리시스=±{hysteresis:.0%}, 최대 이동폭={max_allocation_step:.0%}p")

    def _raw_phase_index(self, ratio: float) -> int:
        """히스테리시스 없이 R값이 속하는 국면 인덱스"""
        for i, boundary in enumerate(self.boundaries):
            if ratio < boundary:
                return i
        return len(self.boundaries)

    def determine_phase(
        self,
        ratio: Optional[float],
        previous_phase: Optional[ValuationPhase] = None,
    ) -> Optional[ValuationPhase]:
        """
        시장 국면 판단 (경계 히스테리시스 적용)

        국면을 올리려면(고평가 방향) 진입 경계 × (1+h)를 넘어야 하고,
        내리려면(저평가 방향) 진입 경계 × (1-h) 아래로 내려가야 한다.
        경계 부근에서는 직전 국면을 유지해 휩쏘를 방지한다.

        Args:
            ratio: R = 현재가 / 200주 MA (None이면 판단 불가)
            previous_phase: 직전 국면

        Returns:
            판단된 국면, 또는 None (ratio가 유효하지 않고 직전 국면도 없음)
        """
        if ratio is None or ratio <= 0:
            logger.error(f"국면 판단 불가 (잘못된 R값: {ratio}) — "
                         f"{'직전 국면 유지' if previous_phase else '판단 불가'}")
            return previous_phase  # 직전 국면 유지 (없으면 None)

        raw_idx = self._raw_phase_index(ratio)

        if previous_phase is None:
            return PHASE_ORDER[raw_idx]

        prev_idx = PHASE_ORDER.index(previous_phase)

        if raw_idx == prev_idx:
            return previous_phase

        if raw_idx > prev_idx:
            # 고평가 방향 이동: 최종 진입 경계를 (1+h) 이상 확실히 돌파해야 함
            entry_boundary = self.boundaries[raw_idx - 1]
            if ratio >= entry_boundary * (1 + self.hysteresis):
                new_idx = raw_idx
            else:
                # 경계 부근 — 한 단계 아래까지만 인정 (직전보다 낮아지지는 않음)
                new_idx = max(prev_idx, raw_idx - 1)
        else:
            # 저평가 방향 이동: 진입 경계를 (1-h) 이하로 확실히 이탈해야 함
            entry_boundary = self.boundaries[raw_idx]
            if ratio <= entry_boundary * (1 - self.hysteresis):
                new_idx = raw_idx
            else:
                new_idx = min(prev_idx, raw_idx + 1)

        new_phase = PHASE_ORDER[new_idx]
        if new_phase != previous_phase:
            logger.info(f"시장 국면 전환: {previous_phase.value} → {new_phase.value} (R={ratio:.3f})")
        return new_phase

    def get_target_crypto_weight(self, phase: ValuationPhase) -> float:
        """국면별 목표 crypto 비중"""
        return self.allocations[phase]

    def step_allocation(
        self,
        current_crypto_weight: Optional[float],
        target_crypto_weight: float,
    ) -> float:
        """
        비중 단계 이동: 현재 비중에서 목표 방향으로 회당 최대 max_allocation_step만큼만 이동

        국면 전환 시 일괄 매매(40%p 스윙)를 방지한다.
        현재 비중을 모르면(최초 실행) 목표 비중을 그대로 사용한다.
        """
        if current_crypto_weight is None:
            return target_crypto_weight

        diff = target_crypto_weight - current_crypto_weight
        step = max(-self.max_allocation_step, min(self.max_allocation_step, diff))
        next_weight = current_crypto_weight + step

        if abs(diff) > self.max_allocation_step:
            logger.info(f"비중 단계 이동: {current_crypto_weight:.1%} → {next_weight:.1%} "
                        f"(최종 목표 {target_crypto_weight:.1%}, 회당 {self.max_allocation_step:.0%}p 제한)")
        return next_weight

    def analyze(
        self,
        current_price: Optional[float],
        ma_200w: Optional[float],
        previous_phase: Optional[ValuationPhase] = None,
        current_crypto_weight: Optional[float] = None,
    ) -> Dict:
        """
        국면 분석 및 목표 배분 산출 (단일 진입점)

        Args:
            current_price: BTC 현재가 (KRW)
            ma_200w: 200주 이동평균 (KRW)
            previous_phase: 직전 국면 (DB에서 조회해 전달)
            current_crypto_weight: 현재 crypto 비중 (단계 이동용)

        Returns:
            분석 결과 딕셔너리 (success=False면 거래 판단에 사용 금지)
        """
        if (current_price is None or ma_200w is None
                or current_price <= 0 or ma_200w <= 0):
            logger.error(f"가치 국면 분석 불가: price={current_price}, ma_200w={ma_200w}")
            return {
                "success": False,
                "error": "가격/200주 MA 데이터 없음 — 판단 중단",
                "analysis_date": datetime.now(),
            }

        ratio = current_price / ma_200w
        phase = self.determine_phase(ratio, previous_phase)

        if phase is None:
            return {
                "success": False,
                "error": "국면 판단 불가",
                "analysis_date": datetime.now(),
            }

        final_target = self.get_target_crypto_weight(phase)
        stepped_target = self.step_allocation(current_crypto_weight, final_target)

        result = {
            "success": True,
            "analysis_date": datetime.now(),
            "valuation_phase": phase.value,
            "price_ratio": ratio,
            "current_price": current_price,
            "ma_200w": ma_200w,
            "final_target_crypto_weight": final_target,
            "allocation_weights": {
                "crypto": stepped_target,
                "krw": 1.0 - stepped_target,
            },
            "phase_changed": (previous_phase is not None and phase != previous_phase),
            "boundaries": list(self.boundaries),
        }

        logger.info(f"가치 국면 분석: {phase.value} (R={ratio:.3f}) → "
                    f"crypto 목표 {stepped_target:.1%} (최종 목표 {final_target:.1%})")
        return result
