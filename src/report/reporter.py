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
        self, portfolio_return: float, total_value_krw: float,
        crypto_ratio: float, window_days: int = 30,
    ) -> Dict:
        """window_days: 포트폴리오 수익률의 실제 관측 창 — 벤치마크도 같은
        창으로 계산해야 초과수익 비교가 성립한다 (배포 초기 5일치 수익률을
        30일 BTC와 비교하는 오류 방지)."""
        benchmark = self.btc_benchmark_return(days=window_days)
        report = {
            "portfolio_return": portfolio_return,
            "btc_benchmark_return": benchmark,
            "excess_return": portfolio_return - benchmark,
            "total_value_krw": total_value_krw,
            "crypto_ratio": crypto_ratio,
            "window_days": window_days,
        }
        self.alerts.send_info_alert(
            "월간 성과 리포트",
            f"수익률({window_days}일) {portfolio_return:+.1%} / "
            f"BTC {benchmark:+.1%} "
            f"(초과 {report['excess_return']:+.1%}) | "
            f"총자산 {total_value_krw:,.0f} KRW | 크립토 {crypto_ratio:.0%}",
        )
        return report
