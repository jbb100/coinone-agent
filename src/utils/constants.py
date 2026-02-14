"""
Constants for KAIROS-1 Trading System

모든 하드코딩된 값들과 매직 넘버들을 중앙 집중화하여 관리합니다.
"""

from typing import Dict

# =============================================================================
# Trading Constants
# =============================================================================

# Rebalancing thresholds
REBALANCE_THRESHOLD = 0.01  # 1% - 리밸런싱 임계값
MIN_ORDER_KRW = 1_000  # 1,000 KRW - 거래소 기술적 최소값 (Coinone API 기준)
MIN_TRADE_AMOUNT_KRW = 10_000  # 10,000 KRW - 운영상 최소 거래 금액 (수수료/슬리피지 고려)
MIN_ORDER_KRW_BUFFER = 1.05  # 5% 안전 마진
SAFETY_MARGIN = 0.99  # 99% - 안전 마진 (수수료 고려)

# Order limits and safety
MAX_SLIPPAGE = 0.005  # 0.5% - 최대 슬리피지
ORDER_TIMEOUT_SECONDS = 300  # 5분 - 주문 타임아웃
MAX_RETRIES = 3  # 최대 재시도 횟수

# Portfolio allocation ratios
CORE_WEIGHT = 0.70  # 70% - Core 자산 비중
SATELLITE_WEIGHT = 0.30  # 30% - Satellite 자산 비중

# =============================================================================
# Risk Management Constants
# =============================================================================

# Risk thresholds
MAX_DAILY_LOSS_THRESHOLD = 0.05  # 5% - 일일 최대 손실 한도
MAX_POSITION_SIZE = 0.25  # 25% - 개별 자산 최대 비중
MIN_KRW_RATIO = 0.01  # 1% - 최소 KRW 비율

# Volatility parameters
VOLATILITY_LOOKBACK_DAYS = 30  # 30일 - 변동성 계산 기간
HIGH_VOLATILITY_THRESHOLD = 0.05  # 5% - 고변동성 임계값

# =============================================================================
# Market Season Constants
# =============================================================================

# Market season allocation weights
DEFAULT_CRYPTO_ALLOCATION = {
    "RISK_ON": 0.70,    # 70% - 강세장 시 암호화폐 비중
    "RISK_OFF": 0.30,   # 30% - 약세장 시 암호화폐 비중
    "NEUTRAL": 0.50     # 50% - 중립 시 암호화폐 비중
}

# Moving average periods
MA_200W_BUFFER_BAND = 0.05  # 5% - 200주 이동평균 버퍼 밴드
MA_CALCULATION_FALLBACK_RATIO = 0.9  # 90% - 200주 이동평균 계산 실패 시 fallback 비율

# =============================================================================
# API and Database Constants
# =============================================================================

# API rate limits
API_RATE_LIMIT_PER_MINUTE = 100  # 분당 API 호출 제한
API_REQUEST_TIMEOUT = 30  # 30초 - API 요청 타임아웃

# Database settings
DB_CONNECTION_TIMEOUT = 10  # 10초 - DB 연결 타임아웃
DB_QUERY_TIMEOUT = 30  # 30초 - DB 쿼리 타임아웃
DB_RETRY_ATTEMPTS = 3  # DB 재시도 횟수

# Data freshness
MARKET_ANALYSIS_MAX_AGE_DAYS = 7  # 7일 - 시장 분석 데이터 유효 기간
PRICE_DATA_MAX_AGE_MINUTES = 5  # 5분 - 가격 데이터 유효 기간

# =============================================================================
# Market Data Defaults
# =============================================================================

# Exchange rate defaults
DEFAULT_USD_KRW_RATE = 1400.0  # 기본 USD/KRW 환율 (API 실패 시 폴백)

# BTC dominance defaults
DEFAULT_BTC_DOMINANCE = 0.6  # 기본 BTC 도미넌스 (API 실패 시 폴백)
BTC_DOMINANCE_MIN = 0.65  # BTC 도미넌스 축적 임계값

# =============================================================================
# TWAP Constants
# =============================================================================

# TWAP execution parameters
DEFAULT_TWAP_HOURS = 4  # 4시간 - 기본 TWAP 실행 시간
MIN_SLICE_INTERVAL_MINUTES = 10  # 10분 - 최소 슬라이스 간격
MAX_SLICE_INTERVAL_MINUTES = 60  # 60분 - 최대 슬라이스 간격
MIN_SLICES_PER_ORDER = 2  # 최소 슬라이스 개수
MAX_SLICES_PER_ORDER = 24  # 최대 슬라이스 개수

