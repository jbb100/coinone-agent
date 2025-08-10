"""
Pytest Configuration and Fixtures for KAIROS-1 Tests

테스트를 위한 공통 설정과 픽스처들
"""

import pytest
import asyncio
import sqlite3
import tempfile
import shutil
from pathlib import Path
from typing import Generator, Dict, Any
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

# Test imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.core.exceptions import *
from src.security.secrets_manager import SecretsManager, APIKeyManager
from src.core.async_client import AsyncHTTPClient, AsyncCache
from src.core.base_service import ServiceRegistry, ServiceConfig
from src.backtesting.backtesting_engine import BacktestingEngine, BacktestConfig, BacktestMode


# ============================================================================
# Test Configuration
# ============================================================================

def pytest_configure(config):
    """Pytest 설정"""
    # 커스텀 마커 등록
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "async_test: Async tests")
    config.addinivalue_line("markers", "slow: Slow tests")
    config.addinivalue_line("markers", "network: Tests requiring network access")


def pytest_collection_modifyitems(config, items):
    """테스트 아이템 수정 (마커 자동 추가 등)"""
    for item in items:
        # 비동기 테스트 마커 자동 추가
        if asyncio.iscoroutinefunction(item.function):
            item.add_marker(pytest.mark.async_test)
        
        # 네트워크 테스트 식별
        if "network" in item.nodeid or "api" in item.nodeid:
            item.add_marker(pytest.mark.network)


# ============================================================================
# Event Loop Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """세션 범위 이벤트 루프"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def async_client_session():
    """비동기 클라이언트 세션"""
    client = AsyncHTTPClient()
    try:
        yield client
    finally:
        await client.close()


# ============================================================================
# File System Fixtures
# ============================================================================

@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """임시 디렉토리"""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def temp_db_path(temp_dir) -> Generator[str, None, None]:
    """임시 데이터베이스 경로"""
    db_path = temp_dir / "test.db"
    yield str(db_path)
    
    # 정리
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def temp_config_dir(temp_dir) -> Generator[Path, None, None]:
    """임시 설정 디렉토리"""
    config_dir = temp_dir / "config"
    config_dir.mkdir()
    yield config_dir


# ============================================================================
# Security Fixtures
# ============================================================================

@pytest.fixture
def mock_secrets_manager(temp_dir) -> Generator[SecretsManager, None, None]:
    """Mock SecretsManager"""
    secrets_path = temp_dir / "test_secrets"
    
    with patch.dict(os.environ, {'KAIROS_MASTER_KEY': 'test_master_key_12345678901234567890'}):
        manager = SecretsManager(
            master_key='test_master_key_12345678901234567890',
            secrets_path=str(secrets_path)
        )
        yield manager


@pytest.fixture
def mock_api_key_manager(mock_secrets_manager) -> Generator[APIKeyManager, None, None]:
    """Mock APIKeyManager"""
    manager = APIKeyManager(mock_secrets_manager)
    
    # 테스트 데이터 저장
    manager.store_api_key(
        service="coinone",
        api_key="test_api_key",
        secret_key="test_secret_key"
    )
    
    yield manager


# ============================================================================
# Mock Data Fixtures
# ============================================================================

@pytest.fixture
def mock_portfolio_data() -> Dict[str, Any]:
    """Mock 포트폴리오 데이터"""
    return {
        'total_krw': 10000000.0,
        'assets': {
            'KRW': 7000000.0,
            'BTC': 0.05,  # ~2,500,000원
            'ETH': 1.0,   # ~500,000원
        },
        'asset_values': {
            'KRW': 7000000.0,
            'BTC': 2500000.0,
            'ETH': 500000.0,
        },
        'weights': {
            'KRW': 0.7,
            'BTC': 0.25,
            'ETH': 0.05,
        }
    }


@pytest.fixture
def mock_price_data() -> Dict[str, float]:
    """Mock 가격 데이터"""
    return {
        'BTC': 50000000.0,  # 5천만원
        'ETH': 2500000.0,   # 250만원
        'XRP': 600.0,       # 600원
        'SOL': 150000.0,    # 15만원
    }


@pytest.fixture
def mock_trade_history() -> list:
    """Mock 거래 내역"""
    return [
        {
            'timestamp': datetime.now() - timedelta(hours=1),
            'asset': 'BTC',
            'side': 'buy',
            'quantity': 0.01,
            'price': 50000000.0,
            'amount_krw': 500000.0,
            'fee': 500.0,
            'reason': 'rebalance'
        },
        {
            'timestamp': datetime.now() - timedelta(minutes=30),
            'asset': 'ETH',
            'side': 'sell',
            'quantity': 0.1,
            'price': 2500000.0,
            'amount_krw': 250000.0,
            'fee': 250.0,
            'reason': 'rebalance'
        }
    ]


# ============================================================================
# Service Fixtures
# ============================================================================

@pytest.fixture
def mock_service_config() -> ServiceConfig:
    """Mock 서비스 설정"""
    return ServiceConfig(
        name="test_service",
        enabled=True,
        health_check_interval=1  # 짧은 간격으로 설정
    )


@pytest.fixture
def service_registry() -> Generator[ServiceRegistry, None, None]:
    """서비스 레지스트리"""
    registry = ServiceRegistry()
    yield registry
    
    # 정리
    asyncio.create_task(registry.stop_all())


# ============================================================================
# Mock HTTP Fixtures
# ============================================================================

