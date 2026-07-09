"""코인원 주문 실행 — 지정가(슬리피지 상한), 재시도, TWAP 분할.

지정가 주문은 amount=수량(qty)이므로 KRW 금액을 지정가로 나눠 변환한다.
TWAP: twap_slice_krw 초과 주문은 균등 분할해 순차 실행 (최대 6슬라이스).
"""
import math
import time
from dataclasses import dataclass, field
from typing import List, Tuple

from loguru import logger

from src.risk.guard import OrderRequest

SLIPPAGE_CAP = 0.005  # 스펙 2.3: 슬리피지 상한 0.5%
MAX_TWAP_SLICES = 6


@dataclass
class ExecutionReport:
    request: OrderRequest
    success: bool
    filled_krw: float = 0.0
    order_ids: List[str] = field(default_factory=list)
    error: str = ""


class OrderExecutor:
    def __init__(self, coinone_client, twap_slice_krw: float,
                 max_retries: int = 3, retry_wait: float = 2.0):
        self.coinone = coinone_client
        self.twap_slice_krw = twap_slice_krw
        self.max_retries = max_retries
        self.retry_wait = retry_wait

    def execute(self, order: OrderRequest) -> ExecutionReport:
        report = ExecutionReport(request=order, success=True)
        for slice_krw in self._split(order.amount_krw):
            ok, order_id, err = self._place_with_retry(order, slice_krw)
            if ok:
                report.filled_krw += slice_krw
                report.order_ids.append(order_id)
            else:
                report.success = False
                report.error = err
                logger.error(f"{order.asset} {order.side} 슬라이스 실패: {err}")
                break  # 부분 체결 상태로 중단 — filled_krw로 잔량 파악
        return report

    def _split(self, amount_krw: float) -> List[float]:
        if amount_krw <= self.twap_slice_krw:
            return [amount_krw]
        n = min(MAX_TWAP_SLICES, math.ceil(amount_krw / self.twap_slice_krw))
        return [amount_krw / n] * n

    def _place_with_retry(
        self, order: OrderRequest, slice_krw: float
    ) -> Tuple[bool, str, str]:
        last_err = ""
        for attempt in range(1, self.max_retries + 1):
            try:
                price = self.coinone.get_latest_price(order.asset)
                if not price or price <= 0:
                    raise ValueError(f"{order.asset} 현재가 조회 실패: {price}")
                limit = price * (
                    1 + SLIPPAGE_CAP if order.side == "buy" else 1 - SLIPPAGE_CAP
                )
                qty = slice_krw / limit
                result = self.coinone.place_order(
                    currency=order.asset,
                    side=order.side,
                    amount=qty,
                    price=limit,
                )
                if isinstance(result, dict) and result.get("success"):
                    return True, str(result.get("order_id", "")), ""
                last_err = f"API 오류 응답: {result}"
            except Exception as e:
                last_err = str(e)
            if attempt < self.max_retries:
                time.sleep(self.retry_wait * (2 ** (attempt - 1)))
        return False, "", last_err
