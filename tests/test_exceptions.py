"""
Exceptions 테스트 모듈

커스텀 예외 클래스 테스트
"""

import pytest
from datetime import datetime

from src.core.exceptions import (
    # Base
    KairosException,
    # Trading
    TradingException,
    InsufficientBalanceException,
    OrderExecutionException,
    MinimumOrderSizeException,
    PriceSlippageException,
    # API
    APIException,
    APIAuthenticationException,
    APIRateLimitException,
    APITimeoutException,
    APIResponseException,
    APIClientException,
    APIServerException,
    # Risk
    RiskException,
    RiskLimitExceededException,
    DrawdownExceededException,
    # Portfolio
    PortfolioException,
    AssetAllocationException,
    RebalancingException,
    # System
    SystemException,
    ConfigurationException,
    DatabaseException,
    # Data
    DataException,
    DataValidationException,
    DataIntegrityException
)


class TestKairosException:
    """KairosException 기본 클래스 테스트"""

    def test_basic_creation(self):
        """기본 예외 생성"""
        exc = KairosException("테스트 에러")

        assert exc.message == "테스트 에러"
        assert exc.error_code == "KairosException"
        assert exc.details == {}
        assert exc.recoverable is True
        assert isinstance(exc.timestamp, datetime)

    def test_with_all_parameters(self):
        """모든 파라미터 포함 예외 생성"""
        exc = KairosException(
            message="상세 에러",
            error_code="CUSTOM_ERROR",
            details={"key": "value"},
            recoverable=False
        )

        assert exc.message == "상세 에러"
        assert exc.error_code == "CUSTOM_ERROR"
        assert exc.details == {"key": "value"}
        assert exc.recoverable is False

    def test_to_dict(self):
        """to_dict 메서드 테스트"""
        exc = KairosException("테스트", error_code="TEST", details={"a": 1})

        result = exc.to_dict()

        assert result['error_code'] == "TEST"
        assert result['message'] == "테스트"
        assert result['details'] == {"a": 1}
        assert result['recoverable'] is True
        assert 'timestamp' in result

    def test_exception_inheritance(self):
        """예외 상속 테스트"""
        exc = KairosException("테스트")

        assert isinstance(exc, Exception)
        assert str(exc) == "테스트"


class TestTradingExceptions:
    """Trading 관련 예외 테스트"""

    def test_insufficient_balance(self):
        """잔고 부족 예외"""
        exc = InsufficientBalanceException(
            required=1.0,
            available=0.5,
            asset="BTC"
        )

        assert exc.error_code == "INSUFFICIENT_BALANCE"
        assert exc.details['asset'] == "BTC"
        assert exc.details['required'] == 1.0
        assert exc.details['available'] == 0.5
        assert exc.details['shortage'] == 0.5
        assert exc.recoverable is True
        assert isinstance(exc, TradingException)

    def test_order_execution(self):
        """주문 실행 실패 예외"""
        exc = OrderExecutionException(
            order_id="order_123",
            reason="서버 오류"
        )

        assert exc.error_code == "ORDER_EXECUTION_FAILED"
        assert exc.details['order_id'] == "order_123"
        assert exc.details['reason'] == "서버 오류"

    def test_order_execution_with_details(self):
        """추가 상세 정보 포함 주문 실패 예외"""
        exc = OrderExecutionException(
            order_id="order_456",
            reason="가격 변동",
            details={"price_change": 0.05}
        )

        assert exc.details['price_change'] == 0.05

    def test_minimum_order_size(self):
        """최소 주문 크기 미달 예외"""
        exc = MinimumOrderSizeException(
            amount=5000,
            minimum=10000,
            asset="KRW"
        )

        assert exc.error_code == "MINIMUM_ORDER_SIZE"
        assert exc.details['amount'] == 5000
        assert exc.details['minimum'] == 10000

    def test_price_slippage(self):
        """가격 슬리피지 초과 예외"""
        exc = PriceSlippageException(
            expected_price=50000000,
            actual_price=52500000,
            max_slippage=0.01
        )

        assert exc.error_code == "EXCESSIVE_SLIPPAGE"
        assert exc.details['expected_price'] == 50000000
        assert exc.details['actual_price'] == 52500000
        # 슬리피지: 5% = 0.05
        assert exc.details['slippage'] == pytest.approx(0.05, rel=0.01)


