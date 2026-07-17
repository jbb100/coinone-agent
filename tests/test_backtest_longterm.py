"""scripts/backtest_longterm.py 테스트 — 실전 동일 순수함수 백테스트."""
import numpy as np
import pandas as pd
import pytest

from scripts.backtest_longterm import BacktestResult, run_backtest, sweep_starts


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


# --- 다중 시작점 (start 파라미터) ---


def make_crash_after_bull(weeks_bull: int = 240, weeks_crash: int = 30) -> pd.DataFrame:
    """240주 완만한 상승 후 급락 — start 시점에 200주MA 아래로 떨어진 상태."""
    rng = np.random.default_rng(7)
    bull = 1000 * np.cumprod(1 + rng.normal(0.005, 0.01, weeks_bull))
    crash = bull[-1] * np.cumprod(1 + rng.normal(-0.05, 0.01, weeks_crash))
    closes = np.concatenate([bull, crash])
    idx = pd.date_range("2017-01-01", periods=len(closes), freq="W")
    return pd.DataFrame({"Close": closes}, index=idx)


def test_start_trades_only_after_start_index():
    """start 이후 주차만 기록: weekly_values 길이 = len(df) - start"""
    df = make_price_series("sideways", weeks=300)
    r = run_backtest(df, start=250)
    assert len(r.weekly_values) == 50


def test_start_zero_is_default_behavior():
    df = make_price_series("sideways", weeks=300)
    assert run_backtest(df).weekly_values == run_backtest(df, start=0).weekly_values


def test_start_uses_prior_history_for_valuation():
    """start 이전 히스토리로 200주MA·심리 프록시를 계산해야 함.

    급락 직후 시점에서 시작하면 (MA 아래 + 공포) 승수가 커져
    히스토리를 버리고 슬라이스로 시작한 경우(mult=1.0 워밍업)보다 더 사야 한다.
    """
    df = make_crash_after_bull()
    start = 255  # 급락 중반부터 투자 시작
    with_history = run_backtest(df, start=start)
    without_history = run_backtest(df.iloc[start:])
    assert len(with_history.weekly_values) == len(without_history.weekly_values)
    assert with_history.total_buy_krw > without_history.total_buy_krw


def test_start_no_lookahead():
    """start가 있어도 미래 데이터를 잘라낸 결과와 접두부가 일치해야 함"""
    df = make_price_series("sideways", weeks=300)
    full = run_backtest(df, start=220)
    truncated = run_backtest(df.iloc[:260], start=220)
    n = len(truncated.weekly_values)
    assert full.weekly_values[:n] == pytest.approx(truncated.weekly_values, rel=1e-9)


def test_tilt_raises_buys_in_bottom_zone():
    """역발상 틸트: 급락(MA 아래) 구간에서 고정 목표보다 더 매수해야 함"""
    df = make_crash_after_bull()
    tilted = run_backtest(df, start=255, contrarian_tilt=True)
    fixed = run_backtest(df, start=255, contrarian_tilt=False)
    assert tilted.total_buy_krw > fixed.total_buy_krw


def test_tilt_default_matches_production_default():
    """프로덕션 기본값(틸트 on)과 백테스트 기본값이 일치해야 함"""
    df = make_crash_after_bull()
    default = run_backtest(df, start=255)
    explicit = run_backtest(df, start=255, contrarian_tilt=True)
    assert default.weekly_values == explicit.weekly_values


def test_sweep_starts_returns_result_per_start():
    df = make_price_series("sideways", weeks=300)
    rows = sweep_starts(df, starts=[0, 100, 200])
    assert len(rows) == 3
    for (start, start_date, result) in rows:
        assert isinstance(result, BacktestResult)
        assert start_date == df.index[start]
        assert len(result.weekly_values) == len(df) - start


def test_flat_market_sharpe_not_inflated_by_deposits():
    """입금은 수익이 아니다 — 횡보장에서 주간 적립(250k)이 수익률로 잡히면
    Sharpe가 크게 양수로 부풀려진다. 비용만 있는 횡보장의 시간가중 Sharpe는
    0 이하여야 함"""
    import pandas as pd
    weekly = pd.DataFrame({"Close": [100.0] * 260})
    r = run_backtest(weekly)
    assert r.sharpe <= 0.0
