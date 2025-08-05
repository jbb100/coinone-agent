"""
Order Manager

주문 실행 및 관리를 담당하는 모듈
"""

import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
from loguru import logger

from .coinone_client import CoinoneClient


class OrderStatus(Enum):
    """주문 상태"""
    PENDING = "pending"         # 대기 중
    SUBMITTED = "submitted"     # 제출됨
    PARTIALLY_FILLED = "partially_filled"  # 부분 체결
    FILLED = "filled"          # 완전 체결
    CANCELLED = "cancelled"    # 취소됨
    FAILED = "failed"          # 실패
    EXPIRED = "expired"        # 만료됨


class Order:
    """주문 클래스"""
    
    def __init__(
        self,
        order_id: str,
        currency: str,
        side: str,  # "buy" or "sell"
        order_type: str,  # "market" or "limit"
        amount: float,
        price: Optional[float] = None
    ):
        self.order_id = order_id
        self.currency = currency
        self.side = side
        self.order_type = order_type
        self.amount = amount
        self.price = price
        self.status = OrderStatus.PENDING
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.filled_amount = 0.0
        self.average_price = 0.0
        self.fee = 0.0
        self.error_message = None
    
    def update_status(self, status: OrderStatus, **kwargs):
        """주문 상태 업데이트"""
        self.status = status
        self.updated_at = datetime.now()
        
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def to_dict(self) -> Dict:
        """딕셔너리로 변환"""
        return {
            "order_id": self.order_id,
            "currency": self.currency,
            "side": self.side,
            "order_type": self.order_type,
            "amount": self.amount,
            "price": self.price,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "filled_amount": self.filled_amount,
            "average_price": self.average_price,
            "fee": self.fee,
            "error_message": self.error_message
        }


