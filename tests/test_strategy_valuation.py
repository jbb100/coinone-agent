"""src/strategy/valuation.py 테스트 — 역발상 승수·200주MA."""
import pandas as pd
import pytest

from src.strategy.valuation import (
    MarketValuation,
    contrarian_crypto_target,
    dca_multiplier,
    fg_multiplier,
    ma_200w,
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

    465주 32개 시작점 스윕에서 고정 0.60 대비 전 구간 동등 이상 검증
    (평균 1.69x→1.77x, 최악 MDD -50.5%→-46.9%, Sharpe 1.78→1.83).
    밴드 경계는 기존 Mayer 밴드(1.0/2.0/3.0) 재사용 — 신규 피팅 금지.
    """

    @pytest.mark.parametrize("mayer,expected", [
        (0.5, 0.70), (0.99, 0.70),   # 바닥권: +10%p
        (1.0, 0.60), (1.99, 0.60),   # 적정: 기본 유지
        (2.0, 0.50), (2.99, 0.50),   # 확장: -10%p
        (3.0, 0.40), (5.0, 0.40),    # 과열: -20%p
    ])
    def test_boundaries_with_default_base(self, mayer, expected):
        assert contrarian_crypto_target(mayer, base_target=0.60) == pytest.approx(expected)

    def test_offsets_follow_base_target(self):
        assert contrarian_crypto_target(0.8, base_target=0.50) == pytest.approx(0.60)
        assert contrarian_crypto_target(3.5, base_target=0.50) == pytest.approx(0.30)

    def test_clamped_to_valid_ratio(self):
        assert contrarian_crypto_target(0.8, base_target=0.95) == pytest.approx(1.0)
        assert contrarian_crypto_target(4.0, base_target=0.15) == pytest.approx(0.0)

    def test_non_positive_mayer_raises(self):
        with pytest.raises(ValueError):
            contrarian_crypto_target(0.0, base_target=0.60)


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
