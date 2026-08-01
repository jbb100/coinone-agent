"""[폐기됨] KAIROS-Alpha 백테스트 — 횡보장 평균 회귀 스윙 (설계안 검증용).

결과: 불합격 — 15개 변형 전부 PF < 1, 비용 제로에서도 신호 엣지 음수.
상세: docs/superpowers/specs/2026-08-01-short-term-alpha-validation.md

설계 로직 그대로:
- 레짐: BTC 일봉 ADX(14) < 25 AND |종가/50일SMA - 1| <= 10% → 횡보
- 진입: 4h봉 RSI(14, Wilder) < 30 AND 종가 <= BB(20,2) 하단 AND (중심-하단)/하단 >= 1.5%
- 청산: 종가 >= BB 중심(익절) | 진입가 -3%(손절) | 42봉=7일(타임스톱)
- 사이징: 버킷 자본의 50% (리스크 1.5% / 손절폭 3%), 동시 2포지션
- 비용: 수수료 0.2% + 슬리피지 0.2% (편도 0.4%)
- 체결: 신호봉 종가 확정 후 다음 봉 시가 체결 (look-ahead 차단)
"""
import json
import os
import tempfile
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests

CACHE_DIR = os.path.join(tempfile.gettempdir(), "alpha_mr_klines_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

ASSETS = ["BTC", "ETH", "XRP", "SOL"]
START = "2021-01-01"
END = "2026-08-01"

FEE = 0.002
SLIP = 0.002
COST = FEE + SLIP  # 편도

RSI_ENTRY = 30.0
STOP = 0.03
TIME_STOP_BARS = 42          # 7일 × 6봉/일
MIN_BAND_EDGE = 0.015        # (mid-lower)/lower 하한
RISK_PER_TRADE = 0.015
POS_FRAC = RISK_PER_TRADE / STOP   # 0.5
MAX_POS = 2
ADX_MAX = 25.0
MA_DIST_MAX = 0.10


def fetch_klines(symbol: str, interval: str, start: str, end: str) -> pd.DataFrame:
    cache = os.path.join(CACHE_DIR, f"{symbol}_{interval}.csv")
    if os.path.exists(cache):
        df = pd.read_csv(cache, index_col=0, parse_dates=True)
        return df
    url = "https://api.binance.com/api/v3/klines"
    start_ms = int(pd.Timestamp(start, tz="UTC").timestamp() * 1000)
    end_ms = int(pd.Timestamp(end, tz="UTC").timestamp() * 1000)
    rows = []
    cur = start_ms
    while cur < end_ms:
        r = requests.get(url, params={
            "symbol": symbol, "interval": interval,
            "startTime": cur, "endTime": end_ms, "limit": 1000,
        }, timeout=30)
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        rows.extend(batch)
        cur = batch[-1][0] + 1
        time.sleep(0.15)
    df = pd.DataFrame(rows, columns=[
        "open_time", "Open", "High", "Low", "Close", "Volume",
        "close_time", "qv", "n", "tbb", "tbq", "ig"])
    df["ts"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df = df.set_index("ts")[["Open", "High", "Low", "Close", "Volume"]].astype(float)
    df = df[~df.index.duplicated(keep="first")]
    df.to_csv(cache)
    return df


def rsi_wilder(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - 100 / (1 + rs)
    return rsi.where(avg_loss != 0, 100.0)


def adx_wilder(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["High"], df["Low"], df["Close"]
    up = high.diff()
    down = -low.diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, min_periods=period, adjust=False).mean() / atr
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, min_periods=period, adjust=False).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    return dx.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def build_regime(btc_daily: pd.DataFrame) -> pd.Series:
    adx = adx_wilder(btc_daily, 14)
    sma50 = btc_daily["Close"].rolling(50).mean()
    dist = (btc_daily["Close"] / sma50 - 1.0).abs()
    sideways = (adx < ADX_MAX) & (dist <= MA_DIST_MAX)
    return sideways


def prep_asset(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["rsi"] = rsi_wilder(out["Close"])
    out["bb_mid"] = out["Close"].rolling(20).mean()
    std = out["Close"].rolling(20).std(ddof=0)
    out["bb_lower"] = out["bb_mid"] - 2 * std
    out["band_edge"] = (out["bb_mid"] - out["bb_lower"]) / out["bb_lower"]
    return out


def run_backtest(data: dict, regime_daily: pd.Series, use_regime: bool = True,
                 rsi_entry: float = RSI_ENTRY, stop: float = STOP,
                 min_band: float = MIN_BAND_EDGE, verbose: bool = False):
    # 공통 4h 타임라인
    timeline = sorted(set().union(*[set(d.index) for d in data.values()]))
    # 레짐: 각 4h 시점에서 '그 이전에 마감된' 일봉 기준 (look-ahead 방지: 일봉 open_time+1d <= t)
    regime_shifted = regime_daily.copy()
    regime_shifted.index = regime_shifted.index + pd.Timedelta(days=1)
    regime_at = regime_shifted.reindex(timeline, method="ffill").fillna(False)

    equity = 1.0
    positions = {}   # asset -> dict(entry_px, qty_frac(=투입 equity 비율 아님, 명목), stop_px, bars, cost_basis)
    trades = []
    equity_curve = []
    pos_frac = RISK_PER_TRADE / stop

    idx_map = {a: {t: i for i, t in enumerate(d.index)} for a, d in data.items()}

    for t in timeline:
        # 1) 청산 체크 (현재 봉 t 진행: 시가/저가/종가 사용 — 진입은 t 이전 봉 신호만)
        for asset in list(positions.keys()):
            d = data[asset]
            if t not in idx_map[asset]:
                continue
            i = idx_map[asset][t]
            row = d.iloc[i]
            p = positions[asset]
            p["bars"] += 1
            exit_px, reason = None, None
            if row["Low"] <= p["stop_px"]:
                exit_px = min(row["Open"], p["stop_px"]) * (1 - SLIP)
                reason = "stop"
            elif not np.isnan(row["bb_mid"]) and row["Close"] >= row["bb_mid"]:
                # 신호는 종가 확정, 체결은 다음 봉 시가
                if i + 1 < len(d):
                    exit_px = d.iloc[i + 1]["Open"] * (1 - SLIP)
                    reason = "target"
            elif p["bars"] >= TIME_STOP_BARS:
                if i + 1 < len(d):
                    exit_px = d.iloc[i + 1]["Open"] * (1 - SLIP)
                    reason = "timestop"
            if exit_px is not None:
                gross = exit_px / p["entry_px"] - 1.0
                net = (1 + gross) * (1 - FEE) - 1.0   # 매도 수수료
                pnl = p["alloc"] * net
                equity += pnl
                trades.append({
                    "asset": asset, "entry_t": p["entry_t"], "exit_t": t,
                    "entry_px": p["entry_px"], "exit_px": exit_px,
                    "net_ret": net, "pnl": pnl, "reason": reason,
                    "bars": p["bars"],
                })
                del positions[asset]

        # 2) 진입 스캔 (신호: 직전 마감봉 = t 시점에서 인덱스 i-1)
        if len(positions) < MAX_POS and (regime_at.loc[t] or not use_regime):
            for asset in ASSETS:
                if asset in positions or len(positions) >= MAX_POS:
                    continue
                d = data[asset]
                if t not in idx_map[asset]:
                    continue
                i = idx_map[asset][t]
                if i < 1:
                    continue
                sig = d.iloc[i - 1]
                if (not np.isnan(sig["rsi"]) and sig["rsi"] < rsi_entry
                        and sig["Close"] <= sig["bb_lower"]
                        and sig["band_edge"] >= min_band):
                    entry_px = d.iloc[i]["Open"] * (1 + SLIP)
                    alloc = equity * pos_frac
                    alloc_net = alloc * (1 - FEE)  # 매수 수수료
                    positions[asset] = {
                        "entry_t": t, "entry_px": entry_px,
                        "stop_px": entry_px * (1 - stop),
                        "alloc": alloc_net, "bars": 0,
                    }
        equity_curve.append((t, equity))

    # 미청산 포지션 마지막 종가 청산
    for asset, p in positions.items():
        d = data[asset]
        last = d.iloc[-1]
        exit_px = last["Close"] * (1 - SLIP)
        gross = exit_px / p["entry_px"] - 1.0
        net = (1 + gross) * (1 - FEE) - 1.0
        equity += p["alloc"] * net
        trades.append({"asset": asset, "entry_t": p["entry_t"], "exit_t": d.index[-1],
                       "entry_px": p["entry_px"], "exit_px": exit_px,
                       "net_ret": net, "pnl": p["alloc"] * net, "reason": "eod", "bars": p["bars"]})

    ec = pd.Series(dict(equity_curve)).sort_index()
    return trades, ec, regime_at


def summarize(name, trades, ec, regime_at=None):
    tdf = pd.DataFrame(trades)
    out = {"name": name, "final_equity": round(float(ec.iloc[-1]), 4)}
    if tdf.empty:
        out["trades"] = 0
        return out
    wins = tdf[tdf["pnl"] > 0]
    losses = tdf[tdf["pnl"] <= 0]
    dd = (ec / ec.cummax() - 1.0).min()
    years = (ec.index[-1] - ec.index[0]).days / 365.25
    out.update({
        "trades": len(tdf),
        "win_rate": round(len(wins) / len(tdf), 3),
        "profit_factor": round(float(wins["pnl"].sum() / abs(losses["pnl"].sum())), 2)
        if len(losses) and losses["pnl"].sum() != 0 else float("inf"),
        "total_return_pct": round((float(ec.iloc[-1]) - 1) * 100, 2),
        "cagr_pct": round((float(ec.iloc[-1]) ** (1 / years) - 1) * 100, 2),
        "max_dd_pct": round(float(dd) * 100, 2),
        "avg_trade_pct": round(float(tdf["net_ret"].mean()) * 100, 3),
        "avg_hold_days": round(float(tdf["bars"].mean()) / 6, 1),
        "exit_reasons": tdf["reason"].value_counts().to_dict(),
        "by_asset": tdf.groupby("asset")["pnl"].agg(["count", "sum"]).round(4).to_dict("index"),
    })
    tdf["year"] = pd.to_datetime(tdf["exit_t"]).dt.year
    out["yearly_pnl"] = tdf.groupby("year")["pnl"].sum().round(4).to_dict()
    out["yearly_trades"] = tdf.groupby("year")["pnl"].count().to_dict()
    if regime_at is not None:
        out["pct_time_sideways"] = round(float(regime_at.mean()) * 100, 1)
    return out


def main():
    print("데이터 수집 중...", flush=True)
    btc_daily = fetch_klines("BTCUSDT", "1d", START, END)
    data = {}
    for a in ASSETS:
        raw = fetch_klines(f"{a}USDT", "4h", START, END)
        data[a] = prep_asset(raw)
        print(f"  {a}: {len(raw)} 4h candles ({raw.index[0].date()} ~ {raw.index[-1].date()})")
    regime = build_regime(btc_daily)

    results = []
    trades, ec, regime_at = run_backtest(data, regime, use_regime=True)
    results.append(summarize("기본안 (레짐 필터 ON)", trades, ec, regime_at))
    pd.DataFrame(trades).to_csv(os.path.join(CACHE_DIR, "trades_base.csv"), index=False)

    t2, ec2, _ = run_backtest(data, regime, use_regime=False)
    results.append(summarize("레짐 필터 OFF (비교용)", t2, ec2))

    # 민감도
    for label, kw in [
        ("RSI<25", {"rsi_entry": 25}),
        ("RSI<35", {"rsi_entry": 35}),
        ("손절 2%", {"stop": 0.02}),
        ("손절 4%", {"stop": 0.04}),
        ("밴드폭 필터 OFF", {"min_band": 0.0}),
    ]:
        tt, ee, _ = run_backtest(data, regime, use_regime=True, **kw)
        results.append(summarize(f"민감도: {label}", tt, ee))

    print(json.dumps(results, indent=2, ensure_ascii=False, default=str))

    # 연도별 자본곡선 저장
    ec.to_csv(os.path.join(CACHE_DIR, "equity_base.csv"))


if __name__ == "__main__":
    main()
