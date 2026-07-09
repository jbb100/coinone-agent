# KAIROS-Simple 장기 역발상 매집형 개편 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 추세추종/역발상이 뒤섞인 30+개 모듈 시스템을, 목업 데이터 없이 무료 실 API만 쓰는 "고정 비중(크립토 60/KRW 40) + 밴드(±5%p) 리밸런싱 + F&G×200주MA 승수 주간 DCA" 단일 철학 시스템(8모듈)으로 재구축한다.

**Architecture:** 전략(valuation/dca/rebalance)은 순수 함수로 작성해 백테스트와 실거래가 동일 코드를 쓴다. 모든 주문은 단일 RiskGuard 관문을 통과한다. 데이터 실패 시 하드코딩 폴백 대신 예외를 던지고 거래를 중단한다(fail-loud). 신규 모듈을 먼저 TDD로 만들고, 엔트리포인트를 갈아끼운 뒤, 구모듈을 삭제한다 — 매 커밋마다 전체 테스트가 통과해야 한다(pre-commit 훅이 강제).

**Tech Stack:** Python 3.x, pandas, pytest(+pytest-cov), 기존 유지 모듈: `src/trading/coinone_client.py`, `src/trading/rate_limited_client.py`, `src/utils/binance_data_provider.py`, `src/utils/external_api_client.py`, `src/utils/database_manager.py`, `src/monitoring/alert_system.py`.

**Spec:** `docs/superpowers/specs/2026-07-10-longterm-strategy-redesign-design.md`

**실행 환경 주의:** 테스트는 저장소 루트에서 `kairos_env/bin/pytest`로 실행한다(워크트리에는 심링크 있음). pre-commit 훅이 전체 스위트(~2분)를 돌리므로 커밋은 태스크 단위로만 한다.

---

## File Structure (최종 상태)

```
src/
├── strategy/__init__.py
│   ├── valuation.py     # 순수 함수: F&G 승수, Mayer(200주MA) 승수, DCA 종합 승수, 200주MA 계산
│   ├── dca.py           # 순수 함수: 주간 DCA 주문 목록 생성
│   └── rebalance.py     # 순수 함수: 밴드 이탈 판정 → 리밸런싱 주문 목록 생성
├── risk/__init__.py
│   └── guard.py         # RiskGuard: 모든 주문의 단일 검증 관문 + 데이터 신선도 검사
├── data/__init__.py
│   └── market_data.py   # MarketDataService: Binance/코인원/F&G 실 API 래퍼, fail-loud
├── portfolio/__init__.py
│   └── portfolio.py     # PortfolioService: 잔고 스냅샷(KRW 평가), 거래 기록
├── execution/__init__.py
│   └── executor.py      # OrderExecutor: 지정가/재시도/TWAP 분할 실행
├── report/__init__.py
│   └── reporter.py      # 성과 리포트(실제 BTC 벤치마크), 알림 발송
kairos1_main.py           # 축소된 오케스트레이터 (weekly-dca / daily-check / report CLI)
scripts/backtest_longterm.py  # 순수 함수 재사용 백테스트 (수수료+슬리피지 반영)
```

삭제 대상은 Task 10–12에 명시. `src/core/`는 최종적으로 `types.py`, `exceptions.py`, `resilience.py`, `base_service.py`만 남는다.

---

### Task 1: `src/strategy/valuation.py` — 승수 및 200주MA (순수 함수)

**Files:**
- Create: `src/strategy/__init__.py` (빈 파일)
- Create: `src/strategy/valuation.py`
- Test: `tests/test_strategy_valuation.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_strategy_valuation.py
import pandas as pd
import pytest

from src.strategy.valuation import (
    MarketValuation,
    dca_multiplier,
    fg_multiplier,
    ma_200w,
    valuation_multiplier,
)
from src.core.exceptions import InsufficientDataError


class TestFgMultiplier:
    """스펙 2.2: F&G 구간별 승수 — 공포에 많이, 탐욕에 적게"""

    @pytest.mark.parametrize("fg,expected", [
        (0, 2.0), (24, 2.0),      # 극공포
        (25, 1.5), (44, 1.5),     # 공포
        (45, 1.0), (55, 1.0),     # 중립
        (56, 0.7), (74, 0.7),     # 탐욕
        (75, 0.3), (100, 0.3),    # 극탐욕
    ])
    def test_boundaries(self, fg, expected):
        assert fg_multiplier(fg) == expected

    @pytest.mark.parametrize("bad", [-1, 101])
    def test_out_of_range_raises(self, bad):
        with pytest.raises(ValueError):
            fg_multiplier(bad)


class TestValuationMultiplier:
    """스펙 2.2: Mayer ratio(현재가/200주MA) 구간별 승수"""

    @pytest.mark.parametrize("ratio,expected", [
        (0.5, 1.5), (0.99, 1.5),   # 바닥권
        (1.0, 1.0), (1.99, 1.0),   # 적정
        (2.0, 0.7), (2.99, 0.7),   # 확장
        (3.0, 0.5), (5.0, 0.5),    # 과열
    ])
    def test_boundaries(self, ratio, expected):
        assert valuation_multiplier(ratio) == expected

    def test_non_positive_raises(self):
        with pytest.raises(ValueError):
            valuation_multiplier(0.0)


class TestDcaMultiplier:
    def test_extreme_fear_below_ma_is_capped_at_3(self):
        # 2.0 * 1.5 = 3.0 → 상한 3.0
        v = MarketValuation(fear_greed=10, mayer_ratio=0.8)
        assert dca_multiplier(v) == 3.0

    def test_extreme_greed_overheated_is_floored(self):
        # 0.3 * 0.5 = 0.15 → 하한 0.3
        v = MarketValuation(fear_greed=90, mayer_ratio=3.5)
        assert dca_multiplier(v) == 0.3

    def test_neutral_is_1(self):
        v = MarketValuation(fear_greed=50, mayer_ratio=1.5)
        assert dca_multiplier(v) == 1.0


class TestMa200w:
    def test_computes_rolling_mean_of_last_200_weeks(self):
        closes = pd.Series(range(1, 251), dtype=float)  # 250주
        # 마지막 200개 = 51..250 의 평균 = 150.5
        assert ma_200w(closes) == pytest.approx(150.5)

    def test_insufficient_data_raises(self):
        """스펙 fail-loud: 데이터 부족 시 하드코딩 폴백 금지, 예외 발생"""
        with pytest.raises(InsufficientDataError):
            ma_200w(pd.Series(range(199), dtype=float))

    def test_nan_in_window_raises(self):
        closes = pd.Series([float("nan")] + list(range(200)), dtype=float)
        closes.iloc[-1] = float("nan")
        with pytest.raises(InsufficientDataError):
            ma_200w(closes)
```

- [ ] **Step 2: 실패 확인**

Run: `kairos_env/bin/pytest tests/test_strategy_valuation.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.strategy'` 및 `InsufficientDataError` import 오류

- [ ] **Step 3: `src/core/exceptions.py`에 예외 추가 (기존 예외 계층 확인 후 스타일 맞춤)**

`src/core/exceptions.py`를 열어 기존 베이스 예외 클래스명을 확인하고 다음을 추가한다(베이스가 `KairosException`이면 그것을 상속, 없으면 `Exception`):

```python
class InsufficientDataError(Exception):
    """지표 계산에 필요한 데이터가 부족하거나 오염됨 — 폴백 금지, 거래 중단."""


class DataUnavailableError(Exception):
    """외부 API에서 신선한 데이터를 얻지 못함 — 해당 사이클 거래 중단."""
```

- [ ] **Step 4: 최소 구현**

```python
# src/strategy/valuation.py
"""시장 밸류에이션 순수 함수.

철학: 싸질수록(공포·200주MA 아래) 승수를 키우고,
비싸질수록(탐욕·MA 대비 과열) 승수를 줄인다.
"""
from dataclasses import dataclass

import pandas as pd

from src.core.exceptions import InsufficientDataError

MIN_WEEKS = 200
MULTIPLIER_FLOOR = 0.3
MULTIPLIER_CAP = 3.0

# (상한 경계, 승수) — 경계는 "이하"
_FG_BANDS = [(24, 2.0), (44, 1.5), (55, 1.0), (74, 0.7), (100, 0.3)]
# (상한 경계, 승수) — 경계는 "미만"
_MAYER_BANDS = [(1.0, 1.5), (2.0, 1.0), (3.0, 0.7)]
_MAYER_OVERHEATED = 0.5


@dataclass(frozen=True)
class MarketValuation:
    fear_greed: int      # 0-100
    mayer_ratio: float   # 현재가 / 200주MA


def fg_multiplier(fear_greed: int) -> float:
    if not 0 <= fear_greed <= 100:
        raise ValueError(f"Fear&Greed 범위 오류: {fear_greed}")
    for upper, mult in _FG_BANDS:
        if fear_greed <= upper:
            return mult
    raise AssertionError("unreachable")


def valuation_multiplier(mayer_ratio: float) -> float:
    if mayer_ratio <= 0:
        raise ValueError(f"Mayer ratio는 양수여야 함: {mayer_ratio}")
    for upper, mult in _MAYER_BANDS:
        if mayer_ratio < upper:
            return mult
    return _MAYER_OVERHEATED


def dca_multiplier(valuation: MarketValuation) -> float:
    raw = fg_multiplier(valuation.fear_greed) * valuation_multiplier(valuation.mayer_ratio)
    return max(MULTIPLIER_FLOOR, min(MULTIPLIER_CAP, raw))


def ma_200w(weekly_closes: pd.Series) -> float:
    valid = weekly_closes.dropna()
    if len(valid) < MIN_WEEKS:
        raise InsufficientDataError(
            f"200주MA 계산 불가: 유효 주봉 {len(valid)}개 < {MIN_WEEKS}개"
        )
    window = weekly_closes.iloc[-MIN_WEEKS:]
    if window.isna().any():
        raise InsufficientDataError("200주MA 윈도우에 NaN 포함 — 데이터 오염")
    return float(window.mean())
```

`src/strategy/__init__.py`는 빈 파일로 생성.

- [ ] **Step 5: 통과 확인**

Run: `kairos_env/bin/pytest tests/test_strategy_valuation.py -q`
Expected: 전부 PASS

- [ ] **Step 6: 커밋**

