"""
Base Service Classes

공통 서비스 기능을 제공하는 기본 클래스들
"""

import abc
import asyncio
from typing import Dict, Any, Optional, List, Type, TypeVar, Generic
from datetime import datetime
from dataclasses import dataclass
from loguru import logger

from .exceptions import KairosException, ConfigurationException
from .resilience import RetryManager, CircuitBreaker, RetryConfig, CircuitBreakerConfig
from .async_client import AsyncHTTPClient


T = TypeVar('T')


@dataclass
class ServiceConfig:
    """서비스 기본 설정"""
    name: str
    enabled: bool = True
    retry_config: Optional[RetryConfig] = None
    circuit_breaker_config: Optional[CircuitBreakerConfig] = None
    health_check_interval: int = 60  # seconds
    
    def __post_init__(self):
        if self.retry_config is None:
            self.retry_config = RetryConfig()
        if self.circuit_breaker_config is None:
            self.circuit_breaker_config = CircuitBreakerConfig()


class ServiceStatus:
    """서비스 상태"""
    def __init__(self, name: str):
        self.name = name
        self.started_at: Optional[datetime] = None
        self.last_health_check: Optional[datetime] = None
        self.is_healthy = False
        self.error_count = 0
        self.last_error: Optional[Exception] = None
        self.metrics: Dict[str, Any] = {}


