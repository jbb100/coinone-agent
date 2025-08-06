"""
Scenario Response System

시나리오별 대응 전략 시스템
- 블랙스완 이벤트 대응
- 규제 리스크 대응
- 알트시즌 대응
- 시장 크래시 대응
- 상황별 자동 리밸런싱
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd
import numpy as np
from loguru import logger


class ScenarioType(Enum):
    """시나리오 유형"""
    BLACK_SWAN = "black_swan"           # 블랙스완 이벤트
    REGULATION_RISK = "regulation_risk"  # 규제 리스크
    ALT_SEASON = "alt_season"           # 알트시즌
    MARKET_CRASH = "market_crash"       # 시장 크래시
    EUPHORIA = "euphoria"               # 시장 과열
    STABLECOIN_DEPEG = "stablecoin_depeg"  # 스테이블코인 디페깅
    EXCHANGE_RISK = "exchange_risk"     # 거래소 리스크
    MACRO_SHOCK = "macro_shock"         # 매크로 충격


class ScenarioSeverity(Enum):
    """시나리오 심각도"""
    LOW = "low"           # 낮음
    MEDIUM = "medium"     # 보통
    HIGH = "high"         # 높음
    CRITICAL = "critical" # 치명적


class ResponseAction(Enum):
    """대응 행동"""
    HOLD = "hold"                    # 보유
    DEFENSIVE_REBALANCE = "defensive_rebalance"  # 방어적 리밸런싱
    EMERGENCY_DCA = "emergency_dca"  # 응급 DCA
    RISK_OFF = "risk_off"           # 리스크 회피
    OPPORTUNISTIC_BUY = "opportunistic_buy"  # 기회매수
    SATELLITE_BOOST = "satellite_boost"      # 위성자산 강화
    IMMEDIATE_SELL = "immediate_sell"        # 즉시매도


@dataclass
class ScenarioTrigger:
    """시나리오 트리거"""
    trigger_id: str
    scenario_type: ScenarioType
    condition_func: Callable[[Dict[str, Any]], bool]  # 조건 함수
    description: str
    severity_func: Callable[[Dict[str, Any]], ScenarioSeverity]  # 심각도 함수
    cooldown_hours: int = 24  # 재발동 방지 시간


@dataclass
class ScenarioResponse:
    """시나리오 대응"""
    scenario_type: ScenarioType
    severity: ScenarioSeverity
    recommended_actions: List[ResponseAction]
    target_allocation: Dict[str, float]
    execution_priority: int  # 1-10 (높을수록 우선)
    risk_adjustment: float   # -1.0 ~ 1.0
    reasoning: str
    confidence: float        # 0-1
    estimated_duration: timedelta  # 예상 지속 시간


@dataclass
class ScenarioEvent:
    """시나리오 이벤트"""
    event_id: str
    scenario_type: ScenarioType
    severity: ScenarioSeverity
    triggered_at: datetime
    resolved_at: Optional[datetime] = None
    trigger_data: Dict[str, Any] = field(default_factory=dict)
    response_taken: Optional[ScenarioResponse] = None
    outcome_data: Dict[str, Any] = field(default_factory=dict)


class ScenarioResponseSystem:
    """
    시나리오 대응 시스템
    
    다양한 시장 시나리오를 감지하고 자동으로 적절한 대응 전략을 실행합니다.
    """
    
    def __init__(self):
        """시나리오 대응 시스템 초기화"""
        
        self.active_scenarios: List[ScenarioEvent] = []
        self.scenario_history: List[ScenarioEvent] = []
        self.trigger_cooldowns: Dict[str, datetime] = {}
        
        # 시나리오 트리거들 등록
        self.triggers = self._initialize_triggers()
        
        # 기본 대응 전략들
        self.response_strategies = self._initialize_response_strategies()
        
        logger.info("Scenario Response System 초기화 완료")
    
    def _initialize_triggers(self) -> List[ScenarioTrigger]:
        """시나리오 트리거들 초기화"""
        
        triggers = []
        
        # 1. 블랙스완 이벤트 (급격한 하락)
        triggers.append(ScenarioTrigger(
            trigger_id="black_swan_crash",
            scenario_type=ScenarioType.BLACK_SWAN,
            condition_func=lambda data: (
                data.get("price_change_24h", 0) < -0.30 and  # 24시간 -30% 이상
                data.get("volume_surge", 1) > 3.0             # 거래량 3배 이상 증가
            ),
            description="급격한 가격 하락과 거래량 급증 (블랙스완)",
            severity_func=lambda data: (
                ScenarioSeverity.CRITICAL if data.get("price_change_24h", 0) < -0.50
                else ScenarioSeverity.HIGH
            ),
            cooldown_hours=48
        ))
        
        # 2. 규제 리스크
        triggers.append(ScenarioTrigger(
            trigger_id="regulation_news",
            scenario_type=ScenarioType.REGULATION_RISK,
            condition_func=lambda data: (
                data.get("regulation_sentiment", 0) < -0.7 and  # 강한 부정적 뉴스
                data.get("price_change_1h", 0) < -0.10           # 1시간 -10% 이상
            ),
            description="규제 관련 부정적 뉴스와 급락",
            severity_func=lambda data: (
                ScenarioSeverity.HIGH if data.get("regulation_sentiment", 0) < -0.8
                else ScenarioSeverity.MEDIUM
            ),
            cooldown_hours=12
        ))
        
        # 3. 알트시즌
        triggers.append(ScenarioTrigger(
            trigger_id="alt_season_start",
            scenario_type=ScenarioType.ALT_SEASON,
            condition_func=lambda data: (
                data.get("alt_dominance", 0) > 0.25 and          # 알트코인 도미넌스 25% 이상
                data.get("alt_performance_7d", 0) > 0.20 and     # 7일간 +20% 이상
                data.get("btc_dominance", 1) < 0.60              # BTC 도미넌스 60% 미만
            ),
            description="알트코인 강세 및 도미넌스 상승 (알트시즌)",
            severity_func=lambda data: ScenarioSeverity.MEDIUM,
            cooldown_hours=72
        ))
        
        # 4. 시장 크래시
        triggers.append(ScenarioTrigger(
            trigger_id="market_crash",
            scenario_type=ScenarioType.MARKET_CRASH,
            condition_func=lambda data: (
                data.get("price_change_7d", 0) < -0.40 and       # 7일간 -40% 이상
                data.get("fear_greed_index", 50) < 20 and        # 공포지수 20 미만
                data.get("liquidations_24h", 0) > 1000000000     # 청산 10억달러 이상
            ),
            description="지속적 하락과 대량 청산 (시장 크래시)",
            severity_func=lambda data: (
                ScenarioSeverity.CRITICAL if data.get("price_change_7d", 0) < -0.60
                else ScenarioSeverity.HIGH
            ),
            cooldown_hours=24
        ))
        
        # 5. 시장 과열 (버블)
        triggers.append(ScenarioTrigger(
            trigger_id="market_euphoria",
            scenario_type=ScenarioType.EUPHORIA,
            condition_func=lambda data: (
                data.get("price_change_30d", 0) > 1.0 and        # 30일간 100% 이상 상승
                data.get("fear_greed_index", 50) > 80 and        # 극도의 탐욕
                data.get("funding_rate", 0) > 0.01               # 높은 펀딩비율
            ),
            description="급격한 상승과 극도의 탐욕 (시장 과열)",
            severity_func=lambda data: ScenarioSeverity.HIGH,
            cooldown_hours=48
        ))
        
        # 6. 스테이블코인 디페깅
        triggers.append(ScenarioTrigger(
            trigger_id="stablecoin_depeg",
            scenario_type=ScenarioType.STABLECOIN_DEPEG,
            condition_func=lambda data: (
                data.get("usdt_price", 1.0) < 0.98 or           # USDT 2% 이상 디스카운트
                data.get("stablecoin_outflow", 0) > 5000000000   # 50억달러 이상 유출
            ),
            description="주요 스테이블코인 디페깅 발생",
            severity_func=lambda data: (
                ScenarioSeverity.CRITICAL if data.get("usdt_price", 1.0) < 0.95
                else ScenarioSeverity.HIGH
            ),
            cooldown_hours=6
        ))
        
        # 7. 매크로 충격
        triggers.append(ScenarioTrigger(
            trigger_id="macro_shock",
            scenario_type=ScenarioType.MACRO_SHOCK,
            condition_func=lambda data: (
                data.get("vix_spike", 0) > 15 and               # VIX 급등 (15p 이상)
                data.get("dxy_spike", 0) > 3 and                # 달러지수 급등 (3p 이상)
                data.get("gold_change_24h", 0) > 0.05           # 금 5% 이상 상승
            ),
            description="매크로 경제 충격 (VIX, 달러 급등)",
            severity_func=lambda data: ScenarioSeverity.HIGH,
            cooldown_hours=12
        ))
        
        return triggers
    
    def _initialize_response_strategies(self) -> Dict[ScenarioType, Dict[ScenarioSeverity, ScenarioResponse]]:
        """대응 전략 초기화"""
        
        strategies = {}
        
        # 블랙스완 대응
        strategies[ScenarioType.BLACK_SWAN] = {
            ScenarioSeverity.HIGH: ScenarioResponse(
                scenario_type=ScenarioType.BLACK_SWAN,
                severity=ScenarioSeverity.HIGH,
                recommended_actions=[ResponseAction.EMERGENCY_DCA, ResponseAction.DEFENSIVE_REBALANCE],
                target_allocation={"crypto": 0.60, "krw": 0.40},  # 기회매수 증가
                execution_priority=9,
                risk_adjustment=-0.2,
                reasoning="블랙스완 이벤트 시 장기적 기회매수 기회 포착",
                confidence=0.8,
                estimated_duration=timedelta(hours=72)
            ),
            ScenarioSeverity.CRITICAL: ScenarioResponse(
                scenario_type=ScenarioType.BLACK_SWAN,
                severity=ScenarioSeverity.CRITICAL,
                recommended_actions=[ResponseAction.EMERGENCY_DCA, ResponseAction.RISK_OFF],
                target_allocation={"crypto": 0.40, "krw": 0.60},  # 더 보수적
                execution_priority=10,
                risk_adjustment=-0.4,
                reasoning="극심한 블랙스완 이벤트 시 방어 위주 전략",
                confidence=0.9,
                estimated_duration=timedelta(days=7)
            )
        }
        
        # 규제 리스크 대응
        strategies[ScenarioType.REGULATION_RISK] = {
            ScenarioSeverity.MEDIUM: ScenarioResponse(
                scenario_type=ScenarioType.REGULATION_RISK,
                severity=ScenarioSeverity.MEDIUM,
                recommended_actions=[ResponseAction.DEFENSIVE_REBALANCE],
                target_allocation={"crypto": 0.40, "krw": 0.60},
                execution_priority=6,
                risk_adjustment=-0.3,
                reasoning="규제 불확실성 증가로 보수적 대응",
                confidence=0.7,
                estimated_duration=timedelta(days=14)
            ),
            ScenarioSeverity.HIGH: ScenarioResponse(
                scenario_type=ScenarioType.REGULATION_RISK,
                severity=ScenarioSeverity.HIGH,
                recommended_actions=[ResponseAction.RISK_OFF],
                target_allocation={"crypto": 0.25, "krw": 0.75},
                execution_priority=8,
                risk_adjustment=-0.5,
                reasoning="심각한 규제 리스크로 대폭 비중 축소",
                confidence=0.8,
                estimated_duration=timedelta(days=30)
            )
        }
        
        # 알트시즌 대응
        strategies[ScenarioType.ALT_SEASON] = {
            ScenarioSeverity.MEDIUM: ScenarioResponse(
                scenario_type=ScenarioType.ALT_SEASON,
                severity=ScenarioSeverity.MEDIUM,
                recommended_actions=[ResponseAction.SATELLITE_BOOST],
                target_allocation={"crypto": 0.75, "krw": 0.25},  # 알트코인 비중 증가
                execution_priority=7,
                risk_adjustment=0.2,
                reasoning="알트시즌 진입으로 위성자산 비중 확대",
                confidence=0.6,
                estimated_duration=timedelta(days=45)
            )
        }
        
        # 시장 크래시 대응
        strategies[ScenarioType.MARKET_CRASH] = {
            ScenarioSeverity.HIGH: ScenarioResponse(
                scenario_type=ScenarioType.MARKET_CRASH,
                severity=ScenarioSeverity.HIGH,
                recommended_actions=[ResponseAction.EMERGENCY_DCA, ResponseAction.DEFENSIVE_REBALANCE],
                target_allocation={"crypto": 0.50, "krw": 0.50},
                execution_priority=8,
                risk_adjustment=-0.3,
                reasoning="시장 크래시 시 단계적 기회매수",
                confidence=0.8,
                estimated_duration=timedelta(days=21)
            ),
            ScenarioSeverity.CRITICAL: ScenarioResponse(
                scenario_type=ScenarioType.MARKET_CRASH,
                severity=ScenarioSeverity.CRITICAL,
                recommended_actions=[ResponseAction.RISK_OFF, ResponseAction.HOLD],
                target_allocation={"crypto": 0.30, "krw": 0.70},
                execution_priority=9,
                risk_adjustment=-0.5,
                reasoning="극심한 크래시 시 안전자산 중심 방어",
                confidence=0.9,
                estimated_duration=timedelta(days=60)
            )
        }
        
        # 시장 과열 대응
        strategies[ScenarioType.EUPHORIA] = {
            ScenarioSeverity.HIGH: ScenarioResponse(
                scenario_type=ScenarioType.EUPHORIA,
                severity=ScenarioSeverity.HIGH,
                recommended_actions=[ResponseAction.DEFENSIVE_REBALANCE],
                target_allocation={"crypto": 0.40, "krw": 0.60},  # 비중 축소
                execution_priority=7,
                risk_adjustment=-0.3,
                reasoning="시장 과열로 수익 실현 및 비중 축소",
                confidence=0.7,
                estimated_duration=timedelta(days=30)
            )
        }
        
        # 스테이블코인 디페깅 대응
        strategies[ScenarioType.STABLECOIN_DEPEG] = {
            ScenarioSeverity.HIGH: ScenarioResponse(
                scenario_type=ScenarioType.STABLECOIN_DEPEG,
                severity=ScenarioSeverity.HIGH,
                recommended_actions=[ResponseAction.RISK_OFF],
                target_allocation={"crypto": 0.30, "krw": 0.70},
                execution_priority=9,
                risk_adjustment=-0.4,
                reasoning="스테이블코인 디페깅으로 시스템 리스크 대응",
                confidence=0.9,
                estimated_duration=timedelta(days=14)
            )
        }
        
        # 매크로 충격 대응
        strategies[ScenarioType.MACRO_SHOCK] = {
            ScenarioSeverity.HIGH: ScenarioResponse(
                scenario_type=ScenarioType.MACRO_SHOCK,
                severity=ScenarioSeverity.HIGH,
                recommended_actions=[ResponseAction.RISK_OFF],
                target_allocation={"crypto": 0.35, "krw": 0.65},
                execution_priority=8,
                risk_adjustment=-0.4,
                reasoning="매크로 충격으로 리스크 자산 비중 축소",
                confidence=0.8,
                estimated_duration=timedelta(days=21)
            )
        }
        
        return strategies
    
    def detect_scenarios(self, market_data: Dict[str, Any]) -> List[ScenarioEvent]:
        """시나리오 감지"""
        
        detected_scenarios = []
        current_time = datetime.now()
        
        try:
            for trigger in self.triggers:
                # 쿨다운 체크
                if trigger.trigger_id in self.trigger_cooldowns:
                    cooldown_end = self.trigger_cooldowns[trigger.trigger_id] + timedelta(hours=trigger.cooldown_hours)
                    if current_time < cooldown_end:
                        continue
                
                # 트리거 조건 체크
                if trigger.condition_func(market_data):
                    # 심각도 계산
                    severity = trigger.severity_func(market_data)
                    
                    # 시나리오 이벤트 생성
                    event = ScenarioEvent(
                        event_id=f"{trigger.trigger_id}_{current_time.strftime('%Y%m%d_%H%M%S')}",
                        scenario_type=trigger.scenario_type,
                        severity=severity,
                        triggered_at=current_time,
                        trigger_data=market_data.copy()
                    )
                    
                    detected_scenarios.append(event)
                    
                    # 쿨다운 설정
                    self.trigger_cooldowns[trigger.trigger_id] = current_time
                    
                    logger.warning(f"시나리오 감지: {trigger.scenario_type.value} ({severity.value})")
            
            return detected_scenarios
            
        except Exception as e:
            logger.error(f"시나리오 감지 실패: {e}")
            return []
    
    def generate_response(self, scenario_event: ScenarioEvent) -> Optional[ScenarioResponse]:
        """시나리오 대응 생성"""
        
        try:
            scenario_type = scenario_event.scenario_type
            severity = scenario_event.severity
            
            # 대응 전략 조회
            if scenario_type not in self.response_strategies:
                logger.warning(f"정의되지 않은 시나리오: {scenario_type.value}")
                return None
            
            severity_strategies = self.response_strategies[scenario_type]
            
            if severity not in severity_strategies:
                # 가장 가까운 심각도 찾기
                available_severities = list(severity_strategies.keys())
                if not available_severities:
                    return None
                
                # 간단한 매칭 (실제로는 더 정교한 로직 필요)
                severity = available_severities[0]
                logger.warning(f"정확한 심각도 매칭 없음, {severity.value} 사용")
            
            response = severity_strategies[severity]
            
            # 시장 상황에 따른 조정
            adjusted_response = self._adjust_response_for_context(
                response, scenario_event.trigger_data
            )
            
            logger.info(f"시나리오 대응 생성: {scenario_type.value} -> {adjusted_response.recommended_actions}")
            return adjusted_response
            
        except Exception as e:
            logger.error(f"시나리오 대응 생성 실패: {e}")
            return None
    
    def _adjust_response_for_context(
        self, 
        base_response: ScenarioResponse, 
        market_context: Dict[str, Any]
    ) -> ScenarioResponse:
        """시장 상황에 따른 대응 조정"""
        
        # 기본 응답 복사
        adjusted_response = ScenarioResponse(
            scenario_type=base_response.scenario_type,
            severity=base_response.severity,
            recommended_actions=base_response.recommended_actions.copy(),
            target_allocation=base_response.target_allocation.copy(),
            execution_priority=base_response.execution_priority,
            risk_adjustment=base_response.risk_adjustment,
            reasoning=base_response.reasoning,
            confidence=base_response.confidence,
            estimated_duration=base_response.estimated_duration
        )
        
        # 시장 상황에 따른 조정
        
        # 1. 유동성 상황 고려
        liquidity_score = market_context.get("liquidity_score", 0.5)  # 0-1
        if liquidity_score < 0.3:  # 낮은 유동성
            adjusted_response.risk_adjustment -= 0.1
            adjusted_response.confidence *= 0.9
            adjusted_response.reasoning += " (낮은 유동성 고려)"
        
        # 2. 변동성 상황 고려  
        volatility = market_context.get("volatility_24h", 0.1)
        if volatility > 0.20:  # 높은 변동성
            # 더 보수적으로 조정
            crypto_allocation = adjusted_response.target_allocation.get("crypto", 0.5)
            adjusted_response.target_allocation["crypto"] = max(0.2, crypto_allocation - 0.1)
            adjusted_response.target_allocation["krw"] = 1 - adjusted_response.target_allocation["crypto"]
        
        # 3. 거래량 고려
        volume_surge = market_context.get("volume_surge", 1.0)
        if volume_surge > 5.0:  # 극심한 거래량 증가
            adjusted_response.execution_priority = min(10, adjusted_response.execution_priority + 1)
            adjusted_response.estimated_duration = timedelta(
                seconds=adjusted_response.estimated_duration.total_seconds() * 1.5
            )
        
        return adjusted_response
    
    def execute_scenario_response(
        self, 
        scenario_event: ScenarioEvent,
        current_portfolio: Dict[str, float]
    ) -> Dict[str, Any]:
        """시나리오 대응 실행"""
        
        try:
            # 대응 전략 생성
            response = self.generate_response(scenario_event)
            if not response:
                return {"success": False, "error": "대응 전략 생성 실패"}
            
            scenario_event.response_taken = response
            
            # 실행 계획 수립
            execution_plan = self._create_execution_plan(response, current_portfolio)
            
            # 활성 시나리오에 추가
            self.active_scenarios.append(scenario_event)
            
            logger.info(f"시나리오 대응 실행: {response.scenario_type.value} "
                       f"우선순위 {response.execution_priority}")
            
            return {
                "success": True,
                "scenario_event": scenario_event,
                "response": response,
                "execution_plan": execution_plan
            }
            
        except Exception as e:
            logger.error(f"시나리오 대응 실행 실패: {e}")
            return {"success": False, "error": str(e)}
    
    def _create_execution_plan(
        self, 
        response: ScenarioResponse, 
        current_portfolio: Dict[str, float]
    ) -> Dict[str, Any]:
        """실행 계획 생성"""
        
        plan = {
            "rebalancing_needed": False,
            "target_allocation": response.target_allocation,
            "current_allocation": current_portfolio,
            "required_trades": {},
            "estimated_cost": 0.0,
            "urgency_level": "normal"
        }
        
        # 현재 배분과 목표 배분 비교
        total_diff = 0
        for asset in response.target_allocation:
            current = current_portfolio.get(asset, 0)
            target = response.target_allocation[asset]
            diff = abs(target - current)
            total_diff += diff
            
            if diff > 0.05:  # 5% 이상 차이
                plan["required_trades"][asset] = {
                    "current": current,
                    "target": target,
                    "change": target - current,
                    "action": "buy" if target > current else "sell"
                }
        
        if total_diff > 0.1:  # 총 10% 이상 변경 필요
            plan["rebalancing_needed"] = True
            
            # 긴급도 결정
            if response.execution_priority >= 8:
                plan["urgency_level"] = "high"
            elif response.execution_priority >= 6:
                plan["urgency_level"] = "medium"
        
        return plan
    
    def monitor_active_scenarios(self) -> List[Dict[str, Any]]:
        """활성 시나리오 모니터링"""
        
        monitoring_results = []
        current_time = datetime.now()
        
        try:
            for scenario in self.active_scenarios.copy():
                # 시나리오 지속 시간 체크
                duration = current_time - scenario.triggered_at
                estimated_end = scenario.triggered_at + (
                    scenario.response_taken.estimated_duration 
                    if scenario.response_taken else timedelta(hours=24)
                )
                
                status = {
                    "scenario_id": scenario.event_id,
                    "scenario_type": scenario.scenario_type.value,
                    "severity": scenario.severity.value,
                    "duration": duration,
                    "estimated_remaining": max(timedelta(0), estimated_end - current_time),
                    "is_expired": current_time > estimated_end,
                    "response_actions": [action.value for action in scenario.response_taken.recommended_actions] if scenario.response_taken else []
                }
                
                # 만료된 시나리오 해결 처리
                if status["is_expired"] and not scenario.resolved_at:
                    scenario.resolved_at = current_time
                    self.scenario_history.append(scenario)
                    self.active_scenarios.remove(scenario)
                    status["resolved"] = True
                    logger.info(f"시나리오 해결: {scenario.scenario_type.value}")
                
                monitoring_results.append(status)
            
            return monitoring_results
            
        except Exception as e:
            logger.error(f"시나리오 모니터링 실패: {e}")
            return []
    
    def get_combined_scenario_adjustment(self) -> Dict[str, Any]:
        """활성 시나리오들의 통합 조정값 계산"""
        
        if not self.active_scenarios:
            return {
                "risk_adjustment": 0.0,
                "allocation_adjustment": {},
                "active_scenarios_count": 0
            }
        
        try:
            # 가중치 기반 통합 계산
            total_risk_adjustment = 0.0
            total_weight = 0.0
            combined_allocation = {"crypto": 0.0, "krw": 0.0}
            
            for scenario in self.active_scenarios:
                if not scenario.response_taken:
                    continue
                
                response = scenario.response_taken
                weight = response.execution_priority / 10.0  # 0-1 범위로 정규화
                
                # 리스크 조정 통합
                total_risk_adjustment += response.risk_adjustment * weight
                total_weight += weight
                
                # 배분 조정 통합 (가중평균)
                for asset in response.target_allocation:
                    if asset not in combined_allocation:
                        combined_allocation[asset] = 0.0
                    combined_allocation[asset] += response.target_allocation[asset] * weight
            
            # 가중 평균 계산
            if total_weight > 0:
                final_risk_adjustment = total_risk_adjustment / total_weight
                
                for asset in combined_allocation:
                    combined_allocation[asset] /= total_weight
            else:
                final_risk_adjustment = 0.0
                combined_allocation = {"crypto": 0.5, "krw": 0.5}
            
            return {
                "risk_adjustment": final_risk_adjustment,
                "allocation_adjustment": combined_allocation,
                "active_scenarios_count": len(self.active_scenarios),
                "scenario_types": [s.scenario_type.value for s in self.active_scenarios]
            }
            
        except Exception as e:
            logger.error(f"통합 시나리오 조정 계산 실패: {e}")
            return {
                "risk_adjustment": 0.0,
                "allocation_adjustment": {"crypto": 0.5, "krw": 0.5},
                "active_scenarios_count": 0
            }
    
    def get_scenario_statistics(self) -> Dict[str, Any]:
        """시나리오 통계"""
        
        try:
            all_scenarios = self.active_scenarios + self.scenario_history
            
            if not all_scenarios:
                return {"total_scenarios": 0}
            
            # 시나리오 유형별 통계
            type_counts = {}
            severity_counts = {}
            
            for scenario in all_scenarios:
                scenario_type = scenario.scenario_type.value
                severity = scenario.severity.value
                
                type_counts[scenario_type] = type_counts.get(scenario_type, 0) + 1
                severity_counts[severity] = severity_counts.get(severity, 0) + 1
            
            # 평균 지속 시간
            resolved_scenarios = [s for s in all_scenarios if s.resolved_at]
            avg_duration = None
            if resolved_scenarios:
                total_duration = sum(
                    (s.resolved_at - s.triggered_at).total_seconds() 
                    for s in resolved_scenarios
                )
                avg_duration = total_duration / len(resolved_scenarios) / 3600  # 시간 단위
            
            return {
                "total_scenarios": len(all_scenarios),
                "active_scenarios": len(self.active_scenarios),
                "resolved_scenarios": len(self.scenario_history),
                "scenario_type_distribution": type_counts,
                "severity_distribution": severity_counts,
                "average_duration_hours": avg_duration
            }
            
        except Exception as e:
            logger.error(f"시나리오 통계 계산 실패: {e}")
            return {"error": str(e)}
    
    def force_resolve_scenario(self, scenario_id: str, outcome_data: Dict[str, Any] = None) -> bool:
        """시나리오 강제 해결"""
        
        try:
            for scenario in self.active_scenarios:
                if scenario.event_id == scenario_id:
                    scenario.resolved_at = datetime.now()
                    if outcome_data:
                        scenario.outcome_data = outcome_data
                    
                    self.scenario_history.append(scenario)
                    self.active_scenarios.remove(scenario)
                    
                    logger.info(f"시나리오 강제 해결: {scenario_id}")
                    return True
            
            logger.warning(f"시나리오 ID 찾을 수 없음: {scenario_id}")
            return False
            
        except Exception as e:
            logger.error(f"시나리오 강제 해결 실패: {e}")
            return False