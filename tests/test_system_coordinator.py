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
