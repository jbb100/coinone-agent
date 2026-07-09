"""
Allocation Arbiter (Phase 3)

계층 간 반대 매매를 구조적으로 차단하는 단일 조정자.

문제: 약세장에서 기회적 매수가 사들인 물량을 다음 리밸런싱이 도로 팔아
수수료·세금·슬리피지만 남기는 왕복 매매가 발생한다.

해결:
1. 클로백 면제: 기회적 매수분은 매수 후 N일(기본 30일)간 리밸런싱 매도에서 제외
2. 허용 밴드: 국면별 목표 비중 ± band_width(기본 8%p) 안에서만
   기회적 매수/매도가 움직일 수 있도록 한도 계산

실데이터 원칙: 면제 금액은 DB의 실제 기회적 매수 기록에서 계산한다.
"""

from datetime import datetime, timedelta
from typing import Dict, Optional

from loguru import logger


class AllocationArbiter:
    """자산 배분 조정자 — 전략 계층 간 충돌 방지"""

    def __init__(
        self,
        db_manager=None,
        band_width: float = 0.08,
        clawback_exempt_days: int = 30,
    ):
        """
        Args:
            db_manager: 데이터베이스 매니저 (기회적 매수 기록 조회용)
            band_width: 목표 비중 대비 허용 밴드 폭 (±8%p)
            clawback_exempt_days: 기회적 매수분의 리밸런싱 매도 면제 기간 (일)
        """
        self.db_manager = db_manager
        self.band_width = band_width
        self.clawback_exempt_days = clawback_exempt_days

        logger.info(f"AllocationArbiter 초기화: 밴드 ±{band_width:.0%}p, "
                    f"클로백 면제 {clawback_exempt_days}일")

    # ------------------------------------------------------------------
    # 클로백 면제 (기회적 매수분 보호)
    # ------------------------------------------------------------------

    def get_clawback_exempt_amount(self, asset: str) -> float:
        """
        해당 자산의 리밸런싱 매도 면제 금액 (KRW)

        최근 clawback_exempt_days일 내 기회적 매수 금액의 합.
        """
        if not self.db_manager:
            return 0.0
        try:
            records = self.db_manager.get_recent_opportunistic_buys(
                days=self.clawback_exempt_days
            )
            exempt = sum(
                float(r.get("amount_krw", 0) or 0)
                for r in records
                if r.get("asset") == asset
            )
            return exempt
        except Exception as e:
            logger.warning(f"{asset} 클로백 면제 금액 조회 실패 (면제 없음으로 처리): {e}")
            return 0.0

    def adjust_rebalance_sell(self, asset: str, proposed_sell_krw: float) -> float:
        """
        리밸런싱 매도 금액에서 클로백 면제분을 차감

        Args:
            asset: 자산 심볼
            proposed_sell_krw: 리밸런서가 계산한 매도 금액 (양수)

        Returns:
            조정된 매도 금액 (0이면 매도 스킵)
        """
        exempt = self.get_clawback_exempt_amount(asset)
        if exempt <= 0:
            return proposed_sell_krw

        adjusted = max(0.0, proposed_sell_krw - exempt)
        if adjusted < proposed_sell_krw:
            logger.info(f"🛡️ {asset} 리밸런싱 매도 조정: {proposed_sell_krw:,.0f} → {adjusted:,.0f} KRW "
                        f"(최근 {self.clawback_exempt_days}일 기회적 매수 {exempt:,.0f} KRW 면제)")
        return adjusted

    # ------------------------------------------------------------------
    # 허용 밴드 (기회적 매수/매도 한도)
    # ------------------------------------------------------------------

    def get_allocation_band(self, target_crypto_weight: float) -> Dict[str, float]:
        """목표 비중 기준 허용 밴드 [min, max] (0~1 클램프)"""
        return {
            "min": max(0.0, target_crypto_weight - self.band_width),
            "max": min(1.0, target_crypto_weight + self.band_width),
        }

    def max_opportunistic_buy(
        self,
        total_value_krw: float,
        crypto_value_krw: float,
        target_crypto_weight: float,
    ) -> float:
        """
        기회적 매수 가능 최대 금액 (KRW)

        매수 후 crypto 비중이 밴드 상단을 넘지 않는 한도.
        """
        if total_value_krw <= 0:
            return 0.0
        band = self.get_allocation_band(target_crypto_weight)
        headroom = band["max"] * total_value_krw - crypto_value_krw
        allowed = max(0.0, headroom)

        current_weight = crypto_value_krw / total_value_krw
        logger.info(f"기회적 매수 한도: {allowed:,.0f} KRW "
                    f"(현재 {current_weight:.1%} → 밴드 상단 {band['max']:.1%})")
        return allowed

    def max_opportunistic_sell(
        self,
        total_value_krw: float,
        crypto_value_krw: float,
        target_crypto_weight: float,
    ) -> float:
        """
        기회적 매도 가능 최대 금액 (KRW)

        매도 후 crypto 비중이 밴드 하단 아래로 내려가지 않는 한도.
        """
        if total_value_krw <= 0:
            return 0.0
        band = self.get_allocation_band(target_crypto_weight)
        headroom = crypto_value_krw - band["min"] * total_value_krw
        allowed = max(0.0, headroom)

        current_weight = crypto_value_krw / total_value_krw
        logger.info(f"기회적 매도 한도: {allowed:,.0f} KRW "
                    f"(현재 {current_weight:.1%} → 밴드 하단 {band['min']:.1%})")
        return allowed
