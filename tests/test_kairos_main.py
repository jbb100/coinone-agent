"""kairos1_main.py 테스트 — KAIROS-Simple 오케스트레이션."""
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from kairos1_main import KairosSimple
from src.core.exceptions import DataUnavailableError
from src.portfolio.portfolio import PortfolioSnapshot
from src.strategy.valuation import MarketValuation


def make_system(fg=50, mayer=1.5, holdings=None, krw=40_000_000):
    holdings = holdings or {
        "BTC": 30_000_000, "ETH": 18_000_000, "XRP": 6_000_000, "SOL": 6_000_000
    }
    market = MagicMock()
    market.get_valuation.return_value = MarketValuation(fg, mayer)
    market.get_mayer_ratio.return_value = mayer
    market.get_price_change_24h.return_value = {a: 0.0 for a in holdings}
    portfolio = MagicMock()
    portfolio.get_snapshot.return_value = PortfolioSnapshot(
        holdings_krw=holdings, krw_balance=krw, taken_at=datetime.now()
    )
    executor = MagicMock()
    executor.execute.return_value = MagicMock(success=True, filled_krw=1.0)
    alerts = MagicMock()
    sys_ = KairosSimple.from_components(
        market_data=market, portfolio=portfolio, executor=executor,
        alerts=alerts, config=KairosSimple.default_config(),
    )
    return sys_, executor, alerts


def test_weekly_dca_places_buy_orders():
    sys_, executor, _ = make_system(fg=20, mayer=0.9)  # 극공포+바닥 → 3.0x
    result = sys_.run_weekly_dca(dry_run=False)
    assert result["executed"] > 0
    assert all(c.args[0].side == "buy" for c in executor.execute.call_args_list)


def test_weekly_dca_dry_run_places_nothing():
    sys_, executor, _ = make_system(fg=20, mayer=0.9)  # 매수 계획이 있는 상황
    result = sys_.run_weekly_dca(dry_run=True)
    executor.execute.assert_not_called()
    assert result["executed"] == 0 and not result["halted"]


def test_weekly_dca_skips_when_crypto_at_target():
    """일관성 불변식: 크립토 비중이 이미 목표(60%)면 공포장이어도 DCA는
    현금을 보존한다 — 10분 뒤 리밸런서가 되팔 물량을 사지 않는다"""
    sys_, executor, _ = make_system(fg=20, mayer=1.5)  # 크립토 정확히 60%
    result = sys_.run_weekly_dca(dry_run=False)
    executor.execute.assert_not_called()
    assert result["executed"] == 0 and not result["halted"]


def test_weekly_dca_capped_by_target_headroom():
    """크립토 59%/목표 60% → 여유 1M만 매수 (계획 2M이어도 목표 초과 금지)"""
    holdings = {
        "BTC": 29_500_000, "ETH": 17_700_000, "XRP": 5_900_000, "SOL": 5_900_000
    }
    sys_, executor, _ = make_system(fg=20, mayer=1.5, holdings=holdings,
                                    krw=41_000_000)
    result = sys_.run_weekly_dca(dry_run=False)
    total = sum(c.args[0].amount_krw for c in executor.execute.call_args_list)
    assert result["executed"] > 0
    assert total == pytest.approx(1_000_000)


def test_weekly_dca_cap_uses_fixed_target_when_tilt_disabled():
    """틸트 꺼짐 + 바닥권이어도 고정 목표(60%) 기준으로 상한 적용"""
    import dataclasses
    sys_, executor, _ = make_system(fg=20, mayer=0.8)  # 크립토 정확히 60%
    sys_.config = dataclasses.replace(sys_.config, contrarian_tilt=False)
    sys_.run_weekly_dca(dry_run=False)
    executor.execute.assert_not_called()


def test_daily_check_no_orders_within_band():
    sys_, executor, _ = make_system()  # 크립토 60% 정확히 목표
    result = sys_.run_daily_check(dry_run=False)
    assert result["executed"] == 0
    executor.execute.assert_not_called()


