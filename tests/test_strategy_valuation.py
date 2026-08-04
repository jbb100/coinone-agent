"""src/strategy/valuation.py 테스트 — 역발상 승수·200주MA."""
import pandas as pd
import pytest

from src.strategy.valuation import (
    MarketValuation,
    apply_relative_strength,
    contrarian_crypto_target,
    dca_multiplier,
    fg_multiplier,
    ma_200w,
    relative_weight_factor,
    valuation_multiplier,
)
from src.core.exceptions import InsufficientDataError


class TestFgMultiplier:
    """스펙 2.2: F&G 구간별 승수 — 공포에 많이, 탐욕에 적게"""

    @pytest.mark.parametrize("fg,expected", [
        (0, 2.0), (24, 2.0),      # 극공포
        (25, 1.5), (44, 1.5),     # 공포
        (45, 1.0), (55, 1.0),     # 중립
        (56, 0.7), (74, 0.7),     # 탐욕
        (75, 0.3), (100, 0.3),    # 극탐욕
    ])
    def test_boundaries(self, fg, expected):
        assert fg_multiplier(fg) == expected

    @pytest.mark.parametrize("bad", [-1, 101])
    def test_out_of_range_raises(self, bad):
        with pytest.raises(ValueError):
            fg_multiplier(bad)


class TestValuationMultiplier:
    """스펙 2.2: Mayer ratio(현재가/200주MA) 구간별 승수"""

    @pytest.mark.parametrize("ratio,expected", [
        (0.5, 1.5), (0.99, 1.5),   # 바닥권
        (1.0, 1.0), (1.99, 1.0),   # 적정
        (2.0, 0.7), (2.99, 0.7),   # 확장
        (3.0, 0.5), (5.0, 0.5),    # 과열
    ])
    def test_boundaries(self, ratio, expected):
        assert valuation_multiplier(ratio) == expected

    def test_non_positive_raises(self):
        with pytest.raises(ValueError):
            valuation_multiplier(0.0)


class TestDcaMultiplier:
    def test_extreme_fear_below_ma_is_capped_at_3(self):
        # 2.0 * 1.5 = 3.0 → 상한 3.0
        v = MarketValuation(fear_greed=10, mayer_ratio=0.8)
        assert dca_multiplier(v) == 3.0

    def test_extreme_greed_overheated_is_floored(self):
        # 0.3 * 0.5 = 0.15 → 하한 0.3
        v = MarketValuation(fear_greed=90, mayer_ratio=3.5)
        assert dca_multiplier(v) == 0.3

    def test_neutral_is_1(self):
        v = MarketValuation(fear_greed=50, mayer_ratio=1.5)
        assert dca_multiplier(v) == 1.0


class TestContrarianCryptoTarget:
    """역발상 목표 비중 틸트 — 바닥권에 비중을 올리고 과열에 내린다.

    경계(1.0/2.0/3.0)는 기존 Mayer 밴드 재사용 — 신규 피팅 금지.
    계단식이 아닌 구간 선형 보간: 경계 ±0.1 전이 구간에서 목표가 연속으로
    변해, Mayer가 경계를 오가며 목표가 ±10%p씩 점프하는 절벽 효과
    (예: 1.01→0.99 시 60%→70% 점프 → 수백만 원 왕복 매매)를 제거한다.
    """

    @pytest.mark.parametrize("mayer,expected", [
        (0.3, 0.80), (0.5, 0.80),    # 깊은 바닥: +20%p (피라미드 최심부)
        (0.7, 0.75),                 # 심화 매집: +15%p
        (0.9, 0.70),                 # 바닥권: +10%p
        (1.0, 0.65),                 # 전이 구간: +5%p (절벽 없음)
        (1.1, 0.60), (1.9, 0.60),    # 적정: 기본 유지
        (2.0, 0.55),                 # 전이 구간: -5%p
        (2.1, 0.50), (2.9, 0.50),    # 확장: -10%p
        (3.0, 0.45),                 # 전이 구간: -15%p
        (3.1, 0.40), (5.0, 0.40),    # 과열: -20%p
    ])
    def test_piecewise_linear_tilt(self, mayer, expected):
        assert contrarian_crypto_target(mayer, base_target=0.60) == pytest.approx(expected)

    def test_target_is_monotonically_nonincreasing_in_mayer(self):
        """싸질수록 비중이 낮아지는 일은 없어야 함 (역발상 방향성)"""
        targets = [
            contrarian_crypto_target(m / 100, base_target=0.60)
            for m in range(10, 400, 5)
        ]
        assert all(a >= b for a, b in zip(targets, targets[1:]))

    def test_small_mayer_noise_moves_target_smoothly(self):
        """경계 근처 0.02 노이즈가 목표를 1%p 이상 흔들면 안 됨 (플립플롭 방지)"""
        a = contrarian_crypto_target(0.99, base_target=0.60)
        b = contrarian_crypto_target(1.01, base_target=0.60)
        assert abs(a - b) < 0.011

    def test_offsets_follow_base_target(self):
        assert contrarian_crypto_target(0.5, base_target=0.50) == pytest.approx(0.70)
        assert contrarian_crypto_target(3.5, base_target=0.50) == pytest.approx(0.30)

    def test_clamped_to_valid_ratio(self):
        assert contrarian_crypto_target(0.8, base_target=0.95) == pytest.approx(1.0)
        assert contrarian_crypto_target(4.0, base_target=0.15) == pytest.approx(0.0)

    def test_non_positive_mayer_raises(self):
        with pytest.raises(ValueError):
            contrarian_crypto_target(0.0, base_target=0.60)


