"""주간 DCA 주문 계산 — 순수 함수."""
import math
from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class DCAOrder:
    asset: str
    amount_krw: float


@dataclass(frozen=True)
class DCAConfig:
    base_amount_krw: float
    crypto_weights: Dict[str, float]
    max_single_dca_krw: float
    krw_usage_cap: float
    min_order_krw: float

    def __post_init__(self):
        if not math.isclose(sum(self.crypto_weights.values()), 1.0, abs_tol=1e-9):
            raise ValueError(f"crypto_weights 합이 1이 아님: {self.crypto_weights}")
        if not 0 < self.krw_usage_cap <= 1:
            raise ValueError(f"krw_usage_cap 범위 오류: {self.krw_usage_cap}")


def plan_weekly_dca(
    config: DCAConfig, multiplier: float, krw_balance: float
) -> List[DCAOrder]:
    total = config.base_amount_krw * multiplier
    total = min(total, config.max_single_dca_krw, krw_balance * config.krw_usage_cap)
    if total <= 0:
        return []
    orders = []
    for asset, weight in config.crypto_weights.items():
        amount = total * weight
        if amount >= config.min_order_krw:
            orders.append(DCAOrder(asset, amount))
    return orders
