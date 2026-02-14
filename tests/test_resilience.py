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


class TestBackoffStrategy:
    """BackoffStrategy Enum 테스트"""

    def test_backoff_strategy_values(self):
        """백오프 전략 값 확인"""
        from src.core.resilience import BackoffStrategy

        assert BackoffStrategy.FIXED.value == "fixed"
        assert BackoffStrategy.LINEAR.value == "linear"
        assert BackoffStrategy.EXPONENTIAL.value == "exponential"
        assert BackoffStrategy.FIBONACCI.value == "fibonacci"
        assert BackoffStrategy.RANDOM.value == "random"

    def test_backoff_strategy_count(self):
        """백오프 전략 개수 확인"""
        from src.core.resilience import BackoffStrategy

        assert len(BackoffStrategy) == 5


class TestRetryConfig:
    """RetryConfig 데이터클래스 테스트"""

    def test_default_config(self):
        """기본 설정 값 확인"""
        from src.core.resilience import RetryConfig, BackoffStrategy

        config = RetryConfig()

        assert config.max_attempts == 3
        assert config.initial_delay == 1.0
        assert config.max_delay == 60.0
        assert config.backoff_strategy == BackoffStrategy.EXPONENTIAL
        assert config.backoff_factor == 2.0
        assert config.jitter == True

    def test_custom_config(self):
        """커스텀 설정"""
        from src.core.resilience import RetryConfig, BackoffStrategy

        config = RetryConfig(
            max_attempts=5,
            initial_delay=0.5,
            max_delay=30.0,
            backoff_strategy=BackoffStrategy.LINEAR,
            jitter=False
        )

        assert config.max_attempts == 5
        assert config.initial_delay == 0.5
        assert config.backoff_strategy == BackoffStrategy.LINEAR


class TestRetryManager:
    """RetryManager 클래스 테스트"""

    def test_success_first_attempt(self):
        """첫 시도에서 성공"""
        from src.core.resilience import RetryManager

        manager = RetryManager()
        result = manager.retry(lambda: "success")

        assert result == "success"

    def test_success_after_retry(self):
        """재시도 후 성공"""
        from src.core.resilience import RetryManager, RetryConfig

        config = RetryConfig(max_attempts=3, initial_delay=0.01)
        manager = RetryManager(config)

        call_count = 0

        def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Temporary failure")
            return "success"

        result = manager.retry(fail_then_succeed)

        assert result == "success"
        assert call_count == 2

    def test_max_attempts_exceeded(self):
        """최대 재시도 횟수 초과"""
        from src.core.resilience import RetryManager, RetryConfig

        config = RetryConfig(max_attempts=3, initial_delay=0.01)
        manager = RetryManager(config)

        call_count = 0

        def always_fail():
            nonlocal call_count
            call_count += 1
            raise Exception("Always fails")

        with pytest.raises(Exception, match="Always fails"):
            manager.retry(always_fail)

        assert call_count == 3

    def test_non_retryable_exception(self):
        """재시도 불가능한 예외"""
        from src.core.resilience import RetryManager, RetryConfig

        config = RetryConfig(
            max_attempts=3,
            initial_delay=0.01,
            non_retryable_exceptions=(ValueError,)
        )
        manager = RetryManager(config)

        call_count = 0

        def raise_value_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("Non retryable")

        with pytest.raises(ValueError):
            manager.retry(raise_value_error)

        # 재시도 없이 즉시 실패
        assert call_count == 1

    def test_not_retryable_exception_type(self):
        """재시도 가능 예외가 아닌 경우"""
        from src.core.resilience import RetryManager, RetryConfig

        config = RetryConfig(
            max_attempts=3,
            initial_delay=0.01,
            retryable_exceptions=(ValueError,)  # ValueError만 재시도
        )
        manager = RetryManager(config)

        call_count = 0

        def raise_type_error():
            nonlocal call_count
            call_count += 1
            raise TypeError("Not retryable type")

        with pytest.raises(TypeError):
            manager.retry(raise_type_error)

        assert call_count == 1