```bash
git add src/strategy/ src/core/exceptions.py tests/test_strategy_valuation.py
git commit -m "feat(strategy): 역발상 DCA 승수·200주MA 순수 함수 (fail-loud)"
```

---

### Task 2: `src/strategy/dca.py` — 주간 DCA 주문 계산 (순수 함수)

**Files:**
- Create: `src/strategy/dca.py`
- Test: `tests/test_strategy_dca.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_strategy_dca.py
import pytest

from src.strategy.dca import DCAOrder, DCAConfig, plan_weekly_dca

CONFIG = DCAConfig(
    base_amount_krw=1_000_000,
    crypto_weights={"BTC": 0.5, "ETH": 0.3, "XRP": 0.1, "SOL": 0.1},
    max_single_dca_krw=5_000_000,
    krw_usage_cap=0.25,        # 스펙 2.2: KRW 잔고의 25% 초과 불가
    min_order_krw=10_000,      # 거래소 최소 주문
)


def test_neutral_multiplier_splits_by_weights():
    orders = plan_weekly_dca(CONFIG, multiplier=1.0, krw_balance=100_000_000)
    assert orders == [
        DCAOrder("BTC", 500_000),
        DCAOrder("ETH", 300_000),
        DCAOrder("XRP", 100_000),
        DCAOrder("SOL", 100_000),
    ]


def test_multiplier_scales_total():
    orders = plan_weekly_dca(CONFIG, multiplier=2.0, krw_balance=100_000_000)
    assert sum(o.amount_krw for o in orders) == pytest.approx(2_000_000)


def test_total_capped_by_max_single_dca():
    cfg = DCAConfig(**{**CONFIG.__dict__, "base_amount_krw": 3_000_000})
    orders = plan_weekly_dca(cfg, multiplier=3.0, krw_balance=1_000_000_000)
    # 3M * 3.0 = 9M → cap 5M
    assert sum(o.amount_krw for o in orders) == pytest.approx(5_000_000)


def test_total_capped_by_krw_usage_cap():
    orders = plan_weekly_dca(CONFIG, multiplier=2.0, krw_balance=4_000_000)
    # 4M * 25% = 1M < 2M
    assert sum(o.amount_krw for o in orders) == pytest.approx(1_000_000)


def test_orders_below_min_are_dropped():
    orders = plan_weekly_dca(CONFIG, multiplier=1.0, krw_balance=200_000)
    # 총액 = 200_000*0.25 = 50_000 → XRP/SOL 몫 5_000 < 10_000 → 제외
    assets = [o.asset for o in orders]
    assert "XRP" not in assets and "SOL" not in assets
    assert "BTC" in assets


def test_zero_balance_returns_empty():
    assert plan_weekly_dca(CONFIG, multiplier=3.0, krw_balance=0) == []


def test_invalid_weights_raise():
    with pytest.raises(ValueError):
        DCAConfig(
            base_amount_krw=1_000_000,
            crypto_weights={"BTC": 0.5, "ETH": 0.4},  # 합 0.9
            max_single_dca_krw=5_000_000,
            krw_usage_cap=0.25,
            min_order_krw=10_000,
        )
```

- [ ] **Step 2: 실패 확인**

Run: `kairos_env/bin/pytest tests/test_strategy_dca.py -q`
Expected: FAIL — `No module named 'src.strategy.dca'`

- [ ] **Step 3: 최소 구현**

```python
# src/strategy/dca.py
"""주간 DCA 주문 계산 — 순수 함수."""
import math
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class DCAOrder:
    asset: str
    amount_krw: float


@dataclass(frozen=True)
class DCAConfig:
    base_amount_krw: float
    crypto_weights: Dict[str, float]
    max_single_dca_krw: float
    krw_usage_cap: float
    min_order_krw: float

    def __post_init__(self):
        if not math.isclose(sum(self.crypto_weights.values()), 1.0, abs_tol=1e-9):
            raise ValueError(f"crypto_weights 합이 1이 아님: {self.crypto_weights}")
        if not 0 < self.krw_usage_cap <= 1:
            raise ValueError(f"krw_usage_cap 범위 오류: {self.krw_usage_cap}")


def plan_weekly_dca(
    config: DCAConfig, multiplier: float, krw_balance: float
) -> List[DCAOrder]:
    total = config.base_amount_krw * multiplier
    total = min(total, config.max_single_dca_krw, krw_balance * config.krw_usage_cap)
    if total <= 0:
        return []
    orders = []
    for asset, weight in config.crypto_weights.items():
        amount = total * weight
        if amount >= config.min_order_krw:
            orders.append(DCAOrder(asset, amount))
    return orders
```

- [ ] **Step 4: 통과 확인**

Run: `kairos_env/bin/pytest tests/test_strategy_dca.py -q`
Expected: 전부 PASS

- [ ] **Step 5: 커밋**

```bash
git add src/strategy/dca.py tests/test_strategy_dca.py
git commit -m "feat(strategy): 주간 DCA 주문 계산 순수 함수 (한도 3종 적용)"
```

---

### Task 3: `src/strategy/rebalance.py` — 밴드 리밸런싱 (순수 함수)

**Files:**
- Create: `src/strategy/rebalance.py`
- Test: `tests/test_strategy_rebalance.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_strategy_rebalance.py
import pytest

from src.strategy.rebalance import RebalanceConfig, RebalanceOrder, plan_rebalance

CONFIG = RebalanceConfig(
    crypto_target=0.60,
    band_pp=0.05,               # 총 크립토 비중 ±5%p
    crypto_weights={"BTC": 0.5, "ETH": 0.3, "XRP": 0.1, "SOL": 0.1},
    relative_band=0.20,         # 코인별 상대 ±20%
    min_trade_krw=10_000,
)


def test_within_band_no_orders():
    # 크립토 62% (밴드 55~65% 내) → 거래 없음
    holdings = {"BTC": 31_000_000, "ETH": 18_600_000, "XRP": 6_200_000, "SOL": 6_200_000}
    assert plan_rebalance(CONFIG, holdings, krw_balance=38_000_000) == []


def test_bull_market_overweight_sells_back_to_target():
    """상승장: 크립토 70% > 65% → 목표 60%까지 매도 (자동 익절)"""
    holdings = {"BTC": 35_000_000, "ETH": 21_000_000, "XRP": 7_000_000, "SOL": 7_000_000}
    orders = plan_rebalance(CONFIG, holdings, krw_balance=30_000_000)
    sells = [o for o in orders if o.side == "sell"]
    assert sells, "상승장 초과분은 매도되어야 함"
    total_sell = sum(o.amount_krw for o in sells)
    assert total_sell == pytest.approx(10_000_000)  # 70% → 60% of 100M


def test_bear_market_underweight_buys_back_to_target():
    """하락장: 크립토 50% < 55% → 목표 60%까지 매수 (자동 저가 매집)"""
    holdings = {"BTC": 25_000_000, "ETH": 15_000_000, "XRP": 5_000_000, "SOL": 5_000_000}
    orders = plan_rebalance(CONFIG, holdings, krw_balance=50_000_000)
    buys = [o for o in orders if o.side == "buy"]
    assert buys, "하락장 미달분은 매수되어야 함"
    assert sum(o.amount_krw for o in buys) == pytest.approx(10_000_000)


def test_trades_split_toward_per_asset_targets():
    """거래 후 개별 코인도 크립토 내 목표 비중에 수렴해야 함"""
    # BTC만 급등해 크립토 내 비중 왜곡 + 총비중 초과
    holdings = {"BTC": 50_000_000, "ETH": 12_000_000, "XRP": 4_000_000, "SOL": 4_000_000}
    orders = plan_rebalance(CONFIG, holdings, krw_balance=30_000_000)
    by_asset = {o.asset: o for o in orders}
    # 총 100M, 목표 크립토 60M → BTC 목표 30M: 20M 매도
    assert by_asset["BTC"].side == "sell"
    assert by_asset["BTC"].amount_krw == pytest.approx(20_000_000)
    # ETH 목표 18M: 6M 매수
    assert by_asset["ETH"].side == "buy"
    assert by_asset["ETH"].amount_krw == pytest.approx(6_000_000)


def test_per_asset_drift_triggers_even_when_total_in_band():
    """총비중은 밴드 내지만 개별 코인이 상대 ±20% 초과 이탈하면 내부 리밸런싱"""
    # 크립토 총 60M(=60%), 그러나 BTC 42M(내부 70% vs 목표 50%, 상대 +40%)
    holdings = {"BTC": 42_000_000, "ETH": 10_000_000, "XRP": 4_000_000, "SOL": 4_000_000}
    orders = plan_rebalance(CONFIG, holdings, krw_balance=40_000_000)
    by_asset = {o.asset: o for o in orders}
    assert by_asset["BTC"].side == "sell"
    buys = sum(o.amount_krw for o in orders if o.side == "buy")
    sells = sum(o.amount_krw for o in orders if o.side == "sell")
    assert buys == pytest.approx(sells)  # 내부 재배분: 총 크립토 불변


def test_dust_trades_dropped():
    holdings = {"BTC": 30_000_000, "ETH": 18_000_000, "XRP": 6_000_000, "SOL": 6_005_000}
    orders = plan_rebalance(CONFIG, holdings, krw_balance=40_000_000)
    assert all(o.amount_krw >= CONFIG.min_trade_krw for o in orders)
```

- [ ] **Step 2: 실패 확인**

Run: `kairos_env/bin/pytest tests/test_strategy_rebalance.py -q`
Expected: FAIL — `No module named 'src.strategy.rebalance'`

- [ ] **Step 3: 최소 구현**

