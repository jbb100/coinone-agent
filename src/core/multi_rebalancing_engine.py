"""
Multi-Account Rebalancing Engine for KAIROS-1 System

여러 계정의 리밸런싱을 스케줄링하고 조율하는 엔진
"""

import asyncio
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from enum import Enum
from loguru import logger
from dataclasses import dataclass
from croniter import croniter

from .types import AccountID, MarketSeason, RiskLevel
from .base_service import BaseService, ServiceConfig
from .exceptions import KairosException, TradingException
from .multi_portfolio_manager import get_multi_portfolio_manager
from .multi_account_manager import get_multi_account_manager


class RebalanceScheduleType(Enum):
    """리밸런싱 스케줄 타입"""
    MANUAL = "manual"           # 수동 실행
    DAILY = "daily"             # 매일
    WEEKLY = "weekly"           # 매주
    MONTHLY = "monthly"         # 매월
    MARKET_TRIGGER = "market_trigger"  # 시장 조건 트리거
    DEVIATION_TRIGGER = "deviation_trigger"  # 편차 트리거


@dataclass
class RebalanceTask:
    """리밸런싱 작업"""
    account_id: AccountID
    schedule_type: RebalanceScheduleType
    cron_expression: Optional[str] = None
    next_run: Optional[datetime] = None
    last_run: Optional[datetime] = None
    enabled: bool = True
    force: bool = False
    
    # 트리거 조건
    deviation_threshold: float = 0.05  # 5% 편차
    market_condition: Optional[MarketSeason] = None