class TestCalculateDelay:
    """_calculate_delay 메서드 테스트"""

    def test_fixed_strategy(self):
        """고정 지연 전략"""
        from src.core.resilience import RetryManager, RetryConfig, BackoffStrategy

        config = RetryConfig(
            initial_delay=1.0,
            backoff_strategy=BackoffStrategy.FIXED,
            jitter=False
        )
        manager = RetryManager(config)

        delay1 = manager._calculate_delay(1)
        delay2 = manager._calculate_delay(2)
        delay3 = manager._calculate_delay(3)

        assert delay1 == delay2 == delay3 == 1.0

    def test_linear_strategy(self):
        """선형 증가 전략"""
        from src.core.resilience import RetryManager, RetryConfig, BackoffStrategy

        config = RetryConfig(
            initial_delay=1.0,
            backoff_strategy=BackoffStrategy.LINEAR,
            jitter=False
        )
        manager = RetryManager(config)

        assert manager._calculate_delay(1) == 1.0
        assert manager._calculate_delay(2) == 2.0
        assert manager._calculate_delay(3) == 3.0

    def test_exponential_strategy(self):
        """지수 증가 전략"""
        from src.core.resilience import RetryManager, RetryConfig, BackoffStrategy

        config = RetryConfig(
            initial_delay=1.0,
            backoff_factor=2.0,
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            jitter=False
        )
        manager = RetryManager(config)

        assert manager._calculate_delay(1) == 1.0
        assert manager._calculate_delay(2) == 2.0
        assert manager._calculate_delay(3) == 4.0

    def test_fibonacci_strategy(self):
        """피보나치 전략"""
        from src.core.resilience import RetryManager, RetryConfig, BackoffStrategy

        config = RetryConfig(
            initial_delay=1.0,
            backoff_strategy=BackoffStrategy.FIBONACCI,
            jitter=False
        )
        manager = RetryManager(config)

        assert manager._calculate_delay(1) == 1.0  # fib(1) = 1
        assert manager._calculate_delay(2) == 2.0  # fib(2) = 2
        assert manager._calculate_delay(3) == 3.0  # fib(3) = 3

    def test_random_strategy(self):
        """랜덤 전략"""
        from src.core.resilience import RetryManager, RetryConfig, BackoffStrategy

        config = RetryConfig(
            initial_delay=1.0,
            max_delay=10.0,
            backoff_strategy=BackoffStrategy.RANDOM,
            jitter=False
        )
        manager = RetryManager(config)

        delay = manager._calculate_delay(1)

        assert 1.0 <= delay <= 10.0

    def test_max_delay_limit(self):
        """최대 지연 제한"""
        from src.core.resilience import RetryManager, RetryConfig, BackoffStrategy

        config = RetryConfig(
            initial_delay=10.0,
            max_delay=5.0,  # 최대 5초
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            jitter=False
        )
        manager = RetryManager(config)

        delay = manager._calculate_delay(5)

        assert delay == 5.0  # max_delay 제한

    def test_jitter_adds_randomness(self):
        """지터 추가"""
        from src.core.resilience import RetryManager, RetryConfig, BackoffStrategy

        config = RetryConfig(
            initial_delay=1.0,
            backoff_strategy=BackoffStrategy.FIXED,
            jitter=True
        )
        manager = RetryManager(config)

        delays = [manager._calculate_delay(1) for _ in range(10)]

        # 지터로 인해 모든 값이 정확히 같지 않을 것
        # 하지만 1.0 근처 (1.0 ~ 1.1)
        for delay in delays:
            assert 1.0 <= delay <= 1.1