```python
# src/strategy/rebalance.py
"""밴드 리밸런싱 — 순수 함수.

오르면 초과분을 팔고(익절), 내리면 미달분을 산다(저가 매집).
트리거는 두 가지:
  1) 크립토 총비중이 목표 ±band_pp 이탈
  2) 개별 코인이 크립토 내 목표 대비 상대 ±relative_band 이탈
거래가 트리거되면 모든 자산을 정확히 목표 비중으로 되돌린다.
"""
from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class RebalanceOrder:
    asset: str
    side: str        # "buy" | "sell"
    amount_krw: float


@dataclass(frozen=True)
class RebalanceConfig:
    crypto_target: float
    band_pp: float
    crypto_weights: Dict[str, float]
    relative_band: float
    min_trade_krw: float


def plan_rebalance(
    config: RebalanceConfig,
    holdings_krw: Dict[str, float],
    krw_balance: float,
) -> List[RebalanceOrder]:
    crypto_value = sum(holdings_krw.values())
    total_value = crypto_value + krw_balance
    if total_value <= 0:
        return []

    crypto_ratio = crypto_value / total_value
    total_breach = abs(crypto_ratio - config.crypto_target) > config.band_pp

    asset_breach = False
    if crypto_value > 0:
        for asset, target_w in config.crypto_weights.items():
            actual_w = holdings_krw.get(asset, 0.0) / crypto_value
            if target_w > 0 and abs(actual_w / target_w - 1.0) > config.relative_band:
                asset_breach = True
                break

    if not (total_breach or asset_breach):
        return []

    # 총비중 이탈 시 목표는 crypto_target, 내부 이탈만이면 현 총액 유지
    target_crypto_value = (
        total_value * config.crypto_target if total_breach else crypto_value
    )

    orders = []
    for asset, target_w in config.crypto_weights.items():
        target_value = target_crypto_value * target_w
        diff = target_value - holdings_krw.get(asset, 0.0)
        if abs(diff) < config.min_trade_krw:
            continue
        side = "buy" if diff > 0 else "sell"
        orders.append(RebalanceOrder(asset, side, abs(diff)))
    return orders
```

- [ ] **Step 4: 통과 확인**

Run: `kairos_env/bin/pytest tests/test_strategy_rebalance.py -q`
Expected: 전부 PASS

- [ ] **Step 5: 커밋**

```bash
git add src/strategy/rebalance.py tests/test_strategy_rebalance.py
git commit -m "feat(strategy): 밴드 리밸런싱 순수 함수 (상승 익절·하락 매집)"
```

---

### Task 4: `src/risk/guard.py` — 단일 리스크 관문

**Files:**
- Create: `src/risk/__init__.py` (빈 파일)
- Create: `src/risk/guard.py`
- Test: `tests/test_risk_guard.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_risk_guard.py
from datetime import datetime, timedelta

import pytest

from src.risk.guard import (
    OrderRequest,
    PortfolioContext,
    RiskGuard,
    RiskLimits,
    ensure_fresh,
)
from src.core.exceptions import DataUnavailableError

LIMITS = RiskLimits(
    max_single_trade_krw=10_000_000,
    max_daily_volume_krw=50_000_000,
    min_krw_ratio=0.10,
    fomo_surge_threshold=0.15,
)


def make_ctx(**kw):
    defaults = dict(
        total_value_krw=100_000_000,
        krw_balance=40_000_000,
        daily_traded_krw=0.0,
        price_change_24h={"BTC": 0.02},
    )
    defaults.update(kw)
    return PortfolioContext(**defaults)


def test_valid_order_passes():
    r = RiskGuard(LIMITS).validate(OrderRequest("BTC", "buy", 1_000_000, "dca"), make_ctx())
    assert r.approved


def test_single_trade_limit_rejects():
    r = RiskGuard(LIMITS).validate(OrderRequest("BTC", "buy", 10_000_001, "dca"), make_ctx())
    assert not r.approved and "단일 거래" in r.reason


def test_daily_volume_limit_rejects():
    ctx = make_ctx(daily_traded_krw=45_000_000)
    r = RiskGuard(LIMITS).validate(OrderRequest("BTC", "buy", 6_000_000, "dca"), ctx)
    assert not r.approved and "일일" in r.reason


def test_buy_breaking_krw_floor_rejects():
    # 매수 후 KRW 10.5M < 총자산 100M의 10%
    ctx = make_ctx(krw_balance=11_000_000)
    r = RiskGuard(LIMITS).validate(OrderRequest("BTC", "buy", 500_001, "dca"), ctx)
    assert not r.approved and "KRW" in r.reason


def test_sell_never_blocked_by_krw_floor():
    ctx = make_ctx(krw_balance=0)
    r = RiskGuard(LIMITS).validate(OrderRequest("BTC", "sell", 5_000_000, "rebalance"), ctx)
    assert r.approved


def test_fomo_guard_blocks_non_dca_buy_after_surge():
    """스펙 2.3: 24h +15% 급등 자산은 DCA 외 추가 매수 금지"""
    ctx = make_ctx(price_change_24h={"BTC": 0.16})
    r = RiskGuard(LIMITS).validate(
        OrderRequest("BTC", "buy", 1_000_000, "rebalance"), ctx
    )
    assert not r.approved and "급등" in r.reason


def test_fomo_guard_allows_dca_and_sells():
    ctx = make_ctx(price_change_24h={"BTC": 0.20})
    assert RiskGuard(LIMITS).validate(OrderRequest("BTC", "buy", 1_000_000, "dca"), ctx).approved
    assert RiskGuard(LIMITS).validate(OrderRequest("BTC", "sell", 1_000_000, "rebalance"), ctx).approved


def test_ensure_fresh_rejects_stale():
    stale = datetime.now() - timedelta(hours=25)
    with pytest.raises(DataUnavailableError):
        ensure_fresh("fear_greed", stale, max_age_hours=24)


def test_ensure_fresh_rejects_none_timestamp():
    with pytest.raises(DataUnavailableError):
        ensure_fresh("ticker", None, max_age_hours=24)
```

- [ ] **Step 2: 실패 확인**

Run: `kairos_env/bin/pytest tests/test_risk_guard.py -q`
Expected: FAIL — `No module named 'src.risk'`

- [ ] **Step 3: 최소 구현**

```python
# src/risk/guard.py
"""모든 주문이 통과해야 하는 단일 리스크 관문."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional

from src.core.exceptions import DataUnavailableError


@dataclass(frozen=True)
class RiskLimits:
    max_single_trade_krw: float
    max_daily_volume_krw: float
    min_krw_ratio: float
    fomo_surge_threshold: float


@dataclass(frozen=True)
class OrderRequest:
    asset: str
    side: str          # "buy" | "sell"
    amount_krw: float
    origin: str        # "dca" | "rebalance"


@dataclass(frozen=True)
class PortfolioContext:
    total_value_krw: float
    krw_balance: float
    daily_traded_krw: float
    price_change_24h: Dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationResult:
    approved: bool
    reason: str = ""


class RiskGuard:
    def __init__(self, limits: RiskLimits):
        self.limits = limits

    def validate(self, order: OrderRequest, ctx: PortfolioContext) -> ValidationResult:
        l = self.limits
        if order.amount_krw > l.max_single_trade_krw:
            return ValidationResult(
                False,
                f"단일 거래 한도 초과: {order.amount_krw:,.0f} > {l.max_single_trade_krw:,.0f}",
            )
        if ctx.daily_traded_krw + order.amount_krw > l.max_daily_volume_krw:
            return ValidationResult(
                False,
                f"일일 거래량 한도 초과: {ctx.daily_traded_krw + order.amount_krw:,.0f}"
                f" > {l.max_daily_volume_krw:,.0f}",
            )
        if order.side == "buy":
            krw_after = ctx.krw_balance - order.amount_krw
            if krw_after < ctx.total_value_krw * l.min_krw_ratio:
                return ValidationResult(
                    False,
                    f"매수 후 KRW 비중이 하한({l.min_krw_ratio:.0%}) 미달",
                )
            change = ctx.price_change_24h.get(order.asset, 0.0)
            if order.origin != "dca" and change >= l.fomo_surge_threshold:
                return ValidationResult(
                    False,
                    f"{order.asset} 24h {change:+.0%} 급등 — FOMO 가드: DCA 외 매수 금지",
                )
        return ValidationResult(True)


def ensure_fresh(name: str, ts: Optional[datetime], max_age_hours: float) -> None:
    """데이터 신선도 검사 — 스테일이면 거래 중단(fail-loud)."""
    if ts is None:
        raise DataUnavailableError(f"{name}: 타임스탬프 없음")
    age_hours = (datetime.now() - ts).total_seconds() / 3600
    if age_hours > max_age_hours:
        raise DataUnavailableError(f"{name}: 데이터 스테일 ({age_hours:.1f}h > {max_age_hours}h)")
```

- [ ] **Step 4: 통과 확인 후 커밋**

Run: `kairos_env/bin/pytest tests/test_risk_guard.py -q` → 전부 PASS

```bash
git add src/risk/ tests/test_risk_guard.py
git commit -m "feat(risk): 단일 리스크 관문 RiskGuard (한도·KRW하한·FOMO·신선도)"
```

---

### Task 5: `src/data/market_data.py` — 실 API 래퍼 (fail-loud)

**Files:**
- Create: `src/data/__init__.py` (빈 파일)
- Create: `src/data/market_data.py`
- Test: `tests/test_market_data_service.py`

기존 클라이언트를 조합한다: `BinanceDataProvider.get_historical_klines(symbol, interval="1w", limit=...)`(주봉 DataFrame, 'Close' 컬럼), `ExternalAPIClient.get_fear_greed_index() -> Optional[int]`, `CoinoneClient.get_latest_price(currency) -> float`. 테스트는 전부 모킹 — 실 네트워크 호출 없음.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_market_data_service.py
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.data.market_data import MarketDataService
from src.core.exceptions import DataUnavailableError, InsufficientDataError


def make_service(fg=30, weekly_rows=260, price=100_000_000.0):
    binance = MagicMock()
    closes = pd.Series([50_000.0 + i for i in range(weekly_rows)])
    binance.get_historical_klines.return_value = pd.DataFrame({"Close": closes})
    external = MagicMock()
    external.get_fear_greed_index.return_value = fg
    coinone = MagicMock()
    coinone.get_latest_price.return_value = price
    return MarketDataService(binance, external, coinone), binance, external, coinone


def test_get_valuation_combines_fg_and_mayer():
    svc, *_ = make_service(fg=20)
    v = svc.get_valuation()
    assert v.fear_greed == 20
    assert v.mayer_ratio > 0


def test_fg_none_raises_data_unavailable():
    """스펙 fail-loud: F&G 실패 시 50 폴백 금지, 예외"""
    svc, _, external, _ = make_service()
    external.get_fear_greed_index.return_value = None
    with pytest.raises(DataUnavailableError):
        svc.get_valuation()


def test_short_history_raises_insufficient_data():
    svc, *_ = make_service(weekly_rows=100)
    with pytest.raises(InsufficientDataError):
        svc.get_valuation()


