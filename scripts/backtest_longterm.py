"""KAIROS-Simple 백테스트 — 실거래와 동일한 순수 함수 사용.

단순화: BTC 단일 자산(주봉). Fear&Greed는 과거 시계열이 없으므로
회고적 프록시(직전 12주 수익률)로 생성 — t 시점 결정에 t 이후 데이터를
쓰지 않는다(look-ahead 금지).

실행: kairos_env/bin/python scripts/backtest_longterm.py
CLAUDE.md 체크리스트: 수수료 0.2% + 슬리피지 0.2% 왕복 반영,
동적 포지션 사이징(전략 함수), 상승/하락/횡보 시나리오 테스트 포함.
"""
import dataclasses
from dataclasses import dataclass, field
from typing import List

import numpy as np
import pandas as pd

from src.strategy.dca import DCAConfig, plan_weekly_dca
from src.strategy.rebalance import RebalanceConfig, plan_rebalance
from src.strategy.valuation import (
    MarketValuation,
    contrarian_crypto_target,
    dca_multiplier,
)

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
    start: int = 0,
    contrarian_tilt: bool = True,
    enable_dca: bool = True,
    enable_rebalance: bool = True,
    band_pp: float = 0.05,
    order_fraction: float = 1.0,
) -> BacktestResult:
    """start: 투자 시작 주차 인덱스. 거래·적립은 start부터 시작하되
    200주MA·심리 프록시는 start 이전 데이터까지 활용한다
    (실전에서 과거 시세는 시장에 이미 존재하므로).
    contrarian_tilt: 프로덕션과 동일한 Mayer 밴드 목표 비중 틸트.
    enable_dca/enable_rebalance: 컴포넌트 ablation용 — 주간 적립 현금은
    항상 들어오고, 끈 컴포넌트만 배치를 멈춘다."""
    dca_cfg = DCAConfig(
        base_amount_krw=WEEKLY_BASE_DCA, crypto_weights={"BTC": 1.0},
        max_single_dca_krw=5 * WEEKLY_BASE_DCA, krw_usage_cap=0.25,
        min_order_krw=1_000,
    )
    reb_cfg = RebalanceConfig(
        crypto_target=crypto_target, band_pp=band_pp, crypto_weights={"BTC": 1.0},
        relative_band=0.20, min_trade_krw=1_000,
        order_fraction=order_fraction,
    )
    cost = fee + slippage

    krw, btc_qty = 10_000_000.0, 0.0
    buys = sells = 0.0
    trades = 0
    values: List[float] = []
    closes = weekly["Close"]

    for t in range(start, len(closes)):
        price = float(closes.iloc[t])
        krw += WEEKLY_BASE_DCA  # 주간 적립

        history = closes.iloc[: t + 1]  # t 시점까지의 데이터만 사용
        week_reb_cfg = reb_cfg
        if len(history) >= 200:
            ma = float(history.iloc[-200:].mean())
            ret12 = float(history.iloc[-1] / history.iloc[-13] - 1) if t >= 12 else 0.0
            mayer = price / ma
            valuation = MarketValuation(_fg_proxy(ret12), mayer)
            mult = dca_multiplier(valuation)
            if contrarian_tilt:
                week_reb_cfg = dataclasses.replace(
                    reb_cfg,
                    crypto_target=contrarian_crypto_target(mayer, crypto_target),
                )
        else:
            mult = 1.0  # 워밍업 구간: 기본 DCA만 (MA 없으면 틸트도 불가)

        # 실운영과 동일: 매수 후 비중이 (틸트된) 목표를 넘지 않도록 상한
        dca_orders = plan_weekly_dca(
            dca_cfg, mult, krw,
            crypto_value_krw=btc_qty * price,
            target_crypto_ratio=week_reb_cfg.crypto_target,
        ) if enable_dca else []
        for order in dca_orders:
            spend = order.amount_krw
            btc_qty += spend * (1 - cost) / price
            krw -= spend
            buys += spend
            trades += 1

        holdings = {"BTC": btc_qty * price}
        reb_orders = (
            plan_rebalance(week_reb_cfg, holdings, krw) if enable_rebalance else []
        )
        for order in reb_orders:
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
    # 시간가중 수익률: 주간 적립(외부 입금)은 수익이 아니다 —
    # r_t = (V_t − 입금) / V_{t−1} − 1. 원시 가치 시계열로 계산하면
    # 입금이 수익률로 잡혀 Sharpe가 부풀고 MDD가 완충된다.
    weekly_ret = ((series - WEEKLY_BASE_DCA) / series.shift(1) - 1.0).dropna()
    sharpe = (
        float(weekly_ret.mean() / weekly_ret.std() * np.sqrt(52))
        if len(weekly_ret) > 1 and weekly_ret.std() > 0
        else 0.0
    )
    twr_index = (1.0 + weekly_ret).cumprod()
    drawdown = (
        float((twr_index / twr_index.cummax() - 1).min())
        if len(twr_index) > 0 else 0.0
    )
    return BacktestResult(
        final_value=float(series.iloc[-1]), total_buy_krw=float(buys),
        total_sell_krw=float(sells), total_trades=int(trades),
        max_drawdown=drawdown, sharpe=sharpe, weekly_values=values,
    )


