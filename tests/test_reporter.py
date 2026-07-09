"""src/report/reporter.py 테스트 — 실제 BTC 벤치마크 성과 리포트."""
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.report.reporter import Reporter
from src.core.exceptions import DataUnavailableError


def make_reporter(btc_closes):
    binance = MagicMock()
    binance.get_historical_klines.return_value = pd.DataFrame({"Close": btc_closes})
    alerts = MagicMock()
    return Reporter(binance, alerts), alerts


def test_btc_benchmark_return_from_real_prices():
    reporter, _ = make_reporter(btc_closes=[100.0] + [110.0] * 29 + [120.0])
    assert reporter.btc_benchmark_return(days=30) == pytest.approx(0.20)


def test_benchmark_empty_data_raises():
    """스펙 fail-loud: 하드코딩 5% 벤치마크 금지 — 데이터 없으면 예외"""
    reporter, _ = make_reporter(btc_closes=[])
    with pytest.raises(DataUnavailableError):
        reporter.btc_benchmark_return(days=30)


def test_benchmark_zero_start_price_raises():
    reporter, _ = make_reporter(btc_closes=[0.0, 120.0])
    with pytest.raises(DataUnavailableError):
        reporter.btc_benchmark_return(days=30)


def test_monthly_report_includes_vs_benchmark_and_sends_alert():
    reporter, alerts = make_reporter(btc_closes=[100.0] + [105.0] * 29 + [110.0])
    report = reporter.monthly_report(
        portfolio_return=0.15, total_value_krw=110_000_000, crypto_ratio=0.61
    )
    assert report["portfolio_return"] == pytest.approx(0.15)
    assert report["btc_benchmark_return"] == pytest.approx(0.10)
    assert report["excess_return"] == pytest.approx(0.05)
    assert alerts.send_info_alert.called