def test_empty_klines_raises():
    svc, binance, *_ = make_service()
    binance.get_historical_klines.return_value = pd.DataFrame()
    with pytest.raises(DataUnavailableError):
        svc.get_valuation()


def test_get_prices_krw_returns_per_asset():
    svc, _, _, coinone = make_service(price=50_000_000.0)
    prices = svc.get_prices_krw(["BTC", "ETH"])
    assert prices == {"BTC": 50_000_000.0, "ETH": 50_000_000.0}


def test_get_prices_krw_invalid_price_raises():
    svc, _, _, coinone = make_service()
    coinone.get_latest_price.return_value = 0.0
    with pytest.raises(DataUnavailableError):
        svc.get_prices_krw(["BTC"])


def test_price_change_24h_computed_from_daily_klines():
    svc, binance, _, _ = make_service()
    binance.get_historical_klines.return_value = pd.DataFrame(
        {"Close": [100.0, 116.0]}
    )
    change = svc.get_price_change_24h(["BTC"])
    assert change["BTC"] == pytest.approx(0.16)
```

- [ ] **Step 2: 실패 확인**

Run: `kairos_env/bin/pytest tests/test_market_data_service.py -q`
Expected: FAIL — `No module named 'src.data'`

- [ ] **Step 3: 최소 구현**

```python
# src/data/market_data.py
"""실 API 래퍼 — 폴백 상수 금지, 실패는 예외로 (fail-loud)."""
from typing import Dict, List

from loguru import logger

from src.core.exceptions import DataUnavailableError
from src.strategy.valuation import MarketValuation, ma_200w


class MarketDataService:
    def __init__(self, binance_provider, external_api, coinone_client):
        self.binance = binance_provider
        self.external = external_api
        self.coinone = coinone_client

    def get_valuation(self) -> MarketValuation:
        fg = self.external.get_fear_greed_index()
        if fg is None:
            raise DataUnavailableError("Fear&Greed 조회 실패 — 이번 사이클 거래 중단")

        klines = self.binance.get_historical_klines(
            symbol="BTCUSDT", interval="1w", limit=300
        )
        if klines is None or klines.empty or "Close" not in klines.columns:
            raise DataUnavailableError("Binance 주봉 조회 실패 — 이번 사이클 거래 중단")

        ma = ma_200w(klines["Close"])          # 부족/NaN 시 InsufficientDataError
        current = float(klines["Close"].iloc[-1])
        valuation = MarketValuation(fear_greed=int(fg), mayer_ratio=current / ma)
        logger.info(f"밸류에이션: F&G={fg}, Mayer={valuation.mayer_ratio:.2f}")
        return valuation

    def get_prices_krw(self, assets: List[str]) -> Dict[str, float]:
        prices = {}
        for asset in assets:
            price = self.coinone.get_latest_price(asset)
            if not price or price <= 0:
                raise DataUnavailableError(f"{asset} 코인원 시세 조회 실패")
            prices[asset] = float(price)
        return prices

    def get_price_change_24h(self, assets: List[str]) -> Dict[str, float]:
        changes = {}
        for asset in assets:
            daily = self.binance.get_historical_klines(
                symbol=f"{asset}USDT", interval="1d", limit=2
            )
            if daily is None or len(daily) < 2:
                raise DataUnavailableError(f"{asset} 일봉 조회 실패")
            prev, last = float(daily["Close"].iloc[-2]), float(daily["Close"].iloc[-1])
            changes[asset] = last / prev - 1.0
        return changes
```

- [ ] **Step 4: 통과 확인 후 커밋**

Run: `kairos_env/bin/pytest tests/test_market_data_service.py -q` → 전부 PASS

```bash
git add src/data/ tests/test_market_data_service.py
git commit -m "feat(data): 실 API 시장 데이터 서비스 (하드코딩 폴백 없는 fail-loud)"
```

---

### Task 6: `src/portfolio/portfolio.py` — 잔고 스냅샷·거래 기록

**Files:**
- Create: `src/portfolio/__init__.py` (빈 파일)
- Create: `src/portfolio/portfolio.py`
- Test: `tests/test_portfolio_service.py`

`CoinoneClient.get_balances() -> Dict[str, float]`(코인 수량, "krw" 포함 — 실제 키 형식은 `src/trading/coinone_client.py:164-193`을 읽고 맞출 것)와 `MarketDataService.get_prices_krw`를 조합한다. 거래 기록은 기존 `DatabaseManager`의 트레이드 기록 메서드를 사용한다(`src/utils/database_manager.py`에서 `record_trade`/`save_trade` 계열 메서드명을 확인해 호출부를 맞춘다 — 없으면 이 태스크에서 `record_trade(asset, side, amount_krw, origin, executed_at)` 테이블/메서드를 추가).

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_portfolio_service.py
from unittest.mock import MagicMock

import pytest

from src.portfolio.portfolio import PortfolioService, PortfolioSnapshot


def make_service(balances, prices):
    coinone = MagicMock()
    coinone.get_balances.return_value = balances
    market = MagicMock()
    market.get_prices_krw.return_value = prices
    db = MagicMock()
    return PortfolioService(coinone, market, db, assets=["BTC", "ETH"]), db


def test_snapshot_values_holdings_in_krw():
    svc, _ = make_service(
        balances={"krw": 40_000_000.0, "btc": 0.5, "eth": 4.0},
        prices={"BTC": 100_000_000.0, "ETH": 5_000_000.0},
    )
    snap = svc.get_snapshot()
    assert snap.holdings_krw == {"BTC": 50_000_000.0, "ETH": 20_000_000.0}
    assert snap.krw_balance == 40_000_000.0
    assert snap.total_value_krw == pytest.approx(110_000_000.0)
    assert snap.crypto_ratio == pytest.approx(70_000_000.0 / 110_000_000.0)


def test_snapshot_missing_asset_counts_zero():
    svc, _ = make_service(
        balances={"krw": 1_000_000.0},
        prices={"BTC": 100_000_000.0, "ETH": 5_000_000.0},
    )
    snap = svc.get_snapshot()
    assert snap.holdings_krw == {"BTC": 0.0, "ETH": 0.0}


def test_record_trade_persists_to_db():
    svc, db = make_service(
        balances={"krw": 1_000_000.0},
        prices={"BTC": 100_000_000.0, "ETH": 5_000_000.0},
    )
    svc.record_trade("BTC", "buy", 500_000.0, origin="dca")
    assert db.record_trade.called
```

- [ ] **Step 2: 실패 확인**

Run: `kairos_env/bin/pytest tests/test_portfolio_service.py -q`
Expected: FAIL — `No module named 'src.portfolio'`

- [ ] **Step 3: 최소 구현**

```python
# src/portfolio/portfolio.py
"""포트폴리오 스냅샷(KRW 평가)과 거래 기록."""
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List


@dataclass(frozen=True)
class PortfolioSnapshot:
    holdings_krw: Dict[str, float]
    krw_balance: float
    taken_at: datetime

    @property
    def crypto_value_krw(self) -> float:
        return sum(self.holdings_krw.values())

    @property
    def total_value_krw(self) -> float:
        return self.crypto_value_krw + self.krw_balance

    @property
    def crypto_ratio(self) -> float:
        total = self.total_value_krw
        return self.crypto_value_krw / total if total > 0 else 0.0


class PortfolioService:
    def __init__(self, coinone_client, market_data, db_manager, assets: List[str]):
        self.coinone = coinone_client
        self.market = market_data
        self.db = db_manager
        self.assets = assets

    def get_snapshot(self) -> PortfolioSnapshot:
        balances = self.coinone.get_balances()
        prices = self.market.get_prices_krw(self.assets)
        holdings = {
            asset: balances.get(asset.lower(), 0.0) * prices[asset]
            for asset in self.assets
        }
        return PortfolioSnapshot(
            holdings_krw=holdings,
            krw_balance=float(balances.get("krw", 0.0)),
            taken_at=datetime.now(),
        )

    def record_trade(self, asset: str, side: str, amount_krw: float, origin: str) -> None:
        self.db.record_trade(
            asset=asset, side=side, amount_krw=amount_krw,
            origin=origin, executed_at=datetime.now(),
        )
```

구현 중 `get_balances()`의 실제 반환 키(`"krw"` vs `"KRW"`, 코인 소문자 여부)를 `src/trading/coinone_client.py:164-193`에서 확인하고, 다르면 이 파일의 조회부만 수정한다(테스트의 balances 딕셔너리도 실제 형식으로 맞춘다). `DatabaseManager`에 `record_trade`가 없으면 동명 메서드를 추가하고 그 테스트를 `tests/test_database_manager.py`에 1건 추가한다.

- [ ] **Step 4: 통과 확인 후 커밋**

Run: `kairos_env/bin/pytest tests/test_portfolio_service.py -q` → 전부 PASS

```bash
git add src/portfolio/ tests/test_portfolio_service.py
git commit -m "feat(portfolio): 잔고 스냅샷·거래 기록 서비스"
```

---

### Task 7: `src/execution/executor.py` — 주문 실행 (지정가·재시도·TWAP)

**Files:**
- Create: `src/execution/__init__.py` (빈 파일)
- Create: `src/execution/executor.py`
- Test: `tests/test_order_executor.py`

기존 `CoinoneClient.place_order(currency, side, amount, price=None, amount_in_krw=False)`를 사용. 재시도 백오프는 기존 `src/core/resilience.py`의 유틸을 재사용(파일을 읽고 데코레이터/함수명 확인; 재사용이 어려우면 executor 내부에 단순 루프 구현). TWAP: 500만원 초과 주문은 균등 분할(슬라이스당 ≤500만원, 최대 6슬라이스) — 기존 스케줄 지연 실행 대신 **한 사이클 내 순차 실행**으로 단순화한다(장기 전략에서 분 단위 타이밍은 무의미, YAGNI).

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_order_executor.py
from unittest.mock import MagicMock, call

import pytest

from src.execution.executor import ExecutionReport, OrderExecutor
from src.risk.guard import OrderRequest


def make_executor(place_results=None, price=100_000_000.0):
    coinone = MagicMock()
    coinone.get_latest_price.return_value = price
    coinone.place_order.side_effect = place_results or (
        lambda **kw: {"result": "success", "order_id": "oid-1"}
    )
    return OrderExecutor(coinone, twap_slice_krw=5_000_000, max_retries=3), coinone


