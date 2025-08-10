"""
Multi-Account Coordinator for KAIROS-1 System

멀티 계정 작업의 병렬 실행, 스케줄링, 리소스 관리를 담당하는 중앙 조정자
"""

import asyncio
import json
from typing import Dict, List, Optional, Any, Callable, Union
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger
from dataclasses import dataclass, field
from enum import Enum
import uuid
from collections import defaultdict

from .types import AccountID
from .base_service import BaseService, ServiceConfig
from .exceptions import KairosException, ConfigurationException
from .multi_account_manager import MultiAccountManager, get_multi_account_manager
from .multi_account_feature_manager import MultiAccountFeatureManager, get_multi_account_feature_manager, MultiAccountOperationResult


class TaskPriority(Enum):
    """작업 우선순위"""
    CRITICAL = 1    # 즉시 실행 (리스크 관리, 긴급 중단)
    HIGH = 2        # 높은 우선순위 (리밸런싱, 주문 실행)
    MEDIUM = 3      # 보통 우선순위 (성과 분석, 포트폴리오 최적화)
    LOW = 4         # 낮은 우선순위 (로그 분석, 리포트 생성)


class TaskStatus(Enum):
    """작업 상태"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ScheduledTask:
    """스케줄된 작업"""
    task_id: str
    name: str
    function: Callable
    target_accounts: Optional[List[AccountID]] = None
    priority: TaskPriority = TaskPriority.MEDIUM
    scheduled_time: Optional[datetime] = None
    recurring: bool = False
    interval_minutes: Optional[int] = None
    max_retries: int = 3
    timeout_seconds: int = 300
    
    # 상태 추적
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    last_error: Optional[str] = None
    
    # 결과
    result: Optional[MultiAccountOperationResult] = None


@dataclass
class ResourcePool:
    """리소스 풀 관리"""
    max_concurrent_tasks: int = 10
    max_concurrent_per_account: int = 3
    max_api_calls_per_minute: int = 60
    
    # 현재 사용량
    active_tasks: int = 0
    account_active_tasks: Dict[AccountID, int] = field(default_factory=dict)
    api_calls_this_minute: int = 0
    last_api_reset: datetime = field(default_factory=datetime.now)


class MultiAccountCoordinator(BaseService):
    """멀티 계정 조정자
    
    여러 계정에 대한 작업을 효율적으로 조정하고 실행합니다:
    - 작업 스케줄링 및 우선순위 관리
    - 리소스 풀 관리 (동시성 제어)
    - 계정별 부하 분산
    - 실패 복구 및 재시도 메커니즘
    """
    
    def __init__(self):
        super().__init__(ServiceConfig(
            name="multi_account_coordinator",
            enabled=True,
            health_check_interval=60
        ))
        
        self.multi_account_manager = get_multi_account_manager()
        self.feature_manager = get_multi_account_feature_manager()
        
        # 작업 관리
        self.scheduled_tasks: Dict[str, ScheduledTask] = {}
        self.task_queue = None  # 이벤트 루프에서 초기화됨
        self.running_tasks: Dict[str, asyncio.Task] = {}
        
        # 리소스 관리
        self.resource_pool = ResourcePool()
        self.resource_lock = None  # 이벤트 루프에서 초기화됨
        self._initialized = False
        
    async def _ensure_initialized(self):
        """이벤트 루프에서 초기화"""
        if not self._initialized:
            self.task_queue = asyncio.PriorityQueue()
            self.resource_lock = asyncio.Lock()
            self._initialized = True
        
        # 스케줄 관리
        self.scheduler_task: Optional[asyncio.Task] = None
        self.executor_task: Optional[asyncio.Task] = None
        self.cleanup_task: Optional[asyncio.Task] = None
        
        # 통계
        self.stats = {
            'total_tasks_executed': 0,
            'successful_tasks': 0,
            'failed_tasks': 0,
            'avg_execution_time': 0.0,
            'last_reset': datetime.now()
        }
    
    async def initialize(self):
        """조정자 초기화"""
        try:
            logger.info("🎬 멀티 계정 조정자 초기화 시작")
            
            # 의존 서비스 초기화
            if not hasattr(self.multi_account_manager, '_initialized'):
                await self.multi_account_manager.initialize()
            
            if not hasattr(self.feature_manager, '_initialized'):
                await self.feature_manager.initialize()
            
            # 기본 스케줄 설정
            await self._setup_default_schedules()
            
            logger.info("✅ 멀티 계정 조정자 초기화 완료")
            
        except Exception as e:
            logger.error(f"❌ 멀티 계정 조정자 초기화 실패: {e}")
            raise ConfigurationException("multi_account_coordinator", str(e))
    
    async def _setup_default_schedules(self):
        """기본 스케줄 설정"""
        
        # 매일 오전 9시 포트폴리오 최적화
        await self.schedule_recurring_task(
            name="daily_portfolio_optimization",
            function=self.feature_manager.run_portfolio_optimization_for_all,
            scheduled_time=datetime.now().replace(hour=9, minute=0, second=0, microsecond=0),
            interval_minutes=24 * 60,  # 24시간
            priority=TaskPriority.MEDIUM
        )
        
        # 매주 일요일 오전 10시 리밸런싱
        await self.schedule_recurring_task(
            name="weekly_rebalancing",
            function=lambda: self.feature_manager.execute_rebalancing_for_all(dry_run=False),
            scheduled_time=self._get_next_sunday(10, 0),
            interval_minutes=7 * 24 * 60,  # 1주일
            priority=TaskPriority.HIGH
        )
        
        # 매시간 리스크 분석
        await self.schedule_recurring_task(
            name="hourly_risk_analysis",
            function=self.feature_manager.run_risk_analysis_for_all,
            interval_minutes=60,
            priority=TaskPriority.MEDIUM
        )
        
        # 매일 오후 6시 성과 분석
        await self.schedule_recurring_task(
            name="daily_performance_analysis",
            function=self.feature_manager.run_performance_analysis_for_all,
            scheduled_time=datetime.now().replace(hour=18, minute=0, second=0, microsecond=0),
            interval_minutes=24 * 60,  # 24시간
            priority=TaskPriority.LOW
        )
        
        logger.info("📅 기본 스케줄 설정 완료")
    
    def _get_next_sunday(self, hour: int, minute: int) -> datetime:
        """다음 일요일 특정 시간 반환"""
        now = datetime.now()
        days_until_sunday = (6 - now.weekday()) % 7
        if days_until_sunday == 0 and now.hour >= hour:
            days_until_sunday = 7
        
        next_sunday = now + timedelta(days=days_until_sunday)
        return next_sunday.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    async def schedule_task(
        self,
        name: str,
        function: Callable,
        target_accounts: Optional[List[AccountID]] = None,
        priority: TaskPriority = TaskPriority.MEDIUM,
        scheduled_time: Optional[datetime] = None,
        max_retries: int = 3,
        timeout_seconds: int = 300
    ) -> str:
        """단일 작업 스케줄링"""
        await self._ensure_initialized()
        
        task_id = f"{name}_{uuid.uuid4().hex[:8]}"
        
        task = ScheduledTask(
            task_id=task_id,
            name=name,
            function=function,
            target_accounts=target_accounts,
            priority=priority,
            scheduled_time=scheduled_time or datetime.now(),
            max_retries=max_retries,
            timeout_seconds=timeout_seconds
        )
        
        self.scheduled_tasks[task_id] = task
        
        # 우선순위 큐에 추가
        await self.task_queue.put((priority.value, task.scheduled_time.timestamp(), task))
        
        logger.info(f"📋 작업 스케줄링: {name} (ID: {task_id}, 우선순위: {priority.name})")
        return task_id
    
    async def schedule_recurring_task(
        self,
        name: str,
        function: Callable,
        target_accounts: Optional[List[AccountID]] = None,
        priority: TaskPriority = TaskPriority.MEDIUM,
        scheduled_time: Optional[datetime] = None,
        interval_minutes: int = 60,
        max_retries: int = 3,
        timeout_seconds: int = 300
    ) -> str:
        """반복 작업 스케줄링"""
        
        task_id = f"{name}_recurring_{uuid.uuid4().hex[:8]}"
        
        task = ScheduledTask(
            task_id=task_id,
            name=name,
            function=function,
            target_accounts=target_accounts,
            priority=priority,
            scheduled_time=scheduled_time or datetime.now(),
            recurring=True,
            interval_minutes=interval_minutes,
            max_retries=max_retries,
            timeout_seconds=timeout_seconds
        )
        
        self.scheduled_tasks[task_id] = task
        
        # 우선순위 큐에 추가
        await self.task_queue.put((priority.value, task.scheduled_time.timestamp(), task))
        
        logger.info(f"🔄 반복 작업 스케줄링: {name} (ID: {task_id}, 간격: {interval_minutes}분)")
        return task_id
    
    async def cancel_task(self, task_id: str) -> bool:
        """작업 취소"""
        if task_id not in self.scheduled_tasks:
            return False
        
        task = self.scheduled_tasks[task_id]
        
        # 실행 중인 작업이면 중단
        if task_id in self.running_tasks:
            running_task = self.running_tasks[task_id]
            running_task.cancel()
            try:
                await running_task
            except asyncio.CancelledError:
                pass
        
        task.status = TaskStatus.CANCELLED
        logger.info(f"❌ 작업 취소: {task.name} (ID: {task_id})")
        return True
    
    async def execute_immediate_task(
        self,
        name: str,
        function: Callable,
        target_accounts: Optional[List[AccountID]] = None,
        priority: TaskPriority = TaskPriority.HIGH,
        timeout_seconds: int = 300
    ) -> MultiAccountOperationResult:
        """즉시 작업 실행"""
        
        # 리소스 확인
        if not await self._can_execute_task():
            raise KairosException("리소스 부족으로 즉시 실행 불가", "RESOURCE_EXHAUSTED")
        
        task_id = await self.schedule_task(
            name=f"immediate_{name}",
            function=function,
            target_accounts=target_accounts,
            priority=priority,
            scheduled_time=datetime.now(),
            timeout_seconds=timeout_seconds
        )
        
        # 작업 완료까지 대기
        task = self.scheduled_tasks[task_id]
        while task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
            await asyncio.sleep(0.1)
        
        if task.result:
            return task.result
        else:
            raise KairosException(f"작업 실행 실패: {task.last_error}", "TASK_EXECUTION_FAILED")
    
    async def _can_execute_task(self) -> bool:
        """작업 실행 가능 여부 확인"""
        async with self.resource_lock:
            # API 호출 제한 확인
            now = datetime.now()
            if (now - self.resource_pool.last_api_reset).total_seconds() >= 60:
                self.resource_pool.api_calls_this_minute = 0
                self.resource_pool.last_api_reset = now
            
            # 리소스 제한 확인
            if self.resource_pool.active_tasks >= self.resource_pool.max_concurrent_tasks:
                return False
            
            if self.resource_pool.api_calls_this_minute >= self.resource_pool.max_api_calls_per_minute:
                return False
            
            return True
    
    async def _execute_task(self, task: ScheduledTask) -> MultiAccountOperationResult:
        """작업 실행"""
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        
        async with self.resource_lock:
            self.resource_pool.active_tasks += 1
            # 계정별 활성 작업 수 증가
            if task.target_accounts:
                for account_id in task.target_accounts:
                    self.resource_pool.account_active_tasks[account_id] = \
                        self.resource_pool.account_active_tasks.get(account_id, 0) + 1
        
        try:
            logger.info(f"🚀 작업 실행 시작: {task.name} (ID: {task.task_id})")
            
            # 타임아웃 설정하여 함수 실행
            result = await asyncio.wait_for(
                task.function(task.target_accounts) if task.target_accounts else task.function(),
                timeout=task.timeout_seconds
            )
            
            task.result = result
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            
            # 통계 업데이트
            self.stats['successful_tasks'] += 1
            execution_time = (task.completed_at - task.started_at).total_seconds()
            self._update_avg_execution_time(execution_time)
            
            logger.info(f"✅ 작업 완료: {task.name} (실행시간: {execution_time:.2f}초)")
            
            return result
            
        except asyncio.TimeoutError:
            task.status = TaskStatus.FAILED
            task.last_error = f"작업 타임아웃 ({task.timeout_seconds}초)"
            self.stats['failed_tasks'] += 1
            logger.error(f"⏰ 작업 타임아웃: {task.name}")
            raise
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.last_error = str(e)
            task.completed_at = datetime.now()
            self.stats['failed_tasks'] += 1
            logger.error(f"❌ 작업 실행 실패: {task.name} - {e}")
            raise
            
        finally:
            # 리소스 정리
            async with self.resource_lock:
                self.resource_pool.active_tasks -= 1
                if task.target_accounts:
                    for account_id in task.target_accounts:
                        if account_id in self.resource_pool.account_active_tasks:
                            self.resource_pool.account_active_tasks[account_id] -= 1
                            if self.resource_pool.account_active_tasks[account_id] <= 0:
                                del self.resource_pool.account_active_tasks[account_id]
            
            self.stats['total_tasks_executed'] += 1
    
    def _update_avg_execution_time(self, execution_time: float):
        """평균 실행 시간 업데이트"""
        total_successful = self.stats['successful_tasks']
        if total_successful == 1:
            self.stats['avg_execution_time'] = execution_time
        else:
            current_avg = self.stats['avg_execution_time']
            self.stats['avg_execution_time'] = (current_avg * (total_successful - 1) + execution_time) / total_successful
    
    async def _scheduler_loop(self):
        """스케줄러 메인 루프"""
        logger.info("📅 스케줄러 시작")
        
        while True:
            try:
                # 대기 중인 작업 확인
                if not self.task_queue.empty():
                    try:
                        # 논블로킹으로 작업 가져오기
                        priority, scheduled_timestamp, task = await asyncio.wait_for(
                            self.task_queue.get(), timeout=1.0
                        )
                        
                        # 실행 시간 확인
                        scheduled_time = datetime.fromtimestamp(scheduled_timestamp)
                        if scheduled_time <= datetime.now():
                            # 리소스 확인 후 실행
                            if await self._can_execute_task():
                                # 비동기 실행
                                asyncio.create_task(self._handle_task_execution(task))
                            else:
                                # 리소스 부족시 다시 큐에 추가
                                await self.task_queue.put((priority, scheduled_timestamp, task))
                        else:
                            # 아직 실행 시간이 아니면 다시 큐에 추가
                            await self.task_queue.put((priority, scheduled_timestamp, task))
                    
                    except asyncio.TimeoutError:
                        pass  # 타임아웃은 정상적인 동작
                
                await asyncio.sleep(1)  # 1초 대기
                
            except asyncio.CancelledError:
                logger.info("📅 스케줄러 종료")
                break
            except Exception as e:
                logger.error(f"❌ 스케줄러 오류: {e}")
                await asyncio.sleep(5)  # 오류 발생시 5초 대기
    
    async def _handle_task_execution(self, task: ScheduledTask):
        """작업 실행 핸들러"""
        task_asyncio_task = asyncio.create_task(self._execute_task_with_retry(task))
        self.running_tasks[task.task_id] = task_asyncio_task
        
        try:
            await task_asyncio_task
        finally:
            # 완료된 작업은 running_tasks에서 제거
            if task.task_id in self.running_tasks:
                del self.running_tasks[task.task_id]
    
    async def _execute_task_with_retry(self, task: ScheduledTask):
        """재시도 로직이 포함된 작업 실행"""
        for attempt in range(task.max_retries + 1):
            try:
                result = await self._execute_task(task)
                
                # 반복 작업인 경우 다음 실행 스케줄링
                if task.recurring and task.status == TaskStatus.COMPLETED:
                    await self._schedule_next_recurring(task)
                
                return result
                
            except Exception as e:
                task.retry_count = attempt + 1
                
                if attempt < task.max_retries:
                    wait_time = min(2 ** attempt, 60)  # 지수 백오프, 최대 60초
                    logger.warning(f"⚠️ 작업 실패 ({attempt + 1}/{task.max_retries + 1}), {wait_time}초 후 재시도: {task.name}")
                    await asyncio.sleep(wait_time)
                    task.status = TaskStatus.PENDING  # 재시도를 위해 상태 리셋
                else:
                    logger.error(f"❌ 작업 최종 실패: {task.name} - {e}")
                    raise
    
    async def _schedule_next_recurring(self, task: ScheduledTask):
        """반복 작업의 다음 실행 스케줄링"""
        if not task.recurring or not task.interval_minutes:
            return
        
        next_execution = datetime.now() + timedelta(minutes=task.interval_minutes)
        
        # 새로운 작업 인스턴스 생성
        next_task = ScheduledTask(
            task_id=f"{task.name}_{uuid.uuid4().hex[:8]}",
            name=task.name,
            function=task.function,
            target_accounts=task.target_accounts,
            priority=task.priority,
            scheduled_time=next_execution,
            recurring=True,
            interval_minutes=task.interval_minutes,
            max_retries=task.max_retries,
            timeout_seconds=task.timeout_seconds
        )
        
        self.scheduled_tasks[next_task.task_id] = next_task
        await self.task_queue.put((next_task.priority.value, next_task.scheduled_time.timestamp(), next_task))
        
        logger.debug(f"🔄 반복 작업 재스케줄링: {task.name} -> {next_execution}")
    
    async def _cleanup_completed_tasks(self):
        """완료된 작업 정리"""
        while True:
            try:
                cutoff_time = datetime.now() - timedelta(hours=24)  # 24시간 이전 작업들 정리
                
                to_remove = []
                for task_id, task in self.scheduled_tasks.items():
                    if (task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED] 
                        and task.completed_at 
                        and task.completed_at < cutoff_time):
                        to_remove.append(task_id)
                
                for task_id in to_remove:
                    del self.scheduled_tasks[task_id]
                
                if to_remove:
                    logger.info(f"🧹 완료된 작업 {len(to_remove)}개 정리")
                
                await asyncio.sleep(3600)  # 1시간마다 정리
                
            except asyncio.CancelledError:
                logger.info("🧹 정리 작업 종료")
                break
            except Exception as e:
                logger.error(f"❌ 정리 작업 오류: {e}")
                await asyncio.sleep(300)  # 오류 발생시 5분 대기
    
    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """작업 상태 조회"""
        if task_id not in self.scheduled_tasks:
            return None
        
        task = self.scheduled_tasks[task_id]
        return {
            'task_id': task.task_id,
            'name': task.name,
            'status': task.status.value,
            'priority': task.priority.name,
            'created_at': task.created_at.isoformat(),
            'started_at': task.started_at.isoformat() if task.started_at else None,
            'completed_at': task.completed_at.isoformat() if task.completed_at else None,
            'retry_count': task.retry_count,
            'last_error': task.last_error,
            'recurring': task.recurring,
            'interval_minutes': task.interval_minutes
        }
    
    async def get_system_status(self) -> Dict[str, Any]:
        """시스템 전체 상태 조회"""
        task_counts = defaultdict(int)
        for task in self.scheduled_tasks.values():
            task_counts[task.status.value] += 1
        
        return {
            'coordinator_status': 'active',
            'resource_pool': {
                'active_tasks': self.resource_pool.active_tasks,
                'max_concurrent_tasks': self.resource_pool.max_concurrent_tasks,
                'account_active_tasks': dict(self.resource_pool.account_active_tasks),
                'api_calls_this_minute': self.resource_pool.api_calls_this_minute,
                'max_api_calls_per_minute': self.resource_pool.max_api_calls_per_minute
            },
            'task_statistics': {
                'total_scheduled': len(self.scheduled_tasks),
                'pending': task_counts[TaskStatus.PENDING.value],
                'running': task_counts[TaskStatus.RUNNING.value],
                'completed': task_counts[TaskStatus.COMPLETED.value],
                'failed': task_counts[TaskStatus.FAILED.value],
                'cancelled': task_counts[TaskStatus.CANCELLED.value]
            },
            'execution_stats': self.stats,
            'queue_size': self.task_queue.qsize(),
            'last_update': datetime.now().isoformat()
        }
    
    async def start(self):
        """서비스 시작"""
        await self.initialize()
        
        # 백그라운드 작업 시작
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        self.cleanup_task = asyncio.create_task(self._cleanup_completed_tasks())
        
        logger.info("🎬 멀티 계정 조정자 시작")
    
    async def stop(self):
        """서비스 중지"""
        logger.info("🎬 멀티 계정 조정자 중지 시작")
        
        # 모든 실행 중인 작업 취소
        for task_id in list(self.running_tasks.keys()):
            await self.cancel_task(task_id)
        
        # 백그라운드 작업 취소
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass
        
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("🎬 멀티 계정 조정자 중지 완료")
    
    async def health_check(self) -> Dict[str, Any]:
        """헬스체크"""
        return {
            'service': 'multi_account_coordinator',
            'status': 'healthy' if (self.scheduler_task and not self.scheduler_task.done()) else 'degraded',
            'system_status': await self.get_system_status(),
            'last_check': datetime.now().isoformat()
        }


# 전역 인스턴스
_multi_account_coordinator: Optional[MultiAccountCoordinator] = None

def get_multi_account_coordinator() -> MultiAccountCoordinator:
    """멀티 계정 조정자 인스턴스 반환"""
    global _multi_account_coordinator
    if _multi_account_coordinator is None:
        _multi_account_coordinator = MultiAccountCoordinator()
    return _multi_account_coordinator