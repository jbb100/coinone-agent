"""src/strategy/rebalance.py 테스트 — 밴드 리밸런싱 (상승 익절·하락 매집)."""
import pytest

from src.strategy.rebalance import (
    RebalanceConfig,
    RebalanceOrder,
    apply_crash_guard,
    plan_rebalance,
)

CONFIG = RebalanceConfig(
    crypto_target=0.60,
    band_pp=0.05,               # 총 크립토 비중 ±5%p
    crypto_weights={"BTC": 0.5, "ETH": 0.3, "XRP": 0.1, "SOL": 0.1},
    relative_band=0.20,         # 코인별 상대 ±20%
    min_trade_krw=10_000,
)


def test_within_band_no_orders():
    # 크립토 62% (밴드 55~65% 내) → 거래 없음
    holdings = {"BTC": 31_000_000, "ETH": 18_600_000, "XRP": 6_200_000, "SOL": 6_200_000}
    assert plan_rebalance(CONFIG, holdings, krw_balance=38_000_000) == []


def test_bull_market_overweight_sells_back_to_target():
    """상승장: 크립토 70% > 65% → 목표 60%까지 매도 (자동 익절)"""
    holdings = {"BTC": 35_000_000, "ETH": 21_000_000, "XRP": 7_000_000, "SOL": 7_000_000}
    orders = plan_rebalance(CONFIG, holdings, krw_balance=30_000_000)
    sells = [o for o in orders if o.side == "sell"]
    assert sells, "상승장 초과분은 매도되어야 함"
    total_sell = sum(o.amount_krw for o in sells)
    assert total_sell == pytest.approx(10_000_000)  # 70% → 60% of 100M


def test_bear_market_underweight_buys_back_to_target():
    """하락장: 크립토 50% < 55% → 목표 60%까지 매수 (자동 저가 매집)"""
    holdings = {"BTC": 25_000_000, "ETH": 15_000_000, "XRP": 5_000_000, "SOL": 5_000_000}
    orders = plan_rebalance(CONFIG, holdings, krw_balance=50_000_000)
    buys = [o for o in orders if o.side == "buy"]
    assert buys, "하락장 미달분은 매수되어야 함"
    assert sum(o.amount_krw for o in buys) == pytest.approx(10_000_000)


def test_trades_split_toward_per_asset_targets():
    """거래 후 개별 코인도 크립토 내 목표 비중에 수렴해야 함"""
    # BTC만 급등해 크립토 내 비중 왜곡 + 총비중 초과
    holdings = {"BTC": 50_000_000, "ETH": 12_000_000, "XRP": 4_000_000, "SOL": 4_000_000}
    orders = plan_rebalance(CONFIG, holdings, krw_balance=30_000_000)
    by_asset = {o.asset: o for o in orders}
    # 총 100M, 목표 크립토 60M → BTC 목표 30M: 20M 매도
    assert by_asset["BTC"].side == "sell"
    assert by_asset["BTC"].amount_krw == pytest.approx(20_000_000)
    # ETH 목표 18M: 6M 매수
    assert by_asset["ETH"].side == "buy"
    assert by_asset["ETH"].amount_krw == pytest.approx(6_000_000)


def test_per_asset_drift_triggers_even_when_total_in_band():
    """총비중은 밴드 내지만 개별 코인이 상대 ±20% 초과 이탈하면 내부 리밸런싱"""
    # 크립토 총 60M(=60%), 그러나 BTC 42M(내부 70% vs 목표 50%, 상대 +40%)
    holdings = {"BTC": 42_000_000, "ETH": 10_000_000, "XRP": 4_000_000, "SOL": 4_000_000}
    orders = plan_rebalance(CONFIG, holdings, krw_balance=40_000_000)
    by_asset = {o.asset: o for o in orders}
    assert by_asset["BTC"].side == "sell"
    buys = sum(o.amount_krw for o in orders if o.side == "buy")
    sells = sum(o.amount_krw for o in orders if o.side == "sell")
    assert buys == pytest.approx(sells)  # 내부 재배분: 총 크립토 불변