def test_small_order_executes_once():
    ex, coinone = make_executor()
    report = ex.execute(OrderRequest("BTC", "buy", 1_000_000, "dca"))
    assert report.success and coinone.place_order.call_count == 1


def test_order_uses_limit_price_and_krw_amount():
    ex, coinone = make_executor(price=100_000_000.0)
    ex.execute(OrderRequest("BTC", "buy", 1_000_000, "dca"))
    kwargs = coinone.place_order.call_args.kwargs
    assert kwargs["currency"] == "BTC"
    assert kwargs["side"] == "buy"
    assert kwargs["amount_in_krw"] is True
    assert kwargs["price"] == pytest.approx(100_000_000.0 * 1.005)  # 슬리피지 상한 0.5%


def test_sell_limit_price_below_market():
    ex, coinone = make_executor(price=100_000_000.0)
    ex.execute(OrderRequest("BTC", "sell", 1_000_000, "rebalance"))
    assert coinone.place_order.call_args.kwargs["price"] == pytest.approx(
        100_000_000.0 * 0.995
    )


def test_large_order_split_into_twap_slices():
    ex, coinone = make_executor()
    report = ex.execute(OrderRequest("BTC", "buy", 12_000_000, "rebalance"))
    assert report.success
    assert coinone.place_order.call_count == 3  # 12M / 5M → 3 slices (4M each)
    amounts = [c.kwargs["amount"] for c in coinone.place_order.call_args_list]
    assert sum(amounts) == pytest.approx(12_000_000)
    assert all(a <= 5_000_000 for a in amounts)


def test_retry_on_failure_then_success():
    results = [Exception("timeout"), {"result": "success", "order_id": "oid-2"}]
    coinone = MagicMock()
    coinone.get_latest_price.return_value = 100_000_000.0
    coinone.place_order.side_effect = results
    ex = OrderExecutor(coinone, twap_slice_krw=5_000_000, max_retries=3, retry_wait=0)
    report = ex.execute(OrderRequest("BTC", "buy", 1_000_000, "dca"))
    assert report.success and coinone.place_order.call_count == 2


def test_exhausted_retries_reports_failure():
    coinone = MagicMock()
    coinone.get_latest_price.return_value = 100_000_000.0
    coinone.place_order.side_effect = Exception("down")
    ex = OrderExecutor(coinone, twap_slice_krw=5_000_000, max_retries=2, retry_wait=0)
    report = ex.execute(OrderRequest("BTC", "buy", 1_000_000, "dca"))
    assert not report.success and coinone.place_order.call_count == 2


def test_api_error_result_counts_as_failure():
    coinone = MagicMock()
    coinone.get_latest_price.return_value = 100_000_000.0
    coinone.place_order.return_value = {"result": "error", "error_code": "113"}
    ex = OrderExecutor(coinone, twap_slice_krw=5_000_000, max_retries=1, retry_wait=0)
    report = ex.execute(OrderRequest("BTC", "buy", 1_000_000, "dca"))
    assert not report.success
```

- [ ] **Step 2: 실패 확인**

Run: `kairos_env/bin/pytest tests/test_order_executor.py -q`
Expected: FAIL — `No module named 'src.execution.executor'`

- [ ] **Step 3: 최소 구현**

```python
# src/execution/executor.py
"""코인원 주문 실행 — 지정가(슬리피지 상한), 재시도, TWAP 분할."""
import math
import time
from dataclasses import dataclass, field
from typing import List

from loguru import logger

from src.risk.guard import OrderRequest

SLIPPAGE_CAP = 0.005  # 스펙 2.3: 슬리피지 상한 0.5%


@dataclass
class ExecutionReport:
    request: OrderRequest
    success: bool
    filled_krw: float = 0.0
    order_ids: List[str] = field(default_factory=list)
    error: str = ""


class OrderExecutor:
    def __init__(self, coinone_client, twap_slice_krw: float,
                 max_retries: int = 3, retry_wait: float = 2.0):
        self.coinone = coinone_client
        self.twap_slice_krw = twap_slice_krw
        self.max_retries = max_retries
        self.retry_wait = retry_wait

    def execute(self, order: OrderRequest) -> ExecutionReport:
        slices = self._split(order.amount_krw)
        report = ExecutionReport(request=order, success=True)
        for slice_krw in slices:
            ok, order_id, err = self._place_with_retry(order, slice_krw)
            if ok:
                report.filled_krw += slice_krw
                report.order_ids.append(order_id)
            else:
                report.success = False
                report.error = err
                logger.error(f"{order.asset} {order.side} 슬라이스 실패: {err}")
                break  # 부분 체결 상태로 중단 — filled_krw로 잔량 파악 가능
        return report

    def _split(self, amount_krw: float) -> List[float]:
        if amount_krw <= self.twap_slice_krw:
            return [amount_krw]
        n = min(6, math.ceil(amount_krw / self.twap_slice_krw))
        return [amount_krw / n] * n

    def _place_with_retry(self, order: OrderRequest, slice_krw: float):
        last_err = ""
        for attempt in range(1, self.max_retries + 1):
            try:
                price = self.coinone.get_latest_price(order.asset)
                limit = price * (1 + SLIPPAGE_CAP if order.side == "buy" else 1 - SLIPPAGE_CAP)
                result = self.coinone.place_order(
                    currency=order.asset,
                    side=order.side,
                    amount=slice_krw,
                    price=limit,
                    amount_in_krw=True,
                )
                if isinstance(result, dict) and result.get("result") == "success":
                    return True, result.get("order_id", ""), ""
                last_err = f"API 오류 응답: {result}"
            except Exception as e:
                last_err = str(e)
            if attempt < self.max_retries:
                time.sleep(self.retry_wait * (2 ** (attempt - 1)))
        return False, "", last_err
```

구현 중 `place_order`의 성공 응답 필드(`result`/`order_id`)를 `src/trading/coinone_client.py:322-475`에서 실제 형식으로 확인해 맞춘다. `amount_in_krw=True`일 때 KRW 금액→수량 변환을 client가 처리하는지 확인하고, 아니면 executor에서 `qty = slice_krw / limit`으로 변환해 넘긴다(테스트도 그에 맞게 수정).

- [ ] **Step 4: 통과 확인 후 커밋**

Run: `kairos_env/bin/pytest tests/test_order_executor.py -q` → 전부 PASS

```bash
git add src/execution/ tests/test_order_executor.py
git commit -m "feat(execution): 지정가·재시도·TWAP 분할 주문 실행기"
```

---

### Task 8: `src/report/reporter.py` — 성과 리포트 (실제 벤치마크)

**Files:**
- Create: `src/report/__init__.py` (빈 파일)
- Create: `src/report/reporter.py`
- Test: `tests/test_reporter.py`

`performance_tracker.py`의 하드코딩 5% 벤치마크를 대체한다: 벤치마크 = 같은 기간 BTC 단순 보유 수익률(Binance 일봉 실데이터).

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_reporter.py
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.report.reporter import Reporter
from src.core.exceptions import DataUnavailableError


def make_reporter(btc_closes):
    binance = MagicMock()
    binance.get_historical_klines.return_value = pd.DataFrame({"Close": btc_closes})
    alerts = MagicMock()
    return Reporter(binance, alerts), alerts


def test_btc_benchmark_return_from_real_prices():
    reporter, _ = make_reporter(btc_closes=[100.0] + [0.0] * 28 + [120.0])
    assert reporter.btc_benchmark_return(days=30) == pytest.approx(0.20)


def test_benchmark_empty_data_raises():
    reporter, _ = make_reporter(btc_closes=[])
    with pytest.raises(DataUnavailableError):
        reporter.btc_benchmark_return(days=30)


def test_monthly_report_includes_vs_benchmark_and_sends_alert():
    reporter, alerts = make_reporter(btc_closes=[100.0] + [0.0] * 28 + [110.0])
    report = reporter.monthly_report(
        portfolio_return=0.15, total_value_krw=110_000_000, crypto_ratio=0.61
    )
    assert report["portfolio_return"] == pytest.approx(0.15)
    assert report["btc_benchmark_return"] == pytest.approx(0.10)
    assert report["excess_return"] == pytest.approx(0.05)
    assert alerts.send_info_alert.called
```

- [ ] **Step 2: 실패 확인**

Run: `kairos_env/bin/pytest tests/test_reporter.py -q`
Expected: FAIL — `No module named 'src.report'`

- [ ] **Step 3: 최소 구현**

```python
# src/report/reporter.py
"""성과 리포트 — 벤치마크는 실제 BTC 보유 수익률 (하드코딩 금지)."""
from typing import Dict

from src.core.exceptions import DataUnavailableError


class Reporter:
    def __init__(self, binance_provider, alert_system):
        self.binance = binance_provider
        self.alerts = alert_system

    def btc_benchmark_return(self, days: int) -> float:
        klines = self.binance.get_historical_klines(
            symbol="BTCUSDT", interval="1d", limit=days + 1
        )
        if klines is None or len(klines) < 2 or "Close" not in getattr(klines, "columns", []):
            raise DataUnavailableError("벤치마크용 BTC 일봉 조회 실패")
        first = float(klines["Close"].iloc[0])
        last = float(klines["Close"].iloc[-1])
        if first <= 0:
            raise DataUnavailableError("벤치마크 시작가 이상")
        return last / first - 1.0

    def monthly_report(
        self, portfolio_return: float, total_value_krw: float, crypto_ratio: float
    ) -> Dict:
        benchmark = self.btc_benchmark_return(days=30)
        report = {
            "portfolio_return": portfolio_return,
            "btc_benchmark_return": benchmark,
            "excess_return": portfolio_return - benchmark,
            "total_value_krw": total_value_krw,
            "crypto_ratio": crypto_ratio,
        }
        self.alerts.send_info_alert(
            "월간 성과 리포트",
            f"수익률 {portfolio_return:+.1%} / BTC {benchmark:+.1%} "
            f"(초과 {report['excess_return']:+.1%}) | "
            f"총자산 {total_value_krw:,.0f} KRW | 크립토 {crypto_ratio:.0%}",
        )
        return report
```

`alert_system.send_info_alert`의 실제 시그니처를 `src/monitoring/alert_system.py:157`에서 확인해 인자를 맞춘다.

