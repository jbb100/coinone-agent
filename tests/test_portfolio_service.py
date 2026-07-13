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
