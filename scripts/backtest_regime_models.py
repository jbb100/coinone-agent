#!/usr/bin/env python3
"""
국면 모델 백테스트 (Phase 5)

legacy(200주 MA 추세추종) vs valuation(가치 앵커 — 저평가 매집/고평가 분배) 모델을
실제 BTC 주간 데이터로 비교한다.

Real-Data-Only 원칙:
- 실제 거래소/시장 데이터(Binance, 실패 시 CoinGecko)만 사용
- 데이터를 얻지 못하면 백테스트를 중단한다 (합성 데이터 생성 금지)

방법론:
- 자산: BTC + 현금 (단순화 — 알트코인은 2018년 이전 데이터가 없어 제외)
- 주기: 주 1회 국면 평가, 비중 편차 5% 초과 시에만 리밸런싱 (REBALANCE_THRESHOLD)
- 비용: 거래 금액의 0.2% (코인원 수수료 수준, 왕복 아님)
- 과최적화 방지: 2023-01-01 기준으로 학습(in-sample)/검증(out-of-sample) 분리.
  파라미터 격자 탐색은 학습 구간에서만 수행하고 검증 구간 성과로 판단한다.

실행:
    python scripts/backtest_regime_models.py
결과:
    docs/BACKTEST_REGIME_MODELS.md
"""

import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.market_season_filter import MarketSeasonFilter, MarketSeason
from src.core.market_valuation_filter import MarketValuationFilter, ValuationPhase

TRADE_FEE = 0.002              # 0.2% per trade
REBALANCE_THRESHOLD = 0.05     # 비중 편차 5% 초과 시에만 매매
OOS_SPLIT_DATE = "2023-01-01"  # in-sample / out-of-sample 분리 기준
WEEKS_PER_YEAR = 52


# ---------------------------------------------------------------------------
# 데이터 수집 (실데이터만)
# ---------------------------------------------------------------------------

def fetch_btc_weekly_binance() -> Optional[pd.Series]:
    """Binance BTCUSDT 주봉 종가 (2017-08부터)"""
    try:
        all_rows = []
        start_ms = 1500000000000  # 2017-07
        while True:
            r = requests.get(
                "https://api.binance.com/api/v3/klines",
                params={"symbol": "BTCUSDT", "interval": "1w",
                        "startTime": start_ms, "limit": 1000},
                timeout=20,
            )
            r.raise_for_status()
            rows = r.json()
            if not rows:
                break
            all_rows.extend(rows)
            if len(rows) < 1000:
                break
            start_ms = rows[-1][6] + 1  # close time + 1ms

        if not all_rows:
            return None

        idx = pd.to_datetime([r[0] for r in all_rows], unit="ms", utc=True)
        closes = pd.Series([float(r[4]) for r in all_rows], index=idx, name="Close")
        # 마지막(미완성) 주봉 제거
        return closes.iloc[:-1]
    except Exception as e:
        print(f"[data] Binance 실패: {e}")
        return None


def fetch_btc_weekly_coingecko() -> Optional[pd.Series]:
    """CoinGecko BTC/USD 일간 → 주간 리샘플 (2013-04부터)"""
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart",
            params={"vs_currency": "usd", "days": "max", "interval": "daily"},
            timeout=30,
        )
        r.raise_for_status()
        prices = r.json().get("prices", [])
        if not prices:
            return None
        idx = pd.to_datetime([p[0] for p in prices], unit="ms", utc=True)
        daily = pd.Series([float(p[1]) for p in prices], index=idx, name="Close")
        weekly = daily.resample("W").last().dropna()
        return weekly.iloc[:-1]
    except Exception as e:
        print(f"[data] CoinGecko 실패: {e}")
        return None


def fetch_btc_weekly() -> Tuple[pd.Series, str]:
    """주간 BTC 종가 수집 (더 긴 히스토리 우선). 실패 시 예외 — 합성 데이터 금지."""
    coingecko = fetch_btc_weekly_coingecko()
    binance = fetch_btc_weekly_binance()

    candidates = [(s, name) for s, name in [(coingecko, "coingecko"), (binance, "binance")]
                  if s is not None and len(s) >= 260]
    if not candidates:
        raise RuntimeError("실제 BTC 주간 데이터를 얻지 못했습니다 — 백테스트 중단 (합성 데이터 생성 금지)")

    # 더 긴 히스토리 선택 (200주 MA 워밍업 필요)
    series, source = max(candidates, key=lambda c: len(c[0]))
    print(f"[data] 소스: {source}, {len(series)}주 ({series.index[0].date()} ~ {series.index[-1].date()})")
    return series, source


# ---------------------------------------------------------------------------
# 시뮬레이션
# ---------------------------------------------------------------------------

