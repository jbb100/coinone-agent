"""
Custom Exception Classes for KAIROS-1 System

체계적인 에러 처리를 위한 커스텀 예외 클래스들
"""

from typing import Optional, Dict, Any
from datetime import datetime


class KairosException(Exception):
    """KAIROS 시스템 기본 예외 클래스"""
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        recoverable: bool = True
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        self.recoverable = recoverable
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """예외 정보를 딕셔너리로 변환"""
        return {
            'error_code': self.error_code,
            'message': self.message,
            'details': self.details,
            'recoverable': self.recoverable,
            'timestamp': self.timestamp.isoformat()
        }


# Trading Exceptions
class TradingException(KairosException):
    """거래 관련 기본 예외"""
    pass


class InsufficientBalanceException(TradingException):
    """잔고 부족 예외"""
    
    def __init__(self, required: float, available: float, asset: str):
        super().__init__(
            f"잔고 부족: {asset} - 필요: {required}, 가용: {available}",
            error_code="INSUFFICIENT_BALANCE",
            details={
                'asset': asset,
                'required': required,
                'available': available,
                'shortage': required - available
            },
            recoverable=True
        )


class OrderExecutionException(TradingException):
    """주문 실행 실패 예외"""
    
    def __init__(self, order_id: str, reason: str, details: Optional[Dict] = None):
        super().__init__(
            f"주문 실행 실패 [{order_id}]: {reason}",
            error_code="ORDER_EXECUTION_FAILED",
            details={'order_id': order_id, 'reason': reason, **(details or {})},
            recoverable=True
        )


class MinimumOrderSizeException(TradingException):
    """최소 주문 크기 미달 예외"""
    
    def __init__(self, amount: float, minimum: float, asset: str):
        super().__init__(
            f"최소 주문 크기 미달: {asset} - 주문: {amount}, 최소: {minimum}",
            error_code="MINIMUM_ORDER_SIZE",
            details={
                'asset': asset,
                'amount': amount,
                'minimum': minimum
            },
            recoverable=True
        )


class PriceSlippageException(TradingException):
    """가격 슬리피지 초과 예외"""
    
    def __init__(self, expected_price: float, actual_price: float, max_slippage: float):
        slippage = abs((actual_price - expected_price) / expected_price)
        super().__init__(
            f"슬리피지 한도 초과: {slippage:.2%} > {max_slippage:.2%}",
            error_code="EXCESSIVE_SLIPPAGE",
            details={
                'expected_price': expected_price,
                'actual_price': actual_price,
                'slippage': slippage,
                'max_slippage': max_slippage
            },
            recoverable=True
        )


# API Exceptions
class APIException(KairosException):
    """API 관련 기본 예외"""
    pass


class APIAuthenticationException(APIException):
    """API 인증 실패 예외"""
    
    def __init__(self, service: str, details: Optional[Dict] = None):
        super().__init__(
            f"API 인증 실패: {service}",
            error_code="API_AUTH_FAILED",
            details={'service': service, **(details or {})},
            recoverable=False
        )


class APIRateLimitException(APIException):
    """API 요청 한도 초과 예외"""
    
    def __init__(self, service: str, retry_after: Optional[int] = None):
        super().__init__(
            f"API 요청 한도 초과: {service}",
            error_code="API_RATE_LIMIT",
            details={
                'service': service,
                'retry_after': retry_after
            },
            recoverable=True
        )


class APITimeoutException(APIException):
    """API 요청 시간 초과 예외"""
    
    def __init__(self, service: str, timeout: int):
        super().__init__(
            f"API 요청 시간 초과: {service} ({timeout}초)",
            error_code="API_TIMEOUT",
            details={
                'service': service,
                'timeout': timeout
            },
            recoverable=True
        )


class APIResponseException(APIException):
    """API 응답 오류 예외"""
    
    def __init__(self, service: str, status_code: int, response: Optional[str] = None):
        super().__init__(
            f"API 응답 오류: {service} - 상태 코드: {status_code}",
            error_code="API_RESPONSE_ERROR",
            details={
                'service': service,
                'status_code': status_code,
                'response': response
            },
            recoverable=status_code >= 500  # 5xx는 재시도 가능
        )


# Risk Management Exceptions
class RiskException(KairosException):
    """리스크 관리 관련 기본 예외"""
    pass


class RiskLimitExceededException(RiskException):
    """리스크 한도 초과 예외"""
    
    def __init__(self, risk_type: str, current_value: float, limit: float):
        super().__init__(
            f"리스크 한도 초과: {risk_type} - 현재: {current_value}, 한도: {limit}",
            error_code="RISK_LIMIT_EXCEEDED",
            details={
                'risk_type': risk_type,
                'current_value': current_value,
                'limit': limit
            },
            recoverable=False
        )