def test_dust_trades_dropped():
    holdings = {"BTC": 30_000_000, "ETH": 18_000_000, "XRP": 6_000_000, "SOL": 6_005_000}
    orders = plan_rebalance(CONFIG, holdings, krw_balance=40_000_000)
    assert all(o.amount_krw >= CONFIG.min_trade_krw for o in orders)


def test_empty_portfolio_no_orders():
    assert plan_rebalance(CONFIG, {}, krw_balance=0) == []


class TestCrashGuard:
    """급락 시 분할 진입 — FOMO 가드(급등 매수 금지)의 대칭 리스크 컨트롤.

    24h -10% 이상 급락한 자산의 리밸런싱 매수는 절반만 집행하고, 나머지는
    다음날 체크가 (여전히 밴드 이탈이면) 마저 산다 — 낙하는 칼날을 하루에
    다 받지 않는 시간 분산."""

    def test_crash_buy_is_scaled_down(self):
        orders = [RebalanceOrder("BTC", "buy", 1_000_000)]
        out = apply_crash_guard(
            orders, {"BTC": -0.12},
            threshold=-0.10, buy_fraction=0.5, min_trade_krw=10_000,
        )
        assert out == [RebalanceOrder("BTC", "buy", 500_000)]

    def test_normal_dip_buy_unchanged(self):
        orders = [RebalanceOrder("BTC", "buy", 1_000_000)]
        out = apply_crash_guard(
            orders, {"BTC": -0.05},
            threshold=-0.10, buy_fraction=0.5, min_trade_krw=10_000,
        )
        assert out == orders

    def test_sell_never_scaled(self):
        # 매도(익절)는 급락과 무관하게 전량 — 가드는 매수 진입만 분산
        orders = [RebalanceOrder("ETH", "sell", 1_000_000)]
        out = apply_crash_guard(
            orders, {"ETH": -0.20},
            threshold=-0.10, buy_fraction=0.5, min_trade_krw=10_000,
        )
        assert out == orders

    def test_scaled_below_min_trade_dropped(self):
        orders = [RebalanceOrder("XRP", "buy", 15_000)]
        out = apply_crash_guard(
            orders, {"XRP": -0.15},
            threshold=-0.10, buy_fraction=0.5, min_trade_krw=10_000,
        )
        assert out == []  # 7,500 < 최소 주문 → 제외


def test_fully_demoted_asset_triggers_own_sell():
    """가중치 0으로 완전 편출된 자산은 스스로 리밸런싱을 트리거해야 함 —
    'target_w > 0' 가드 때문에 다른 이탈이 생길 때까지 잔여 포지션이
    무기한 방치되던 버그 회귀 방지"""
    config = RebalanceConfig(
        crypto_target=0.60, band_pp=0.05,
        crypto_weights={"BTC": 0.6, "ETH": 0.3, "XRP": 0.1, "SOL": 0.0},
        relative_band=0.20, min_trade_krw=10_000,
    )
    # 크립토 60M (총 100M의 60%, 밴드 내), SOL만 목표 0인데 6M 보유
    holdings = {"BTC": 30_000_000, "ETH": 18_000_000,
                "XRP": 6_000_000, "SOL": 6_000_000}
    orders = plan_rebalance(config, holdings, krw_balance=40_000_000)
    by_asset = {o.asset: o for o in orders}
    assert by_asset["SOL"].side == "sell"
    assert by_asset["SOL"].amount_krw == pytest.approx(6_000_000)


def test_fully_demoted_dust_below_min_trade_ignored():
    """편출 자산 잔여물이 최소 거래액 미만이면 트리거하지 않음 (먼지 방치 OK)"""
    config = RebalanceConfig(
        crypto_target=0.60, band_pp=0.05,
        crypto_weights={"BTC": 0.6, "ETH": 0.3, "XRP": 0.1, "SOL": 0.0},
        relative_band=0.20, min_trade_krw=10_000,
    )
    holdings = {"BTC": 30_000_000, "ETH": 18_000_000,
                "XRP": 6_000_000, "SOL": 5_000}
    assert plan_rebalance(config, holdings, krw_balance=35_995_000) == []