@dataclass
class BacktestResult:
    name: str
    values: pd.Series          # 주간 포트폴리오 가치
    weights: pd.Series         # 주간 crypto 비중
    trades: int
    turnover_total: float      # 총 매매 금액 / 초기 자본

    def metrics(self, start=None, end=None) -> Dict[str, float]:
        v = self.values
        if start:
            v = v[v.index >= pd.Timestamp(start, tz="UTC")]
        if end:
            v = v[v.index < pd.Timestamp(end, tz="UTC")]
        if len(v) < 10:
            return {}
        rets = v.pct_change().dropna()
        years = len(v) / WEEKS_PER_YEAR
        total_return = v.iloc[-1] / v.iloc[0] - 1
        cagr = (v.iloc[-1] / v.iloc[0]) ** (1 / years) - 1 if years > 0 else 0
        running_max = v.cummax()
        mdd = ((v - running_max) / running_max).min()
        sharpe = (rets.mean() / rets.std()) * np.sqrt(WEEKS_PER_YEAR) if rets.std() > 0 else 0
        calmar = cagr / abs(mdd) if mdd < 0 else float("inf")
        return {
            "total_return": total_return,
            "cagr": cagr,
            "mdd": mdd,
            "sharpe": sharpe,
            "calmar": calmar,
        }


def _simulate(
    prices: pd.Series,
    ma200: pd.Series,
    target_weight_fn,
    name: str,
    initial_capital: float = 100.0,
) -> BacktestResult:
    """
    주간 시뮬레이션 공통 루프

    target_weight_fn(date, price, ma, state) -> 목표 crypto 비중 (state는 전략별 딕셔너리)
    """
    cash = initial_capital
    btc = 0.0
    state: Dict = {}
    values, weights = [], []
    trades = 0
    turnover = 0.0

    for date, price in prices.items():
        ma = ma200.get(date)
        total = cash + btc * price
        current_w = (btc * price) / total if total > 0 else 0.0

        target_w = target_weight_fn(date, price, ma, state, current_w)

        if target_w is not None and abs(target_w - current_w) > REBALANCE_THRESHOLD:
            trade_krw = (target_w - current_w) * total
            if trade_krw > 0:
                # 매수: 수수료 포함 현금 한도 내로 제한 (음수 현금 방지)
                trade_krw = min(trade_krw, cash / (1 + TRADE_FEE))
            fee = abs(trade_krw) * TRADE_FEE
            btc += trade_krw / price
            cash -= trade_krw + fee
            trades += 1
            turnover += abs(trade_krw)
            total = cash + btc * price
            current_w = (btc * price) / total

        values.append(total)
        weights.append(current_w)

    return BacktestResult(
        name=name,
        values=pd.Series(values, index=prices.index),
        weights=pd.Series(weights, index=prices.index),
        trades=trades,
        turnover_total=turnover / initial_capital,
    )


def run_legacy(prices: pd.Series, ma200: pd.Series) -> BacktestResult:
    """legacy: RISK_ON 70% / RISK_OFF 30% / 밴드 내 직전 상태 유지"""
    f = MarketSeasonFilter(buffer_band=0.05)

    def fn(date, price, ma, state, current_w):
        if ma is None or np.isnan(ma):
            return None  # 판단 불가 → 거래 없음
        season, _ = f.determine_market_season(price, ma, state.get("season"))
        state["season"] = season
        if season == MarketSeason.RISK_ON:
            return 0.70
        if season == MarketSeason.RISK_OFF:
            return 0.30
        # NEUTRAL: 기존 비중 유지 (최초에는 50%)
        return state.setdefault("neutral_w", 0.50)

    return _simulate(prices, ma200, fn, "legacy (추세추종)")


def run_valuation(
    prices: pd.Series,
    ma200: pd.Series,
    boundaries=None,
    hysteresis=0.05,
    max_step=0.10,
    name="valuation (가치 앵커)",
) -> BacktestResult:
    """valuation: R 기준 5국면, 히스테리시스 + 회당 10%p 단계 이동"""
    f = MarketValuationFilter(
        boundaries=boundaries, hysteresis=hysteresis, max_allocation_step=max_step
    )

    def fn(date, price, ma, state, current_w):
        if ma is None or np.isnan(ma):
            return None
        ratio = price / ma
        phase = f.determine_phase(ratio, state.get("phase"))
        state["phase"] = phase
        if phase is None:
            return None
        final_target = f.get_target_crypto_weight(phase)
        return f.step_allocation(current_w, final_target)

    return _simulate(prices, ma200, fn, name)


def run_buy_and_hold(prices: pd.Series, ma200: pd.Series) -> BacktestResult:
    def fn(date, price, ma, state, current_w):
        return 1.0
    return _simulate(prices, ma200, fn, "Buy & Hold 100% BTC")


def run_static_5050(prices: pd.Series, ma200: pd.Series) -> BacktestResult:
    def fn(date, price, ma, state, current_w):
        return 0.50
    return _simulate(prices, ma200, fn, "고정 50:50 리밸런싱")


# ---------------------------------------------------------------------------
# 리포트
# ---------------------------------------------------------------------------

