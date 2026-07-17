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
    # 크래시 가드: 24h 급락(threshold 이하) 자산의 매수를 분할 진입
    crash_threshold: float = -0.10
    crash_buy_fraction: float = 0.5


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
            actual = holdings_krw.get(asset, 0.0)
            if target_w <= 0:
                # 완전 편출(목표 0) 자산: 잔여 포지션 자체가 트리거 —
                # 다른 이탈을 기다리며 무기한 방치되면 안 된다
                if actual >= config.min_trade_krw:
                    asset_breach = True
                    break
                continue
            actual_w = actual / crypto_value
            if abs(actual_w / target_w - 1.0) > config.relative_band:
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


def apply_crash_guard(
    orders: List[RebalanceOrder],
    price_change_24h: Dict[str, float],
    threshold: float,
    buy_fraction: float,
    min_trade_krw: float,
) -> List[RebalanceOrder]:
    """급락 시 분할 진입 — FOMO 가드(급등 매수 금지)의 대칭 리스크 컨트롤.

    24h 변동이 threshold(예: -10%) 이하인 자산의 매수는 buy_fraction만
    집행한다. 일일 체크가 매일 돌므로 밴드 이탈이 지속되면 남은 미달분을
    다음날 마저 산다 — 며칠에 걸친 자연스러운 시간 분산 진입.
    매도(익절)는 건드리지 않는다.
    """
    out = []
    for order in orders:
        if (
            order.side == "buy"
            and price_change_24h.get(order.asset, 0.0) <= threshold
        ):
            scaled = order.amount_krw * buy_fraction
            if scaled < min_trade_krw:
                continue
            out.append(RebalanceOrder(order.asset, "buy", scaled))
        else:
            out.append(order)
    return out
