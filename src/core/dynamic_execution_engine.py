"""
Dynamic Execution Engine

TWAP (시간 가중 평균 가격) 분할 매매와 변동성 적응형 실행을 담당하는 모듈입니다.
리밸런싱 주문을 시장 상황에 맞게 분할하여 실행함으로써 시장 충격을 최소화합니다.
"""

import time
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd
import numpy as np
from loguru import logger
import uuid

from ..trading.coinone_client import CoinoneClient
from ..utils.database_manager import DatabaseManager


class MarketVolatility(Enum):
    """시장 변동성 상태"""
    STABLE = "stable"         # 안정
    VOLATILE = "volatile"     # 변동성 높음


@dataclass
class TWAPOrder:
    """TWAP 분할 주문 정보"""
    asset: str
    side: str  # "buy" or "sell"
    total_amount_krw: float
    total_quantity: float
    execution_hours: int
    slice_count: int
    slice_amount_krw: float
    slice_quantity: float
    start_time: datetime
    end_time: datetime
    slice_interval_minutes: int
    executed_slices: int = 0
    remaining_amount_krw: float = 0
    remaining_quantity: float = 0
    status: str = "pending"  # pending, executing, completed, failed, cancelled
    last_execution_time: Optional[datetime] = None  # 마지막 실행 시간
    # 시장 상황 추적 정보 추가
    market_season: str = "neutral"  # 주문 시작 시의 시장 계절
    target_allocation: Dict[str, float] = field(default_factory=dict)  # 목표 배분 비율
    created_at: datetime = field(default_factory=datetime.now)  # 주문 생성 시간
    # 실제 거래소 주문 추적
    exchange_order_ids: List[str] = field(default_factory=list)  # 실제 거래소 주문 ID들
    last_rebalance_check: Optional[datetime] = None  # 마지막 리밸런싱 체크 시간
    
    def __post_init__(self):
        if self.remaining_amount_krw == 0:
            self.remaining_amount_krw = self.total_amount_krw
        if self.remaining_quantity == 0:
            self.remaining_quantity = self.total_quantity

    def to_dict(self) -> Dict:
        """주문 정보를 딕셔너리로 변환"""
        return {
            "asset": self.asset,
            "side": self.side,
            "total_amount_krw": self.total_amount_krw,
            "total_quantity": self.total_quantity,
            "execution_hours": self.execution_hours,
            "slice_count": self.slice_count,
            "slice_amount_krw": self.slice_amount_krw,
            "slice_quantity": self.slice_quantity,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "slice_interval_minutes": self.slice_interval_minutes,
            "executed_slices": self.executed_slices,
            "remaining_amount_krw": self.remaining_amount_krw,
            "remaining_quantity": self.remaining_quantity,
            "status": self.status,
            "last_execution_time": self.last_execution_time.isoformat() if self.last_execution_time else None,
            "market_season": self.market_season,
            "target_allocation": self.target_allocation,
            "created_at": self.created_at.isoformat(),
            "exchange_order_ids": self.exchange_order_ids,
            "last_rebalance_check": self.last_rebalance_check.isoformat() if self.last_rebalance_check else None
        }


