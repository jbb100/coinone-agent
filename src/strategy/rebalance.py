"""밴드 리밸런싱 — 순수 함수.

오르면 초과분을 팔고(익절), 내리면 미달분을 산다(저가 매집).
트리거는 두 가지:
  1) 크립토 총비중이 목표 ±band_pp 이탈
  2) 개별 코인이 크립토 내 목표 대비 상대 ±relative_band 이탈
거래가 트리거되면 모든 자산을 정확히 목표 비중으로 되돌린다.
"""
from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class RebalanceOrder:
    asset: str
    side: str        # "buy" | "sell"
    amount_krw: float


@dataclass(frozen=True)
class RebalanceConfig:
    crypto_target: float
    band_pp: float
    crypto_weights: Dict[str, float]
    relative_band: float
    min_trade_krw: float


def plan_rebalance(
    config: RebalanceConfig,
    holdings_krw: Dict[str, float],
    krw_balance: float,
) -> List[RebalanceOrder]:
    crypto_value = sum(holdings_krw.values())
    total_value = crypto_value + krw_balance
    if total_value <= 0:
        return []

    crypto_ratio = crypto_value / total_value
    total_breach = abs(crypto_ratio - config.crypto_target) > config.band_pp

    asset_breach = False
    if crypto_value > 0:
        for asset, target_w in config.crypto_weights.items():
            actual_w = holdings_krw.get(asset, 0.0) / crypto_value
            if target_w > 0 and abs(actual_w / target_w - 1.0) > config.relative_band:
                asset_breach = True
                break

    if not (total_breach or asset_breach):
        return []

    # 총비중 이탈 시 목표는 crypto_target, 내부 이탈만이면 현 총액 유지
    target_crypto_value = (
        total_value * config.crypto_target if total_breach else crypto_value
    )

    orders = []
    for asset, target_w in config.crypto_weights.items():
        target_value = target_crypto_value * target_w
        diff = target_value - holdings_krw.get(asset, 0.0)
        if abs(diff) < config.min_trade_krw:
            continue
        side = "buy" if diff > 0 else "sell"
        orders.append(RebalanceOrder(asset, side, abs(diff)))
    return orders