def sweep_starts(
    weekly: pd.DataFrame, starts: List[int], **kwargs
) -> List[tuple]:
    """여러 시작 주차에 대해 백테스트 실행. [(start, start_date, result), ...]"""
    return [
        (s, weekly.index[s], run_backtest(weekly, start=s, **kwargs))
        for s in starts
    ]


def fetch_bitstamp_weekly() -> pd.DataFrame:
    """Bitstamp 공개 API에서 2011-08부터 BTC/USD 주봉 생성 (무료, 키 불필요).

    Binance는 2017-08부터라 2015-2017 사이클을 틸트 활성 상태로
    검증할 수 없다 — 아웃오브샘플 검증용 장기 데이터 소스.
    docs/backtest-validation.md 참고.
    """
    import time as _time

    import requests

    rows = []
    start = 1315000000  # 2011-09
    while True:
        resp = requests.get(
            "https://www.bitstamp.net/api/v2/ohlc/btcusd/",
            params={"step": 86400, "limit": 1000, "start": start},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()["data"]["ohlc"]
        if not data:
            break
        rows.extend(data)
        last = int(data[-1]["timestamp"])
        if len(data) < 1000 or last > _time.time() - 86400:
            break
        start = last + 86400
        _time.sleep(0.5)

    daily = pd.DataFrame(rows)
    daily["timestamp"] = pd.to_datetime(daily["timestamp"].astype(int), unit="s")
    daily = daily.set_index("timestamp").astype(float).sort_index()
    daily = daily[~daily.index.duplicated()]
    weekly = (
        daily["close"].resample("W-MON", label="left", closed="left")
        .last().dropna().to_frame("Close")
    )
    return weekly


if __name__ == "__main__":
    import argparse
    from datetime import datetime

    from src.utils.binance_data_provider import BinanceDataProvider

    parser = argparse.ArgumentParser(description="KAIROS-Simple 장기·다중 시작점 백테스트")
    parser.add_argument("--since", default=None,
                        help="데이터 시작일 YYYY-MM-DD (기본: binance 2017-01-01, bitstamp 전체)")
    parser.add_argument("--source", choices=["binance", "bitstamp"], default="binance",
                        help="bitstamp: 2011-08부터 (2015-2017 사이클 OOS 검증용)")
    parser.add_argument("--start-every", type=int, default=0,
                        help="N주 간격 다중 시작점 스윕 (0이면 단일 실행)")
    parser.add_argument("--target", type=float, default=0.60, help="크립토 목표 비중")
    parser.add_argument("--no-tilt", action="store_true",
                        help="역발상 목표 비중 틸트 비활성화 (고정 목표 비교용)")
    parser.add_argument("--no-dca", action="store_true",
                        help="주간 DCA 비활성화 (컴포넌트 ablation용)")
    parser.add_argument("--no-rebalance", action="store_true",
                        help="밴드 리밸런싱 비활성화 (컴포넌트 ablation용)")
    args = parser.parse_args()
    tilt = not args.no_tilt

    if args.source == "bitstamp":
        df = fetch_bitstamp_weekly()
        if args.since:
            df = df[df.index >= args.since]
    else:
        df = BinanceDataProvider().get_historical_klines(
            "BTCUSDT", "1w",
            start_date=datetime.fromisoformat(args.since or "2017-01-01"),
        )
    print(f"데이터: {len(df)}주 ({df.index[0].date()} ~ {df.index[-1].date()})")

    if args.start_every > 0:
        starts = list(range(0, len(df) - 52, args.start_every))  # 최소 1년 여유
        print(f"{'시작일':>10} | {'기간':>5} | {'투입원금':>14} | {'최종자산':>14} | "
              f"{'배수':>5} | {'MDD':>7} | {'Sharpe':>6} | 거래")
        for s, date, r in sweep_starts(
            df, starts, crypto_target=args.target, contrarian_tilt=tilt,
            enable_dca=not args.no_dca, enable_rebalance=not args.no_rebalance,
        ):
            weeks = len(df) - s
            invested = 10_000_000 + WEEKLY_BASE_DCA * weeks
            print(f"{str(date.date()):>10} | {weeks:>4}주 | {invested:>13,.0f} | "
                  f"{r.final_value:>13,.0f} | {r.final_value / invested:>4.2f}x | "
                  f"{r.max_drawdown:>6.1%} | {r.sharpe:>6.2f} | {r.total_trades}")
    else:
        result = run_backtest(df, crypto_target=args.target, contrarian_tilt=tilt)
        invested = 10_000_000 + WEEKLY_BASE_DCA * len(df)
        print(f"기간: {len(df)}주 | 투입 원금(적립 포함): {invested:,.0f} KRW")
        print(f"최종 자산: {result.final_value:,.0f} KRW")
        print(f"총 매수 {result.total_buy_krw:,.0f} / 총 매도 {result.total_sell_krw:,.0f} KRW")
        print(f"거래 {result.total_trades}건 | MDD {result.max_drawdown:.1%} | Sharpe {result.sharpe:.2f}")
