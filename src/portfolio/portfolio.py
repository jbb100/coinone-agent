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

    def record_trade(self, asset: str, side: str, amount_krw: float, origin: str) -> None:
        self.db.save_trade({
            "asset": asset,
            "side": side,
            "amount_krw": amount_krw,
            "origin": origin,           # "dca" | "rebalance"
            "trade_date": datetime.now(),
        })