@pytest.fixture
def mock_http_responses() -> Dict[str, Any]:
    """Mock HTTP 응답"""
    return {
        '/api/ticker': {
            'BTC': {
                'last': '50000000',
                'bid': '49950000',
                'ask': '50050000',
                'volume': '100.5'
            },
            'ETH': {
                'last': '2500000',
                'bid': '2495000',
                'ask': '2505000',
                'volume': '1000.0'
            }
        },
        '/api/balance': {
            'KRW': {
                'balance': '7000000',
                'locked': '0'
            },
            'BTC': {
                'balance': '0.05',
                'locked': '0'
            },
            'ETH': {
                'balance': '1.0',
                'locked': '0'
            }
        },
        '/api/order': {
            'order_id': 'test_order_123',
            'status': 'filled',
            'filled_qty': '0.01',
            'filled_amount': '500000'
        }
    }


@pytest.fixture
def mock_aiohttp_client(mock_http_responses):
    """Mock aiohttp 클라이언트"""
    class MockResponse:
        def __init__(self, data, status=200):
            self._data = data
            self.status = status
            self.headers = {}
        
        async def json(self):
            return self._data
        
        async def text(self):
            return str(self._data)
        
        async def __aenter__(self):
            return self
        
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
    
    class MockSession:
        def __init__(self, responses):
            self.responses = responses
            self.closed = False
        
        def request(self, method, url, **kwargs):
            # URL에서 응답 찾기
            for pattern, response in self.responses.items():
                if pattern in url:
                    return MockResponse(response)
            
            return MockResponse({'error': 'Not found'}, 404)
        
        async def close(self):
            self.closed = True
    
    with patch('aiohttp.ClientSession', return_value=MockSession(mock_http_responses)):
        yield


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture
def test_db_connection(temp_db_path):
    """테스트 데이터베이스 연결"""
    conn = sqlite3.connect(temp_db_path)
    
    # 테스트 테이블 생성
    conn.execute("""
        CREATE TABLE IF NOT EXISTS test_table (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            value REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 테스트 데이터 삽입
    conn.execute("INSERT INTO test_table (name, value) VALUES (?, ?)", ("test1", 100.0))
    conn.execute("INSERT INTO test_table (name, value) VALUES (?, ?)", ("test2", 200.0))
    conn.commit()
    
    yield conn
    
    conn.close()


# ============================================================================
# Backtesting Fixtures
# ============================================================================

@pytest.fixture
def backtest_config() -> BacktestConfig:
    """백테스팅 설정"""
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    return BacktestConfig(
        start_date=start_date,
        end_date=end_date,
        initial_capital=1000000.0,  # 100만원
        rebalance_frequency='weekly',
        mode=BacktestMode.SIMPLE,
        risk_level='moderate',
        transaction_cost=0.001
    )


@pytest.fixture
def mock_backtesting_engine(backtest_config):
    """Mock 백테스팅 엔진"""
    engine = BacktestingEngine(backtest_config)
    
    # Mock 데이터 설정
    with patch.object(engine, 'load_historical_data', return_value=True):
        with patch.object(engine, 'historical_data', {
            'BTC': Mock(),
            'ETH': Mock(),
            'XRP': Mock(),
            'SOL': Mock()
        }):
            yield engine


# ============================================================================
# Async Test Fixtures
# ============================================================================

@pytest.fixture
async def async_cache():
    """비동기 캐시"""
    cache = AsyncCache(max_memory_items=100)
    yield cache
    
    # 정리
    cache.clear_cache()


# ============================================================================
# Performance Test Fixtures
# ============================================================================

@pytest.fixture
def performance_timer():
    """성능 측정 타이머"""
    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None
        
        def start(self):
            self.start_time = datetime.now()
        
        def stop(self):
            self.end_time = datetime.now()
        
        @property
        def elapsed(self):
            if self.start_time and self.end_time:
                return (self.end_time - self.start_time).total_seconds()
            return None
        
        def __enter__(self):
            self.start()
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            self.stop()
    
    return Timer()


# ============================================================================
# Exception Test Fixtures
# ============================================================================

@pytest.fixture
def mock_exceptions():
    """Mock 예외 객체들"""
    return {
        'api_timeout': APITimeoutException('test_service', 30),
        'insufficient_balance': InsufficientBalanceException(1000.0, 500.0, 'BTC'),
        'rate_limit': APIRateLimitException('test_service', 60),
        'configuration_error': ConfigurationException('test_key', 'Invalid value'),
    }


# ============================================================================
# Utility Functions for Tests
# ============================================================================

def assert_within_range(actual: float, expected: float, tolerance: float = 0.01):
    """값이 허용 범위 내에 있는지 확인"""
    assert abs(actual - expected) <= tolerance, f"Expected {expected}, got {actual} (tolerance: {tolerance})"


def assert_datetime_close(actual: datetime, expected: datetime, tolerance_seconds: int = 5):
    """두 datetime이 허용 범위 내에 있는지 확인"""
    diff = abs((actual - expected).total_seconds())
    assert diff <= tolerance_seconds, f"Datetime difference too large: {diff} seconds"


async def wait_for_condition(condition_func, timeout: float = 5.0, interval: float = 0.1):
    """조건이 만족될 때까지 대기"""
    start_time = datetime.now()
    
    while (datetime.now() - start_time).total_seconds() < timeout:
        if condition_func():
            return True
        await asyncio.sleep(interval)
    
    return False