def format_metrics_table(results: List[BacktestResult], start=None, end=None, label="") -> str:
    lines = [
        f"| 전략 | 총수익률 | CAGR | MDD | Sharpe | Calmar | 매매횟수 | 회전율 |",
        f"|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        m = r.metrics(start, end)
        if not m:
            continue
        lines.append(
            f"| {r.name} | {m['total_return']:+.1%} | {m['cagr']:+.1%} | {m['mdd']:.1%} "
            f"| {m['sharpe']:.2f} | {m['calmar']:.2f} | {r.trades} | {r.turnover_total:.1f}x |"
        )
    return "\n".join(lines)


def main():
    print("=" * 60)
    print("국면 모델 백테스트 (Phase 5)")
    print("=" * 60)

    # 1. 실데이터 수집
    prices, source = fetch_btc_weekly()

    # 2. 200주 MA (워밍업: 200주 이후부터 유효 — 그 이전엔 판단하지 않음)
    ma200 = prices.rolling(window=200).mean()
    valid = ma200.dropna().index
    if len(valid) < 200:
        raise RuntimeError(f"200주 MA 워밍업 후 데이터 부족: {len(valid)}주")

    sim_prices = prices[prices.index >= valid[0]]
    print(f"[sim] 구간: {sim_prices.index[0].date()} ~ {sim_prices.index[-1].date()} "
          f"({len(sim_prices)}주)")

    # 3. 기본 파라미터 전략 실행
    results = [
        run_legacy(sim_prices, ma200),
        run_valuation(sim_prices, ma200),
        run_buy_and_hold(sim_prices, ma200),
        run_static_5050(sim_prices, ma200),
    ]

    # 4. 격자 탐색 (in-sample에서만) → out-of-sample 검증
    grid = []
    for boundaries in [
        [1.0, 1.4, 2.0, 2.8],
        [0.95, 1.3, 1.9, 2.6],
        [1.05, 1.5, 2.1, 3.0],
        [1.0, 1.5, 2.2, 3.2],
    ]:
        for hysteresis in [0.03, 0.05]:
            r = run_valuation(
                sim_prices, ma200, boundaries=boundaries, hysteresis=hysteresis,
                name=f"valuation b={boundaries} h={hysteresis}",
            )
            in_sample = r.metrics(end=OOS_SPLIT_DATE)
            grid.append((r, in_sample))

    # in-sample Calmar 기준 최적 파라미터
    grid_valid = [(r, m) for r, m in grid if m]
    grid_valid.sort(key=lambda x: x[1]["calmar"], reverse=True)
    best_r, best_in = grid_valid[0]

    # 5. 리포트 생성
    split = OOS_SPLIT_DATE
    report = f"""# 국면 모델 백테스트 리포트 (Phase 5)

- 생성일: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
- 데이터 소스: **{source}** (실데이터, 주봉 종가, USD 기준)
- 시뮬레이션 구간: {sim_prices.index[0].date()} ~ {sim_prices.index[-1].date()} ({len(sim_prices)}주)
- 규칙: 주 1회 국면 평가, 비중 편차 {REBALANCE_THRESHOLD:.0%} 초과 시에만 리밸런싱, 수수료 {TRADE_FEE:.1%}/거래
- 자산: BTC + 현금 (알트코인은 장기 데이터 부재로 제외)
- 참고: USD 기준이므로 원화 환율 변동은 반영되지 않음 (모델 간 상대 비교 목적)

## 전체 구간 성과

{format_metrics_table(results)}

## In-sample ({sim_prices.index[0].date()} ~ {split})

{format_metrics_table(results, end=split)}

## Out-of-sample ({split} ~ {sim_prices.index[-1].date()})

{format_metrics_table(results, start=split)}

## 파라미터 격자 탐색 (in-sample Calmar 기준)

- 탐색 공간: 경계 4세트 × 히스테리시스 2종 = 8개 조합 (과최적화 방지를 위해 제한)
- **최적 (in-sample)**: `{best_r.name}` — Calmar {best_in['calmar']:.2f}, CAGR {best_in['cagr']:+.1%}, MDD {best_in['mdd']:.1%}

### 최적 파라미터의 out-of-sample 검증

{format_metrics_table([best_r, results[0], results[2]], start=split)}

## 해석 가이드

- **valuation이 legacy 대비 봐야 할 것**: MDD가 비슷하거나 낮으면서 Calmar/Sharpe가 높은가.
  가치 앵커 모델은 바닥권에서 비중을 늘리므로 하락 구간 진입 시점이 늦으면 MDD가 커질 수 있다.
- **Buy & Hold 대비**: 절대 수익률은 B&H가 이길 수 있으나, 목적은 MDD를 통제하면서
  위험조정수익(Sharpe/Calmar)을 높이는 것이다.
- **격자 최적 파라미터가 기본값과 크게 다르면** 과최적화 신호일 수 있으므로
  out-of-sample 성과가 기본값보다 유의하게 좋을 때만 config 변경을 고려한다.

## 다음 단계 (롤아웃)

1. 이 결과 검토 후 `strategy.regime_model: valuation` 전환 여부 결정
2. 전환 시: dry-run 2주 → 소액 라이브(일일 한도 5%) 2주 → 전체 전환
3. 문제 발생 시 config 한 줄로 legacy 롤백
"""

    out_path = project_root / "docs" / "BACKTEST_REGIME_MODELS.md"
    out_path.write_text(report, encoding="utf-8")
    print(f"\n리포트 저장: {out_path}")
    print()
    print(format_metrics_table(results))


if __name__ == "__main__":
    main()
