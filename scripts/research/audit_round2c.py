"""[연구] 감사 2라운드-c — 최종 후보 조합의 in-sample/OOS 동시 검증.

후보 (2a/2b에서 관문 통과 또는 근접):
  A) band_pp 0.08                — in-sample 청정 (0/0/0)
  B) 부분 리밸런싱 0.5 (band 0.05) — in-sample 청정 (0/0/0)
  C) band 0.08 + 부분 0.5
  D) band 0.10 + 부분 0.5         — 비용 최저(2.2%), Sharpe 1개 위반

--mode multi  : Binance 일봉 4자산 32개 시작점 (in-sample)
--mode weekly : Bitstamp 2011~ 주봉 BTC 31개 시작점 (OOS, 버블 포함)

실행: kairos_env/bin/python scripts/research/audit_round2c.py --mode weekly
"""
import argparse
import sys

import numpy as np

sys.path.insert(0, ".")

CANDIDATES = {
    "A band 0.08": dict(band_pp=0.08),
    "B 부분 0.5": dict(order_fraction=0.5),
    "C band 0.08 + 부분 0.5": dict(band_pp=0.08, order_fraction=0.5),
    "D band 0.10 + 부분 0.5": dict(band_pp=0.10, order_fraction=0.5),
}


def report(name, base_tuples, var_tuples, n):
    bm, bdd, bsh = base_tuples
    vm, vdd, vsh = var_tuples
    worse_mult = sum(1 for a, b in zip(bm, vm) if b - a < -0.02)
    worse_mdd = sum(1 for a, b in zip(bdd, vdd) if b - a < -0.01)
    worse_sh = sum(1 for a, b in zip(bsh, vsh) if b - a < -0.05)
    d_m = [b - a for a, b in zip(bm, vm)]
    d_dd = [b - a for a, b in zip(bdd, vdd)]
    print(f"{name:<24} | {np.mean(vm):.2f}x | 평균MDD {np.mean(vdd):+.1%} "
          f"(최악 {min(vdd):+.1%}) | Sharpe {np.mean(vsh):.2f} | "
          f"악화[배수 {worse_mult} MDD {worse_mdd} Sharpe {worse_sh}]/{n} | "
          f"Δ배수 [{min(d_m):+.3f},{max(d_m):+.3f}] "
          f"ΔMDD [{min(d_dd):+.1%},{max(d_dd):+.1%}]")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["multi", "weekly"], default="weekly")
    args = parser.parse_args()

    if args.mode == "weekly":
        from scripts.backtest_longterm import fetch_bitstamp_weekly, sweep_starts
        df = fetch_bitstamp_weekly()
        starts = list(range(0, len(df) - 52, 24))
        inv = [10_000_000 + 250_000 * (len(df) - s) for s in starts]

        def run_all(**kw):
            rows = [r for _, _, r in sweep_starts(df, starts, **kw)]
            return ([r.final_value / i for r, i in zip(rows, inv)],
                    [r.max_drawdown for r in rows], [r.sharpe for r in rows])
    else:
        from scripts.backtest_multiasset import fetch_daily, run
        symbols = {"BTC": "BTCUSDT", "ETH": "ETHUSDT",
                   "XRP": "XRPUSDT", "SOL": "SOLUSDT"}
        prices = {a: fetch_daily(sym) for a, sym in symbols.items()}
        starts = list(range(0, len(prices["BTC"]) - 365, 91))

        def run_all(**kw):
            rows = [run(prices, s, relative_band=0.30, **kw) for s in starts]
            return ([r.multiple for r in rows],
                    [r.max_drawdown for r in rows], [r.sharpe for r in rows])

    base = run_all()
    print(f"{'기준선':<24} | {np.mean(base[0]):.2f}x | "
          f"평균MDD {np.mean(base[1]):+.1%} (최악 {min(base[1]):+.1%}) | "
          f"Sharpe {np.mean(base[2]):.2f}   [n={len(base[0])}]")
    for name, kw in CANDIDATES.items():
        report(name, base, run_all(**kw), len(base[0]))


if __name__ == "__main__":
    main()
