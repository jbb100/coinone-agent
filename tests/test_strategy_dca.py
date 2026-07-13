"""src/strategy/dca.py 테스트 — 주간 DCA 주문 계산."""
import pytest

from src.strategy.dca import DCAOrder, DCAConfig, plan_weekly_dca

CONFIG = DCAConfig(
    base_amount_krw=1_000_000,
    crypto_weights={"BTC": 0.5, "ETH": 0.3, "XRP": 0.1, "SOL": 0.1},
    max_single_dca_krw=5_000_000,
    krw_usage_cap=0.25,        # 스펙 2.2: KRW 잔고의 25% 초과 불가
    min_order_krw=10_000,      # 거래소 최소 주문
)


def test_neutral_multiplier_splits_by_weights():
    orders = plan_weekly_dca(CONFIG, multiplier=1.0, krw_balance=100_000_000)
    assert orders == [
        DCAOrder("BTC", 500_000),
        DCAOrder("ETH", 300_000),
        DCAOrder("XRP", 100_000),
        DCAOrder("SOL", 100_000),
    ]


def test_multiplier_scales_total():
    orders = plan_weekly_dca(CONFIG, multiplier=2.0, krw_balance=100_000_000)
    assert sum(o.amount_krw for o in orders) == pytest.approx(2_000_000)


def test_total_capped_by_max_single_dca():
    cfg = DCAConfig(**{**CONFIG.__dict__, "base_amount_krw": 3_000_000})
    orders = plan_weekly_dca(cfg, multiplier=3.0, krw_balance=1_000_000_000)
    # 3M * 3.0 = 9M → cap 5M
    assert sum(o.amount_krw for o in orders) == pytest.approx(5_000_000)


def test_total_capped_by_krw_usage_cap():
    orders = plan_weekly_dca(CONFIG, multiplier=2.0, krw_balance=4_000_000)
    # 4M * 25% = 1M < 2M
    assert sum(o.amount_krw for o in orders) == pytest.approx(1_000_000)


def test_orders_below_min_are_dropped():
    orders = plan_weekly_dca(CONFIG, multiplier=1.0, krw_balance=200_000)
    # 총액 = 200_000*0.25 = 50_000 → XRP/SOL 몫 5_000 < 10_000 → 제외
    assets = [o.asset for o in orders]
    assert "XRP" not in assets and "SOL" not in assets
    assert "BTC" in assets


def test_zero_balance_returns_empty():
    assert plan_weekly_dca(CONFIG, multiplier=3.0, krw_balance=0) == []


class TestTargetRatioCap:
    """목표 비중 인지형 DCA — 매수 후 크립토 비중이 목표를 넘지 않도록 상한.

    불변식: DCA는 목표 비중 위로 사지 않고, 리밸런서는 목표+밴드 위에서만
    판다 → 같은 포트폴리오 상태에서 매수·매도가 충돌할 수 없다.
    """

    def test_no_buy_when_crypto_at_or_above_target(self):
        # 크립토 64% ≥ 목표 60% → 공포장이어도 매수 없음 (현금 보존)
        orders = plan_weekly_dca(
            CONFIG, multiplier=1.5, krw_balance=36_000_000,
            crypto_value_krw=64_000_000, target_crypto_ratio=0.60,
        )
        assert orders == []

    def test_buy_capped_to_target_headroom(self):
        # 총자산 100M, 크립토 59% → 여유 1M < 계획 2M(2.0x) → 1M으로 상한
        orders = plan_weekly_dca(
            CONFIG, multiplier=2.0, krw_balance=41_000_000,
            crypto_value_krw=59_000_000, target_crypto_ratio=0.60,
        )
        assert sum(o.amount_krw for o in orders) == pytest.approx(1_000_000)

    def test_full_amount_when_ample_headroom(self):
        # 크립토 40% → 여유 20M ≫ 계획 1M → 상한 미적용
        orders = plan_weekly_dca(
            CONFIG, multiplier=1.0, krw_balance=60_000_000,
            crypto_value_krw=40_000_000, target_crypto_ratio=0.60,
        )
        assert sum(o.amount_krw for o in orders) == pytest.approx(1_000_000)

    def test_partial_cap_args_raise(self):
        # fail-loud: 둘 중 하나만 주면 호출 오류
        with pytest.raises(ValueError):
            plan_weekly_dca(
                CONFIG, multiplier=1.0, krw_balance=10_000_000,
                crypto_value_krw=50_000_000,
            )


def test_invalid_weights_raise():
    with pytest.raises(ValueError):
        DCAConfig(
            base_amount_krw=1_000_000,
            crypto_weights={"BTC": 0.5, "ETH": 0.4},  # 합 0.9
            max_single_dca_krw=5_000_000,
            krw_usage_cap=0.25,
            min_order_krw=10_000,
        )