def test_daily_check_sells_when_overweight():
    """상승장: 크립토 80% → 매도(익절) 주문 발생"""
    holdings = {"BTC": 40_000_000, "ETH": 24_000_000, "XRP": 8_000_000, "SOL": 8_000_000}
    sys_, executor, _ = make_system(holdings=holdings, krw=20_000_000)
    result = sys_.run_daily_check(dry_run=False)
    sides = [c.args[0].side for c in executor.execute.call_args_list]
    assert "sell" in sides
    assert result["executed"] > 0


def test_daily_check_buys_when_underweight():
    """하락장: 크립토 40% → 매수(저가 매집) 주문 발생"""
    holdings = {"BTC": 20_000_000, "ETH": 12_000_000, "XRP": 4_000_000, "SOL": 4_000_000}
    sys_, executor, _ = make_system(holdings=holdings, krw=60_000_000)
    sys_.run_daily_check(dry_run=False)
    sides = [c.args[0].side for c in executor.execute.call_args_list]
    assert "buy" in sides


def test_sells_execute_before_buys():
    """매도 먼저 실행해 KRW 확보 후 매수"""
    holdings = {"BTC": 50_000_000, "ETH": 12_000_000, "XRP": 4_000_000, "SOL": 4_000_000}
    sys_, executor, _ = make_system(holdings=holdings, krw=30_000_000)
    sys_.run_daily_check(dry_run=False)
    sides = [c.args[0].side for c in executor.execute.call_args_list]
    assert sides == sorted(sides, key=lambda s: s != "sell")


def test_daily_check_tilts_target_up_in_bottom_zone():
    """역발상 틸트: Mayer<1(바닥권) → 목표 70%. 크립토 60%는 10%p 미달
    (밴드 5%p 초과 이탈)이므로 매수 주문이 나가야 함"""
    sys_, executor, _ = make_system(mayer=0.8)  # 크립토 정확히 60%
    result = sys_.run_daily_check(dry_run=False)
    sides = [c.args[0].side for c in executor.execute.call_args_list]
    assert result["executed"] > 0
    assert set(sides) == {"buy"}


def test_daily_check_tilts_target_down_when_overheated():
    """역발상 틸트: Mayer≥3(과열) → 목표 40%. 크립토 60%는 20%p 초과
    이므로 매도(익절) 주문이 나가야 함"""
    sys_, executor, _ = make_system(mayer=3.2)
    result = sys_.run_daily_check(dry_run=False)
    sides = [c.args[0].side for c in executor.execute.call_args_list]
    assert result["executed"] > 0
    assert set(sides) == {"sell"}


def test_daily_check_neutral_mayer_keeps_base_target():
    """Mayer 1.0-2.0(적정) → 기본 목표 60% 유지, 밴드 내 거래 없음"""
    sys_, executor, _ = make_system(mayer=1.5)
    result = sys_.run_daily_check(dry_run=False)
    assert result["executed"] == 0
    executor.execute.assert_not_called()


def test_daily_check_tilt_disabled_uses_fixed_target():
    """contrarian_tilt=False면 바닥권에서도 고정 60% 유지"""
    import dataclasses
    sys_, executor, _ = make_system(mayer=0.8)
    sys_.config = dataclasses.replace(sys_.config, contrarian_tilt=False)
    result = sys_.run_daily_check(dry_run=False)
    assert result["executed"] == 0
    executor.execute.assert_not_called()


def test_daily_check_halts_when_mayer_unavailable():
    """스펙 fail-loud: 틸트용 Mayer 조회 실패 시 리밸런싱 중단 + 알림"""
    sys_, executor, alerts = make_system()
    sys_.market.get_mayer_ratio.side_effect = DataUnavailableError("Binance down")
    result = sys_.run_daily_check(dry_run=False)
    assert result["executed"] == 0 and result["halted"]
    executor.execute.assert_not_called()
    assert alerts.send_warning_alert.called


