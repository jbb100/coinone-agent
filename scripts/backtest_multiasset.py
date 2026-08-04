"""KAIROS-Simple 멀티자산 일봉 백테스트 — 실거래와 동일한 순수 함수 사용.

기존 backtest_longterm.py(BTC 단일·주봉)의 최대 증거 공백 해소:
실제 포트폴리오(BTC/ETH/XRP/SOL)를 일봉으로 시뮬레이션하여
상대강도 편출·크래시 가드·FOMO 가드까지 실운영 파이프라인 전체를 검증한다.

실운영과의 대응:
  - 일일: 밴드 체크(틸트 목표) + 크래시 가드 + FOMO 가드
  - 주간(월요일): DCA (F&G 프록시 × Mayer 승수, 목표 인지 상한)
  - 26주 상대수익 → 알트 편출 (BTC로 재배분)
  - 200주MA는 일봉→주봉 리샘플 후 계산 (t 시점 이전 데이터만)

비용: 수수료 0.25%(코인원 일반, 보수 기준) + 슬리피지 0.2%.
자산 유니버스: 상장 전 자산은 제외하고 가중치를 잔여 자산에 재정규화
(SOL은 2020-08 Binance 상장 이후 편입).

실행: kairos_env/bin/python scripts/backtest_multiasset.py --start-every 91
"""
import argparse
import dataclasses
import os
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List

import numpy as np
import pandas as pd

from src.strategy.dca import DCAConfig, plan_weekly_dca
from src.strategy.rebalance import (
    RebalanceConfig,
    apply_crash_guard,
    plan_rebalance,
)
from src.strategy.valuation import (
    _TILT_MAYER_ANCHORS,
    MarketValuation,
    apply_relative_strength,
    contrarian_crypto_target,
    dca_multiplier,
)

WEEKLY_BASE_DCA = 250_000
INITIAL_KRW = 10_000_000
FEE = 0.0025      # 코인원 일반 수수료 (보수 기준 — 프로모션 티어 배제)
SLIPPAGE = 0.002
DEFAULT_WEIGHTS = {"BTC": 0.5, "ETH": 0.3, "XRP": 0.1, "SOL": 0.1}

CACHE_DIR = os.path.join(tempfile.gettempdir(), "kairos_multiasset_cache")
os.makedirs(CACHE_DIR, exist_ok=True)


@dataclass
class Result:
    final_value: float
    invested: float
    multiple: float
    max_drawdown: float
    sharpe: float
    total_trades: int
    total_volume_krw: float = 0.0   # 총 매매대금 (비용 = volume × 편도비용)
    daily_values: List[float] = field(default_factory=list)


def fetch_daily(symbol: str, start: str = "2017-08-01") -> pd.Series:
    """Binance 일봉 종가 (공개 API, 캐시)."""
    import requests

    cache = os.path.join(CACHE_DIR, f"{symbol}_1d.csv")
    if os.path.exists(cache):
        s = pd.read_csv(cache, index_col=0, parse_dates=True).iloc[:, 0]
        return s
    url = "https://api.binance.com/api/v3/klines"
    start_ms = int(pd.Timestamp(start, tz="UTC").timestamp() * 1000)
    rows = []
    cur = start_ms
    while True:
        r = requests.get(url, params={
            "symbol": symbol, "interval": "1d", "startTime": cur, "limit": 1000,
        }, timeout=30)
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        rows.extend(batch)
        cur = batch[-1][0] + 1
        if len(batch) < 1000:
            break
        time.sleep(0.15)
    idx = pd.to_datetime([b[0] for b in rows], unit="ms", utc=True)
    s = pd.Series([float(b[4]) for b in rows], index=idx, name="Close")
    s = s[~s.index.duplicated()]
    s.to_frame().to_csv(cache)
    return s


def _fg_proxy(ret_12w: float) -> int:
    return int(np.clip(50 + ret_12w * 100, 0, 100))


def _active_weights(base: Dict[str, float], available: List[str]) -> Dict[str, float]:
    """상장된 자산만으로 가중치 재정규화."""
    active = {a: w for a, w in base.items() if a in available}
    total = sum(active.values())
    return {a: w / total for a, w in active.items()}


