"""[연구] 감사 2라운드-b OOS — band_pp 확대를 Bitstamp 2011~ 주봉으로 검증.

밴드가 넓으면 파라볼릭 버블(2013/2017, Mayer>3)에서 과열 익절이 지연된다
— 일봉 in-sample(2021+ 틸트 활성)에는 없는 시나리오라 OOS 필수.

실행: kairos_env/bin/python scripts/research/audit_round2b_oos.py
"""
import sys

import numpy as np

sys.path.insert(0, ".")
from scripts.backtest_longterm import fetch_bitstamp_weekly, sweep_starts  # noqa: E402

BANDS = [0.07, 0.10, 0.15]


def main():
    df = fetch_bitstamp_weekly()
    print(f"Bitstamp 주봉 {len(df)}주 ({df.index[0].date()} ~ {df.index[-1].date()})")
    starts = list(range(0, len(df) - 52, 24))
    inv = [10_000_000 + 250_000 * (len(df) - s) for s in starts]

    base = [r for _, _, r in sweep_starts(df, starts, band_pp=0.05)]
    bm = [r.final_value / i for r, i in zip(base, inv)]
    print(f"{'기준선 band 0.05':<20} | {np.mean(bm):.2f}x | "
          f"평균MDD {np.mean([r.max_drawdown for r in base]):+.1%} "
          f"(최악 {min(r.max_drawdown for r in base):+.1%}) | "
          f"Sharpe {np.mean([r.sharpe for r in base]):.2f}")

    for band in BANDS:
        rows = [r for _, _, r in sweep_starts(df, starts, band_pp=band)]
        vm = [r.final_value / i for r, i in zip(rows, inv)]
        worse_mult = sum(1 for a, b in zip(bm, vm) if b - a < -0.02)
        worse_mdd = sum(1 for a, b in zip(base, rows)
                        if b.max_drawdown - a.max_drawdown < -0.01)
        worse_sh = sum(1 for a, b in zip(base, rows)
                       if b.sharpe - a.sharpe < -0.05)
        d_m = [b - a for a, b in zip(bm, vm)]
        d_dd = [b.max_drawdown - a.max_drawdown for a, b in zip(base, rows)]
        print(f"band {band:<15} | {np.mean(vm):.2f}x | "
              f"평균MDD {np.mean([r.max_drawdown for r in rows]):+.1%} "
              f"(최악 {min(r.max_drawdown for r in rows):+.1%}) | "
              f"Sharpe {np.mean([r.sharpe for r in rows]):.2f} | "
              f"악화[배수 {worse_mult} MDD {worse_mdd} Sharpe {worse_sh}]"
              f"/{len(starts)} | Δ배수 [{min(d_m):+.3f},{max(d_m):+.3f}] "
              f"ΔMDD [{min(d_dd):+.1%},{max(d_dd):+.1%}]")


if __name__ == "__main__":
    main()