- [ ] **Step 4: 통과 확인 후 커밋**

Run: `kairos_env/bin/pytest tests/test_reporter.py -q` → 전부 PASS

```bash
git add src/report/ tests/test_reporter.py
git commit -m "feat(report): 실제 BTC 벤치마크 기반 성과 리포트"
```

---

### Task 9: `kairos1_main.py` 재작성 + 신규 config 스키마

**Files:**
- Modify: `kairos1_main.py` (전면 재작성 — 기존 2513줄 → ~300줄)
- Modify: `config/config.example.yaml` (신규 스키마로 교체)
- Test: `tests/test_kairos_main.py` (기존 것이 있으면 교체, 없으면 생성)

- [ ] **Step 1: 실패하는 테스트 작성** — 오케스트레이션만 검증(모든 의존성 모킹)

```python
# tests/test_kairos_main.py
from unittest.mock import MagicMock

import pytest

from kairos1_main import KairosSimple
from src.portfolio.portfolio import PortfolioSnapshot
from src.strategy.valuation import MarketValuation
from src.core.exceptions import DataUnavailableError
from datetime import datetime


def make_system(fg=50, mayer=1.5, crypto_ratio_holdings=None, krw=40_000_000):
    holdings = crypto_ratio_holdings or {
        "BTC": 30_000_000, "ETH": 18_000_000, "XRP": 6_000_000, "SOL": 6_000_000
    }
    market = MagicMock()
    market.get_valuation.return_value = MarketValuation(fg, mayer)
    market.get_price_change_24h.return_value = {a: 0.0 for a in holdings}
    portfolio = MagicMock()
    portfolio.get_snapshot.return_value = PortfolioSnapshot(
        holdings_krw=holdings, krw_balance=krw, taken_at=datetime.now()
    )
    executor = MagicMock()
    executor.execute.return_value = MagicMock(success=True, filled_krw=0.0)
    alerts = MagicMock()
    sys = KairosSimple.from_components(
        market_data=market, portfolio=portfolio, executor=executor,
        alerts=alerts, config=KairosSimple.default_config(),
    )
    return sys, executor, alerts


def test_weekly_dca_places_buy_orders():
    sys, executor, _ = make_system(fg=20, mayer=0.9)  # 극공포+바닥 → 3.0x
    result = sys.run_weekly_dca(dry_run=False)
    assert result["executed"] > 0
    assert all(c.args[0].side == "buy" for c in executor.execute.call_args_list)


def test_weekly_dca_dry_run_places_nothing():
    sys, executor, _ = make_system()
    sys.run_weekly_dca(dry_run=True)
    executor.execute.assert_not_called()


def test_daily_check_no_orders_within_band():
    sys, executor, _ = make_system()  # 크립토 60% 정확히 목표
    result = sys.run_daily_check(dry_run=False)
    assert result["executed"] == 0


def test_daily_check_sells_when_overweight():
    holdings = {"BTC": 40_000_000, "ETH": 24_000_000, "XRP": 8_000_000, "SOL": 8_000_000}
    sys, executor, _ = make_system(crypto_ratio_holdings=holdings, krw=20_000_000)  # 80%
    result = sys.run_daily_check(dry_run=False)
    sides = [c.args[0].side for c in executor.execute.call_args_list]
    assert "sell" in sides


def test_data_failure_halts_and_alerts():
    """스펙 fail-loud: 데이터 실패 시 주문 0건 + 경고 알림"""
    sys, executor, alerts = make_system()
    sys.market.get_valuation.side_effect = DataUnavailableError("F&G down")
    result = sys.run_weekly_dca(dry_run=False)
    assert result["executed"] == 0 and result["halted"]
    executor.execute.assert_not_called()
    assert alerts.send_warning_alert.called or alerts.send_error_alert.called
```

- [ ] **Step 2: 실패 확인**

Run: `kairos_env/bin/pytest tests/test_kairos_main.py -q`
Expected: FAIL — `ImportError: cannot import name 'KairosSimple'`

- [ ] **Step 3: `kairos1_main.py` 재작성**

구조(전체 코드는 아래 골격을 그대로 구현하되, `_build()`에서 실제 클라이언트 조립은 기존 `_load_configuration`의 config 로딩 패턴을 참고):

```python
#!/usr/bin/env python3
"""KAIROS-Simple: 장기 역발상 매집형 자동 트레이딩.

파이프라인: market_data → strategy(순수 함수) → risk_guard → executor → record/alert
CLI: python kairos1_main.py {weekly-dca|daily-check|report|status} [--dry-run]
"""
import argparse
import sys
from dataclasses import dataclass
from typing import Dict

from loguru import logger

from src.core.exceptions import DataUnavailableError, InsufficientDataError
from src.risk.guard import OrderRequest, PortfolioContext, RiskGuard, RiskLimits
from src.strategy.dca import DCAConfig, plan_weekly_dca
from src.strategy.rebalance import RebalanceConfig, plan_rebalance
from src.strategy.valuation import dca_multiplier


@dataclass(frozen=True)
class SystemConfig:
    dca: DCAConfig
    rebalance: RebalanceConfig
    limits: RiskLimits


class KairosSimple:
    def __init__(self, market_data, portfolio, executor, alerts, risk_guard, config):
        self.market = market_data
        self.portfolio = portfolio
        self.executor = executor
        self.alerts = alerts
        self.guard = risk_guard
        self.config = config
        self._daily_traded_krw = 0.0

    # ---- 조립 ----
    @classmethod
    def default_config(cls) -> SystemConfig:
        weights = {"BTC": 0.5, "ETH": 0.3, "XRP": 0.1, "SOL": 0.1}
        return SystemConfig(
            dca=DCAConfig(
                base_amount_krw=1_000_000, crypto_weights=weights,
                max_single_dca_krw=5_000_000, krw_usage_cap=0.25,
                min_order_krw=10_000,
            ),
            rebalance=RebalanceConfig(
                crypto_target=0.60, band_pp=0.05, crypto_weights=weights,
                relative_band=0.20, min_trade_krw=10_000,
            ),
            limits=RiskLimits(
                max_single_trade_krw=10_000_000, max_daily_volume_krw=50_000_000,
                min_krw_ratio=0.10, fomo_surge_threshold=0.15,
            ),
        )

    @classmethod
    def from_components(cls, market_data, portfolio, executor, alerts, config):
        return cls(market_data, portfolio, executor, alerts,
                   RiskGuard(config.limits), config)

    @classmethod
    def from_yaml(cls, path: str = "config/config.yaml"):
        """실운영 조립: config 로딩 → 실제 클라이언트 생성."""
        # 기존 config_loader 재사용, CoinoneClient/BinanceDataProvider/
        # ExternalAPIClient/DatabaseManager/AlertSystem 조립,
        # MarketDataService/PortfolioService/OrderExecutor 생성 후 cls(...) 반환
        ...

    # ---- 실행 사이클 ----
    def run_weekly_dca(self, dry_run: bool = False) -> Dict:
        try:
            valuation = self.market.get_valuation()
        except (DataUnavailableError, InsufficientDataError) as e:
            return self._halt("주간 DCA", e)
        snap = self.portfolio.get_snapshot()
        mult = dca_multiplier(valuation)
        orders = plan_weekly_dca(self.config.dca, mult, snap.krw_balance)
        logger.info(f"DCA 승수 {mult:.2f} (F&G={valuation.fear_greed}, "
                    f"Mayer={valuation.mayer_ratio:.2f}) → 주문 {len(orders)}건")
        requests = [OrderRequest(o.asset, "buy", o.amount_krw, "dca") for o in orders]
        return self._execute_all("주간 DCA", requests, snap, dry_run)

    def run_daily_check(self, dry_run: bool = False) -> Dict:
        try:
            snap = self.portfolio.get_snapshot()
            orders = plan_rebalance(self.config.rebalance, snap.holdings_krw,
                                    snap.krw_balance)
            if not orders:
                return {"executed": 0, "halted": False, "note": "밴드 내 — 거래 없음"}
            changes = self.market.get_price_change_24h(
                [o.asset for o in orders]
            )
        except (DataUnavailableError, InsufficientDataError) as e:
            return self._halt("일일 밴드 체크", e)
        requests = [OrderRequest(o.asset, o.side, o.amount_krw, "rebalance")
                    for o in orders]
        return self._execute_all("밴드 리밸런싱", requests, snap, dry_run,
                                 price_changes=changes)

    # ---- 내부 ----
    def _execute_all(self, label, requests, snap, dry_run, price_changes=None) -> Dict:
        executed, rejected = 0, []
        # 매도 먼저 실행해 KRW 확보 후 매수 (하락장 리밸런싱 매수 자금)
        for req in sorted(requests, key=lambda r: r.side != "sell"):
            ctx = PortfolioContext(
                total_value_krw=snap.total_value_krw,
                krw_balance=snap.krw_balance,
                daily_traded_krw=self._daily_traded_krw,
                price_change_24h=price_changes or {},
            )
            verdict = self.guard.validate(req, ctx)
            if not verdict.approved:
                rejected.append((req.asset, verdict.reason))
                logger.warning(f"리스크 가드 거부: {req.asset} — {verdict.reason}")
                continue
            if dry_run:
                logger.info(f"[DRY-RUN] {req.side} {req.asset} {req.amount_krw:,.0f} KRW")
                continue
            report = self.executor.execute(req)
            if report.success:
                executed += 1
                self._daily_traded_krw += req.amount_krw
                self.portfolio.record_trade(req.asset, req.side, req.amount_krw,
                                            origin=req.origin)
        result = {"executed": executed, "rejected": rejected, "halted": False}
        logger.info(f"{label} 완료: 실행 {executed}건, 거부 {len(rejected)}건")
        return result

    def _halt(self, label: str, error: Exception) -> Dict:
        logger.error(f"{label} 중단: {error}")
        self.alerts.send_warning_alert(f"{label} 중단", f"데이터 이상: {error}")
        return {"executed": 0, "halted": True, "error": str(error)}


def main():
    parser = argparse.ArgumentParser(description="KAIROS-Simple")
    parser.add_argument("command", choices=["weekly-dca", "daily-check", "report", "status"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    system = KairosSimple.from_yaml()
    if args.command == "weekly-dca":
        print(system.run_weekly_dca(dry_run=args.dry_run))
    elif args.command == "daily-check":
        print(system.run_daily_check(dry_run=args.dry_run))
    # report/status는 Reporter/PortfolioService 호출


if __name__ == "__main__":
    sys.exit(main() or 0)
```