class TestRelativeWeightFactor:
    """상대강도 편출 — 진짜 붕괴에만 반응하는 재해 보험.

    구간 선형(틸트와 동일 방식): -50%까지는 유지, -70%에서 0, 사이는 보간.
    2026-08-01 멀티자산 일봉 백테스트에서 기존 -30%~-50% 트리거가 정상
    알트 사이클에도 상시 발동해 회전율 2배·수익 -0.16x를 유발함을 확인,
    트리거를 심화해 LUNA형 구조적 붕괴 전용으로 재조정 (backtest-validation.md)."""

    @pytest.mark.parametrize("rel,factor", [
        (0.5, 1.0), (0.0, 1.0), (-0.3, 1.0),    # 정상 알트 사이클: 미발동
        (-0.5, 1.0),                             # 구 완전편출 지점 → 이제 유지
        (-0.6, 0.5),                             # 전이 구간
        (-0.7, 0.0), (-0.9, 0.0),                # -70% 이하 완전 편출
    ])
    def test_piecewise_linear(self, rel, factor):
        assert relative_weight_factor(rel) == pytest.approx(factor)


class TestApplyRelativeStrength:
    WEIGHTS = {"BTC": 0.5, "ETH": 0.3, "XRP": 0.1, "SOL": 0.1}

    def test_underperformer_weight_moves_to_btc(self):
        # XRP가 BTC 대비 -60% → 가중치 절반(0.05), 빠진 0.05는 BTC로
        out = apply_relative_strength(
            self.WEIGHTS, {"ETH": 0.0, "XRP": -0.6, "SOL": 0.0}
        )
        assert out["XRP"] == pytest.approx(0.05)
        assert out["BTC"] == pytest.approx(0.55)
        assert out["ETH"] == pytest.approx(0.30)
        assert sum(out.values()) == pytest.approx(1.0)

    def test_no_underperformance_keeps_weights(self):
        # -50%까지의 열위는 정상 알트 사이클 범위 — 편출하지 않는다
        out = apply_relative_strength(
            self.WEIGHTS, {"ETH": 0.1, "XRP": -0.5, "SOL": -0.2}
        )
        assert out == pytest.approx(self.WEIGHTS)

    def test_full_demotion_zeroes_weight(self):
        out = apply_relative_strength(
            self.WEIGHTS, {"ETH": 0.0, "XRP": -0.8, "SOL": 0.0}
        )
        assert out["XRP"] == pytest.approx(0.0)
        assert out["BTC"] == pytest.approx(0.60)

    def test_missing_anchor_raises(self):
        with pytest.raises(ValueError):
            apply_relative_strength({"ETH": 1.0}, {"ETH": 0.0})

    def test_missing_relative_return_raises(self):
        # fail-loud: 데이터 누락 시 조용히 1.0 취급 금지
        with pytest.raises(ValueError):
            apply_relative_strength(self.WEIGHTS, {"ETH": 0.0, "XRP": -0.6})


class TestMa200w:
    def test_computes_rolling_mean_of_last_200_weeks(self):
        closes = pd.Series(range(1, 251), dtype=float)  # 250주
        # 마지막 200개 = 51..250 의 평균 = 150.5
        assert ma_200w(closes) == pytest.approx(150.5)

    def test_insufficient_data_raises(self):
        """스펙 fail-loud: 데이터 부족 시 하드코딩 폴백 금지, 예외 발생"""
        with pytest.raises(InsufficientDataError):
            ma_200w(pd.Series(range(199), dtype=float))

    def test_nan_in_window_raises(self):
        closes = pd.Series([float("nan")] + [float(i) for i in range(200)])
        closes.iloc[-1] = float("nan")
        with pytest.raises(InsufficientDataError):
            ma_200w(closes)
