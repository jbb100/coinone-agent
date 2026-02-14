"""
Resilience 테스트 모듈

서킷 브레이커, 재시도 패턴 등 시스템 복원력 테스트
"""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.core.resilience import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState
)


class TestCircuitState:
    """CircuitState Enum 테스트"""

    def test_circuit_states_exist(self):
        """모든 서킷 상태 존재 확인"""
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"

    def test_circuit_state_count(self):
        """서킷 상태 개수 확인"""
        assert len(CircuitState) == 3


class TestCircuitBreakerConfig:
    """CircuitBreakerConfig 데이터클래스 테스트"""

    def test_default_config(self):
        """기본 설정 값 확인"""
        config = CircuitBreakerConfig()

        assert config.failure_threshold == 5
        assert config.success_threshold == 2
        assert config.timeout == 60
        assert config.excluded_exceptions == ()

    def test_custom_config(self):
        """커스텀 설정"""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=1,
            timeout=30,
            excluded_exceptions=(ValueError,)
        )

        assert config.failure_threshold == 3
        assert config.success_threshold == 1
        assert config.timeout == 30
        assert ValueError in config.excluded_exceptions


class TestCircuitBreaker:
    """CircuitBreaker 클래스 테스트"""

    @pytest.fixture
    def circuit_breaker(self):
        """기본 CircuitBreaker 인스턴스"""
        return CircuitBreaker("test_breaker")

    @pytest.fixture
    def custom_breaker(self):
        """커스텀 설정 CircuitBreaker"""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=1,
            timeout=1
        )
        return CircuitBreaker("custom_breaker", config)

    def test_init(self, circuit_breaker):
        """초기화 테스트"""
        assert circuit_breaker.name == "test_breaker"
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.failure_count == 0
        assert circuit_breaker.success_count == 0
        assert circuit_breaker.last_failure_time is None

    def test_call_success(self, circuit_breaker):
        """성공적인 호출"""
        def success_func():
            return "success"

        result = circuit_breaker.call(success_func)

        assert result == "success"
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.failure_count == 0

    def test_call_with_args(self, circuit_breaker):
        """인자를 포함한 호출"""
        def add_func(a, b):
            return a + b

        result = circuit_breaker.call(add_func, 1, 2)

        assert result == 3

    def test_call_with_kwargs(self, circuit_breaker):
        """키워드 인자를 포함한 호출"""
        def greet_func(name, greeting="Hello"):
            return f"{greeting}, {name}"

        result = circuit_breaker.call(greet_func, "World", greeting="Hi")

        assert result == "Hi, World"

    def test_failure_count_increments(self, circuit_breaker):
        """실패 시 카운트 증가"""
        def fail_func():
            raise Exception("Test failure")

        with pytest.raises(Exception):
            circuit_breaker.call(fail_func)

        assert circuit_breaker.failure_count == 1
        assert circuit_breaker.state == CircuitState.CLOSED

    def test_open_after_threshold(self, custom_breaker):
        """임계값 초과 시 OPEN 상태 전환"""
        def fail_func():
            raise Exception("Test failure")

        # 3번 실패하면 OPEN 상태로 전환
        for _ in range(3):
            with pytest.raises(Exception):
                custom_breaker.call(fail_func)

        assert custom_breaker.state == CircuitState.OPEN

    def test_call_blocked_when_open(self, custom_breaker):
        """OPEN 상태에서 호출 차단"""
        def fail_func():
            raise Exception("Test failure")

        # OPEN 상태로 전환
        for _ in range(3):
            with pytest.raises(Exception):
                custom_breaker.call(fail_func)

        assert custom_breaker.state == CircuitState.OPEN

        # OPEN 상태에서 호출 시도 (timeout 전)
        with pytest.raises(Exception, match="차단 상태"):
            custom_breaker.call(lambda: "test")

    def test_half_open_after_timeout(self, custom_breaker):
        """timeout 후 HALF_OPEN 상태 전환"""
        def fail_func():
            raise Exception("Test failure")

        # OPEN 상태로 전환
        for _ in range(3):
            with pytest.raises(Exception):
                custom_breaker.call(fail_func)

        assert custom_breaker.state == CircuitState.OPEN

        # timeout 대기 (설정: 1초)
        time.sleep(1.1)

        # 다음 호출 시 HALF_OPEN으로 전환
        def success_func():
            return "success"

        result = custom_breaker.call(success_func)

        assert result == "success"
        assert custom_breaker.state == CircuitState.CLOSED  # 성공 시 바로 CLOSED

    def test_success_resets_failure_count(self, circuit_breaker):
        """성공 시 실패 카운트 리셋"""
        def fail_func():
            raise Exception("fail")

        def success_func():
            return "success"

        # 몇 번 실패
        for _ in range(2):
            with pytest.raises(Exception):
                circuit_breaker.call(fail_func)

        assert circuit_breaker.failure_count == 2

        # 성공
        circuit_breaker.call(success_func)

        assert circuit_breaker.failure_count == 0

    def test_reset(self, custom_breaker):
        """수동 리셋"""
        def fail_func():
            raise Exception("fail")

        # OPEN 상태로 전환
        for _ in range(3):
            with pytest.raises(Exception):
                custom_breaker.call(fail_func)

        assert custom_breaker.state == CircuitState.OPEN

        # 수동 리셋
        custom_breaker.reset()

        assert custom_breaker.state == CircuitState.CLOSED
        assert custom_breaker.failure_count == 0
        assert custom_breaker.success_count == 0
        assert custom_breaker.last_failure_time is None

    def test_get_state(self, circuit_breaker):
        """상태 조회"""
        state = circuit_breaker.get_state()

        assert state['name'] == "test_breaker"
        # get_state()는 상태 값을 문자열로 반환
        assert state['state'] == CircuitState.CLOSED.value or state['state'] == CircuitState.CLOSED
        assert state['failure_count'] == 0

    def test_excluded_exceptions(self):
        """제외된 예외는 카운트에 포함되지 않음"""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            excluded_exceptions=(ValueError,)
        )
        breaker = CircuitBreaker("test", config)

        def raise_value_error():
            raise ValueError("excluded")

        # ValueError는 제외되어 카운트 안됨
        with pytest.raises(ValueError):
            breaker.call(raise_value_error)

        assert breaker.failure_count == 0
        assert breaker.state == CircuitState.CLOSED

    def test_half_open_failure_returns_to_open(self, custom_breaker):
        """HALF_OPEN 상태에서 실패 시 다시 OPEN으로 전환"""
        def fail_func():
            raise Exception("fail")

        # OPEN 상태로 전환
        for _ in range(3):
            with pytest.raises(Exception):
                custom_breaker.call(fail_func)

        assert custom_breaker.state == CircuitState.OPEN

        # timeout 대기
        time.sleep(1.1)

        # HALF_OPEN 상태에서 다시 실패
        with pytest.raises(Exception):
            custom_breaker.call(fail_func)

        assert custom_breaker.state == CircuitState.OPEN


class TestCircuitBreakerEdgeCases:
    """CircuitBreaker 엣지 케이스 테스트"""

    def test_concurrent_calls_thread_safe(self):
        """동시 호출 스레드 안전성"""
        import threading

        breaker = CircuitBreaker("concurrent_test")
        results = []
        errors = []

        def make_call():
            try:
                result = breaker.call(lambda: "ok")
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=make_call) for _ in range(10)]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        assert len(results) == 10
        assert len(errors) == 0

    def test_should_attempt_reset_no_failure_time(self):
        """last_failure_time이 None일 때"""
        breaker = CircuitBreaker("test")
        breaker.state = CircuitState.OPEN
        breaker.last_failure_time = None

        assert breaker._should_attempt_reset() is True
