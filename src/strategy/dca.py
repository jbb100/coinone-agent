"""주간 DCA 주문 계산 — 순수 함수.

목표 비중 인지형(value averaging): 매수 후 크립토 비중이 목표를 넘지
않도록 총액을 상한 처리한다. 불변식 "DCA는 목표 위로 사지 않고,
리밸런서는 목표+밴드 위에서만 판다"로 두 전략의 충돌(매수 직후 매도)을
구조적으로 차단한다. 목표 도달 시 남는 현금은 다음 하락 매집 재원이 된다.
"""
import math
from dataclasses import dataclass
from typing import Dict, List, Optional


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
    config: DCAConfig,
    multiplier: float,
    krw_balance: float,
    crypto_value_krw: Optional[float] = None,
    target_crypto_ratio: Optional[float] = None,
) -> List[DCAOrder]:
    if (crypto_value_krw is None) != (target_crypto_ratio is None):
        raise ValueError(
            "crypto_value_krw와 target_crypto_ratio는 함께 지정해야 함"
        )
    total = config.base_amount_krw * multiplier
    total = min(total, config.max_single_dca_krw, krw_balance * config.krw_usage_cap)
    if crypto_value_krw is not None:
        # 매수는 KRW→크립토 전환이라 총자산 불변 → 목표 도달까지의 여유분만 매수
        headroom = (
            target_crypto_ratio * (crypto_value_krw + krw_balance) - crypto_value_krw
        )
        total = min(total, max(0.0, headroom))
    if total <= 0:
        return []
    orders = []
    for asset, weight in config.crypto_weights.items():
        amount = total * weight
        if amount >= config.min_order_krw:
            orders.append(DCAOrder(asset, amount))
    return orders