`from_yaml`은 기존 `kairos1_main.py`의 config 로딩(`_load_configuration`, `config_loader` 사용부)을 참고해 완성한다 — `...` 상태로 커밋 금지. `report`/`status` 분기도 실제 구현한다(Reporter.monthly_report / snapshot 출력).

**주의:** 기존 `tests/test_kairos_main*.py` 또는 기존 `KairosSystem`을 import하는 테스트가 있는지 `grep -rl "kairos1_main\|KairosSystem" tests/`로 확인하고, 구 시스템 대상 테스트는 이 태스크에서 함께 삭제한다(Task 11에서 지우는 모듈에 의존하므로).

- [ ] **Step 4: config.example.yaml 교체**

```yaml
# KAIROS-Simple 설정 — 장기 역발상 매집형
# 철학: 싸질수록 사고, 비싸질수록 판다. 목업 데이터 금지, 데이터 실패 시 거래 중단.

api:
  coinone:
    api_key: "${COINONE_API_KEY}"
    secret_key: "${COINONE_SECRET_KEY}"
    sandbox: "${COINONE_SANDBOX:true}"
    rate_limit: "${API_RATE_LIMIT_PER_MINUTE:100}"
    timeout: "${API_REQUEST_TIMEOUT:30}"

strategy:
  targets:
    crypto: 0.60          # 고정 목표 — 시장 상황에 따라 바꾸지 않는다
    weights: { BTC: 0.50, ETH: 0.30, XRP: 0.10, SOL: 0.10 }
  rebalance:
    band_pp: 0.05         # 총 크립토 비중 ±5%p 이탈 시에만 거래
    relative_band: 0.20   # 개별 코인 상대 ±20%
    min_trade_krw: 10000
  dca:
    base_amount_krw: 1000000
    max_single_dca_krw: 5000000
    krw_usage_cap: 0.25

risk:
  max_single_trade_krw: 10000000
  max_daily_volume_krw: 50000000
  min_krw_ratio: 0.10
  fomo_surge_threshold: 0.15
  data_max_age_hours: 24

execution:
  twap_slice_krw: 5000000
  slippage_cap: 0.005
  max_retries: 3

scheduler:
  weekly_dca:   { cron: "0 9 * * 1", timezone: "Asia/Seoul" }
  daily_check:  { cron: "0 9 * * *", timezone: "Asia/Seoul" }
  monthly_report: { cron: "0 9 1 * *", timezone: "Asia/Seoul" }

notifications:
  slack:
    enabled: false
    webhook_url: "${SLACK_WEBHOOK_URL}"
    channel: "${SLACK_CHANNEL:#trading-alerts}"
  email:
    enabled: false

logging:
  level: "${LOG_LEVEL:INFO}"
  file_path: "./logs/kairos1.log"

database:
  url: "${DATABASE_URL:sqlite:///./data/kairos1.db}"
```

- [ ] **Step 5: 통과 확인 후 커밋**

Run: `kairos_env/bin/pytest tests/test_kairos_main.py -q` → PASS
Run: `kairos_env/bin/pytest tests/ -q` → 삭제한 구 엔트리포인트 테스트 외 전부 PASS

```bash
git add kairos1_main.py config/config.example.yaml tests/test_kairos_main.py
git rm <구 KairosSystem 의존 테스트들>
git commit -m "feat(main): KAIROS-Simple 오케스트레이터로 엔트리포인트 전면 교체"
```

---

### Task 10: 가짜 데이터 모듈 삭제 (1차)

**Files:**
- Delete: `src/core/onchain_stub_data.py`, `src/core/onchain_data_analyzer.py`, `src/core/macro_economic_analyzer.py`
- Delete: `tests/test_onchain_data_analyzer.py`, `tests/test_macro_economic_analyzer.py` (실제 파일명은 `ls tests/`로 확인)
- Delete: `scripts/market_analysis_hourly.py` (가짜 분석기 2종에 의존 — 대체 기능은 daily-check가 수행)

- [ ] **Step 1: 의존처 확인**

Run: `grep -rln "onchain_data_analyzer\|macro_economic_analyzer\|onchain_stub_data" src/ scripts/ tests/ kairos1_main.py kairos1_multi.py kairos1_enhanced_multi.py`
Expected: 삭제 대상 자신들 + `multi_account_feature_manager.py`, `market_season_filter.py`(DB 통합부), 구 엔트리포인트들 — 전부 Task 11에서 함께 삭제되는 파일인지 확인. Task 11 삭제 대상이 아닌 파일에서 참조가 나오면 그 import/호출부를 먼저 제거.

- [ ] **Step 2: 삭제**

```bash
git rm src/core/onchain_stub_data.py src/core/onchain_data_analyzer.py \
       src/core/macro_economic_analyzer.py scripts/market_analysis_hourly.py
git rm tests/test_onchain_data_analyzer.py tests/test_macro_economic_analyzer.py
```

- [ ] **Step 3: 전체 테스트로 파급 확인**

Run: `kairos_env/bin/pytest tests/ -q 2>&1 | tail -20`
Expected: PASS. ImportError가 나면 해당 참조부(Task 11 대상 파일이면 Task 11로 이월하지 말고 import 라인만 즉시 제거) 수정.

- [ ] **Step 4: 커밋**

```bash
git commit -m "refactor(core)!: 목업 데이터 모듈 삭제 (온체인/매크로/스텁)

가짜 신호가 자산 배분에 ±20% 반영되던 경로 제거"
```

---

### Task 11: 철학 충돌·중복 모듈 삭제 (2차)

**Files (Delete):**
- 엔트리포인트: `kairos1_multi.py`, `kairos1_enhanced_multi.py`
- 계절 스위칭: `src/core/market_season_filter.py`
- 멀티계좌: `src/core/multi_account_manager.py`, `multi_account_coordinator.py`, `multi_account_feature_manager.py`, `multi_portfolio_manager.py`, `multi_rebalancing_engine.py`, `src/cli/multi_account_cli.py`, `src/cli/enhanced_multi_account_cli.py`
- 범위 축소: `src/core/tax_optimization_system.py`, `scenario_response_system.py`, `behavioral_bias_prevention.py`, `risk_parity_model.py`, `adaptive_portfolio_manager.py`, `dynamic_portfolio_optimizer.py`, `dynamic_execution_engine.py`, `smart_execution_engine.py`, `multi_timeframe_analyzer.py`, `composite_signal_analyzer.py`, `opportunistic_buyer.py`, `system_coordinator.py`, `advanced_performance_analytics.py`, `dca_plus_strategy.py`, `rebalancer.py`, `portfolio_manager.py`, `system_integration_helper.py`, `src/cli/portfolio_optimizer_cli.py`
- 스크립트: `scripts/execute_opportunistic_buy.py`, `scripts/quarterly_rebalance.py`, `scripts/apply_improvements.py` (`scripts/performance_report.py`는 열어보고 Reporter로 대체 가능하면 삭제, 독립 유용하면 신규 모듈 기반으로 수정)
- 각 모듈의 `tests/test_*.py` 전부 (`ls tests/`와 대조하여 매칭 삭제)

**유지:** `src/core/types.py`, `exceptions.py`, `resilience.py`, `base_service.py`(참조 여부 확인 후 무참조면 삭제), `async_client.py`(신규 파이프라인 미사용이면 삭제), `dca_plus_strategy.py`의 로직은 이미 Task 1-2가 대체.

- [ ] **Step 1: 삭제 전 역참조 확인**

Run: 각 삭제 대상에 대해 `grep -rln "<모듈명>" src/ scripts/ tests/ *.py | grep -v <삭제목록>` — 유지 파일에서 참조가 남아 있으면 해당 참조부터 제거.
특히 `src/core/__init__.py`와 `src/utils/config_factory.py`, `src/utils/config_loader.py`가 삭제 모듈을 import/생성하는지 확인하고 정리.

- [ ] **Step 2: git rm 실행 (위 목록 전부)**

- [ ] **Step 3: 전체 테스트**

Run: `kairos_env/bin/pytest tests/ -q 2>&1 | tail -20`
Expected: PASS (커버리지 25% 기준도 통과 — 남은 코드가 적어져 비율은 오히려 상승).

- [ ] **Step 4: 죽은 설정 정리**

`src/utils/constants.py`에서 삭제된 모듈만 쓰던 상수(`DEFAULT_BTC_DOMINANCE`, `MA_CALCULATION_FALLBACK_RATIO` 등)를 `grep -rn <상수명> src/`로 확인 후 무참조면 제거.

- [ ] **Step 5: 커밋**

```bash
git commit -m "refactor!: 철학 충돌(계절 스위칭)·중복·범위외 모듈 일괄 삭제

src/core 30+개 → 핵심 8모듈 구조로 단순화"
```

---

### Task 12: 유지 모듈의 잔여 가짜 폴백 제거

**Files:**
- Modify: `src/utils/market_data_provider.py:68,78` — `fallback_ma = current_price * 0.9`, 비상 `50000.0` 앵커 제거
- Modify: `src/utils/external_api_client.py` — `DEFAULT_USD_KRW_RATE`/`DEFAULT_BTC_DOMINANCE` 폴백 반환을 예외로 교체 (단, 신규 파이프라인이 이 두 값을 안 쓰면 메서드 자체 삭제 검토)
- Modify: `src/monitoring/performance_tracker.py:152-154` — 하드코딩 5% 벤치마크 제거, `Reporter.btc_benchmark_return` 사용 또는 메서드 삭제
- Test: 해당 모듈 기존 테스트 수정 (폴백 기대 → 예외 기대)

- [ ] **Step 1: 신규 파이프라인의 실사용 확인**

Run: `grep -rn "market_data_provider\|MarketDataProvider" src/ kairos1_main.py scripts/`
신규 파이프라인은 `MarketDataService`를 쓰므로 `market_data_provider.py`가 무참조면 **파일째 삭제**가 정답(테스트 포함). 참조가 남으면 폴백만 예외로 교체.

- [ ] **Step 2: 폴백 → 예외 교체 (파일 유지 시)**