class TestAPIExceptions:
    """API 관련 예외 테스트"""

    def test_api_authentication(self):
        """API 인증 실패 예외"""
        exc = APIAuthenticationException(service="Coinone")

        assert exc.error_code == "API_AUTH_FAILED"
        assert exc.details['service'] == "Coinone"
        assert exc.recoverable is False  # 인증 실패는 복구 불가
        assert isinstance(exc, APIException)

    def test_api_authentication_with_details(self):
        """상세 정보 포함 인증 실패"""
        exc = APIAuthenticationException(
            service="Binance",
            details={"reason": "Invalid API key"}
        )

        assert exc.details['reason'] == "Invalid API key"

    def test_api_rate_limit(self):
        """API 요청 한도 초과 예외"""
        exc = APIRateLimitException(
            service="Coinone",
            retry_after=60
        )

        assert exc.error_code == "API_RATE_LIMIT"
        assert exc.details['service'] == "Coinone"
        assert exc.details['retry_after'] == 60
        assert exc.recoverable is True

    def test_api_timeout(self):
        """API 요청 시간 초과 예외"""
        exc = APITimeoutException(service="Coinone", timeout=30)

        assert exc.error_code == "API_TIMEOUT"
        assert exc.details['timeout'] == 30
        assert exc.recoverable is True

    def test_api_response_5xx(self):
        """API 5xx 응답 예외"""
        exc = APIResponseException(
            service="Coinone",
            status_code=503,
            response="Service Unavailable"
        )

        assert exc.error_code == "API_RESPONSE_ERROR"
        assert exc.details['status_code'] == 503
        assert exc.recoverable is True  # 5xx는 재시도 가능

    def test_api_response_4xx(self):
        """API 4xx 응답 예외"""
        exc = APIResponseException(
            service="Coinone",
            status_code=400,
            response="Bad Request"
        )

        assert exc.recoverable is False  # 4xx는 재시도 불가

    def test_api_client_exception(self):
        """API 클라이언트 오류"""
        exc = APIClientException(
            service="Coinone",
            status_code=404,
            response="Not Found"
        )

        assert exc.error_code == "API_CLIENT_ERROR"
        assert exc.recoverable is False

    def test_api_server_exception(self):
        """API 서버 오류"""
        exc = APIServerException(
            service="Coinone",
            status_code=500,
            response="Internal Server Error"
        )

        assert exc.error_code == "API_SERVER_ERROR"
        assert exc.recoverable is True


class TestRiskExceptions:
    """Risk 관련 예외 테스트"""

    def test_risk_limit_exceeded(self):
        """리스크 한도 초과 예외"""
        exc = RiskLimitExceededException(
            risk_type="position_size",
            current_value=0.35,
            limit=0.25
        )

        assert exc.error_code == "RISK_LIMIT_EXCEEDED"
        assert exc.details['risk_type'] == "position_size"
        assert exc.details['current_value'] == 0.35
        assert exc.details['limit'] == 0.25
        assert exc.recoverable is False
        assert isinstance(exc, RiskException)

    def test_drawdown_exceeded(self):
        """최대 낙폭 초과 예외"""
        exc = DrawdownExceededException(
            current_drawdown=0.25,
            max_drawdown=0.20
        )

        assert exc.error_code == "MAX_DRAWDOWN_EXCEEDED"
        assert exc.details['current_drawdown'] == 0.25
        assert exc.details['max_drawdown'] == 0.20
        assert exc.recoverable is False


class TestPortfolioExceptions:
    """Portfolio 관련 예외 테스트"""

    def test_asset_allocation(self):
        """자산 배분 오류 예외"""
        exc = AssetAllocationException(
            reason="자산 배분 합계가 100%를 초과",
            allocations={"BTC": 0.5, "ETH": 0.6}
        )

        assert isinstance(exc, PortfolioException)
        assert exc.error_code == "ASSET_ALLOCATION_ERROR"
        assert exc.details['reason'] == "자산 배분 합계가 100%를 초과"

    def test_rebalancing_exception(self):
        """리밸런싱 오류 예외"""
        exc = RebalancingException(
            reason="리밸런싱 실패",
            details={"attempt": 1}
        )

        assert isinstance(exc, PortfolioException)
        assert exc.error_code == "REBALANCING_FAILED"


class TestSystemExceptions:
    """System 관련 예외 테스트"""

    def test_configuration_exception(self):
        """설정 오류 예외"""
        exc = ConfigurationException(
            config_key="api.key",
            issue="필수 설정값 누락"
        )

        assert isinstance(exc, KairosException)
        assert exc.error_code == "CONFIGURATION_ERROR"

    def test_database_exception(self):
        """데이터베이스 오류 예외"""
        exc = DatabaseException(
            operation="INSERT",
            error="연결 실패"
        )

        assert isinstance(exc, SystemException)
        assert exc.error_code == "DATABASE_ERROR"


class TestDataExceptions:
    """Data 관련 예외 테스트"""

    def test_data_validation(self):
        """데이터 검증 오류 예외"""
        exc = DataValidationException(
            field="price",
            value=-100,
            expected="양수"
        )

        assert isinstance(exc, DataException)
        assert exc.error_code == "DATA_VALIDATION_FAILED"

    def test_data_integrity(self):
        """데이터 무결성 오류 예외"""
        exc = DataIntegrityException(
            data_type="portfolio",
            issue="잔고 불일치"
        )

        assert isinstance(exc, DataException)
        assert exc.error_code == "DATA_INTEGRITY_ERROR"


class TestExceptionHierarchy:
    """예외 계층 구조 테스트"""

    def test_trading_hierarchy(self):
        """Trading 예외 계층"""
        exc = InsufficientBalanceException(1.0, 0.5, "BTC")

        assert isinstance(exc, InsufficientBalanceException)
        assert isinstance(exc, TradingException)
        assert isinstance(exc, KairosException)
        assert isinstance(exc, Exception)

    def test_api_hierarchy(self):
        """API 예외 계층"""
        exc = APIRateLimitException("Coinone")

        assert isinstance(exc, APIRateLimitException)
        assert isinstance(exc, APIException)
        assert isinstance(exc, KairosException)
        assert isinstance(exc, Exception)

    def test_risk_hierarchy(self):
        """Risk 예외 계층"""
        exc = RiskLimitExceededException("test", 1.0, 0.5)

        assert isinstance(exc, RiskLimitExceededException)
        assert isinstance(exc, RiskException)
        assert isinstance(exc, KairosException)
