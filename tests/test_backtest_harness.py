"""
백테스트 하네스 (scripts/backtest_regime_models.py) 시뮬레이션 로직 테스트

NOTE: 여기서 쓰는 가격 시계열은 시뮬레이션 '엔진'의 정확성(수수료, 임계값,
비중 이동)을 검증하기 위한 테스트 픽스처다. 실제 백테스트 '결과'는 반드시
실데이터(Binance/CoinGecko)로 실행해야 하며, 데이터 수집 실패 시 하네스는
합성 데이터를 만들지 않고 중단한다.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "scripts"))

from backtest_regime_models import (
    _simulate,
    run_legacy,
    run_valuation,
    run_buy_and_hold,
    run_static_5050,
    TRADE_FEE,
    REBALANCE_THRESHOLD,
)


def _weekly_index(n):
    return pd.date_range("2020-01-05", periods=n, freq="W", tz="UTC")


def _flat_market(n=50, price=100.0):
    idx = _weekly_index(n)
    prices = pd.Series(np.full(n, price), index=idx)
    ma = pd.Series(np.full(n, price), index=idx)
    return prices, ma


class TestSimulateEngine:
    def test_no_trade_below_threshold(self):
        """목표와 현재 비중 차이가 임계값 이하면 매매하지 않음"""
        prices, ma = _flat_market()

        def fn(date, price, m, state, current_w):
            return current_w + REBALANCE_THRESHOLD * 0.5  # 임계값 미만 차이

        result = _simulate(prices, ma, fn, "no-trade")
        assert result.trades == 0
        assert result.values.iloc[-1] == pytest.approx(100.0)

    def test_fee_deducted_on_trade(self):
        """매매 시 수수료가 차감됨"""
        prices, ma = _flat_market()

        def fn(date, price, m, state, current_w):
            return 0.50  # 첫 주에 0% → 50% 매수 1회

        result = _simulate(prices, ma, fn, "one-trade")
        assert result.trades == 1
        expected_fee = 50.0 * TRADE_FEE  # 50원어치 매수 수수료
        assert result.values.iloc[-1] == pytest.approx(100.0 - expected_fee, rel=1e-6)

    def test_none_target_means_no_action(self):
        """판단 불가(None) 시 거래 없음 (fail-safe)"""
        prices, ma = _flat_market()

        def fn(date, price, m, state, current_w):
            return None

        result = _simulate(prices, ma, fn, "abstain")
        assert result.trades == 0

    def test_cash_never_negative(self):
        """수수료 포함 매수 한도로 현금이 음수가 되지 않음"""
        prices, ma = _flat_market()

        def fn(date, price, m, state, current_w):
            return 1.0

        result = _simulate(prices, ma, fn, "all-in")
        # 최종 가치 = 100 - 수수료(현금 한도 내), 가치가 양수이고 100 미만
        assert 99.0 < result.values.iloc[-1] < 100.0


class TestStrategyBehavior:
    def _bear_then_recovery(self):
        """MA=100 고정, 가격이 130 → 60 → 130으로 하락 후 회복하는 픽스처"""
        n = 60
        idx = _weekly_index(n)
        down = np.linspace(130, 60, 25)
        up = np.linspace(60, 130, 35)
        prices = pd.Series(np.concatenate([down, up]), index=idx)
        ma = pd.Series(np.full(n, 100.0), index=idx)
        return prices, ma

    def test_legacy_sells_low_valuation_buys_low(self):
        """핵심 차이 검증: 바닥(R<1)에서 legacy는 저비중, valuation은 고비중"""
        prices, ma = self._bear_then_recovery()

        legacy = run_legacy(prices, ma)
        valuation = run_valuation(prices, ma)

        bottom_idx = prices.idxmin()  # R = 0.6 시점

        # legacy: RISK_OFF → 30% (5% 임계값 리밸런싱이므로 ±5%p 표류 허용)
        assert legacy.weights[bottom_idx] == pytest.approx(0.30, abs=REBALANCE_THRESHOLD + 0.01)
        # valuation: DEEP_VALUE → 75%를 향해 매집 (최소 60% 이상 도달)
        assert valuation.weights[bottom_idx] > 0.60

    def test_valuation_reduces_in_euphoria(self):
        """과열(R>=2.8)에서 valuation은 비중을 25%까지 축소"""
        n = 80
        idx = _weekly_index(n)
        prices = pd.Series(np.linspace(150, 320, n), index=idx)  # R: 1.5 → 3.2
        ma = pd.Series(np.full(n, 100.0), index=idx)

        result = run_valuation(prices, ma)
        # 마지막 구간(R>3)에서 25% 부근
        assert result.weights.iloc[-1] == pytest.approx(0.25, abs=0.06)

    def test_benchmarks_run(self):
        prices, ma = self._bear_then_recovery()
        bh = run_buy_and_hold(prices, ma)
        static = run_static_5050(prices, ma)
        assert bh.weights.iloc[-1] > 0.99
        assert static.weights.iloc[-1] == pytest.approx(0.50, abs=REBALANCE_THRESHOLD + 0.01)

    def test_metrics_computable(self):
        prices, ma = self._bear_then_recovery()
        result = run_valuation(prices, ma)
        m = result.metrics()
        assert set(m.keys()) == {"total_return", "cagr", "mdd", "sharpe", "calmar"}
        assert m["mdd"] <= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
