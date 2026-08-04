"""포트폴리오 스냅샷(KRW 평가)과 거래 기록."""
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from src.report.performance import DailyPoint, compute_twr


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
        balances = self.coinone.get_balances()  # 키: 대문자 통화 코드
        prices = self.market.get_prices_krw(self.assets)
        holdings = {
            asset: float(balances.get(asset.upper(), 0.0)) * prices[asset]
            for asset in self.assets
        }
        return PortfolioSnapshot(
            holdings_krw=holdings,
            krw_balance=float(balances.get("KRW", 0.0)),
            taken_at=datetime.now(),
        )

    def get_traded_krw_today(self) -> float:
        """오늘 체결된 거래액 합계 — 프로세스 간 일일 거래량 한도 공유용."""
        return float(self.db.get_traded_krw_today())

    def record_snapshot(self, snap: PortfolioSnapshot) -> None:
        """일일 스냅샷 기록 — 월간 수익률 산출의 데이터 원천."""
        self.db.save_portfolio_snapshot({
            "total_value_krw": snap.total_value_krw,
            "assets": {
                **{asset: {"balance": 0.0, "value_krw": value}
                   for asset, value in snap.holdings_krw.items()},
                "KRW": snap.krw_balance,
            },
        })

    def get_value_change_30d(self, current_total_krw: float):
        """최근 30일 총자산 변화율 (입출금 포함 단순 변화).

        (변화율, 관측 창 일수) 튜플을 반환 — 5일치 데이터로 계산한 수익률을
        30일 벤치마크와 비교하는 사과-오렌지 비교를 막으려면 호출부가
        실제 창을 알아야 한다. 오늘 이전 스냅샷이 없으면 None — 당일
        스냅샷을 기준선으로 잡으면 수익률이 항상 ≈0%가 된다.
        """
        today = datetime.now().strftime("%Y-%m-%d")
        baseline = next(
            ((float(row["total_value_krw"]), str(row["snapshot_date"])[:10])
             for row in self.db.get_portfolio_history(30)
             if float(row.get("total_value_krw") or 0) > 0
             and str(row.get("snapshot_date", ""))[:10] < today),
            None,
        )
        if baseline is None:
            return None
        value, date_str = baseline
        window_days = (
            datetime.now() - datetime.strptime(date_str, "%Y-%m-%d")
        ).days
        return current_total_krw / value - 1.0, max(window_days, 1)

    def get_twr(self, days: int = 30) -> Optional[Tuple[float, int]]:
        """시간가중수익률 (TWR, 관측 창 일수) — 입출금을 수익에서 분리.

        스냅샷 이력 + 일별 거래 합계로 외부 KRW 흐름을 역산한다.
        유효 스냅샷 2개 미만이면 None. 코인 외부 이체는 구분 불가
        (performance.py 참고).
        """
        points: Dict[str, DailyPoint] = {}
        for row in self.db.get_portfolio_history(days):
            date = str(row.get("snapshot_date", ""))[:10]
            total = float(row.get("total_value_krw") or 0)
            if not date or total <= 0:
                continue
            try:
                detail = json.loads(row.get("portfolio_detail") or "{}")
                krw = float(detail.get("assets", {}).get("KRW", 0.0))
            except (ValueError, TypeError):
                krw = 0.0
            # 같은 날 여러 스냅샷이면 마지막 것으로 덮어쓴다
            points[date] = DailyPoint(
                date=date, total_value_krw=total, krw_balance=krw
            )
        trades = {
            str(row["date"]): (
                float(row.get("buys_krw") or 0), float(row.get("sells_krw") or 0)
            )
            for row in self.db.get_daily_trade_sums(days)
        }
        ordered = [points[d] for d in sorted(points)]
        return compute_twr(ordered, trades)

    def get_previous_total_krw(self):
        """오늘 이전 가장 최근 스냅샷의 총자산 — 데일리 브리핑 전일 대비용.

        이력이 없으면 None — 데이터 없이 변화율을 주장하지 않는다.
        """
        today = datetime.now().strftime("%Y-%m-%d")
        totals = [
            float(row["total_value_krw"])
            for row in self.db.get_portfolio_history(7)
            if float(row.get("total_value_krw") or 0) > 0
            and str(row.get("snapshot_date", ""))[:10] < today
        ]
        return totals[-1] if totals else None

    def record_trade(self, asset: str, side: str, amount_krw: float, origin: str) -> None:
        self.db.save_trade({
            "asset": asset,
            "side": side,
            "amount_krw": amount_krw,
            "origin": origin,           # "dca" | "rebalance"
            "trade_date": datetime.now(),
        })
