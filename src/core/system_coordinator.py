"""
System Coordinator
시스템 전체의 상태 관리와 자원 조정을 담당하는 모듈입니다.
자산별 락, API 호출 제한, 상태 동기화를 통합 관리합니다.
"""
import asyncio
import time
from typing import Dict, List, Optional, Set, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from loguru import logger
from contextlib import asynccontextmanager
from .types import AccountID
class OperationType(Enum):
    """작업 유형"""
    TWAP_EXECUTION = "twap_execution"
    REBALANCING = "rebalancing"
    ORDER_MANAGEMENT = "order_management"
    PORTFOLIO_SYNC = "portfolio_sync"
@dataclass
class ActiveOperation:
    """활성 작업 정보"""
    operation_id: str
    operation_type: OperationType
    account_id: AccountID
    assets: Set[str]
    started_at: datetime
    priority: int = 1  # 낮을수록 높은 우선순위
class ConflictError(Exception):
    """자원 충돌 오류"""
    pass
class AssetLockManager:
    """자산별 락 관리자"""
    def __init__(self):
        self.locks: Dict[str, asyncio.Lock] = {}
        self.lock_holders: Dict[str, str] = {}  # asset -> operation_id
        self._lock = None  # 이벤트 루프에서 초기화됨
        self._initialized = False
    
    async def _ensure_initialized(self):
        """이벤트 루프에서 초기화"""
        if not self._initialized:
            self._lock = asyncio.Lock()
            self._initialized = True
    
    async def acquire_asset_lock(self, asset: str, operation_id: str):
        """자산 락 획득"""
        await self._ensure_initialized()
        async with self._lock:
            if asset not in self.locks:
                self.locks[asset] = asyncio.Lock()
        lock = self.locks[asset]
        await lock.acquire()
        self.lock_holders[asset] = operation_id
        logger.debug(f"자산 락 획득: {asset} by {operation_id}")
        return lock
    def release_asset_lock(self, asset: str, operation_id: str):
        """자산 락 해제"""
        if asset in self.lock_holders and self.lock_holders[asset] == operation_id:
            if asset in self.locks:
                self.locks[asset].release()
                del self.lock_holders[asset]
                logger.debug(f"자산 락 해제: {asset} by {operation_id}")
    @asynccontextmanager
    async def lock_assets(self, assets: List[str], operation_id: str):
        """자산들에 대한 락을 컨텍스트 매니저로 관리"""
        acquired_locks = []
        try:
            # 자산 이름순으로 정렬하여 데드락 방지
            sorted_assets = sorted(assets)
            for asset in sorted_assets:
                lock = await self.acquire_asset_lock(asset, operation_id)
                acquired_locks.append((asset, lock))
            yield
        finally:
            # 역순으로 락 해제
            for asset, lock in reversed(acquired_locks):
                self.release_asset_lock(asset, operation_id)
class APIRateLimiter:
    """API 호출 속도 제한기"""
    def __init__(self, max_calls_per_second: float = 8.0):
        self.max_calls_per_second = max_calls_per_second
        self.min_interval = 1.0 / max_calls_per_second
        self.last_call_time = 0.0
        self._lock = None  # 이벤트 루프에서 초기화됨
        self._initialized = False
        self.call_history: List[float] = []
        self.window_size = 1.0  # 1초 윈도우
    
    async def _ensure_initialized(self):
        """이벤트 루프에서 초기화"""
        if not self._initialized:
            self._lock = asyncio.Lock()
            self._initialized = True
    async def acquire(self):
        """API 호출 권한 획득"""
        await self._ensure_initialized()
        async with self._lock:
            current_time = time.time()
            # 윈도우 범위 내의 호출 기록만 유지
            cutoff_time = current_time - self.window_size
            self.call_history = [t for t in self.call_history if t > cutoff_time]
            # 호출 빈도 체크
            if len(self.call_history) >= self.max_calls_per_second:
                # 가장 오래된 호출 시간 기준으로 대기
                sleep_time = self.window_size - (current_time - self.call_history[0])
                if sleep_time > 0:
                    logger.debug(f"API 속도 제한으로 {sleep_time:.3f}초 대기")
                    await asyncio.sleep(sleep_time)
                    current_time = time.time()
            # 최소 간격 보장
            time_since_last = current_time - self.last_call_time
            if time_since_last < self.min_interval:
                sleep_time = self.min_interval - time_since_last
                await asyncio.sleep(sleep_time)
                current_time = time.time()
            self.last_call_time = current_time
            self.call_history.append(current_time)
class AlertDeduplicator:
    """알림 중복 제거기"""
    def __init__(self, dedup_window_minutes: int = 5):
        self.dedup_window = timedelta(minutes=dedup_window_minutes)
        self.recent_alerts: Dict[str, tuple] = {}  # alert_key -> (timestamp, content_hash)
    def should_send_alert(self, alert_key: str, content: str) -> bool:
        """알림 전송 여부 판단"""
        now = datetime.now()
        content_hash = hash(content)
        if alert_key in self.recent_alerts:
            last_sent, last_hash = self.recent_alerts[alert_key]
            if (now - last_sent < self.dedup_window and last_hash == content_hash):
                logger.debug(f"중복 알림 필터링: {alert_key}")
                return False
        self.recent_alerts[alert_key] = (now, content_hash)
        # 오래된 기록 정리
        cutoff_time = now - self.dedup_window * 2
        keys_to_remove = [
            key for key, (timestamp, _) in self.recent_alerts.items()
            if timestamp < cutoff_time
        ]
        for key in keys_to_remove:
            del self.recent_alerts[key]
        return True
    def clear_alert_history(self, alert_key: Optional[str] = None):
        """알림 기록 초기화"""
        if alert_key:
            self.recent_alerts.pop(alert_key, None)
        else:
            self.recent_alerts.clear()
