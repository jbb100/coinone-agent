"""
Dynamic Execution Engine

TWAP (시간 가중 평균 가격) 분할 매매와 변동성 적응형 실행을 담당하는 모듈입니다.
리밸런싱 주문을 시장 상황에 맞게 분할하여 실행함으로써 시장 충격을 최소화합니다.
"""

import time
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import numpy as np
from loguru import logger

from ..trading.coinone_client import CoinoneClient
from ..utils.database_manager import DatabaseManager


class MarketVolatility(Enum):
    """시장 변동성 수준"""
    STABLE = "stable"      # 안정 시장 (ATR 낮음)
    VOLATILE = "volatile"  # 변동 시장 (ATR 높음)


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
    status: str = "pending"  # pending, executing, completed, failed
    
    def __post_init__(self):
        if self.remaining_amount_krw == 0:
            self.remaining_amount_krw = self.total_amount_krw
        if self.remaining_quantity == 0:
            self.remaining_quantity = self.total_quantity


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
        atr_period: int = 14,
        atr_threshold: float = 0.05
    ):
        """
        Args:
            coinone_client: 코인원 API 클라이언트
            db_manager: 데이터베이스 매니저
            atr_period: ATR 계산 기간 (기본값: 14일)
            atr_threshold: 변동성 임계값 (기본값: 5%)
        """
        self.coinone_client = coinone_client
        self.db_manager = db_manager
        self.atr_period = atr_period
        self.atr_threshold = atr_threshold
        
        # 실행 중인 TWAP 주문들
        self.active_twap_orders: List[TWAPOrder] = []
        
        logger.info("DynamicExecutionEngine 초기화 완료")
        logger.info(f"ATR 기간: {atr_period}일, 변동성 임계값: {atr_threshold:.1%}")
    
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
        market_data: Optional[pd.DataFrame] = None
    ) -> List[TWAPOrder]:
        """
        리밸런싱 주문들을 TWAP 주문으로 변환
        
        Args:
            rebalance_orders: 리밸런싱 주문 정보
            market_data: BTC 시장 데이터 (ATR 계산용)
            
        Returns:
            TWAP 주문 리스트
        """
        try:
            # 1. 시장 변동성 분석
            if market_data is not None:
                atr = self.calculate_atr(market_data)
                volatility = self.determine_market_volatility(atr)
            else:
                # 기본값: 중간 변동성으로 가정
                volatility = MarketVolatility.VOLATILE
                logger.warning("시장 데이터 없음. 기본 변동성(VOLATILE) 적용")
            
            # 2. 실행 파라미터 결정
            execution_hours, slice_count = self.get_execution_parameters(volatility)
            slice_interval_minutes = (execution_hours * 60) // slice_count
            
            # 3. TWAP 주문 생성
            twap_orders = []
            start_time = datetime.now()
            end_time = start_time + timedelta(hours=execution_hours)
            
            for asset, order_info in rebalance_orders.items():
                # KRW는 건너뜀 (기본 통화)
                if asset.upper() == "KRW":
                    continue
                
                # 너무 작은 주문은 즉시 실행
                amount_krw = abs(order_info["amount_diff_krw"])
                if amount_krw < 50000:  # 5만원 미만 (코인원 최소 주문 금액 고려)
                    logger.info(f"{asset}: 소액 주문({amount_krw:,.0f} KRW)으로 즉시 실행")
                    continue
                
                # 슬라이스 크기가 너무 작으면 분할 횟수 조정
                slice_amount = amount_krw / slice_count
                min_slice_amount = 5000  # 코인원 최소 주문 금액 (5,000원)
                
                if slice_amount < min_slice_amount:
                    # 분할 횟수를 줄여서 슬라이스 크기를 늘림
                    adjusted_slice_count = max(1, int(amount_krw / min_slice_amount))
                    logger.warning(f"{asset}: 슬라이스 크기 조정 {slice_count} → {adjusted_slice_count}회 "
                                 f"(슬라이스 크기: {amount_krw/adjusted_slice_count:,.0f} KRW)")
                    slice_count = adjusted_slice_count
                    slice_interval_minutes = max(5, (execution_hours * 60) // slice_count)  # 최소 5분 간격
                
                # 현재가 조회하여 수량 계산
                try:
                    ticker = self.coinone_client.get_ticker(asset)
                    current_price = float(ticker.get("data", {}).get("close_24h", 0))
                    if current_price <= 0:
                        logger.error(f"{asset}: 잘못된 현재가 {current_price}")
                        continue
                    
                    quantity = amount_krw / current_price
                except Exception as e:
                    logger.error(f"{asset}: 현재가 조회 실패 - {e}")
                    continue
                
                # TWAP 주문 생성
                twap_order = TWAPOrder(
                    asset=asset,
                    side=order_info["action"],
                    total_amount_krw=amount_krw,
                    total_quantity=quantity,
                    execution_hours=execution_hours,
                    slice_count=slice_count,
                    slice_amount_krw=amount_krw / slice_count,
                    slice_quantity=quantity / slice_count,
                    start_time=start_time,
                    end_time=end_time,
                    slice_interval_minutes=slice_interval_minutes
                )
                
                twap_orders.append(twap_order)
                logger.info(f"TWAP 주문 생성: {asset} {order_info['action']} {amount_krw:,.0f} KRW "
                          f"({slice_count}회 분할, {slice_interval_minutes}분 간격)")
            
            return twap_orders
            
        except Exception as e:
            logger.error(f"TWAP 주문 생성 실패: {e}")
            return []
    
    def execute_twap_slice(self, twap_order: TWAPOrder) -> Dict:
        """
        TWAP 주문의 단일 슬라이스 실행
        
        Args:
            twap_order: TWAP 주문 정보
            
        Returns:
            실행 결과
        """
        try:
            # 실행할 슬라이스 크기 계산
            if twap_order.executed_slices >= twap_order.slice_count:
                return {
                    "success": False,
                    "error": "모든 슬라이스 실행 완료"
                }
            
            # 마지막 슬라이스인 경우 남은 전체 수량 실행
            if twap_order.executed_slices == twap_order.slice_count - 1:
                amount_krw = twap_order.remaining_amount_krw
            else:
                amount_krw = twap_order.slice_amount_krw
            
            # 실제 주문 실행
            order_result = self.coinone_client.place_order(
                currency=twap_order.asset,
                side=twap_order.side,
                amount=amount_krw,
                amount_in_krw=True
            )
            
            # 결과 처리
            if order_result.get("result") == "success":
                twap_order.executed_slices += 1
                twap_order.remaining_amount_krw -= amount_krw
                
                if twap_order.executed_slices >= twap_order.slice_count:
                    twap_order.status = "completed"
                else:
                    twap_order.status = "executing"
                
                logger.info(f"TWAP 슬라이스 실행 성공: {twap_order.asset} "
                          f"({twap_order.executed_slices}/{twap_order.slice_count})")
                
                return {
                    "success": True,
                    "order_id": order_result.get("order_id"),
                    "amount_krw": amount_krw,
                    "executed_slices": twap_order.executed_slices,
                    "total_slices": twap_order.slice_count
                }
            else:
                logger.error(f"TWAP 슬라이스 실행 실패: {order_result}")
                return {
                    "success": False,
                    "error": order_result.get("error_msg", "주문 실패")
                }
                
        except Exception as e:
            logger.error(f"TWAP 슬라이스 실행 중 오류: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def start_twap_execution(self, rebalance_orders: Dict[str, Dict]) -> Dict:
        """
        TWAP 실행 시작
        
        Args:
            rebalance_orders: 리밸런싱 주문 정보
            
        Returns:
            실행 계획 정보
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
            
            # 2. TWAP 주문 생성
            twap_orders = self.create_twap_orders(rebalance_orders, market_data)
            
            if not twap_orders:
                return {
                    "success": True,
                    "message": "TWAP 실행할 주문이 없습니다",
                    "twap_orders": [],
                    "immediate_orders": len(rebalance_orders)
                }
            
            # 3. 활성 TWAP 주문에 추가
            self.active_twap_orders.extend(twap_orders)
            
            # 4. 첫 번째 슬라이스 즉시 실행
            immediate_results = []
            for twap_order in twap_orders:
                result = self.execute_twap_slice(twap_order)
                immediate_results.append({
                    "asset": twap_order.asset,
                    "result": result
                })
            
            # 5. 실행 계획 저장
            execution_plan = {
                "start_time": datetime.now(),
                "twap_orders": len(twap_orders),
                "total_execution_hours": twap_orders[0].execution_hours if twap_orders else 0,
                "slice_interval_minutes": twap_orders[0].slice_interval_minutes if twap_orders else 0,
                "immediate_results": immediate_results
            }
            
            # 데이터베이스에 저장
            self.db_manager.save_twap_execution_plan(execution_plan)
            
            logger.info(f"TWAP 실행 시작: {len(twap_orders)}개 주문, "
                       f"{twap_orders[0].execution_hours if twap_orders else 0}시간 실행 계획")
            
            return {
                "success": True,
                "message": f"TWAP 실행 시작: {len(twap_orders)}개 주문",
                "execution_plan": execution_plan,
                "twap_orders": [
                    {
                        "asset": order.asset,
                        "side": order.side,
                        "total_amount_krw": order.total_amount_krw,
                        "slice_count": order.slice_count,
                        "execution_hours": order.execution_hours
                    } for order in twap_orders
                ]
            }
            
        except Exception as e:
            logger.error(f"TWAP 실행 시작 실패: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def process_pending_twap_orders(self) -> Dict:
        """
        대기 중인 TWAP 주문들을 처리
        
        Returns:
            처리 결과
        """
        try:
            if not self.active_twap_orders:
                return {
                    "success": True,
                    "message": "처리할 TWAP 주문이 없습니다"
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
                next_execution_time = (
                    twap_order.start_time + 
                    timedelta(minutes=twap_order.slice_interval_minutes * twap_order.executed_slices)
                )
                
                # 실행 시간이 되었는지 확인
                if current_time >= next_execution_time:
                    result = self.execute_twap_slice(twap_order)
                    processed_orders.append({
                        "asset": twap_order.asset,
                        "executed_slices": twap_order.executed_slices,
                        "total_slices": twap_order.slice_count,
                        "result": result
                    })
                    
                    if twap_order.status == "completed":
                        completed_orders.append(twap_order)
            
            # 완료된 주문들 제거
            for completed_order in completed_orders:
                if completed_order in self.active_twap_orders:
                    self.active_twap_orders.remove(completed_order)
                    logger.info(f"TWAP 주문 완료: {completed_order.asset}")
            
            return {
                "success": True,
                "processed_orders": len(processed_orders),
                "completed_orders": len(completed_orders),
                "remaining_orders": len(self.active_twap_orders),
                "details": processed_orders
            }
            
        except Exception as e:
            logger.error(f"TWAP 주문 처리 실패: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
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