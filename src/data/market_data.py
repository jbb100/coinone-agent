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

        mayer = self.get_mayer_ratio()
        valuation = MarketValuation(fear_greed=int(fg), mayer_ratio=mayer)
        logger.info(f"밸류에이션: F&G={fg}, Mayer={valuation.mayer_ratio:.2f}")
        return valuation

    def get_mayer_ratio(self) -> float:
        """현재가/200주MA — F&G 없이 조회 가능 (일일 틸트용)."""
        klines = self.binance.get_historical_klines(
            symbol="BTCUSDT", interval="1w", limit=300
        )
        if klines is None or klines.empty or "Close" not in klines.columns:
            raise DataUnavailableError("Binance 주봉 조회 실패 — 이번 사이클 거래 중단")

        ma = ma_200w(klines["Close"])          # 부족/NaN 시 InsufficientDataError
        return float(klines["Close"].iloc[-1]) / ma

    def get_relative_returns(
        self, assets: List[str], anchor: str = "BTC", weeks: int = 26
    ) -> Dict[str, float]:
        """앵커(BTC) 대비 26주 상대수익 — 상대강도 편출 입력.

        rel = (자산 26주 수익배수 / 앵커 26주 수익배수) - 1
        """
        def growth(symbol: str) -> float:
            klines = self.binance.get_historical_klines(
                symbol=f"{symbol}USDT", interval="1w", limit=weeks + 1
            )
            if klines is None or len(klines) < weeks + 1 or "Close" not in klines:
                raise DataUnavailableError(
                    f"{symbol} 주봉 {weeks + 1}개 조회 실패 — 이번 사이클 거래 중단"
                )
            first = float(klines["Close"].iloc[-(weeks + 1)])
            last = float(klines["Close"].iloc[-1])
            if first <= 0:
                raise DataUnavailableError(f"{symbol} 주봉 가격 이상: {first}")
            return last / first

        anchor_growth = growth(anchor)
        return {asset: growth(asset) / anchor_growth - 1.0 for asset in assets}

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
