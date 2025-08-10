"""
Resilience Patterns for KAIROS-1 System

재시도 로직, 서킷 브레이커, 백오프 전략 등 시스템 복원력 패턴
"""

import time
import random
import functools
from typing import Callable, Optional, Type, Tuple, Any, Dict, List
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from loguru import logger
from threading import Lock

from .exceptions import KairosException, APIException, APIRateLimitException


class CircuitState(Enum):
    """서킷 브레이커 상태"""
    CLOSED = "closed"  # 정상 작동
    OPEN = "open"      # 차단 상태
    HALF_OPEN = "half_open"  # 테스트 중


@dataclass
class CircuitBreakerConfig:
    """서킷 브레이커 설정"""
    failure_threshold: int = 5  # 실패 임계값
    success_threshold: int = 2  # 성공 임계값 (HALF_OPEN에서)
    timeout: int = 60  # OPEN 상태 유지 시간 (초)
    excluded_exceptions: Tuple[Type[Exception], ...] = ()  # 제외할 예외


class CircuitBreaker:
    """
    서킷 브레이커 패턴 구현
    
    연속된 실패 시 서비스 호출을 차단하여 시스템 보호
    """
    
    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.lock = Lock()
        
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """서킷 브레이커를 통한 함수 호출"""
        with self.lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    logger.info(f"서킷 브레이커 [{self.name}]: HALF_OPEN 상태로 전환")
                else:
                    raise Exception(f"서킷 브레이커 [{self.name}]: 차단 상태")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure(e)
            raise
    
    def _should_attempt_reset(self) -> bool:
        """OPEN 상태에서 재시도 가능 여부 확인"""
        if self.last_failure_time is None:
            return True
        
        time_since_failure = (datetime.now() - self.last_failure_time).total_seconds()
        return time_since_failure >= self.config.timeout
    
    def _on_success(self):
        """성공 시 처리"""
        with self.lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.success_count = 0
                    logger.info(f"서킷 브레이커 [{self.name}]: CLOSED 상태로 복구")
            else:
                self.failure_count = 0
    
    def _on_failure(self, exception: Exception):
        """실패 시 처리"""
        # 제외할 예외인지 확인
        if isinstance(exception, self.config.excluded_exceptions):
            return
        
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                logger.warning(f"서킷 브레이커 [{self.name}]: OPEN 상태로 전환 (HALF_OPEN 실패)")
            elif self.failure_count >= self.config.failure_threshold:
                self.state = CircuitState.OPEN
                logger.warning(f"서킷 브레이커 [{self.name}]: OPEN 상태로 전환 (임계값 초과)")
    
    def reset(self):
        """서킷 브레이커 수동 리셋"""
        with self.lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.last_failure_time = None
            logger.info(f"서킷 브레이커 [{self.name}]: 수동 리셋")
    
    def get_state(self) -> Dict[str, Any]:
        """현재 상태 조회"""
        return {
            'name': self.name,
            'state': self.state.value,
            'failure_count': self.failure_count,
            'success_count': self.success_count,
            'last_failure_time': self.last_failure_time.isoformat() if self.last_failure_time else None
        }


class BackoffStrategy(Enum):
    """백오프 전략"""
    FIXED = "fixed"              # 고정 지연
    LINEAR = "linear"            # 선형 증가
    EXPONENTIAL = "exponential"  # 지수 증가
    FIBONACCI = "fibonacci"      # 피보나치 수열
    RANDOM = "random"           # 랜덤 지터


@dataclass
class RetryConfig:
    """재시도 설정"""
    max_attempts: int = 3
    initial_delay: float = 1.0  # 초
    max_delay: float = 60.0     # 초
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    backoff_factor: float = 2.0
    jitter: bool = True
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
    non_retryable_exceptions: Tuple[Type[Exception], ...] = ()


