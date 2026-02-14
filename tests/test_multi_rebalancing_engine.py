"""
Multi-Rebalancing Engine 테스트 모듈

멀티 계정 리밸런싱 엔진 테스트
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, AsyncMock, patch

from src.core.multi_rebalancing_engine import (
    MultiRebalancingEngine,
    RebalanceScheduleType,
    RebalanceTask,
    get_multi_rebalancing_engine
)
from src.core.types import AccountID, MarketSeason


class TestRebalanceScheduleType:
    """RebalanceScheduleType Enum 테스트"""

    def test_schedule_types_exist(self):
        """모든 스케줄 타입이 정의되어 있는지 확인"""
        assert RebalanceScheduleType.MANUAL.value == "manual"
        assert RebalanceScheduleType.DAILY.value == "daily"
        assert RebalanceScheduleType.WEEKLY.value == "weekly"
        assert RebalanceScheduleType.MONTHLY.value == "monthly"
        assert RebalanceScheduleType.MARKET_TRIGGER.value == "market_trigger"
        assert RebalanceScheduleType.DEVIATION_TRIGGER.value == "deviation_trigger"

    def test_schedule_type_count(self):
        """스케줄 타입 개수 확인"""
        assert len(RebalanceScheduleType) == 6


class TestRebalanceTask:
    """RebalanceTask Dataclass 테스트"""

    def test_task_creation(self):
        """RebalanceTask 생성 테스트"""
        task = RebalanceTask(
            account_id=AccountID("test_acc"),
            schedule_type=RebalanceScheduleType.WEEKLY
        )

        assert task.account_id == AccountID("test_acc")
        assert task.schedule_type == RebalanceScheduleType.WEEKLY
        assert task.enabled is True
        assert task.force is False

    def test_task_default_values(self):
        """기본값 테스트"""
        task = RebalanceTask(
            account_id=AccountID("test"),
            schedule_type=RebalanceScheduleType.MANUAL
        )

        assert task.cron_expression is None
        assert task.next_run is None
        assert task.last_run is None
        assert task.deviation_threshold == 0.05

    def test_task_with_cron(self):
        """Cron 표현식 포함 태스크"""
        task = RebalanceTask(
            account_id=AccountID("test"),
            schedule_type=RebalanceScheduleType.WEEKLY,
            cron_expression="0 9 * * 1"
        )

        assert task.cron_expression == "0 9 * * 1"


class TestMultiRebalancingEngine:
    """MultiRebalancingEngine 클래스 테스트"""

    @pytest.fixture
    def engine(self):
        """MultiRebalancingEngine 인스턴스"""
        with patch('src.core.multi_rebalancing_engine.get_multi_portfolio_manager') as mock_pm, \
             patch('src.core.multi_rebalancing_engine.get_multi_account_manager') as mock_am:
            mock_pm.return_value = AsyncMock()
            mock_am.return_value = AsyncMock()
            return MultiRebalancingEngine()

    def test_init(self, engine):
        """초기화 테스트"""
        assert engine.max_concurrent_rebalancing == 3
        assert engine.rebalance_tasks == {}
        assert engine.running_tasks == set()
        assert engine.current_market_season == MarketSeason.NEUTRAL

    def test_init_stats(self, engine):
        """통계 초기화 테스트"""
        assert engine.rebalance_stats['total_runs'] == 0
        assert engine.rebalance_stats['successful_runs'] == 0
        assert engine.rebalance_stats['failed_runs'] == 0

    def test_calculate_next_run_valid_cron(self, engine):
        """유효한 Cron 표현식 다음 실행 시간 계산"""
        next_run = engine._calculate_next_run("0 9 * * 1")  # 매주 월요일 9시

        assert next_run is not None
        assert isinstance(next_run, datetime)
        assert next_run > datetime.now()

    def test_calculate_next_run_invalid_cron(self, engine):
        """잘못된 Cron 표현식 처리"""
        next_run = engine._calculate_next_run("invalid cron")

        # 에러 시 1시간 후 기본값
        assert next_run is not None
        assert next_run > datetime.now()
        assert next_run < datetime.now() + timedelta(hours=2)

    @pytest.mark.asyncio
    async def test_add_account_schedule(self, engine):
        """계정 스케줄 추가"""
        result = await engine.add_account_schedule(
            account_id=AccountID("test_acc"),
            schedule_type=RebalanceScheduleType.WEEKLY,
            cron_expression="0 9 * * 1"
        )

        assert result is True
        assert AccountID("test_acc") in engine.rebalance_tasks

    @pytest.mark.asyncio
    async def test_add_account_schedule_with_options(self, engine):
        """옵션 포함 스케줄 추가"""
        result = await engine.add_account_schedule(
            account_id=AccountID("test_acc"),
            schedule_type=RebalanceScheduleType.DEVIATION_TRIGGER,
            deviation_threshold=0.10,
            enabled=False
        )

        assert result is True
        task = engine.rebalance_tasks[AccountID("test_acc")]
        assert task.deviation_threshold == 0.10
        assert task.enabled is False

    @pytest.mark.asyncio
    async def test_remove_account_schedule(self, engine):
        """계정 스케줄 제거"""
        # 먼저 추가
        await engine.add_account_schedule(
            account_id=AccountID("test_acc"),
            schedule_type=RebalanceScheduleType.WEEKLY
        )

        # 제거
        result = await engine.remove_account_schedule(AccountID("test_acc"))

        assert result is True
        assert AccountID("test_acc") not in engine.rebalance_tasks

    @pytest.mark.asyncio
    async def test_remove_nonexistent_schedule(self, engine):
        """존재하지 않는 스케줄 제거"""
        result = await engine.remove_account_schedule(AccountID("nonexistent"))

        assert result is False

    @pytest.mark.asyncio
    async def test_enable_account_schedule(self, engine):
        """스케줄 활성화"""
        await engine.add_account_schedule(
            account_id=AccountID("test_acc"),
            schedule_type=RebalanceScheduleType.WEEKLY,
            enabled=False
        )

        result = await engine.enable_account_schedule(AccountID("test_acc"), True)

        assert result is True
        assert engine.rebalance_tasks[AccountID("test_acc")].enabled is True

    @pytest.mark.asyncio
    async def test_disable_account_schedule(self, engine):
        """스케줄 비활성화"""
        await engine.add_account_schedule(
            account_id=AccountID("test_acc"),
            schedule_type=RebalanceScheduleType.WEEKLY,
            enabled=True
        )

        result = await engine.enable_account_schedule(AccountID("test_acc"), False)

        assert result is True
        assert engine.rebalance_tasks[AccountID("test_acc")].enabled is False

    @pytest.mark.asyncio
    async def test_trigger_manual_rebalance_single(self, engine):
        """단일 계정 수동 리밸런싱"""
        engine.portfolio_manager.rebalance_account = AsyncMock(return_value={
            'action': 'completed',
            'account_id': 'test_acc'
        })

        result = await engine.trigger_manual_rebalance(AccountID("test_acc"))

        assert 'single_account' in result
        engine.portfolio_manager.rebalance_account.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_manual_rebalance_all(self, engine):
        """전체 계정 수동 리밸런싱"""
        engine.portfolio_manager.rebalance_all_accounts = AsyncMock(return_value=[])

        result = await engine.trigger_manual_rebalance()

        assert 'all_accounts' in result
        engine.portfolio_manager.rebalance_all_accounts.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_schedule_status(self, engine):
        """스케줄 상태 조회"""
        await engine.add_account_schedule(
            account_id=AccountID("test_acc"),
            schedule_type=RebalanceScheduleType.WEEKLY
        )

        status = await engine.get_schedule_status()

        assert status['total_schedules'] == 1
        assert status['enabled_schedules'] == 1
        assert status['running_tasks'] == 0
        assert 'schedules' in status

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, engine):
        """헬스체크 - 정상"""
        await engine.add_account_schedule(
            account_id=AccountID("test_acc"),
            schedule_type=RebalanceScheduleType.WEEKLY
        )

        health = await engine.health_check()

        assert health['service'] == 'multi_rebalancing_engine'
        assert health['status'] == 'healthy'
        assert health['active_schedules'] == 1

    @pytest.mark.asyncio
    async def test_health_check_degraded(self, engine):
        """헬스체크 - 스케줄 없음"""
        health = await engine.health_check()

        assert health['status'] == 'degraded'

    @pytest.mark.asyncio
    async def test_update_market_condition(self, engine):
        """시장 상황 업데이트"""
        engine.portfolio_manager.get_market_season = AsyncMock(return_value=MarketSeason.RISK_ON)

        await engine._update_market_condition()

        assert engine.current_market_season == MarketSeason.RISK_ON
        assert engine.last_market_check is not None

    @pytest.mark.asyncio
    async def test_execute_rebalance_task_already_running(self, engine):
        """이미 실행 중인 태스크"""
        task = RebalanceTask(
            account_id=AccountID("test_acc"),
            schedule_type=RebalanceScheduleType.MANUAL
        )

        engine.running_tasks.add(AccountID("test_acc"))

        # 이미 실행 중이면 바로 리턴
        await engine._execute_rebalance_task(task)

        # 중복 실행 없음 확인
        engine.portfolio_manager.rebalance_account.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_rebalance_task_success(self, engine):
        """태스크 실행 성공"""
        task = RebalanceTask(
            account_id=AccountID("test_acc"),
            schedule_type=RebalanceScheduleType.MANUAL,
            cron_expression="0 9 * * 1"
        )

        engine.portfolio_manager.rebalance_account = AsyncMock(return_value={
            'action': 'completed'
        })

        await engine._execute_rebalance_task(task)

        assert engine.rebalance_stats['successful_runs'] == 1
        assert task.last_run is not None
        assert AccountID("test_acc") not in engine.running_tasks

    @pytest.mark.asyncio
    async def test_execute_rebalance_task_failure(self, engine):
        """태스크 실행 실패"""
        task = RebalanceTask(
            account_id=AccountID("test_acc"),
            schedule_type=RebalanceScheduleType.MANUAL
        )

        engine.portfolio_manager.rebalance_account = AsyncMock(return_value={
            'action': 'failed',
            'error': 'Test error'
        })

        await engine._execute_rebalance_task(task)

        assert engine.rebalance_stats['failed_runs'] == 1
        assert AccountID("test_acc") not in engine.running_tasks

    @pytest.mark.asyncio
    async def test_shutdown(self, engine):
        """서비스 종료"""
        # 실제 취소 가능한 태스크 생성
        async def dummy_task():
            try:
                await asyncio.sleep(100)
            except asyncio.CancelledError:
                pass

        engine._scheduler_task = asyncio.create_task(dummy_task())

        await engine.shutdown()

        # 태스크가 취소되었는지 확인
        assert engine._scheduler_task.cancelled() or engine._scheduler_task.done()


class TestGetMultiRebalancingEngine:
    """get_multi_rebalancing_engine 함수 테스트"""

    def test_singleton_pattern(self):
        """싱글톤 패턴 테스트"""
        import src.core.multi_rebalancing_engine as mre
        mre._multi_rebalancing_engine = None

        with patch('src.core.multi_rebalancing_engine.get_multi_portfolio_manager'), \
             patch('src.core.multi_rebalancing_engine.get_multi_account_manager'):
            engine1 = get_multi_rebalancing_engine()
            engine2 = get_multi_rebalancing_engine()

            assert engine1 is engine2


class TestMultiRebalancingEngineAdvanced:
    """MultiRebalancingEngine 고급 테스트"""

    @pytest.fixture
    def engine(self):
        """MultiRebalancingEngine 인스턴스"""
        with patch('src.core.multi_rebalancing_engine.get_multi_portfolio_manager') as mock_pm, \
             patch('src.core.multi_rebalancing_engine.get_multi_account_manager') as mock_am:
            mock_pm.return_value = AsyncMock()
            mock_am.return_value = AsyncMock()
            return MultiRebalancingEngine()

    @pytest.mark.asyncio
    async def test_execute_rebalance_task_skip(self, engine):
        """태스크 실행 스킵"""
        task = RebalanceTask(
            account_id=AccountID("test_acc"),
            schedule_type=RebalanceScheduleType.MANUAL
        )

        engine.portfolio_manager.rebalance_account = AsyncMock(return_value={
            'action': 'skipped',
            'reason': 'No changes needed'
        })

        await engine._execute_rebalance_task(task)

        # 스킵된 경우 통계에 추가되지 않음
        assert engine.rebalance_stats['successful_runs'] == 0
        assert engine.rebalance_stats['failed_runs'] == 0

    @pytest.mark.asyncio
    async def test_execute_rebalance_task_exception(self, engine):
        """태스크 실행 중 예외 발생"""
        task = RebalanceTask(
            account_id=AccountID("test_acc"),
            schedule_type=RebalanceScheduleType.MANUAL
        )

        engine.portfolio_manager.rebalance_account = AsyncMock(side_effect=Exception("Test exception"))

        await engine._execute_rebalance_task(task)

        # 예외 발생 시 failed_runs 증가
        assert engine.rebalance_stats['failed_runs'] == 1
        assert engine.rebalance_stats['last_failed_run'] is not None
        # running_tasks에서 제거됨
        assert AccountID("test_acc") not in engine.running_tasks

    @pytest.mark.asyncio
    async def test_check_deviation_trigger_true(self, engine):
        """편차 트리거 조건 충족"""
        account_id = AccountID("test_acc")

        # account_manager mock 설정
        mock_manager = AsyncMock()
        mock_manager.calculate_target_weights = AsyncMock(return_value={"BTC": 0.5, "ETH": 0.5})
        mock_manager.needs_rebalancing = AsyncMock(return_value=True)

        engine.portfolio_manager.account_managers = {account_id: mock_manager}

        result = await engine._check_deviation_trigger(account_id, 0.05)

        assert result == True

    @pytest.mark.asyncio
    async def test_check_deviation_trigger_false(self, engine):
        """편차 트리거 조건 미충족"""
        account_id = AccountID("test_acc")

        mock_manager = AsyncMock()
        mock_manager.calculate_target_weights = AsyncMock(return_value={"BTC": 0.5, "ETH": 0.5})
        mock_manager.needs_rebalancing = AsyncMock(return_value=False)

        engine.portfolio_manager.account_managers = {account_id: mock_manager}

        result = await engine._check_deviation_trigger(account_id, 0.05)

        assert result == False

    @pytest.mark.asyncio
    async def test_check_deviation_trigger_no_manager(self, engine):
        """계정 매니저 없는 경우"""
        result = await engine._check_deviation_trigger(AccountID("nonexistent"), 0.05)

        assert result == False

    @pytest.mark.asyncio
    async def test_check_deviation_trigger_exception(self, engine):
        """편차 트리거 확인 중 예외"""
        account_id = AccountID("test_acc")

        mock_manager = AsyncMock()
        mock_manager.calculate_target_weights = AsyncMock(side_effect=Exception("Test error"))

        engine.portfolio_manager.account_managers = {account_id: mock_manager}

        result = await engine._check_deviation_trigger(account_id, 0.05)

        assert result == False

    @pytest.mark.asyncio
    async def test_update_market_condition_exception(self, engine):
        """시장 상황 업데이트 예외"""
        engine.portfolio_manager.get_market_season = AsyncMock(side_effect=Exception("Test error"))

        await engine._update_market_condition()

        # 예외 발생해도 에러 없이 처리됨
        # last_market_check는 업데이트되지 않음

    @pytest.mark.asyncio
    async def test_execute_scheduled_tasks(self, engine):
        """스케줄된 작업 실행"""
        # 과거 시간으로 next_run 설정
        task = RebalanceTask(
            account_id=AccountID("test_acc"),
            schedule_type=RebalanceScheduleType.WEEKLY,
            cron_expression="0 9 * * 1",
            next_run=datetime.now() - timedelta(minutes=5),
            enabled=True
        )
        engine.rebalance_tasks[AccountID("test_acc")] = task

        engine.portfolio_manager.rebalance_account = AsyncMock(return_value={
            'action': 'completed'
        })

        await engine._execute_scheduled_tasks(datetime.now())

        # 태스크가 실행됨
        engine.portfolio_manager.rebalance_account.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_scheduled_tasks_disabled(self, engine):
        """비활성화된 작업은 실행 안됨"""
        task = RebalanceTask(
            account_id=AccountID("test_acc"),
            schedule_type=RebalanceScheduleType.WEEKLY,
            next_run=datetime.now() - timedelta(minutes=5),
            enabled=False  # 비활성화
        )
        engine.rebalance_tasks[AccountID("test_acc")] = task

        await engine._execute_scheduled_tasks(datetime.now())

        engine.portfolio_manager.rebalance_account.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_trigger_conditions_deviation(self, engine):
        """편차 트리거 조건 확인"""
        account_id = AccountID("test_acc")

        task = RebalanceTask(
            account_id=account_id,
            schedule_type=RebalanceScheduleType.DEVIATION_TRIGGER,
            deviation_threshold=0.05,
            enabled=True
        )
        engine.rebalance_tasks[account_id] = task

        # 편차 트리거 반환 True
        mock_manager = AsyncMock()
        mock_manager.calculate_target_weights = AsyncMock(return_value={})
        mock_manager.needs_rebalancing = AsyncMock(return_value=True)
        engine.portfolio_manager.account_managers = {account_id: mock_manager}

        engine.portfolio_manager.rebalance_account = AsyncMock(return_value={'action': 'completed'})

        await engine._check_trigger_conditions()

        engine.portfolio_manager.rebalance_account.assert_called()

    @pytest.mark.asyncio
    async def test_check_trigger_conditions_market(self, engine):
        """시장 트리거 조건 확인"""
        account_id = AccountID("test_acc")

        engine.current_market_season = MarketSeason.RISK_ON

        task = RebalanceTask(
            account_id=account_id,
            schedule_type=RebalanceScheduleType.MARKET_TRIGGER,
            market_condition=MarketSeason.RISK_ON,  # 현재 시장 상황과 일치
            enabled=True
        )
        engine.rebalance_tasks[account_id] = task

        engine.portfolio_manager.rebalance_account = AsyncMock(return_value={'action': 'completed'})

        await engine._check_trigger_conditions()

        engine.portfolio_manager.rebalance_account.assert_called()

    @pytest.mark.asyncio
    async def test_trigger_manual_rebalance_exception(self, engine):
        """수동 리밸런싱 예외 처리"""
        engine.portfolio_manager.rebalance_account = AsyncMock(side_effect=Exception("Test error"))

        result = await engine.trigger_manual_rebalance(AccountID("test_acc"))

        assert 'error' in result
        assert 'Test error' in result['error']

    @pytest.mark.asyncio
    async def test_add_account_schedule_exception(self, engine):
        """스케줄 추가 예외 처리"""
        # 잘못된 파라미터로 예외 유발 - None 타입에 대해 에러
        with patch.object(engine, '_calculate_next_run', side_effect=Exception("Test error")):
            result = await engine.add_account_schedule(
                account_id=AccountID("test_acc"),
                schedule_type=RebalanceScheduleType.WEEKLY,
                cron_expression="0 9 * * 1"
            )

            assert result == False

    @pytest.mark.asyncio
    async def test_enable_account_schedule_nonexistent(self, engine):
        """존재하지 않는 스케줄 활성화"""
        result = await engine.enable_account_schedule(AccountID("nonexistent"), True)

        assert result == False

    @pytest.mark.asyncio
    async def test_start(self, engine):
        """서비스 시작"""
        with patch.object(engine, 'initialize', new_callable=AsyncMock) as mock_init:
            await engine.start()

            mock_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop(self, engine):
        """서비스 중지"""
        with patch.object(engine, 'shutdown', new_callable=AsyncMock) as mock_shutdown:
            await engine.stop()

            mock_shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_default_schedules(self, engine):
        """기본 스케줄 로드"""
        engine.account_manager.get_all_accounts = AsyncMock(return_value=[
            {'account_id': AccountID('acc1'), 'auto_rebalance': True},
            {'account_id': AccountID('acc2'), 'auto_rebalance': False}
        ])

        await engine._load_default_schedules()

        assert len(engine.rebalance_tasks) == 2
        assert AccountID('acc1') in engine.rebalance_tasks
        assert engine.rebalance_tasks[AccountID('acc1')].enabled == True
        assert engine.rebalance_tasks[AccountID('acc2')].enabled == False

    @pytest.mark.asyncio
    async def test_initialize_success(self, engine):
        """초기화 성공"""
        engine.portfolio_manager.initialize = AsyncMock()
        engine.account_manager.get_all_accounts = AsyncMock(return_value=[])

        # _scheduler_loop를 즉시 취소하도록 mock
        async def mock_scheduler():
            pass

        with patch.object(engine, '_scheduler_loop', new=mock_scheduler):
            await engine.initialize()

            engine.portfolio_manager.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_failure(self, engine):
        """초기화 실패"""
        engine.portfolio_manager.initialize = AsyncMock(side_effect=Exception("Init failed"))

        with pytest.raises(Exception, match="Init failed"):
            await engine.initialize()

    @pytest.mark.asyncio
    async def test_shutdown_without_scheduler_task(self, engine):
        """스케줄러 태스크 없이 종료"""
        # _scheduler_task 속성 없이 종료
        await engine.shutdown()

        # 에러 없이 종료

    @pytest.mark.asyncio
    async def test_get_schedule_status_with_times(self, engine):
        """시간 정보 포함 상태 조회"""
        now = datetime.now()
        task = RebalanceTask(
            account_id=AccountID("test_acc"),
            schedule_type=RebalanceScheduleType.WEEKLY,
            next_run=now + timedelta(days=1),
            last_run=now - timedelta(days=1),
            enabled=True
        )
        engine.rebalance_tasks[AccountID("test_acc")] = task
        engine.last_market_check = now

        status = await engine.get_schedule_status()

        assert status['last_market_check'] is not None
        assert len(status['schedules']) == 1
        assert status['schedules'][0]['next_run'] is not None
        assert status['schedules'][0]['last_run'] is not None


# ============================================================================
# Exception Handling Tests (Lines 174, 191, 206-207, 299-301, 312-314)
# ============================================================================

class TestExceptionHandling:
    """예외 처리 테스트"""

    @pytest.fixture
    def engine(self):
        """MultiRebalancingEngine 인스턴스"""
        with patch('src.core.multi_rebalancing_engine.get_multi_portfolio_manager') as mock_pm, \
             patch('src.core.multi_rebalancing_engine.get_multi_account_manager') as mock_am:
            mock_pm.return_value = AsyncMock()
            mock_am.return_value = AsyncMock()
            return MultiRebalancingEngine()

    @pytest.mark.asyncio
    async def test_execute_scheduled_tasks_running_task_skipped(self, engine):
        """이미 실행 중인 태스크는 스킵 (line 174)"""
        account_id = AccountID("test_acc")

        task = RebalanceTask(
            account_id=account_id,
            schedule_type=RebalanceScheduleType.WEEKLY,
            next_run=datetime.now() - timedelta(minutes=5),
            enabled=True
        )
        engine.rebalance_tasks[account_id] = task
        engine.running_tasks.add(account_id)  # 이미 실행 중

        engine.portfolio_manager.rebalance_account = AsyncMock()

        await engine._execute_scheduled_tasks(datetime.now())

        # 이미 실행 중인 태스크는 실행되지 않음
        engine.portfolio_manager.rebalance_account.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_trigger_conditions_running_task_skipped(self, engine):
        """이미 실행 중인 태스크는 트리거 확인 스킵 (line 191)"""
        account_id = AccountID("test_acc")

        task = RebalanceTask(
            account_id=account_id,
            schedule_type=RebalanceScheduleType.DEVIATION_TRIGGER,
            deviation_threshold=0.05,
            enabled=True
        )
        engine.rebalance_tasks[account_id] = task
        engine.running_tasks.add(account_id)  # 이미 실행 중

        engine.portfolio_manager.rebalance_account = AsyncMock()

        await engine._check_trigger_conditions()

        # 이미 실행 중인 태스크는 확인되지 않음
        engine.portfolio_manager.rebalance_account.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_trigger_conditions_exception(self, engine):
        """트리거 조건 확인 중 예외 (lines 206-207)"""
        account_id = AccountID("test_acc")

        task = RebalanceTask(
            account_id=account_id,
            schedule_type=RebalanceScheduleType.DEVIATION_TRIGGER,
            deviation_threshold=0.05,
            enabled=True
        )
        engine.rebalance_tasks[account_id] = task

        # _check_deviation_trigger에서 예외 발생
        with patch.object(engine, '_check_deviation_trigger', new_callable=AsyncMock) as mock_check:
            mock_check.side_effect = Exception("트리거 확인 오류")

            # 예외가 발생해도 에러 없이 처리됨
            await engine._check_trigger_conditions()

    @pytest.mark.asyncio
    async def test_remove_account_schedule_exception(self, engine):
        """스케줄 제거 중 예외 (lines 299-301)"""
        # rebalance_tasks를 None으로 설정하여 예외 유발
        engine.rebalance_tasks = None

        result = await engine.remove_account_schedule(AccountID("test_acc"))

        assert result == False

    @pytest.mark.asyncio
    async def test_enable_account_schedule_exception(self, engine):
        """스케줄 활성화 중 예외 (lines 312-314)"""
        # rebalance_tasks를 None으로 설정하여 예외 유발
        engine.rebalance_tasks = None

        result = await engine.enable_account_schedule(AccountID("test_acc"), True)

        assert result == False

    @pytest.mark.asyncio
    async def test_remove_account_schedule_success(self, engine):
        """스케줄 제거 성공"""
        account_id = AccountID("test_acc")
        task = RebalanceTask(
            account_id=account_id,
            schedule_type=RebalanceScheduleType.WEEKLY
        )
        engine.rebalance_tasks[account_id] = task

        result = await engine.remove_account_schedule(account_id)

        assert result == True
        assert account_id not in engine.rebalance_tasks

    @pytest.mark.asyncio
    async def test_remove_account_schedule_not_found(self, engine):
        """존재하지 않는 스케줄 제거"""
        result = await engine.remove_account_schedule(AccountID("nonexistent"))

        assert result == False

    @pytest.mark.asyncio
    async def test_enable_account_schedule_success(self, engine):
        """스케줄 활성화 성공"""
        account_id = AccountID("test_acc")
        task = RebalanceTask(
            account_id=account_id,
            schedule_type=RebalanceScheduleType.WEEKLY,
            enabled=False
        )
        engine.rebalance_tasks[account_id] = task

        result = await engine.enable_account_schedule(account_id, True)

        assert result == True
        assert engine.rebalance_tasks[account_id].enabled == True
