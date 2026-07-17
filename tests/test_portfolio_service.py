"""src/portfolio/portfolio.py 테스트 — 잔고 스냅샷·거래 기록."""
from unittest.mock import MagicMock

import pytest

from src.portfolio.portfolio import PortfolioService, PortfolioSnapshot


def make_service(balances, prices):
    coinone = MagicMock()
    coinone.get_balances.return_value = balances
    market = MagicMock()
    market.get_prices_krw.return_value = prices
    db = MagicMock()
    return PortfolioService(coinone, market, db, assets=["BTC", "ETH"]), db


def test_snapshot_values_holdings_in_krw():
    svc, _ = make_service(
        balances={"KRW": 40_000_000.0, "BTC": 0.5, "ETH": 4.0},
        prices={"BTC": 100_000_000.0, "ETH": 5_000_000.0},
    )
    snap = svc.get_snapshot()
    assert snap.holdings_krw == {"BTC": 50_000_000.0, "ETH": 20_000_000.0}
    assert snap.krw_balance == 40_000_000.0
    assert snap.total_value_krw == pytest.approx(110_000_000.0)
    assert snap.crypto_ratio == pytest.approx(70_000_000.0 / 110_000_000.0)


def test_snapshot_missing_asset_counts_zero():
    svc, _ = make_service(
        balances={"KRW": 1_000_000.0},
        prices={"BTC": 100_000_000.0, "ETH": 5_000_000.0},
    )
    snap = svc.get_snapshot()
    assert snap.holdings_krw == {"BTC": 0.0, "ETH": 0.0}


def test_empty_snapshot_ratio_zero():
    svc, _ = make_service(
        balances={},
        prices={"BTC": 100_000_000.0, "ETH": 5_000_000.0},
    )
    assert svc.get_snapshot().crypto_ratio == 0.0


def test_record_trade_persists_to_db():
    svc, db = make_service(
        balances={"KRW": 1_000_000.0},
        prices={"BTC": 100_000_000.0, "ETH": 5_000_000.0},
    )
    svc.record_trade("BTC", "buy", 500_000.0, origin="dca")
    assert db.save_trade.called
    saved = db.save_trade.call_args.args[0]
    assert saved["asset"] == "BTC"          # trade_history DDL 컬럼과 일치해야 함
    assert saved["side"] == "buy"
    assert saved["amount_krw"] == 500_000.0
    assert saved["origin"] == "dca"


def test_traded_krw_today_delegates_to_db():
    """일일 거래량 한도 시딩용 — DB의 오늘 거래액 합계를 그대로 노출"""
    svc, db = make_service(balances={}, prices={})
    db.get_traded_krw_today.return_value = 12_345.0
    assert svc.get_traded_krw_today() == pytest.approx(12_345.0)


def test_record_snapshot_saves_totals_and_assets():
    """일일 스냅샷 축적 — 월간 수익률 산출의 데이터 원천"""
    from datetime import datetime
    svc, db = make_service(balances={}, prices={})
    snap = PortfolioSnapshot(
        holdings_krw={"BTC": 50_000_000.0, "ETH": 10_000_000.0},
        krw_balance=40_000_000.0,
        taken_at=datetime.now(),
    )
    svc.record_snapshot(snap)
    (data,), _ = db.save_portfolio_snapshot.call_args
    assert data["total_value_krw"] == pytest.approx(100_000_000.0)
    assert data["assets"]["BTC"]["value_krw"] == pytest.approx(50_000_000.0)
    assert data["assets"]["KRW"] == pytest.approx(40_000_000.0)


def test_value_change_30d_returns_change_and_window_days():
    """수익률은 실제 관측 창(일수)과 함께 반환 — 5일치 데이터로 계산한
    수익률을 30일 BTC 벤치마크와 비교하는 사과-오렌지 비교 방지"""
    from datetime import datetime, timedelta
    svc, db = make_service(balances={}, prices={})
    d28 = (datetime.now() - timedelta(days=28)).strftime("%Y-%m-%d 09:10:00")
    d1 = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d 09:10:00")
    db.get_portfolio_history.return_value = [
        {"snapshot_date": d28, "total_value_krw": 80_000_000.0},
        {"snapshot_date": d1, "total_value_krw": 95_000_000.0},
    ]
    change, days = svc.get_value_change_30d(current_total_krw=100_000_000.0)
    assert change == pytest.approx(0.25)  # 80M → 100M
    assert days == 28


def test_value_change_30d_excludes_same_day_baseline():
    """당일 09:10 스냅샷을 기준선으로 잡으면 수익률이 항상 ≈0%로 나온다 —
    오늘 이전 스냅샷이 없으면 None (데이터 축적 중)"""
    from datetime import datetime
    svc, db = make_service(balances={}, prices={})
    today = datetime.now().strftime("%Y-%m-%d 09:10:00")
    db.get_portfolio_history.return_value = [
        {"snapshot_date": today, "total_value_krw": 100_000_000.0},
    ]
    assert svc.get_value_change_30d(current_total_krw=100_500_000.0) is None


def test_value_change_30d_none_when_no_history():
    """데이터 축적 전에는 수익률 주장 금지 (fail-loud 대신 None)"""
    svc, db = make_service(balances={}, prices={})
    db.get_portfolio_history.return_value = []
    assert svc.get_value_change_30d(current_total_krw=100_000_000.0) is None


def test_previous_total_uses_latest_snapshot_before_today():
    """데일리 브리핑 전일 대비 — 오늘 이전의 가장 최근 스냅샷 기준"""
    from datetime import datetime, timedelta
    svc, db = make_service(balances={}, prices={})
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d 09:10:00")
    day_before = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d 09:10:00")
    today = datetime.now().strftime("%Y-%m-%d 09:10:00")
    db.get_portfolio_history.return_value = [
        {"snapshot_date": day_before, "total_value_krw": 90_000_000.0},
        {"snapshot_date": yesterday, "total_value_krw": 95_000_000.0},
        {"snapshot_date": today, "total_value_krw": 100_000_000.0},  # 오늘 것은 제외
    ]
    assert svc.get_previous_total_krw() == pytest.approx(95_000_000.0)


def test_previous_total_skips_zero_rows():
    """과거 버그로 total 0으로 저장된 행은 기준으로 쓰지 않는다"""
    from datetime import datetime, timedelta
    svc, db = make_service(balances={}, prices={})
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d 09:10:00")
    db.get_portfolio_history.return_value = [
        {"snapshot_date": yesterday, "total_value_krw": 0.0},
    ]
    assert svc.get_previous_total_krw() is None


def test_previous_total_none_without_history():
    svc, db = make_service(balances={}, prices={})
    db.get_portfolio_history.return_value = []
    assert svc.get_previous_total_krw() is None
