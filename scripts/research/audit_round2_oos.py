"""[연구] 감사 2라운드 OOS — 매도 틸트 변형의 주봉 BTC 검증.

멀티자산 일봉(Binance)은 200주MA 워밍업 탓에 틸트가 2021-06 이후에만
활성 — Mayer가 2.9/3.1 심화 앵커에 도달한 적이 없어(최고 ~2.4) 매도측
변형은 in-sample에서 분별 불가. 2013/2017 파라볼릭 버블(Mayer>3)을 포함한
Bitstamp 2011~ 주봉이 유일한 판별 데이터다.

실행: kairos_env/bin/python scripts/research/audit_round2_oos.py
"""
import sys

import numpy as np

sys.path.insert(0, ".")
import src.strategy.valuation as valuation  # noqa: E402
from scripts.backtest_longterm import fetch_bitstamp_weekly, sweep_starts  # noqa: E402

VARIANTS = {
    "매도 심화 (3.1→-30%p)": (0.20, 0.15, 0.10, 0.0, 0.0, -0.10, -0.10, -0.30),
    "매도 조기+심화 (2.1→-15, 3.1→-30%p)": (0.20, 0.15, 0.10, 0.0, 0.0, -0.15, -0.15, -0.30),
    "매도 조기 (2.1→-15, 3.1→-20%p)": (0.20, 0.15, 0.10, 0.0, 0.0, -0.15, -0.15, -0.20),
}


def run_sweep(df, starts):
    return [r for _, _, r in sweep_starts(df, starts)]


def main():
    df = fetch_bitstamp_weekly()
    print(f"Bitstamp 주봉 {len(df)}주 ({df.index[0].date()} ~ {df.index[-1].date()})")
    starts = list(range(0, len(df) - 52, 24))
    print(f"시작점 {len(starts)}개\n")

    baseline_anchors = valuation._TILT_OFFSET_ANCHORS
    base = run_sweep(df, starts)
    inv = [10_000_000 + 250_000 * (len(df) - s) for s in starts]
    bm = [r.final_value / i for r, i in zip(base, inv)]
    print(f"{'기준선 (현행 앵커)':<40} | {np.mean(bm):.2f}x | "
          f"평균MDD {np.mean([r.max_drawdown for r in base]):+.1%} "
          f"(최악 {min(r.max_drawdown for r in base):+.1%}) | "
          f"Sharpe {np.mean([r.sharpe for r in base]):.2f}")

    for name, anchors in VARIANTS.items():
        valuation._TILT_OFFSET_ANCHORS = anchors
        rows = run_sweep(df, starts)
        valuation._TILT_OFFSET_ANCHORS = baseline_anchors
        vm = [r.final_value / i for r, i in zip(rows, inv)]
        worse_mult = sum(1 for a, b in zip(bm, vm) if b - a < -0.02)
        worse_mdd = sum(1 for a, b in zip(base, rows)
                        if b.max_drawdown - a.max_drawdown < -0.01)
        worse_sh = sum(1 for a, b in zip(base, rows)
                       if b.sharpe - a.sharpe < -0.05)
        d_m = [b - a for a, b in zip(bm, vm)]
        print(f"{name:<40} | {np.mean(vm):.2f}x | "
              f"평균MDD {np.mean([r.max_drawdown for r in rows]):+.1%} "
              f"(최악 {min(r.max_drawdown for r in rows):+.1%}) | "
              f"Sharpe {np.mean([r.sharpe for r in rows]):.2f} | "
              f"악화[배수 {worse_mult} MDD {worse_mdd} Sharpe {worse_sh}]"
              f"/{len(starts)} | Δ배수 [{min(d_m):+.3f},{max(d_m):+.3f}]")


if __name__ == "__main__":
    main()
