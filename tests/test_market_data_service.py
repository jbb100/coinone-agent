"""src/data/market_data.py 테스트 — 실 API 래퍼 (fail-loud)."""
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.data.market_data import MarketDataService
from src.core.exceptions import DataUnavailableError, InsufficientDataError


def make_service(fg=30, weekly_rows=260, price=100_000_000.0):
    binance = MagicMock()
    closes = pd.Series([50_000.0 + i for i in range(weekly_rows)])
    binance.get_historical_klines.return_value = pd.DataFrame({"Close": closes})
    external = MagicMock()
    external.get_fear_greed_index.return_value = fg
    coinone = MagicMock()
    coinone.get_latest_price.return_value = price
    return MarketDataService(binance, external, coinone), binance, external, coinone


def test_get_valuation_combines_fg_and_mayer():
    svc, *_ = make_service(fg=20)
    v = svc.get_valuation()
    assert v.fear_greed == 20
    assert v.mayer_ratio > 0


def test_fg_none_raises_data_unavailable():
    """스펙 fail-loud: F&G 실패 시 50 폴백 금지, 예외"""
    svc, _, external, _ = make_service()
    external.get_fear_greed_index.return_value = None
    with pytest.raises(DataUnavailableError):
        svc.get_valuation()


def test_short_history_raises_insufficient_data():
    svc, *_ = make_service(weekly_rows=100)
    with pytest.raises(InsufficientDataError):
        svc.get_valuation()


def test_empty_klines_raises():
    svc, binance, *_ = make_service()
    binance.get_historical_klines.return_value = pd.DataFrame()
    with pytest.raises(DataUnavailableError):
        svc.get_valuation()


def test_get_prices_krw_returns_per_asset():
    svc, _, _, coinone = make_service(price=50_000_000.0)
    prices = svc.get_prices_krw(["BTC", "ETH"])
    assert prices == {"BTC": 50_000_000.0, "ETH": 50_000_000.0}


def test_get_prices_krw_invalid_price_raises():
    svc, _, _, coinone = make_service()
    coinone.get_latest_price.return_value = 0.0
    with pytest.raises(DataUnavailableError):
        svc.get_prices_krw(["BTC"])


def test_price_change_24h_computed_from_daily_klines():
    svc, binance, _, _ = make_service()
    binance.get_historical_klines.return_value = pd.DataFrame(
        {"Close": [100.0, 116.0]}
    )
    change = svc.get_price_change_24h(["BTC"])
    assert change["BTC"] == pytest.approx(0.16)


def test_price_change_24h_missing_data_raises():
    svc, binance, _, _ = make_service()
    binance.get_historical_klines.return_value = pd.DataFrame({"Close": [100.0]})
    with pytest.raises(DataUnavailableError):
        svc.get_price_change_24h(["BTC"])
