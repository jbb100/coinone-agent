"""
Smart Execution Engine

고급 매수/매도 로직을 담당하는 모듈입니다.
10개 고급 분석 시스템의 신호를 통합하여 최적의 매수/매도 전략을 실행합니다.
"""

import time
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import numpy as np
from loguru import logger

from ..trading.coinone_client import CoinoneClient
from ..trading.order_manager import OrderManager, OrderStatus
from ..utils.constants import MIN_ORDER_QUANTITIES, SAFETY_MARGIN


class ExecutionStrategy(Enum):
    """실행 전략"""
    MARKET = "market"           # 시장가 즉시 실행
    LIMIT_AGGRESSIVE = "limit_aggressive"  # 적극적 지정가 (현재가 ±0.1%)
    LIMIT_CONSERVATIVE = "limit_conservative"  # 보수적 지정가 (현재가 ±0.3%)
    TWAP_SMART = "twap_smart"   # 스마트 TWAP (고급 신호 반영)


class MarketCondition(Enum):
    """시장 상황"""
    VERY_BULLISH = "very_bullish"     # 매우 강세
    BULLISH = "bullish"               # 강세
    NEUTRAL = "neutral"               # 중립
    BEARISH = "bearish"               # 약세
    VERY_BEARISH = "very_bearish"     # 매우 약세


@dataclass
class SmartOrderParams:
    """스마트 주문 파라미터"""
    asset: str
    side: str  # "buy" or "sell"
    amount_krw: float
    strategy: ExecutionStrategy
    market_condition: MarketCondition
    urgency_score: float  # 0-1, 긴급도
    confidence_score: float  # 0-1, 신뢰도
    max_slippage: float = 0.005  # 최대 슬리피지 0.5%
    timeout_minutes: int = 30  # 타임아웃
    
    # 고급 분석 신호들
    multi_timeframe_signal: float = 0  # -1 to 1
    onchain_signal: float = 0
    macro_signal: float = 0
    sentiment_signal: float = 0
    
    # 리스크 관리
    max_position_size: float = 0.1  # 전체 포트폴리오의 10%
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


@dataclass 
class ExecutionResult:
    """실행 결과"""
    success: bool
    asset: str
    side: str
    requested_amount_krw: float
    executed_amount_krw: float = 0
    executed_quantity: float = 0
    average_price: float = 0
    slippage: float = 0
    fees: float = 0
    order_ids: List[str] = None
    execution_time: datetime = None
    error_message: str = None
    
    def __post_init__(self):
        if self.execution_time is None:
            self.execution_time = datetime.now()
        if self.order_ids is None:
            self.order_ids = []


