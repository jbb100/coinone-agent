"""
System Integration Helper
기존 코드와 새로운 시스템 조정자를 통합하는 헬퍼 함수들을 제공합니다.
"""
import asyncio
from datetime import datetime
from typing import Dict, Any, List
from loguru import logger
from .system_coordinator import get_system_coordinator, OperationType
def with_asset_protection(assets: List[str], account_id: str = "main"):
    """
    자산 보호 데코레이터
    사용법:
    @with_asset_protection(["BTC", "KRW"])
    def some_trading_function():
        pass
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            operation_id = f"{func.__name__}_{datetime.now().timestamp()}"
            coordinator = get_system_coordinator()
            try:
                # 충돌 체크
                conflicting_ops = []
                for op_id, op in coordinator.active_operations.items():
                    if op.account_id == account_id and op.assets.intersection(set(assets)):
                        conflicting_ops.append(op_id)
                if conflicting_ops:
                    logger.warning(f"자산 충돌 감지: {func.__name__} - {assets} (충돌: {conflicting_ops})")
                    return {
                        "success": False,
                        "error": "resource_conflict",
                        "message": f"자산 {assets} 사용 중 - 나중에 다시 시도",
                        "conflicting_operations": conflicting_ops
                    }
                # 작업 등록
                try:
                    asyncio.run(coordinator.register_operation(
                        operation_id=operation_id,
                        operation_type=OperationType.ORDER_MANAGEMENT,
                        account_id=account_id,
                        assets=assets,
                        priority=2
                    ))
                except Exception as e:
                    logger.warning(f"작업 등록 실패, 계속 진행: {e}")
                # 실제 함수 실행
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                logger.error(f"자산 보호 래퍼 오류: {e}")
                return func(*args, **kwargs)  # 실패 시 원본 함수 실행
            finally:
                # 작업 완료 처리
                try:
                    asyncio.run(coordinator.complete_operation(operation_id))
                except Exception as e:
                    logger.debug(f"작업 완료 처리 실패 (무시): {e}")
        return wrapper
    return decorator
def check_api_rate_limit():
    """
    API 속도 제한 체크 (동기 함수용)
    """
    coordinator = get_system_coordinator()
    try:
        # 현재 API 호출 빈도 체크
        recent_calls = len(coordinator.api_rate_limiter.call_history)
        max_calls = coordinator.api_rate_limiter.max_calls_per_second
        if recent_calls >= max_calls * 0.8:  # 80% 임계값
            logger.warning(f"API 호출 빈도 높음: {recent_calls}/{max_calls}")
            return False
        return True
    except Exception as e:
        logger.debug(f"API 속도 제한 체크 실패: {e}")
        return True  # 실패 시 계속 진행
def should_send_alert(alert_type: str, title: str, content: str) -> bool:
    """
    중복 알림 체크 (동기 함수용)
    """
    coordinator = get_system_coordinator()
    alert_key = f"{alert_type}:{title}"
    return coordinator.should_send_alert(alert_key, content)
def get_system_status() -> Dict[str, Any]:
    """
    시스템 상태 조회
    """
    coordinator = get_system_coordinator()
    return coordinator.get_system_status()
