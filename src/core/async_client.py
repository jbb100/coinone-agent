"""
Asynchronous HTTP Client for KAIROS-1 System

비동기 HTTP 클라이언트와 성능 최적화 기능
"""

import asyncio
import aiohttp
import time
from typing import Dict, Any, Optional, List, Callable, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from loguru import logger

from .exceptions import APIException, APITimeoutException, APIRateLimitException


class CacheStrategy(Enum):
    """캐시 전략"""
    NO_CACHE = "no_cache"
    MEMORY_ONLY = "memory_only"
    DISK_ONLY = "disk_only"
    MEMORY_AND_DISK = "memory_and_disk"


@dataclass
class CacheEntry:
    """캐시 엔트리"""
    data: Any
    timestamp: datetime
    ttl: int  # Time to live in seconds
    
    def is_expired(self) -> bool:
        """만료 여부 확인"""
        return datetime.now() > self.timestamp + timedelta(seconds=self.ttl)


class AsyncCache:
    """
    비동기 캐시 시스템
    
    메모리와 디스크 기반 캐싱 지원
    """
    
    def __init__(self, max_memory_items: int = 1000):
        self.max_memory_items = max_memory_items
        self.memory_cache: Dict[str, CacheEntry] = {}
        self.access_times: Dict[str, datetime] = {}
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        """캐시에서 데이터 조회"""
        async with self._lock:
            # 메모리 캐시 확인
            if key in self.memory_cache:
                entry = self.memory_cache[key]
                
                if entry.is_expired():
                    # 만료된 엔트리 삭제
                    del self.memory_cache[key]
                    if key in self.access_times:
                        del self.access_times[key]
                    return None
                
                # 접근 시간 업데이트 (LRU)
                self.access_times[key] = datetime.now()
                return entry.data
            
            return None
    
    async def set(self, key: str, data: Any, ttl: int = 300):
        """캐시에 데이터 저장"""
        async with self._lock:
            # 메모리 한도 확인 및 LRU 삭제
            if len(self.memory_cache) >= self.max_memory_items:
                await self._evict_lru()
            
            # 새 엔트리 저장
            entry = CacheEntry(
                data=data,
                timestamp=datetime.now(),
                ttl=ttl
            )
            
            self.memory_cache[key] = entry
            self.access_times[key] = datetime.now()
    
    async def _evict_lru(self):
        """LRU 캐시 삭제"""
        if not self.access_times:
            return
        
        # 가장 오래된 접근 시간의 키 찾기
        oldest_key = min(self.access_times.keys(), 
                        key=lambda k: self.access_times[k])
        
        # 삭제
        if oldest_key in self.memory_cache:
            del self.memory_cache[oldest_key]
        if oldest_key in self.access_times:
            del self.access_times[oldest_key]
        
        logger.debug(f"LRU 캐시 삭제: {oldest_key}")
    
    async def clear_expired(self):
        """만료된 캐시 정리"""
        async with self._lock:
            expired_keys = [
                key for key, entry in self.memory_cache.items()
                if entry.is_expired()
            ]
            
            for key in expired_keys:
                del self.memory_cache[key]
                if key in self.access_times:
                    del self.access_times[key]
            
            if expired_keys:
                logger.debug(f"만료된 캐시 정리: {len(expired_keys)}개 항목")
    
    def get_stats(self) -> Dict[str, Any]:
        """캐시 통계"""
        return {
            'memory_items': len(self.memory_cache),
            'max_memory_items': self.max_memory_items,
            'memory_usage_percent': len(self.memory_cache) / self.max_memory_items * 100
        }


