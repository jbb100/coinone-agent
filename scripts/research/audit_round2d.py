"""[연구] 감사 2라운드-d — 부분 리밸런싱 비율 민감도 (weekly OOS).

B(0.5)의 OOS Sharpe 위반 2개의 실제 크기와, 0.6/0.7에서의 소멸 여부.

실행: kairos_env/bin/python scripts/research/audit_round2d.py
"""
import sys

import numpy as np

sys.path.insert(0, ".")
from scripts.backtest_longterm import fetch_bitstamp_weekly, sweep_starts  # noqa: E402


def main():
    df = fetch_bitstamp_weekly()
    starts = list(range(0, len(df) - 52, 24))
    inv = [10_000_000 + 250_000 * (len(df) - s) for s in starts]

    base = [r for _, _, r in sweep_starts(df, starts)]
    bm = [r.final_value / i for r, i in zip(base, inv)]

    for frac in (0.5, 0.6, 0.7):
        rows = [r for _, _, r in sweep_starts(df, starts, order_fraction=frac)]
        vm = [r.final_value / i for r, i in zip(rows, inv)]
        d_sh = [b.sharpe - a.sharpe for a, b in zip(base, rows)]
        d_dd = [b.max_drawdown - a.max_drawdown for a, b in zip(base, rows)]
        d_m = [b - a for a, b in zip(bm, vm)]
        viol = [(df.index[starts[i]].date(), round(d_sh[i], 3),
                 round(base[i].sharpe, 2))
                for i in range(len(d_sh)) if d_sh[i] < -0.05]
        print(f"fraction {frac} | {np.mean(vm):.2f}x | "
              f"평균MDD {np.mean([r.max_drawdown for r in rows]):+.1%} | "
              f"Sharpe {np.mean([r.sharpe for r in rows]):.2f} | "
              f"Δ배수min {min(d_m):+.3f} ΔMDDmin {min(d_dd):+.1%} "
              f"ΔSharpe min {min(d_sh):+.3f} | Sharpe위반 {viol}")


if __name__ == "__main__":
    main()