class BaseService(abc.ABC):
    """
    기본 서비스 클래스
    
    모든 서비스가 상속받아야 하는 추상 기본 클래스
    """
    
    def __init__(self, config: ServiceConfig):
        self.config = config
        self.status = ServiceStatus(config.name)
        
        # 복원력 패턴
        self.retry_manager = RetryManager(config.retry_config)
        self.circuit_breaker = CircuitBreaker(config.name, config.circuit_breaker_config)
        
        # 헬스체크 태스크
        self._health_check_task: Optional[asyncio.Task] = None
        
        logger.info(f"서비스 초기화: {self.config.name}")
    
    @abc.abstractmethod
    async def start(self):
        """서비스 시작"""
        pass
    
    @abc.abstractmethod
    async def stop(self):
        """서비스 종료"""
        pass
    
    @abc.abstractmethod
    async def health_check(self) -> bool:
        """헬스체크 수행"""
        pass
    
    async def initialize(self):
        """서비스 초기화"""
        if not self.config.enabled:
            logger.info(f"서비스 비활성화됨: {self.config.name}")
            return
        
        try:
            await self.start()
            self.status.started_at = datetime.now()
            self.status.is_healthy = True
            
            # 헬스체크 스케줄링
            if self.config.health_check_interval > 0:
                self._health_check_task = asyncio.create_task(
                    self._periodic_health_check()
                )
            
            logger.info(f"✅ 서비스 시작 완료: {self.config.name}")
            
        except Exception as e:
            self.status.last_error = e
            self.status.error_count += 1
            logger.error(f"❌ 서비스 시작 실패: {self.config.name} - {e}")
            raise
    
    async def shutdown(self):
        """서비스 종료"""
        logger.info(f"서비스 종료 중: {self.config.name}")
        
        # 헬스체크 태스크 종료
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        try:
            await self.stop()
            logger.info(f"✅ 서비스 종료 완료: {self.config.name}")
        except Exception as e:
            logger.error(f"❌ 서비스 종료 실패: {self.config.name} - {e}")
            raise
    
    async def _periodic_health_check(self):
        """주기적 헬스체크"""
        while True:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                
                is_healthy = await self.health_check()
                self.status.is_healthy = is_healthy
                self.status.last_health_check = datetime.now()
                
                if not is_healthy:
                    logger.warning(f"⚠️ 헬스체크 실패: {self.config.name}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.status.last_error = e
                self.status.error_count += 1
                self.status.is_healthy = False
                logger.error(f"❌ 헬스체크 오류: {self.config.name} - {e}")
    
    async def execute_with_resilience(self, func, *args, **kwargs):
        """복원력 패턴이 적용된 함수 실행"""
        try:
            return await asyncio.to_thread(
                lambda: self.circuit_breaker.call(
                    lambda: self.retry_manager.retry(func, *args, **kwargs)
                )
            )
        except Exception as e:
            self.status.last_error = e
            self.status.error_count += 1
            raise
    
    def get_status(self) -> Dict[str, Any]:
        """서비스 상태 조회"""
        return {
            'name': self.status.name,
            'enabled': self.config.enabled,
            'started_at': self.status.started_at.isoformat() if self.status.started_at else None,
            'is_healthy': self.status.is_healthy,
            'last_health_check': self.status.last_health_check.isoformat() if self.status.last_health_check else None,
            'error_count': self.status.error_count,
            'last_error': str(self.status.last_error) if self.status.last_error else None,
            'circuit_breaker': self.circuit_breaker.get_state(),
            'metrics': self.status.metrics.copy()
        }


class HTTPService(BaseService):
    """
    HTTP 기반 서비스 기본 클래스
    
    API 클라이언트 서비스들의 공통 기능
    """
    
    def __init__(self, config: ServiceConfig, base_url: str, default_headers: Optional[Dict] = None):
        super().__init__(config)
        self.base_url = base_url
        self.client = AsyncHTTPClient(
            base_url=base_url,
            default_headers=default_headers or {}
        )
    
    async def start(self):
        """HTTP 서비스 시작"""
        # 연결 테스트
        await self.health_check()
    
    async def stop(self):
        """HTTP 서비스 종료"""
        if self.client:
            await self.client.close()
    
    async def health_check(self) -> bool:
        """HTTP 헬스체크"""
        try:
            # 기본적으로 base URL에 대한 간단한 요청
            health_url = self.get_health_check_url()
            if health_url:
                response = await self.client.get(health_url)
                return self.validate_health_response(response)
            return True
        except Exception as e:
            logger.warning(f"HTTP 헬스체크 실패: {self.config.name} - {e}")
            return False
    
    def get_health_check_url(self) -> Optional[str]:
        """헬스체크 URL 반환 (서브클래스에서 오버라이드)"""
        return None
    
    def validate_health_response(self, response: Dict[str, Any]) -> bool:
        """헬스체크 응답 검증 (서브클래스에서 오버라이드)"""
        return True
    
    async def make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """복원력이 적용된 HTTP 요청"""
        async def _request():
            if method.upper() == 'GET':
                return await self.client.get(endpoint, **kwargs)
            elif method.upper() == 'POST':
                return await self.client.post(endpoint, **kwargs)
            else:
                raise NotImplementedError(f"지원하지 않는 HTTP 메서드: {method}")
        
        return await self.execute_with_resilience(_request)


class DatabaseService(BaseService):
    """
    데이터베이스 서비스 기본 클래스
    """
    
    def __init__(self, config: ServiceConfig, connection_string: str):
        super().__init__(config)
        self.connection_string = connection_string
        self.connection = None
    
    @abc.abstractmethod
    async def connect(self):
        """데이터베이스 연결"""
        pass
    
    @abc.abstractmethod
    async def disconnect(self):
        """데이터베이스 연결 해제"""
        pass
    
    @abc.abstractmethod
    async def execute_query(self, query: str, params: Optional[Dict] = None) -> Any:
        """쿼리 실행"""
        pass
    
    async def start(self):
        """데이터베이스 서비스 시작"""
        await self.connect()
    
    async def stop(self):
        """데이터베이스 서비스 종료"""
        await self.disconnect()
    
    async def health_check(self) -> bool:
        """데이터베이스 헬스체크"""
        try:
            # 간단한 쿼리로 연결 상태 확인
            await self.execute_query("SELECT 1")
            return True
        except Exception as e:
            logger.warning(f"DB 헬스체크 실패: {self.config.name} - {e}")
            return False


class ServiceRegistry:
    """
    서비스 레지스트리
    
    모든 서비스를 중앙에서 관리
    """
    
    def __init__(self):
        self.services: Dict[str, BaseService] = {}
        self._startup_order: List[str] = []
    
    def register(self, service: BaseService, startup_priority: int = 0):
        """서비스 등록"""
        name = service.config.name
        
        if name in self.services:
            raise ConfigurationException(f"이미 등록된 서비스: {name}")
        
        self.services[name] = service
        
        # 시작 순서 관리 (우선순위별)
        self._startup_order.append(name)
        self._startup_order.sort(key=lambda n: startup_priority)
        
        logger.info(f"서비스 등록: {name}")
    
    def unregister(self, name: str):
        """서비스 등록 해제"""
        if name in self.services:
            del self.services[name]
            if name in self._startup_order:
                self._startup_order.remove(name)
            logger.info(f"서비스 등록 해제: {name}")
    
    def get_service(self, name: str) -> Optional[BaseService]:
        """서비스 조회"""
        return self.services.get(name)
    
    async def start_all(self):
        """모든 서비스 시작"""
        logger.info("모든 서비스 시작 중...")
        
        for name in self._startup_order:
            service = self.services[name]
            try:
                await service.initialize()
            except Exception as e:
                logger.error(f"서비스 시작 실패: {name} - {e}")
                # 의존성에 따라 계속 진행하거나 중단 결정
                # 여기서는 로그만 남기고 계속 진행
        
        logger.info("✅ 모든 서비스 시작 완료")
    
    async def stop_all(self):
        """모든 서비스 종료 (역순)"""
        logger.info("모든 서비스 종료 중...")
        
        # 시작 순서의 역순으로 종료
        for name in reversed(self._startup_order):
            service = self.services[name]
            try:
                await service.shutdown()
            except Exception as e:
                logger.error(f"서비스 종료 실패: {name} - {e}")
        
        logger.info("✅ 모든 서비스 종료 완료")
    
    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """모든 서비스 상태 조회"""
        return {
            name: service.get_status()
            for name, service in self.services.items()
        }
    
    def get_healthy_services(self) -> List[str]:
        """건강한 서비스 목록"""
        return [
            name for name, service in self.services.items()
            if service.status.is_healthy
        ]
    
    def get_unhealthy_services(self) -> List[str]:
        """비건강한 서비스 목록"""
        return [
            name for name, service in self.services.items()
            if not service.status.is_healthy
        ]


# 전역 서비스 레지스트리
service_registry = ServiceRegistry()


class DataValidationMixin:
    """
    데이터 검증 믹스인
    
    공통 데이터 검증 로직
    """
    
    def validate_required_fields(self, data: Dict[str, Any], required_fields: List[str]):
        """필수 필드 검증"""
        missing_fields = [field for field in required_fields if field not in data or data[field] is None]
        if missing_fields:
            raise KairosException(
                f"필수 필드 누락: {', '.join(missing_fields)}",
                error_code="MISSING_REQUIRED_FIELDS",
                details={'missing_fields': missing_fields}
            )
    
    def validate_numeric_range(self, value: float, field_name: str, min_val: Optional[float] = None, max_val: Optional[float] = None):
        """숫자 범위 검증"""
        if min_val is not None and value < min_val:
            raise KairosException(
                f"{field_name} 값이 최솟값보다 작습니다: {value} < {min_val}",
                error_code="VALUE_TOO_SMALL",
                details={'field': field_name, 'value': value, 'min': min_val}
            )
        
        if max_val is not None and value > max_val:
            raise KairosException(
                f"{field_name} 값이 최댓값보다 큽니다: {value} > {max_val}",
                error_code="VALUE_TOO_LARGE",
                details={'field': field_name, 'value': value, 'max': max_val}
            )
    
    def validate_percentage(self, value: float, field_name: str):
        """백분율 검증 (0-1 범위)"""
        self.validate_numeric_range(value, field_name, 0.0, 1.0)
    
    def validate_positive_number(self, value: float, field_name: str):
        """양수 검증"""
        if value <= 0:
            raise KairosException(
                f"{field_name}는 양수여야 합니다: {value}",
                error_code="INVALID_POSITIVE_NUMBER",
                details={'field': field_name, 'value': value}
            )


class CacheableMixin:
    """
    캐시 가능 믹스인
    
    공통 캐싱 로직
    """
    
    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, datetime] = {}
    
    def get_from_cache(self, key: str, ttl: int = 300) -> Optional[Any]:
        """캐시에서 값 조회"""
        if key not in self._cache:
            return None
        
        # TTL 확인
        timestamp = self._cache_timestamps.get(key)
        if timestamp and (datetime.now() - timestamp).total_seconds() > ttl:
            self.invalidate_cache(key)
            return None
        
        return self._cache[key]
    
    def set_cache(self, key: str, value: Any):
        """캐시에 값 저장"""
        self._cache[key] = value
        self._cache_timestamps[key] = datetime.now()
    
    def invalidate_cache(self, key: Optional[str] = None):
        """캐시 무효화"""
        if key:
            self._cache.pop(key, None)
            self._cache_timestamps.pop(key, None)
        else:
            self._cache.clear()
            self._cache_timestamps.clear()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """캐시 통계"""
        return {
            'cache_size': len(self._cache),
            'oldest_entry': min(self._cache_timestamps.values()) if self._cache_timestamps else None
        }