# TWAP size limits
MIN_TWAP_AMOUNT_KRW = 50_000  # 50,000 KRW - 최소 TWAP 금액
MAX_SLICE_AMOUNT_KRW = 100_000_000  # 100,000,000 KRW - 최대 슬라이스 금액 (100M KRW)

# Coinone exchange limits
COINONE_MAX_ORDER_AMOUNT_KRW = 500_000_000  # 500M KRW - 코인원 최대 주문 금액
COINONE_SAFE_ORDER_LIMIT_KRW = 200_000_000  # 200M KRW - 안전한 주문 금액 한도

# =============================================================================
# Cryptocurrency Specific Constants
# =============================================================================

# Minimum order quantities by currency
MIN_ORDER_QUANTITIES = {
    "BTC": 0.0001,
    "ETH": 0.0001, 
    "XRP": 1.0,
    "SOL": 0.01,
    "ADA": 2.0,
    "DOT": 1.0,
    "DOGE": 10.0,
    "TRX": 10.0,
    "XLM": 10.0,
    "ATOM": 0.2,
    "ALGO": 5.0,
    "VET": 50.0
}

# Minimum order amounts by currency (KRW) - for buy orders
MIN_ORDER_AMOUNTS_KRW = {
    "BTC": 5000,
    "ETH": 5000,
    "XRP": 5000,
    "SOL": 5000,
    "ADA": 5000,
    "DOT": 5000,
    "DOGE": 5000,
    "TRX": 5000,
    "XLM": 5000,
    "ATOM": 5000,
    "ALGO": 5000,
    "VET": 5000
}

# Maximum order limits by currency (KRW)
MAX_ORDER_LIMITS_KRW = {
    "BTC": 10_000_000,
    "ETH": 10_000_000,
    "XRP": 5_000_000,
    "SOL": 5_000_000,
    "ADA": 3_000_000,
    "DOT": 3_000_000
}

# Supported cryptocurrencies
SUPPORTED_CRYPTOCURRENCIES = ["BTC", "ETH", "XRP", "SOL"]
CORE_ASSETS = ["BTC", "ETH"]
SATELLITE_ASSETS = ["XRP", "SOL"]

# =============================================================================
# Logging and Monitoring Constants
# =============================================================================

# Log rotation settings
LOG_MAX_SIZE = "100 MB"
LOG_RETENTION = "30 days"

# Alert thresholds
PORTFOLIO_VALUE_ALERT_THRESHOLD = 0.1  # 10% - 포트폴리오 가치 변동 알림 임계값
ORDER_FAILURE_ALERT_THRESHOLD = 3  # 연속 주문 실패 시 알림

# Performance tracking
PERFORMANCE_CALCULATION_PERIOD_DAYS = 30  # 30일 - 성과 계산 기간
BENCHMARK_SYMBOL = "BTC"  # 벤치마크 기준

# =============================================================================
# System Health Constants
# =============================================================================

# Health check intervals
SYSTEM_HEALTH_CHECK_INTERVAL_MINUTES = 5  # 5분 - 시스템 상태 체크 간격
MARKET_DATA_FRESHNESS_CHECK_MINUTES = 1  # 1분 - 시장 데이터 신선도 체크

# Error handling
MAX_CONSECUTIVE_ERRORS = 5  # 최대 연속 오류 허용 횟수
ERROR_BACKOFF_SECONDS = 60  # 오류 발생 시 대기 시간

# =============================================================================
# Configuration Keys
# =============================================================================

# Required configuration keys for validation
# API 키는 멀티 계정 관리자에서 관리하므로 제외
REQUIRED_CONFIG_KEYS = [
    "logging.level"
]

# Sensitive configuration keys (for masking in logs)
SENSITIVE_CONFIG_KEYS = [
    "api_key", "secret_key", "password", "token",
    "access_token", "private_key", "webhook_url"
]

# =============================================================================
# Technical Indicators Constants (CLAUDE.md 기준)
# =============================================================================

# RSI (Relative Strength Index)
RSI_PERIOD = 14  # 14일 기간
RSI_OVERSOLD = 30  # 과매도 임계값
RSI_OVERBOUGHT = 70  # 과매수 임계값
RSI_MIDLINE = 50  # 중심선