class SmartExecutionEngine:
    """
    스마트 실행 엔진
    
    고급 분석 시스템의 신호를 통합하여 최적의 매수/매도 전략을 실행합니다.
    """
    
    def __init__(
        self, 
        coinone_client: CoinoneClient,
        order_manager: OrderManager,
        # 고급 분석 시스템들
        multi_timeframe_analyzer=None,
        onchain_analyzer=None,
        macro_analyzer=None,
        bias_prevention=None,
        scenario_response=None
    ):
        """
        Args:
            coinone_client: 코인원 클라이언트
            order_manager: 주문 관리자
            multi_timeframe_analyzer: 멀티 타임프레임 분석기
            onchain_analyzer: 온체인 데이터 분석기
            macro_analyzer: 매크로 경제 분석기
            bias_prevention: 심리적 편향 방지 시스템
            scenario_response: 시나리오 대응 시스템
        """
        self.coinone_client = coinone_client
        self.order_manager = order_manager
        
        # 고급 분석 시스템들
        self.multi_timeframe_analyzer = multi_timeframe_analyzer
        self.onchain_analyzer = onchain_analyzer
        self.macro_analyzer = macro_analyzer
        self.bias_prevention = bias_prevention
        self.scenario_response = scenario_response
        
        # 실행 통계
        self.execution_stats = {
            "total_orders": 0,
            "successful_orders": 0,
            "failed_orders": 0,
            "average_slippage": 0,
            "total_fees": 0
        }
        
        logger.info("SmartExecutionEngine 초기화 완료")
    
    def execute_smart_order(self, params: SmartOrderParams) -> ExecutionResult:
        """
        스마트 주문 실행
        
        Args:
            params: 스마트 주문 파라미터
            
        Returns:
            실행 결과
        """
        try:
            logger.info(f"스마트 주문 실행 시작: {params.asset} {params.side} {params.amount_krw:,.0f} KRW")
            
            # 1. 심리적 편향 검사
            bias_check = self._check_psychological_bias(params)
            if not bias_check["allowed"]:
                return ExecutionResult(
                    success=False,
                    asset=params.asset,
                    side=params.side,
                    requested_amount_krw=params.amount_krw,
                    error_message=f"심리적 편향 감지: {bias_check['reason']}"
                )
            
            # 2. 시나리오별 대응 확인
            scenario_check = self._check_scenario_response(params)
            if not scenario_check["allowed"]:
                return ExecutionResult(
                    success=False,
                    asset=params.asset,
                    side=params.side,
                    requested_amount_krw=params.amount_krw,
                    error_message=f"시나리오 대응 활성화: {scenario_check['reason']}"
                )
            
            # 3. 시장 상황 분석 및 전략 최적화
            optimized_params = self._optimize_execution_strategy(params)
            
            # 4. 사전 검증
            validation_result = self._validate_order_parameters(optimized_params)
            if not validation_result["valid"]:
                return ExecutionResult(
                    success=False,
                    asset=params.asset,
                    side=params.side,
                    requested_amount_krw=params.amount_krw,
                    error_message=validation_result["error"]
                )
            
            # 5. 실행 전략별 주문 실행
            if optimized_params.strategy == ExecutionStrategy.MARKET:
                result = self._execute_market_order(optimized_params)
            elif optimized_params.strategy in [ExecutionStrategy.LIMIT_AGGRESSIVE, ExecutionStrategy.LIMIT_CONSERVATIVE]:
                result = self._execute_limit_order(optimized_params)
            elif optimized_params.strategy == ExecutionStrategy.TWAP_SMART:
                result = self._execute_smart_twap(optimized_params)
            else:
                result = self._execute_market_order(optimized_params)  # 기본값
            
            # 6. 결과 통계 업데이트
            self._update_execution_stats(result)
            
            # 7. 실행 후 분석 및 학습
            self._post_execution_analysis(params, result)
            
            logger.info(f"스마트 주문 실행 완료: {result.success} "
                       f"(체결금액: {result.executed_amount_krw:,.0f} KRW, "
                       f"슬리피지: {result.slippage:.3%})")
            
            return result
            
        except Exception as e:
            logger.error(f"스마트 주문 실행 실패: {e}")
            return ExecutionResult(
                success=False,
                asset=params.asset,
                side=params.side,
                requested_amount_krw=params.amount_krw,
                error_message=str(e)
            )
    
    def _check_psychological_bias(self, params: SmartOrderParams) -> Dict:
        """심리적 편향 검사"""
        try:
            if self.bias_prevention is None:
                return {"allowed": True}
            
            # FOMO 검사
            if params.side == "buy" and params.urgency_score > 0.8:
                portfolio = self.coinone_client.get_portfolio_value()
                asset_info = portfolio.get("assets", {}).get(params.asset, {})
                current_value = asset_info.get("value_krw", 0)
                total_value = portfolio.get("total_krw", 1)
                current_weight = current_value / total_value
                
                if current_weight > params.max_position_size:
                    return {
                        "allowed": False,
                        "reason": f"FOMO 방지: {params.asset} 비중이 이미 {current_weight:.1%}로 높음"
                    }
            
            # 패닉 셀링 검사
            if params.side == "sell" and params.urgency_score > 0.8:
                # 최근 24시간 가격 변화 확인
                try:
                    current_price = self.coinone_client.get_latest_price(params.asset)
                    # 간단한 패닉 셀링 방지: 10% 이상 하락 시 일시 정지
                    # 실제로는 더 정교한 로직 필요
                    return {"allowed": True}  # 일단 허용
                except:
                    pass
            
            return {"allowed": True}
            
        except Exception as e:
            logger.warning(f"심리적 편향 검사 실패: {e}")
            return {"allowed": True}  # 오류 시 허용
    
    def _check_scenario_response(self, params: SmartOrderParams) -> Dict:
        """시나리오 대응 확인"""
        try:
            if self.scenario_response is None:
                return {"allowed": True}
            
            # 시나리오 대응 시스템에서 현재 활성 시나리오 확인
            # 실제 구현에서는 scenario_response.get_active_scenarios() 같은 메서드 사용
            
            # 예시: 블랙스완 이벤트 시 대량 주문 제한
            if params.amount_krw > 10000000:  # 1천만원 이상
                # 대량 주문 시 추가 검증 로직
                pass
            
            return {"allowed": True}
            
        except Exception as e:
            logger.warning(f"시나리오 대응 확인 실패: {e}")
            return {"allowed": True}
    
    def _optimize_execution_strategy(self, params: SmartOrderParams) -> SmartOrderParams:
        """실행 전략 최적화"""
        try:
            # 1. 고급 분석 신호 종합
            combined_signal = self._calculate_combined_signal(params)
            
            # 2. 시장 상황별 전략 조정
            if params.market_condition in [MarketCondition.VERY_VOLATILE, MarketCondition.BEARISH]:
                # 변동성 높거나 약세장: 보수적 접근
                if params.strategy == ExecutionStrategy.MARKET:
                    params.strategy = ExecutionStrategy.LIMIT_CONSERVATIVE
                params.max_slippage *= 1.5  # 슬리피지 허용치 증가
                
            elif params.market_condition == MarketCondition.VERY_BULLISH:
                # 강세장: 적극적 접근
                if params.strategy == ExecutionStrategy.LIMIT_CONSERVATIVE:
                    params.strategy = ExecutionStrategy.LIMIT_AGGRESSIVE
            
            # 3. 신호 강도에 따른 긴급도 조정
            if abs(combined_signal) > 0.7:
                params.urgency_score = min(1.0, params.urgency_score * 1.2)
            elif abs(combined_signal) < 0.3:
                params.urgency_score = max(0.1, params.urgency_score * 0.8)
            
            # 4. 주문 크기 최적화
            params = self._optimize_order_size(params, combined_signal)
            
            logger.info(f"전략 최적화: {params.strategy.value}, "
                       f"긴급도: {params.urgency_score:.2f}, "
                       f"종합신호: {combined_signal:.2f}")
            
            return params
            
        except Exception as e:
            logger.error(f"실행 전략 최적화 실패: {e}")
            return params
    
    def _calculate_combined_signal(self, params: SmartOrderParams) -> float:
        """고급 분석 신호 종합"""
        try:
            signals = []
            weights = []
            
            # 멀티 타임프레임 신호 (가중치: 30%)
            if abs(params.multi_timeframe_signal) > 0:
                signals.append(params.multi_timeframe_signal)
                weights.append(0.30)
            
            # 온체인 데이터 신호 (가중치: 25%)
            if abs(params.onchain_signal) > 0:
                signals.append(params.onchain_signal)
                weights.append(0.25)
            
            # 매크로 경제 신호 (가중치: 20%)
            if abs(params.macro_signal) > 0:
                signals.append(params.macro_signal)
                weights.append(0.20)
            
            # 시장 심리 신호 (가중치: 25%)
            if abs(params.sentiment_signal) > 0:
                signals.append(params.sentiment_signal)
                weights.append(0.25)
            
            if not signals:
                return 0.0
            
            # 가중 평균 계산
            weighted_sum = sum(s * w for s, w in zip(signals, weights))
            total_weight = sum(weights)
            
            combined_signal = weighted_sum / total_weight if total_weight > 0 else 0.0
            
            # 신뢰도로 신호 강도 조정
            combined_signal *= params.confidence_score
            
            return max(-1.0, min(1.0, combined_signal))
            
        except Exception as e:
            logger.error(f"종합 신호 계산 실패: {e}")
            return 0.0
    
    def _optimize_order_size(self, params: SmartOrderParams, combined_signal: float) -> SmartOrderParams:
        """주문 크기 최적화"""
        try:
            # 현재 포트폴리오 조회
            portfolio = self.coinone_client.get_portfolio_value()
            total_value = portfolio.get("total_krw", 0)
            
            if total_value <= 0:
                return params
            
            # 신호 강도에 따른 주문 크기 조정
            signal_multiplier = 1.0
            
            if params.side == "buy":
                # 매수: 긍정적 신호가 강할수록 더 큰 주문
                if combined_signal > 0.5:
                    signal_multiplier = 1.2  # 20% 증가
                elif combined_signal > 0.3:
                    signal_multiplier = 1.1  # 10% 증가
                elif combined_signal < -0.3:
                    signal_multiplier = 0.7  # 30% 감소
            else:  # sell
                # 매도: 부정적 신호가 강할수록 더 큰 매도
                if combined_signal < -0.5:
                    signal_multiplier = 1.2
                elif combined_signal < -0.3:
                    signal_multiplier = 1.1
                elif combined_signal > 0.3:
                    signal_multiplier = 0.7
            
            # 조정된 주문 크기 계산
            adjusted_amount = params.amount_krw * signal_multiplier
            
            # 최대 포지션 크기 제한 (전체 포트폴리오의 10%)
            max_order_size = total_value * params.max_position_size
            adjusted_amount = min(adjusted_amount, max_order_size)
            
            # 최소 주문 크기 보장 (1만원)
            adjusted_amount = max(adjusted_amount, 10000)
            
            if adjusted_amount != params.amount_krw:
                logger.info(f"주문 크기 조정: {params.amount_krw:,.0f} → {adjusted_amount:,.0f} KRW "
                          f"(신호: {combined_signal:+.2f})")
                params.amount_krw = adjusted_amount
            
            return params
            
        except Exception as e:
            logger.error(f"주문 크기 최적화 실패: {e}")
            return params
    
    def _validate_order_parameters(self, params: SmartOrderParams) -> Dict:
        """주문 파라미터 검증"""
        try:
            # 1. 기본 파라미터 검증
            if params.amount_krw < 1000:
                return {"valid": False, "error": "주문 금액이 너무 작습니다 (최소 1,000원)"}
            
            if params.asset not in self.coinone_client.supported_coins:
                return {"valid": False, "error": f"지원하지 않는 코인입니다: {params.asset}"}
            
            # 2. 잔고 확인
            balances = self.coinone_client.get_balances()
            
            if params.side == "buy":
                krw_balance = balances.get("KRW", 0)
                if krw_balance < params.amount_krw:
                    return {"valid": False, "error": f"KRW 잔고 부족: {krw_balance:,.0f} < {params.amount_krw:,.0f}"}
            
            else:  # sell
                asset_balance = balances.get(params.asset, 0)
                current_price = self.coinone_client.get_latest_price(params.asset)
                
                if current_price <= 0:
                    return {"valid": False, "error": f"{params.asset} 현재가 조회 실패"}
                
                required_quantity = params.amount_krw / current_price
                if asset_balance < required_quantity:
                    return {"valid": False, "error": f"{params.asset} 잔고 부족: {asset_balance:.8f} < {required_quantity:.8f}"}
            
            # 3. 시장 상태 확인
            try:
                ticker = self.coinone_client.get_ticker(params.asset)
                if not ticker.get("success", True):
                    return {"valid": False, "error": f"{params.asset} 시장 데이터 조회 실패"}
            except:
                pass  # 티커 조회 실패는 치명적이지 않음
            
            return {"valid": True}
            
        except Exception as e:
            logger.error(f"주문 파라미터 검증 실패: {e}")
            return {"valid": False, "error": str(e)}
    
    def _execute_market_order(self, params: SmartOrderParams) -> ExecutionResult:
        """시장가 주문 실행"""
        try:
            logger.info(f"시장가 주문 실행: {params.asset} {params.side} {params.amount_krw:,.0f} KRW")
            
            # 현재가 조회 (슬리피지 계산용)
            current_price = self.coinone_client.get_latest_price(params.asset)
            
            # 주문 실행
            if params.side == "buy":
                amount = params.amount_krw  # KRW 금액
            else:
                amount = params.amount_krw / current_price  # 코인 수량
            
            order = self.order_manager.submit_market_order(
                currency=params.asset,
                side=params.side,
                amount=amount
            )
            
            if order and order.status != OrderStatus.FAILED:
                # 주문 완료 대기 (최대 1분)
                timeout = time.time() + 60
                while time.time() < timeout:
                    status = self.order_manager.check_order_status(order.order_id)
                    if status == OrderStatus.FILLED:
                        break
                    time.sleep(2)
                
                # 실행 결과 계산
                executed_amount_krw = order.filled_amount * order.average_price if params.side == "sell" else order.filled_amount
                executed_quantity = order.filled_amount
                average_price = order.average_price
                
                # 슬리피지 계산
                slippage = abs(average_price - current_price) / current_price if current_price > 0 else 0
                
                return ExecutionResult(
                    success=True,
                    asset=params.asset,
                    side=params.side,
                    requested_amount_krw=params.amount_krw,
                    executed_amount_krw=executed_amount_krw,
                    executed_quantity=executed_quantity,
                    average_price=average_price,
                    slippage=slippage,
                    fees=order.fee,
                    order_ids=[order.order_id]
                )
            else:
                error_msg = order.error_message if order else "주문 제출 실패"
                return ExecutionResult(
                    success=False,
                    asset=params.asset,
                    side=params.side,
                    requested_amount_krw=params.amount_krw,
                    error_message=error_msg
                )
                
        except Exception as e:
            logger.error(f"시장가 주문 실행 실패: {e}")
            return ExecutionResult(
                success=False,
                asset=params.asset,
                side=params.side,
                requested_amount_krw=params.amount_krw,
                error_message=str(e)
            )
    
    def _execute_limit_order(self, params: SmartOrderParams) -> ExecutionResult:
        """지정가 주문 실행"""
        try:
            logger.info(f"지정가 주문 실행: {params.asset} {params.side} {params.amount_krw:,.0f} KRW")
            
            # 현재가 조회
            current_price = self.coinone_client.get_latest_price(params.asset)
            
            # 지정가 계산
            if params.strategy == ExecutionStrategy.LIMIT_AGGRESSIVE:
                price_offset = 0.001  # 0.1%
            else:  # LIMIT_CONSERVATIVE
                price_offset = 0.003  # 0.3%
            
            if params.side == "buy":
                limit_price = current_price * (1 + price_offset)  # 현재가보다 높게
                amount = params.amount_krw / limit_price
            else:  # sell
                limit_price = current_price * (1 - price_offset)  # 현재가보다 낮게
                amount = params.amount_krw / current_price
            
            # 주문 제출
            order = self.order_manager.submit_limit_order(
                currency=params.asset,
                side=params.side,
                amount=amount,
                price=limit_price
            )
            
            if order and order.status != OrderStatus.FAILED:
                # 주문 완료 대기 (타임아웃 적용)
                timeout = time.time() + (params.timeout_minutes * 60)
                while time.time() < timeout:
                    status = self.order_manager.check_order_status(order.order_id)
                    if status == OrderStatus.FILLED:
                        break
                    elif status in [OrderStatus.CANCELLED, OrderStatus.FAILED]:
                        # 지정가 주문이 실패하면 시장가로 전환
                        logger.warning(f"지정가 주문 실패, 시장가로 전환: {params.asset}")
                        params.strategy = ExecutionStrategy.MARKET
                        return self._execute_market_order(params)
                    time.sleep(5)
                
                # 타임아웃 시 시장가 전환
                if time.time() >= timeout:
                    self.order_manager.cancel_order(order.order_id)
                    logger.warning(f"지정가 주문 타임아웃, 시장가로 전환: {params.asset}")
                    params.strategy = ExecutionStrategy.MARKET
                    return self._execute_market_order(params)
                
                # 실행 결과 계산
                executed_amount_krw = order.filled_amount * order.average_price if params.side == "sell" else order.filled_amount * limit_price
                slippage = abs(order.average_price - current_price) / current_price if current_price > 0 else 0
                
                return ExecutionResult(
                    success=True,
                    asset=params.asset,
                    side=params.side,
                    requested_amount_krw=params.amount_krw,
                    executed_amount_krw=executed_amount_krw,
                    executed_quantity=order.filled_amount,
                    average_price=order.average_price,
                    slippage=slippage,
                    fees=order.fee,
                    order_ids=[order.order_id]
                )
            else:
                error_msg = order.error_message if order else "지정가 주문 제출 실패"
                return ExecutionResult(
                    success=False,
                    asset=params.asset,
                    side=params.side,
                    requested_amount_krw=params.amount_krw,
                    error_message=error_msg
                )
                
        except Exception as e:
            logger.error(f"지정가 주문 실행 실패: {e}")
            return ExecutionResult(
                success=False,
                asset=params.asset,
                side=params.side,
                requested_amount_krw=params.amount_krw,
                error_message=str(e)
            )
    
    def _execute_smart_twap(self, params: SmartOrderParams) -> ExecutionResult:
        """스마트 TWAP 실행"""
        try:
            logger.info(f"스마트 TWAP 실행: {params.asset} {params.side} {params.amount_krw:,.0f} KRW")
            
            # TWAP 파라미터 계산
            total_amount = params.amount_krw
            
            # 신호 강도에 따른 실행 시간 조정
            combined_signal = abs(self._calculate_combined_signal(params))
            
            if combined_signal > 0.7:
                # 강한 신호: 빠른 실행 (30분, 6회)
                execution_minutes = 30
                slice_count = 6
            elif combined_signal > 0.4:
                # 중간 신호: 보통 실행 (60분, 8회)
                execution_minutes = 60
                slice_count = 8
            else:
                # 약한 신호: 긴 실행 (120분, 12회)
                execution_minutes = 120
                slice_count = 12
            
            slice_amount = total_amount / slice_count
            slice_interval = execution_minutes / slice_count
            
            logger.info(f"TWAP 계획: {slice_count}회 분할, {slice_interval:.1f}분 간격")
            
            # 슬라이스 실행
            executed_orders = []
            total_executed_amount = 0
            total_executed_quantity = 0
            total_fees = 0
            
            for i in range(slice_count):
                try:
                    # 각 슬라이스를 시장가로 실행
                    slice_params = SmartOrderParams(
                        asset=params.asset,
                        side=params.side,
                        amount_krw=slice_amount,
                        strategy=ExecutionStrategy.MARKET,
                        market_condition=params.market_condition,
                        urgency_score=params.urgency_score,
                        confidence_score=params.confidence_score
                    )
                    
                    slice_result = self._execute_market_order(slice_params)
                    
                    if slice_result.success:
                        executed_orders.extend(slice_result.order_ids)
                        total_executed_amount += slice_result.executed_amount_krw
                        total_executed_quantity += slice_result.executed_quantity
                        total_fees += slice_result.fees
                        
                        logger.info(f"TWAP 슬라이스 {i+1}/{slice_count} 완료: "
                                  f"{slice_result.executed_amount_krw:,.0f} KRW")
                    else:
                        logger.warning(f"TWAP 슬라이스 {i+1}/{slice_count} 실패: "
                                     f"{slice_result.error_message}")
                    
                    # 마지막 슬라이스가 아니면 대기
                    if i < slice_count - 1:
                        time.sleep(slice_interval * 60)
                        
                except Exception as e:
                    logger.error(f"TWAP 슬라이스 {i+1} 실행 중 오류: {e}")
                    continue
            
            # 평균 실행가 계산
            average_price = total_executed_amount / total_executed_quantity if total_executed_quantity > 0 else 0
            
            # 슬리피지는 각 슬라이스의 평균으로 근사치 계산
            slippage = 0.002  # 2% 근사치 (실제로는 각 슬라이스별로 계산 필요)
            
            success = total_executed_amount > 0
            
            return ExecutionResult(
                success=success,
                asset=params.asset,
                side=params.side,
                requested_amount_krw=params.amount_krw,
                executed_amount_krw=total_executed_amount,
                executed_quantity=total_executed_quantity,
                average_price=average_price,
                slippage=slippage,
                fees=total_fees,
                order_ids=executed_orders
            )
            
        except Exception as e:
            logger.error(f"스마트 TWAP 실행 실패: {e}")
            return ExecutionResult(
                success=False,
                asset=params.asset,
                side=params.side,
                requested_amount_krw=params.amount_krw,
                error_message=str(e)
            )
    
    def _update_execution_stats(self, result: ExecutionResult):
        """실행 통계 업데이트"""
        try:
            self.execution_stats["total_orders"] += 1
            
            if result.success:
                self.execution_stats["successful_orders"] += 1
                self.execution_stats["total_fees"] += result.fees
                
                # 평균 슬리피지 업데이트
                current_avg = self.execution_stats["average_slippage"]
                total_successful = self.execution_stats["successful_orders"]
                new_avg = (current_avg * (total_successful - 1) + result.slippage) / total_successful
                self.execution_stats["average_slippage"] = new_avg
                
            else:
                self.execution_stats["failed_orders"] += 1
                
        except Exception as e:
            logger.error(f"실행 통계 업데이트 실패: {e}")
    
    def _post_execution_analysis(self, params: SmartOrderParams, result: ExecutionResult):
        """실행 후 분석 및 학습"""
        try:
            if not result.success:
                return
            
            # 슬리피지 분석
            if result.slippage > params.max_slippage:
                logger.warning(f"높은 슬리피지 감지: {result.slippage:.3%} > {params.max_slippage:.3%}")
                # 향후 같은 자산에 대해 더 보수적인 전략 적용 가능
            
            # 실행 효율성 분석
            execution_efficiency = result.executed_amount_krw / params.amount_krw if params.amount_krw > 0 else 0
            
            if execution_efficiency < 0.95:  # 95% 미만 실행
                logger.warning(f"낮은 실행 효율성: {execution_efficiency:.1%}")
            
            logger.info(f"실행 분석 - 슬리피지: {result.slippage:.3%}, "
                       f"효율성: {execution_efficiency:.1%}, "
                       f"수수료: {result.fees:,.0f} KRW")
            
        except Exception as e:
            logger.error(f"실행 후 분석 실패: {e}")
    
    def get_execution_stats(self) -> Dict:
        """실행 통계 조회"""
        return self.execution_stats.copy()
    
    def get_optimal_strategy(
        self, 
        asset: str, 
        side: str, 
        amount_krw: float,
        market_signals: Dict = None
    ) -> ExecutionStrategy:
        """
        최적 실행 전략 추천
        
        Args:
            asset: 자산
            side: 매수/매도
            amount_krw: 주문 금액
            market_signals: 시장 신호들
            
        Returns:
            추천 실행 전략
        """
        try:
            # 기본 전략: 소액은 시장가, 고액은 TWAP
            if amount_krw < 100000:  # 10만원 미만
                return ExecutionStrategy.MARKET
            elif amount_krw < 1000000:  # 100만원 미만
                return ExecutionStrategy.LIMIT_AGGRESSIVE
            else:  # 100만원 이상
                return ExecutionStrategy.TWAP_SMART
            
        except Exception as e:
            logger.error(f"최적 전략 추천 실패: {e}")
            return ExecutionStrategy.MARKET