"""
MarketValuationFilter (Phase 2) 테스트

가치 앵커 모델: 저평가(R<1.0)에 최대 매집, 고평가(R>=2.8)에 최대 분배.
경계 히스테리시스와 비중 단계 이동, fail-safe 동작을 검증한다.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.market_valuation_filter import (
    MarketValuationFilter,
    ValuationPhase,
    phase_from_string,
)


class TestPhaseDetermination:
    def setup_method(self):
        self.f = MarketValuationFilter()

    def test_deep_value_below_ma(self):
        """200주 MA 아래 = 사이클 바닥권 = 최대 매집 (기존 legacy와 정반대)"""
        assert self.f.determine_phase(0.85) == ValuationPhase.DEEP_VALUE

    def test_accumulation(self):
        assert self.f.determine_phase(1.2) == ValuationPhase.ACCUMULATION

    def test_neutral(self):
        assert self.f.determine_phase(1.7) == ValuationPhase.NEUTRAL

    def test_distribution(self):
        assert self.f.determine_phase(2.3) == ValuationPhase.DISTRIBUTION

    def test_euphoria(self):
        assert self.f.determine_phase(3.5) == ValuationPhase.EUPHORIA

    def test_invalid_ratio_keeps_previous(self):
        assert self.f.determine_phase(None, ValuationPhase.NEUTRAL) == ValuationPhase.NEUTRAL
        assert self.f.determine_phase(-1, ValuationPhase.ACCUMULATION) == ValuationPhase.ACCUMULATION

    def test_invalid_ratio_without_previous_is_none(self):
        assert self.f.determine_phase(None) is None


class TestHysteresis:
    def setup_method(self):
        self.f = MarketValuationFilter(hysteresis=0.05)

    def test_upward_move_requires_full_break(self):
        """ACCUMULATION(경계 1.4)에서 R=1.42로는 NEUTRAL 전환 안 됨 (1.4×1.05=1.47 필요)"""
        phase = self.f.determine_phase(1.42, ValuationPhase.ACCUMULATION)
        assert phase == ValuationPhase.ACCUMULATION

    def test_upward_move_with_full_break(self):
        phase = self.f.determine_phase(1.48, ValuationPhase.ACCUMULATION)
        assert phase == ValuationPhase.NEUTRAL

    def test_downward_move_requires_full_break(self):
        """NEUTRAL에서 R=1.38로는 ACCUMULATION 전환 안 됨 (1.4×0.95=1.33 필요)"""
        phase = self.f.determine_phase(1.38, ValuationPhase.NEUTRAL)
        assert phase == ValuationPhase.NEUTRAL

    def test_downward_move_with_full_break(self):
        phase = self.f.determine_phase(1.30, ValuationPhase.NEUTRAL)
        assert phase == ValuationPhase.ACCUMULATION

    def test_no_whipsaw_around_boundary(self):
        """경계를 오르내려도 확실히 돌파하기 전에는 국면이 흔들리지 않음"""
        phase = ValuationPhase.ACCUMULATION
        for r in [1.41, 1.39, 1.43, 1.38, 1.44]:
            phase = self.f.determine_phase(r, phase)
            assert phase == ValuationPhase.ACCUMULATION

    def test_multi_phase_jump_allowed_when_clear(self):
        """급락으로 R이 명확히 낮으면 여러 단계 이동 허용"""
        phase = self.f.determine_phase(0.80, ValuationPhase.NEUTRAL)
        assert phase == ValuationPhase.DEEP_VALUE


class TestAllocation:
    def setup_method(self):
        self.f = MarketValuationFilter(max_allocation_step=0.10)

    def test_bear_market_accumulates(self):
        """저평가 국면일수록 crypto 목표 비중이 높아야 함 (하락장 매집)"""
        w = {p: self.f.get_target_crypto_weight(p) for p in ValuationPhase}
        assert w[ValuationPhase.DEEP_VALUE] > w[ValuationPhase.ACCUMULATION] \
               > w[ValuationPhase.NEUTRAL] > w[ValuationPhase.DISTRIBUTION] \
               > w[ValuationPhase.EUPHORIA]
        assert w[ValuationPhase.DEEP_VALUE] == pytest.approx(0.75)
        assert w[ValuationPhase.EUPHORIA] == pytest.approx(0.25)

    def test_step_limits_swing(self):
        """50% → 75% 목표라도 회당 10%p만 이동"""
        assert self.f.step_allocation(0.50, 0.75) == pytest.approx(0.60)

    def test_step_downward(self):
        assert self.f.step_allocation(0.70, 0.25) == pytest.approx(0.60)

    def test_step_within_limit_reaches_target(self):
        assert self.f.step_allocation(0.50, 0.55) == pytest.approx(0.55)

    def test_step_without_current_uses_target(self):
        assert self.f.step_allocation(None, 0.75) == pytest.approx(0.75)


class TestAnalyze:
    def setup_method(self):
        self.f = MarketValuationFilter()

    def test_analyze_success(self):
        result = self.f.analyze(
            current_price=90_000_000,
            ma_200w=100_000_000,   # R = 0.9 → DEEP_VALUE
            current_crypto_weight=0.50,
        )
        assert result["success"] is True
        assert result["valuation_phase"] == "deep_value"
        assert result["final_target_crypto_weight"] == pytest.approx(0.75)
        # 단계 이동: 50% → 60% (회당 10%p 제한)
        assert result["allocation_weights"]["crypto"] == pytest.approx(0.60)

    def test_analyze_fails_without_data(self):
        """실데이터 없으면 판단하지 않음 (fail-safe)"""
        result = self.f.analyze(current_price=None, ma_200w=100_000_000)
        assert result["success"] is False
        assert "allocation_weights" not in result

        result = self.f.analyze(current_price=90_000_000, ma_200w=0)
        assert result["success"] is False

    def test_analyze_euphoria_distributes(self):
        result = self.f.analyze(
            current_price=300_000_000,
            ma_200w=100_000_000,   # R = 3.0 → EUPHORIA
            current_crypto_weight=0.70,
        )
        assert result["success"] is True
        assert result["valuation_phase"] == "euphoria"
        assert result["final_target_crypto_weight"] == pytest.approx(0.25)
        assert result["allocation_weights"]["crypto"] == pytest.approx(0.60)  # 70% - 10%p


class TestPhaseFromString:
    def test_valid(self):
        assert phase_from_string("deep_value") == ValuationPhase.DEEP_VALUE
        assert phase_from_string("EUPHORIA") == ValuationPhase.EUPHORIA

    def test_invalid(self):
        assert phase_from_string(None) is None
        assert phase_from_string("risk_on") is None  # legacy 계절 문자열은 국면이 아님


class TestConfigValidation:
    def test_invalid_boundary_count(self):
        with pytest.raises(ValueError):
            MarketValuationFilter(boundaries=[1.0, 2.0])

    def test_unsorted_boundaries(self):
        with pytest.raises(ValueError):
            MarketValuationFilter(boundaries=[1.4, 1.0, 2.0, 2.8])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
