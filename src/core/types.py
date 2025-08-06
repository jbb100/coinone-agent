"""
Type Definitions for KAIROS-1 System

시스템 전반에서 사용되는 타입 정의
"""

from typing import (
    Dict, List, Optional, Union, Any, Callable, Awaitable,
    TypeVar, Generic, Protocol, Literal, NewType, TypedDict
)
from datetime import datetime
from decimal import Decimal
from enum import Enum
from dataclasses import dataclass
from abc import ABC, abstractmethod


# ============================================================================
# Basic Types
# ============================================================================

# 화폐 관련 타입
KRWAmount = NewType('KRWAmount', Decimal)
CryptoAmount = NewType('CryptoAmount', Decimal)
Price = NewType('Price', Decimal)
Percentage = NewType('Percentage', float)  # 0.0 ~ 1.0
BasisPoints = NewType('BasisPoints', int)   # 0 ~ 10000 (100% = 10000bp)

# 식별자 타입
AssetSymbol = NewType('AssetSymbol', str)
OrderID = NewType('OrderID', str)
TransactionID = NewType('TransactionID', str)
UserID = NewType('UserID', str)
AccountID = NewType('AccountID', str)  # 멀티 계정 지원
AccountName = NewType('AccountName', str)  # 계정 표시명

# 타임스탬프 타입
UnixTimestamp = NewType('UnixTimestamp', int)
ISOTimestamp = NewType('ISOTimestamp', str)


# ============================================================================
# Enums
# ============================================================================

class AssetType(Enum):
    """자산 유형"""
    FIAT = "fiat"           # 법정화폐
    CRYPTO = "crypto"       # 암호화폐
    STABLECOIN = "stablecoin"  # 스테이블코인
    TOKEN = "token"         # 토큰


class OrderSide(Enum):
    """주문 방향"""
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    """주문 유형"""
    MARKET = "market"       # 시장가 주문
    LIMIT = "limit"         # 지정가 주문
    STOP = "stop"           # 스탑 주문
    STOP_LIMIT = "stop_limit"  # 스탑 리미트 주문


class OrderStatus(Enum):
    """주문 상태"""
    PENDING = "pending"     # 대기 중
    PARTIAL = "partial"     # 부분 체결
    FILLED = "filled"       # 완전 체결
    CANCELLED = "cancelled" # 취소됨
    REJECTED = "rejected"   # 거부됨
    EXPIRED = "expired"     # 만료됨


class MarketSeason(Enum):
    """시장 계절"""
    RISK_ON = "risk_on"     # 위험 선호
    RISK_OFF = "risk_off"   # 위험 회피
    NEUTRAL = "neutral"     # 중립