기존:
```python
fallback_ma = current_price * 0.9
```
교체:
```python
raise InsufficientDataError("200주MA 계산 데이터 부족 — 폴백 금지")
```
기존 테스트에서 `assert result == pytest.approx(price * 0.9)` 류를 `pytest.raises(InsufficientDataError)`로 수정.

- [ ] **Step 3: 전체 테스트 후 커밋**

Run: `kairos_env/bin/pytest tests/ -q 2>&1 | tail -5` → PASS

```bash
git commit -m "refactor(data): 하드코딩 폴백 전면 제거 — 데이터 실패는 예외로"
```

---

### Task 13: 백테스트 스크립트 (순수 함수 재사용)

**Files:**
- Create: `scripts/backtest_longterm.py`
- Test: `tests/test_backtest_longterm.py`

CLAUDE.md 백테스팅 체크리스트 반영: 수수료 0.2% + 슬리피지 0.2%, 동적 포지션 사이징(전략 함수가 담당), look-ahead 금지(t 시점 결정에 t-1까지 데이터만).

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_backtest_longterm.py
import numpy as np
import pandas as pd
import pytest

from scripts.backtest_longterm import BacktestResult, run_backtest


def make_price_series(pattern: str, weeks: int = 300) -> pd.DataFrame:
    """주봉 Close 시계열 생성. F&G는 가격 모멘텀 프록시로 백테스트 내부 생성."""
    rng = np.random.default_rng(42)
    if pattern == "bull":
        closes = 1000 * np.cumprod(1 + rng.normal(0.01, 0.03, weeks))
    elif pattern == "bear":
        closes = 1000 * np.cumprod(1 + rng.normal(-0.008, 0.03, weeks))
    else:  # sideways
        closes = 1000 * np.cumprod(1 + rng.normal(0.0, 0.02, weeks))
    idx = pd.date_range("2018-01-01", periods=weeks, freq="W")
    return pd.DataFrame({"Close": closes}, index=idx)


def test_costs_are_applied():
    df = make_price_series("sideways")
    r0 = run_backtest(df, fee=0.0, slippage=0.0)
    r1 = run_backtest(df, fee=0.002, slippage=0.002)
    assert r1.total_trades == r0.total_trades
    assert r1.final_value < r0.final_value  # 비용 반영 시 성과 하락


def test_counter_cyclical_behavior_in_bear():
    """하락장에서 매수 체결 금액 > 매도 금액 (매집 동작 검증)"""
    r = run_backtest(make_price_series("bear"))
    assert r.total_buy_krw > r.total_sell_krw


def test_profit_taking_in_bull():
    """상승장에서 리밸런싱 매도(익절)가 발생해야 함"""
    r = run_backtest(make_price_series("bull"))
    assert r.total_sell_krw > 0


def test_no_lookahead():
    """t주차까지의 결과는 이후 데이터를 잘라도 동일해야 함"""
    df = make_price_series("sideways", weeks=300)
    full = run_backtest(df)
    truncated = run_backtest(df.iloc[:260])
    n = len(truncated.weekly_values)
    assert full.weekly_values[: n] == pytest.approx(truncated.weekly_values, rel=1e-9)


def test_result_reports_required_metrics():
    r = run_backtest(make_price_series("sideways"))
    assert r.max_drawdown <= 0
    assert isinstance(r.sharpe, float)
```

- [ ] **Step 2: 실패 확인**

Run: `kairos_env/bin/pytest tests/test_backtest_longterm.py -q`
Expected: FAIL — `No module named 'scripts.backtest_longterm'` (scripts에 `__init__.py` 없으면 함께 생성)

- [ ] **Step 3: 구현**

```python
# scripts/backtest_longterm.py
"""KAIROS-Simple 백테스트 — 실거래와 동일한 순수 함수 사용.

단순화: BTC 단일 자산(주봉), F&G는 미래 데이터가 없으므로
회고적 프록시(직전 12주 수익률 분위)로 생성 — look-ahead 없음.
"""
from dataclasses import dataclass, field
from typing import List

import numpy as np
import pandas as pd

from src.strategy.dca import DCAConfig, plan_weekly_dca
from src.strategy.rebalance import RebalanceConfig, plan_rebalance
from src.strategy.valuation import MarketValuation, dca_multiplier

WEEKLY_BASE_DCA = 250_000  # 주간 신규 적립 현금


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
    weekly: pd.DataFrame, fee: float = 0.002, slippage: float = 0.002,
    crypto_target: float = 0.60,
) -> BacktestResult:
    dca_cfg = DCAConfig(
        base_amount_krw=WEEKLY_BASE_DCA, crypto_weights={"BTC": 1.0},
        max_single_dca_krw=5 * WEEKLY_BASE_DCA, krw_usage_cap=0.25,
        min_order_krw=1_000,
    )
    reb_cfg = RebalanceConfig(
        crypto_target=crypto_target, band_pp=0.05, crypto_weights={"BTC": 1.0},
        relative_band=0.20, min_trade_krw=1_000,
    )
    cost = fee + slippage

    krw, btc_qty = 10_000_000.0, 0.0
    buys = sells = trades = 0.0
    values: List[float] = []
    closes = weekly["Close"]

    for t in range(len(closes)):
        price = float(closes.iloc[t])
        krw += WEEKLY_BASE_DCA  # 주간 적립

        history = closes.iloc[: t + 1]  # t 시점까지의 데이터만
        if len(history) >= 200:
            ma = float(history.iloc[-200:].mean())
            ret12 = float(history.iloc[-1] / history.iloc[-13] - 1) if t >= 12 else 0.0
            valuation = MarketValuation(_fg_proxy(ret12), price / ma)
            mult = dca_multiplier(valuation)
        else:
            mult = 1.0  # 워밍업 구간: 기본 DCA만

        for order in plan_weekly_dca(dca_cfg, mult, krw):
            spend = order.amount_krw
            btc_qty += spend * (1 - cost) / price
            krw -= spend
            buys += spend; trades += 1

        holdings = {"BTC": btc_qty * price}
        for order in plan_rebalance(reb_cfg, holdings, krw):
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
    weekly_ret = series.pct_change().dropna()
    sharpe = float(weekly_ret.mean() / weekly_ret.std() * np.sqrt(52)) if len(weekly_ret) > 1 and weekly_ret.std() > 0 else 0.0
    drawdown = float((series / series.cummax() - 1).min())
    return BacktestResult(
        final_value=float(series.iloc[-1]), total_buy_krw=float(buys),
        total_sell_krw=float(sells), total_trades=int(trades),
        max_drawdown=drawdown, sharpe=sharpe, weekly_values=values,
    )


if __name__ == "__main__":
    from src.utils.binance_data_provider import BinanceDataProvider

    df = BinanceDataProvider().get_historical_klines("BTCUSDT", "1w", limit=450)
    result = run_backtest(df)
    print(f"최종 자산: {result.final_value:,.0f} KRW")
    print(f"총 매수 {result.total_buy_krw:,.0f} / 총 매도 {result.total_sell_krw:,.0f}")
    print(f"거래 {result.total_trades}건, MDD {result.max_drawdown:.1%}, Sharpe {result.sharpe:.2f}")
```

- [ ] **Step 4: 테스트 통과 확인 + 실데이터 1회 실행**

Run: `kairos_env/bin/pytest tests/test_backtest_longterm.py -q` → PASS
Run: `kairos_env/bin/python scripts/backtest_longterm.py` (네트워크 가능 시) → 지표 출력 확인, 결과 수치를 커밋 메시지에 기록

- [ ] **Step 5: 커밋**

```bash
git add scripts/backtest_longterm.py tests/test_backtest_longterm.py
git commit -m "feat(backtest): 실전 동일 순수함수 백테스트 (수수료·슬리피지 반영)"
```

---

### Task 14: 최종 검증 및 문서 갱신

**Files:**
- Modify: `README.md` (아키텍처/CLI 설명을 KAIROS-Simple 기준으로 교체)
- Modify: `CLAUDE.md` (필요 시 모듈 구조 언급 갱신 — 전략 원칙 섹션은 유지)

- [ ] **Step 1: 전체 스위트 + 커버리지**

Run: `kairos_env/bin/pytest tests/ -q --cov=src --cov-report=term 2>&1 | tail -25`
Expected: 전부 PASS, 신규 모듈(src/strategy, src/risk, src/data, src/portfolio, src/execution, src/report) 각각 90%+ 확인. 미달 모듈은 누락 라인 확인 후 테스트 보강.

- [ ] **Step 2: 죽은 참조 최종 스캔**

Run: `grep -rn "market_season_filter\|dca_plus_strategy\|opportunistic_buyer\|multi_account\|onchain\|macro_economic" src/ scripts/ tests/ *.py docs/ --include="*.py"`
Expected: 0건 (docs 내 스펙/플랜 문서 제외)

- [ ] **Step 3: dry-run 스모크 테스트**

Run: `kairos_env/bin/python kairos1_main.py daily-check --dry-run` (config.yaml 없으면 example 복사, 샌드박스 모드)
Expected: 데이터 조회 → 밴드 판정 → "[DRY-RUN]" 로그 또는 "밴드 내 — 거래 없음", 예외 없이 종료. 네트워크 불가 환경이면 `DataUnavailableError`로 **깨끗하게 중단**되는지 확인(이것도 스펙 검증).

- [ ] **Step 4: README 갱신 후 최종 커밋**

```bash
git add README.md CLAUDE.md
git commit -m "docs: KAIROS-Simple 아키텍처 반영"
```

---

## Self-Review 결과

- **스펙 커버리지**: 철학 통일(T1-3,9,11), 목업 제거(T10,12), 승수표(T1), 한도(T4), fail-loud(T1,4,5,12), TWAP(T7), 실벤치마크(T8), 백테스트(T13), 비중/밴드(T3,9) — 전 항목 태스크 매핑 확인.
- **플레이스홀더**: `from_yaml`의 `...`는 Step 3 본문에 "커밋 금지, 기존 로딩 패턴 참고해 완성" 지시로 처리. 삭제 목록은 전수 명시.
- **타입 일관성**: `OrderRequest(asset, side, amount_krw, origin)`을 T4에서 정의, T7/T9가 동일 시그니처 사용. `DCAConfig`/`RebalanceConfig` 필드명 T2/T3/T9/T13 일치 확인.
