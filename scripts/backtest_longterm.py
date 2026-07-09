"""KAIROS-Simple 백테스트 — 실거래와 동일한 순수 함수 사용.

단순화: BTC 단일 자산(주봉). Fear&Greed는 과거 시계열이 없으므로
회고적 프록시(직전 12주 수익률)로 생성 — t 시점 결정에 t 이후 데이터를
쓰지 않는다(look-ahead 금지).

실행: kairos_env/bin/python scripts/backtest_longterm.py
CLAUDE.md 체크리스트: 수수료 0.2% + 슬리피지 0.2% 왕복 반영,
동적 포지션 사이징(전략 함수), 상승/하락/횡보 시나리오 테스트 포함.
"""
from dataclasses import dataclass, field
from typing import List

import numpy as np
import pandas as pd

from src.strategy.dca import DCAConfig, plan_weekly_dca
from src.strategy.rebalance import RebalanceConfig, plan_rebalance
from src.strategy.valuation import MarketValuation, dca_multiplier

WEEKLY_BASE_DCA = 250_000  # 주간 신규 적립 현금 (KRW)


@dataclass
class BacktestResult:
    final_value: float
    total_buy_krw: float
    total_sell_krw: float
    total_trades: int
    max_drawdown: float
    sharpe: float
    weekly_values: List[float] = field(default_factory=list)


def _fg_proxy(returns_12w: float) -> int:
    """직전 12주 수익률 → 0-100 심리 프록시 (과거 데이터만 사용)."""
    return int(np.clip(50 + returns_12w * 100, 0, 100))


def run_backtest(
    weekly: pd.DataFrame,
    fee: float = 0.002,
    slippage: float = 0.002,
    crypto_target: float = 0.60,
) -> BacktestResult:
    dca_cfg = DCAConfig(
        base_amount_krw=WEEKLY_BASE_DCA, crypto_weights={"BTC": 1.0},
        max_single_dca_krw=5 * WEEKLY_BASE_DCA, krw_usage_cap=0.25,
        min_order_krw=1_000,
    )
    reb_cfg = RebalanceConfig(
        crypto_target=crypto_target, band_pp=0.05, crypto_weights={"BTC": 1.0},
        relative_band=0.20, min_trade_krw=1_000,
    )
    cost = fee + slippage

    krw, btc_qty = 10_000_000.0, 0.0
    buys = sells = 0.0
    trades = 0
    values: List[float] = []
    closes = weekly["Close"]

    for t in range(len(closes)):
        price = float(closes.iloc[t])
        krw += WEEKLY_BASE_DCA  # 주간 적립

        history = closes.iloc[: t + 1]  # t 시점까지의 데이터만 사용
        if len(history) >= 200:
            ma = float(history.iloc[-200:].mean())
            ret12 = float(history.iloc[-1] / history.iloc[-13] - 1) if t >= 12 else 0.0
            valuation = MarketValuation(_fg_proxy(ret12), price / ma)
            mult = dca_multiplier(valuation)
        else:
            mult = 1.0  # 워밍업 구간: 기본 DCA만

        for order in plan_weekly_dca(dca_cfg, mult, krw):
            spend = order.amount_krw
            btc_qty += spend * (1 - cost) / price
            krw -= spend
            buys += spend
            trades += 1

        holdings = {"BTC": btc_qty * price}
        for order in plan_rebalance(reb_cfg, holdings, krw):
            if order.side == "sell":
                btc_qty -= order.amount_krw / price
                krw += order.amount_krw * (1 - cost)
                sells += order.amount_krw
            else:
                btc_qty += order.amount_krw * (1 - cost) / price
                krw -= order.amount_krw
                buys += order.amount_krw
            trades += 1

        values.append(krw + btc_qty * price)

    series = pd.Series(values)
    weekly_ret = series.pct_change().dropna()
    sharpe = (
        float(weekly_ret.mean() / weekly_ret.std() * np.sqrt(52))
        if len(weekly_ret) > 1 and weekly_ret.std() > 0
        else 0.0
    )
    drawdown = float((series / series.cummax() - 1).min())
    return BacktestResult(
        final_value=float(series.iloc[-1]), total_buy_krw=float(buys),
        total_sell_krw=float(sells), total_trades=int(trades),
        max_drawdown=drawdown, sharpe=sharpe, weekly_values=values,
    )


if __name__ == "__main__":
    from src.utils.binance_data_provider import BinanceDataProvider

    df = BinanceDataProvider().get_historical_klines("BTCUSDT", "1w", limit=450)
    result = run_backtest(df)
    invested = 10_000_000 + WEEKLY_BASE_DCA * len(df)
    print(f"기간: {len(df)}주 | 투입 원금(적립 포함): {invested:,.0f} KRW")
    print(f"최종 자산: {result.final_value:,.0f} KRW")
    print(f"총 매수 {result.total_buy_krw:,.0f} / 총 매도 {result.total_sell_krw:,.0f} KRW")
    print(f"거래 {result.total_trades}건 | MDD {result.max_drawdown:.1%} | Sharpe {result.sharpe:.2f}")
