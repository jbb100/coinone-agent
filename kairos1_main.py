#!/usr/bin/env python3
"""KAIROS-Simple: 장기 역발상 매집형 자동 트레이딩.

철학: 싸질수록 사고, 비싸질수록 판다. 모든 사이클이 하나의 (틸트된)
목표 비중을 공유해 서로 반대 매매를 하지 않는다.
  - 역발상 틸트: Mayer ratio로 목표 비중을 연속 조절 (구간 선형 보간,
    바닥권 +10%p ~ 과열 -20%p) — 역발상 레버를 자산배분에 직접
  - 주간 DCA: Fear&Greed × 200주MA 승수 (공포·바닥권에 많이, 탐욕·과열에
    적게). 단, 매수 후 비중이 목표를 넘지 않도록 상한 — 목표 도달 시
    현금 보존 (리밸런서가 되팔 물량을 사지 않는다)
  - 일일 밴드 체크: 목표 ±5%p 이탈 시에만 리밸런싱 — 상승 초과분 자동
    익절, 하락 미달분 자동 매집
  - fail-loud: 데이터 이상 시 하드코딩 폴백 없이 거래 중단 + 알림

역할 위계: Mayer(장주기 밸류에이션)가 자산배분 목표를 정하고, F&G(단기
심리)는 목표 아래에서 신규 현금의 투입 속도만 조절한다.

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
from src.strategy.valuation import contrarian_crypto_target, dca_multiplier


@dataclass(frozen=True)
class SystemConfig:
    dca: DCAConfig
    rebalance: RebalanceConfig
    limits: RiskLimits
    # 역발상 틸트: Mayer 밴드에 따라 목표 비중을 ±10~20%p 조절
    # (바닥권 +10%p, 과열 -20%p). False면 고정 목표.
    contrarian_tilt: bool = True


class KairosSimple:
    def __init__(self, market_data, portfolio, executor, alerts, risk_guard, config):
        self.market = market_data
        self.portfolio = portfolio
        self.executor = executor
        self.alerts = alerts
        self.guard = risk_guard
        self.config = config
        # 일일 거래량 한도는 프로세스 간 공유 — weekly-dca(09:00)와
        # daily-check(09:10)가 별도 프로세스라 0에서 시작하면 한도가 2배가 됨
        self._daily_traded_krw = float(portfolio.get_traded_krw_today())

    # ------------------------------------------------------------------ 조립
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
    def config_from_loader(cls, loader) -> SystemConfig:
        """ConfigLoader → SystemConfig 변환."""
        weights = {
            str(k): float(v)
            for k, v in loader.get(
                "strategy.targets.weights",
                {"BTC": 0.5, "ETH": 0.3, "XRP": 0.1, "SOL": 0.1},
            ).items()
        }
        return SystemConfig(
            dca=DCAConfig(
                base_amount_krw=float(loader.get("strategy.dca.base_amount_krw", 1_000_000)),
                crypto_weights=weights,
                max_single_dca_krw=float(loader.get("strategy.dca.max_single_dca_krw", 5_000_000)),
                krw_usage_cap=float(loader.get("strategy.dca.krw_usage_cap", 0.25)),
                min_order_krw=float(loader.get("strategy.rebalance.min_trade_krw", 10_000)),
            ),
            rebalance=RebalanceConfig(
                crypto_target=float(loader.get("strategy.targets.crypto", 0.60)),
                band_pp=float(loader.get("strategy.rebalance.band_pp", 0.05)),
                crypto_weights=weights,
                relative_band=float(loader.get("strategy.rebalance.relative_band", 0.20)),
                min_trade_krw=float(loader.get("strategy.rebalance.min_trade_krw", 10_000)),
            ),
            limits=RiskLimits(
                max_single_trade_krw=float(loader.get("risk.max_single_trade_krw", 10_000_000)),
                max_daily_volume_krw=float(loader.get("risk.max_daily_volume_krw", 50_000_000)),
                min_krw_ratio=float(loader.get("risk.min_krw_ratio", 0.10)),
                fomo_surge_threshold=float(loader.get("risk.fomo_surge_threshold", 0.15)),
            ),
            contrarian_tilt=str(
                loader.get("strategy.targets.contrarian_tilt", True)
            ).lower() in ("true", "1", "yes"),
        )

    @classmethod
    def from_yaml(cls, path: str = "config/config.yaml") -> "KairosSimple":
        """실운영 조립: config 로딩 → 실제 클라이언트 생성."""
        from src.data.market_data import MarketDataService
        from src.execution.executor import OrderExecutor
        from src.monitoring.alert_system import AlertSystem
        from src.portfolio.portfolio import PortfolioService
        from src.trading.coinone_client import CoinoneClient
        from src.trading.rate_limited_client import create_rate_limited_client
        from src.utils.binance_data_provider import BinanceDataProvider
        from src.utils.config_loader import ConfigLoader
        from src.utils.database_manager import DatabaseManager
        from src.utils.external_api_client import ExternalAPIClient

        loader = ConfigLoader(path)
        config = cls.config_from_loader(loader)

        sandbox_raw = str(loader.get("api.coinone.sandbox", "true")).lower()
        coinone = create_rate_limited_client(CoinoneClient(
            api_key=loader.get("api.coinone.api_key"),
            secret_key=loader.get("api.coinone.secret_key"),
            sandbox=sandbox_raw in ("true", "1", "yes"),
        ))
        binance = BinanceDataProvider()
        external = ExternalAPIClient()
        db = DatabaseManager(loader)
        alerts = AlertSystem(loader)

        market = MarketDataService(binance, external, coinone)
        portfolio = PortfolioService(
            coinone, market, db, assets=list(config.rebalance.crypto_weights.keys())
        )
        executor = OrderExecutor(
            coinone,
            twap_slice_krw=float(loader.get("execution.twap_slice_krw", 5_000_000)),
            max_retries=int(loader.get("execution.max_retries", 3)),
        )
        system = cls.from_components(market, portfolio, executor, alerts, config)
        system.binance = binance  # report 커맨드용
        return system

    # ------------------------------------------------------------ 실행 사이클
    def _tilted_target(self, mayer: float) -> float:
        """모든 사이클이 공유하는 단일 목표 비중 — DCA와 리밸런서가 같은
        목표를 보므로 한쪽이 사고 다른 쪽이 되파는 충돌이 없다."""
        base = self.config.rebalance.crypto_target
        return contrarian_crypto_target(mayer, base) if self.config.contrarian_tilt else base

    def run_weekly_dca(self, dry_run: bool = False) -> Dict:
        """주간 DCA: 공포·저평가일수록 많이 매수.

        단, 매수 후 크립토 비중이 (틸트된) 목표를 넘지 않도록 상한 —
        목표 도달 시 현금을 보존해 다음 하락 매집 재원으로 남긴다."""
        try:
            valuation = self.market.get_valuation()
            snap = self.portfolio.get_snapshot()
        except (DataUnavailableError, InsufficientDataError) as e:
            return self._halt("주간 DCA", e)
        mult = dca_multiplier(valuation)
        target = self._tilted_target(valuation.mayer_ratio)
        orders = plan_weekly_dca(
            self.config.dca, mult, snap.krw_balance,
            crypto_value_krw=snap.crypto_value_krw, target_crypto_ratio=target,
        )
        logger.info(
            f"DCA 승수 {mult:.2f} (F&G={valuation.fear_greed}, "
            f"Mayer={valuation.mayer_ratio:.2f}) | 크립토 {snap.crypto_ratio:.1%}"
            f"/목표 {target:.1%} → 주문 {len(orders)}건"
        )
        if not orders and snap.crypto_ratio >= target:
            logger.info("목표 비중 도달 — 이번 주 DCA 현금 보존")
        requests = [OrderRequest(o.asset, "buy", o.amount_krw, "dca") for o in orders]
        return self._execute_all("주간 DCA", requests, snap, dry_run)

    def run_daily_check(self, dry_run: bool = False) -> Dict:
        """일일 밴드 체크: 이탈 시에만 목표 비중으로 복귀.

        역발상 틸트가 켜져 있으면 Mayer ratio로 목표 비중을 연속 조절한다
        (바닥권일수록 높게, 과열일수록 낮게)."""
        import dataclasses

        try:
            reb_cfg = self.config.rebalance
            if self.config.contrarian_tilt:
                mayer = self.market.get_mayer_ratio()
                target = self._tilted_target(mayer)
                if target != reb_cfg.crypto_target:
                    logger.info(
                        f"역발상 틸트: Mayer={mayer:.2f} → 목표 "
                        f"{reb_cfg.crypto_target:.0%} → {target:.1%}"
                    )
                reb_cfg = dataclasses.replace(reb_cfg, crypto_target=target)
            snap = self.portfolio.get_snapshot()
            orders = plan_rebalance(reb_cfg, snap.holdings_krw, snap.krw_balance)
            if not orders:
                logger.info(f"밴드 내 (크립토 {snap.crypto_ratio:.1%}) — 거래 없음")
                return {"executed": 0, "rejected": [], "halted": False,
                        "note": "밴드 내 — 거래 없음"}
            changes = self.market.get_price_change_24h([o.asset for o in orders])
        except (DataUnavailableError, InsufficientDataError) as e:
            return self._halt("일일 밴드 체크", e)
        requests = [
            OrderRequest(o.asset, o.side, o.amount_krw, "rebalance") for o in orders
        ]
        return self._execute_all("밴드 리밸런싱", requests, snap, dry_run,
                                 price_changes=changes)

    def run_monthly_report(self) -> Dict:
        from src.report.reporter import Reporter

        snap = self.portfolio.get_snapshot()
        reporter = Reporter(self.binance, self.alerts)
        # 포트폴리오 수익률은 DB 기반 산출이 붙기 전까지 벤치마크 비교만 제공
        benchmark = reporter.btc_benchmark_return(days=30)
        report = {
            "total_value_krw": snap.total_value_krw,
            "crypto_ratio": snap.crypto_ratio,
            "btc_benchmark_return_30d": benchmark,
        }
        self.alerts.send_info_alert(
            "월간 리포트",
            f"총자산 {snap.total_value_krw:,.0f} KRW | 크립토 {snap.crypto_ratio:.0%} "
            f"| BTC 30일 {benchmark:+.1%}",
        )
        return report

    def get_status(self) -> Dict:
        snap = self.portfolio.get_snapshot()
        return {
            "total_value_krw": snap.total_value_krw,
            "krw_balance": snap.krw_balance,
            "holdings_krw": snap.holdings_krw,
            "crypto_ratio": snap.crypto_ratio,
            "target_ratio": self.config.rebalance.crypto_target,
            "band_pp": self.config.rebalance.band_pp,
        }

    # ---------------------------------------------------------------- 내부
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
                logger.info(
                    f"[DRY-RUN] {req.side} {req.asset} {req.amount_krw:,.0f} KRW"
                )
                continue
            report = self.executor.execute(req)
            if report.success:
                executed += 1
                self._daily_traded_krw += req.amount_krw
                # 주문은 이미 체결됨 — 기록 실패가 나머지 주문 실행을 막으면 안 됨
                try:
                    self.portfolio.record_trade(
                        req.asset, req.side, req.amount_krw, origin=req.origin
                    )
                except Exception as e:
                    logger.error(f"거래 기록 실패 (주문은 체결됨): {req.asset} — {e}")
                    self.alerts.send_error_alert(
                        "거래 기록 실패",
                        f"{req.side} {req.asset} {req.amount_krw:,.0f} KRW 주문은 "
                        f"체결됐으나 DB 기록 실패: {e}",
                    )
            else:
                rejected.append((req.asset, f"실행 실패: {report.error}"))
        result = {"executed": executed, "rejected": rejected, "halted": False}
        logger.info(f"{label} 완료: 실행 {executed}건, 거부 {len(rejected)}건")
        return result

    def _halt(self, label: str, error: Exception) -> Dict:
        logger.error(f"{label} 중단: {error}")
        self.alerts.send_warning_alert(f"{label} 중단", f"데이터 이상: {error}")
        return {"executed": 0, "rejected": [], "halted": True, "error": str(error)}


def main() -> int:
    parser = argparse.ArgumentParser(description="KAIROS-Simple 장기 역발상 매집")
    parser.add_argument(
        "command", choices=["weekly-dca", "daily-check", "report", "status"]
    )
    parser.add_argument("--dry-run", action="store_true", help="주문 없이 시뮬레이션")
    parser.add_argument("--config", default="config/config.yaml")
    args = parser.parse_args()

    system = KairosSimple.from_yaml(args.config)
    if args.command == "weekly-dca":
        result = system.run_weekly_dca(dry_run=args.dry_run)
    elif args.command == "daily-check":
        result = system.run_daily_check(dry_run=args.dry_run)
    elif args.command == "report":
        result = system.run_monthly_report()
    else:
        result = system.get_status()
    print(result)
    return 1 if result.get("halted") else 0


if __name__ == "__main__":
    sys.exit(main())
