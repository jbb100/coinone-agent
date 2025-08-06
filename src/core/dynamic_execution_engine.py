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
from ..trading.order_manager import OrderStatus
from ..utils.database_manager import DatabaseManager
from ..utils.constants import MIN_ORDER_AMOUNTS_KRW


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
        alert_system=None,  # Add alert_system parameter
        atr_period: int = 14,
        atr_threshold: float = 0.05
    ):
        """
        Args:
            coinone_client: 코인원 API 클라이언트
            db_manager: 데이터베이스 매니저
            rebalancer: 리밸런서 인스턴스 (선택적)
            alert_system: 알림 시스템 인스턴스 (선택적)
            atr_period: ATR 계산 기간 (기본값: 14일)
            atr_threshold: 변동성 임계값 (기본값: 5%)
        """
        self.coinone_client = coinone_client
        self.db_manager = db_manager
        self.rebalancer = rebalancer  # Store rebalancer instance
        self.alert_system = alert_system  # Store alert_system instance
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
            active_execution = self.db_manager.get_latest_active_twap_execution()
            
            if active_execution:
                self.current_execution_id = active_execution["execution_id"]
                orders_detail = active_execution["twap_orders_detail"]
                
                # 상세 정보를 TWAPOrder 객체로 변환
                loaded_orders = []
                for order_data in orders_detail:
                    # 'status'가 'completed'가 아닌 주문만 로드
                    if order_data.get("status") != "completed":
                        # datetime 필드 변환
                        for field in ['start_time', 'end_time', 'last_execution_time', 'created_at']:
                            if order_data.get(field):
                                order_data[field] = datetime.fromisoformat(order_data[field])
                        
                        loaded_orders.append(TWAPOrder(**order_data))

                self.active_twap_orders = loaded_orders
                logger.info(f"활성 TWAP 실행 복원: {self.current_execution_id} ({len(self.active_twap_orders)}개 주문)")
            else:
                logger.info("현재 활성 TWAP 실행이 없습니다.")
                self.active_twap_orders = []
                self.current_execution_id = None

        except Exception as e:
            logger.error(f"활성 TWAP 주문 로드 실패: {e}")
            self.active_twap_orders = []
            self.current_execution_id = None
    
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
            # 상수 정의
            MIN_ORDER_KRW = 1000  # 코인원 최소 주문 금액 (KRW)
            MIN_ORDER_KRW_BUFFER = 1.05  # 5% 안전 마진
            
            # 코인원 거래소 제한사항
            COINONE_MAX_ORDER_AMOUNT_KRW = 500_000_000  # 500M KRW - 코인원 최대 주문 금액
            COINONE_SAFE_ORDER_LIMIT_KRW = 200_000_000  # 200M KRW - 안전한 주문 금액 한도
            MAX_SLICES_PER_ORDER = 24  # 최대 슬라이스 개수

            # 암호화폐별 최소 주문 수량 (코인원 기준)
            MIN_ORDER_QUANTITIES = {
                "BTC": 0.0001,      # 최소 0.0001 BTC
                "ETH": 0.0001,      # 최소 0.0001 ETH  
                "XRP": 1.0,         # 최소 1 XRP
                "SOL": 0.01,        # 최소 0.01 SOL
                "ADA": 2.0,         # 최소 2 ADA
                "DOT": 1.0,         # 최소 1 DOT
                "DOGE": 10.0,       # 최소 10 DOGE
                "TRX": 10.0,        # 최소 10 TRX
                "XLM": 10.0,        # 최소 10 XLM
                "ATOM": 0.2,        # 최소 0.2 ATOM
                "ALGO": 5.0,        # 최소 5 ALGO
                "VET": 50.0,        # 최소 50 VET
            }

            # 최소 주문 금액을 만족하는 KRW 기준 최소 금액 (각 암호화폐별)
            # 이 값들은 현재가 × 최소 수량으로 동적 계산될 예정

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
                # KRW 주문은 생성하지 않음
                if asset == "KRW":
                    continue

                amount_krw = order_info.get("amount_diff_krw", 0)
                
                # 최소 주문 금액 체크 (1만원)
                if abs(amount_krw) < 10000:
                    logger.info(f"{asset} 주문 금액이 너무 작음: {amount_krw:,.0f} KRW - 건너뜀")
                    continue
                
                # 주문 방향 결정
                side = "buy" if amount_krw > 0 else "sell"
                amount_krw = abs(amount_krw)
                
                # 매수/매도 모두 금액(KRW) 기준으로 주문하므로 수량은 0으로 설정
                quantity = 0

                # 암호화폐별 최소 주문 수량을 고려한 슬라이스 횟수 조정
                local_slice_count = slice_count
                slice_amount = amount_krw / local_slice_count
                
                # 1. 기본 KRW 최소 금액 검증
                min_krw_amount = MIN_ORDER_KRW * MIN_ORDER_KRW_BUFFER
                
                # 2. 암호화폐별 최소 수량을 고려한 최소 KRW 금액 계산
                if asset in MIN_ORDER_QUANTITIES and side == "sell":
                    try:
                        # 현재가 조회하여 최소 수량에 해당하는 KRW 금액 계산
                        current_price = self.coinone_client.get_latest_price(asset)
                        if current_price > 0:
                            min_quantity_krw = MIN_ORDER_QUANTITIES[asset] * current_price
                            min_krw_amount = max(min_krw_amount, min_quantity_krw * 1.1)  # 10% 안전 마진
                            logger.info(f"{asset} 최소 수량 검증: {MIN_ORDER_QUANTITIES[asset]} {asset} = {min_quantity_krw:,.0f} KRW (현재가: {current_price:,.0f})")
                    except Exception as e:
                        logger.warning(f"{asset} 현재가 조회 실패, 기본 최소 금액 사용: {e}")

                if slice_amount < min_krw_amount:
                    new_slice_count = math.floor(amount_krw / min_krw_amount)
                    if new_slice_count > 0:
                        logger.warning(
                            f"{asset}: 슬라이스당 주문 금액({slice_amount:,.0f} KRW)이 최소 금액({min_krw_amount:,.0f} KRW)보다 작아 "
                            f"분할 횟수 조정: {local_slice_count} -> {new_slice_count}"
                        )
                        local_slice_count = new_slice_count
                    else:
                        # 총 주문 금액이 최소 주문 금액보다 작은 경우
                        logger.warning(f"{asset}: 총 주문 금액({amount_krw:,.0f} KRW)이 최소 금액({min_krw_amount:,.0f} KRW)보다 작아 주문을 건너뜁니다.")
                        continue
                
                # 조정된 슬라이스 횟수로 슬라이스당 금액/수량 재계산
                slice_amount = amount_krw / local_slice_count
                slice_quantity = 0
                
                # 슬라이스당 금액이 코인원 최대 주문 한도를 초과하는지 검증
                if slice_amount > COINONE_SAFE_ORDER_LIMIT_KRW:
                    # 안전한 주문 크기로 슬라이스 횟수 재조정
                    required_slices = math.ceil(amount_krw / COINONE_SAFE_ORDER_LIMIT_KRW)
                    logger.warning(
                        f"{asset}: 슬라이스당 주문 금액({slice_amount:,.0f} KRW)이 안전 한도({COINONE_SAFE_ORDER_LIMIT_KRW:,.0f} KRW) 초과. "
                        f"분할 횟수 증가: {local_slice_count} -> {required_slices}"
                    )
                    local_slice_count = min(required_slices, MAX_SLICES_PER_ORDER)  # MAX_SLICES_PER_ORDER는 24
                    slice_amount = amount_krw / local_slice_count
                    
                    # 그래도 초과하는 경우 경고
                    if slice_amount > COINONE_SAFE_ORDER_LIMIT_KRW:
                        logger.error(
                            f"{asset}: 최대 분할 후에도 슬라이스당 금액({slice_amount:,.0f} KRW)이 "
                            f"안전 한도({COINONE_SAFE_ORDER_LIMIT_KRW:,.0f} KRW) 초과. 위험한 주문일 수 있음!"
                        )
                
                # TWAP 주문 생성
                twap_order = TWAPOrder(
                    asset=asset,
                    side=side,
                    total_amount_krw=amount_krw,
                    total_quantity=quantity,
                    execution_hours=execution_hours,
                    slice_count=local_slice_count,
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
                          f"({local_slice_count}회 분할, {slice_interval_minutes}분 간격)")
            
            return twap_orders
            
        except Exception as e:
            logger.error(f"TWAP 주문 생성 실패: {e}")
            return []
    
    def execute_twap_slice(self, order: TWAPOrder) -> Dict:
        """
        TWAP 주문의 한 슬라이스 실행
        
        Args:
            order: TWAP 주문 정보
            
        Returns:
            실행 결과
        """
        try:
            # 1. 포트폴리오 상태 확인
            portfolio = self.coinone_client.get_portfolio_value()
            portfolio_metrics = self.rebalancer.portfolio_manager.get_portfolio_metrics(portfolio)
            
            # 주문 실행 전 잔고 확인
            if order.side == "buy":
                balance = self.coinone_client.get_balances().get("KRW", 0)
                if balance < order.slice_amount_krw:
                    # KRW 비율 확인
                    total_value = portfolio.get("total_krw", 0)
                    krw_ratio = balance / total_value if total_value > 0 else 0
                    
                    # KRW 비율이 2% 미만이면 리밸런싱 필요
                    if krw_ratio < 0.02:
                        logger.warning(f"KRW 비율 심각하게 낮음 ({krw_ratio:.1%}) - 리밸런싱 필요")
                        return {
                            "success": False,
                            "error": "krw_ratio_too_low",
                            "message": "KRW 비율이 너무 낮아 리밸런싱이 필요합니다",
                            "current_ratio": krw_ratio
                        }
                    
                    # KRW가 있지만 부족한 경우 주문 크기 조정
                    min_amount_krw = MIN_ORDER_AMOUNTS_KRW.get(order.asset.upper(), 5000)
                    adjusted_amount = min(balance * 0.99, order.slice_amount_krw)  # 1% 마진
                    if adjusted_amount >= min_amount_krw:  # 최소 주문 금액 확인
                        logger.warning(f"잔고 부족으로 주문 크기 조정: {order.slice_amount_krw:,.0f} → {adjusted_amount:,.0f} KRW")
                        order.slice_amount_krw = adjusted_amount
                    else:
                        logger.error(f"💥 TWAP 주문 실패 - 잔고 부족: {order.asset} (조정된 금액 {adjusted_amount:,.0f} KRW < 최소 금액 {min_amount_krw:,.0f} KRW)")
                        return {
                            "success": False,
                            "error": "insufficient_balance",
                            "message": f"KRW 잔고가 최소 주문 금액({min_amount_krw:,.0f} KRW)보다 작습니다"
                        }
            
            else:  # sell
                # 매도 주문 준비: 현재가와 필요 수량 미리 계산
                pass
            
            # 주문 실행 전 최대 주문 금액 검증 및 조정
            COINONE_SAFE_ORDER_LIMIT_KRW = 200_000_000  # 200M KRW 안전 한도
            
            if order.slice_amount_krw > COINONE_SAFE_ORDER_LIMIT_KRW:
                logger.warning(f"⚠️ 슬라이스 금액({order.slice_amount_krw:,.0f} KRW)이 안전 한도({COINONE_SAFE_ORDER_LIMIT_KRW:,.0f} KRW) 초과!")
                logger.info(f"🔄 주문 크기를 안전 한도로 조정: {order.slice_amount_krw:,.0f} → {COINONE_SAFE_ORDER_LIMIT_KRW:,.0f} KRW")
                
                # 초과 금액을 다음 슬라이스들에 분배
                excess_amount = order.slice_amount_krw - COINONE_SAFE_ORDER_LIMIT_KRW
                remaining_slices = order.slice_count - order.executed_slices - 1  # 현재 슬라이스 제외
                
                if remaining_slices > 0:
                    additional_per_slice = excess_amount / remaining_slices
                    logger.info(f"📈 초과 금액 {excess_amount:,.0f} KRW을 남은 {remaining_slices}개 슬라이스에 {additional_per_slice:,.0f} KRW씩 분배")
                    # Note: 실제 분배는 다음 슬라이스 실행 시 동적으로 처리
                else:
                    logger.warning(f"⚠️ 남은 슬라이스가 없어 {excess_amount:,.0f} KRW 손실 발생 가능")
                
                # 현재 슬라이스를 안전 한도로 제한
                order.slice_amount_krw = COINONE_SAFE_ORDER_LIMIT_KRW
            
            # 주문 실행
            if order.side == "buy":
                # 매수: KRW 금액으로 주문  
                amount = order.slice_amount_krw
                
                # 최종 안전 검증: 절대로 200M KRW를 초과하는 주문은 보내지 않음
                if amount > COINONE_SAFE_ORDER_LIMIT_KRW:
                    logger.error(f"🚨 긴급 차단: 주문 금액({amount:,.0f} KRW)이 안전 한도 초과! 주문을 {COINONE_SAFE_ORDER_LIMIT_KRW:,.0f} KRW로 강제 제한")
                    amount = COINONE_SAFE_ORDER_LIMIT_KRW
                    order.slice_amount_krw = COINONE_SAFE_ORDER_LIMIT_KRW  # 주문 객체도 업데이트
            else:
                # 매도: 코인 수량으로 주문 (KRW 금액을 현재가로 나누어 계산)
                try:
                    current_price = self.coinone_client.get_latest_price(order.asset)
                    if current_price <= 0:
                        logger.error(f"💥 {order.asset} 현재가 조회 실패: {current_price}")
                        return {
                            "success": False,
                            "error": f"현재가 조회 실패: {current_price}"
                        }
                    
                    # 매도 주문도 안전 한도 검증
                    if order.slice_amount_krw > COINONE_SAFE_ORDER_LIMIT_KRW:
                        logger.error(f"🚨 긴급 차단: 매도 주문 금액({order.slice_amount_krw:,.0f} KRW)이 안전 한도 초과! 주문을 {COINONE_SAFE_ORDER_LIMIT_KRW:,.0f} KRW로 강제 제한")
                        order.slice_amount_krw = COINONE_SAFE_ORDER_LIMIT_KRW
                    
                    # KRW 금액을 현재가로 나누어 매도할 수량 계산
                    calculated_quantity = order.slice_amount_krw / current_price
                    
                    # 잔고 확인하여 안전한 수량으로 조정
                    balance = self.coinone_client.get_balances().get(order.asset, 0)
                    
                    # 충분한 잔고가 있는지 먼저 확인
                    if balance < calculated_quantity:
                        logger.error(f"💥 TWAP 주문 실패 - 잔고 부족: {order.asset} (필요: {calculated_quantity:.8f}, 보유: {balance:.8f})")
                        return {
                            "success": False,
                            "error": "insufficient_balance",
                            "message": f"{order.asset} 잔고가 부족합니다 (필요: {calculated_quantity:.8f}, 보유: {balance:.8f})"
                        }
                    
                    # 안전한 수량으로 조정 (수수료 고려)
                    safe_quantity = min(calculated_quantity, balance * 0.99)  # 99%만 매도
                    
                    # 거래소 주문 한도 적용 (최소/최대)
                    min_order_quantities = {
                        "BTC": 0.0001,    # 최소 0.0001 BTC
                        "ETH": 0.001,     # 최소 0.001 ETH  
                        "XRP": 1.0,       # 최소 1 XRP
                        "SOL": 0.01,      # 최소 0.01 SOL
                        "ADA": 2.0,       # 최소 2 ADA
                        "DOT": 1.0,       # 최소 1 DOT
                        "DOGE": 10.0,     # 최소 10 DOGE
                        "TRX": 10.0,      # 최소 10 TRX
                        "XLM": 10.0,      # 최소 10 XLM
                        "ATOM": 0.2,      # 최소 0.2 ATOM
                        "ALGO": 5.0,      # 최소 5 ALGO
                        "VET": 50.0,      # 최소 50 VET
                    }
                    
                    max_order_limits = {
                        "BTC": 10.0,      # 최대 10 BTC
                        "ETH": 100.0,     # 최대 100 ETH
                        "XRP": 100000.0,  # 최대 100,000 XRP
                        "SOL": 1000.0,    # 최대 1,000 SOL
                        "ADA": 100000.0,  # 최대 100,000 ADA
                        "DOT": 5000.0,    # 최대 5,000 DOT
                        "DOGE": 1000000.0,# 최대 1,000,000 DOGE
                        "TRX": 1000000.0, # 최대 1,000,000 TRX
                        "XLM": 100000.0,  # 최대 100,000 XLM
                        "ATOM": 10000.0,  # 최대 10,000 ATOM
                        "ALGO": 100000.0, # 최대 100,000 ALGO
                        "VET": 1000000.0, # 최대 1,000,000 VET
                    }
                    
                    # 최소 주문량 검증 및 처리
                    min_limit = min_order_quantities.get(order.asset, 0.0001)  # 기본값: 0.0001
                    if safe_quantity < min_limit:
                        # 남은 슬라이스 수가 1개일 때는 최소량으로 강제 조정
                        remaining_slices = order.slice_count - order.executed_slices
                        if remaining_slices <= 1:
                            # 마지막 슬라이스: 최소량 또는 전체 잔고 중 작은 값으로 설정
                            safe_quantity = min(min_limit, balance * 0.99)
                            logger.info(f"{order.asset} 마지막 슬라이스: 최소량으로 조정 {safe_quantity:.8f}")
                        else:
                            # 중간 슬라이스: 건너뛰고 다음 슬라이스와 합치기
                            logger.warning(f"{order.asset} 주문량이 최소 한도 미달: {safe_quantity:.8f} < {min_limit:.8f} - 다음 슬라이스와 합치기")
                            
                            # 현재 슬라이스를 실행한 것으로 표시하되 실제 거래는 하지 않음
                            order.executed_slices += 1
                            order.last_execution_time = datetime.now()
                            
                            # 다음 슬라이스 크기를 늘리기 위해 슬라이스 수량 조정
                            if remaining_slices > 1:
                                # 남은 슬라이스들에 현재 슬라이스 분량을 분배
                                additional_quantity_per_slice = order.slice_quantity / (remaining_slices - 1)
                                order.slice_quantity += additional_quantity_per_slice
                                
                                additional_amount_per_slice = order.slice_amount_krw / (remaining_slices - 1)
                                order.slice_amount_krw += additional_amount_per_slice
                                
                                logger.info(f"{order.asset} 다음 슬라이스 크기 증가: {order.slice_quantity:.8f} {order.asset}, {order.slice_amount_krw:,.0f} KRW")
                            
                            return {
                                "success": True,
                                "skipped": True,
                                "message": f"{order.asset} 최소량 미달로 다음 슬라이스와 합침",
                                "executed_slices": order.executed_slices,
                                "remaining_slices": remaining_slices - 1
                            }
                    
                    # 최대 주문량 검증
                    max_limit = max_order_limits.get(order.asset, 1.0)  # 기본값: 1개
                    if safe_quantity > max_limit:
                        logger.warning(f"{order.asset} 주문량이 최대 한도 초과: {safe_quantity:.8f} → {max_limit:.8f}")
                        safe_quantity = max_limit
                    
                    amount = safe_quantity
                    
                    logger.info(f"{order.asset} 매도 수량 계산:")
                    logger.info(f"  • 슬라이스 금액: {order.slice_amount_krw:,.0f} KRW")
                    logger.info(f"  • 현재가: {current_price:,.0f} KRW")
                    logger.info(f"  • 계산된 수량: {calculated_quantity:.8f} {order.asset}")
                    logger.info(f"  • 보유 잔고: {balance:.8f} {order.asset}")
                    logger.info(f"  • 최종 주문량: {amount:.8f} {order.asset}")
                    
                except Exception as e:
                    logger.error(f"💥 {order.asset} 매도 수량 계산 실패: {e}")
                    return {
                        "success": False,
                        "error": f"매도 수량 계산 실패: {e}"
                    }
            
            order_result_obj = self.rebalancer.order_manager.submit_market_order(
                currency=order.asset,
                side=order.side,
                amount=amount
            )
            
            # Order 객체를 딕셔너리로 변환
            if order_result_obj:
                order_result = {
                    "success": order_result_obj.status != OrderStatus.FAILED,
                    "order_id": order_result_obj.order_id,
                    "status": order_result_obj.status.value,
                    "error": order_result_obj.error_message if order_result_obj.status == OrderStatus.FAILED else None
                }
            else:
                order_result = {
                    "success": False,
                    "error": "Order submission returned None"
                }

            # 건너뛴 슬라이스인 경우 (최소량 미달로 다음과 합침)
            if order_result.get("skipped"):
                # 모든 슬라이스가 완료되었는지 확인 (건너뛴 것도 실행으로 간주)
                if order.executed_slices >= order.slice_count:
                    order.status = "completed"
                    logger.info(f"🎉 TWAP 주문 완료: {order.asset} ({order.executed_slices}/{order.slice_count} 슬라이스)")
                else:
                    order.status = "executing"
                
                return {
                    "success": True,
                    "skipped": True,
                    "message": order_result.get("message"),
                    "executed_slices": order.executed_slices,
                    "remaining_slices": order.slice_count - order.executed_slices
                }
            
            if order_result.get("success"):
                # 주문 ID 저장
                order.exchange_order_ids.append(order_result.get("order_id"))
                order.executed_slices += 1
                order.last_execution_time = datetime.now()
                
                # 남은 수량 업데이트 (매수/매도 모두 KRW 기준으로 추적)
                order.remaining_amount_krw -= order.slice_amount_krw
                
                # 모든 슬라이스가 완료되었는지 확인
                if order.executed_slices >= order.slice_count:
                    order.status = "completed"
                    logger.info(f"🎉 TWAP 주문 완료: {order.asset} ({order.executed_slices}/{order.slice_count} 슬라이스)")
                else:
                    order.status = "executing"
                    logger.info(f"✅ TWAP 슬라이스 실행 성공: {order.asset} "
                              f"({order.executed_slices}/{order.slice_count})")
                
                return {
                    "success": True,
                    "order_id": order_result.get("order_id"),
                    "executed_slices": order.executed_slices,
                    "remaining_slices": order.slice_count - order.executed_slices
                }
            else:
                error_msg = order_result.get('error', 'Unknown error')
                logger.error(f"💥 TWAP 주문 실패: {error_msg}")
                
                # 특정 오류의 경우 주문을 실패로 마킹하지 않고 다음 슬라이스를 시도
                retryable_errors = [
                    "Cannot be process the orders exceed the maximum amount",
                    "Cannot be process the orders below the minimum amount", 
                    "order_too_small",
                    "Insufficient balance",
                    "Market temporarily unavailable"
                ]
                
                is_retryable = any(err.lower() in error_msg.lower() for err in retryable_errors)
                error_code = order_result.get('error_code', '')
                
                # 최소 주문 금액 미만 오류 (306)에 대한 특별 처리  
                if error_code == '306' or "below the minimum amount" in error_msg:
                    logger.warning(f"💰 최소 주문 금액 미만 감지 - 남은 전체 금액을 한 번에 주문: {order.asset}")
                    
                    # 남은 전체 금액으로 한 번에 주문 시도
                    total_remaining_amount = order.remaining_amount_krw
                    logger.info(f"🔄 슬라이싱 없이 남은 전체 금액으로 주문: {total_remaining_amount:,.0f} KRW")
                    
                    # 전체 남은 금액으로 주문 제출
                    full_order_result_obj = self.rebalancer.order_manager.submit_market_order(
                        currency=order.asset,
                        side=order.side,
                        amount=total_remaining_amount
                    )
                    
                    # Order 객체를 딕셔너리로 변환
                    if full_order_result_obj:
                        full_order_result = {
                            "success": full_order_result_obj.status != OrderStatus.FAILED,
                            "order_id": full_order_result_obj.order_id,
                            "status": full_order_result_obj.status.value,
                            "error": full_order_result_obj.error_message if full_order_result_obj.status == OrderStatus.FAILED else None
                        }
                    else:
                        full_order_result = {
                            "success": False,
                            "error": "Order submission returned None"
                        }
                    
                    if full_order_result.get("success"):
                        # 전체 주문 성공시 TWAP 완료 처리
                        order.exchange_order_ids.append(full_order_result.get("order_id"))
                        order.executed_slices = order.slice_count  # 모든 슬라이스 완료로 처리
                        order.remaining_amount_krw = 0
                        order.status = "completed"
                        order.last_execution_time = datetime.now()
                        
                        logger.info(f"✅ 전체 주문 성공으로 TWAP 완료: {order.asset}")
                        return {
                            "success": True,
                            "order_id": full_order_result.get("order_id"),
                            "executed_slices": order.executed_slices,
                            "remaining_slices": 0,
                            "full_amount_executed": True
                        }
                    else:
                        logger.error(f"💥 전체 금액 주문도 실패: {full_order_result.get('error')}")
                        order.status = "failed"
                        return full_order_result
                
                # 최대 주문 금액 초과 오류 (307)에 대한 특별 처리
                elif error_code == '307' or "exceed the maximum amount" in error_msg:
                    logger.warning(f"🔄 최대 주문 금액 초과 오류 감지 - 슬라이스 크기 동적 조정: {order.asset}")
                    
                    # 현재 슬라이스 크기를 50% 감소
                    original_amount = order.slice_amount_krw
                    order.slice_amount_krw = order.slice_amount_krw * 0.5
                    
                    # 남은 슬라이스에 추가 금액 분배
                    remaining_slices = order.slice_count - order.executed_slices
                    if remaining_slices > 1:
                        additional_amount_per_slice = (original_amount - order.slice_amount_krw) / (remaining_slices - 1)
                        logger.info(f"📊 슬라이스 크기 조정: {original_amount:,.0f} → {order.slice_amount_krw:,.0f} KRW")
                        logger.info(f"📈 남은 {remaining_slices-1}개 슬라이스에 {additional_amount_per_slice:,.0f} KRW씩 분배")
                    
                    # 조정된 크기로 재시도하지 않고 다음 슬라이스에서 처리
                    return order_result
                
                elif is_retryable:
                    logger.warning(f"⚠️ 일시적 오류로 판단, 다음 슬라이스에서 재시도: {order.asset}")
                    # 주문 상태는 변경하지 않고 오류만 반환
                    return order_result
                else:
                    # 복구 불가능한 오류의 경우 주문을 실패로 마킹
                    order.status = "failed"
                    logger.error(f"💥 복구 불가능한 오류로 TWAP 주문 실패: {order.asset}")
                    return order_result
            
        except Exception as e:
            logger.error(f"TWAP 슬라이스 실행 중 오류: {e}")
            return {
                "success": False,
                "error": str(e)
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
                    orders_to_update = [order.to_dict() for order in self.active_twap_orders if order.status in ["pending", "executing"]]
                    if orders_to_update:
                        self.db_manager.update_twap_orders_status(self.current_execution_id, orders_to_update)
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
            try:
                orders_to_save = [o.to_dict() for o in self.active_twap_orders]
                self.db_manager.update_twap_execution_plan(self.current_execution_id, orders_to_save)
            except Exception as e:
                logger.error(f"TWAP 주문 상태 DB 업데이트 실패: {e}")

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
        시장 상황 변화 체크
        
        시장 계절 변화와 포트폴리오 밸런스를 체크하여 
        리밸런싱이 필요한지 판단합니다.
        
        Returns:
            시장 상황 변화 여부
        """
        try:
            # 현재 시장 상황 조회
            current_market_season, current_allocation = self._get_current_market_condition()
            
            # 포트폴리오 건전성 체크
            portfolio_metrics = self.rebalancer.portfolio_manager.get_portfolio_metrics(
                self.coinone_client.get_portfolio_value()
            )
            is_balanced = portfolio_metrics["portfolio_health"]["is_balanced"]
            
            for twap_order in self.active_twap_orders:
                # 시장 계절 변화 체크
                if current_market_season != twap_order.market_season:
                    logger.warning(f"시장 계절 변화 감지: {twap_order.market_season} -> {current_market_season}")
                    return True
                
                # 포트폴리오 밸런스 체크
                if not is_balanced:
                    current_crypto_weight = portfolio_metrics["weights"]["crypto_total"]
                    target_crypto_weight = twap_order.target_allocation.get("crypto", 0.5)
                    weight_diff = abs(current_crypto_weight - target_crypto_weight)
                    
                    # 5% 이상 차이나면 리밸런싱 필요
                    if weight_diff > 0.05:
                        logger.warning(
                            f"포트폴리오 밸런스 깨짐 감지: "
                            f"현재 암호화폐 비중 {current_crypto_weight:.1%}, "
                            f"목표 비중 {target_crypto_weight:.1%}"
                        )
                        return True
            
            return False
            
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
                            if order_status in ["filled", "cancelled", "not_found"]:
                                logger.info(f"주문 {order_id} 이미 {order_status} 상태 - 취소 건너뜀")
                                cancelled_count += 1  # 이미 완료된 주문으로 간주
                                cancelled_orders.append({
                                    "order_id": order_id,
                                    "asset": twap_order.asset,
                                    "status": order_status
                                })
                                continue
                        
                        # 주문 취소 실행
                        cancel_response = self.coinone_client.cancel_order(order_id)
                        
                        if cancel_response.get("result") == "success":
                            cancel_status = cancel_response.get("status", "cancelled")
                            
                            if cancel_status == "not_found":
                                # 주문이 이미 완료되었거나 존재하지 않음
                                logger.info(f"✅ 주문 {order_id} 이미 완료됨 (찾을 수 없음)")
                            else:
                                logger.info(f"✅ 주문 취소 성공: {order_id}")
                            
                            cancelled_count += 1
                            cancelled_orders.append({
                                "order_id": order_id,
                                "asset": twap_order.asset,
                                "status": cancel_status
                            })
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

 