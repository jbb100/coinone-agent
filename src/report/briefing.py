"""데일리 브리핑 — 매일 무조건 발송하는 잔고 현황 + 생존 신호.

무거래 날 Slack이 조용하면 '조용한 시장'과 '죽은 시스템'을 구분할 수 없다.
브리핑은 거래 여부와 무관하게 매일 도착해야 한다.
"""
from typing import Optional, Tuple

from src.portfolio.portfolio import PortfolioSnapshot


def compose_briefing(
    snap: PortfolioSnapshot,
    target_ratio: float,
    band_pp: float,
    market_line: str,
    prev_total_krw: Optional[float],
    traded_today_krw: float,
) -> Tuple[str, str]:
    """브리핑 (제목, 본문) 구성 — 순수 함수, 외부 호출 없음."""
    total = snap.total_value_krw
    if prev_total_krw:
        change = f"전일 {total / prev_total_krw - 1.0:+.1%}"
    else:
        change = "전일 대비 — 데이터 축적 중"

    deviation = snap.crypto_ratio - target_ratio
    if abs(deviation) > band_pp:
        band = f"밴드 이탈 {deviation:+.1%}p → 리밸런싱 예정"
    else:
        band = f"밴드 내 (±{band_pp:.1%}p)"

    holdings = " | ".join(
        f"{asset} {value:,.0f}" for asset, value in snap.holdings_krw.items()
    )
    body = "\n".join([
        f"총자산 {total:,.0f} KRW ({change})",
        f"크립토 {snap.crypto_ratio:.1%} / 목표 {target_ratio:.1%} — {band}",
        holdings,
        f"KRW 잔고 {snap.krw_balance:,.0f}",
        f"시장: {market_line}",
        f"오늘 거래 {traded_today_krw:,.0f} KRW",
    ])
    return "데일리 브리핑", body