class MultiRebalancingEngine(BaseService):
    """멀티 계정 리밸런싱 엔진"""
    
    def __init__(self):
        super().__init__(ServiceConfig(
            name="multi_rebalancing_engine",
            enabled=True,
            health_check_interval=60  # 1분마다 헬스체크 및 스케줄 확인
        ))
        
        self.portfolio_manager = get_multi_portfolio_manager()
        self.account_manager = get_multi_account_manager()
        
        # 스케줄링 관리
        self.rebalance_tasks: Dict[AccountID, RebalanceTask] = {}
        self.running_tasks: Set[AccountID] = set()
        
        # 글로벌 설정
        self.max_concurrent_rebalancing = 3
        self.rebalance_semaphore = asyncio.Semaphore(self.max_concurrent_rebalancing)
        
        # 상태 추적
        self.last_market_check = None
        self.current_market_season = MarketSeason.NEUTRAL
        
        # 통계
        self.rebalance_stats = {
            'total_runs': 0,
            'successful_runs': 0,
            'failed_runs': 0,
            'last_successful_run': None,
            'last_failed_run': None
        }
    
    async def initialize(self):
        """리밸런싱 엔진 초기화"""
        try:
            logger.info("⚖️ 멀티 리밸런싱 엔진 초기화 시작")
            
            # 포트폴리오 관리자 초기화
            await self.portfolio_manager.initialize()
            
            # 기본 스케줄 설정 로드
            await self._load_default_schedules()
            
            # 스케줄러 시작
            self._scheduler_task = asyncio.create_task(self._scheduler_loop())
            
            logger.info(f"✅ 멀티 리밸런싱 엔진 초기화 완료: {len(self.rebalance_tasks)}개 작업")
            
        except Exception as e:
            logger.error(f"❌ 멀티 리밸런싱 엔진 초기화 실패: {e}")
            raise
    
    async def _load_default_schedules(self):
        """기본 스케줄 설정 로드"""
        accounts = await self.account_manager.get_all_accounts()
        
        for account in accounts:
            account_id = account['account_id']
            
            # 계정별 리밸런싱 주기 설정 (예: 매주 월요일 09:00)
            schedule_type = RebalanceScheduleType.WEEKLY
            cron_expr = "0 9 * * 1"  # 매주 월요일 오전 9시
            
            task = RebalanceTask(
                account_id=account_id,
                schedule_type=schedule_type,
                cron_expression=cron_expr,
                next_run=self._calculate_next_run(cron_expr),
                enabled=account['auto_rebalance']
            )
            
            self.rebalance_tasks[account_id] = task
            logger.info(f"📅 계정 {account_id} 스케줄 설정: {schedule_type.value}")
    
    def _calculate_next_run(self, cron_expression: str) -> datetime:
        """다음 실행 시간 계산"""
        try:
            cron = croniter(cron_expression, datetime.now())
            return cron.get_next(datetime)
        except Exception as e:
            logger.error(f"❌ Cron 표현식 파싱 실패: {cron_expression} - {e}")
            # 기본값: 1시간 후
            return datetime.now() + timedelta(hours=1)
    
    async def _scheduler_loop(self):
        """스케줄러 메인 루프"""
        logger.info("🕐 리밸런싱 스케줄러 시작")
        
        while True:
            try:
                await asyncio.sleep(60)  # 1분마다 체크
                
                current_time = datetime.now()
                
                # 시장 상황 업데이트
                await self._update_market_condition()
                
                # 스케줄된 작업 실행
                await self._execute_scheduled_tasks(current_time)
                
                # 트리거 조건 확인
                await self._check_trigger_conditions()
                
            except Exception as e:
                logger.error(f"❌ 스케줄러 루프 에러: {e}")
                await asyncio.sleep(30)  # 에러 시 30초 대기
    
    async def _update_market_condition(self):
        """시장 상황 업데이트"""
        try:
            # TODO: 실제 시장 분석 로직 구현
            # 임시로 랜덤 또는 고정값 사용
            self.current_market_season = await self.portfolio_manager.get_market_season()
            self.last_market_check = datetime.now()
            
        except Exception as e:
            logger.error(f"❌ 시장 상황 업데이트 실패: {e}")
    
    async def _execute_scheduled_tasks(self, current_time: datetime):
        """스케줄된 작업 실행"""
        tasks_to_run = []
        
        for account_id, task in self.rebalance_tasks.items():
            if not task.enabled or account_id in self.running_tasks:
                continue
            
            if task.next_run and current_time >= task.next_run:
                tasks_to_run.append(task)
        
        if tasks_to_run:
            logger.info(f"📅 {len(tasks_to_run)}개 스케줄된 리밸런싱 작업 실행")
            
            # 병렬 실행
            await asyncio.gather(*[
                self._execute_rebalance_task(task) for task in tasks_to_run
            ], return_exceptions=True)
    
    async def _check_trigger_conditions(self):
        """트리거 조건 확인"""
        for account_id, task in self.rebalance_tasks.items():
            if not task.enabled or account_id in self.running_tasks:
                continue
            
            try:
                # 편차 트리거 확인
                if task.schedule_type == RebalanceScheduleType.DEVIATION_TRIGGER:
                    if await self._check_deviation_trigger(account_id, task.deviation_threshold):
                        logger.info(f"📊 계정 {account_id} 편차 트리거 발동")
                        await self._execute_rebalance_task(task)
                
                # 시장 조건 트리거 확인
                elif task.schedule_type == RebalanceScheduleType.MARKET_TRIGGER:
                    if task.market_condition and self.current_market_season == task.market_condition:
                        logger.info(f"🌊 계정 {account_id} 시장 트리거 발동: {self.current_market_season.value}")
                        await self._execute_rebalance_task(task)
                        
            except Exception as e:
                logger.error(f"❌ 계정 {account_id} 트리거 조건 확인 실패: {e}")
    
    async def _check_deviation_trigger(self, account_id: AccountID, threshold: float) -> bool:
        """편차 트리거 조건 확인"""
        try:
            if account_id not in self.portfolio_manager.account_managers:
                return False
            
            manager = self.portfolio_manager.account_managers[account_id]
            target_weights = await manager.calculate_target_weights(self.current_market_season)
            
            return await manager.needs_rebalancing(target_weights, threshold)
            
        except Exception as e:
            logger.error(f"❌ 계정 {account_id} 편차 확인 실패: {e}")
            return False
    
    async def _execute_rebalance_task(self, task: RebalanceTask):
        """리밸런싱 작업 실행"""
        account_id = task.account_id
        
        async with self.rebalance_semaphore:
            if account_id in self.running_tasks:
                logger.warning(f"⚠️ 계정 {account_id} 리밸런싱 이미 실행 중")
                return
            
            self.running_tasks.add(account_id)
            
            try:
                logger.info(f"⚖️ 계정 {account_id} 리밸런싱 시작")
                
                # 리밸런싱 실행
                result = await self.portfolio_manager.rebalance_account(account_id, task.force)
                
                # 작업 상태 업데이트
                task.last_run = datetime.now()
                if task.cron_expression:
                    task.next_run = self._calculate_next_run(task.cron_expression)
                
                # 통계 업데이트
                self.rebalance_stats['total_runs'] += 1
                
                if result['action'] == 'completed':
                    self.rebalance_stats['successful_runs'] += 1
                    self.rebalance_stats['last_successful_run'] = datetime.now()
                    logger.info(f"✅ 계정 {account_id} 리밸런싱 성공")
                elif result['action'] == 'failed':
                    self.rebalance_stats['failed_runs'] += 1
                    self.rebalance_stats['last_failed_run'] = datetime.now()
                    logger.error(f"❌ 계정 {account_id} 리밸런싱 실패: {result.get('error', 'Unknown error')}")
                else:
                    logger.info(f"⏭️ 계정 {account_id} 리밸런싱 스킵: {result.get('reason', 'No reason')}")
                
            except Exception as e:
                logger.error(f"❌ 계정 {account_id} 리밸런싱 작업 실행 실패: {e}")
                self.rebalance_stats['failed_runs'] += 1
                self.rebalance_stats['last_failed_run'] = datetime.now()
                
            finally:
                self.running_tasks.discard(account_id)
    
    async def add_account_schedule(self, account_id: AccountID, 
                                  schedule_type: RebalanceScheduleType,
                                  cron_expression: Optional[str] = None,
                                  **kwargs) -> bool:
        """계정 스케줄 추가"""
        try:
            task = RebalanceTask(
                account_id=account_id,
                schedule_type=schedule_type,
                cron_expression=cron_expression,
                next_run=self._calculate_next_run(cron_expression) if cron_expression else None,
                **kwargs
            )
            
            self.rebalance_tasks[account_id] = task
            logger.info(f"📅 계정 {account_id} 스케줄 추가: {schedule_type.value}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 계정 {account_id} 스케줄 추가 실패: {e}")
            return False
    
    async def remove_account_schedule(self, account_id: AccountID) -> bool:
        """계정 스케줄 제거"""
        try:
            if account_id in self.rebalance_tasks:
                del self.rebalance_tasks[account_id]
                logger.info(f"📅 계정 {account_id} 스케줄 제거")
                return True
            return False
            
        except Exception as e:
            logger.error(f"❌ 계정 {account_id} 스케줄 제거 실패: {e}")
            return False
    
    async def enable_account_schedule(self, account_id: AccountID, enabled: bool = True) -> bool:
        """계정 스케줄 활성화/비활성화"""
        try:
            if account_id in self.rebalance_tasks:
                self.rebalance_tasks[account_id].enabled = enabled
                logger.info(f"📅 계정 {account_id} 스케줄 {'활성화' if enabled else '비활성화'}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"❌ 계정 {account_id} 스케줄 상태 변경 실패: {e}")
            return False
    
    async def trigger_manual_rebalance(self, account_id: Optional[AccountID] = None, 
                                     force: bool = False) -> Dict[str, Any]:
        """수동 리밸런싱 트리거"""
        try:
            if account_id:
                # 단일 계정 리밸런싱
                logger.info(f"🔧 계정 {account_id} 수동 리밸런싱 트리거")
                result = await self.portfolio_manager.rebalance_account(account_id, force)
                return {'single_account': result}
            else:
                # 전체 계정 리밸런싱
                logger.info("🔧 전체 계정 수동 리밸런싱 트리거")
                results = await self.portfolio_manager.rebalance_all_accounts(force)
                return {'all_accounts': results}
                
        except Exception as e:
            logger.error(f"❌ 수동 리밸런싱 트리거 실패: {e}")
            return {'error': str(e)}
    
    async def get_schedule_status(self) -> Dict[str, Any]:
        """스케줄 상태 조회"""
        return {
            'total_schedules': len(self.rebalance_tasks),
            'enabled_schedules': len([t for t in self.rebalance_tasks.values() if t.enabled]),
            'running_tasks': len(self.running_tasks),
            'current_market_season': self.current_market_season.value,
            'last_market_check': self.last_market_check.isoformat() if self.last_market_check else None,
            'statistics': self.rebalance_stats,
            'schedules': [
                {
                    'account_id': task.account_id,
                    'schedule_type': task.schedule_type.value,
                    'enabled': task.enabled,
                    'next_run': task.next_run.isoformat() if task.next_run else None,
                    'last_run': task.last_run.isoformat() if task.last_run else None
                }
                for task in self.rebalance_tasks.values()
            ]
        }
    
    async def start(self):
        """서비스 시작"""
        await self.initialize()
        logger.info("⚖️ 멀티 리밸런싱 엔진 시작")
    
    async def stop(self):
        """서비스 중지"""
        await self.shutdown()
    
    async def health_check(self) -> Dict[str, Any]:
        """헬스체크"""
        return {
            'service': 'multi_rebalancing_engine',
            'status': 'healthy' if len(self.rebalance_tasks) > 0 else 'degraded',
            'active_schedules': len([t for t in self.rebalance_tasks.values() if t.enabled]),
            'running_tasks': len(self.running_tasks),
            'last_check': datetime.now().isoformat()
        }
    
    async def shutdown(self):
        """서비스 종료"""
        if hasattr(self, '_scheduler_task'):
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        
        logger.info("⚖️ 멀티 리밸런싱 엔진 종료")


# 전역 멀티 리밸런싱 엔진 인스턴스
_multi_rebalancing_engine: Optional[MultiRebalancingEngine] = None

def get_multi_rebalancing_engine() -> MultiRebalancingEngine:
    """멀티 리밸런싱 엔진 인스턴스 반환"""
    global _multi_rebalancing_engine
    if _multi_rebalancing_engine is None:
        _multi_rebalancing_engine = MultiRebalancingEngine()
    return _multi_rebalancing_engine