class RetryManager:
    """
    재시도 관리자
    
    다양한 백오프 전략을 지원하는 재시도 로직
    """
    
    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
        self._fibonacci_cache = [1, 1]
    
    def retry(self, func: Callable, *args, **kwargs) -> Any:
        """재시도 로직을 적용한 함수 실행"""
        last_exception = None
        
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                logger.debug(f"시도 {attempt}/{self.config.max_attempts}: {func.__name__}")
                return func(*args, **kwargs)
                
            except Exception as e:
                last_exception = e
                
                # 재시도 불가능한 예외 확인
                if isinstance(e, self.config.non_retryable_exceptions):
                    logger.error(f"재시도 불가능한 예외 발생: {e}")
                    raise
                
                # 재시도 가능한 예외 확인
                if not isinstance(e, self.config.retryable_exceptions):
                    logger.error(f"예상치 못한 예외 발생: {e}")
                    raise
                
                # 마지막 시도인 경우
                if attempt == self.config.max_attempts:
                    logger.error(f"최대 재시도 횟수 초과: {e}")
                    raise
                
                # 백오프 지연 계산
                delay = self._calculate_delay(attempt)
                
                # Rate limit 예외 처리
                if isinstance(e, APIRateLimitException):
                    if e.details.get('retry_after'):
                        delay = max(delay, e.details['retry_after'])
                
                logger.warning(f"재시도 예정 (시도 {attempt}/{self.config.max_attempts}): "
                             f"{delay:.2f}초 후 - 이유: {e}")
                
                time.sleep(delay)
        
        if last_exception:
            raise last_exception
    
    def _calculate_delay(self, attempt: int) -> float:
        """백오프 지연 시간 계산"""
        if self.config.backoff_strategy == BackoffStrategy.FIXED:
            delay = self.config.initial_delay
            
        elif self.config.backoff_strategy == BackoffStrategy.LINEAR:
            delay = self.config.initial_delay * attempt
            
        elif self.config.backoff_strategy == BackoffStrategy.EXPONENTIAL:
            delay = self.config.initial_delay * (self.config.backoff_factor ** (attempt - 1))
            
        elif self.config.backoff_strategy == BackoffStrategy.FIBONACCI:
            delay = self.config.initial_delay * self._get_fibonacci(attempt)
            
        elif self.config.backoff_strategy == BackoffStrategy.RANDOM:
            delay = random.uniform(self.config.initial_delay, self.config.max_delay)
        
        else:
            delay = self.config.initial_delay
        
        # 최대 지연 시간 제한
        delay = min(delay, self.config.max_delay)
        
        # 지터 추가 (랜덤성)
        if self.config.jitter and self.config.backoff_strategy != BackoffStrategy.RANDOM:
            jitter = random.uniform(0, delay * 0.1)  # 최대 10% 지터
            delay += jitter
        
        return delay
    
    def _get_fibonacci(self, n: int) -> int:
        """피보나치 수 계산 (캐시 사용)"""
        while len(self._fibonacci_cache) <= n:
            self._fibonacci_cache.append(
                self._fibonacci_cache[-1] + self._fibonacci_cache[-2]
            )
        return self._fibonacci_cache[n]


def with_retry(
    max_attempts: int = 3,
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """재시도 데코레이터"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            config = RetryConfig(
                max_attempts=max_attempts,
                backoff_strategy=backoff_strategy,
                retryable_exceptions=retryable_exceptions
            )
            retry_manager = RetryManager(config)
            return retry_manager.retry(func, *args, **kwargs)
        return wrapper
    return decorator


def with_circuit_breaker(
    name: Optional[str] = None,
    failure_threshold: int = 5,
    timeout: int = 60
):
    """서킷 브레이커 데코레이터"""
    def decorator(func: Callable) -> Callable:
        breaker_name = name or f"{func.__module__}.{func.__name__}"
        config = CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            timeout=timeout
        )
        circuit_breaker = CircuitBreaker(breaker_name, config)
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return circuit_breaker.call(func, *args, **kwargs)
        
        # 서킷 브레이커 인스턴스 접근을 위한 속성 추가
        wrapper.circuit_breaker = circuit_breaker
        return wrapper
    return decorator


class RateLimiter:
    """
    레이트 리미터
    
    API 호출 빈도 제한
    """
    
    def __init__(self, max_calls: int, time_window: int):
        """
        Args:
            max_calls: 시간 윈도우 내 최대 호출 수
            time_window: 시간 윈도우 (초)
        """
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls: List[datetime] = []
        self.lock = Lock()
    
    def is_allowed(self) -> bool:
        """호출 가능 여부 확인"""
        with self.lock:
            now = datetime.now()
            
            # 오래된 호출 기록 제거
            self.calls = [
                call_time for call_time in self.calls
                if (now - call_time).total_seconds() < self.time_window
            ]
            
            # 호출 가능 여부 확인
            if len(self.calls) < self.max_calls:
                self.calls.append(now)
                return True
            
            return False
    
    def wait_time(self) -> float:
        """다음 호출까지 대기 시간 (초)"""
        if not self.calls:
            return 0
        
        with self.lock:
            oldest_call = min(self.calls)
            time_passed = (datetime.now() - oldest_call).total_seconds()
            
            if time_passed >= self.time_window:
                return 0
            
            return self.time_window - time_passed


def with_rate_limit(max_calls: int, time_window: int):
    """레이트 리미터 데코레이터"""
    rate_limiter = RateLimiter(max_calls, time_window)
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not rate_limiter.is_allowed():
                wait_time = rate_limiter.wait_time()
                raise APIRateLimitException(
                    service=func.__name__,
                    retry_after=int(wait_time)
                )
            return func(*args, **kwargs)
        return wrapper
    return decorator


class BulkheadPool:
    """
    벌크헤드 패턴
    
    리소스 격리를 통한 장애 전파 방지
    """
    
    def __init__(self, name: str, max_concurrent: int):
        self.name = name
        self.max_concurrent = max_concurrent
        self.active_count = 0
        self.lock = Lock()
    
    def acquire(self) -> bool:
        """리소스 획득"""
        with self.lock:
            if self.active_count < self.max_concurrent:
                self.active_count += 1
                return True
            return False
    
    def release(self):
        """리소스 반환"""
        with self.lock:
            if self.active_count > 0:
                self.active_count -= 1
    
    def __enter__(self):
        if not self.acquire():
            raise Exception(f"벌크헤드 [{self.name}]: 동시 실행 한도 초과")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()