def run(
    prices: Dict[str, pd.Series],
    start_idx: int,
    weights: Dict[str, float] = None,
    crypto_target: float = 0.60,
    contrarian_tilt: bool = True,
    relative_demotion: bool = True,
    demotion_update_days: int = 1,   # 편출 가중치 갱신 주기 (1=매일, 7=주간)
    relative_band: float = 0.20,
    crash_guard: bool = True,
    fomo_guard: bool = True,
    fee: float = FEE,
    slippage: float = SLIPPAGE,
    band_pp: float = 0.05,
    tilt_offsets: tuple = None,        # 실험용: _TILT_OFFSET_ANCHORS 대체
    overheat_alt_anchors: tuple = None,  # 실험용: (mayer앵커, 알트유지비율앵커)
    order_fraction: float = 1.0,       # 부분 리밸런싱 (운영 기본 0.5, 기준선 재현용 1.0)
) -> Result:
    weights = weights or DEFAULT_WEIGHTS
    cost = fee + slippage
    btc = prices["BTC"]
    dates = btc.index

    krw = float(INITIAL_KRW)
    qty: Dict[str, float] = {a: 0.0 for a in weights}
    trades = 0
    volume = 0.0
    values: List[float] = []
    deposits: List[float] = []  # TWR용 일별 외부 입금
    w_eff_cache: Dict[str, float] = None
    w_eff_age = 10**9

    # 주봉 종가(월요일 시작 주의 마지막 일봉) — 200주MA용
    btc_weekly = btc.resample("W-MON", label="left", closed="left").last().dropna()

    reb_base = RebalanceConfig(
        crypto_target=crypto_target, band_pp=band_pp, crypto_weights=weights,
        relative_band=relative_band, min_trade_krw=10_000,
        order_fraction=order_fraction,
    )
    dca_base = DCAConfig(
        base_amount_krw=WEEKLY_BASE_DCA, crypto_weights=weights,
        max_single_dca_krw=5 * WEEKLY_BASE_DCA, krw_usage_cap=0.25,
        min_order_krw=10_000,
    )

    for t in range(start_idx, len(dates)):
        date = dates[t]
        px = {a: float(s.iloc[s.index.searchsorted(date, side="right") - 1])
              if s.index[0] <= date else None
              for a, s in prices.items() if a in weights}
        available = [a for a, p in px.items() if p is not None and p > 0]
        w_active = _active_weights(weights, available)

        deposit = 0.0
        is_monday = date.weekday() == 0
        if is_monday:
            deposit = WEEKLY_BASE_DCA
            krw += deposit

        # ---- 밸류에이션 (t 이전 주봉만) ----
        hist_w = btc_weekly[btc_weekly.index <= date]
        mayer = mult = None
        if len(hist_w) >= 200:
            ma = float(hist_w.iloc[-200:].mean())
            mayer = float(btc.iloc[t]) / ma
            ret12 = (float(hist_w.iloc[-1] / hist_w.iloc[-13] - 1)
                     if len(hist_w) >= 13 else 0.0)
            mult = dca_multiplier(MarketValuation(_fg_proxy(ret12), mayer))

        if contrarian_tilt and mayer is not None:
            if tilt_offsets is not None:
                offset = float(np.interp(mayer, _TILT_MAYER_ANCHORS, tilt_offsets))
                target = min(1.0, max(0.0, crypto_target + offset))
            else:
                target = contrarian_crypto_target(mayer, crypto_target)
        else:
            target = crypto_target

        # ---- 상대강도 편출 (26주=182일 상대수익) ----
        w_eff = w_active
        if relative_demotion and len(w_active) > 1 and t >= 182:
            w_eff_age += 1
            if w_eff_cache is None or w_eff_age >= demotion_update_days:
                rel = {}
                ok = True
                for a in w_active:
                    if a == "BTC":
                        continue
                    s = prices[a]
                    i = s.index.searchsorted(date, side="right") - 1
                    j = i - 182
                    if j < 0:
                        ok = False
                        break
                    rel[a] = (float(s.iloc[i]) / float(s.iloc[j])) / (
                        float(btc.iloc[t]) / float(btc.iloc[t - 182])
                    ) - 1.0
                if ok and rel:
                    w_eff_cache = apply_relative_strength(w_active, rel)
                    w_eff_age = 0
            if w_eff_cache is not None and set(w_eff_cache) == set(w_active):
                w_eff = w_eff_cache

        # ---- 실험: 과열 시 알트→BTC 내부 구성 이동 ----
        if (overheat_alt_anchors is not None and mayer is not None
                and "BTC" in w_eff and len(w_eff) > 1):
            m_anchors, f_anchors = overheat_alt_anchors
            factor = float(np.interp(mayer, m_anchors, f_anchors))
            if factor < 1.0:
                shifted = {}
                freed = 0.0
                for a, w in w_eff.items():
                    if a == "BTC":
                        continue
                    shifted[a] = w * factor
                    freed += w * (1.0 - factor)
                shifted["BTC"] = w_eff["BTC"] + freed
                w_eff = shifted

        # ---- 24h 변동 (크래시/FOMO 가드) ----
        chg24: Dict[str, float] = {}
        for a in available:
            s = prices[a]
            i = s.index.searchsorted(date, side="right") - 1
            chg24[a] = float(s.iloc[i] / s.iloc[i - 1] - 1.0) if i >= 1 else 0.0

        holdings = {a: qty[a] * px[a] for a in available}
        crypto_value = sum(holdings.values())

        # ---- 주간 DCA (월요일, 목표 인지 상한) ----
        if is_monday and mult is not None:
            dca_cfg = dataclasses.replace(dca_base, crypto_weights=w_eff)
            for order in plan_weekly_dca(
                dca_cfg, mult, krw,
                crypto_value_krw=crypto_value, target_crypto_ratio=target,
            ):
                if order.asset not in px or px[order.asset] is None:
                    continue
                qty[order.asset] += order.amount_krw * (1 - cost) / px[order.asset]
                krw -= order.amount_krw
                trades += 1
                volume += order.amount_krw
            holdings = {a: qty[a] * px[a] for a in available}

        # ---- 일일 밴드 체크 ----
        reb_cfg = dataclasses.replace(
            reb_base, crypto_target=target, crypto_weights=w_eff
        )
        orders = plan_rebalance(reb_cfg, holdings, krw)
        if crash_guard and orders:
            orders = apply_crash_guard(
                orders, chg24, threshold=-0.10, buy_fraction=0.5,
                min_trade_krw=reb_cfg.min_trade_krw,
            )
        # 매도 먼저 (실운영 _execute_all과 동일)
        for order in sorted(orders, key=lambda o: o.side != "sell"):
            p = px.get(order.asset)
            if p is None:
                continue
            if order.side == "buy" and fomo_guard and chg24.get(order.asset, 0) >= 0.15:
                continue  # FOMO 가드: 급등 자산 리밸런싱 매수 금지
            if order.side == "sell":
                sell_qty = min(order.amount_krw / p, qty[order.asset])
                qty[order.asset] -= sell_qty
                krw += sell_qty * p * (1 - cost)
                volume += sell_qty * p
            else:
                spend = min(order.amount_krw, krw)
                if spend < reb_cfg.min_trade_krw:
                    continue
                qty[order.asset] += spend * (1 - cost) / p
                krw -= spend
                volume += spend
            trades += 1

        values.append(krw + sum(qty[a] * px[a] for a in available))
        deposits.append(deposit)

    series = pd.Series(values)
    dep = pd.Series(deposits)
    daily_ret = ((series - dep) / series.shift(1) - 1.0).dropna()
    sharpe = (float(daily_ret.mean() / daily_ret.std() * np.sqrt(365))
              if len(daily_ret) > 1 and daily_ret.std() > 0 else 0.0)
    twr = (1.0 + daily_ret).cumprod()
    mdd = float((twr / twr.cummax() - 1).min()) if len(twr) else 0.0
    n_mondays = int(sum(1 for d in dates[start_idx:] if d.weekday() == 0))
    invested = INITIAL_KRW + WEEKLY_BASE_DCA * n_mondays
    final = float(series.iloc[-1])
    return Result(
        final_value=final, invested=invested, multiple=final / invested,
        max_drawdown=mdd, sharpe=sharpe, total_trades=trades,
        total_volume_krw=volume, daily_values=values,
    )


