"""코인원 주문 실행 — 지정가(슬리피지 상한), 재시도, TWAP 분할, 체결 확인.

지정가 주문은 amount=수량(qty)이므로 KRW 금액을 지정가로 나눠 변환한다.
TWAP: twap_slice_krw 초과 주문은 균등 분할해 순차 실행 (최대 6슬라이스).
체결 확인: 접수 성공 ≠ 체결. fill_timeout 내 미체결 잔량은 취소한다 —
방치된 지정가가 몇 시간 뒤 낡은 판단 가격으로 체결되는 것을 방지.
success는 전량 체결을 의미하며, filled_krw가 실제 체결 금액이다.
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
                 max_retries: int = 3, retry_wait: float = 2.0,
                 fill_timeout: float = 45.0, poll_interval: float = 3.0,
                 slippage_cap: float = SLIPPAGE_CAP):
        self.coinone = coinone_client
        self.twap_slice_krw = twap_slice_krw
        self.max_retries = max_retries
        self.retry_wait = retry_wait
        self.fill_timeout = fill_timeout
        self.poll_interval = poll_interval
        self.slippage_cap = slippage_cap

    def execute(self, order: OrderRequest) -> ExecutionReport:
        report = ExecutionReport(request=order, success=True)
        for slice_krw in self._split(order.amount_krw):
            ok, order_id, ordered_qty, err = self._place_with_retry(order, slice_krw)
            if not ok:
                report.success = False
                report.error = err
                logger.error(f"{order.asset} {order.side} 슬라이스 실패: {err}")
                break  # 부분 체결 상태로 중단 — filled_krw로 잔량 파악
            report.order_ids.append(order_id)
            fraction = self._await_fill(order_id, ordered_qty, order.asset)
            report.filled_krw += slice_krw * fraction
            if fraction < 1.0 - 1e-9:
                # 미체결 잔량은 이미 취소됨 — 가격이 지정가 밖으로 움직인
                # 상황이라 다음 슬라이스도 무의미. 체결분만 보고하고 중단.
                report.success = False
                report.error = f"미체결 잔량 취소 (체결 {fraction:.0%})"
                logger.warning(
                    f"{order.asset} {order.side} {report.error}: {order_id}"
                )
                break
        return report

    # ------------------------------------------------------------ 체결 확인
    def _await_fill(self, order_id: str, ordered_qty: float, asset: str) -> float:
        """fill_timeout 내 체결을 폴링, 타임아웃 시 잔량 취소 → 체결 비율.

        order/info·order/cancel은 마켓(quote/target_currency) 지정이 필수라
        자산을 함께 전달한다 — 누락 시 조회·취소가 실패해 체결분이 0으로
        집계되고 미체결 주문이 호가창에 방치된다."""
        deadline = time.monotonic() + self.fill_timeout
        fraction = 0.0
        while True:
            try:
                fraction = self._fill_fraction(
                    self.coinone.get_order_status(order_id, asset), ordered_qty,
                    assume_filled_on_not_found=True,
                )
            except Exception as e:
                logger.warning(f"주문 상태 조회 실패 (재시도): {order_id} — {e}")
            if fraction >= 1.0 - 1e-9:
                return 1.0
            if time.monotonic() >= deadline:
                break
            time.sleep(self.poll_interval)
        try:
            self.coinone.cancel_order(order_id, asset)
        except Exception as e:
            logger.error(f"미체결 취소 실패: {order_id} — {e}")
        try:
            # 취소 직전 체결됐을 수 있으므로 최종 상태 재확인.
            # 취소 후 not_found는 체결로 단정할 수 없어 마지막 관측값 유지.
            return self._fill_fraction(
                self.coinone.get_order_status(order_id, asset), ordered_qty,
                assume_filled_on_not_found=False, default=fraction,
            )
        except Exception:
            return fraction

    @staticmethod
    def _fill_fraction(response, ordered_qty: float,
                       assume_filled_on_not_found: bool,
                       default: float = 0.0) -> float:
        """주문 상태 응답 → 체결 비율(0~1). 스키마 방어적 파싱."""
        if not isinstance(response, dict):
            return default
        if response.get("status") == "not_found":
            # 체결 완료된 주문은 조회에서 사라질 수 있음
            return 1.0 if assume_filled_on_not_found else default
        order = response.get("order") or response
        status = str(order.get("status", "")).lower()
        if status in ("filled", "done", "completed"):
            return 1.0
        remain = order.get("remain_qty", order.get("remaining_qty"))
        if remain is None or ordered_qty <= 0:
            return default
        return max(0.0, min(1.0, 1.0 - float(remain) / ordered_qty))

    def _split(self, amount_krw: float) -> List[float]:
        if amount_krw <= self.twap_slice_krw:
            return [amount_krw]
        n = min(MAX_TWAP_SLICES, math.ceil(amount_krw / self.twap_slice_krw))
        return [amount_krw / n] * n

    def _place_with_retry(
        self, order: OrderRequest, slice_krw: float
    ) -> Tuple[bool, str, float, str]:
        last_err = ""
        for attempt in range(1, self.max_retries + 1):
            try:
                price = self.coinone.get_latest_price(order.asset)
                if not price or price <= 0:
                    raise ValueError(f"{order.asset} 현재가 조회 실패: {price}")
                limit = price * (
                    1 + self.slippage_cap if order.side == "buy"
                    else 1 - self.slippage_cap
                )
                # 코인원 호가 단위 정렬 (오류 310 방지):
                # 매수는 내림(캡 준수), 매도는 올림(하한 준수)
                # 1e-9 보정: 부동소수점 오차로 한 틱이 잘리는 것 방지
                unit = self.coinone.get_price_unit(order.asset, limit)
                if order.side == "buy":
                    limit = math.floor(limit / unit + 1e-9) * unit
                else:
                    limit = math.ceil(limit / unit - 1e-9) * unit
                qty = slice_krw / limit
                result = self.coinone.place_order(
                    currency=order.asset,
                    side=order.side,
                    amount=qty,
                    price=limit,
                )
                if isinstance(result, dict) and result.get("success"):
                    return True, str(result.get("order_id", "")), qty, ""
                if isinstance(result, dict) and result.get("ambiguous"):
                    # 주문이 거래소에 도달했는지 알 수 없는 실패 — 재제출하면
                    # 이중 주문이 될 수 있다. fail-safe로 즉시 중단.
                    last_err = (f"주문 접수 불확실 (네트워크 오류) — 이중 주문 "
                                f"방지 위해 재시도 중단: {result.get('error')}")
                    return False, "", 0.0, last_err
                last_err = f"API 오류 응답: {result}"
            except Exception as e:
                last_err = str(e)
            if attempt < self.max_retries:
                time.sleep(self.retry_wait * (2 ** (attempt - 1)))
        return False, "", 0.0, last_err