class TestGetFibonacci:
    """_get_fibonacci 메서드 테스트"""

    def test_fibonacci_sequence(self):
        """피보나치 수열 계산"""
        from src.core.resilience import RetryManager

        manager = RetryManager()

        assert manager._get_fibonacci(0) == 1
        assert manager._get_fibonacci(1) == 1
        assert manager._get_fibonacci(2) == 2
        assert manager._get_fibonacci(3) == 3
        assert manager._get_fibonacci(4) == 5
        assert manager._get_fibonacci(5) == 8

    def test_fibonacci_cache(self):
        """피보나치 캐시 동작"""
        from src.core.resilience import RetryManager

        manager = RetryManager()

        # 큰 값 계산
        manager._get_fibonacci(10)

        # 캐시에 저장됨
        assert len(manager._fibonacci_cache) >= 11


class TestWithRetryDecorator:
    """with_retry 데코레이터 테스트"""

    def test_decorator_success(self):
        """데코레이터 성공 케이스"""
        from src.core.resilience import with_retry

        @with_retry(max_attempts=3)
        def success_func():
            return "success"

        result = success_func()

        assert result == "success"

    def test_decorator_retry(self):
        """데코레이터 재시도"""
        from src.core.resilience import with_retry, BackoffStrategy

        call_count = 0

        @with_retry(max_attempts=3, backoff_strategy=BackoffStrategy.FIXED)
        def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Temp fail")
            return "success"

        result = fail_then_succeed()

        assert result == "success"
        assert call_count == 2


class TestWithCircuitBreakerDecorator:
    """with_circuit_breaker 데코레이터 테스트"""

    def test_decorator_creates_breaker(self):
        """데코레이터가 서킷 브레이커 생성"""
        from src.core.resilience import with_circuit_breaker

        @with_circuit_breaker(name="test_cb")
        def test_func():
            return "ok"

        assert hasattr(test_func, 'circuit_breaker')
        assert test_func.circuit_breaker.name == "test_cb"

    def test_decorator_auto_name(self):
        """데코레이터 자동 이름 생성"""
        from src.core.resilience import with_circuit_breaker

        @with_circuit_breaker()
        def another_func():
            return "ok"

        assert "another_func" in another_func.circuit_breaker.name

    def test_decorator_function_call(self):
        """데코레이터 적용 함수 호출"""
        from src.core.resilience import with_circuit_breaker

        @with_circuit_breaker(name="call_test")
        def callable_func():
            return "called"

        result = callable_func()

        assert result == "called"


class TestRateLimiter:
    """RateLimiter 클래스 테스트"""

    def test_allows_calls_within_limit(self):
        """제한 내 호출 허용"""
        from src.core.resilience import RateLimiter

        limiter = RateLimiter(max_calls=5, time_window=1)

        for _ in range(5):
            assert limiter.is_allowed() == True

    def test_blocks_calls_over_limit(self):
        """제한 초과 호출 차단"""
        from src.core.resilience import RateLimiter

        limiter = RateLimiter(max_calls=3, time_window=1)

        for _ in range(3):
            limiter.is_allowed()

        assert limiter.is_allowed() == False

    def test_allows_after_window_expires(self):
        """시간 윈도우 후 다시 허용"""
        from src.core.resilience import RateLimiter

        limiter = RateLimiter(max_calls=2, time_window=0.1)

        limiter.is_allowed()
        limiter.is_allowed()
        assert limiter.is_allowed() == False

        time.sleep(0.15)

        assert limiter.is_allowed() == True

    def test_wait_time_returns_zero_when_no_calls(self):
        """호출 없을 때 대기 시간 0"""
        from src.core.resilience import RateLimiter

        limiter = RateLimiter(max_calls=5, time_window=1)

        assert limiter.wait_time() == 0

    def test_wait_time_returns_remaining(self):
        """남은 대기 시간 반환"""
        from src.core.resilience import RateLimiter

        limiter = RateLimiter(max_calls=1, time_window=1)
        limiter.is_allowed()

        wait = limiter.wait_time()

        assert 0 < wait <= 1

    def test_wait_time_zero_after_window(self):
        """윈도우 후 대기 시간 0"""
        from src.core.resilience import RateLimiter

        limiter = RateLimiter(max_calls=1, time_window=0.1)
        limiter.is_allowed()

        time.sleep(0.15)

        assert limiter.wait_time() == 0