def sweep(prices, starts, label, **kw):
    rows = []
    for s in starts:
        r = run(prices, s, **kw)
        rows.append(r)
    mults = [r.multiple for r in rows]
    mdds = [r.max_drawdown for r in rows]
    shs = [r.sharpe for r in rows]
    trs = [r.total_trades for r in rows]
    cost_pct = [r.total_volume_krw * (FEE + SLIPPAGE) / r.invested for r in rows]
    print(f"{label:<40} | 평균 {np.mean(mults):.2f}x (최악 {min(mults):.2f}x) | "
          f"최악MDD {min(mdds):+.1%} 평균 {np.mean(mdds):+.1%} | "
          f"Sharpe {np.mean(shs):.2f} | 거래 {np.mean(trs):.0f} | "
          f"비용 {np.mean(cost_pct):.1%}/원금")
    return rows


def main():
    parser = argparse.ArgumentParser(description="KAIROS 멀티자산 일봉 백테스트")
    parser.add_argument("--start-every", type=int, default=91,
                        help="시작점 간격(일), 기본 91일")
    parser.add_argument("--since", default="2017-08-01")
    args = parser.parse_args()

    symbols = {"BTC": "BTCUSDT", "ETH": "ETHUSDT", "XRP": "XRPUSDT", "SOL": "SOLUSDT"}
    prices = {}
    for a, sym in symbols.items():
        s = fetch_daily(sym, args.since)
        prices[a] = s
        print(f"  {a}: {len(s)}일 ({s.index[0].date()} ~ {s.index[-1].date()})")

    n = len(prices["BTC"])
    # 시작점: 200주MA 워밍업이 필요 없도록(내부에서 처리) 전 구간 스윕,
    # 마지막 1년은 표본 짧아 제외
    starts = list(range(0, n - 365, args.start_every))
    print(f"\n시작점 {len(starts)}개 (간격 {args.start_every}일), "
          f"비용: 수수료 {FEE:.2%} + 슬리피지 {SLIPPAGE:.2%}\n")

    print("== 포트폴리오 구성 비교 ==")
    sweep(prices, starts, "현행 4코인 (BTC50/ETH30/XRP10/SOL10)")
    sweep(prices, starts, "BTC 단독", weights={"BTC": 1.0})
    sweep(prices, starts, "BTC+ETH (62.5/37.5)",
          weights={"BTC": 0.625, "ETH": 0.375})
    sweep(prices, starts, "BTC 중심 (70/20/5/5)",
          weights={"BTC": 0.7, "ETH": 0.2, "XRP": 0.05, "SOL": 0.05})

    print("\n== 컴포넌트 ablation (현행 4코인) ==")
    sweep(prices, starts, "상대강도 편출 OFF", relative_demotion=False)
    sweep(prices, starts, "크래시 가드 OFF", crash_guard=False)
    sweep(prices, starts, "FOMO 가드 OFF", fomo_guard=False)
    sweep(prices, starts, "틸트 OFF", contrarian_tilt=False)

    print("\n== 회전율 진단 — 편출·상대밴드 변형 ==")
    sweep(prices, starts, "편출 주간 갱신 (demotion 7d)", demotion_update_days=7)
    sweep(prices, starts, "편출 OFF + 상대밴드 0.30",
          relative_demotion=False, relative_band=0.30)
    sweep(prices, starts, "편출 OFF + 상대밴드 0.40",
          relative_demotion=False, relative_band=0.40)
    sweep(prices, starts, "편출 주간 + 상대밴드 0.30",
          demotion_update_days=7, relative_band=0.30)
    sweep(prices, starts, "편출 주간 + 상대밴드 0.40",
          demotion_update_days=7, relative_band=0.40)


if __name__ == "__main__":
    main()