class ConnectionPool:
    """
    비동기 HTTP 연결 풀
    
    연결 재사용을 통한 성능 최적화
    """
    
    def __init__(
        self,
        max_connections: int = 100,
        max_keepalive_connections: int = 20,
        keepalive_expiry: int = 30,
        timeout: int = 30
    ):
        self.connector = aiohttp.TCPConnector(
            limit=max_connections,
            limit_per_host=max_keepalive_connections,
            keepalive_timeout=keepalive_expiry,
            ttl_dns_cache=300,  # DNS 캐시 TTL
            use_dns_cache=True,
        )
        
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def get_session(self) -> aiohttp.ClientSession:
        """세션 획득 (싱글톤)"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                connector=self.connector,
                timeout=self.timeout,
                headers={'User-Agent': 'KAIROS-1/1.0'}
            )
        return self.session
    
    async def close(self):
        """연결 풀 종료"""
        if self.session and not self.session.closed:
            await self.session.close()
        if self.connector:
            await self.connector.close()


class RequestBatcher:
    """
    요청 배치 처리기
    
    여러 요청을 배치로 처리하여 성능 최적화
    """
    
    def __init__(self, batch_size: int = 10, batch_timeout: float = 0.1):
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.pending_requests: List[Tuple[Callable, asyncio.Future]] = []
        self._batch_lock = asyncio.Lock()
        self._batch_task: Optional[asyncio.Task] = None
    
    async def add_request(self, request_func: Callable) -> Any:
        """배치에 요청 추가"""
        future = asyncio.Future()
        
        async with self._batch_lock:
            self.pending_requests.append((request_func, future))
            
            # 배치 크기 확인
            if len(self.pending_requests) >= self.batch_size:
                await self._process_batch()
            elif not self._batch_task:
                # 타임아웃 배치 스케줄링
                self._batch_task = asyncio.create_task(
                    self._wait_and_process_batch()
                )
        
        return await future
    
    async def _wait_and_process_batch(self):
        """타임아웃 후 배치 처리"""
        await asyncio.sleep(self.batch_timeout)
        async with self._batch_lock:
            await self._process_batch()
    
    async def _process_batch(self):
        """배치 처리 실행"""
        if not self.pending_requests:
            return
        
        batch = self.pending_requests.copy()
        self.pending_requests.clear()
        
        if self._batch_task:
            self._batch_task.cancel()
            self._batch_task = None
        
        # 배치 내 모든 요청을 병렬로 실행
        results = await asyncio.gather(
            *[req_func() for req_func, _ in batch],
            return_exceptions=True
        )
        
        # 결과를 각 Future에 설정
        for (_, future), result in zip(batch, results):
            if isinstance(result, Exception):
                future.set_exception(result)
            else:
                future.set_result(result)


class AsyncHTTPClient:
    """
    비동기 HTTP 클라이언트
    
    캐싱, 연결 풀링, 배치 처리를 지원하는 고성능 클라이언트
    """
    
    def __init__(
        self,
        base_url: str = "",
        default_headers: Optional[Dict[str, str]] = None,
        cache_ttl: int = 300,
        enable_caching: bool = True,
        enable_batching: bool = False,
        rate_limit: Optional[Tuple[int, int]] = None  # (calls, seconds)
    ):
        self.base_url = base_url
        self.default_headers = default_headers or {}
        self.cache_ttl = cache_ttl
        self.enable_caching = enable_caching
        self.enable_batching = enable_batching
        
        # 구성 요소 초기화
        self.connection_pool = ConnectionPool()
        self.cache = AsyncCache() if enable_caching else None
        self.batcher = RequestBatcher() if enable_batching else None
        
        # 성능 메트릭
        self.request_count = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.total_request_time = 0
        
        # Rate limiting
        if rate_limit:
            self.rate_limit_calls, self.rate_limit_window = rate_limit
            self.rate_limit_requests: List[datetime] = []
        else:
            self.rate_limit_calls = None
    
    async def get(
        self,
        url: str,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        cache_ttl: Optional[int] = None,
        bypass_cache: bool = False
    ) -> Dict[str, Any]:
        """GET 요청"""
        return await self._request(
            'GET', url, params=params, headers=headers,
            cache_ttl=cache_ttl, bypass_cache=bypass_cache
        )
    
    async def post(
        self,
        url: str,
        data: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        headers: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """POST 요청 (캐시 안 함)"""
        return await self._request(
            'POST', url, data=data, json_data=json_data,
            headers=headers, bypass_cache=True
        )
    
    async def _request(
        self,
        method: str,
        url: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        cache_ttl: Optional[int] = None,
        bypass_cache: bool = False
    ) -> Dict[str, Any]:
        """실제 요청 처리"""
        
        # URL 완성
        full_url = self._build_url(url)
        
        # 헤더 병합
        request_headers = self.default_headers.copy()
        if headers:
            request_headers.update(headers)
        
        # 캐시 키 생성 (GET 요청만)
        cache_key = None
        if (method == 'GET' and self.enable_caching and 
            self.cache and not bypass_cache):
            cache_key = self._generate_cache_key(
                method, full_url, params, request_headers
            )
            
            # 캐시 확인
            cached_data = await self.cache.get(cache_key)
            if cached_data is not None:
                self.cache_hits += 1
                return cached_data
            
            self.cache_misses += 1
        
        # Rate limit 확인
        await self._check_rate_limit()
        
        # 요청 함수 정의
        async def make_request():
            return await self._execute_request(
                method, full_url, params, data, json_data, request_headers
            )
        
        # 배치 처리 또는 직접 실행
        if self.enable_batching and self.batcher and method == 'GET':
            response_data = await self.batcher.add_request(make_request)
        else:
            response_data = await make_request()
        
        # 캐시 저장 (성공한 GET 요청만)
        if (cache_key and response_data and 
            isinstance(response_data, dict) and self.cache):
            ttl = cache_ttl or self.cache_ttl
            await self.cache.set(cache_key, response_data, ttl)
        
        return response_data
    
    async def _execute_request(
        self,
        method: str,
        url: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        headers: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """실제 HTTP 요청 실행"""
        start_time = time.time()
        
        try:
            session = await self.connection_pool.get_session()
            
            async with session.request(
                method=method,
                url=url,
                params=params,
                data=data,
                json=json_data,
                headers=headers
            ) as response:
                # 성능 메트릭 업데이트
                self.request_count += 1
                self.total_request_time += time.time() - start_time
                
                # 응답 상태 확인
                if response.status == 429:  # Rate limit
                    retry_after = response.headers.get('Retry-After')
                    raise APIRateLimitException(
                        service=url,
                        retry_after=int(retry_after) if retry_after else None
                    )
                
                if response.status >= 400:
                    error_text = await response.text()
                    raise APIException(
                        f"HTTP {response.status}: {error_text}",
                        details={
                            'status_code': response.status,
                            'url': url,
                            'method': method,
                            'response': error_text[:500]  # 처음 500자만
                        }
                    )
                
                # JSON 응답 파싱
                return await response.json()
        
        except asyncio.TimeoutError:
            raise APITimeoutException(
                service=url,
                timeout=self.connection_pool.timeout.total
            )
        except Exception as e:
            self.total_request_time += time.time() - start_time
            raise
    
    def _build_url(self, url: str) -> str:
        """URL 완성"""
        if url.startswith(('http://', 'https://')):
            return url
        return f"{self.base_url.rstrip('/')}/{url.lstrip('/')}"
    
    def _generate_cache_key(
        self,
        method: str,
        url: str,
        params: Optional[Dict],
        headers: Dict[str, str]
    ) -> str:
        """캐시 키 생성"""
        # 캐시에 영향을 주는 요소들을 해시
        key_data = {
            'method': method,
            'url': url,
            'params': sorted(params.items()) if params else None,
            'auth_header': headers.get('Authorization', '')[:20]  # 인증 정보 일부만
        }
        
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    async def _check_rate_limit(self):
        """Rate limit 확인"""
        if not self.rate_limit_calls:
            return
        
        now = datetime.now()
        
        # 윈도우 외 요청 제거
        self.rate_limit_requests = [
            req_time for req_time in self.rate_limit_requests
            if (now - req_time).total_seconds() < self.rate_limit_window
        ]
        
        # Rate limit 확인
        if len(self.rate_limit_requests) >= self.rate_limit_calls:
            oldest_request = min(self.rate_limit_requests)
            wait_time = self.rate_limit_window - (now - oldest_request).total_seconds()
            
            if wait_time > 0:
                raise APIRateLimitException(
                    service="client_rate_limit",
                    retry_after=int(wait_time)
                )
        
        # 현재 요청 기록
        self.rate_limit_requests.append(now)
    
    async def close(self):
        """클라이언트 종료"""
        await self.connection_pool.close()
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """성능 통계"""
        avg_request_time = (
            self.total_request_time / self.request_count
            if self.request_count > 0 else 0
        )
        
        cache_hit_rate = (
            self.cache_hits / (self.cache_hits + self.cache_misses)
            if (self.cache_hits + self.cache_misses) > 0 else 0
        )
        
        stats = {
            'request_count': self.request_count,
            'avg_request_time': round(avg_request_time, 3),
            'cache_hit_rate': round(cache_hit_rate, 3),
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
        }
        
        if self.cache:
            stats['cache_stats'] = self.cache.get_stats()
        
        return stats