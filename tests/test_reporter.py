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


def test_monthly_report_benchmark_matches_observation_window():
    """포트폴리오 수익률이 5일치 관측이면 벤치마크도 5일로 — 서로 다른
    창의 수익률을 빼서 초과수익이라 주장하면 안 됨"""
    reporter, alerts = make_reporter(btc_closes=[100.0, 105.0, 110.0])
    report = reporter.monthly_report(
        portfolio_return=0.02, total_value_krw=100_000_000, crypto_ratio=0.60,
        window_days=5,
    )
    reporter.binance.get_historical_klines.assert_called_once()
    assert reporter.binance.get_historical_klines.call_args.kwargs["limit"] == 6
    assert report["window_days"] == 5
    _, body = alerts.send_info_alert.call_args.args
    assert "5일" in body


def test_monthly_report_includes_static_6040_drift_baseline():
    """드리프트 기준선: 60% BTC + 40% KRW 무리밸런싱 대비 초과수익.

    전략이 약속(밴드 리밸런싱 알파)대로 작동하면 이 기준선을 장기적으로
    상회해야 한다 — 지속적 대폭 열위는 구현·체결 문제의 조기 신호."""
    reporter, alerts = make_reporter(btc_closes=[100.0] + [105.0] * 29 + [110.0])
    report = reporter.monthly_report(
        portfolio_return=0.08, total_value_krw=110_000_000, crypto_ratio=0.61,
    )
    assert report["static_6040_return"] == pytest.approx(0.06)   # 0.6 × 10%
    assert report["drift_vs_6040"] == pytest.approx(0.02)
    _, body = alerts.send_info_alert.call_args.args
    assert "60/40" in body


def test_monthly_report_labels_return_method():
    """수익률 산출 방식(TWR vs 단순)이 리포트에 명시돼야 함"""
    reporter, alerts = make_reporter(btc_closes=[100.0, 110.0])
    reporter.monthly_report(
        portfolio_return=0.05, total_value_krw=100_000_000, crypto_ratio=0.60,
        window_days=1, method="TWR",
    )
    _, body = alerts.send_info_alert.call_args.args
    assert "TWR" in body
