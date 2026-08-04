"""[연구] 감사 2라운드-b — band_pp 확대의 민감도·과적합 점검 + 부분 리밸런싱.

2a 결과 band_pp 0.07/0.10이 전 지표 개선 → 두 가지 검증 추가:
  1) 민감도: 0.15까지 계속 좋아지면 "리밸런싱 축소 = 상승 표본 베타 편승"
     의심 (플래토가 있어야 구조적 개선)
  2) 부분 리밸런싱(order_fraction 0.5): 비용 절감의 다른 경로와 비교

실행: kairos_env/bin/python scripts/research/audit_round2b.py
"""
import sys

import numpy as np

sys.path.insert(0, ".")
from scripts.backtest_multiasset import fetch_daily, run  # noqa: E402

BASE_KW = dict(relative_band=0.30)

VARIANTS = {
    "band_pp 0.08": dict(band_pp=0.08),
    "band_pp 0.12": dict(band_pp=0.12),
    "band_pp 0.15": dict(band_pp=0.15),
    "부분 리밸런싱 0.5 (band 0.05)": dict(order_fraction=0.5),
    "band 0.10 + 부분 0.5": dict(band_pp=0.10, order_fraction=0.5),
}


def stats(rows):
    return (np.mean([r.multiple for r in rows]),
            np.mean([r.max_drawdown for r in rows]),
            min(r.max_drawdown for r in rows),
            np.mean([r.sharpe for r in rows]),
            np.mean([r.total_volume_krw * 0.0045 / r.invested for r in rows]))


def main():
    symbols = {"BTC": "BTCUSDT", "ETH": "ETHUSDT", "XRP": "XRPUSDT", "SOL": "SOLUSDT"}
    prices = {a: fetch_daily(sym) for a, sym in symbols.items()}
    n = len(prices["BTC"])
    starts = list(range(0, n - 365, 91))

    base_rows = [run(prices, s, **BASE_KW) for s in starts]
    m, dd, wdd, sh, c = stats(base_rows)
    print(f"{'기준선 (band 0.05)':<34} | {m:.2f}x | 평균MDD {dd:+.1%} "
          f"(최악 {wdd:+.1%}) | Sharpe {sh:.2f} | 비용 {c:.1%}")

    for name, kw in VARIANTS.items():
        rows = [run(prices, s, **BASE_KW, **kw) for s in starts]
        m, dd, wdd, sh, c = stats(rows)
        worse_mult = sum(1 for a, b in zip(base_rows, rows)
                         if b.multiple - a.multiple < -0.02)
        worse_mdd = sum(1 for a, b in zip(base_rows, rows)
                        if b.max_drawdown - a.max_drawdown < -0.01)
        worse_sh = sum(1 for a, b in zip(base_rows, rows)
                       if b.sharpe - a.sharpe < -0.05)
        d_mult = [b.multiple - a.multiple for a, b in zip(base_rows, rows)]
        d_mdd = [b.max_drawdown - a.max_drawdown for a, b in zip(base_rows, rows)]
        print(f"{name:<34} | {m:.2f}x | 평균MDD {dd:+.1%} "
              f"(최악 {wdd:+.1%}) | Sharpe {sh:.2f} | 비용 {c:.1%} | "
              f"악화[배수 {worse_mult} MDD {worse_mdd} Sharpe {worse_sh}]/"
              f"{len(starts)} | Δ배수 [{min(d_mult):+.3f},{max(d_mult):+.3f}] "
              f"ΔMDD [{min(d_mdd):+.1%},{max(d_mdd):+.1%}]")


if __name__ == "__main__":
    main()
