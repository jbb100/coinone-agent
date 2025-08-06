"""
Behavioral Bias Prevention System

심리적 편향 방지 시스템
- FOMO (Fear of Missing Out) 방지
- 공황 매도 방지
- 과신 편향 체크
- 손실 회피 편향 완화
- 앵커링 편향 방지
- 확증 편향 방지
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import numpy as np
from loguru import logger


class BiasType(Enum):
    """편향 유형"""
    FOMO = "fomo"                           # 기회 상실 공포
    PANIC_SELLING = "panic_selling"         # 공황 매도
    OVERCONFIDENCE = "overconfidence"       # 과신
    LOSS_AVERSION = "loss_aversion"         # 손실 회피
    ANCHORING = "anchoring"                 # 앵커링
    CONFIRMATION = "confirmation"           # 확증 편향
    HERDING = "herding"                     # 군중 심리
    RECENCY_BIAS = "recency_bias"          # 최근 편향


class BiasLevel(Enum):
    """편향 수준"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PreventionAction(Enum):
    """방지 행동"""
    BLOCK_ORDER = "block_order"             # 주문 차단
    DELAY_EXECUTION = "delay_execution"     # 실행 지연
    REQUIRE_CONFIRMATION = "require_confirmation"  # 확인 요구
    REDUCE_AMOUNT = "reduce_amount"         # 금액 축소
    WARN_USER = "warn_user"                 # 사용자 경고
    COOLING_PERIOD = "cooling_period"       # 쿨링 기간


@dataclass
class BiasDetection:
    """편향 감지 결과"""
    bias_type: BiasType
    level: BiasLevel
    confidence: float              # 감지 신뢰도 (0-1)
    evidence: List[str]           # 근거 리스트
    risk_score: float             # 리스크 점수 (0-100)
    detected_at: datetime


@dataclass
class PreventionRule:
    """방지 규칙"""
    rule_id: str
    bias_type: BiasType
    trigger_conditions: Dict[str, Any]
    prevention_actions: List[PreventionAction]
    cooling_period_hours: int
    description: str
    is_active: bool = True


@dataclass
class BiasEvent:
    """편향 이벤트"""
    event_id: str
    bias_type: BiasType
    level: BiasLevel
    triggered_at: datetime
    original_decision: Dict[str, Any]  # 원래 결정
    prevented_actions: List[PreventionAction]
    user_override: bool = False    # 사용자가 오버라이드했는지
    outcome_data: Dict[str, Any] = None  # 결과 데이터