def test_data_failure_halts_and_alerts():
    """스펙 fail-loud: 데이터 실패 시 주문 0건 + 경고 알림"""
    sys_, executor, alerts = make_system()
    sys_.market.get_valuation.side_effect = DataUnavailableError("F&G down")
    result = sys_.run_weekly_dca(dry_run=False)
    assert result["executed"] == 0 and result["halted"]
    executor.execute.assert_not_called()
    assert alerts.send_warning_alert.called


def test_risk_guard_rejection_recorded():
    """리스크 가드 거부 주문은 실행되지 않고 rejected에 기록"""
    # KRW 하한: 매수 후 KRW가 총자산 10% 미만이면 거부
    holdings = {"BTC": 20_000_000, "ETH": 12_000_000, "XRP": 4_000_000, "SOL": 4_000_000}
    sys_, executor, _ = make_system(holdings=holdings, krw=60_000_000)
    # min_krw_ratio를 극단으로 올려 전부 거부되게 함
    limits = sys_.config.limits.__class__(
        max_single_trade_krw=10_000_000, max_daily_volume_krw=50_000_000,
        min_krw_ratio=0.99, fomo_surge_threshold=0.15,
    )
    from src.risk.guard import RiskGuard
    sys_.guard = RiskGuard(limits)
    result = sys_.run_daily_check(dry_run=False)
    assert result["executed"] == 0
    assert result["rejected"]


def test_config_from_loader_parses_yaml_values():
    """config_from_loader가 YAML 값을 SystemConfig로 올바르게 매핑"""
    values = {
        "strategy.targets.weights": {"BTC": 0.6, "ETH": 0.4},
        "strategy.targets.crypto": 0.7,
        "strategy.rebalance.band_pp": 0.03,
        "strategy.rebalance.relative_band": 0.15,
        "strategy.rebalance.min_trade_krw": 20_000,
        "strategy.dca.base_amount_krw": 2_000_000,
        "strategy.dca.max_single_dca_krw": 8_000_000,
        "strategy.dca.krw_usage_cap": 0.30,
        "risk.max_single_trade_krw": 15_000_000,
        "risk.max_daily_volume_krw": 60_000_000,
        "risk.min_krw_ratio": 0.05,
        "risk.fomo_surge_threshold": 0.20,
    }
    loader = MagicMock()
    loader.get.side_effect = lambda key, default=None: values.get(key, default)
    config = KairosSimple.config_from_loader(loader)
    assert config.rebalance.crypto_target == 0.7
    assert config.rebalance.band_pp == 0.03
    assert config.dca.base_amount_krw == 2_000_000
    assert config.dca.crypto_weights == {"BTC": 0.6, "ETH": 0.4}
    assert config.limits.max_single_trade_krw == 15_000_000


def test_config_from_loader_defaults():
    """설정 키가 없으면 안전한 기본값 사용"""
    loader = MagicMock()
    loader.get.side_effect = lambda key, default=None: default
    config = KairosSimple.config_from_loader(loader)
    assert config.rebalance.crypto_target == 0.60
    assert config.limits.min_krw_ratio == 0.10


def test_record_trade_failure_does_not_abort_remaining_orders():
    """운영 회귀 방지: 주문 체결 후 DB 기록 실패가 나머지 주문 실행을
    중단시키면 안 된다 (돈은 이미 움직였으므로 기록 실패는 경고로 강등)."""
    holdings = {"BTC": 50_000_000, "ETH": 12_000_000, "XRP": 4_000_000, "SOL": 4_000_000}
    sys_, executor, alerts = make_system(holdings=holdings, krw=30_000_000)
    sys_.portfolio.record_trade.side_effect = Exception("table trade_history has no column named currency")
    result = sys_.run_daily_check(dry_run=False)
    # 리밸런싱 주문이 여러 건인데, 첫 기록 실패에도 전부 실행 시도되어야 함
    assert executor.execute.call_count >= 2
    assert result["executed"] >= 2
    assert alerts.send_error_alert.called  # 기록 실패는 알림으로 통지