class OrderManager:
    """
    주문 관리자
    
    주문 실행, 모니터링, 실패 처리 등을 담당합니다.
    """
    
    def __init__(self, coinone_client: CoinoneClient):
        """
        Args:
            coinone_client: 코인원 클라이언트
        """
        self.coinone_client = coinone_client
        self.active_orders: Dict[str, Order] = {}
        self.completed_orders: List[Order] = []
        
        # 설정
        self.max_retry_attempts = 3
        self.retry_delay = 5  # 5초
        self.order_timeout = 300  # 5분
        self.status_check_interval = 10  # 10초
        
        logger.info("OrderManager 초기화 완료")
    
    def submit_market_order(
        self,
        currency: str,
        side: str,
        amount: float
    ) -> Optional[Order]:
        """
        시장가 주문 제출
        
        Args:
            currency: 거래할 코인
            side: "buy" or "sell"
            amount: 거래 수량 (매수시 KRW 금액, 매도시 코인 수량)
            
        Returns:
            Order 객체 또는 None (실패시)
        """
        try:
            logger.info(f"시장가 주문 제출: {side} {amount} {currency}")
            
            # 코인원 API 호출
            response = self.coinone_client.place_order(
                currency=currency,
                side=side,
                amount=amount,
                price=None  # 시장가
            )
            
            if response.get("success", False):
                order_id = response.get("order_id") or f"market_{currency}_{int(time.time())}"
                
                order = Order(
                    order_id=order_id,
                    currency=currency,
                    side=side,
                    order_type="market",
                    amount=amount
                )
                
                order.update_status(OrderStatus.SUBMITTED)
                self.active_orders[order_id] = order
                
                logger.info(f"주문 제출 성공: {order_id}")
                return order
            else:
                error_msg = response.get('error_msg', 'Unknown error')
                logger.error(f"주문 제출 실패: {error_msg} - {response}")
                # 상세 오류를 포함하여 반환하도록 수정
                failed_order = Order(
                    order_id=f"failed_{currency}_{int(time.time())}",
                    currency=currency,
                    side=side,
                    order_type="market",
                    amount=amount
                )
                failed_order.update_status(OrderStatus.FAILED, error_message=error_msg)
                return failed_order
                
        except Exception as e:
            logger.error(f"주문 제출 중 오류: {e}")
            return None
    
    def submit_limit_order(
        self,
        currency: str,
        side: str,
        amount: float,
        price: float
    ) -> Optional[Order]:
        """
        지정가 주문 제출
        
        Args:
            currency: 거래할 코인
            side: "buy" or "sell"
            amount: 거래 수량
            price: 지정가격
            
        Returns:
            Order 객체 또는 None (실패시)
        """
        try:
            logger.info(f"지정가 주문 제출: {side} {amount} {currency} @ {price}")
            
            response = self.coinone_client.place_order(
                currency=currency,
                side=side,
                amount=amount,
                price=price
            )
            
            if response.get("result") == "success":
                order_id = response.get("order_id")
                
                order = Order(
                    order_id=order_id,
                    currency=currency,
                    side=side,
                    order_type="limit",
                    amount=amount,
                    price=price
                )
                
                order.update_status(OrderStatus.SUBMITTED)
                self.active_orders[order_id] = order
                
                logger.info(f"지정가 주문 제출 성공: {order_id}")
                return order
            else:
                logger.error(f"지정가 주문 제출 실패: {response}")
                return None
                
        except Exception as e:
            logger.error(f"지정가 주문 제출 중 오류: {e}")
            return None
    
    def cancel_order(self, order_id: str) -> bool:
        """
        주문 취소
        
        Args:
            order_id: 주문 ID
            
        Returns:
            취소 성공 여부
        """
        try:
            order = self.active_orders.get(order_id)
            if not order:
                logger.warning(f"주문을 찾을 수 없음: {order_id}")
                return False
            
            response = self.coinone_client.cancel_order(order_id)
            
            if response.get("result") == "success":
                order.update_status(OrderStatus.CANCELLED)
                self._move_to_completed(order_id)
                logger.info(f"주문 취소 성공: {order_id}")
                return True
            else:
                logger.error(f"주문 취소 실패: {response}")
                return False
                
        except Exception as e:
            logger.error(f"주문 취소 중 오류: {e}")
            return False
    
    def check_order_status(self, order_id: str) -> Optional[OrderStatus]:
        """
        주문 상태 확인
        
        Args:
            order_id: 주문 ID
            
        Returns:
            주문 상태 또는 None (오류시)
        """
        try:
            order = self.active_orders.get(order_id)
            if not order:
                return None
            
            response = self.coinone_client.get_order_status(order_id)
            
            if response.get("result") == "success":
                # 코인원 응답을 OrderStatus로 변환
                coinone_status = response.get("status", "").lower()
                
                if coinone_status in ["live", "pending"]:
                    status = OrderStatus.SUBMITTED
                elif coinone_status == "partially_filled":
                    status = OrderStatus.PARTIALLY_FILLED
                elif coinone_status == "filled":
                    status = OrderStatus.FILLED
                elif coinone_status == "cancelled":
                    status = OrderStatus.CANCELLED
                else:
                    status = OrderStatus.FAILED
                
                # 주문 정보 업데이트
                order.update_status(
                    status=status,
                    filled_amount=float(response.get("filled_qty", 0)),
                    average_price=float(response.get("avg_price", 0)),
                    fee=float(response.get("fee", 0))
                )
                
                # 완료된 주문은 active에서 제거
                if status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.FAILED]:
                    self._move_to_completed(order_id)
                
                return status
            else:
                logger.error(f"주문 상태 조회 실패: {response}")
                return None
                
        except Exception as e:
            logger.error(f"주문 상태 확인 중 오류: {e}")
            return None
    
    def monitor_orders(self) -> Dict[str, int]:
        """
        모든 활성 주문 모니터링
        
        Returns:
            상태별 주문 개수 딕셔너리
        """
        status_count = {
            "submitted": 0,
            "partially_filled": 0,
            "filled": 0,
            "cancelled": 0,
            "failed": 0,
            "expired": 0
        }
        
        current_time = datetime.now()
        expired_orders = []
        
        for order_id, order in self.active_orders.items():
            # 타임아웃 체크
            if (current_time - order.created_at).total_seconds() > self.order_timeout:
                order.update_status(OrderStatus.EXPIRED)
                expired_orders.append(order_id)
                status_count["expired"] += 1
                continue
            
            # 상태 업데이트
            status = self.check_order_status(order_id)
            if status:
                status_count[status.value] += 1
        
        # 만료된 주문 정리
        for order_id in expired_orders:
            self._move_to_completed(order_id)
            logger.warning(f"주문 만료로 인한 정리: {order_id}")
        
        if self.active_orders:
            logger.info(f"활성 주문 모니터링: {status_count}")
        
        return status_count
    
    def execute_rebalance_orders(self, rebalance_orders: List[Dict]) -> Dict[str, List]:
        """
        리밸런싱 주문 일괄 실행
        
        Args:
            rebalance_orders: 리밸런싱 주문 리스트
            
        Returns:
            실행 결과 딕셔너리
        """
        executed_orders = []
        failed_orders = []
        
        logger.info(f"리밸런싱 주문 일괄 실행: {len(rebalance_orders)}개")
        
        # 매도 주문 먼저 실행 (현금 확보)
        sell_orders = [order for order in rebalance_orders if order.get("side") == "sell"]
        buy_orders = [order for order in rebalance_orders if order.get("side") == "buy"]
        
        # 매도 주문 실행
        for order_info in sell_orders:
            order = self._execute_single_order(order_info)
            if order:
                executed_orders.append(order.to_dict())
            else:
                failed_orders.append(order_info)
        
        # 매도 주문 완료 대기
        self._wait_for_orders_completion([o.order_id for o in executed_orders if o])
        
        # 매수 주문 실행
        for order_info in buy_orders:
            order = self._execute_single_order(order_info)
            if order:
                executed_orders.append(order.to_dict())
            else:
                failed_orders.append(order_info)
        
        logger.info(f"리밸런싱 완료: 성공 {len(executed_orders)}, 실패 {len(failed_orders)}")
        return {"executed": executed_orders, "failed": failed_orders}
    
    def _execute_single_order(self, order_info: Dict) -> Optional[Order]:
        """
        단일 주문 실행
        
        Args:
            order_info: 주문 정보
            
        Returns:
            Order 객체 또는 None
        """
        currency = order_info.get("currency")
        side = order_info.get("side")
        amount = order_info.get("amount")
        order_type = order_info.get("type", "market")
        price = order_info.get("price")
        
        for attempt in range(self.max_retry_attempts):
            try:
                if order_type == "market":
                    order = self.submit_market_order(currency, side, amount)
                else:
                    order = self.submit_limit_order(currency, side, amount, price)
                
                if order:
                    return order
                
                # 재시도 전 대기
                if attempt < self.max_retry_attempts - 1:
                    time.sleep(self.retry_delay)
                    
            except Exception as e:
                logger.error(f"주문 실행 시도 {attempt + 1} 실패: {e}")
                if attempt < self.max_retry_attempts - 1:
                    time.sleep(self.retry_delay)
        
        logger.error(f"주문 실행 최종 실패: {order_info}")
        return None
    
    def _wait_for_orders_completion(self, order_ids: List[str], timeout: int = 300):
        """
        주문 완료 대기
        
        Args:
            order_ids: 대기할 주문 ID 리스트
            timeout: 타임아웃 (초)
        """
        start_time = time.time()
        
        while order_ids and (time.time() - start_time) < timeout:
            remaining_orders = []
            
            for order_id in order_ids:
                status = self.check_order_status(order_id)
                if status not in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.FAILED]:
                    remaining_orders.append(order_id)
            
            order_ids = remaining_orders
            
            if order_ids:
                time.sleep(self.status_check_interval)
        
        if order_ids:
            logger.warning(f"타임아웃으로 인한 대기 종료: {len(order_ids)}개 주문 미완료")
    
    def _move_to_completed(self, order_id: str):
        """완료된 주문을 active에서 completed로 이동"""
        if order_id in self.active_orders:
            order = self.active_orders.pop(order_id)
            self.completed_orders.append(order)
    
    def get_order_history(self, days: int = 7) -> List[Dict]:
        """
        주문 내역 조회
        
        Args:
            days: 조회 기간 (일)
            
        Returns:
            주문 내역 리스트
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        
        recent_orders = [
            order.to_dict() 
            for order in self.completed_orders 
            if order.created_at >= cutoff_date
        ]
        
        return sorted(recent_orders, key=lambda x: x["created_at"], reverse=True)
    
    def get_active_orders(self) -> List[Dict]:
        """활성 주문 목록 조회"""
        return [order.to_dict() for order in self.active_orders.values()]


# 설정 상수
DEFAULT_MAX_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_DELAY = 5         # 5초
DEFAULT_ORDER_TIMEOUT = 300     # 5분
DEFAULT_STATUS_CHECK_INTERVAL = 10  # 10초 