"""[연구] 2026-08-04 감사 2라운드 — 후보 개선안 페어 검증.

기준선: PR #18 채택 구성 (편출 -50/-70, 상대밴드 0.30, band_pp 0.05).
후보:
  1) band_pp 스윕 (0.04 / 0.07 / 0.10) — 한 번도 스윕된 적 없는 파라미터
  2) 과열 시 알트→BTC 내부 구성 이동 (고베타 알트의 하락장 노출 축소)
  3) 매도 틸트 심화/조기화 (-30%p 심화, 2.1부터 -15%p 조기)

관문(기존과 동일): 32개 시작점 페어 비교에서
  배수 악화(Δ<-0.02) / MDD 1%p 이상 악화 / Sharpe 0.05 이상 악화 윈도우 수.

실행: kairos_env/bin/python scripts/research/audit_round2.py
"""
import sys

import numpy as np

sys.path.insert(0, ".")
from scripts.backtest_multiasset import fetch_daily, run  # noqa: E402

BASE_KW = dict(relative_band=0.30)

VARIANTS = {
    "band_pp 0.04": dict(band_pp=0.04),
    "band_pp 0.07": dict(band_pp=0.07),
    "band_pp 0.10": dict(band_pp=0.10),
    "알트이동 온건 (2.1+→0.7, 3.1→0.5)": dict(
        overheat_alt_anchors=((1.9, 2.1, 2.9, 3.1), (1.0, 0.7, 0.7, 0.5))),
    "알트이동 강 (2.1+→0.5, 3.1→0.25)": dict(
        overheat_alt_anchors=((1.9, 2.1, 2.9, 3.1), (1.0, 0.5, 0.5, 0.25))),
    "알트이동 조기 (1.5→1.0, 2.5→0.5)": dict(
        overheat_alt_anchors=((1.5, 2.5), (1.0, 0.5))),
    "매도 심화 (3.1→-30%p)": dict(
        tilt_offsets=(0.20, 0.15, 0.10, 0.0, 0.0, -0.10, -0.10, -0.30)),
    "매도 조기+심화 (2.1→-15, 3.1→-30%p)": dict(
        tilt_offsets=(0.20, 0.15, 0.10, 0.0, 0.0, -0.15, -0.15, -0.30)),
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
    print(f"시작점 {len(starts)}개, 데이터 ~{prices['BTC'].index[-1].date()}\n")

    base_rows = [run(prices, s, **BASE_KW) for s in starts]
    m, dd, wdd, sh, c = stats(base_rows)
    print(f"{'기준선 (채택 구성)':<42} | {m:.2f}x | 평균MDD {dd:+.1%} "
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
        print(f"{name:<42} | {m:.2f}x | 평균MDD {dd:+.1%} "
              f"(최악 {wdd:+.1%}) | Sharpe {sh:.2f} | 비용 {c:.1%} | "
              f"악화[배수 {worse_mult} MDD {worse_mdd} Sharpe {worse_sh}]/"
              f"{len(starts)} | Δ배수 [{min(d_mult):+.3f},{max(d_mult):+.3f}] "
              f"ΔMDD [{min(d_mdd):+.1%},{max(d_mdd):+.1%}]")


if __name__ == "__main__":
    main()
