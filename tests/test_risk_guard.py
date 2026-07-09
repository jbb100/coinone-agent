"""src/risk/guard.py 테스트 — 단일 리스크 관문."""
from datetime import datetime, timedelta

import pytest

from src.risk.guard import (
    OrderRequest,
    PortfolioContext,
    RiskGuard,
    RiskLimits,
    ensure_fresh,
)
from src.core.exceptions import DataUnavailableError

LIMITS = RiskLimits(
    max_single_trade_krw=10_000_000,
    max_daily_volume_krw=50_000_000,
    min_krw_ratio=0.10,
    fomo_surge_threshold=0.15,
)


def make_ctx(**kw):
    defaults = dict(
        total_value_krw=100_000_000,
        krw_balance=40_000_000,
        daily_traded_krw=0.0,
        price_change_24h={"BTC": 0.02},
    )
    defaults.update(kw)
    return PortfolioContext(**defaults)


def test_valid_order_passes():
    r = RiskGuard(LIMITS).validate(OrderRequest("BTC", "buy", 1_000_000, "dca"), make_ctx())
    assert r.approved


def test_single_trade_limit_rejects():
    r = RiskGuard(LIMITS).validate(OrderRequest("BTC", "buy", 10_000_001, "dca"), make_ctx())
    assert not r.approved and "단일 거래" in r.reason


def test_daily_volume_limit_rejects():
    ctx = make_ctx(daily_traded_krw=45_000_000)
    r = RiskGuard(LIMITS).validate(OrderRequest("BTC", "buy", 6_000_000, "dca"), ctx)
    assert not r.approved and "일일" in r.reason


def test_buy_breaking_krw_floor_rejects():
    # 매수 후 KRW 10.5M < 총자산 100M의 10%... (11M - 0.5M = 10.5M은 통과,
    # 11M - 1.5M = 9.5M은 거부)
    ctx = make_ctx(krw_balance=11_000_000)
    r = RiskGuard(LIMITS).validate(OrderRequest("BTC", "buy", 1_500_000, "dca"), ctx)
    assert not r.approved and "KRW" in r.reason


def test_sell_never_blocked_by_krw_floor():
    ctx = make_ctx(krw_balance=0)
    r = RiskGuard(LIMITS).validate(OrderRequest("BTC", "sell", 5_000_000, "rebalance"), ctx)
    assert r.approved


def test_fomo_guard_blocks_non_dca_buy_after_surge():
    """스펙 2.3: 24h +15% 급등 자산은 DCA 외 추가 매수 금지"""
    ctx = make_ctx(price_change_24h={"BTC": 0.16})
    r = RiskGuard(LIMITS).validate(
        OrderRequest("BTC", "buy", 1_000_000, "rebalance"), ctx
    )
    assert not r.approved and "급등" in r.reason


def test_fomo_guard_allows_dca_and_sells():
    ctx = make_ctx(price_change_24h={"BTC": 0.20})
    assert RiskGuard(LIMITS).validate(OrderRequest("BTC", "buy", 1_000_000, "dca"), ctx).approved
    assert RiskGuard(LIMITS).validate(OrderRequest("BTC", "sell", 1_000_000, "rebalance"), ctx).approved


def test_ensure_fresh_rejects_stale():
    stale = datetime.now() - timedelta(hours=25)
    with pytest.raises(DataUnavailableError):
        ensure_fresh("fear_greed", stale, max_age_hours=24)


def test_ensure_fresh_accepts_recent():
    ensure_fresh("ticker", datetime.now() - timedelta(hours=1), max_age_hours=24)


def test_ensure_fresh_rejects_none_timestamp():
    with pytest.raises(DataUnavailableError):
        ensure_fresh("ticker", None, max_age_hours=24)
