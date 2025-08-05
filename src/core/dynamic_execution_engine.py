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
    last_execution_time: Optional[datetime] = None  # 마지막 실행 시간
    
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
            self.current_execution_id, self.active_twap_orders = self.db_manager.load_active_twap_orders()
            logger.info(f"활성 TWAP 주문 로드: {len(self.active_twap_orders)}개")
        except Exception as e:
            logger.error(f"활성 TWAP 주문 로드 실패: {e}")
            self.active_twap_orders = []
            self.current_execution_id = None
    
    def _save_twap_orders_to_db(self):
        """현재 TWAP 주문들을 데이터베이스에 저장"""
        try:
            if self.current_execution_id and self.active_twap_orders:
                self.db_manager.update_twap_orders_status(self.current_execution_id, self.active_twap_orders)
                logger.debug("TWAP 주문 상태 데이터베이스 업데이트 완료")
        except Exception as e:
            logger.error(f"TWAP 주문 상태 저장 실패: {e}")
    
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
            
            # crontab 주기에 맞춰 슬라이스 간격 조정 (기본값: 15분)
            crontab_interval_minutes = getattr(self, 'crontab_interval_minutes', 15)
            total_minutes = execution_hours * 60
            
            # 기본 간격 계산
            base_interval = total_minutes // slice_count
            
            # crontab 주기를 고려한 최적 간격 설정
            if base_interval > crontab_interval_minutes:
                # 간격이 crontab 주기보다 크면 슬라이스 수를 늘림
                optimal_slice_count = total_minutes // crontab_interval_minutes
                slice_count = max(slice_count, optimal_slice_count)
                slice_interval_minutes = total_minutes // slice_count
            else:
                # crontab 주기에 맞춰 최적 간격 설정 (25분 - 5분 여유)
                slice_interval_minutes = min(base_interval, crontab_interval_minutes - 5)
                # 조정된 간격으로 슬라이스 수 재계산
                optimal_slice_count = total_minutes // slice_interval_minutes
                slice_count = max(slice_count, optimal_slice_count)
            
            logger.info(f"TWAP 실행 파라미터 최적화: {slice_count}개 슬라이스, {slice_interval_minutes}분 간격 (crontab 주기: {crontab_interval_minutes}분)")
            
            # 3. TWAP 주문 생성
            twap_orders = []
            immediate_orders = []  # 즉시 실행할 소액 주문들
            start_time = datetime.now()
            end_time = start_time + timedelta(hours=execution_hours)
            
            for asset, order_info in rebalance_orders.items():
                # KRW는 건너뜀 (기본 통화)
                if asset.upper() == "KRW":
                    continue
                
                amount_krw = abs(order_info["amount_diff_krw"])
                
                # 현재가 조회하여 수량 계산 (먼저 처리)
                try:
                    ticker = self.coinone_client.get_ticker(asset)
                    logger.debug(f"{asset} ticker 응답 타입: {type(ticker)}, 내용: {ticker}")
                    
                    # ticker가 딕셔너리가 아닌 경우 처리
                    if not isinstance(ticker, dict):
                        logger.error(f"{asset} ticker 응답이 딕셔너리가 아님: {type(ticker)}")
                        continue
                    
                    # 코인원 API 응답에서 현재가 추출 (여러 필드 시도)
                    ticker_data = ticker.get("data", {})
                    if not isinstance(ticker_data, dict):
                        logger.error(f"{asset} ticker data가 딕셔너리가 아님: {type(ticker_data)}")
                        continue
                    
                    current_price = (
                        float(ticker_data.get("last", 0)) or
                        float(ticker_data.get("close_24h", 0)) or
                        float(ticker_data.get("close", 0))
                    )
                    
                    if current_price <= 0:
                        logger.error(f"{asset}: 현재가 조회 실패 - ticker_data: {ticker_data}")
                        continue
                    
                    quantity = amount_krw / current_price
                    logger.info(f"{asset} 현재가: {current_price:,.0f} KRW, 주문량: {quantity:.6f}")
                    
                except Exception as e:
                    logger.error(f"{asset}: 현재가 조회 실패 - {e}")
                    continue
                
                # 소액 주문은 즉시 실행 큐에 추가
                if amount_krw < 50000:  # 5만원 미만
                    logger.info(f"{asset}: 소액 주문({amount_krw:,.0f} KRW) 즉시 실행 큐에 추가")
                    immediate_orders.append({
                        "asset": asset,
                        "side": order_info["action"],
                        "amount_krw": amount_krw,
                        "quantity": quantity,
                        "current_price": current_price
                    })
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
            
            # 즉시 실행 주문들 처리
            if immediate_orders:
                logger.info(f"즉시 실행 주문 {len(immediate_orders)}개 처리 시작")
                for order in immediate_orders:
                    try:
                        result = self.coinone_client.place_safe_order(
                            currency=order["asset"],
                            side=order["side"],
                            amount=order["amount_krw"],
                            amount_in_krw=True,
                            max_retries=3
                        )
                        if result.get("success"):
                            logger.info(f"✅ {order['asset']} 즉시 실행 성공: {order['amount_krw']:,.0f} KRW")
                        else:
                            error_msg = result.get("error", "Unknown error")
                            error_code = result.get("error_code", "unknown")
                            logger.error(f"❌ {order['asset']} 즉시 실행 실패 ({error_code}): {error_msg}")
                    except Exception as e:
                        logger.error(f"❌ {order['asset']} 즉시 실행 중 오류: {e}")
            
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
            
            logger.info(f"TWAP 슬라이스 실행 시작: {twap_order.asset} {amount_krw:,.0f} KRW "
                       f"({twap_order.executed_slices + 1}/{twap_order.slice_count})")
            
            # 안전한 주문 실행 (잔액 확인, 한도 검증, 자동 재시도)
            order_result = self.coinone_client.place_safe_order(
                currency=twap_order.asset,
                side=twap_order.side,
                amount=amount_krw,
                amount_in_krw=True,
                max_retries=3
            )
            
            # 결과 처리
            if order_result.get("success"):
                # 실제 실행된 금액 (조정된 경우 반영)
                executed_amount = amount_krw  # TODO: 실제 체결 금액으로 업데이트
                
                twap_order.executed_slices += 1
                twap_order.remaining_amount_krw -= executed_amount
                twap_order.last_execution_time = datetime.now()
                
                if twap_order.executed_slices >= twap_order.slice_count:
                    twap_order.status = "completed"
                else:
                    twap_order.status = "executing"
                
                # 데이터베이스에 상태 업데이트
                self._save_twap_orders_to_db()
                
                logger.info(f"✅ TWAP 슬라이스 실행 성공: {twap_order.asset} "
                          f"({twap_order.executed_slices}/{twap_order.slice_count})")
                
                return {
                    "success": True,
                    "order_id": order_result.get("order_id"),
                    "amount_krw": executed_amount,
                    "executed_slices": twap_order.executed_slices,
                    "total_slices": twap_order.slice_count,
                    "remaining_amount": twap_order.remaining_amount_krw
                }
            else:
                # 주문 실패 시 처리
                twap_order.last_execution_time = datetime.now()
                error_msg = order_result.get("error", "Unknown error")
                error_code = order_result.get("error_code", "unknown")
                
                # 잔고 부족 등 치명적인 오류의 경우 주문을 실패 상태로 마킹
                if "잔고" in error_msg or "잔액" in error_msg or "insufficient" in error_msg.lower():
                    twap_order.status = "failed"
                    logger.error(f"💥 TWAP 주문 실패 - 잔고 부족: {twap_order.asset} (실행 중단)")
                    # 데이터베이스에 실패 상태 저장
                    self._save_twap_orders_to_db()
                else:
                    # 일시적인 오류의 경우 계속 재시도
                    logger.warning(f"⚠️ TWAP 슬라이스 일시 실패 (재시도 예정): {twap_order.asset} - {error_msg}")
                    # 실패 시에도 데이터베이스 업데이트 (재시도를 위해)
                    self._save_twap_orders_to_db()
                
                logger.error(f"❌ TWAP 슬라이스 실행 실패: {twap_order.asset} - {error_msg}")
                
                return {
                    "success": False,
                    "error": error_msg,
                    "error_code": error_code,
                    "asset": twap_order.asset,
                    "amount_krw": amount_krw,
                    "executed_slices": twap_order.executed_slices,
                    "total_slices": twap_order.slice_count,
                    "is_fatal": twap_order.status == "failed"
                }
                
        except Exception as e:
            logger.error(f"TWAP 슬라이스 실행 중 오류: {e}")
            return {
                "success": False,
                "error": str(e),
                "asset": twap_order.asset
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
            # 기존 활성 TWAP 주문들 정리 (새로운 실행 시작 전)
            if self.active_twap_orders:
                logger.warning(f"새로운 TWAP 실행 시작 - 기존 활성 주문 {len(self.active_twap_orders)}개 정리")
                completed_orders = [order for order in self.active_twap_orders if order.status == "completed"]
                pending_orders = [order for order in self.active_twap_orders if order.status in ["pending", "executing"]]
                
                if completed_orders:
                    logger.info(f"완료된 주문 {len(completed_orders)}개 제거")
                    
                if pending_orders:
                    logger.warning(f"미완료 주문 {len(pending_orders)}개 강제 정리 - 새로운 리밸런싱 시작")
                    for order in pending_orders:
                        logger.warning(f"  - {order.asset}: {order.executed_slices}/{order.slice_count} 슬라이스 (강제 중단)")
                
                # 기존 실행을 완료로 마킹
                if self.current_execution_id:
                    try:
                        self.db_manager.update_twap_orders_status(self.current_execution_id, self.active_twap_orders)
                    except Exception as e:
                        logger.error(f"기존 TWAP 실행 상태 업데이트 실패: {e}")
                
                # 활성 주문 리스트 초기화
                self.active_twap_orders = []
                self.current_execution_id = None
                
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
            
            # 3. 활성 TWAP 주문에 추가 (이제 빈 리스트에 추가)
            self.active_twap_orders.extend(twap_orders)
            
            # 4. 첫 번째 슬라이스 즉시 실행
            immediate_results = []
            for twap_order in twap_orders:
                logger.info(f"첫 번째 TWAP 슬라이스 즉시 실행: {twap_order.asset}")
                result = self.execute_twap_slice(twap_order)
                immediate_results.append({
                    "asset": twap_order.asset,
                    "result": result,
                    "slice": f"1/{twap_order.slice_count}"
                })
            
            # 5. 실행 계획 생성 및 데이터베이스에 저장
            execution_plan = {
                "start_time": datetime.now(),
                "twap_orders": len(twap_orders),
                "total_execution_hours": twap_orders[0].execution_hours if twap_orders else 0,
                "slice_interval_minutes": twap_orders[0].slice_interval_minutes if twap_orders else 0,
                "immediate_results": immediate_results
            }
            
            # 데이터베이스에 TWAP 주문 정보와 함께 저장
            self.current_execution_id = self.db_manager.save_twap_execution_plan(execution_plan, twap_orders)
            
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
            self._save_twap_orders_to_db()

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