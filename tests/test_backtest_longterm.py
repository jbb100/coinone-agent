"""scripts/backtest_longterm.py 테스트 — 실전 동일 순수함수 백테스트."""
import numpy as np
import pandas as pd
import pytest

from scripts.backtest_longterm import BacktestResult, run_backtest


def make_price_series(pattern: str, weeks: int = 300) -> pd.DataFrame:
    """주봉 Close 시계열 생성."""
    rng = np.random.default_rng(42)
    if pattern == "bull":
        closes = 1000 * np.cumprod(1 + rng.normal(0.01, 0.03, weeks))
    elif pattern == "bear":
        closes = 1000 * np.cumprod(1 + rng.normal(-0.008, 0.03, weeks))
    else:  # sideways
        closes = 1000 * np.cumprod(1 + rng.normal(0.0, 0.02, weeks))
    idx = pd.date_range("2018-01-01", periods=weeks, freq="W")
    return pd.DataFrame({"Close": closes}, index=idx)


def test_costs_are_applied():
    """CLAUDE.md 백테스팅 체크리스트: 수수료·슬리피지 반영 시 성과 하락"""
    df = make_price_series("sideways")
    r0 = run_backtest(df, fee=0.0, slippage=0.0)
    r1 = run_backtest(df, fee=0.002, slippage=0.002)
    assert r1.total_trades == r0.total_trades
    assert r1.final_value < r0.final_value


def test_counter_cyclical_behavior_in_bear():
    """하락장에서 매수 체결 금액 > 매도 금액 (매집 동작 검증)"""
    r = run_backtest(make_price_series("bear"))
    assert r.total_buy_krw > r.total_sell_krw


def test_profit_taking_in_bull():
    """상승장에서 리밸런싱 매도(익절)가 발생해야 함"""
    r = run_backtest(make_price_series("bull"))
    assert r.total_sell_krw > 0


def test_no_lookahead():
    """t주차까지의 결과는 이후 데이터를 잘라도 동일해야 함 (look-ahead bias 금지)"""
    df = make_price_series("sideways", weeks=300)
    full = run_backtest(df)
    truncated = run_backtest(df.iloc[:260])
    n = len(truncated.weekly_values)
    assert full.weekly_values[:n] == pytest.approx(truncated.weekly_values, rel=1e-9)


def test_result_reports_required_metrics():
    r = run_backtest(make_price_series("sideways"))
    assert r.max_drawdown <= 0
    assert isinstance(r.sharpe, float)
    assert r.final_value > 0
