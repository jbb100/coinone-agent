"""
Scenario Response System 테스트 모듈

시나리오별 대응 전략 시스템 테스트
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.core.scenario_response_system import (
    ScenarioResponseSystem,
    ScenarioType,
    ScenarioSeverity,
    ResponseAction,
    ScenarioTrigger,
    ScenarioResponse,
    ScenarioEvent
)


class TestScenarioType:
    """ScenarioType Enum 테스트"""

    def test_scenario_types_exist(self):
        """모든 시나리오 유형 존재 확인"""
        assert ScenarioType.BLACK_SWAN.value == "black_swan"
        assert ScenarioType.REGULATION_RISK.value == "regulation_risk"
        assert ScenarioType.ALT_SEASON.value == "alt_season"
        assert ScenarioType.MARKET_CRASH.value == "market_crash"
        assert ScenarioType.EUPHORIA.value == "euphoria"
        assert ScenarioType.STABLECOIN_DEPEG.value == "stablecoin_depeg"
        assert ScenarioType.EXCHANGE_RISK.value == "exchange_risk"
        assert ScenarioType.MACRO_SHOCK.value == "macro_shock"

    def test_scenario_type_count(self):
        """시나리오 유형 개수 확인"""
        assert len(ScenarioType) == 8


class TestScenarioSeverity:
    """ScenarioSeverity Enum 테스트"""

    def test_severity_levels_exist(self):
        """모든 심각도 레벨 존재 확인"""
        assert ScenarioSeverity.LOW.value == "low"
        assert ScenarioSeverity.MEDIUM.value == "medium"
        assert ScenarioSeverity.HIGH.value == "high"
        assert ScenarioSeverity.CRITICAL.value == "critical"

    def test_severity_count(self):
        """심각도 레벨 개수 확인"""
        assert len(ScenarioSeverity) == 4


class TestResponseAction:
    """ResponseAction Enum 테스트"""

    def test_response_actions_exist(self):
        """모든 대응 행동 존재 확인"""
        assert ResponseAction.HOLD.value == "hold"
        assert ResponseAction.DEFENSIVE_REBALANCE.value == "defensive_rebalance"
        assert ResponseAction.EMERGENCY_DCA.value == "emergency_dca"
        assert ResponseAction.RISK_OFF.value == "risk_off"
        assert ResponseAction.OPPORTUNISTIC_BUY.value == "opportunistic_buy"
        assert ResponseAction.SATELLITE_BOOST.value == "satellite_boost"
        assert ResponseAction.IMMEDIATE_SELL.value == "immediate_sell"

    def test_response_action_count(self):
        """대응 행동 개수 확인"""
        assert len(ResponseAction) == 7


class TestScenarioTrigger:
    """ScenarioTrigger 데이터클래스 테스트"""

    def test_trigger_creation(self):
        """트리거 생성 테스트"""
        trigger = ScenarioTrigger(
            trigger_id="test_trigger",
            scenario_type=ScenarioType.BLACK_SWAN,
            condition_func=lambda data: data.get("test", False),
            description="테스트 트리거",
            severity_func=lambda data: ScenarioSeverity.HIGH,
            cooldown_hours=24
        )

        assert trigger.trigger_id == "test_trigger"
        assert trigger.scenario_type == ScenarioType.BLACK_SWAN
        assert trigger.cooldown_hours == 24

    def test_trigger_condition_func(self):
        """트리거 조건 함수 테스트"""
        trigger = ScenarioTrigger(
            trigger_id="test",
            scenario_type=ScenarioType.MARKET_CRASH,
            condition_func=lambda data: data.get("price_drop", 0) < -0.20,
            description="가격 하락 트리거",
            severity_func=lambda data: ScenarioSeverity.HIGH
        )

        # 조건 만족
        assert trigger.condition_func({"price_drop": -0.25}) is True
        # 조건 불만족
        assert trigger.condition_func({"price_drop": -0.10}) is False


class TestScenarioResponse:
    """ScenarioResponse 데이터클래스 테스트"""

    def test_response_creation(self):
        """대응 전략 생성 테스트"""
        response = ScenarioResponse(
            scenario_type=ScenarioType.BLACK_SWAN,
            severity=ScenarioSeverity.CRITICAL,
            recommended_actions=[ResponseAction.EMERGENCY_DCA, ResponseAction.RISK_OFF],
            target_allocation={"crypto": 0.40, "krw": 0.60},
            execution_priority=10,
            risk_adjustment=-0.4,
            reasoning="블랙스완 대응",
            confidence=0.9,
            estimated_duration=timedelta(days=7)
        )

        assert response.scenario_type == ScenarioType.BLACK_SWAN
        assert response.severity == ScenarioSeverity.CRITICAL
        assert len(response.recommended_actions) == 2
        assert response.execution_priority == 10
        assert response.confidence == 0.9


class TestScenarioEvent:
    """ScenarioEvent 데이터클래스 테스트"""

    def test_event_creation(self):
        """이벤트 생성 테스트"""
        event = ScenarioEvent(
            event_id="event_001",
            scenario_type=ScenarioType.REGULATION_RISK,
            severity=ScenarioSeverity.HIGH,
            triggered_at=datetime.now()
        )

        assert event.event_id == "event_001"
        assert event.scenario_type == ScenarioType.REGULATION_RISK
        assert event.resolved_at is None
        assert event.response_taken is None

    def test_event_with_trigger_data(self):
        """트리거 데이터 포함 이벤트"""
        event = ScenarioEvent(
            event_id="event_002",
            scenario_type=ScenarioType.MARKET_CRASH,
            severity=ScenarioSeverity.CRITICAL,
            triggered_at=datetime.now(),
            trigger_data={"price_change_24h": -0.35, "volume_surge": 4.0}
        )

        assert event.trigger_data["price_change_24h"] == -0.35


class TestScenarioResponseSystem:
    """ScenarioResponseSystem 클래스 테스트"""

    @pytest.fixture
    def system(self):
        """ScenarioResponseSystem 인스턴스"""
        return ScenarioResponseSystem()

    def test_init(self, system):
        """초기화 테스트"""
        assert system.active_scenarios == []
        assert system.scenario_history == []
        assert system.trigger_cooldowns == {}
        assert len(system.triggers) > 0
        assert len(system.response_strategies) > 0

    def test_triggers_initialized(self, system):
        """트리거 초기화 확인"""
        trigger_ids = [t.trigger_id for t in system.triggers]

        assert "black_swan_crash" in trigger_ids
        assert "regulation_news" in trigger_ids

    def test_response_strategies_initialized(self, system):
        """대응 전략 초기화 확인"""
        # 블랙스완 대응 전략 존재
        assert ScenarioType.BLACK_SWAN in system.response_strategies
        assert ScenarioSeverity.HIGH in system.response_strategies[ScenarioType.BLACK_SWAN]
        assert ScenarioSeverity.CRITICAL in system.response_strategies[ScenarioType.BLACK_SWAN]

        # 규제 리스크 대응 전략 존재
        assert ScenarioType.REGULATION_RISK in system.response_strategies

    def test_detect_scenarios_black_swan(self, system):
        """블랙스완 시나리오 감지"""
        market_data = {
            "price_change_24h": -0.35,  # -35% 하락
            "volume_surge": 4.0         # 4배 거래량 증가
        }

        detected = system.detect_scenarios(market_data)

        # 블랙스완 감지됨
        assert any(e.scenario_type == ScenarioType.BLACK_SWAN for e in detected)

    def test_detect_scenarios_no_trigger(self, system):
        """시나리오 미감지 (정상 시장)"""
        market_data = {
            "price_change_24h": 0.02,  # +2% 상승
            "volume_surge": 1.0        # 정상 거래량
        }

        detected = system.detect_scenarios(market_data)

        assert len(detected) == 0

    def test_detect_scenarios_cooldown(self, system):
        """쿨다운 중 시나리오 재감지 방지"""
        market_data = {
            "price_change_24h": -0.35,
            "volume_surge": 4.0
        }

        # 첫 번째 감지
        detected1 = system.detect_scenarios(market_data)
        assert len(detected1) > 0

        # 두 번째 감지 (쿨다운 중)
        detected2 = system.detect_scenarios(market_data)
        # 쿨다운 중이면 같은 트리거는 발동하지 않음
        assert len(detected2) < len(detected1) or len(detected2) == 0

    def test_detect_scenarios_regulation_risk(self, system):
        """규제 리스크 시나리오 감지"""
        market_data = {
            "regulation_sentiment": -0.8,  # 강한 부정적 뉴스
            "price_change_1h": -0.12       # 1시간 -12% 하락
        }

        detected = system.detect_scenarios(market_data)

        assert any(e.scenario_type == ScenarioType.REGULATION_RISK for e in detected)

    def test_detect_scenarios_market_crash(self, system):
        """시장 크래시 시나리오 감지"""
        # 실제 조건: price_change_7d < -0.40, fear_greed_index < 20, liquidations_24h > 1B
        market_data = {
            "price_change_7d": -0.45,        # 7일간 -45% 하락
            "fear_greed_index": 15,          # 극단적 공포 (20 미만)
            "liquidations_24h": 2_000_000_000  # 20억달러 청산
        }

        detected = system.detect_scenarios(market_data)

        assert any(e.scenario_type == ScenarioType.MARKET_CRASH for e in detected)

    def test_detect_scenarios_euphoria(self, system):
        """시장 과열 시나리오 감지"""
        # 실제 조건: price_change_30d > 1.0 (100%), fear_greed_index > 80, funding_rate > 0.01
        market_data = {
            "price_change_30d": 1.2,     # 30일간 +120% 상승
            "fear_greed_index": 90,      # 극단적 탐욕
            "funding_rate": 0.02         # 높은 펀딩비율
        }

        detected = system.detect_scenarios(market_data)

        assert any(e.scenario_type == ScenarioType.EUPHORIA for e in detected)

    def test_detect_scenarios_stablecoin_depeg(self, system):
        """스테이블코인 디페깅 시나리오 감지"""
        market_data = {
            "usdt_price": 0.97,                   # USDT 디페그
            "stablecoin_outflow": 6_000_000_000   # 60억 달러 유출
        }

        detected = system.detect_scenarios(market_data)

        assert any(e.scenario_type == ScenarioType.STABLECOIN_DEPEG for e in detected)


class TestScenarioResponseSystemStrategies:
    """ScenarioResponseSystem 대응 전략 테스트"""

    @pytest.fixture
    def system(self):
        """ScenarioResponseSystem 인스턴스"""
        return ScenarioResponseSystem()

    def test_black_swan_high_response(self, system):
        """블랙스완 HIGH 대응 전략"""
        response = system.response_strategies[ScenarioType.BLACK_SWAN][ScenarioSeverity.HIGH]

        assert ResponseAction.EMERGENCY_DCA in response.recommended_actions
        assert response.target_allocation["crypto"] == 0.60
        assert response.execution_priority == 9

    def test_black_swan_critical_response(self, system):
        """블랙스완 CRITICAL 대응 전략"""
        response = system.response_strategies[ScenarioType.BLACK_SWAN][ScenarioSeverity.CRITICAL]

        assert ResponseAction.RISK_OFF in response.recommended_actions
        assert response.target_allocation["crypto"] == 0.40
        assert response.execution_priority == 10

    def test_regulation_risk_response(self, system):
        """규제 리스크 대응 전략"""
        response = system.response_strategies[ScenarioType.REGULATION_RISK][ScenarioSeverity.HIGH]

        assert ResponseAction.RISK_OFF in response.recommended_actions
        assert response.target_allocation["crypto"] == 0.25
        assert response.risk_adjustment == -0.5

    def test_alt_season_response(self, system):
        """알트시즌 대응 전략"""
        response = system.response_strategies[ScenarioType.ALT_SEASON][ScenarioSeverity.MEDIUM]

        assert ResponseAction.SATELLITE_BOOST in response.recommended_actions
        assert response.target_allocation["crypto"] == 0.75
        assert response.risk_adjustment == 0.2

    def test_market_crash_critical_response(self, system):
        """시장 크래시 CRITICAL 대응 전략"""
        response = system.response_strategies[ScenarioType.MARKET_CRASH][ScenarioSeverity.CRITICAL]

        assert ResponseAction.RISK_OFF in response.recommended_actions
        assert ResponseAction.HOLD in response.recommended_actions
        assert response.target_allocation["crypto"] == 0.30

    def test_euphoria_response(self, system):
        """시장 과열 대응 전략"""
        response = system.response_strategies[ScenarioType.EUPHORIA][ScenarioSeverity.HIGH]

        assert ResponseAction.DEFENSIVE_REBALANCE in response.recommended_actions
        assert response.target_allocation["crypto"] == 0.40

    def test_macro_shock_response(self, system):
        """매크로 충격 대응 전략"""
        response = system.response_strategies[ScenarioType.MACRO_SHOCK][ScenarioSeverity.HIGH]

        assert ResponseAction.RISK_OFF in response.recommended_actions
        assert response.target_allocation["crypto"] == 0.35


class TestScenarioResponseSystemEdgeCases:
    """ScenarioResponseSystem 엣지 케이스 테스트"""

    @pytest.fixture
    def system(self):
        """ScenarioResponseSystem 인스턴스"""
        return ScenarioResponseSystem()

    def test_detect_scenarios_empty_data(self, system):
        """빈 데이터로 시나리오 감지"""
        detected = system.detect_scenarios({})

        assert detected == []

    def test_detect_scenarios_partial_data(self, system):
        """일부 데이터만 있을 때"""
        market_data = {
            "price_change_24h": -0.35
            # volume_surge 누락
        }

        detected = system.detect_scenarios(market_data)

        # 조건을 완전히 만족하지 않으면 감지 안됨
        assert not any(e.scenario_type == ScenarioType.BLACK_SWAN for e in detected)

    def test_detect_scenarios_invalid_values(self, system):
        """유효하지 않은 값"""
        market_data = {
            "price_change_24h": "invalid",
            "volume_surge": None
        }

        # 에러 없이 처리됨
        detected = system.detect_scenarios(market_data)
        assert isinstance(detected, list)

    def test_multiple_scenarios_detected(self, system):
        """여러 시나리오 동시 감지"""
        market_data = {
            "price_change_24h": -0.35,
            "volume_surge": 4.0,
            "fear_greed_index": 10,
            "usdt_price": 0.97,
            "stablecoin_outflow": 6_000_000_000
        }

        detected = system.detect_scenarios(market_data)

        # 여러 시나리오가 동시에 감지될 수 있음
        scenario_types = [e.scenario_type for e in detected]
        assert len(set(scenario_types)) >= 1  # 최소 1개 이상 고유 시나리오

    def test_severity_determination(self, system):
        """심각도 결정 테스트"""
        # CRITICAL 수준 블랙스완
        market_data_critical = {
            "price_change_24h": -0.55,  # -55% (임계값 -50% 초과)
            "volume_surge": 5.0
        }

        detected = system.detect_scenarios(market_data_critical)
        black_swan_events = [e for e in detected if e.scenario_type == ScenarioType.BLACK_SWAN]

        if black_swan_events:
            assert black_swan_events[0].severity == ScenarioSeverity.CRITICAL


class TestGenerateResponse:
    """generate_response 메서드 테스트"""

    @pytest.fixture
    def system(self):
        return ScenarioResponseSystem()

    def test_generate_response_black_swan_high(self, system):
        """블랙스완 HIGH 대응 생성"""
        event = ScenarioEvent(
            event_id="test_bs",
            scenario_type=ScenarioType.BLACK_SWAN,
            severity=ScenarioSeverity.HIGH,
            triggered_at=datetime.now(),
            trigger_data={}
        )

        response = system.generate_response(event)

        assert response is not None
        assert response.scenario_type == ScenarioType.BLACK_SWAN
        assert ResponseAction.EMERGENCY_DCA in response.recommended_actions

    def test_generate_response_black_swan_critical(self, system):
        """블랙스완 CRITICAL 대응 생성"""
        event = ScenarioEvent(
            event_id="test_bs_crit",
            scenario_type=ScenarioType.BLACK_SWAN,
            severity=ScenarioSeverity.CRITICAL,
            triggered_at=datetime.now(),
            trigger_data={}
        )

        response = system.generate_response(event)

        assert response is not None
        assert ResponseAction.RISK_OFF in response.recommended_actions

    def test_generate_response_market_crash(self, system):
        """시장 크래시 대응 생성"""
        event = ScenarioEvent(
            event_id="test_mc",
            scenario_type=ScenarioType.MARKET_CRASH,
            severity=ScenarioSeverity.CRITICAL,
            triggered_at=datetime.now(),
            trigger_data={}
        )

        response = system.generate_response(event)

        assert response is not None
        assert ResponseAction.RISK_OFF in response.recommended_actions

    def test_generate_response_alt_season(self, system):
        """알트시즌 대응 생성"""
        event = ScenarioEvent(
            event_id="test_as",
            scenario_type=ScenarioType.ALT_SEASON,
            severity=ScenarioSeverity.MEDIUM,
            triggered_at=datetime.now(),
            trigger_data={}
        )

        response = system.generate_response(event)

        assert response is not None
        assert ResponseAction.SATELLITE_BOOST in response.recommended_actions

    def test_generate_response_undefined_scenario(self, system):
        """정의되지 않은 시나리오는 None 반환"""
        event = ScenarioEvent(
            event_id="test_ex",
            scenario_type=ScenarioType.EXCHANGE_RISK,
            severity=ScenarioSeverity.HIGH,
            triggered_at=datetime.now(),
            trigger_data={}
        )

        response = system.generate_response(event)

        assert response is None

    def test_generate_response_fallback_severity(self, system):
        """정확한 심각도 없으면 가장 가까운 심각도 사용"""
        event = ScenarioEvent(
            event_id="test_low",
            scenario_type=ScenarioType.ALT_SEASON,
            severity=ScenarioSeverity.LOW,
            triggered_at=datetime.now(),
            trigger_data={}
        )

        response = system.generate_response(event)

        # LOW가 없으면 MEDIUM으로 폴백
        assert response is not None


class TestAdjustResponseForContext:
    """_adjust_response_for_context 메서드 테스트"""

    @pytest.fixture
    def system(self):
        return ScenarioResponseSystem()

    @pytest.fixture
    def base_response(self):
        return ScenarioResponse(
            scenario_type=ScenarioType.MARKET_CRASH,
            severity=ScenarioSeverity.HIGH,
            recommended_actions=[ResponseAction.EMERGENCY_DCA],
            target_allocation={"crypto": 0.5, "krw": 0.5},
            execution_priority=7,
            risk_adjustment=-0.2,
            reasoning="Base response",
            confidence=0.8,
            estimated_duration=timedelta(days=7)
        )

    def test_low_liquidity_adjustment(self, system, base_response):
        """낮은 유동성 환경 조정"""
        context = {"liquidity_score": 0.2}

        adjusted = system._adjust_response_for_context(base_response, context)

        assert adjusted.risk_adjustment < base_response.risk_adjustment
        assert adjusted.confidence < base_response.confidence
        assert "낮은 유동성" in adjusted.reasoning

    def test_high_volatility_adjustment(self, system, base_response):
        """높은 변동성 환경 조정"""
        context = {"volatility_24h": 0.25}

        adjusted = system._adjust_response_for_context(base_response, context)

        assert adjusted.target_allocation["crypto"] < base_response.target_allocation["crypto"]

    def test_high_volume_surge_adjustment(self, system, base_response):
        """극심한 거래량 증가 조정"""
        context = {"volume_surge": 6.0}

        adjusted = system._adjust_response_for_context(base_response, context)

        assert adjusted.execution_priority > base_response.execution_priority
        assert adjusted.estimated_duration > base_response.estimated_duration

    def test_normal_context_minimal_change(self, system, base_response):
        """정상 환경에서는 변경 최소화"""
        context = {
            "liquidity_score": 0.7,
            "volatility_24h": 0.05,
            "volume_surge": 1.2
        }

        adjusted = system._adjust_response_for_context(base_response, context)

        assert adjusted.risk_adjustment == base_response.risk_adjustment
        assert adjusted.confidence == base_response.confidence


class TestExecuteScenarioResponse:
    """execute_scenario_response 메서드 테스트"""

    @pytest.fixture
    def system(self):
        return ScenarioResponseSystem()

    def test_execute_valid_scenario(self, system):
        """유효한 시나리오 대응 실행"""
        event = ScenarioEvent(
            event_id="test_exec",
            scenario_type=ScenarioType.BLACK_SWAN,
            severity=ScenarioSeverity.HIGH,
            triggered_at=datetime.now(),
            trigger_data={}
        )

        current_portfolio = {"crypto": 0.7, "krw": 0.3}

        result = system.execute_scenario_response(event, current_portfolio)

        assert result["success"] == True
        assert "execution_plan" in result
        assert event in system.active_scenarios

    def test_execute_undefined_scenario_fails(self, system):
        """정의되지 않은 시나리오 실행 실패"""
        event = ScenarioEvent(
            event_id="test_fail",
            scenario_type=ScenarioType.EXCHANGE_RISK,
            severity=ScenarioSeverity.HIGH,
            triggered_at=datetime.now(),
            trigger_data={}
        )

        result = system.execute_scenario_response(event, {})

        assert result["success"] == False
        assert "error" in result

    def test_execute_updates_event_response(self, system):
        """실행 시 이벤트에 대응 전략 저장"""
        event = ScenarioEvent(
            event_id="test_update",
            scenario_type=ScenarioType.REGULATION_RISK,
            severity=ScenarioSeverity.HIGH,
            triggered_at=datetime.now(),
            trigger_data={}
        )

        result = system.execute_scenario_response(event, {"crypto": 0.5, "krw": 0.5})

        assert result["success"] == True
        assert event.response_taken is not None


class TestCreateExecutionPlan:
    """_create_execution_plan 메서드 테스트"""

    @pytest.fixture
    def system(self):
        return ScenarioResponseSystem()

    @pytest.fixture
    def response(self):
        return ScenarioResponse(
            scenario_type=ScenarioType.MARKET_CRASH,
            severity=ScenarioSeverity.HIGH,
            recommended_actions=[ResponseAction.DEFENSIVE_REBALANCE],
            target_allocation={"crypto": 0.4, "krw": 0.6},
            execution_priority=8,
            risk_adjustment=-0.3,
            reasoning="Test",
            confidence=0.8,
            estimated_duration=timedelta(days=7)
        )

    def test_rebalancing_needed_large_diff(self, system, response):
        """큰 차이가 있으면 리밸런싱 필요"""
        current = {"crypto": 0.7, "krw": 0.3}

        plan = system._create_execution_plan(response, current)

        assert plan["rebalancing_needed"] == True
        assert "crypto" in plan["required_trades"]
        assert plan["urgency_level"] == "high"

    def test_no_rebalancing_small_diff(self, system, response):
        """차이가 작으면 리밸런싱 불필요"""
        current = {"crypto": 0.42, "krw": 0.58}

        plan = system._create_execution_plan(response, current)

        assert plan["rebalancing_needed"] == False

    def test_required_trades_calculated(self, system, response):
        """필요한 거래 계산"""
        current = {"crypto": 0.8, "krw": 0.2}

        plan = system._create_execution_plan(response, current)

        crypto_trade = plan["required_trades"]["crypto"]
        assert crypto_trade["action"] == "sell"
        assert crypto_trade["change"] < 0

    def test_medium_urgency_level(self, system):
        """중간 긴급도 레벨"""
        response = ScenarioResponse(
            scenario_type=ScenarioType.REGULATION_RISK,
            severity=ScenarioSeverity.MEDIUM,
            recommended_actions=[ResponseAction.DEFENSIVE_REBALANCE],
            target_allocation={"crypto": 0.4, "krw": 0.6},
            execution_priority=6,
            risk_adjustment=-0.2,
            reasoning="Test",
            confidence=0.7,
            estimated_duration=timedelta(days=14)
        )

        current = {"crypto": 0.7, "krw": 0.3}

        plan = system._create_execution_plan(response, current)

        assert plan["urgency_level"] == "medium"


class TestMonitorActiveScenarios:
    """monitor_active_scenarios 메서드 테스트"""

    @pytest.fixture
    def system(self):
        return ScenarioResponseSystem()

    def test_monitor_empty_scenarios(self, system):
        """활성 시나리오 없을 때"""
        results = system.monitor_active_scenarios()

        assert results == []

    def test_monitor_active_scenarios(self, system):
        """활성 시나리오 모니터링"""
        response = ScenarioResponse(
            scenario_type=ScenarioType.BLACK_SWAN,
            severity=ScenarioSeverity.HIGH,
            recommended_actions=[ResponseAction.EMERGENCY_DCA],
            target_allocation={"crypto": 0.5, "krw": 0.5},
            execution_priority=8,
            risk_adjustment=-0.3,
            reasoning="Test",
            confidence=0.8,
            estimated_duration=timedelta(hours=2)
        )

        event = ScenarioEvent(
            event_id="test_monitor",
            scenario_type=ScenarioType.BLACK_SWAN,
            severity=ScenarioSeverity.HIGH,
            triggered_at=datetime.now(),
            response_taken=response
        )

        system.active_scenarios.append(event)

        results = system.monitor_active_scenarios()

        assert len(results) == 1
        assert results[0]["scenario_id"] == "test_monitor"
        assert results[0]["scenario_type"] == "black_swan"

    def test_expired_scenario_resolved(self, system):
        """만료된 시나리오 해결 처리"""
        response = ScenarioResponse(
            scenario_type=ScenarioType.BLACK_SWAN,
            severity=ScenarioSeverity.HIGH,
            recommended_actions=[ResponseAction.EMERGENCY_DCA],
            target_allocation={"crypto": 0.5, "krw": 0.5},
            execution_priority=8,
            risk_adjustment=-0.3,
            reasoning="Test",
            confidence=0.8,
            estimated_duration=timedelta(seconds=1)
        )

        event = ScenarioEvent(
            event_id="test_expired",
            scenario_type=ScenarioType.BLACK_SWAN,
            severity=ScenarioSeverity.HIGH,
            triggered_at=datetime.now() - timedelta(hours=2),
            response_taken=response
        )

        system.active_scenarios.append(event)

        results = system.monitor_active_scenarios()

        assert len(system.active_scenarios) == 0
        assert len(system.scenario_history) == 1

    def test_monitor_without_response(self, system):
        """대응 전략 없는 이벤트 모니터링"""
        event = ScenarioEvent(
            event_id="test_no_response",
            scenario_type=ScenarioType.ALT_SEASON,
            severity=ScenarioSeverity.MEDIUM,
            triggered_at=datetime.now()
        )

        system.active_scenarios.append(event)

        results = system.monitor_active_scenarios()

        assert len(results) == 1
        assert results[0]["response_actions"] == []


class TestGetCombinedScenarioAdjustment:
    """get_combined_scenario_adjustment 메서드 테스트"""

    @pytest.fixture
    def system(self):
        return ScenarioResponseSystem()

    def test_no_active_scenarios(self, system):
        """활성 시나리오 없을 때"""
        result = system.get_combined_scenario_adjustment()

        assert result["risk_adjustment"] == 0.0
        assert result["active_scenarios_count"] == 0

    def test_single_scenario_adjustment(self, system):
        """단일 시나리오 조정"""
        response = ScenarioResponse(
            scenario_type=ScenarioType.MARKET_CRASH,
            severity=ScenarioSeverity.HIGH,
            recommended_actions=[ResponseAction.RISK_OFF],
            target_allocation={"crypto": 0.4, "krw": 0.6},
            execution_priority=8,
            risk_adjustment=-0.3,
            reasoning="Test",
            confidence=0.8,
            estimated_duration=timedelta(days=7)
        )

        event = ScenarioEvent(
            event_id="test_single",
            scenario_type=ScenarioType.MARKET_CRASH,
            severity=ScenarioSeverity.HIGH,
            triggered_at=datetime.now(),
            response_taken=response
        )

        system.active_scenarios.append(event)

        result = system.get_combined_scenario_adjustment()

        assert result["risk_adjustment"] == -0.3
        assert result["active_scenarios_count"] == 1

    def test_multiple_scenarios_weighted_average(self, system):
        """여러 시나리오 가중 평균"""
        response1 = ScenarioResponse(
            scenario_type=ScenarioType.MARKET_CRASH,
            severity=ScenarioSeverity.HIGH,
            recommended_actions=[ResponseAction.RISK_OFF],
            target_allocation={"crypto": 0.3, "krw": 0.7},
            execution_priority=8,
            risk_adjustment=-0.4,
            reasoning="Test 1",
            confidence=0.8,
            estimated_duration=timedelta(days=7)
        )

        event1 = ScenarioEvent(
            event_id="test_1",
            scenario_type=ScenarioType.MARKET_CRASH,
            severity=ScenarioSeverity.HIGH,
            triggered_at=datetime.now(),
            response_taken=response1
        )

        response2 = ScenarioResponse(
            scenario_type=ScenarioType.REGULATION_RISK,
            severity=ScenarioSeverity.MEDIUM,
            recommended_actions=[ResponseAction.DEFENSIVE_REBALANCE],
            target_allocation={"crypto": 0.5, "krw": 0.5},
            execution_priority=6,
            risk_adjustment=-0.2,
            reasoning="Test 2",
            confidence=0.7,
            estimated_duration=timedelta(days=14)
        )

        event2 = ScenarioEvent(
            event_id="test_2",
            scenario_type=ScenarioType.REGULATION_RISK,
            severity=ScenarioSeverity.MEDIUM,
            triggered_at=datetime.now(),
            response_taken=response2
        )

        system.active_scenarios.extend([event1, event2])

        result = system.get_combined_scenario_adjustment()

        assert result["active_scenarios_count"] == 2
        assert -0.4 < result["risk_adjustment"] < -0.2

    def test_scenario_without_response(self, system):
        """대응 전략 없는 시나리오는 건너뜀"""
        event = ScenarioEvent(
            event_id="test_no_resp",
            scenario_type=ScenarioType.ALT_SEASON,
            severity=ScenarioSeverity.MEDIUM,
            triggered_at=datetime.now()
        )

        system.active_scenarios.append(event)

        result = system.get_combined_scenario_adjustment()

        # 대응 없으면 기본값 반환
        assert result["risk_adjustment"] == 0.0


class TestGetScenarioStatistics:
    """get_scenario_statistics 메서드 테스트"""

    @pytest.fixture
    def system(self):
        return ScenarioResponseSystem()

    def test_empty_statistics(self, system):
        """시나리오 없을 때 통계"""
        stats = system.get_scenario_statistics()

        assert stats["total_scenarios"] == 0

    def test_statistics_with_active_scenario(self, system):
        """활성 시나리오 통계"""
        event = ScenarioEvent(
            event_id="active_1",
            scenario_type=ScenarioType.BLACK_SWAN,
            severity=ScenarioSeverity.HIGH,
            triggered_at=datetime.now()
        )

        system.active_scenarios.append(event)

        stats = system.get_scenario_statistics()

        assert stats["total_scenarios"] == 1
        assert stats["active_scenarios"] == 1
        assert stats["resolved_scenarios"] == 0

    def test_statistics_with_resolved_scenario(self, system):
        """해결된 시나리오 통계"""
        event = ScenarioEvent(
            event_id="resolved_1",
            scenario_type=ScenarioType.MARKET_CRASH,
            severity=ScenarioSeverity.CRITICAL,
            triggered_at=datetime.now() - timedelta(hours=5),
            resolved_at=datetime.now()
        )

        system.scenario_history.append(event)

        stats = system.get_scenario_statistics()

        assert stats["total_scenarios"] == 1
        assert stats["resolved_scenarios"] == 1
        assert stats["average_duration_hours"] is not None

    def test_statistics_type_distribution(self, system):
        """시나리오 유형 분포 통계"""
        event1 = ScenarioEvent(
            event_id="e1",
            scenario_type=ScenarioType.BLACK_SWAN,
            severity=ScenarioSeverity.HIGH,
            triggered_at=datetime.now()
        )

        event2 = ScenarioEvent(
            event_id="e2",
            scenario_type=ScenarioType.BLACK_SWAN,
            severity=ScenarioSeverity.CRITICAL,
            triggered_at=datetime.now()
        )

        system.active_scenarios.extend([event1, event2])

        stats = system.get_scenario_statistics()

        assert stats["scenario_type_distribution"]["black_swan"] == 2


class TestForceResolveScenario:
    """force_resolve_scenario 메서드 테스트"""

    @pytest.fixture
    def system(self):
        return ScenarioResponseSystem()

    def test_force_resolve_existing_scenario(self, system):
        """존재하는 시나리오 강제 해결"""
        event = ScenarioEvent(
            event_id="to_resolve",
            scenario_type=ScenarioType.BLACK_SWAN,
            severity=ScenarioSeverity.HIGH,
            triggered_at=datetime.now()
        )

        system.active_scenarios.append(event)

        result = system.force_resolve_scenario("to_resolve", {"reason": "manual"})

        assert result == True
        assert len(system.active_scenarios) == 0
        assert len(system.scenario_history) == 1
        assert system.scenario_history[0].outcome_data["reason"] == "manual"

    def test_force_resolve_nonexistent_scenario(self, system):
        """존재하지 않는 시나리오 해결 시도"""
        result = system.force_resolve_scenario("nonexistent")

        assert result == False

    def test_force_resolve_without_outcome_data(self, system):
        """outcome_data 없이 해결"""
        event = ScenarioEvent(
            event_id="simple_resolve",
            scenario_type=ScenarioType.REGULATION_RISK,
            severity=ScenarioSeverity.MEDIUM,
            triggered_at=datetime.now()
        )

        system.active_scenarios.append(event)

        result = system.force_resolve_scenario("simple_resolve")

        assert result == True
        assert system.scenario_history[0].resolved_at is not None

    def test_force_resolve_sets_resolved_time(self, system):
        """강제 해결 시 해결 시간 설정"""
        event = ScenarioEvent(
            event_id="time_test",
            scenario_type=ScenarioType.ALT_SEASON,
            severity=ScenarioSeverity.MEDIUM,
            triggered_at=datetime.now() - timedelta(hours=1)
        )

        system.active_scenarios.append(event)

        before_resolve = datetime.now()
        result = system.force_resolve_scenario("time_test")
        after_resolve = datetime.now()

        assert result == True
        resolved_time = system.scenario_history[0].resolved_at
        assert before_resolve <= resolved_time <= after_resolve