class DynamicExecutionEngine:
    """
    동적 실행 엔진
    
    TWAP 분할 매매와 변동성 적응형 실행을 통해 
    시장 충격을 최소화하면서 리밸런싱을 수행합니다.
    """
    
    def __init__(
        self, 
        coinone_client: CoinoneClient,
        db_manager: DatabaseManager,
        rebalancer=None,  # Add rebalancer parameter
        atr_period: int = 14,
        atr_threshold: float = 0.05
    ):
        """
        Args:
            coinone_client: 코인원 API 클라이언트
            db_manager: 데이터베이스 매니저
            rebalancer: 리밸런서 인스턴스 (선택적)
            atr_period: ATR 계산 기간 (기본값: 14일)
            atr_threshold: 변동성 임계값 (기본값: 5%)
        """
        self.coinone_client = coinone_client
        self.db_manager = db_manager
        self.rebalancer = rebalancer  # Store rebalancer instance
        self.atr_period = atr_period
        self.atr_threshold = atr_threshold
        
        # crontab 실행 주기 (분) - 기본값: 15분
        self.crontab_interval_minutes = 15
        
        # 실행 중인 TWAP 주문들
        self.active_twap_orders: List[TWAPOrder] = []
        self.current_execution_id = None  # 현재 활성 실행 ID
        
        # 데이터베이스에서 활성 TWAP 주문들 복원
        self._load_active_twap_orders()
        
        logger.info("DynamicExecutionEngine 초기화 완료")
        logger.info(f"ATR 기간: {atr_period}일, 변동성 임계값: {atr_threshold:.1%}")
        
        if self.active_twap_orders:
            logger.info(f"기존 활성 TWAP 주문 {len(self.active_twap_orders)}개 복원 완료")
            for order in self.active_twap_orders:
                logger.info(f"  - {order.asset}: {order.executed_slices}/{order.slice_count} 슬라이스 ({order.status})")
    
    def _load_active_twap_orders(self):
        """데이터베이스에서 활성 TWAP 주문들을 로드"""
        try:
            # 현재 실행 ID가 없으면 빈 리스트 반환
            if not self.current_execution_id:
                logger.info("현재 활성 TWAP 실행 ID가 없음")
                self.active_twap_orders = []
                return

            self.active_twap_orders = self.db_manager.load_active_twap_orders(self.current_execution_id)
            logger.info(f"활성 TWAP 주문 로드: {len(self.active_twap_orders)}개")
        except Exception as e:
            logger.error(f"활성 TWAP 주문 로드 실패: {e}")
            self.active_twap_orders = []
    
    def calculate_atr(self, price_data: pd.DataFrame) -> float:
        """
        ATR (Average True Range) 계산
        
        Args:
            price_data: OHLC 가격 데이터 (yfinance 형태)
            
        Returns:
            ATR 값 (소수점)
        """
        try:
            # True Range 계산
            high_low = price_data['High'] - price_data['Low']
            high_close_prev = (price_data['High'] - price_data['Close'].shift(1)).abs()
            low_close_prev = (price_data['Low'] - price_data['Close'].shift(1)).abs()
            
            true_range = pd.concat([high_low, high_close_prev, low_close_prev], axis=1).max(axis=1)
            
            # ATR = True Range의 지수이동평균
            atr = true_range.ewm(span=self.atr_period).mean().iloc[-1]
            
            # 상대적 ATR (ATR / 현재가)
            current_price = price_data['Close'].iloc[-1]
            relative_atr = atr / current_price
            
            logger.info(f"ATR 계산 완료: {relative_atr:.3%} (절대값: {atr:,.0f})")
            return relative_atr
            
        except Exception as e:
            logger.error(f"ATR 계산 실패: {e}")
            # 기본값 반환 (중간 변동성)
            return self.atr_threshold
    
    def determine_market_volatility(self, atr: float) -> MarketVolatility:
        """
        ATR을 기반으로 시장 변동성 수준 결정
        
        Args:
            atr: 상대적 ATR 값
            
        Returns:
            시장 변동성 수준
        """
        if atr <= self.atr_threshold:
            volatility = MarketVolatility.STABLE
            logger.info(f"시장 상태: 안정 (ATR: {atr:.3%} <= {self.atr_threshold:.1%})")
        else:
            volatility = MarketVolatility.VOLATILE
            logger.info(f"시장 상태: 변동 (ATR: {atr:.3%} > {self.atr_threshold:.1%})")
        
        return volatility
    
    def get_execution_parameters(self, volatility: MarketVolatility) -> Tuple[int, int]:
        """
        시장 변동성에 따른 실행 파라미터 결정
        
        Args:
            volatility: 시장 변동성 수준
            
        Returns:
            (실행 시간(시간), 분할 횟수)
        """
        if volatility == MarketVolatility.STABLE:
            # 안정 시장: 6시간 동안 신속 실행
            execution_hours = 6
            slice_count = 12  # 30분 간격
        else:
            # 변동 시장: 24시간 동안 보수적 실행
            execution_hours = 24
            slice_count = 24  # 1시간 간격
        
        logger.info(f"실행 계획: {execution_hours}시간 동안 {slice_count}회 분할 실행")
        return execution_hours, slice_count
    
    def create_twap_orders(
        self, 
        rebalance_orders: Dict[str, Dict],
        market_season: str = None,
        target_allocation: Dict[str, float] = None
    ) -> List[TWAPOrder]:
        """
        리밸런싱 주문을 TWAP 분할 주문으로 변환
        
        Args:
            rebalance_orders: 리밸런싱 주문 정보
            market_season: 현재 시장 계절
            target_allocation: 목표 배분 비율
            
        Returns:
            TWAP 주문 리스트
        """
        try:
            # 실행 파라미터 계산
            exec_params = self._get_execution_parameters()
            
            if not exec_params:
                logger.error("실행 파라미터 계산 실패")
                return []
            
            execution_hours = exec_params["execution_hours"]
            slice_count = exec_params["slice_count"]
            slice_interval_minutes = exec_params["slice_interval_minutes"]
            
            # 실행 시간 계산
            start_time = datetime.now()
            end_time = start_time + timedelta(hours=execution_hours)
            
            twap_orders = []
            
            for asset, order_info in rebalance_orders.items():
                amount_krw = order_info.get("amount_diff_krw", 0)
                
                # 최소 주문 금액 체크 (1만원)
                if abs(amount_krw) < 10000:
                    logger.info(f"{asset} 주문 금액이 너무 작음: {amount_krw:,.0f} KRW - 건너뜀")
                    continue
                
                # 주문 방향 결정
                side = "buy" if amount_krw > 0 else "sell"
                amount_krw = abs(amount_krw)
                
                # 수량 계산 (매도 시에만 사용)
                quantity = order_info.get("quantity_diff", 0)
                quantity = abs(quantity) if side == "sell" else 0
                
                # 슬라이스당 금액/수량 계산
                slice_amount = amount_krw / slice_count
                slice_quantity = quantity / slice_count if quantity > 0 else 0
                
                # TWAP 주문 생성
                twap_order = TWAPOrder(
                    asset=asset,
                    side=side,
                    total_amount_krw=amount_krw,
                    total_quantity=quantity,
                    execution_hours=execution_hours,
                    slice_count=slice_count,
                    slice_amount_krw=slice_amount,
                    slice_quantity=slice_quantity,
                    start_time=start_time,
                    end_time=end_time,
                    slice_interval_minutes=slice_interval_minutes,
                    remaining_amount_krw=amount_krw,
                    remaining_quantity=quantity,
                    market_season=market_season,
                    target_allocation=target_allocation
                )
                
                twap_orders.append(twap_order)
                logger.info(f"TWAP 주문 생성: {asset} {side} {amount_krw:,.0f} KRW "
                          f"({slice_count}회 분할, {slice_interval_minutes}분 간격)")
            
            return twap_orders
            
        except Exception as e:
            logger.error(f"TWAP 주문 생성 실패: {e}")
            return []
    
    def execute_twap_slice(self, order: TWAPOrder) -> Dict:
        """TWAP 슬라이스 실행"""
        try:
            logger.info(f"TWAP 슬라이스 실행 시작: {order.asset} {order.slice_amount_krw:,.0f} KRW ({order.executed_slices + 1}/{order.slice_count})")
            
            # 잔고 확인 및 주문 크기 조정
            if order.side == "buy":
                balance = self.coinone_client.get_balances().get("KRW", 0)
                if balance < order.slice_amount_krw:
                    adjusted_amount = min(balance * 0.99, order.slice_amount_krw)  # 1% 마진
                    if adjusted_amount < 1000:  # 최소 주문 금액
                        logger.error(f"💥 TWAP 주문 실패 - 잔고 부족: {order.asset} (실행 중단)")
                        order.status = "failed"
                        return {"success": False, "error": "insufficient_balance"}
                    logger.warning(f"잔고 부족으로 주문 크기 조정: {order.slice_amount_krw:,.0f} → {adjusted_amount:,.0f} KRW")
                    order.slice_amount_krw = adjusted_amount
            else:  # sell
                balance = self.coinone_client.get_balances().get(order.asset, 0)
                if balance < order.slice_quantity:
                    adjusted_quantity = min(balance * 0.99, order.slice_quantity)
                    if adjusted_quantity * self.coinone_client.get_current_price(order.asset) < 1000:
                        logger.error(f"💥 TWAP 주문 실패 - 잔고 부족: {order.asset} (실행 중단)")
                        order.status = "failed"
                        return {"success": False, "error": "insufficient_balance"}
                    logger.warning(f"잔고 부족으로 주문 수량 조정: {order.slice_quantity} → {adjusted_quantity} {order.asset}")
                    order.slice_quantity = adjusted_quantity
            
            # 실행할 슬라이스 크기 계산
            if order.executed_slices >= order.slice_count:
                return {
                    "success": False,
                    "error": "모든 슬라이스 실행 완료"
                }
            
            # 마지막 슬라이스인 경우 남은 전체 수량 실행
            if order.executed_slices == order.slice_count - 1:
                amount_krw = order.remaining_amount_krw
            else:
                amount_krw = order.slice_amount_krw
            
            logger.info(f"TWAP 슬라이스 실행 시작: {order.asset} {amount_krw:,.0f} KRW "
                       f"({order.executed_slices + 1}/{order.slice_count})")
            
            # 안전한 주문 실행 (잔액 확인, 한도 검증, 자동 재시도)
            order_result = self.coinone_client.place_safe_order(
                currency=order.asset,
                side=order.side,
                amount=amount_krw,
                amount_in_krw=True,
                max_retries=3
            )
            
            # 결과 처리
            if order_result.get("success"):
                # 실제 실행된 금액 (조정된 경우 반영)
                executed_amount = amount_krw  # TODO: 실제 체결 금액으로 업데이트
                
                # 거래소 주문 ID 추가
                order_id = order_result.get("order_id")
                if order_id and order_id not in order.exchange_order_ids:
                    order.exchange_order_ids.append(order_id)
                
                order.executed_slices += 1
                order.remaining_amount_krw -= executed_amount
                order.last_execution_time = datetime.now()
                
                if order.executed_slices >= order.slice_count:
                    order.status = "completed"
                else:
                    order.status = "executing"
                
                # 데이터베이스에 상태 업데이트
                self.db_manager.update_twap_orders_status(self.current_execution_id, self.active_twap_orders)
                
                logger.info(f"✅ TWAP 슬라이스 실행 성공: {order.asset} "
                          f"({order.executed_slices}/{order.slice_count})")
                
                return {
                    "success": True,
                    "order_id": order_result.get("order_id"),
                    "amount_krw": executed_amount,
                    "executed_slices": order.executed_slices,
                    "total_slices": order.slice_count,
                    "remaining_amount": order.remaining_amount_krw
                }
            else:
                # 주문 실패 시 처리
                order.last_execution_time = datetime.now()
                error_msg = order_result.get("error", "Unknown error")
                error_code = order_result.get("error_code", "unknown")
                
                # 잔고 부족 등 치명적인 오류의 경우 주문을 실패 상태로 마킹
                if "잔고" in error_msg or "잔액" in error_msg or "insufficient" in error_msg.lower():
                    order.status = "failed"
                    logger.error(f"💥 TWAP 주문 실패 - 잔고 부족: {order.asset} (실행 중단)")
                    # 데이터베이스에 실패 상태 저장
                    self.db_manager.update_twap_orders_status(self.current_execution_id, self.active_twap_orders)
                else:
                    # 일시적인 오류의 경우 계속 재시도
                    logger.warning(f"⚠️ TWAP 슬라이스 일시 실패 (재시도 예정): {order.asset} - {error_msg}")
                    # 실패 시에도 데이터베이스 업데이트 (재시도를 위해)
                    self.db_manager.update_twap_orders_status(self.current_execution_id, self.active_twap_orders)
                
                logger.error(f"❌ TWAP 슬라이스 실행 실패: {order.asset} - {error_msg}")
                
                return {
                    "success": False,
                    "error": error_msg,
                    "error_code": error_code,
                    "asset": order.asset,
                    "amount_krw": amount_krw,
                    "executed_slices": order.executed_slices,
                    "total_slices": order.slice_count,
                    "is_fatal": order.status == "failed"
                }
                
        except Exception as e:
            logger.error(f"TWAP 슬라이스 실행 중 오류: {e}")
            return {
                "success": False,
                "error": str(e),
                "asset": order.asset
            }

    def start_twap_execution(self, rebalance_orders: Dict[str, Dict], market_season: str = None, target_allocation: Dict[str, float] = None) -> Dict:
        """
        TWAP 실행 시작
        
        Args:
            rebalance_orders: 리밸런싱 주문 정보
            market_season: 현재 시장 계절
            target_allocation: 목표 배분 비율
            
        Returns:
            실행 계획 정보
        """
        try:
            # 1. 기존 활성 TWAP 주문들 정리
            if self.active_twap_orders:
                logger.warning(f"새로운 TWAP 실행 시작 - 기존 활성 주문 {len(self.active_twap_orders)}개 정리")
                
                # 1-1. 실제 거래소 주문들 취소
                cancel_result = self._cancel_pending_exchange_orders(self.active_twap_orders)
                if cancel_result.get("success"):
                    cancelled_count = cancel_result.get("cancelled_count", 0)
                    failed_count = cancel_result.get("failed_count", 0)
                    logger.info(f"거래소 주문 취소 결과: 성공 {cancelled_count}개, 실패 {failed_count}개")
                    
                    if failed_count > 0:
                        logger.warning("일부 거래소 주문 취소 실패 - 수동 확인 필요")
                else:
                    logger.error(f"거래소 주문 취소 실패: {cancel_result.get('error')}")
                    return {
                        "success": False,
                        "error": "거래소 주문 취소 실패로 새로운 TWAP 실행 중단"
                    }
                
                # 1-2. 모든 TWAP 주문을 cancelled 상태로 변경
                for order in self.active_twap_orders:
                    if order.status in ["pending", "executing"]:
                        order.status = "cancelled"
                        logger.info(f"TWAP 주문 중단: {order.asset} ({order.executed_slices}/{order.slice_count} 슬라이스 완료)")
                
                # 1-3. 데이터베이스 상태 업데이트
                try:
                    self.db_manager.update_twap_orders_status(self.current_execution_id, self.active_twap_orders)
                except Exception as e:
                    logger.error(f"TWAP 주문 상태 업데이트 실패: {e}")
                    # 실패해도 계속 진행
                
                # 1-4. 메모리에서 모든 주문 제거
                self.active_twap_orders = []
                logger.info("기존 TWAP 주문 정리 완료")
                
                # 1-5. 잠시 대기 (거래소 주문 취소 반영 시간)
                if cancel_result.get("cancelled_count", 0) > 0:
                    logger.info("⏱️ 거래소 주문 취소 반영을 위해 5초 대기...")
                    import time
                    time.sleep(5)
            
            # 2. 새로운 TWAP 주문 생성
            logger.info("새로운 TWAP 주문 생성 시작")
            
            # 시장 상황 정보 설정
            if market_season is None or target_allocation is None:
                current_market_season, current_allocation = self._get_current_market_condition()
                market_season = current_market_season
                target_allocation = current_allocation
            
            # 실행 파라미터 계산
            exec_params = self._get_execution_parameters()
            
            # TWAP 주문 생성
            twap_orders = self.create_twap_orders(
                rebalance_orders=rebalance_orders,
                market_season=market_season,
                target_allocation=target_allocation
            )
            
            if not twap_orders:
                return {
                    "success": False,
                    "error": "TWAP 주문 생성 실패"
                }
            
            # 새로운 실행 ID 생성
            self.current_execution_id = str(uuid.uuid4())
            
            # 새로운 TWAP 주문들 저장
            self.active_twap_orders = twap_orders
            
            # 데이터베이스에 저장
            try:
                self.db_manager.save_twap_execution_plan(self.current_execution_id, twap_orders)
            except Exception as e:
                logger.error(f"TWAP 실행 계획 저장 실패: {e}")
                # 저장 실패해도 계속 진행 (다음 실행 시 복구 가능)
            
            logger.info(f"✅ TWAP 실행 계획 수립 완료: {len(twap_orders)}개 주문")
            for order in twap_orders:
                logger.info(f"  - {order.asset}: {order.slice_count}회 분할, {order.total_amount_krw:,.0f} KRW")
            
            return {
                "success": True,
                "execution_id": self.current_execution_id,
                "twap_orders": [
                    {
                        "asset": order.asset,
                        "side": order.side,
                        "total_amount_krw": order.total_amount_krw,
                        "slice_count": order.slice_count,
                        "execution_hours": order.execution_hours,
                        "slice_interval_minutes": order.slice_interval_minutes
                    } for order in twap_orders
                ],
                "execution_params": exec_params
            }
            
        except Exception as e:
            logger.error(f"TWAP 실행 시작 실패: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def process_pending_twap_orders(self, check_market_conditions: bool = True) -> Dict:
        """
        대기 중인 TWAP 주문들을 처리
        
        Args:
            check_market_conditions: 시장 상황 체크 여부
            
        Returns:
            처리 결과
        """
        try:
            if not self.active_twap_orders:
                return {
                    "success": True,
                    "message": "처리할 TWAP 주문이 없습니다"
                }
            
            # 시장 상황 체크 (기본적으로 활성화)
            market_condition_changed = False
            if check_market_conditions and self.active_twap_orders:
                market_condition_changed = self._check_market_condition_change()
                
                if market_condition_changed:
                    logger.warning("🔄 시장 상황 변화 감지 - 기존 TWAP 주문 중단하고 새로운 리밸런싱 필요")
                    return {
                        "success": True,
                        "market_condition_changed": True,
                        "message": "시장 상황 변화로 인한 TWAP 중단",
                        "action_required": "new_rebalancing",
                        "processed_orders": 0,
                        "completed_orders": 0,
                        "remaining_orders": len(self.active_twap_orders)
                    }
            
            current_time = datetime.now()
            processed_orders = []
            completed_orders = []
            
            for twap_order in self.active_twap_orders:
                # 완료된 주문은 건너뜀
                if twap_order.status == "completed":
                    completed_orders.append(twap_order)
                    continue
                
                # 다음 슬라이스 실행 시간 계산
                if twap_order.last_execution_time is None:
                    # 첫 번째 슬라이스: 시작 시간 기준
                    next_execution_time = twap_order.start_time
                else:
                    # 두 번째 슬라이스부터: 마지막 실행 시간 + 간격
                    next_execution_time = (
                        twap_order.last_execution_time + 
                        timedelta(minutes=twap_order.slice_interval_minutes)
                    )
                
                # 실행 시간이 되었는지 확인
                if current_time >= next_execution_time:
                    logger.info(f"TWAP 슬라이스 실행 시간: {twap_order.asset} "
                              f"({twap_order.executed_slices + 1}/{twap_order.slice_count})")
                    result = self.execute_twap_slice(twap_order)
                    processed_orders.append({
                        "asset": twap_order.asset,
                        "executed_slices": twap_order.executed_slices,
                        "total_slices": twap_order.slice_count,
                        "result": result,
                        "next_execution_time": next_execution_time.strftime("%Y-%m-%d %H:%M:%S")
                    })
                    
                    if twap_order.status == "completed":
                        completed_orders.append(twap_order)
                else:
                    # 아직 실행 시간이 안된 경우 로그 출력
                    remaining_minutes = (next_execution_time - current_time).total_seconds() / 60
                    logger.info(f"{twap_order.asset}: 다음 실행까지 {remaining_minutes:.1f}분 남음 (예정: {next_execution_time.strftime('%H:%M:%S')})")
            
            # 완료된 주문들과 실패한 주문들 제거
            orders_to_remove = []
            for completed_order in completed_orders:
                if completed_order in self.active_twap_orders:
                    orders_to_remove.append(completed_order)
                    logger.info(f"TWAP 주문 완료: {completed_order.asset}")
            
            # 실패한 주문들도 제거
            failed_orders = [order for order in self.active_twap_orders if order.status == "failed"]
            for failed_order in failed_orders:
                if failed_order in self.active_twap_orders:
                    orders_to_remove.append(failed_order)
                    logger.warning(f"TWAP 주문 실패로 제거: {failed_order.asset} (잔고 부족 등)")
            
            # 한 번에 제거
            for order in orders_to_remove:
                self.active_twap_orders.remove(order)
            
            # 데이터베이스에 활성 TWAP 주문 상태 업데이트
            self.db_manager.update_twap_orders_status(self.current_execution_id, self.active_twap_orders)

            return {
                "success": True,
                "processed_orders": len(processed_orders),
                "completed_orders": len(completed_orders),
                "remaining_orders": len(self.active_twap_orders),
                "details": processed_orders,
                "market_condition_changed": market_condition_changed
            }
            
        except Exception as e:
            logger.error(f"TWAP 주문 처리 실패: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _check_market_condition_change(self) -> bool:
        """
        시장 상황 변화 체크 (개선된 버전)
        
        Returns:
            시장 상황이 변경되었는지 여부
        """
        try:
            if not self.active_twap_orders:
                return False
            
            # 기존 TWAP 주문의 시장 계절과 목표 배분 가져오기
            first_order = self.active_twap_orders[0]
            original_market_season = first_order.market_season
            original_allocation = first_order.target_allocation
            
            # 쿨다운 체크 - 최근 리밸런싱 체크 후 최소 30분 대기
            cooldown_minutes = 30
            if first_order.last_rebalance_check:
                time_since_last_check = datetime.now() - first_order.last_rebalance_check
                if time_since_last_check.total_seconds() < cooldown_minutes * 60:
                    remaining_minutes = cooldown_minutes - (time_since_last_check.total_seconds() / 60)
                    logger.debug(f"리밸런싱 쿨다운 중: {remaining_minutes:.1f}분 남음")
                    return False
            
            # 현재 시장 상황 분석
            current_market_season, current_allocation = self._get_current_market_condition()
            
            # 현재 실제 포트폴리오 상태 조회 (부분 실행된 주문 반영)
            try:
                current_portfolio = self.coinone_client.get_portfolio_value()
                current_weights = self._calculate_current_weights(current_portfolio)
            except Exception as e:
                logger.error(f"현재 포트폴리오 조회 실패: {e}")
                return False
            
            # 시장 계절 변화 체크
            season_changed = original_market_season != current_market_season
            if season_changed:
                logger.warning(f"🔄 시장 계절 변화: {original_market_season} → {current_market_season}")
            
            # 목표 배분 비율의 유의미한 변화 체크
            allocation_changed = False
            significant_threshold = 0.03  # 3% 이상 차이
            min_absolute_change = 20000   # 최소 2만원 이상 차이
            
            if original_allocation and current_allocation and current_weights:
                total_value = current_portfolio.get("total_krw", 0)
                
                for asset, original_weight in original_allocation.items():
                    if asset in ["crypto", "krw"]:  # 상위 레벨 배분만 체크
                        continue
                        
                    current_target_weight = current_allocation.get(asset, 0)
                    current_actual_weight = current_weights.get(asset, 0)
                    
                    # 목표 비중 변화
                    target_weight_change = abs(original_weight - current_target_weight)
                    
                    # 현재 실제 비중과 새로운 목표 비중의 차이
                    actual_vs_new_target = abs(current_actual_weight - current_target_weight)
                    
                    # 절대 금액으로 환산
                    target_change_krw = target_weight_change * total_value
                    actual_vs_target_krw = actual_vs_new_target * total_value
                    
                    # 유의미한 변화 조건:
                    # 1. 목표 비중이 3% 이상 변했거나
                    # 2. 현재 실제 비중과 새 목표 비중의 차이가 3% 이상이면서 2만원 이상
                    if (target_weight_change > significant_threshold or 
                        (actual_vs_new_target > significant_threshold and actual_vs_target_krw > min_absolute_change)):
                        
                        logger.warning(f"📊 {asset} 배분 변화 감지:")
                        logger.warning(f"  목표 비중 변화: {original_weight:.1%} → {current_target_weight:.1%} (차이: {target_weight_change:.1%})")
                        logger.warning(f"  현재 실제: {current_actual_weight:.1%}, 새 목표: {current_target_weight:.1%} (차이: {actual_vs_new_target:.1%})")
                        logger.warning(f"  금액 환산: {actual_vs_target_krw:,.0f} KRW")
                        allocation_changed = True
                        break
            
            # TWAP 주문이 너무 오래 실행 중인지 체크 (24시간 초과)
            max_execution_hours = 24
            execution_timeout = False
            if first_order.created_at:
                execution_duration = datetime.now() - first_order.created_at
                if execution_duration.total_seconds() > max_execution_hours * 3600:
                    logger.warning(f"⏰ TWAP 실행 시간 초과: {execution_duration.total_seconds() / 3600:.1f}시간")
                    execution_timeout = True
            
            # 리밸런싱 체크 시간 업데이트
            for order in self.active_twap_orders:
                order.last_rebalance_check = datetime.now()
            
            # 변화 감지 결과
            needs_rebalancing = season_changed or allocation_changed or execution_timeout
            
            if needs_rebalancing:
                change_reasons = []
                if season_changed:
                    change_reasons.append("시장 계절 변화")
                if allocation_changed:
                    change_reasons.append("목표 배분 변화")
                if execution_timeout:
                    change_reasons.append("실행 시간 초과")
                
                logger.warning(f"🚨 리밸런싱 필요: {', '.join(change_reasons)}")
            
            return needs_rebalancing
            
        except Exception as e:
            logger.error(f"시장 상황 체크 실패: {e}")
            return False
    
    def _get_current_market_condition(self) -> Tuple[str, Dict[str, float]]:
        """
        현재 시장 상황 조회
        
        Returns:
            (현재 시장 계절, 현재 목표 배분)
        """
        try:
            # 리밸런서를 통해 현재 시장 상황 분석
            rebalance_result = self.rebalancer.calculate_rebalancing_orders()
            
            if not rebalance_result.get("success"):
                logger.error("시장 상황 분석 실패")
                return "neutral", {}
            
            # 시장 계절과 목표 비중 추출
            market_season = rebalance_result.get("market_season", "neutral")
            target_weights = rebalance_result.get("target_weights", {})
            
            # 상위 레벨 배분 (crypto vs krw) 계산
            crypto_total = sum(weight for asset, weight in target_weights.items() if asset != "KRW")
            target_allocation = {
                "crypto": crypto_total,
                "krw": target_weights.get("KRW", 0),
                **{asset: weight for asset, weight in target_weights.items() if asset not in ["crypto", "KRW"]}
            }
            
            logger.info(f"현재 시장 상황: {market_season} (암호화폐 {crypto_total:.1%}, KRW {target_weights.get('KRW', 0):.1%})")
            
            return market_season, target_allocation
            
        except Exception as e:
            logger.error(f"시장 상황 조회 실패: {e}")
            return "neutral", {}
    
    def get_twap_status(self) -> Dict:
        """
        현재 TWAP 실행 상태 조회
        
        Returns:
            TWAP 상태 정보
        """
        try:
            status_info = {
                "active_orders": len(self.active_twap_orders),
                "orders": []
            }
            
            for twap_order in self.active_twap_orders:
                progress = (twap_order.executed_slices / twap_order.slice_count) * 100
                remaining_time = twap_order.end_time - datetime.now()
                
                order_status = {
                    "asset": twap_order.asset,
                    "side": twap_order.side,
                    "total_amount_krw": twap_order.total_amount_krw,
                    "progress": f"{progress:.1f}%",
                    "executed_slices": twap_order.executed_slices,
                    "total_slices": twap_order.slice_count,
                    "remaining_amount_krw": twap_order.remaining_amount_krw,
                    "remaining_time_hours": max(0, remaining_time.total_seconds() / 3600),
                    "status": twap_order.status
                }
                
                status_info["orders"].append(order_status)
            
            return status_info
            
        except Exception as e:
            logger.error(f"TWAP 상태 조회 실패: {e}")
            return {"error": str(e)} 

    def _optimize_execution_for_crontab(self, exec_params: Dict) -> Dict:
        """
        crontab 실행 주기에 맞춰 TWAP 실행 파라미터 최적화
        
        Args:
            exec_params: 기본 실행 파라미터
            
        Returns:
            최적화된 실행 파라미터
        """
        execution_hours = exec_params["execution_hours"]
        slice_count = exec_params["slice_count"]
        
        # crontab 주기에 맞춰 슬라이스 간격 조정 (기본값: 15분)
        crontab_interval_minutes = getattr(self, 'crontab_interval_minutes', 15)
        total_minutes = execution_hours * 60
        
        # 기본 간격 계산
        base_interval = total_minutes // slice_count if slice_count > 0 else crontab_interval_minutes
        
        # crontab 주기를 고려한 최적 간격 설정
        if base_interval > crontab_interval_minutes:
            # 간격이 crontab 주기보다 크면 슬라이스 수를 늘림
            optimal_slice_count = total_minutes // crontab_interval_minutes
            slice_count = max(slice_count, optimal_slice_count)
            slice_interval_minutes = total_minutes // slice_count
        else:
            # crontab 주기에 맞춰 최적 간격 설정
            slice_interval_minutes = max(crontab_interval_minutes, base_interval)
            # 조정된 간격으로 슬라이스 수 재계산
            if slice_interval_minutes > 0:
                optimal_slice_count = total_minutes // slice_interval_minutes
                slice_count = max(slice_count, optimal_slice_count)
        
        return {
            "execution_hours": execution_hours,
            "slice_count": slice_count,
            "slice_interval_minutes": slice_interval_minutes
        } 

    def _calculate_current_weights(self, portfolio: Dict) -> Dict[str, float]:
        """
        현재 포트폴리오 비중 계산
        
        Args:
            portfolio: 포트폴리오 정보
            
        Returns:
            자산별 비중 딕셔너리
        """
        try:
            total_value = portfolio.get("total_krw", 0)
            if total_value <= 0:
                return {}
            
            weights = {}
            for asset, asset_info in portfolio.get("assets", {}).items():
                if isinstance(asset_info, dict):
                    value_krw = asset_info.get("value_krw", 0)
                elif isinstance(asset_info, (int, float)):
                    value_krw = asset_info
                else:
                    continue
                    
                weights[asset] = value_krw / total_value
            
            return weights
            
        except Exception as e:
            logger.error(f"현재 비중 계산 실패: {e}")
            return {} 

    def _cancel_pending_exchange_orders(self, twap_orders: List[TWAPOrder]) -> Dict:
        """
        대기 중인 거래소 주문들을 모두 취소
        
        Args:
            twap_orders: 취소할 TWAP 주문들
            
        Returns:
            취소 결과
        """
        cancelled_count = 0
        failed_count = 0
        cancelled_orders = []
        
        try:
            for twap_order in twap_orders:
                for order_id in twap_order.exchange_order_ids:
                    try:
                        logger.info(f"거래소 주문 취소 시도: {order_id} ({twap_order.asset})")
                        
                        # 주문 상태 먼저 확인
                        status_response = self.coinone_client.get_order_status(order_id)
                        if status_response.get("result") == "success":
                            order_status = status_response.get("status", "").lower()
                            
                            # 이미 체결되었거나 취소된 주문은 건너뜀
                            if order_status in ["filled", "cancelled"]:
                                logger.info(f"주문 {order_id} 이미 {order_status} 상태 - 취소 건너뜀")
                                continue
                        
                        # 주문 취소 실행
                        cancel_response = self.coinone_client.cancel_order(order_id)
                        
                        if cancel_response.get("result") == "success":
                            cancelled_count += 1
                            cancelled_orders.append({
                                "order_id": order_id,
                                "asset": twap_order.asset,
                                "status": "cancelled"
                            })
                            logger.info(f"✅ 주문 취소 성공: {order_id}")
                        else:
                            failed_count += 1
                            error_msg = cancel_response.get("error_message", "Unknown error")
                            logger.warning(f"⚠️ 주문 취소 실패: {order_id} - {error_msg}")
                            
                    except Exception as e:
                        failed_count += 1
                        logger.error(f"❌ 주문 취소 중 오류: {order_id} - {e}")
                
                # TWAP 주문 상태를 cancelled로 변경
                if twap_order.status in ["pending", "executing"]:
                    twap_order.status = "cancelled"
            
            logger.info(f"거래소 주문 취소 완료: 성공 {cancelled_count}개, 실패 {failed_count}개")
            
            return {
                "success": True,
                "cancelled_count": cancelled_count,
                "failed_count": failed_count,
                "cancelled_orders": cancelled_orders,
                "total_processed": cancelled_count + failed_count
            }
            
        except Exception as e:
            logger.error(f"거래소 주문 취소 실패: {e}")
            return {
                "success": False,
                "error": str(e),
                "cancelled_count": cancelled_count,
                "failed_count": failed_count
            } 

    def _get_execution_parameters(self) -> Dict:
        """
        TWAP 실행 파라미터 계산
        
        Returns:
            실행 파라미터 딕셔너리
        """
        try:
            # 1. BTC 시장 데이터 수집 (ATR 계산용)
            try:
                import yfinance as yf
                btc_ticker = yf.Ticker("BTC-USD")
                market_data = btc_ticker.history(period="30d")  # 30일 데이터
            except Exception as e:
                logger.warning(f"시장 데이터 수집 실패: {e}")
                market_data = None
            
            # 2. ATR 기반 변동성 분석
            if market_data is not None and not market_data.empty:
                atr = self.calculate_atr(market_data)
                volatility = self.determine_market_volatility(atr)
            else:
                volatility = MarketVolatility.STABLE
            
            # 3. 변동성에 따른 실행 파라미터 조정
            if volatility == MarketVolatility.VOLATILE: # Changed from MarketVolatility.HIGH to MarketVolatility.VOLATILE
                execution_hours = 12  # 12시간
                slice_count = 24      # 30분 간격
            elif volatility == MarketVolatility.STABLE: # Changed from MarketVolatility.MEDIUM to MarketVolatility.STABLE
                execution_hours = 8   # 8시간
                slice_count = 16      # 30분 간격
            else:  # STABLE
                execution_hours = 6   # 6시간
                slice_count = 12      # 30분 간격
            
            # 4. crontab 실행 주기에 맞춰 최적화
            crontab_interval_minutes = getattr(self, 'crontab_interval_minutes', 15)  # 기본값 15분
            total_minutes = execution_hours * 60
            
            # 기본 간격 계산
            base_interval = total_minutes // slice_count if slice_count > 0 else crontab_interval_minutes
            
            # crontab 주기를 고려한 최적 간격 설정
            if base_interval > crontab_interval_minutes:
                # 간격이 crontab 주기보다 크면 슬라이스 수를 늘림
                optimal_interval = max(crontab_interval_minutes, base_interval // 2)
                slice_count = total_minutes // optimal_interval
            else:
                # 간격이 crontab 주기보다 작으면 crontab 주기로 맞춤
                optimal_interval = crontab_interval_minutes
                slice_count = total_minutes // optimal_interval
            
            # 최소 슬라이스 수 보장
            min_slices = 4
            if slice_count < min_slices:
                slice_count = min_slices
                optimal_interval = total_minutes // slice_count
            
            # 최대 슬라이스 수 제한
            max_slices = 48  # 15분 간격으로 12시간
            if slice_count > max_slices:
                slice_count = max_slices
                optimal_interval = total_minutes // slice_count
            
            logger.info(f"TWAP 실행 파라미터 계산 완료:")
            logger.info(f"  • 실행 시간: {execution_hours}시간")
            logger.info(f"  • 분할 횟수: {slice_count}회")
            logger.info(f"  • 실행 간격: {optimal_interval}분")
            logger.info(f"  • 시장 변동성: {volatility.value}")
            
            return {
                "execution_hours": execution_hours,
                "slice_count": slice_count,
                "slice_interval_minutes": optimal_interval,
                "market_volatility": volatility.value,
                "atr_value": atr if 'atr' in locals() else None
            }
            
        except Exception as e:
            logger.error(f"실행 파라미터 계산 실패: {e}")
            # 기본값 반환
            return {
                "execution_hours": 6,
                "slice_count": 12,
                "slice_interval_minutes": 30,
                "market_volatility": "stable",
                "atr_value": None
            } 

    def _send_twap_start_notification(self, twap_orders: List[TWAPOrder]) -> None:
        """TWAP 시작 알림 발송"""
        try:
            if not twap_orders:
                return
                
            message = "🔄 **TWAP 실행 시작**\n\n"
            
            for order in twap_orders:
                order_info = order.to_dict()
                message += f"**{order_info['asset']}**: {order_info['side']} {order_info['total_amount_krw']:,.0f} KRW\n"
                message += f"  • {order_info['slice_count']}회 분할, {order_info['slice_interval_minutes']}분 간격\n"
                message += f"  • 실행 시간: {order_info['execution_hours']}시간\n\n"
            
            self.alert_system.send_notification(
                title="🔄 TWAP 실행 시작",
                message=message,
                alert_type="twap_start",
                priority="high"
            )
            
        except Exception as e:
            logger.error(f"TWAP 시작 알림 실패: {e}") 