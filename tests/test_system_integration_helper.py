"""
System Integration Helper Tests
system_integration_helper.py 모듈의 테스트
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime


class TestWithAssetProtection:
    """with_asset_protection 데코레이터 테스트"""

    def test_decorator_without_conflict(self):
        """충돌 없이 정상 실행"""
        from src.core.system_integration_helper import with_asset_protection

        mock_coordinator = Mock()
        mock_coordinator.active_operations = {}

        with patch('src.core.system_integration_helper.get_system_coordinator', return_value=mock_coordinator):
            @with_asset_protection(["BTC", "KRW"])
            def test_func():
                return {"success": True, "result": "test"}

            result = test_func()
            assert result.get("success") == True
            assert result.get("result") == "test"

    def test_decorator_with_conflict(self):
        """자산 충돌 감지"""
        from src.core.system_integration_helper import with_asset_protection
        from src.core.system_coordinator import ActiveOperation, OperationType

        # 충돌하는 작업 생성
        conflicting_op = ActiveOperation(
            operation_id="existing_op",
            operation_type=OperationType.TWAP_EXECUTION,
            account_id="main",
            assets={"BTC", "ETH"},
            started_at=datetime.now(),
            priority=1
        )

        mock_coordinator = Mock()
        mock_coordinator.active_operations = {"existing_op": conflicting_op}

        with patch('src.core.system_integration_helper.get_system_coordinator', return_value=mock_coordinator):
            @with_asset_protection(["BTC", "KRW"], account_id="main")
            def test_func():
                return {"success": True}

            result = test_func()
            # 충돌 시 실패 반환
            assert result.get("success") == False
            assert result.get("error") == "resource_conflict"
            assert "existing_op" in result.get("conflicting_operations", [])

    def test_decorator_with_different_account(self):
        """다른 계정의 자산은 충돌하지 않음"""
        from src.core.system_integration_helper import with_asset_protection
        from src.core.system_coordinator import ActiveOperation, OperationType

        # 다른 계정의 작업
        other_account_op = ActiveOperation(
            operation_id="other_op",
            operation_type=OperationType.TWAP_EXECUTION,
            account_id="sub_account",  # 다른 계정
            assets={"BTC", "ETH"},
            started_at=datetime.now(),
            priority=1
        )

        mock_coordinator = Mock()
        mock_coordinator.active_operations = {"other_op": other_account_op}

        with patch('src.core.system_integration_helper.get_system_coordinator', return_value=mock_coordinator):
            @with_asset_protection(["BTC", "KRW"], account_id="main")  # 메인 계정
            def test_func():
                return {"success": True}

            result = test_func()
            assert result.get("success") == True

    def test_decorator_exception_in_function(self):
        """래핑된 함수에서 예외 발생 시 처리"""
        from src.core.system_integration_helper import with_asset_protection

        mock_coordinator = Mock()
        mock_coordinator.active_operations = {}

        with patch('src.core.system_integration_helper.get_system_coordinator', return_value=mock_coordinator):
            @with_asset_protection(["BTC"])
            def test_func():
                raise ValueError("Test error")

            # 예외가 전파되어야 함
            with pytest.raises(ValueError):
                test_func()

    def test_decorator_registration_failure(self):
        """작업 등록 실패 시 계속 진행"""
        from src.core.system_integration_helper import with_asset_protection

        mock_coordinator = Mock()
        mock_coordinator.active_operations = {}

        # asyncio.run이 예외를 발생시키도록 설정
        with patch('src.core.system_integration_helper.get_system_coordinator', return_value=mock_coordinator):
            with patch('src.core.system_integration_helper.asyncio.run', side_effect=RuntimeError("Event loop error")):
                @with_asset_protection(["BTC"])
                def test_func():
                    return {"success": True, "data": "test"}

                # 등록 실패해도 함수는 실행됨
                result = test_func()
                assert result.get("success") == True

    def test_decorator_with_args_and_kwargs(self):
        """인자가 있는 함수에 적용"""
        from src.core.system_integration_helper import with_asset_protection

        mock_coordinator = Mock()
        mock_coordinator.active_operations = {}

        with patch('src.core.system_integration_helper.get_system_coordinator', return_value=mock_coordinator):
            @with_asset_protection(["BTC"])
            def test_func(a, b, c=None):
                return {"a": a, "b": b, "c": c}

            result = test_func(1, 2, c=3)
            assert result == {"a": 1, "b": 2, "c": 3}


class TestCheckApiRateLimit:
    """check_api_rate_limit 함수 테스트"""

    def test_below_threshold(self):
        """임계값 이하면 True 반환"""
        from src.core.system_integration_helper import check_api_rate_limit

        mock_rate_limiter = Mock()
        mock_rate_limiter.call_history = [1.0, 2.0, 3.0]  # 3개 호출
        mock_rate_limiter.max_calls_per_second = 10.0  # 최대 10개

        mock_coordinator = Mock()
        mock_coordinator.api_rate_limiter = mock_rate_limiter

        with patch('src.core.system_integration_helper.get_system_coordinator', return_value=mock_coordinator):
            result = check_api_rate_limit()
            assert result == True

    def test_above_threshold(self):
        """80% 이상이면 False 반환"""
        from src.core.system_integration_helper import check_api_rate_limit

        mock_rate_limiter = Mock()
        mock_rate_limiter.call_history = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]  # 9개 호출
        mock_rate_limiter.max_calls_per_second = 10.0  # 최대 10개, 80% = 8개

        mock_coordinator = Mock()
        mock_coordinator.api_rate_limiter = mock_rate_limiter

        with patch('src.core.system_integration_helper.get_system_coordinator', return_value=mock_coordinator):
            result = check_api_rate_limit()
            assert result == False

    def test_exactly_at_threshold(self):
        """정확히 80%이면 False 반환"""
        from src.core.system_integration_helper import check_api_rate_limit

        mock_rate_limiter = Mock()
        mock_rate_limiter.call_history = [1.0] * 8  # 8개 호출
        mock_rate_limiter.max_calls_per_second = 10.0  # 최대 10개

        mock_coordinator = Mock()
        mock_coordinator.api_rate_limiter = mock_rate_limiter

        with patch('src.core.system_integration_helper.get_system_coordinator', return_value=mock_coordinator):
            result = check_api_rate_limit()
            assert result == False

    def test_exception_returns_true(self):
        """예외 발생 시 True 반환 (계속 진행)"""
        from src.core.system_integration_helper import check_api_rate_limit

        mock_coordinator = Mock()
        mock_coordinator.api_rate_limiter = None  # AttributeError 유발

        with patch('src.core.system_integration_helper.get_system_coordinator', return_value=mock_coordinator):
            result = check_api_rate_limit()
            assert result == True


class TestShouldSendAlert:
    """should_send_alert 함수 테스트"""

    def test_should_send_alert_true(self):
        """알림을 보내야 하는 경우"""
        from src.core.system_integration_helper import should_send_alert

        mock_coordinator = Mock()
        mock_coordinator.should_send_alert.return_value = True

        with patch('src.core.system_integration_helper.get_system_coordinator', return_value=mock_coordinator):
            result = should_send_alert("error", "Test Alert", "Test content")
            assert result == True
            mock_coordinator.should_send_alert.assert_called_once_with(
                "error:Test Alert",
                "Test content"
            )

    def test_should_send_alert_false(self):
        """중복 알림으로 보내지 않아야 하는 경우"""
        from src.core.system_integration_helper import should_send_alert

        mock_coordinator = Mock()
        mock_coordinator.should_send_alert.return_value = False

        with patch('src.core.system_integration_helper.get_system_coordinator', return_value=mock_coordinator):
            result = should_send_alert("warning", "Duplicate", "Same content")
            assert result == False

    def test_alert_key_format(self):
        """알림 키 형식 확인"""
        from src.core.system_integration_helper import should_send_alert

        mock_coordinator = Mock()
        mock_coordinator.should_send_alert.return_value = True

        with patch('src.core.system_integration_helper.get_system_coordinator', return_value=mock_coordinator):
            should_send_alert("critical", "System Down", "System is not responding")

            # alert_key는 "type:title" 형식
            called_args = mock_coordinator.should_send_alert.call_args
            assert called_args[0][0] == "critical:System Down"


class TestGetSystemStatus:
    """get_system_status 함수 테스트"""

    def test_returns_status_dict(self):
        """시스템 상태 딕셔너리 반환"""
        from src.core.system_integration_helper import get_system_status

        expected_status = {
            "active_operations": 5,
            "api_calls_per_second": 3.5,
            "locked_assets": ["BTC", "ETH"],
            "system_health": "healthy"
        }

        mock_coordinator = Mock()
        mock_coordinator.get_system_status.return_value = expected_status

        with patch('src.core.system_integration_helper.get_system_coordinator', return_value=mock_coordinator):
            result = get_system_status()
            assert result == expected_status

    def test_empty_status(self):
        """빈 상태 반환"""
        from src.core.system_integration_helper import get_system_status

        mock_coordinator = Mock()
        mock_coordinator.get_system_status.return_value = {}

        with patch('src.core.system_integration_helper.get_system_coordinator', return_value=mock_coordinator):
            result = get_system_status()
            assert result == {}

    def test_status_with_detailed_info(self):
        """상세 정보가 포함된 상태"""
        from src.core.system_integration_helper import get_system_status

        detailed_status = {
            "active_operations": 2,
            "operations_detail": [
                {"id": "op1", "type": "TWAP_EXECUTION", "assets": ["BTC"]},
                {"id": "op2", "type": "REBALANCING", "assets": ["ETH", "XRP"]}
            ],
            "rate_limit_usage": 0.45,
            "last_api_call": "2025-01-15T10:30:00"
        }

        mock_coordinator = Mock()
        mock_coordinator.get_system_status.return_value = detailed_status

        with patch('src.core.system_integration_helper.get_system_coordinator', return_value=mock_coordinator):
            result = get_system_status()
            assert result["active_operations"] == 2
            assert len(result["operations_detail"]) == 2
            assert result["rate_limit_usage"] == 0.45


class TestIntegrationScenarios:
    """통합 시나리오 테스트"""

    def test_multiple_protected_functions(self):
        """여러 보호된 함수가 순차적으로 실행"""
        from src.core.system_integration_helper import with_asset_protection

        mock_coordinator = Mock()
        mock_coordinator.active_operations = {}

        with patch('src.core.system_integration_helper.get_system_coordinator', return_value=mock_coordinator):
            @with_asset_protection(["BTC"])
            def func1():
                return {"func": 1}

            @with_asset_protection(["ETH"])
            def func2():
                return {"func": 2}

            result1 = func1()
            result2 = func2()

            assert result1 == {"func": 1}
            assert result2 == {"func": 2}

    def test_rate_limit_before_operation(self):
        """작업 전 속도 제한 확인"""
        from src.core.system_integration_helper import check_api_rate_limit, with_asset_protection

        mock_rate_limiter = Mock()
        mock_rate_limiter.call_history = [1.0, 2.0]
        mock_rate_limiter.max_calls_per_second = 10.0

        mock_coordinator = Mock()
        mock_coordinator.api_rate_limiter = mock_rate_limiter
        mock_coordinator.active_operations = {}

        with patch('src.core.system_integration_helper.get_system_coordinator', return_value=mock_coordinator):
            # 먼저 속도 제한 확인
            can_proceed = check_api_rate_limit()
            assert can_proceed == True

            # 속도 제한 OK면 작업 수행
            @with_asset_protection(["BTC"])
            def trading_operation():
                return {"executed": True}

            result = trading_operation()
            assert result.get("executed") == True