class RebalanceFrequency(Enum):
    """리밸런싱 주기"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


class RiskLevel(Enum):
    """리스크 수준"""
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


class AccountStatus(Enum):
    """계정 상태"""
    ACTIVE = "active"           # 활성
    INACTIVE = "inactive"       # 비활성
    SUSPENDED = "suspended"     # 정지
    ERROR = "error"            # 오류


class ExecutionStrategy(Enum):
    """실행 전략"""
    MARKET = "market"
    LIMIT_AGGRESSIVE = "limit_aggressive"
    LIMIT_CONSERVATIVE = "limit_conservative"
    TWAP_SMART = "twap_smart"


# ============================================================================
# TypedDict Classes
# ============================================================================

class AssetInfo(TypedDict):
    """자산 정보"""
    symbol: AssetSymbol
    name: str
    asset_type: AssetType
    decimals: int
    min_order_size: CryptoAmount
    max_order_size: Optional[CryptoAmount]
    trading_fee: Percentage
    withdrawal_fee: Optional[CryptoAmount]
    is_active: bool


class PriceData(TypedDict):
    """가격 데이터"""
    symbol: AssetSymbol
    price: Price
    bid: Price
    ask: Price
    volume_24h: CryptoAmount
    change_24h: Percentage
    timestamp: datetime


class BalanceInfo(TypedDict):
    """잔고 정보"""
    asset: AssetSymbol
    total: CryptoAmount
    available: CryptoAmount
    locked: CryptoAmount
    value_krw: KRWAmount


class AccountInfo(TypedDict):
    """계정 정보"""
    account_id: AccountID
    account_name: AccountName
    description: str
    status: AccountStatus
    risk_level: RiskLevel
    created_at: datetime
    last_updated: datetime
    
    # API 정보
    api_key_id: str
    
    # 투자 설정
    initial_capital: KRWAmount
    max_investment: KRWAmount
    auto_rebalance: bool
    
    # 성과 정보
    current_value: KRWAmount
    total_return: Percentage
    last_rebalance: Optional[datetime]


class OrderInfo(TypedDict):
    """주문 정보"""
    order_id: OrderID
    symbol: AssetSymbol
    side: OrderSide
    order_type: OrderType
    quantity: CryptoAmount
    price: Optional[Price]
    status: OrderStatus
    filled_quantity: CryptoAmount
    filled_price: Optional[Price]
    fee: KRWAmount
    timestamp: datetime


class TradeInfo(TypedDict):
    """거래 정보"""
    trade_id: TransactionID
    order_id: OrderID
    symbol: AssetSymbol
    side: OrderSide
    quantity: CryptoAmount
    price: Price
    fee: KRWAmount
    timestamp: datetime


class PortfolioSnapshot(TypedDict):
    """포트폴리오 스냅샷"""
    timestamp: datetime
    total_value_krw: KRWAmount
    assets: Dict[AssetSymbol, BalanceInfo]
    weights: Dict[AssetSymbol, Percentage]
    daily_return: Optional[Percentage]
    total_return: Percentage


class RiskMetrics(TypedDict):
    """리스크 지표"""
    portfolio_value: KRWAmount
    var_95: KRWAmount           # Value at Risk (95%)
    cvar_95: KRWAmount          # Conditional VaR (95%)
    max_drawdown: Percentage
    volatility: Percentage
    sharpe_ratio: float
    beta: Optional[float]


# ============================================================================
# Protocol Classes (Interface Definitions)
# ============================================================================

class PriceProvider(Protocol):
    """가격 제공자 인터페이스"""
    
    async def get_price(self, symbol: AssetSymbol) -> Price:
        """단일 자산 가격 조회"""
        ...
    
    async def get_prices(self, symbols: List[AssetSymbol]) -> Dict[AssetSymbol, Price]:
        """다중 자산 가격 조회"""
        ...
    
    async def get_price_data(self, symbol: AssetSymbol) -> PriceData:
        """상세 가격 데이터 조회"""
        ...


class ExchangeClient(Protocol):
    """거래소 클라이언트 인터페이스"""
    
    async def get_balances(self) -> List[BalanceInfo]:
        """잔고 조회"""
        ...
    
    async def place_order(
        self,
        symbol: AssetSymbol,
        side: OrderSide,
        order_type: OrderType,
        quantity: CryptoAmount,
        price: Optional[Price] = None
    ) -> OrderInfo:
        """주문 생성"""
        ...
    
    async def get_order(self, order_id: OrderID) -> OrderInfo:
        """주문 조회"""
        ...
    
    async def cancel_order(self, order_id: OrderID) -> bool:
        """주문 취소"""
        ...
    
    async def get_trades(
        self,
        symbol: Optional[AssetSymbol] = None,
        limit: int = 100
    ) -> List[TradeInfo]:
        """거래 내역 조회"""
        ...


class PortfolioManager(Protocol):
    """포트폴리오 관리자 인터페이스"""
    
    async def get_portfolio_snapshot(self) -> PortfolioSnapshot:
        """포트폴리오 스냅샷 조회"""
        ...
    
    async def calculate_target_weights(
        self,
        market_season: MarketSeason,
        risk_level: RiskLevel
    ) -> Dict[AssetSymbol, Percentage]:
        """목표 비중 계산"""
        ...
    
    async def rebalance_portfolio(
        self,
        target_weights: Dict[AssetSymbol, Percentage]
    ) -> List[OrderInfo]:
        """포트폴리오 리밸런싱"""
        ...


class RiskManager(Protocol):
    """리스크 관리자 인터페이스"""
    
    async def calculate_risk_metrics(
        self,
        portfolio: PortfolioSnapshot
    ) -> RiskMetrics:
        """리스크 지표 계산"""
        ...
    
    async def check_risk_limits(
        self,
        portfolio: PortfolioSnapshot,
        proposed_trades: List[OrderInfo]
    ) -> bool:
        """리스크 한도 확인"""
        ...
    
    async def get_position_size_limit(
        self,
        symbol: AssetSymbol,
        side: OrderSide
    ) -> CryptoAmount:
        """포지션 크기 한도"""
        ...


# ============================================================================
# Generic Types and Constraints
# ============================================================================

T = TypeVar('T')
K = TypeVar('K')
V = TypeVar('V')

# 숫자 타입
NumericType = TypeVar('NumericType', int, float, Decimal)

# 시계열 데이터
TimeSeriesData = Dict[datetime, T]
PriceTimeSeries = TimeSeriesData[Price]
VolumeTimeSeries = TimeSeriesData[CryptoAmount]

# 콜백 함수 타입
EventCallback = Callable[[str, Dict[str, Any]], None]
AsyncEventCallback = Callable[[str, Dict[str, Any]], Awaitable[None]]

# 필터 함수 타입
DataFilter = Callable[[T], bool]
AsyncDataFilter = Callable[[T], Awaitable[bool]]


# ============================================================================
# Configuration Types
# ============================================================================

class TradingConfig(TypedDict):
    """거래 설정"""
    enabled: bool
    min_order_amount: KRWAmount
    max_order_amount: KRWAmount
    max_slippage: Percentage
    max_position_size: Percentage
    dry_run: bool


class RebalancingConfig(TypedDict):
    """리밸런싱 설정"""
    enabled: bool
    frequency: RebalanceFrequency
    threshold: Percentage        # 리밸런싱 임계값
    max_trades_per_session: int
    cooldown_minutes: int


class RiskConfig(TypedDict):
    """리스크 설정"""
    max_portfolio_drawdown: Percentage
    max_asset_weight: Percentage
    min_asset_weight: Percentage
    var_confidence_level: float  # 0.95 for 95% VaR
    stop_loss_threshold: Optional[Percentage]


class BacktestConfig(TypedDict):
    """백테스팅 설정"""
    start_date: str              # YYYY-MM-DD
    end_date: str               # YYYY-MM-DD
    initial_capital: KRWAmount
    transaction_cost: Percentage
    slippage: Percentage
    rebalance_frequency: RebalanceFrequency
    risk_level: RiskLevel


# ============================================================================
# Result Types
# ============================================================================

@dataclass
class ExecutionResult:
    """실행 결과"""
    success: bool
    order_id: Optional[OrderID] = None
    filled_quantity: CryptoAmount = CryptoAmount(Decimal('0'))
    average_price: Optional[Price] = None
    total_fee: KRWAmount = KRWAmount(Decimal('0'))
    error_message: Optional[str] = None
    execution_time_ms: int = 0


@dataclass
class RebalanceResult:
    """리밸런싱 결과"""
    success: bool
    orders_placed: List[OrderInfo]
    orders_failed: List[Dict[str, Any]]
    total_value_before: KRWAmount
    total_value_after: KRWAmount
    execution_time_seconds: float
    error_message: Optional[str] = None


@dataclass
class PerformanceMetrics:
    """성과 지표"""
    total_return: Percentage
    annualized_return: Percentage
    volatility: Percentage
    sharpe_ratio: float
    max_drawdown: Percentage
    calmar_ratio: float
    win_rate: Percentage
    profit_factor: float
    
    # 거래 통계
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_trade_return: Percentage
    largest_win: Percentage
    largest_loss: Percentage
    
    # 시기별 수익률
    monthly_returns: List[Percentage]
    yearly_returns: List[Percentage]


# ============================================================================
# Error Types
# ============================================================================

class ErrorDetail(TypedDict):
    """에러 상세 정보"""
    error_code: str
    message: str
    details: Dict[str, Any]
    timestamp: datetime
    recoverable: bool


class ValidationError(TypedDict):
    """검증 에러"""
    field: str
    value: Any
    constraint: str
    message: str


# ============================================================================
# API Response Types
# ============================================================================

class APIResponse(TypedDict):
    """API 응답"""
    success: bool
    data: Optional[Any]
    error: Optional[ErrorDetail]
    timestamp: datetime


class PaginatedResponse(TypedDict):
    """페이지네이션 응답"""
    items: List[Any]
    total_count: int
    page: int
    page_size: int
    has_next: bool


# ============================================================================
# Event Types
# ============================================================================

class OrderEvent(TypedDict):
    """주문 이벤트"""
    event_type: Literal["order_created", "order_filled", "order_cancelled"]
    order_info: OrderInfo
    timestamp: datetime


class PriceEvent(TypedDict):
    """가격 이벤트"""
    event_type: Literal["price_update"]
    symbol: AssetSymbol
    old_price: Price
    new_price: Price
    change_percentage: Percentage
    timestamp: datetime


class PortfolioEvent(TypedDict):
    """포트폴리오 이벤트"""
    event_type: Literal["rebalance_started", "rebalance_completed", "risk_limit_exceeded"]
    portfolio_snapshot: PortfolioSnapshot
    details: Dict[str, Any]
    timestamp: datetime


# Event union type
Event = Union[OrderEvent, PriceEvent, PortfolioEvent]


# ============================================================================
# Function Signatures
# ============================================================================

# 일반적인 비동기 함수 시그니처
AsyncFunction = Callable[..., Awaitable[Any]]
AsyncPredicate = Callable[..., Awaitable[bool]]

# 이벤트 핸들러 시그니처
EventHandler = Callable[[Event], None]
AsyncEventHandler = Callable[[Event], Awaitable[None]]

# 데이터 변환 함수 시그니처
DataTransformer = Callable[[T], K]
AsyncDataTransformer = Callable[[T], Awaitable[K]]

# 가격 계산 함수 시그니처
PriceCalculator = Callable[[List[Price]], Price]
WeightCalculator = Callable[[PortfolioSnapshot, MarketSeason], Dict[AssetSymbol, Percentage]]