class SystemStateCoordinator:
    """시스템 상태 조정자"""
    def __init__(self):
        self.asset_lock_manager = AssetLockManager()
        self.api_rate_limiter = APIRateLimiter()
        self.alert_deduplicator = AlertDeduplicator()
        self.active_operations: Dict[str, ActiveOperation] = {}
        self.operation_events: Dict[str, asyncio.Event] = {}
        self._coordinator_lock = None  # 이벤트 루프에서 초기화됨
        self._initialized = False
        # 통계
        self.stats = {
            "total_operations": 0,
            "conflicts_prevented": 0,
            "api_calls_throttled": 0,
            "alerts_deduplicated": 0
        }
    
    async def _ensure_initialized(self):
        """이벤트 루프에서 초기화"""
        if not self._initialized:
            self._coordinator_lock = asyncio.Lock()
            self._initialized = True
    async def register_operation(
        self,
        operation_id: str,
        operation_type: OperationType,
        account_id: AccountID,
        assets: List[str],
        priority: int = 1
    ):
        """작업 등록"""
        await self._ensure_initialized()
        async with self._coordinator_lock:
            # 충돌 검사
            conflicting_ops = []
            for op_id, op in self.active_operations.items():
                if op.account_id == account_id and op.assets.intersection(set(assets)):
                    if op.priority <= priority:  # 더 높거나 같은 우선순위
                        conflicting_ops.append(op_id)
            if conflicting_ops:
                self.stats["conflicts_prevented"] += 1
                raise ConflictError(
                    f"Operation {operation_id} conflicts with: {conflicting_ops}. "
                    f"Assets: {assets}, Account: {account_id}"
                )
            # 작업 등록
            operation = ActiveOperation(
                operation_id=operation_id,
                operation_type=operation_type,
                account_id=account_id,
                assets=set(assets),
                started_at=datetime.now(),
                priority=priority
            )
            self.active_operations[operation_id] = operation
            self.operation_events[operation_id] = asyncio.Event()
            self.stats["total_operations"] += 1
            logger.info(f"작업 등록: {operation_id} ({operation_type.value}) for {account_id}")
    async def complete_operation(self, operation_id: str):
        """작업 완료"""
        await self._ensure_initialized()
        async with self._coordinator_lock:
            if operation_id in self.active_operations:
                operation = self.active_operations.pop(operation_id)
                if operation_id in self.operation_events:
                    event = self.operation_events.pop(operation_id)
                    event.set()
                logger.info(f"작업 완료: {operation_id} (소요시간: {datetime.now() - operation.started_at})")
            else:
                logger.warning(f"완료하려는 작업이 등록되지 않음: {operation_id}")
    @asynccontextmanager
    async def coordinate_operation(
        self,
        operation_id: str,
        operation_type: OperationType,
        account_id: AccountID,
        assets: List[str],
        priority: int = 1
    ):
        """작업 조정 컨텍스트 매니저"""
        try:
            await self.register_operation(operation_id, operation_type, account_id, assets, priority)
            async with self.asset_lock_manager.lock_assets(assets, operation_id):
                yield
        finally:
            await self.complete_operation(operation_id)
    async def api_call_with_limit(self, api_method, *args, **kwargs):
        """속도 제한이 적용된 API 호출"""
        await self.api_rate_limiter.acquire()
        try:
            return await api_method(*args, **kwargs)
        except Exception as e:
            logger.error(f"API 호출 실패: {e}")
            raise
    def should_send_alert(self, alert_key: str, content: str) -> bool:
        """중복 제거가 적용된 알림 전송 여부 판단"""
        should_send = self.alert_deduplicator.should_send_alert(alert_key, content)
        if not should_send:
            self.stats["alerts_deduplicated"] += 1
        return should_send
    def get_system_status(self) -> Dict[str, Any]:
        """시스템 상태 조회"""
        return {
            "active_operations": len(self.active_operations),
            "operations_by_type": {
                op_type.value: sum(1 for op in self.active_operations.values()
                                 if op.operation_type == op_type)
                for op_type in OperationType
            },
            "locked_assets": list(self.asset_lock_manager.lock_holders.keys()),
            "api_rate_limit": {
                "max_calls_per_second": self.api_rate_limiter.max_calls_per_second,
                "recent_calls": len(self.api_rate_limiter.call_history)
            },
            "stats": self.stats.copy()
        }
    async def wait_for_operation(self, operation_id: str, timeout: Optional[float] = None):
        """특정 작업 완료까지 대기"""
        if operation_id in self.operation_events:
            try:
                await asyncio.wait_for(
                    self.operation_events[operation_id].wait(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                logger.warning(f"작업 대기 타임아웃: {operation_id}")
                raise
    async def shutdown(self):
        """시스템 종료"""
        logger.info("SystemStateCoordinator 종료 중...")
        # 모든 활성 작업 완료 대기 (최대 30초)
        if self.active_operations:
            logger.info(f"{len(self.active_operations)}개 활성 작업 완료 대기 중...")
            try:
                await asyncio.wait_for(
                    asyncio.gather(*[
                        event.wait() for event in self.operation_events.values()
                    ]),
                    timeout=30.0
                )
            except asyncio.TimeoutError:
                logger.warning("일부 작업이 시간 내에 완료되지 않았습니다")
        logger.info("SystemStateCoordinator 종료 완료")
# 전역 인스턴스
_system_coordinator: Optional[SystemStateCoordinator] = None
def get_system_coordinator() -> SystemStateCoordinator:
    """시스템 조정자 인스턴스 반환"""
    global _system_coordinator
    if _system_coordinator is None:
        _system_coordinator = SystemStateCoordinator()
    return _system_coordinator
