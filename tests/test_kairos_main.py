"""kairos1_main.py 테스트 — KAIROS-Simple 오케스트레이션."""
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from kairos1_main import KairosSimple
from src.core.exceptions import DataUnavailableError
from src.portfolio.portfolio import PortfolioSnapshot
from src.strategy.valuation import MarketValuation


def make_system(fg=50, mayer=1.5, holdings=None, krw=40_000_000):
    holdings = holdings or {
        "BTC": 30_000_000, "ETH": 18_000_000, "XRP": 6_000_000, "SOL": 6_000_000
    }
    market = MagicMock()
    market.get_valuation.return_value = MarketValuation(fg, mayer)
    market.get_price_change_24h.return_value = {a: 0.0 for a in holdings}
    portfolio = MagicMock()
    portfolio.get_snapshot.return_value = PortfolioSnapshot(
        holdings_krw=holdings, krw_balance=krw, taken_at=datetime.now()
    )
    executor = MagicMock()
    executor.execute.return_value = MagicMock(success=True, filled_krw=1.0)
    alerts = MagicMock()
    sys_ = KairosSimple.from_components(
        market_data=market, portfolio=portfolio, executor=executor,
        alerts=alerts, config=KairosSimple.default_config(),
    )
    return sys_, executor, alerts


def test_weekly_dca_places_buy_orders():
    sys_, executor, _ = make_system(fg=20, mayer=0.9)  # 극공포+바닥 → 3.0x
    result = sys_.run_weekly_dca(dry_run=False)
    assert result["executed"] > 0
    assert all(c.args[0].side == "buy" for c in executor.execute.call_args_list)


def test_weekly_dca_dry_run_places_nothing():
    sys_, executor, _ = make_system()
    result = sys_.run_weekly_dca(dry_run=True)
    executor.execute.assert_not_called()
    assert result["executed"] == 0 and not result["halted"]


def test_daily_check_no_orders_within_band():
    sys_, executor, _ = make_system()  # 크립토 60% 정확히 목표
    result = sys_.run_daily_check(dry_run=False)
    assert result["executed"] == 0
    executor.execute.assert_not_called()


def test_daily_check_sells_when_overweight():
    """상승장: 크립토 80% → 매도(익절) 주문 발생"""
    holdings = {"BTC": 40_000_000, "ETH": 24_000_000, "XRP": 8_000_000, "SOL": 8_000_000}
    sys_, executor, _ = make_system(holdings=holdings, krw=20_000_000)
    result = sys_.run_daily_check(dry_run=False)
    sides = [c.args[0].side for c in executor.execute.call_args_list]
    assert "sell" in sides
    assert result["executed"] > 0


def test_daily_check_buys_when_underweight():
    """하락장: 크립토 40% → 매수(저가 매집) 주문 발생"""
    holdings = {"BTC": 20_000_000, "ETH": 12_000_000, "XRP": 4_000_000, "SOL": 4_000_000}
    sys_, executor, _ = make_system(holdings=holdings, krw=60_000_000)
    sys_.run_daily_check(dry_run=False)
    sides = [c.args[0].side for c in executor.execute.call_args_list]
    assert "buy" in sides


def test_sells_execute_before_buys():
    """매도 먼저 실행해 KRW 확보 후 매수"""
    holdings = {"BTC": 50_000_000, "ETH": 12_000_000, "XRP": 4_000_000, "SOL": 4_000_000}
    sys_, executor, _ = make_system(holdings=holdings, krw=30_000_000)
    sys_.run_daily_check(dry_run=False)
    sides = [c.args[0].side for c in executor.execute.call_args_list]
    assert sides == sorted(sides, key=lambda s: s != "sell")


def test_data_failure_halts_and_alerts():
    """스펙 fail-loud: 데이터 실패 시 주문 0건 + 경고 알림"""
    sys_, executor, alerts = make_system()
    sys_.market.get_valuation.side_effect = DataUnavailableError("F&G down")
    result = sys_.run_weekly_dca(dry_run=False)
    assert result["executed"] == 0 and result["halted"]
    executor.execute.assert_not_called()
    assert alerts.send_warning_alert.called


def test_risk_guard_rejection_recorded():
    """리스크 가드 거부 주문은 실행되지 않고 rejected에 기록"""
    # KRW 하한: 매수 후 KRW가 총자산 10% 미만이면 거부
    holdings = {"BTC": 20_000_000, "ETH": 12_000_000, "XRP": 4_000_000, "SOL": 4_000_000}
    sys_, executor, _ = make_system(holdings=holdings, krw=60_000_000)
    # min_krw_ratio를 극단으로 올려 전부 거부되게 함
    limits = sys_.config.limits.__class__(
        max_single_trade_krw=10_000_000, max_daily_volume_krw=50_000_000,
        min_krw_ratio=0.99, fomo_surge_threshold=0.15,
    )
    from src.risk.guard import RiskGuard
    sys_.guard = RiskGuard(limits)
    result = sys_.run_daily_check(dry_run=False)
    assert result["executed"] == 0
    assert result["rejected"]
