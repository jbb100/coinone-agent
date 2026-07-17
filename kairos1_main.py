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
    익절, 하락 미달분 자동 매집. 24h -10% 급락 자산은 분할 진입(크래시 가드)
  - 상대강도 편출: 26주 BTC 대비 열위 알트의 목표 가중치를 연속 감축
    (-30%까지 유지, -50%에서 0), 감축분은 BTC로
  - fail-loud: 데이터 이상 시 하드코딩 폴백 없이 거래 중단 + 알림

역할 위계: Mayer(장주기 밸류에이션)가 자산배분 목표를 정하고, F&G(단기
심리)는 목표 아래에서 신규 현금의 투입 속도만 조절한다.

파이프라인: market_data → strategy(순수 함수) → risk_guard → executor → record/alert
CLI: python kairos1_main.py {weekly-dca|daily-check|briefing|report|status} [--dry-run]
"""
import argparse
import sys
from dataclasses import dataclass
from typing import Dict

from loguru import logger

from src.core.exceptions import DataUnavailableError, InsufficientDataError
from src.risk.guard import OrderRequest, PortfolioContext, RiskGuard, RiskLimits
from src.strategy.dca import DCAConfig, plan_weekly_dca
from src.strategy.rebalance import RebalanceConfig, apply_crash_guard, plan_rebalance
from src.strategy.valuation import (
    apply_relative_strength,
    contrarian_crypto_target,
    dca_multiplier,
)


@dataclass(frozen=True)
class SystemConfig:
    dca: DCAConfig
    rebalance: RebalanceConfig
    limits: RiskLimits
    # 역발상 틸트: Mayer 밴드에 따라 목표 비중을 ±10~20%p 조절
    # (바닥권 +10%p, 과열 -20%p). False면 고정 목표.
    contrarian_tilt: bool = True
    # 상대강도 편출: 26주 BTC 대비 열위 알트의 목표 가중치를 연속 감축,
    # 감축분은 BTC로. False면 고정 가중치.
    relative_demotion: bool = True


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
                crash_threshold=float(
                    loader.get("strategy.rebalance.crash_threshold_24h", -0.10)
                ),
                crash_buy_fraction=float(
                    loader.get("strategy.rebalance.crash_buy_fraction", 0.5)
                ),
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
            relative_demotion=str(
                loader.get("strategy.targets.relative_demotion", True)
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
            timeout=float(loader.get("api.coinone.timeout", 30)),
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
            fill_timeout=float(loader.get("execution.fill_timeout_sec", 45)),
            poll_interval=float(loader.get("execution.poll_interval_sec", 3)),
            slippage_cap=float(loader.get("execution.slippage_cap", 0.005)),
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

    def _effective_weights(self, notes=None) -> Dict[str, float]:
        """모든 사이클이 공유하는 단일 자산 가중치 — 상대강도 편출 반영.

        26주 BTC 대비 열위 알트의 가중치를 연속 감축(감축분은 BTC로).
        DCA와 리밸런서가 같은 가중치를 봐야 충돌이 없다."""
        weights = self.config.rebalance.crypto_weights
        alts = [a for a in weights if a != "BTC"]
        if not self.config.relative_demotion or not alts:
            return weights
        rel = self.market.get_relative_returns(alts)
        effective = apply_relative_strength(weights, rel)
        demoted = {a: w for a, w in effective.items()
                   if abs(w - weights[a]) > 1e-9}
        if demoted:
            msg = "상대강도 편출: " + ", ".join(
                f"{a} {weights[a]:.0%}→{w:.1%}" for a, w in sorted(demoted.items())
            )
            logger.info(msg)
            if notes is not None:
                notes.append(msg)
        return effective

    def run_weekly_dca(self, dry_run: bool = False) -> Dict:
        return self._guarded("주간 DCA", lambda: self._weekly_dca(dry_run))

    def run_daily_check(self, dry_run: bool = False) -> Dict:
        return self._guarded("일일 밴드 체크", lambda: self._daily_check(dry_run))

    def _weekly_dca(self, dry_run: bool) -> Dict:
        """주간 DCA: 공포·저평가일수록 많이 매수.

        단, 매수 후 크립토 비중이 (틸트된) 목표를 넘지 않도록 상한 —
        목표 도달 시 현금을 보존해 다음 하락 매집 재원으로 남긴다."""
        import dataclasses

        valuation = self.market.get_valuation()
        weights = self._effective_weights()
        snap = self.portfolio.get_snapshot()
        mult = dca_multiplier(valuation)
        target = self._tilted_target(valuation.mayer_ratio)
        dca_cfg = dataclasses.replace(self.config.dca, crypto_weights=weights)
        orders = plan_weekly_dca(
            dca_cfg, mult, snap.krw_balance,
            crypto_value_krw=snap.crypto_value_krw, target_crypto_ratio=target,
        )
        notes = [
            f"승수 {mult:.2f} (F&G={valuation.fear_greed}, "
            f"Mayer={valuation.mayer_ratio:.2f}) | "
            f"크립토 {snap.crypto_ratio:.1%} → 목표 {target:.1%}"
        ]
        logger.info(f"{notes[0]} → 주문 {len(orders)}건")
        if not orders and snap.crypto_ratio >= target:
            logger.info("목표 비중 도달 — 이번 주 DCA 현금 보존")
        requests = [OrderRequest(o.asset, "buy", o.amount_krw, "dca") for o in orders]
        result = self._execute_all("주간 DCA", requests, snap, dry_run, notes=notes)
        if not dry_run and result["executed"] == 0 and not result["rejected"]:
            # 주간 하트비트 — 무거래 주에도 최소 주 1회 알림이 가야
            # '조용한 시장'과 '죽은 크론'을 구분할 수 있다
            self.alerts.send_info_alert(
                "주간 상태 (하트비트)",
                f"크립토 {snap.crypto_ratio:.1%}/목표 {target:.1%} | "
                f"총자산 {snap.total_value_krw:,.0f} KRW | "
                f"매수 없음 — 목표 도달, 현금 보존",
            )
        return result

    def _daily_check(self, dry_run: bool) -> Dict:
        """일일 밴드 체크: 이탈 시에만 목표 비중으로 복귀.

        역발상 틸트가 켜져 있으면 Mayer ratio로 목표 비중을 연속 조절한다
        (바닥권일수록 높게, 과열일수록 낮게)."""
        import dataclasses

        notes = []
        reb_cfg = self.config.rebalance
        if self.config.contrarian_tilt:
            mayer = self.market.get_mayer_ratio()
            target = self._tilted_target(mayer)
            if target != reb_cfg.crypto_target:
                msg = (f"역발상 틸트: Mayer={mayer:.2f} → 목표 "
                       f"{reb_cfg.crypto_target:.0%} → {target:.1%}")
                logger.info(msg)
                notes.append(msg)
            reb_cfg = dataclasses.replace(reb_cfg, crypto_target=target)
        reb_cfg = dataclasses.replace(
            reb_cfg, crypto_weights=self._effective_weights(notes)
        )
        snap = self.portfolio.get_snapshot()
        if not dry_run:
            # dry-run이 스냅샷을 남기면 전일 대비·30일 수익률 기준선 오염
            try:
                # 월간 수익률 데이터 축적 — 기록 실패가 거래를 막으면 안 됨
                self.portfolio.record_snapshot(snap)
            except Exception as e:
                logger.error(f"스냅샷 기록 실패 (체크는 계속): {e}")
        orders = plan_rebalance(reb_cfg, snap.holdings_krw, snap.krw_balance)
        if not orders:
            logger.info(f"밴드 내 (크립토 {snap.crypto_ratio:.1%}) — 거래 없음")
            return {"executed": 0, "rejected": [], "halted": False,
                    "note": "밴드 내 — 거래 없음"}
        notes.insert(0, f"크립토 {snap.crypto_ratio:.1%} → 목표 "
                        f"{reb_cfg.crypto_target:.1%} 복귀")
        changes = self.market.get_price_change_24h([o.asset for o in orders])
        guarded = apply_crash_guard(
            orders, changes,
            threshold=reb_cfg.crash_threshold,
            buy_fraction=reb_cfg.crash_buy_fraction,
            min_trade_krw=reb_cfg.min_trade_krw,
        )
        if guarded != orders:
            msg = "크래시 가드: 급락 자산 매수 분할 진입"
            logger.info(msg)
            notes.append(msg)
        orders = guarded
        requests = [
            OrderRequest(o.asset, o.side, o.amount_krw, "rebalance") for o in orders
        ]
        return self._execute_all("밴드 리밸런싱", requests, snap, dry_run,
                                 price_changes=changes, notes=notes)

    def run_daily_briefing(self) -> Dict:
        return self._guarded("데일리 브리핑", self._daily_briefing)

    def _daily_briefing(self) -> Dict:
        """데일리 브리핑: 무거래 날에도 매일 발송되는 잔고 현황 + 생존 신호.

        핵심은 잔고와 '살아있음' — 시장 데이터 실패로 브리핑 자체가 죽으면
        안 되므로 시장 라인만 실패 표기로 강등한다. 잔고 조회 실패는
        _guarded가 에러 알림으로 통지 (어느 쪽이든 매일 무언가는 도착)."""
        from src.report.briefing import compose_briefing

        snap = self.portfolio.get_snapshot()
        try:
            valuation = self.market.get_valuation()
            target = self._tilted_target(valuation.mayer_ratio)
            market_line = (f"Mayer {valuation.mayer_ratio:.2f} | "
                           f"F&G {valuation.fear_greed}")
        except (DataUnavailableError, InsufficientDataError) as e:
            target = self.config.rebalance.crypto_target
            market_line = f"조회 실패 ({e})"
        title, body = compose_briefing(
            snap,
            target_ratio=target,
            band_pp=self.config.rebalance.band_pp,
            market_line=market_line,
            prev_total_krw=self.portfolio.get_previous_total_krw(),
            traded_today_krw=self._daily_traded_krw,
        )
        self.alerts.send_info_alert(title, body)
        return {"executed": 0, "rejected": [], "halted": False,
                "note": "브리핑 발송"}

    def run_monthly_report(self) -> Dict:
        return self._guarded("월간 리포트", self._monthly_report)

    def _monthly_report(self) -> Dict:
        from src.report.reporter import Reporter

        snap = self.portfolio.get_snapshot()
        reporter = Reporter(self.binance, self.alerts)
        # 일일 스냅샷 이력 기반 30일 총자산 변화율 (입출금 포함 단순 변화)
        change = self.portfolio.get_value_change_30d(snap.total_value_krw)
        if change is not None:
            portfolio_return, window_days = change
            return reporter.monthly_report(
                portfolio_return, snap.total_value_krw, snap.crypto_ratio,
                window_days=window_days,
            )
        benchmark = reporter.btc_benchmark_return(days=30)
        report = {
            "portfolio_return": None,
            "total_value_krw": snap.total_value_krw,
            "crypto_ratio": snap.crypto_ratio,
            "btc_benchmark_return_30d": benchmark,
        }
        self.alerts.send_info_alert(
            "월간 리포트",
            f"총자산 {snap.total_value_krw:,.0f} KRW | 크립토 {snap.crypto_ratio:.0%} "
            f"| BTC 30일 {benchmark:+.1%} | 포트폴리오 수익률: 스냅샷 데이터 축적 중",
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
    def _execute_all(self, label, requests, snap, dry_run,
                     price_changes=None, notes=None) -> Dict:
        executed, rejected = 0, []
        executed_reqs = []
        # KRW 러닝 잔고 — 배치 시작 스냅샷으로 모든 주문을 검증하면
        # (a) 여러 매수가 합산 후 KRW 하한을 뚫고, (b) 매도 대금으로
        # 승인돼야 할 매수가 거부된다(한쪽 다리 리밸런싱). 체결마다 갱신.
        krw_running = snap.krw_balance
        # 매도 먼저 실행해 KRW 확보 후 매수 (하락장 리밸런싱 매수 자금)
        for req in sorted(requests, key=lambda r: r.side != "sell"):
            ctx = PortfolioContext(
                total_value_krw=snap.total_value_krw,
                krw_balance=krw_running,
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
            filled = float(report.filled_krw)
            if filled > 0:
                # 실제 체결분만 집계·기록 — 접수 성공 ≠ 체결
                executed += 1
                executed_reqs.append(
                    OrderRequest(req.asset, req.side, filled, req.origin)
                )
                self._daily_traded_krw += filled
                krw_running += filled if req.side == "sell" else -filled
                # 주문은 이미 체결됨 — 기록 실패가 나머지 주문 실행을 막으면 안 됨
                try:
                    self.portfolio.record_trade(
                        req.asset, req.side, filled, origin=req.origin
                    )
                except Exception as e:
                    logger.error(f"거래 기록 실패 (주문은 체결됨): {req.asset} — {e}")
                    self.alerts.send_error_alert(
                        "거래 기록 실패",
                        f"{req.side} {req.asset} {filled:,.0f} KRW 주문은 "
                        f"체결됐으나 DB 기록 실패: {e}",
                    )
            if not report.success:
                rejected.append((
                    req.asset,
                    f"체결 {filled:,.0f}/{req.amount_krw:,.0f} KRW — {report.error}",
                ))
        result = {"executed": executed, "rejected": rejected, "halted": False}
        logger.info(f"{label} 완료: 실행 {executed}건, 거부 {len(rejected)}건")
        if not dry_run:
            self._notify_result(label, executed_reqs, rejected, notes)
        return result

    def _notify_result(self, label, executed_reqs, rejected, notes=None) -> None:
        """체결·거부 내역 Slack 통지 — 무거래 날은 조용히 (알림 피로 방지).

        판단 근거(notes: 틸트·편출·승수·가드)를 함께 실어 서버 로그 없이
        Slack만으로 왜 거래했는지 이해할 수 있게 한다.
        알림 실패가 사이클 결과를 바꾸면 안 됨 (주문은 이미 체결됨)."""
        if not executed_reqs and not rejected:
            return
        lines = [f"📐 {n}" for n in (notes or [])] + [
            f"✅ {r.side} {r.asset} {r.amount_krw:,.0f} KRW" for r in executed_reqs
        ] + [f"🚫 {asset}: {reason}" for asset, reason in rejected]
        body = "\n".join(lines)
        try:
            if executed_reqs:
                self.alerts.send_info_alert(
                    f"{label}: 실행 {len(executed_reqs)}건"
                    + (f", 거부 {len(rejected)}건" if rejected else ""),
                    body,
                )
            else:
                self.alerts.send_warning_alert(f"{label}: 전량 거부", body)
        except Exception as e:
            logger.error(f"Slack 알림 실패 (거래는 정상 처리됨): {e}")

    def _guarded(self, label: str, fn) -> Dict:
        """무인 운영 가드 — 어떤 실패도 조용히 죽지 않고 Slack에 남긴다."""
        try:
            return fn()
        except (DataUnavailableError, InsufficientDataError) as e:
            return self._halt(label, e)
        except Exception as e:
            return self._crash(label, e)

    def _halt(self, label: str, error: Exception) -> Dict:
        logger.error(f"{label} 중단: {error}")
        self.alerts.send_warning_alert(f"{label} 중단", f"데이터 이상: {error}")
        return {"executed": 0, "rejected": [], "halted": True, "error": str(error)}

    def _crash(self, label: str, error: Exception) -> Dict:
        """예상치 못한 예외 — 데이터 이상(warning)과 구분해 error로 통지."""
        logger.exception(f"{label} 비정상 종료: {error}")
        try:
            self.alerts.send_error_alert(
                f"{label} 비정상 종료",
                f"예상치 못한 오류로 사이클 중단: {error}",
            )
        except Exception as alert_err:
            logger.error(f"오류 알림 발송도 실패: {alert_err}")
        return {"executed": 0, "rejected": [], "halted": True, "error": str(error)}


def _crash_alert_best_effort(command: str, config_path: str, error) -> None:
    """조립 단계(설정 파싱·DB·클라이언트 생성) 실패도 Slack에 남긴다.

    _guarded는 run_* 안쪽만 덮는다 — 여기서 죽으면 briefing 하트비트까지
    조용히 끊겨 fail-loud 계약이 깨진다. AlertSystem 조립조차 실패하면
    SLACK_WEBHOOK_URL 환경변수로 직접 POST한다."""
    import os

    msg = f"'{command}' 실행 불가 — 시스템 조립 단계 오류: {error}"
    try:
        from src.monitoring.alert_system import AlertSystem
        from src.utils.config_loader import ConfigLoader

        AlertSystem(ConfigLoader(config_path)).send_error_alert(
            "시스템 시작 실패", msg
        )
        return
    except Exception as e:
        logger.warning(f"AlertSystem 경유 크래시 알림 실패, webhook 직접 시도: {e}")
    try:
        import requests

        webhook = os.environ.get("SLACK_WEBHOOK_URL")
        if webhook:
            requests.post(
                webhook, json={"text": f"🚨 KAIROS 시스템 시작 실패\n{msg}"},
                timeout=10,
            )
        else:
            logger.error("SLACK_WEBHOOK_URL 미설정 — 크래시 알림 발송 불가")
    except Exception as e:
        logger.error(f"크래시 알림 발송 실패: {e}")


def main() -> int:
    parser = argparse.ArgumentParser(description="KAIROS-Simple 장기 역발상 매집")
    parser.add_argument(
        "command",
        choices=["weekly-dca", "daily-check", "briefing", "report", "status"],
    )
    parser.add_argument("--dry-run", action="store_true", help="주문 없이 시뮬레이션")
    parser.add_argument("--config", default="config/config.yaml")
    args = parser.parse_args()

    try:
        system = KairosSimple.from_yaml(args.config)
        if args.command == "weekly-dca":
            result = system.run_weekly_dca(dry_run=args.dry_run)
        elif args.command == "daily-check":
            result = system.run_daily_check(dry_run=args.dry_run)
        elif args.command == "briefing":
            result = system.run_daily_briefing()
        elif args.command == "report":
            result = system.run_monthly_report()
        else:
            result = system.get_status()
    except Exception as e:
        # run_*는 자체 가드가 있다 — 여기 오는 건 조립·status 단계 예외
        logger.exception(f"시스템 조립/실행 실패: {e}")
        _crash_alert_best_effort(args.command, args.config, e)
        return 1
    print(result)
    return 1 if result.get("halted") else 0


if __name__ == "__main__":
    sys.exit(main())
