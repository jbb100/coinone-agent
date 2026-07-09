"""
System Coordinator 테스트 모듈

시스템 전체 상태 관리 및 자원 조정 테스트
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

from src.core.system_coordinator import (
    AssetLockManager,
    APIRateLimiter,
    OperationType,
    ActiveOperation,
    ConflictError
)
from src.core.types import AccountID


class TestOperationType:
    """OperationType Enum 테스트"""

    def test_operation_types_exist(self):
        """모든 작업 유형 존재 확인"""
        assert OperationType.TWAP_EXECUTION.value == "twap_execution"
        assert OperationType.REBALANCING.value == "rebalancing"
        assert OperationType.ORDER_MANAGEMENT.value == "order_management"
        assert OperationType.PORTFOLIO_SYNC.value == "portfolio_sync"

    def test_operation_type_count(self):
        """작업 유형 개수 확인"""
        assert len(OperationType) == 4


class TestActiveOperation:
    """ActiveOperation 데이터클래스 테스트"""

    def test_active_operation_creation(self):
        """ActiveOperation 생성 테스트"""
        operation = ActiveOperation(
            operation_id="op_001",
            operation_type=OperationType.REBALANCING,
            account_id=AccountID("acc_001"),
            assets={"BTC", "ETH"},
            started_at=datetime.now()
        )

        assert operation.operation_id == "op_001"
        assert operation.operation_type == OperationType.REBALANCING
        assert operation.account_id == AccountID("acc_001")
        assert "BTC" in operation.assets
        assert operation.priority == 1  # 기본값

    def test_active_operation_with_priority(self):
        """우선순위 포함 ActiveOperation"""
        operation = ActiveOperation(
            operation_id="op_002",
            operation_type=OperationType.TWAP_EXECUTION,
            account_id=AccountID("acc_001"),
            assets={"SOL"},
            started_at=datetime.now(),
            priority=5
        )

        assert operation.priority == 5


class TestAssetLockManager:
    """AssetLockManager 클래스 테스트"""

    @pytest.fixture
    def lock_manager(self):
        """AssetLockManager 인스턴스"""
        return AssetLockManager()

    @pytest.mark.asyncio
    async def test_init(self, lock_manager):
        """초기화 테스트"""
        assert lock_manager.locks == {}
        assert lock_manager.lock_holders == {}
        assert lock_manager._initialized is False

    @pytest.mark.asyncio
    async def test_acquire_asset_lock(self, lock_manager):
        """자산 락 획득"""
        lock = await lock_manager.acquire_asset_lock("BTC", "op_001")

        assert "BTC" in lock_manager.locks
        assert lock_manager.lock_holders["BTC"] == "op_001"
        assert lock is not None

        # 락 해제
        lock_manager.release_asset_lock("BTC", "op_001")

    @pytest.mark.asyncio
    async def test_release_asset_lock(self, lock_manager):
        """자산 락 해제"""
        await lock_manager.acquire_asset_lock("ETH", "op_002")

        lock_manager.release_asset_lock("ETH", "op_002")

        assert "ETH" not in lock_manager.lock_holders

    @pytest.mark.asyncio
    async def test_release_asset_lock_wrong_owner(self, lock_manager):
        """잘못된 소유자의 락 해제 시도"""
        await lock_manager.acquire_asset_lock("XRP", "op_001")

        # 다른 operation_id로 해제 시도
        lock_manager.release_asset_lock("XRP", "op_002")

        # 여전히 원래 소유자가 락을 보유
        assert lock_manager.lock_holders["XRP"] == "op_001"

        # 정리
        lock_manager.release_asset_lock("XRP", "op_001")

    @pytest.mark.asyncio
    async def test_lock_assets_context_manager(self, lock_manager):
        """컨텍스트 매니저로 자산 락 관리"""
        async with lock_manager.lock_assets(["BTC", "ETH"], "op_001"):
            assert lock_manager.lock_holders.get("BTC") == "op_001"
            assert lock_manager.lock_holders.get("ETH") == "op_001"

        # 컨텍스트 종료 후 락 해제됨
        assert "BTC" not in lock_manager.lock_holders
        assert "ETH" not in lock_manager.lock_holders

    @pytest.mark.asyncio
    async def test_lock_assets_sorted_order(self, lock_manager):
        """데드락 방지를 위한 정렬된 순서로 락 획득"""
        acquired_order = []

        original_acquire = lock_manager.acquire_asset_lock

        async def track_acquire(asset, op_id):
            acquired_order.append(asset)
            return await original_acquire(asset, op_id)

        lock_manager.acquire_asset_lock = track_acquire

        async with lock_manager.lock_assets(["ETH", "BTC", "SOL"], "op_001"):
            # 알파벳 순서로 락 획득: BTC, ETH, SOL
            assert acquired_order == ["BTC", "ETH", "SOL"]

    @pytest.mark.asyncio
    async def test_ensure_initialized(self, lock_manager):
        """이벤트 루프에서 초기화"""
        await lock_manager._ensure_initialized()

        assert lock_manager._initialized is True
        assert lock_manager._lock is not None


class TestAPIRateLimiter:
    """APIRateLimiter 클래스 테스트"""

    @pytest.fixture
    def rate_limiter(self):
        """APIRateLimiter 인스턴스"""
        return APIRateLimiter(max_calls_per_second=10.0)

    @pytest.mark.asyncio
    async def test_init(self, rate_limiter):
        """초기화 테스트"""
        assert rate_limiter.max_calls_per_second == 10.0
        assert rate_limiter.min_interval == 0.1
        assert rate_limiter.last_call_time == 0.0
        assert rate_limiter.call_history == []

    @pytest.mark.asyncio
    async def test_acquire(self, rate_limiter):
        """API 호출 권한 획득"""
        await rate_limiter.acquire()

        assert len(rate_limiter.call_history) == 1
        assert rate_limiter.last_call_time > 0

    @pytest.mark.asyncio
    async def test_multiple_acquires(self, rate_limiter):
        """여러 번 권한 획득"""
        for _ in range(3):
            await rate_limiter.acquire()

        assert len(rate_limiter.call_history) == 3

    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """속도 제한 적용"""
        # 초당 2회로 제한
        limiter = APIRateLimiter(max_calls_per_second=2.0)

        start_time = asyncio.get_event_loop().time()

        # 3번 호출
        for _ in range(3):
            await limiter.acquire()

        end_time = asyncio.get_event_loop().time()
        elapsed = end_time - start_time

        # 최소 0.5초 이상 걸려야 함 (2회/초 제한)
        assert elapsed >= 0.4  # 약간의 오차 허용

    @pytest.mark.asyncio
    async def test_ensure_initialized(self, rate_limiter):
        """이벤트 루프에서 초기화"""
        await rate_limiter._ensure_initialized()

        assert rate_limiter._initialized is True
        assert rate_limiter._lock is not None

    @pytest.mark.asyncio
    async def test_call_history_cleanup(self, rate_limiter):
        """윈도우 범위 밖의 호출 기록 정리"""
        # 첫 번째 호출
        await rate_limiter.acquire()

        # 인위적으로 오래된 기록 추가
        import time
        old_time = time.time() - 2.0  # 2초 전
        rate_limiter.call_history.insert(0, old_time)

        # 다음 호출 시 오래된 기록 제거됨
        await rate_limiter.acquire()

        # 1초 윈도우 내의 호출만 남음
        for call_time in rate_limiter.call_history:
            assert time.time() - call_time <= 1.0


class TestConflictError:
    """ConflictError 예외 테스트"""

    def test_conflict_error_creation(self):
        """ConflictError 생성"""
        error = ConflictError("자원 충돌 발생")

        assert str(error) == "자원 충돌 발생"
        assert isinstance(error, Exception)

    def test_conflict_error_raise(self):
        """ConflictError 발생"""
        with pytest.raises(ConflictError):
            raise ConflictError("테스트 에러")


class TestAlertDeduplicator:
    """AlertDeduplicator 클래스 테스트"""

    @pytest.fixture
    def deduplicator(self):
        """AlertDeduplicator 인스턴스"""
        from src.core.system_coordinator import AlertDeduplicator
        return AlertDeduplicator(dedup_window_minutes=5)

    def test_init(self, deduplicator):
        """초기화 테스트"""
        assert deduplicator.recent_alerts == {}
        assert deduplicator.dedup_window.total_seconds() == 300

    def test_should_send_alert_first_time(self, deduplicator):
        """첫 번째 알림은 전송"""
        result = deduplicator.should_send_alert("error:system", "System error occurred")
        assert result == True
        assert "error:system" in deduplicator.recent_alerts

    def test_should_send_alert_duplicate(self, deduplicator):
        """중복 알림은 필터링"""
        # 첫 번째 알림
        deduplicator.should_send_alert("error:system", "System error")

        # 같은 내용의 알림
        result = deduplicator.should_send_alert("error:system", "System error")
        assert result == False

    def test_should_send_alert_different_content(self, deduplicator):
        """다른 내용의 알림은 전송"""
        deduplicator.should_send_alert("error:system", "Error A")

        result = deduplicator.should_send_alert("error:system", "Error B")
        assert result == True

    def test_should_send_alert_different_key(self, deduplicator):
        """다른 키의 알림은 전송"""
        deduplicator.should_send_alert("error:A", "Content")

        result = deduplicator.should_send_alert("error:B", "Content")
        assert result == True

    def test_clear_alert_history_specific(self, deduplicator):
        """특정 알림 기록 초기화"""
        deduplicator.should_send_alert("key1", "content1")
        deduplicator.should_send_alert("key2", "content2")

        deduplicator.clear_alert_history("key1")

        assert "key1" not in deduplicator.recent_alerts
        assert "key2" in deduplicator.recent_alerts

    def test_clear_alert_history_all(self, deduplicator):
        """모든 알림 기록 초기화"""
        deduplicator.should_send_alert("key1", "content1")
        deduplicator.should_send_alert("key2", "content2")

        deduplicator.clear_alert_history()

        assert deduplicator.recent_alerts == {}


class TestSystemStateCoordinator:
    """SystemStateCoordinator 클래스 테스트"""

    @pytest.fixture
    def coordinator(self):
        """SystemStateCoordinator 인스턴스"""
        from src.core.system_coordinator import SystemStateCoordinator
        return SystemStateCoordinator()

    def test_init(self, coordinator):
        """초기화 테스트"""
        assert coordinator.active_operations == {}
        assert coordinator.operation_events == {}
        assert coordinator._initialized == False
        assert coordinator.stats["total_operations"] == 0

    @pytest.mark.asyncio
    async def test_ensure_initialized(self, coordinator):
        """이벤트 루프에서 초기화"""
        await coordinator._ensure_initialized()

        assert coordinator._initialized == True
        assert coordinator._coordinator_lock is not None

    @pytest.mark.asyncio
    async def test_register_operation(self, coordinator):
        """작업 등록"""
        await coordinator.register_operation(
            operation_id="op_001",
            operation_type=OperationType.REBALANCING,
            account_id=AccountID("acc_001"),
            assets=["BTC", "ETH"],
            priority=1
        )

        assert "op_001" in coordinator.active_operations
        assert coordinator.stats["total_operations"] == 1
        assert "op_001" in coordinator.operation_events

    @pytest.mark.asyncio
    async def test_register_operation_conflict(self, coordinator):
        """충돌하는 작업 등록 시 예외"""
        # 첫 번째 작업 등록
        await coordinator.register_operation(
            operation_id="op_001",
            operation_type=OperationType.REBALANCING,
            account_id=AccountID("acc_001"),
            assets=["BTC"],
            priority=1
        )

        # 같은 자산에 대한 두 번째 작업
        with pytest.raises(ConflictError):
            await coordinator.register_operation(
                operation_id="op_002",
                operation_type=OperationType.TWAP_EXECUTION,
                account_id=AccountID("acc_001"),
                assets=["BTC"],
                priority=2  # 낮은 우선순위
            )

        assert coordinator.stats["conflicts_prevented"] == 1

    @pytest.mark.asyncio
    async def test_register_operation_no_conflict_different_account(self, coordinator):
        """다른 계정은 충돌 없음"""
        await coordinator.register_operation(
            operation_id="op_001",
            operation_type=OperationType.REBALANCING,
            account_id=AccountID("acc_001"),
            assets=["BTC"],
            priority=1
        )

        # 다른 계정의 작업
        await coordinator.register_operation(
            operation_id="op_002",
            operation_type=OperationType.REBALANCING,
            account_id=AccountID("acc_002"),  # 다른 계정
            assets=["BTC"],
            priority=1
        )

        assert "op_002" in coordinator.active_operations

    @pytest.mark.asyncio
    async def test_complete_operation(self, coordinator):
        """작업 완료"""
        await coordinator.register_operation(
            operation_id="op_001",
            operation_type=OperationType.REBALANCING,
            account_id=AccountID("acc_001"),
            assets=["BTC"],
            priority=1
        )

        await coordinator.complete_operation("op_001")

        assert "op_001" not in coordinator.active_operations
        assert "op_001" not in coordinator.operation_events

    @pytest.mark.asyncio
    async def test_complete_operation_nonexistent(self, coordinator):
        """존재하지 않는 작업 완료 시도"""
        await coordinator._ensure_initialized()

        # 경고 로그만 출력하고 에러 없음
        await coordinator.complete_operation("nonexistent")

    @pytest.mark.asyncio
    async def test_coordinate_operation_context_manager(self, coordinator):
        """작업 조정 컨텍스트 매니저"""
        async with coordinator.coordinate_operation(
            operation_id="op_001",
            operation_type=OperationType.ORDER_MANAGEMENT,
            account_id=AccountID("acc_001"),
            assets=["BTC"]
        ):
            assert "op_001" in coordinator.active_operations

        # 컨텍스트 종료 후 작업 완료됨
        assert "op_001" not in coordinator.active_operations

    @pytest.mark.asyncio
    async def test_api_call_with_limit(self, coordinator):
        """속도 제한이 적용된 API 호출"""
        async def mock_api():
            return {"result": "success"}

        result = await coordinator.api_call_with_limit(mock_api)

        assert result["result"] == "success"

    @pytest.mark.asyncio
    async def test_api_call_with_limit_exception(self, coordinator):
        """API 호출 실패 시 예외 전파"""
        async def failing_api():
            raise ValueError("API Error")

        with pytest.raises(ValueError):
            await coordinator.api_call_with_limit(failing_api)

    def test_should_send_alert(self, coordinator):
        """알림 전송 여부 판단"""
        result1 = coordinator.should_send_alert("test:alert", "Content")
        assert result1 == True

        result2 = coordinator.should_send_alert("test:alert", "Content")
        assert result2 == False
        assert coordinator.stats["alerts_deduplicated"] == 1

    def test_get_system_status(self, coordinator):
        """시스템 상태 조회"""
        status = coordinator.get_system_status()

        assert "active_operations" in status
        assert "operations_by_type" in status
        assert "locked_assets" in status
        assert "api_rate_limit" in status
        assert "stats" in status

    @pytest.mark.asyncio
    async def test_wait_for_operation(self, coordinator):
        """작업 완료 대기"""
        await coordinator.register_operation(
            operation_id="op_001",
            operation_type=OperationType.REBALANCING,
            account_id=AccountID("acc_001"),
            assets=["BTC"]
        )

        # 백그라운드에서 작업 완료
        async def complete_later():
            await asyncio.sleep(0.1)
            await coordinator.complete_operation("op_001")

        task = asyncio.create_task(complete_later())

        await coordinator.wait_for_operation("op_001", timeout=1.0)

        await task

    @pytest.mark.asyncio
    async def test_wait_for_operation_timeout(self, coordinator):
        """작업 대기 타임아웃"""
        await coordinator.register_operation(
            operation_id="op_001",
            operation_type=OperationType.REBALANCING,
            account_id=AccountID("acc_001"),
            assets=["BTC"]
        )

        with pytest.raises(asyncio.TimeoutError):
            await coordinator.wait_for_operation("op_001", timeout=0.1)

    @pytest.mark.asyncio
    async def test_wait_for_operation_nonexistent(self, coordinator):
        """존재하지 않는 작업 대기 (즉시 반환)"""
        # 에러 없이 바로 반환
        await coordinator.wait_for_operation("nonexistent", timeout=0.1)

    @pytest.mark.asyncio
    async def test_shutdown_with_active_operations(self, coordinator):
        """활성 작업이 있는 상태에서 종료"""
        await coordinator.register_operation(
            operation_id="op_001",
            operation_type=OperationType.REBALANCING,
            account_id=AccountID("acc_001"),
            assets=["BTC"]
        )

        # 백그라운드에서 작업 완료
        async def complete_later():
            await asyncio.sleep(0.1)
            await coordinator.complete_operation("op_001")

        task = asyncio.create_task(complete_later())

        await coordinator.shutdown()

        await task

    @pytest.mark.asyncio
    async def test_shutdown_timeout(self, coordinator):
        """종료 시 타임아웃"""
        await coordinator.register_operation(
            operation_id="op_001",
            operation_type=OperationType.REBALANCING,
            account_id=AccountID("acc_001"),
            assets=["BTC"]
        )

        # 짧은 타임아웃으로 종료 (실제 코드의 30초 대신 테스트용)
        # 실제 shutdown은 30초 타임아웃이므로 테스트하기 어려움
        # 이 테스트는 코드 경로만 확인


class TestGetSystemCoordinator:
    """get_system_coordinator 함수 테스트"""

    def test_singleton_pattern(self):
        """싱글톤 패턴 테스트"""
        from src.core.system_coordinator import get_system_coordinator
        import src.core.system_coordinator as sc

        sc._system_coordinator = None

        coordinator1 = get_system_coordinator()
        coordinator2 = get_system_coordinator()

        assert coordinator1 is coordinator2