class DrawdownExceededException(RiskException):
    """최대 낙폭 초과 예외"""
    
    def __init__(self, current_drawdown: float, max_drawdown: float):
        super().__init__(
            f"최대 낙폭 초과: {current_drawdown:.2%} > {max_drawdown:.2%}",
            error_code="MAX_DRAWDOWN_EXCEEDED",
            details={
                'current_drawdown': current_drawdown,
                'max_drawdown': max_drawdown
            },
            recoverable=False
        )


# Portfolio Exceptions
class PortfolioException(KairosException):
    """포트폴리오 관련 기본 예외"""
    pass


class AssetAllocationException(PortfolioException):
    """자산 배분 오류 예외"""
    
    def __init__(self, reason: str, allocations: Optional[Dict] = None):
        super().__init__(
            f"자산 배분 오류: {reason}",
            error_code="ASSET_ALLOCATION_ERROR",
            details={
                'reason': reason,
                'allocations': allocations
            },
            recoverable=True
        )


class RebalancingException(PortfolioException):
    """리밸런싱 실패 예외"""
    
    def __init__(self, reason: str, details: Optional[Dict] = None):
        super().__init__(
            f"리밸런싱 실패: {reason}",
            error_code="REBALANCING_FAILED",
            details={'reason': reason, **(details or {})},
            recoverable=True
        )


# Data Exceptions
class DataException(KairosException):
    """데이터 관련 기본 예외"""
    pass


class DataValidationException(DataException):
    """데이터 검증 실패 예외"""
    
    def __init__(self, field: str, value: Any, expected: str):
        super().__init__(
            f"데이터 검증 실패: {field} - 값: {value}, 예상: {expected}",
            error_code="DATA_VALIDATION_FAILED",
            details={
                'field': field,
                'value': value,
                'expected': expected
            },
            recoverable=True
        )


class DataIntegrityException(DataException):
    """데이터 무결성 오류 예외"""
    
    def __init__(self, data_type: str, issue: str):
        super().__init__(
            f"데이터 무결성 오류: {data_type} - {issue}",
            error_code="DATA_INTEGRITY_ERROR",
            details={
                'data_type': data_type,
                'issue': issue
            },
            recoverable=False
        )


class StaleDataException(DataException):
    """오래된 데이터 예외"""
    
    def __init__(self, data_type: str, age_seconds: int, max_age: int):
        super().__init__(
            f"오래된 데이터: {data_type} - 경과: {age_seconds}초, 최대: {max_age}초",
            error_code="STALE_DATA",
            details={
                'data_type': data_type,
                'age_seconds': age_seconds,
                'max_age': max_age
            },
            recoverable=True
        )


# Configuration Exceptions
class ConfigurationException(KairosException):
    """설정 관련 기본 예외"""
    
    def __init__(self, config_key: str, issue: str):
        super().__init__(
            f"설정 오류: {config_key} - {issue}",
            error_code="CONFIGURATION_ERROR",
            details={
                'config_key': config_key,
                'issue': issue
            },
            recoverable=False
        )


class MissingConfigurationException(ConfigurationException):
    """필수 설정 누락 예외"""
    
    def __init__(self, config_key: str):
        super().__init__(
            config_key,
            f"필수 설정 누락: {config_key}"
        )


class InvalidConfigurationException(ConfigurationException):
    """잘못된 설정 예외"""
    
    def __init__(self, config_key: str, value: Any, expected: str):
        super().__init__(
            config_key,
            f"잘못된 값: {value}, 예상: {expected}"
        )


# System Exceptions
class SystemException(KairosException):
    """시스템 관련 기본 예외"""
    pass


class DatabaseException(SystemException):
    """데이터베이스 오류 예외"""
    
    def __init__(self, operation: str, error: str):
        super().__init__(
            f"데이터베이스 오류: {operation} - {error}",
            error_code="DATABASE_ERROR",
            details={
                'operation': operation,
                'error': error
            },
            recoverable=True
        )


class FileSystemException(SystemException):
    """파일 시스템 오류 예외"""
    
    def __init__(self, operation: str, file_path: str, error: str):
        super().__init__(
            f"파일 시스템 오류: {operation} - {file_path}: {error}",
            error_code="FILESYSTEM_ERROR",
            details={
                'operation': operation,
                'file_path': file_path,
                'error': error
            },
            recoverable=True
        )


class NetworkException(SystemException):
    """네트워크 오류 예외"""
    
    def __init__(self, service: str, error: str):
        super().__init__(
            f"네트워크 오류: {service} - {error}",
            error_code="NETWORK_ERROR",
            details={
                'service': service,
                'error': error
            },
            recoverable=True
        )