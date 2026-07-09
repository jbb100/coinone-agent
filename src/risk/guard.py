"""모든 주문이 통과해야 하는 단일 리스크 관문."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional

from src.core.exceptions import DataUnavailableError


@dataclass(frozen=True)
class RiskLimits:
    max_single_trade_krw: float
    max_daily_volume_krw: float
    min_krw_ratio: float
    fomo_surge_threshold: float


@dataclass(frozen=True)
class OrderRequest:
    asset: str
    side: str          # "buy" | "sell"
    amount_krw: float
    origin: str        # "dca" | "rebalance"


@dataclass(frozen=True)
class PortfolioContext:
    total_value_krw: float
    krw_balance: float
    daily_traded_krw: float
    price_change_24h: Dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationResult:
    approved: bool
    reason: str = ""


class RiskGuard:
    def __init__(self, limits: RiskLimits):
        self.limits = limits

    def validate(self, order: OrderRequest, ctx: PortfolioContext) -> ValidationResult:
        limits = self.limits
        if order.amount_krw > limits.max_single_trade_krw:
            return ValidationResult(
                False,
                f"단일 거래 한도 초과: {order.amount_krw:,.0f}"
                f" > {limits.max_single_trade_krw:,.0f}",
            )
        if ctx.daily_traded_krw + order.amount_krw > limits.max_daily_volume_krw:
            return ValidationResult(
                False,
                f"일일 거래량 한도 초과: {ctx.daily_traded_krw + order.amount_krw:,.0f}"
                f" > {limits.max_daily_volume_krw:,.0f}",
            )
        if order.side == "buy":
            krw_after = ctx.krw_balance - order.amount_krw
            if krw_after < ctx.total_value_krw * limits.min_krw_ratio:
                return ValidationResult(
                    False,
                    f"매수 후 KRW 비중이 하한({limits.min_krw_ratio:.0%}) 미달",
                )
            change = ctx.price_change_24h.get(order.asset, 0.0)
            if order.origin != "dca" and change >= limits.fomo_surge_threshold:
                return ValidationResult(
                    False,
                    f"{order.asset} 24h {change:+.0%} 급등 — FOMO 가드: DCA 외 매수 금지",
                )
        return ValidationResult(True)


def ensure_fresh(name: str, ts: Optional[datetime], max_age_hours: float) -> None:
    """데이터 신선도 검사 — 스테일이면 거래 중단(fail-loud)."""
    if ts is None:
        raise DataUnavailableError(f"{name}: 타임스탬프 없음")
    age_hours = (datetime.now() - ts).total_seconds() / 3600
    if age_hours > max_age_hours:
        raise DataUnavailableError(f"{name}: 데이터 스테일 ({age_hours:.1f}h > {max_age_hours}h)")