# MACD (Moving Average Convergence Divergence)
MACD_FAST = 12  # 빠른 EMA 기간
MACD_SLOW = 26  # 느린 EMA 기간
MACD_SIGNAL = 9  # 시그널 라인 기간

# Bollinger Bands
BOLLINGER_PERIOD = 20  # SMA 기간
BOLLINGER_STD = 2  # 표준편차 배수

# Moving Averages
MA_SHORT = 50  # 단기 이동평균
MA_LONG = 200  # 장기 이동평균

# =============================================================================
# On-chain Metrics Constants (CLAUDE.md 기준)
# =============================================================================

# MVRV (Market Value to Realized Value)
MVRV_UNDERVALUED = 1.0  # 과소평가 임계값
MVRV_OVERVALUED = 3.0  # 과대평가 임계값

# Fear & Greed Index
FEAR_GREED_EXTREME_FEAR = 25  # 극단적 공포
FEAR_GREED_FEAR = 40  # 공포
FEAR_GREED_NEUTRAL = 50  # 중립
FEAR_GREED_GREED = 60  # 탐욕
FEAR_GREED_EXTREME_GREED = 75  # 극단적 탐욕

# NUPL (Net Unrealized Profit/Loss)
NUPL_CAPITULATION = 0.0  # 항복
NUPL_HOPE = 0.25  # 희망
NUPL_OPTIMISM = 0.50  # 낙관
NUPL_BELIEF = 0.75  # 확신
NUPL_EUPHORIA = 0.90  # 행복감

# =============================================================================
# Kelly Criterion Constants (CLAUDE.md 기준)
# =============================================================================

# Kelly fraction multipliers
KELLY_FULL = 1.0  # Full Kelly
KELLY_HALF = 0.5  # Half Kelly (권장)
KELLY_QUARTER = 0.25  # Quarter Kelly (보수적)

# Position sizing rules
MAX_RISK_PER_TRADE = 0.01  # 1% 규칙 (거래당 최대 리스크)
MAX_RISK_AGGRESSIVE = 0.02  # 2% (공격적)
MAX_RISK_CONSERVATIVE = 0.005  # 0.5% (보수적)

# =============================================================================
# Signal Strength Constants
# =============================================================================

# Composite signal confidence levels
SIGNAL_CONFIDENCE_HIGH = 0.85  # 3개 지표 정렬
SIGNAL_CONFIDENCE_MEDIUM = 0.65  # 2개 지표 정렬
SIGNAL_CONFIDENCE_LOW = 0.40  # 지표 혼재

# Signal alignment thresholds
SIGNAL_STRONG_THRESHOLD = 3  # STRONG 신호에 필요한 정렬 지표 수
SIGNAL_NORMAL_THRESHOLD = 2  # 일반 신호에 필요한 정렬 지표 수

# =============================================================================
# Bitcoin Cycle Constants (CLAUDE.md 기준)
# =============================================================================

# Halving cycle allocations
CYCLE_ACCUMULATION_CRYPTO = 0.80  # 축적기 암호화폐 비중
CYCLE_EARLY_BULL_CRYPTO = 0.70  # 초기 상승장 비중
CYCLE_DISTRIBUTION_CRYPTO = 0.30  # 분배기 비중
CYCLE_BEAR_MARKET_CRYPTO = 0.20  # 하락장 비중

# Cycle timing (days after halving)
CYCLE_PEAK_MIN_DAYS = 365  # 반감기 후 최소 피크 기간
CYCLE_PEAK_MAX_DAYS = 550  # 반감기 후 최대 피크 기간

# =============================================================================
# Backtesting Constants (CLAUDE.md 기준)
# =============================================================================

# Overfitting warnings
SHARPE_OVERFITTING_THRESHOLD = 3.0  # Sharpe > 3.0 시 과적합 의심
MAX_STRATEGY_PARAMS = 5  # 최대 전략 파라미터 수
OOS_PERFORMANCE_DROP_THRESHOLD = 0.30  # OOS 성능 하락 30% 시 과적합

# Data requirements
MIN_BACKTEST_DAYS = 365  # 최소 백테스트 기간 (1년)
TRAIN_TEST_SPLIT = 0.7  # 학습/테스트 분할 비율