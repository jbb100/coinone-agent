"""데일리 브리핑 메시지 구성 테스트 — 매일 발송되는 생존 신호 + 잔고 현황."""
from datetime import datetime

import pytest

from src.portfolio.portfolio import PortfolioSnapshot
from src.report.briefing import compose_briefing


def make_snapshot(holdings=None, krw=40_000_000):
    holdings = holdings or {
        "BTC": 30_000_000, "ETH": 18_000_000, "XRP": 6_000_000, "SOL": 6_000_000
    }
    return PortfolioSnapshot(
        holdings_krw=holdings, krw_balance=krw, taken_at=datetime.now()
    )


def test_briefing_includes_total_and_daily_change():
    """총자산과 전일 대비 변화율이 본문에 있어야 함"""
    snap = make_snapshot()  # 총자산 100M
    _, body = compose_briefing(
        snap, target_ratio=0.60, band_pp=0.05, market_line="Mayer 1.50 | F&G 50",
        prev_total_krw=98_000_000, traded_today_krw=0.0,
    )
    assert "100,000,000" in body
    assert "+2.0%" in body


def test_briefing_without_history_notes_accumulating():
    """전일 스냅샷이 없으면 수익률을 주장하지 않고 축적 중임을 알림"""
    _, body = compose_briefing(
        make_snapshot(), target_ratio=0.60, band_pp=0.05,
        market_line="Mayer 1.50 | F&G 50",
        prev_total_krw=None, traded_today_krw=0.0,
    )
    assert "축적" in body
    assert "%" not in body.split("\n")[0] or "+" not in body.split("\n")[0]


def test_briefing_shows_ratio_vs_target_within_band():
    """크립토 비중 vs 목표 + 밴드 내 상태 표시"""
    _, body = compose_briefing(
        make_snapshot(), target_ratio=0.60, band_pp=0.05,
        market_line="Mayer 1.50 | F&G 50",
        prev_total_krw=None, traded_today_krw=0.0,
    )
    assert "60.0%" in body and "목표" in body
    assert "밴드 내" in body


def test_briefing_flags_band_breach():
    """밴드 이탈 시 다음 리밸런싱 예고가 보여야 함"""
    holdings = {
        "BTC": 40_000_000, "ETH": 24_000_000, "XRP": 8_000_000, "SOL": 8_000_000
    }
    _, body = compose_briefing(
        make_snapshot(holdings=holdings, krw=20_000_000),  # 크립토 80%
        target_ratio=0.60, band_pp=0.05, market_line="Mayer 1.50 | F&G 50",
        prev_total_krw=None, traded_today_krw=0.0,
    )
    assert "밴드 이탈" in body


def test_briefing_lists_each_asset_and_krw():
    _, body = compose_briefing(
        make_snapshot(), target_ratio=0.60, band_pp=0.05,
        market_line="Mayer 1.50 | F&G 50",
        prev_total_krw=None, traded_today_krw=0.0,
    )
    for asset in ("BTC", "ETH", "XRP", "SOL"):
        assert asset in body
    assert "40,000,000" in body  # KRW 잔고


def test_briefing_includes_market_line_and_traded_amount():
    _, body = compose_briefing(
        make_snapshot(), target_ratio=0.65, band_pp=0.05,
        market_line="Mayer 0.90 | F&G 20",
        prev_total_krw=None, traded_today_krw=1_500_000.0,
    )
    assert "Mayer 0.90" in body and "F&G 20" in body
    assert "1,500,000" in body


def test_briefing_negative_daily_change():
    snap = make_snapshot()  # 100M
    _, body = compose_briefing(
        snap, target_ratio=0.60, band_pp=0.05, market_line="Mayer 1.50 | F&G 50",
        prev_total_krw=104_000_000, traded_today_krw=0.0,
    )
    assert "-3.8%" in body


def test_briefing_warns_when_exchange_exposure_exceeds_cap():
    """거래소 총평가액이 콜드월렛 기준을 넘으면 초과분 이전 검토 경고"""
    snap = make_snapshot()  # 총자산 100M (전부 거래소)
    _, body = compose_briefing(
        snap, target_ratio=0.60, band_pp=0.05, market_line="-",
        prev_total_krw=None, traded_today_krw=0.0,
        exchange_exposure_cap_krw=80_000_000,
    )
    assert "콜드월렛" in body
    assert "20,000,000" in body  # 초과분


def test_briefing_silent_when_exposure_under_cap():
    snap = make_snapshot()
    _, body = compose_briefing(
        snap, target_ratio=0.60, band_pp=0.05, market_line="-",
        prev_total_krw=None, traded_today_krw=0.0,
        exchange_exposure_cap_krw=200_000_000,
    )
    assert "콜드월렛" not in body


def test_briefing_no_exposure_check_when_cap_unset():
    """기준 미설정(None/0) 시 경고 없음 — 기능 옵트인"""
    snap = make_snapshot()
    _, body = compose_briefing(
        snap, target_ratio=0.60, band_pp=0.05, market_line="-",
        prev_total_krw=None, traded_today_krw=0.0,
    )
    assert "콜드월렛" not in body