class TestWithRateLimitDecorator:
    """with_rate_limit 데코레이터 테스트"""

    def test_decorator_allows_within_limit(self):
        """제한 내 호출 허용"""
        from src.core.resilience import with_rate_limit

        @with_rate_limit(max_calls=5, time_window=1)
        def limited_func():
            return "ok"

        for _ in range(5):
            result = limited_func()
            assert result == "ok"

    def test_decorator_raises_on_limit(self):
        """제한 초과 시 예외 발생"""
        from src.core.resilience import with_rate_limit
        from src.core.exceptions import APIRateLimitException

        @with_rate_limit(max_calls=2, time_window=10)
        def limited_func():
            return "ok"

        limited_func()
        limited_func()

        with pytest.raises(APIRateLimitException):
            limited_func()


class TestBulkheadPool:
    """BulkheadPool 클래스 테스트"""

    def test_acquire_within_limit(self):
        """제한 내 리소스 획득"""
        from src.core.resilience import BulkheadPool

        pool = BulkheadPool("test", max_concurrent=3)

        assert pool.acquire() == True
        assert pool.active_count == 1

        assert pool.acquire() == True
        assert pool.active_count == 2

    def test_acquire_over_limit(self):
        """제한 초과 시 획득 실패"""
        from src.core.resilience import BulkheadPool

        pool = BulkheadPool("test", max_concurrent=2)

        assert pool.acquire() == True
        assert pool.acquire() == True
        assert pool.acquire() == False

    def test_release(self):
        """리소스 반환"""
        from src.core.resilience import BulkheadPool

        pool = BulkheadPool("test", max_concurrent=2)

        pool.acquire()
        pool.acquire()
        assert pool.active_count == 2

        pool.release()
        assert pool.active_count == 1

    def test_release_below_zero(self):
        """0 이하로 릴리스 시도"""
        from src.core.resilience import BulkheadPool

        pool = BulkheadPool("test", max_concurrent=2)

        pool.release()  # active_count가 0이면 변화 없음
        assert pool.active_count == 0

    def test_context_manager_success(self):
        """컨텍스트 매니저 성공"""
        from src.core.resilience import BulkheadPool

        pool = BulkheadPool("test", max_concurrent=1)

        with pool:
            assert pool.active_count == 1

        assert pool.active_count == 0

    def test_context_manager_limit_exceeded(self):
        """컨텍스트 매니저 제한 초과"""
        from src.core.resilience import BulkheadPool

        pool = BulkheadPool("test", max_concurrent=1)
        pool.acquire()  # 이미 1개 사용 중

        with pytest.raises(Exception, match="동시 실행 한도 초과"):
            with pool:
                pass

    def test_context_manager_releases_on_exception(self):
        """예외 발생 시에도 리소스 반환"""
        from src.core.resilience import BulkheadPool

        pool = BulkheadPool("test", max_concurrent=1)

        try:
            with pool:
                assert pool.active_count == 1
                raise ValueError("Test error")
        except ValueError:
            pass

        assert pool.active_count == 0


class TestAPIRateLimitExceptionHandling:
    """APIRateLimitException 처리 테스트"""

    def test_retry_with_rate_limit_exception(self):
        """Rate limit 예외 시 재시도"""
        from src.core.resilience import RetryManager, RetryConfig
        from src.core.exceptions import APIRateLimitException

        config = RetryConfig(max_attempts=3, initial_delay=0.01)
        manager = RetryManager(config)

        call_count = 0

        def raise_rate_limit_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise APIRateLimitException(service="test", retry_after=0.01)
            return "success"

        result = manager.retry(raise_rate_limit_then_succeed)

        assert result == "success"
        assert call_count == 2
