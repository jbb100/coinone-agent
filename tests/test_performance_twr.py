"""TWR(시간가중수익률) 계산 테스트 — 입출금이 수익률로 잡히면 안 된다.

기존 월간 리포트의 '30일 총자산 변화'는 입금과 수익이 섞여 전략이
백테스트 기대를 따라가는지 검증할 수 없었다 (감사 허점 5).
"""
import pytest

from src.report.performance import DailyPoint, compute_twr, infer_external_flow


def P(date, total, krw):
    return DailyPoint(date=date, total_value_krw=total, krw_balance=krw)


class TestInferExternalFlow:
    def test_deposit_detected_from_krw_delta(self):
        # 거래 없이 KRW가 100만원 늘면 = 외부 입금 100만원
        prev, cur = P("2026-08-01", 10_000_000, 4_000_000), P("2026-08-02", 11_000_000, 5_000_000)
        assert infer_external_flow(prev, cur, buys_krw=0.0, sells_krw=0.0) == pytest.approx(1_000_000)

    def test_buy_is_not_a_flow(self):
        # KRW 100만원 감소 + 매수 100만원 = 내부 자산 전환, 외부 흐름 0
        prev, cur = P("2026-08-01", 10_000_000, 4_000_000), P("2026-08-02", 10_000_000, 3_000_000)
        assert infer_external_flow(prev, cur, buys_krw=1_000_000, sells_krw=0.0) == pytest.approx(0.0)

    def test_sell_is_not_a_flow(self):
        prev, cur = P("2026-08-01", 10_000_000, 4_000_000), P("2026-08-02", 10_000_000, 5_000_000)
        assert infer_external_flow(prev, cur, buys_krw=0.0, sells_krw=1_000_000) == pytest.approx(0.0)

    def test_withdrawal_detected(self):
        prev, cur = P("2026-08-01", 10_000_000, 4_000_000), P("2026-08-02", 8_000_000, 2_000_000)
        assert infer_external_flow(prev, cur, buys_krw=0.0, sells_krw=0.0) == pytest.approx(-2_000_000)


class TestComputeTwr:
    def test_pure_market_gain_without_flows(self):
        points = [P("2026-07-01", 10_000_000, 4_000_000),
                  P("2026-07-31", 12_000_000, 4_000_000)]
        twr, days = compute_twr(points, {})
        assert twr == pytest.approx(0.20)
        assert days == 30

    def test_deposit_does_not_inflate_return(self):
        # 시장 변동 0, 입금 500만원만 → TWR 0%
        points = [P("2026-07-01", 10_000_000, 4_000_000),
                  P("2026-07-02", 15_000_000, 9_000_000)]
        twr, _ = compute_twr(points, {})
        assert twr == pytest.approx(0.0)

    def test_gain_plus_deposit_isolates_gain(self):
        # 1일차: +10% 시장 수익 / 2일차: 입금 1000만원만
        points = [P("2026-07-01", 10_000_000, 0),
                  P("2026-07-02", 11_000_000, 0),
                  P("2026-07-03", 21_000_000, 10_000_000)]
        twr, _ = compute_twr(points, {})
        assert twr == pytest.approx(0.10)

    def test_internal_trades_do_not_distort(self):
        # 매수(내부 전환)가 있는 날, 시장 수익 +5%만 TWR에 반영
        points = [P("2026-07-01", 10_000_000, 4_000_000),
                  P("2026-07-02", 10_500_000, 3_000_000)]
        twr, _ = compute_twr(points, {"2026-07-02": (1_000_000, 0.0)})
        assert twr == pytest.approx(0.05)

    def test_insufficient_points_returns_none(self):
        assert compute_twr([P("2026-07-01", 10_000_000, 0)], {}) is None
        assert compute_twr([], {}) is None

    def test_zero_baseline_skipped_fail_safe(self):
        # 총자산 0인 스냅샷(수집 실패 잔재)은 수익률 계산에서 건너뛴다
        points = [P("2026-07-01", 10_000_000, 0),
                  P("2026-07-02", 0, 0),
                  P("2026-07-03", 11_000_000, 0)]
        result = compute_twr(points, {})
        assert result is not None
        twr, _ = result
        assert twr == pytest.approx(0.10)