class BehavioralBiasPrevention:
    """
    심리적 편향 방지 시스템
    
    투자 결정에서 발생할 수 있는 다양한 심리적 편향을 
    감지하고 방지합니다.
    """
    
    def __init__(self):
        """편향 방지 시스템 초기화"""
        
        self.prevention_rules = self._initialize_prevention_rules()
        self.bias_history: List[BiasEvent] = []
        self.cooling_periods: Dict[str, datetime] = {}
        self.user_overrides: Dict[BiasType, int] = {}  # 편향별 오버라이드 횟수
        
        # 임계값 설정
        self.detection_thresholds = {
            BiasType.FOMO: {
                "price_surge_24h": 0.15,          # 24시간 15% 이상 상승
                "volume_surge": 3.0,               # 거래량 3배 증가
                "order_frequency_increase": 5.0    # 주문 빈도 5배 증가
            },
            BiasType.PANIC_SELLING: {
                "price_drop_1h": -0.10,            # 1시간 10% 하락
                "fear_index": 25,                  # 공포지수 25 미만
                "quick_sell_threshold": 0.05       # 5분내 매도 시도
            },
            BiasType.OVERCONFIDENCE: {
                "consecutive_wins": 5,             # 연속 5회 수익
                "position_size_increase": 0.5,     # 포지션 크기 50% 증가
                "frequency_increase": 3.0          # 거래 빈도 3배 증가
            }
        }
        
        logger.info("Behavioral Bias Prevention System 초기화 완료")
    
    def _initialize_prevention_rules(self) -> List[PreventionRule]:
        """방지 규칙 초기화"""
        
        rules = []
        
        # 1. FOMO 방지 규칙
        rules.append(PreventionRule(
            rule_id="fomo_price_surge",
            bias_type=BiasType.FOMO,
            trigger_conditions={
                "price_change_24h": ">0.20",       # 20% 이상 상승
                "order_amount": ">normal_amount*2", # 평소 2배 이상
                "quick_decision": "<300"            # 5분 이내 결정
            },
            prevention_actions=[
                PreventionAction.DELAY_EXECUTION,
                PreventionAction.WARN_USER,
                PreventionAction.REDUCE_AMOUNT
            ],
            cooling_period_hours=4,
            description="급격한 가격 상승 시 FOMO 방지"
        ))
        
        # 2. 공황 매도 방지
        rules.append(PreventionRule(
            rule_id="panic_selling_crash",
            bias_type=BiasType.PANIC_SELLING,
            trigger_conditions={
                "price_change_1h": "<-0.15",       # 1시간 15% 하락
                "sell_order": "True",              # 매도 주문
                "fear_index": "<30"                # 공포지수 30 미만
            },
            prevention_actions=[
                PreventionAction.DELAY_EXECUTION,
                PreventionAction.REQUIRE_CONFIRMATION,
                PreventionAction.WARN_USER
            ],
            cooling_period_hours=2,
            description="급락 시 공황 매도 방지"
        ))
        
        # 3. 과신 편향 방지
        rules.append(PreventionRule(
            rule_id="overconfidence_winning_streak",
            bias_type=BiasType.OVERCONFIDENCE,
            trigger_conditions={
                "consecutive_wins": ">=5",         # 연속 5회 수익
                "position_increase": ">0.5",       # 포지션 50% 증가
                "leverage_increase": "True"        # 레버리지 증가 시도
            },
            prevention_actions=[
                PreventionAction.WARN_USER,
                PreventionAction.REDUCE_AMOUNT,
                PreventionAction.COOLING_PERIOD
            ],
            cooling_period_hours=24,
            description="연승 후 과신 편향 방지"
        ))
        
        # 4. 손실 회피 편향 방지
        rules.append(PreventionRule(
            rule_id="loss_aversion_hold",
            bias_type=BiasType.LOSS_AVERSION,
            trigger_conditions={
                "unrealized_loss": ">0.20",        # 20% 이상 손실
                "holding_period": ">30",           # 30일 이상 보유
                "no_sell_action": "True"           # 매도 행동 없음
            },
            prevention_actions=[
                PreventionAction.WARN_USER,
                PreventionAction.REQUIRE_CONFIRMATION
            ],
            cooling_period_hours=168,  # 7일
            description="손실 포지션 과도한 보유 방지"
        ))
        
        # 5. 앵커링 편향 방지
        rules.append(PreventionRule(
            rule_id="anchoring_ath_reference",
            bias_type=BiasType.ANCHORING,
            trigger_conditions={
                "reference_to_ath": "True",        # 최고가 기준 언급
                "current_vs_ath": "<0.5",          # 최고가 대비 50% 미만
                "expected_return": ">2.0"          # 2배 이상 기대수익
            },
            prevention_actions=[
                PreventionAction.WARN_USER,
                PreventionAction.DELAY_EXECUTION
            ],
            cooling_period_hours=12,
            description="과거 최고가 앵커링 편향 방지"
        ))
        
        # 6. 군중 심리 방지
        rules.append(PreventionRule(
            rule_id="herding_social_media",
            bias_type=BiasType.HERDING,
            trigger_conditions={
                "social_sentiment": ">0.8",        # 소셜 미디어 극도 긍정
                "follow_trend": "True",            # 트렌드 추종
                "no_analysis": "True"              # 독립적 분석 없음
            },
            prevention_actions=[
                PreventionAction.WARN_USER,
                PreventionAction.DELAY_EXECUTION,
                PreventionAction.REQUIRE_CONFIRMATION
            ],
            cooling_period_hours=6,
            description="소셜 미디어 군중 심리 방지"
        ))
        
        return rules
    
    def detect_bias(
        self, 
        decision_data: Dict[str, Any], 
        market_context: Dict[str, Any],
        user_history: Dict[str, Any]
    ) -> List[BiasDetection]:
        """편향 감지"""
        
        detected_biases = []
        
        try:
            # 각 편향 유형별로 검사
            for bias_type in BiasType:
                detection = self._detect_specific_bias(
                    bias_type, decision_data, market_context, user_history
                )
                if detection:
                    detected_biases.append(detection)
            
            if detected_biases:
                logger.warning(f"{len(detected_biases)}개 편향 감지: "
                             f"{[d.bias_type.value for d in detected_biases]}")
            
            return detected_biases
            
        except Exception as e:
            logger.error(f"편향 감지 실패: {e}")
            return []
    
    def _detect_specific_bias(
        self,
        bias_type: BiasType,
        decision_data: Dict[str, Any],
        market_context: Dict[str, Any], 
        user_history: Dict[str, Any]
    ) -> Optional[BiasDetection]:
        """특정 편향 감지"""
        
        if bias_type == BiasType.FOMO:
            return self._detect_fomo(decision_data, market_context, user_history)
        elif bias_type == BiasType.PANIC_SELLING:
            return self._detect_panic_selling(decision_data, market_context, user_history)
        elif bias_type == BiasType.OVERCONFIDENCE:
            return self._detect_overconfidence(decision_data, market_context, user_history)
        elif bias_type == BiasType.LOSS_AVERSION:
            return self._detect_loss_aversion(decision_data, market_context, user_history)
        elif bias_type == BiasType.ANCHORING:
            return self._detect_anchoring(decision_data, market_context, user_history)
        elif bias_type == BiasType.HERDING:
            return self._detect_herding(decision_data, market_context, user_history)
        
        return None
    
    def _detect_fomo(
        self,
        decision_data: Dict[str, Any],
        market_context: Dict[str, Any],
        user_history: Dict[str, Any]
    ) -> Optional[BiasDetection]:
        """FOMO 감지"""
        
        try:
            evidence = []
            risk_score = 0.0
            
            # 가격 급등 확인
            price_change_24h = market_context.get("price_change_24h", 0)
            if price_change_24h > 0.15:  # 15% 이상 상승
                evidence.append(f"24시간 {price_change_24h*100:.1f}% 급등")
                risk_score += 30
            
            # 거래량 급증 확인
            volume_surge = market_context.get("volume_surge", 1.0)
            if volume_surge > 2.0:
                evidence.append(f"거래량 {volume_surge:.1f}배 급증")
                risk_score += 20
            
            # 비정상적 주문 크기
            normal_amount = user_history.get("avg_order_amount", 100000)
            current_amount = decision_data.get("order_amount", 0)
            if current_amount > normal_amount * 3:
                evidence.append(f"평소 {current_amount/normal_amount:.1f}배 주문 크기")
                risk_score += 25
            
            # 빠른 의사결정
            decision_time = decision_data.get("decision_time_seconds", 600)
            if decision_time < 300:  # 5분 이내
                evidence.append(f"성급한 의사결정 ({decision_time}초)")
                risk_score += 15
            
            # 소셜 미디어 영향
            social_sentiment = market_context.get("social_sentiment", 0.5)
            if social_sentiment > 0.8:
                evidence.append("소셜 미디어 극도 긍정 분위기")
                risk_score += 10
            
            # 편향 수준 결정
            if risk_score >= 70:
                level = BiasLevel.CRITICAL
            elif risk_score >= 50:
                level = BiasLevel.HIGH
            elif risk_score >= 30:
                level = BiasLevel.MEDIUM
            else:
                return None  # 임계값 미만
            
            return BiasDetection(
                bias_type=BiasType.FOMO,
                level=level,
                confidence=min(risk_score / 100, 0.95),
                evidence=evidence,
                risk_score=risk_score,
                detected_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"FOMO 감지 실패: {e}")
            return None
    
    def _detect_panic_selling(
        self,
        decision_data: Dict[str, Any],
        market_context: Dict[str, Any],
        user_history: Dict[str, Any]
    ) -> Optional[BiasDetection]:
        """공황 매도 감지"""
        
        try:
            # 매도 주문이 아니면 스킵
            if decision_data.get("order_side") != "sell":
                return None
            
            evidence = []
            risk_score = 0.0
            
            # 급격한 가격 하락
            price_change_1h = market_context.get("price_change_1h", 0)
            if price_change_1h < -0.10:  # 1시간 10% 하락
                evidence.append(f"1시간 {abs(price_change_1h)*100:.1f}% 급락")
                risk_score += 40
            
            # 공포 지수
            fear_index = market_context.get("fear_greed_index", 50)
            if fear_index < 25:
                evidence.append(f"극도의 공포 상태 (공포지수: {fear_index})")
                risk_score += 30
            
            # 빠른 매도 결정
            decision_time = decision_data.get("decision_time_seconds", 600)
            if decision_time < 180:  # 3분 이내
                evidence.append(f"성급한 매도 결정 ({decision_time}초)")
                risk_score += 20
            
            # 손실 상태에서 매도
            unrealized_pnl = decision_data.get("unrealized_pnl_pct", 0)
            if unrealized_pnl < -0.15:  # 15% 이상 손실
                evidence.append(f"손실 상태 매도 ({unrealized_pnl*100:.1f}%)")
                risk_score += 15
            
            # 대량 청산
            liquidations_24h = market_context.get("liquidations_24h", 0)
            if liquidations_24h > 500000000:  # 5억달러 이상
                evidence.append("대규모 청산 발생")
                risk_score += 10
            
            # 편향 수준 결정
            if risk_score >= 75:
                level = BiasLevel.CRITICAL
            elif risk_score >= 50:
                level = BiasLevel.HIGH
            elif risk_score >= 30:
                level = BiasLevel.MEDIUM
            else:
                return None
            
            return BiasDetection(
                bias_type=BiasType.PANIC_SELLING,
                level=level,
                confidence=min(risk_score / 100, 0.95),
                evidence=evidence,
                risk_score=risk_score,
                detected_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"공황 매도 감지 실패: {e}")
            return None
    
    def _detect_overconfidence(
        self,
        decision_data: Dict[str, Any],
        market_context: Dict[str, Any],
        user_history: Dict[str, Any]
    ) -> Optional[BiasDetection]:
        """과신 편향 감지"""
        
        try:
            evidence = []
            risk_score = 0.0
            
            # 연속 수익 거래
            consecutive_wins = user_history.get("consecutive_wins", 0)
            if consecutive_wins >= 5:
                evidence.append(f"연속 {consecutive_wins}회 수익")
                risk_score += 30
            
            # 포지션 크기 급증
            avg_position_size = user_history.get("avg_position_size", 100000)
            current_position = decision_data.get("order_amount", 0)
            if current_position > avg_position_size * 2:
                size_ratio = current_position / avg_position_size
                evidence.append(f"평소 {size_ratio:.1f}배 포지션 크기")
                risk_score += 25
            
            # 거래 빈도 증가
            recent_trades = user_history.get("trades_last_7d", 0)
            avg_trades = user_history.get("avg_trades_per_week", 1)
            if recent_trades > avg_trades * 3:
                evidence.append(f"거래 빈도 {recent_trades/avg_trades:.1f}배 증가")
                risk_score += 20
            
            # 높은 기대 수익률
            expected_return = decision_data.get("expected_return", 0)
            if expected_return > 0.5:  # 50% 이상 기대
                evidence.append(f"비현실적 기대수익률 {expected_return*100:.1f}%")
                risk_score += 15
            
            # 리스크 관리 무시
            stop_loss = decision_data.get("has_stop_loss", True)
            if not stop_loss:
                evidence.append("손절매 설정 없음")
                risk_score += 10
            
            # 편향 수준 결정
            if risk_score >= 70:
                level = BiasLevel.CRITICAL
            elif risk_score >= 50:
                level = BiasLevel.HIGH
            elif risk_score >= 30:
                level = BiasLevel.MEDIUM
            else:
                return None
            
            return BiasDetection(
                bias_type=BiasType.OVERCONFIDENCE,
                level=level,
                confidence=min(risk_score / 100, 0.9),
                evidence=evidence,
                risk_score=risk_score,
                detected_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"과신 편향 감지 실패: {e}")
            return None
    
    def _detect_loss_aversion(
        self,
        decision_data: Dict[str, Any],
        market_context: Dict[str, Any],
        user_history: Dict[str, Any]
    ) -> Optional[BiasDetection]:
        """손실 회피 편향 감지"""
        
        try:
            evidence = []
            risk_score = 0.0
            
            # 장기간 손실 포지션 보유
            holding_positions = user_history.get("current_positions", [])
            for position in holding_positions:
                unrealized_loss = position.get("unrealized_pnl_pct", 0)
                holding_days = position.get("holding_days", 0)
                
                if unrealized_loss < -0.20 and holding_days > 30:  # 20% 이상 손실, 30일 이상
                    evidence.append(f"{position.get('asset')} {holding_days}일간 {abs(unrealized_loss)*100:.1f}% 손실 보유")
                    risk_score += 30
                
                if unrealized_loss < -0.30 and holding_days > 60:  # 더 심각한 경우
                    risk_score += 20
            
            # 손절매 회피 패턴
            stop_loss_hits = user_history.get("stop_loss_triggered_count", 0)
            total_loss_trades = user_history.get("total_loss_trades", 1)
            if total_loss_trades > 5 and stop_loss_hits / total_loss_trades < 0.1:
                evidence.append("손절매 회피 패턴 (자동 손절 비율 매우 낮음)")
                risk_score += 25
            
            # 평균 손실 크기
            avg_loss_pct = user_history.get("avg_loss_percentage", 0)
            if avg_loss_pct > 0.25:  # 평균 25% 이상 손실
                evidence.append(f"평균 손실률 {avg_loss_pct*100:.1f}% (과도함)")
                risk_score += 20
            
            # 현재 의사결정이 손실 회피인지
            if decision_data.get("order_side") == "hold" and decision_data.get("unrealized_pnl_pct", 0) < -0.15:
                evidence.append("15% 이상 손실 상황에서 보유 지속 결정")
                risk_score += 15
            
            # 편향 수준 결정
            if risk_score >= 60:
                level = BiasLevel.HIGH
            elif risk_score >= 40:
                level = BiasLevel.MEDIUM
            elif risk_score >= 20:
                level = BiasLevel.LOW
            else:
                return None
            
            return BiasDetection(
                bias_type=BiasType.LOSS_AVERSION,
                level=level,
                confidence=min(risk_score / 100, 0.85),
                evidence=evidence,
                risk_score=risk_score,
                detected_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"손실 회피 편향 감지 실패: {e}")
            return None
    
    def _detect_anchoring(
        self,
        decision_data: Dict[str, Any],
        market_context: Dict[str, Any],
        user_history: Dict[str, Any]
    ) -> Optional[BiasDetection]:
        """앵커링 편향 감지"""
        
        try:
            evidence = []
            risk_score = 0.0
            
            # 과거 최고가 기준 참조
            current_price = market_context.get("current_price", 0)
            all_time_high = market_context.get("all_time_high", current_price)
            
            if all_time_high > current_price * 2:  # 최고가가 현재의 2배 이상
                ath_ratio = all_time_high / current_price
                evidence.append(f"최고가 대비 {(1-1/ath_ratio)*100:.1f}% 하락 상태")
                risk_score += 20
                
                # 목표가가 최고가 근처인지
                target_price = decision_data.get("target_price", 0)
                if target_price > current_price * 1.5:  # 50% 이상 상승 기대
                    evidence.append(f"현재가 대비 {(target_price/current_price-1)*100:.1f}% 상승 기대")
                    risk_score += 25
            
            # 매수가 기준 앵커링
            user_positions = user_history.get("current_positions", [])
            for position in user_positions:
                entry_price = position.get("entry_price", 0)
                if entry_price > current_price * 1.3:  # 매수가가 현재가의 1.3배 이상
                    evidence.append(f"높은 매수가({entry_price:,.0f}) 기준 판단 가능성")
                    risk_score += 15
            
            # 라운드 넘버 앵커링
            if current_price > 10000:  # 만원 이상일 때
                round_number_distance = abs(current_price % 10000) / 10000
                if round_number_distance < 0.05:  # 라운드 넘버 5% 이내
                    evidence.append(f"라운드 넘버({int(current_price//10000)*10000:,}) 근처에서 결정")
                    risk_score += 10
            
            # 최근 가격 변동 무시
            price_trend_7d = market_context.get("price_trend_7d", "neutral")
            if price_trend_7d == "downward" and decision_data.get("order_side") == "buy":
                evidence.append("하락 추세 무시하고 매수 결정 (앵커링 가능성)")
                risk_score += 15
            
            # 편향 수준 결정
            if risk_score >= 50:
                level = BiasLevel.HIGH
            elif risk_score >= 30:
                level = BiasLevel.MEDIUM
            elif risk_score >= 15:
                level = BiasLevel.LOW
            else:
                return None
            
            return BiasDetection(
                bias_type=BiasType.ANCHORING,
                level=level,
                confidence=min(risk_score / 80, 0.8),  # 앵커링은 확실성이 낮음
                evidence=evidence,
                risk_score=risk_score,
                detected_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"앵커링 편향 감지 실패: {e}")
            return None
    
    def _detect_herding(
        self,
        decision_data: Dict[str, Any],
        market_context: Dict[str, Any],
        user_history: Dict[str, Any]
    ) -> Optional[BiasDetection]:
        """군중 심리 편향 감지"""
        
        try:
            evidence = []
            risk_score = 0.0
            
            # 소셜 미디어 센티먼트와 동일한 방향
            social_sentiment = market_context.get("social_sentiment", 0.5)
            order_side = decision_data.get("order_side")
            
            if social_sentiment > 0.8 and order_side == "buy":
                evidence.append("소셜 미디어 극도 낙관과 동일한 매수 결정")
                risk_score += 30
            elif social_sentiment < 0.2 and order_side == "sell":
                evidence.append("소셜 미디어 극도 비관과 동일한 매도 결정")
                risk_score += 30
            
            # 거래량 급증 시 동참
            volume_surge = market_context.get("volume_surge", 1.0)
            if volume_surge > 3.0:
                evidence.append(f"거래량 {volume_surge:.1f}배 급증 시 거래 동참")
                risk_score += 20
            
            # 뉴스/이벤트 직후 거래
            news_impact = market_context.get("news_impact_score", 0)  # -1 to 1
            decision_delay = decision_data.get("time_since_news_minutes", 1440)  # 기본 24시간
            
            if abs(news_impact) > 0.7 and decision_delay < 60:  # 1시간 이내
                evidence.append("중대 뉴스 직후 즉석 거래 (군중 심리 가능성)")
                risk_score += 25
            
            # 인플루언서 의견과 동일
            influencer_sentiment = market_context.get("influencer_sentiment", 0.5)
            if (influencer_sentiment > 0.8 and order_side == "buy") or \
               (influencer_sentiment < 0.2 and order_side == "sell"):
                evidence.append("인플루언서 의견과 동일한 방향 거래")
                risk_score += 15
            
            # 독립적 분석 부재
            has_analysis = decision_data.get("has_independent_analysis", True)
            if not has_analysis:
                evidence.append("독립적 분석 없이 거래 결정")
                risk_score += 20
            
            # 편향 수준 결정
            if risk_score >= 60:
                level = BiasLevel.HIGH
            elif risk_score >= 40:
                level = BiasLevel.MEDIUM
            elif risk_score >= 20:
                level = BiasLevel.LOW
            else:
                return None
            
            return BiasDetection(
                bias_type=BiasType.HERDING,
                level=level,
                confidence=min(risk_score / 100, 0.85),
                evidence=evidence,
                risk_score=risk_score,
                detected_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"군중 심리 감지 실패: {e}")
            return None
    
    def apply_prevention_measures(
        self, 
        biases: List[BiasDetection],
        original_decision: Dict[str, Any]
    ) -> Dict[str, Any]:
        """방지 조치 적용"""
        
        try:
            prevention_result = {
                "decision_modified": False,
                "actions_taken": [],
                "warnings": [],
                "modified_decision": original_decision.copy(),
                "requires_confirmation": False,
                "cooling_period_applied": False
            }
            
            # 편향별 방지 조치 적용
            for bias in sorted(biases, key=lambda x: x.risk_score, reverse=True):
                measures = self._get_prevention_measures(bias)
                
                for action in measures:
                    if action == PreventionAction.BLOCK_ORDER:
                        prevention_result["modified_decision"]["blocked"] = True
                        prevention_result["decision_modified"] = True
                        prevention_result["actions_taken"].append("주문 차단")
                        
                    elif action == PreventionAction.DELAY_EXECUTION:
                        delay_minutes = self._calculate_delay(bias.level)
                        prevention_result["modified_decision"]["delay_minutes"] = delay_minutes
                        prevention_result["decision_modified"] = True
                        prevention_result["actions_taken"].append(f"{delay_minutes}분 지연")
                        
                    elif action == PreventionAction.REQUIRE_CONFIRMATION:
                        prevention_result["requires_confirmation"] = True
                        prevention_result["warnings"].append(
                            f"{bias.bias_type.value} 편향 감지: 신중한 확인이 필요합니다"
                        )
                        
                    elif action == PreventionAction.REDUCE_AMOUNT:
                        reduction_rate = self._calculate_reduction_rate(bias.level)
                        original_amount = original_decision.get("order_amount", 0)
                        reduced_amount = original_amount * (1 - reduction_rate)
                        prevention_result["modified_decision"]["order_amount"] = reduced_amount
                        prevention_result["decision_modified"] = True
                        prevention_result["actions_taken"].append(
                            f"주문 금액 {reduction_rate*100:.0f}% 축소"
                        )
                        
                    elif action == PreventionAction.WARN_USER:
                        warning_msg = self._generate_warning_message(bias)
                        prevention_result["warnings"].append(warning_msg)
                        
                    elif action == PreventionAction.COOLING_PERIOD:
                        cooling_hours = self._calculate_cooling_period(bias.level)
                        self.cooling_periods[bias.bias_type.value] = (
                            datetime.now() + timedelta(hours=cooling_hours)
                        )
                        prevention_result["cooling_period_applied"] = True
                        prevention_result["actions_taken"].append(f"{cooling_hours}시간 쿨링 기간")
            
            # 이벤트 기록
            for bias in biases:
                event = BiasEvent(
                    event_id=f"{bias.bias_type.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    bias_type=bias.bias_type,
                    level=bias.level,
                    triggered_at=bias.detected_at,
                    original_decision=original_decision.copy(),
                    prevented_actions=[action for action in PreventionAction 
                                     if action.value in prevention_result["actions_taken"]]
                )
                self.bias_history.append(event)
            
            logger.info(f"편향 방지 조치 적용: {len(prevention_result['actions_taken'])}개 조치")
            return prevention_result
            
        except Exception as e:
            logger.error(f"편향 방지 조치 적용 실패: {e}")
            return {
                "decision_modified": False,
                "actions_taken": [],
                "warnings": [f"편향 방지 시스템 오류: {e}"],
                "modified_decision": original_decision,
                "requires_confirmation": False,
                "cooling_period_applied": False
            }
    
    def _get_prevention_measures(self, bias: BiasDetection) -> List[PreventionAction]:
        """편향별 방지 조치 결정"""
        
        measures = []
        
        if bias.bias_type == BiasType.FOMO:
            if bias.level == BiasLevel.CRITICAL:
                measures = [PreventionAction.DELAY_EXECUTION, PreventionAction.REDUCE_AMOUNT, 
                           PreventionAction.REQUIRE_CONFIRMATION]
            elif bias.level == BiasLevel.HIGH:
                measures = [PreventionAction.DELAY_EXECUTION, PreventionAction.WARN_USER]
            else:
                measures = [PreventionAction.WARN_USER]
                
        elif bias.bias_type == BiasType.PANIC_SELLING:
            if bias.level == BiasLevel.CRITICAL:
                measures = [PreventionAction.BLOCK_ORDER, PreventionAction.COOLING_PERIOD]
            elif bias.level == BiasLevel.HIGH:
                measures = [PreventionAction.DELAY_EXECUTION, PreventionAction.REQUIRE_CONFIRMATION]
            else:
                measures = [PreventionAction.WARN_USER]
                
        elif bias.bias_type == BiasType.OVERCONFIDENCE:
            measures = [PreventionAction.REDUCE_AMOUNT, PreventionAction.WARN_USER, 
                       PreventionAction.COOLING_PERIOD]
                       
        else:  # 기타 편향들
            if bias.level in [BiasLevel.CRITICAL, BiasLevel.HIGH]:
                measures = [PreventionAction.WARN_USER, PreventionAction.REQUIRE_CONFIRMATION]
            else:
                measures = [PreventionAction.WARN_USER]
        
        return measures
    
    def _calculate_delay(self, level: BiasLevel) -> int:
        """지연 시간 계산 (분)"""
        delay_map = {
            BiasLevel.LOW: 5,
            BiasLevel.MEDIUM: 15,
            BiasLevel.HIGH: 30,
            BiasLevel.CRITICAL: 60
        }
        return delay_map.get(level, 15)
    
    def _calculate_reduction_rate(self, level: BiasLevel) -> float:
        """금액 축소율 계산"""
        reduction_map = {
            BiasLevel.LOW: 0.1,      # 10% 축소
            BiasLevel.MEDIUM: 0.25,  # 25% 축소
            BiasLevel.HIGH: 0.4,     # 40% 축소
            BiasLevel.CRITICAL: 0.6  # 60% 축소
        }
        return reduction_map.get(level, 0.25)
    
    def _calculate_cooling_period(self, level: BiasLevel) -> int:
        """쿨링 기간 계산 (시간)"""
        cooling_map = {
            BiasLevel.LOW: 1,
            BiasLevel.MEDIUM: 4,
            BiasLevel.HIGH: 12,
            BiasLevel.CRITICAL: 24
        }
        return cooling_map.get(level, 4)
    
    def _generate_warning_message(self, bias: BiasDetection) -> str:
        """경고 메시지 생성"""
        
        bias_messages = {
            BiasType.FOMO: "급등 상황에서 FOMO(기회상실 공포)가 감지되었습니다. 신중한 판단이 필요합니다.",
            BiasType.PANIC_SELLING: "급락 상황에서 공황 매도 심리가 감지되었습니다. 감정적 매도를 피하세요.",
            BiasType.OVERCONFIDENCE: "연승 이후 과신 편향이 감지되었습니다. 리스크 관리를 재점검하세요.",
            BiasType.LOSS_AVERSION: "손실 회피 편향이 감지되었습니다. 손절매 규칙을 재검토하세요.",
            BiasType.ANCHORING: "과거 가격에 대한 앵커링 편향 가능성이 있습니다. 현재 시장 상황을 재평가하세요.",
            BiasType.HERDING: "군중 심리를 따라가는 패턴이 감지되었습니다. 독립적 분석을 권장합니다."
        }
        
        base_message = bias_messages.get(bias.bias_type, "심리적 편향이 감지되었습니다.")
        evidence_text = " | ".join(bias.evidence[:2])  # 주요 근거 2개만
        
        return f"{base_message} 근거: {evidence_text}"
    
    def get_bias_statistics(self) -> Dict[str, Any]:
        """편향 통계"""
        
        try:
            if not self.bias_history:
                return {"total_events": 0}
            
            # 편향 유형별 통계
            type_counts = {}
            level_counts = {}
            
            for event in self.bias_history:
                bias_type = event.bias_type.value
                level = event.level.value
                
                type_counts[bias_type] = type_counts.get(bias_type, 0) + 1
                level_counts[level] = level_counts.get(level, 0) + 1
            
            # 방지 효과 통계
            prevented_count = len([e for e in self.bias_history if e.prevented_actions])
            override_count = len([e for e in self.bias_history if e.user_override])
            
            # 최근 7일 편향 발생 빈도
            recent_events = [
                e for e in self.bias_history 
                if (datetime.now() - e.triggered_at).days <= 7
            ]
            
            return {
                "total_events": len(self.bias_history),
                "recent_7d_events": len(recent_events),
                "bias_type_distribution": type_counts,
                "severity_distribution": level_counts,
                "prevention_rate": prevented_count / len(self.bias_history) if self.bias_history else 0,
                "user_override_rate": override_count / len(self.bias_history) if self.bias_history else 0,
                "active_cooling_periods": len([
                    cp for cp in self.cooling_periods.values() 
                    if cp > datetime.now()
                ])
            }
            
        except Exception as e:
            logger.error(f"편향 통계 계산 실패: {e}")
            return {"error": str(e)}
    
    def is_in_cooling_period(self, bias_type: BiasType) -> Tuple[bool, Optional[datetime]]:
        """쿨링 기간 확인"""
        
        bias_key = bias_type.value
        if bias_key in self.cooling_periods:
            cooling_end = self.cooling_periods[bias_key]
            if datetime.now() < cooling_end:
                return True, cooling_end
            else:
                # 만료된 쿨링 기간 제거
                del self.cooling_periods[bias_key]
        
        return False, None