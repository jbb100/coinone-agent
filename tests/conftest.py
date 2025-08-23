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
    config.addinivalue_line("markers", "security: Security-related tests")
    config.addinivalue_line("markers", "trading: Trading logic tests")
    config.addinivalue_line("markers", "portfolio: Portfolio management tests")
    config.addinivalue_line("markers", "rebalancing: Rebalancing tests")
    config.addinivalue_line("markers", "multi_account: Multi-account system tests")


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
def mock_service_config():
    """Mock 서비스 설정"""
    return {
        "name": "test_service",
        "enabled": True,
        "health_check_interval": 1  # 짧은 간격으로 설정
    }


@pytest.fixture
def service_registry():
    """서비스 레지스트리"""
    registry = Mock()
    return registry


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


# ============================================================================
# Enhanced Mock Fixtures for Trading System
# ============================================================================

@pytest.fixture
def mock_coinone_client():
    """개선된 Mock Coinone 클라이언트"""
    client = Mock()
    
    # 기본 잔고 응답
    client.get_balance = AsyncMock(return_value={
        'KRW': {'balance': '5000000', 'locked': '0'},
        'BTC': {'balance': '0.1', 'locked': '0'},
        'ETH': {'balance': '2.0', 'locked': '0'},
        'XRP': {'balance': '1000', 'locked': '0'}
    })
    
    # 기본 시세 응답
    client.get_ticker = AsyncMock(return_value={
        'BTC': {'last': '50000000', 'bid': '49950000', 'ask': '50050000'},
        'ETH': {'last': '2500000', 'bid': '2495000', 'ask': '2505000'},
        'XRP': {'last': '600', 'bid': '598', 'ask': '602'}
    })
    
    # 주문 성공 응답
    client.create_order = AsyncMock(return_value={
        'order_id': 'test_order_12345',
        'status': 'filled',
        'filled_qty': '0.01',
        'filled_amount': '500000',
        'fee': '500'
    })
    
    # 주문 조회
    client.get_order = AsyncMock(return_value={
        'order_id': 'test_order_12345',
        'status': 'filled',
        'side': 'buy',
        'asset': 'BTC',
        'quantity': '0.01',
        'price': '50000000'
    })
    
    return client


@pytest.fixture
def realistic_market_data():
    """현실적인 시장 데이터"""
    return {
        'prices': {
            'BTC': {
                'current': 50000000,
                'high_24h': 52000000,
                'low_24h': 48000000,
                'volume_24h': 1500.5,
                'change_24h': 0.02
            },
            'ETH': {
                'current': 2500000,
                'high_24h': 2600000,
                'low_24h': 2400000,
                'volume_24h': 5000.0,
                'change_24h': 0.04
            },
            'XRP': {
                'current': 600,
                'high_24h': 620,
                'low_24h': 580,
                'volume_24h': 100000.0,
                'change_24h': -0.01
            }
        },
        'timestamps': {
            'last_update': datetime.now(),
            'market_open': datetime.now().replace(hour=9, minute=0, second=0),
            'market_close': datetime.now().replace(hour=18, minute=0, second=0)
        }
    }


@pytest.fixture
def portfolio_scenarios():
    """다양한 포트폴리오 시나리오"""
    return {
        'balanced': {
            'total_value': 10000000,
            'allocation': {'BTC': 0.4, 'ETH': 0.3, 'XRP': 0.2, 'KRW': 0.1}
        },
        'crypto_heavy': {
            'total_value': 15000000,
            'allocation': {'BTC': 0.6, 'ETH': 0.25, 'XRP': 0.1, 'KRW': 0.05}
        },
        'conservative': {
            'total_value': 8000000,
            'allocation': {'BTC': 0.2, 'ETH': 0.1, 'KRW': 0.7}
        },
        'small_portfolio': {
            'total_value': 1000000,
            'allocation': {'BTC': 0.3, 'KRW': 0.7}
        }
    }


@pytest.fixture
def trading_scenarios():
    """거래 시나리오 데이터"""
    return {
        'successful_buy': {
            'asset': 'BTC',
            'action': 'buy',
            'amount': 1000000,
            'expected_quantity': 0.02,
            'expected_fee': 1000,
            'expected_status': 'filled'
        },
        'successful_sell': {
            'asset': 'ETH',
            'action': 'sell',
            'amount': 500000,
            'expected_quantity': 0.2,
            'expected_fee': 500,
            'expected_status': 'filled'
        },
        'partial_fill': {
            'asset': 'XRP',
            'action': 'buy',
            'amount': 300000,
            'filled_ratio': 0.7,
            'expected_status': 'partially_filled'
        },
        'failed_insufficient_balance': {
            'asset': 'BTC',
            'action': 'buy',
            'amount': 100000000,  # 잔고 부족
            'expected_error': 'InsufficientBalanceException'
        }
    }


@pytest.fixture
def rebalancing_scenarios():
    """리밸런싱 시나리오"""
    return {
        'minor_rebalancing': {
            'current_weights': {'BTC': 0.42, 'ETH': 0.28, 'KRW': 0.3},
            'target_weights': {'BTC': 0.4, 'ETH': 0.3, 'KRW': 0.3},
            'threshold': 0.05,
            'should_rebalance': False
        },
        'major_rebalancing': {
            'current_weights': {'BTC': 0.6, 'ETH': 0.1, 'KRW': 0.3},
            'target_weights': {'BTC': 0.4, 'ETH': 0.3, 'KRW': 0.3},
            'threshold': 0.05,
            'should_rebalance': True,
            'expected_trades': [
                {'asset': 'BTC', 'action': 'sell'},
                {'asset': 'ETH', 'action': 'buy'}
            ]
        }
    }


@pytest.fixture
def mock_market_conditions():
    """시장 상황별 Mock 데이터 생성기"""
    def generate_market_data(condition='normal', volatility=0.02):
        base_prices = {'BTC': 50000000, 'ETH': 2500000, 'XRP': 600}
        
        if condition == 'bull':
            multipliers = {'BTC': 1.1, 'ETH': 1.15, 'XRP': 1.2}
        elif condition == 'bear':
            multipliers = {'BTC': 0.9, 'ETH': 0.85, 'XRP': 0.8}
        else:  # normal
            multipliers = {'BTC': 1.0, 'ETH': 1.0, 'XRP': 1.0}
        
        return {
            asset: {
                'last': str(int(base_prices[asset] * multipliers[asset])),
                'change_24h': (multipliers[asset] - 1.0)
            }
            for asset in base_prices
        }
    
    return generate_market_data


@pytest.fixture
async def integration_test_environment(temp_dir, mock_coinone_client):
    """통합 테스트를 위한 완전한 환경 설정"""
    # 테스트용 설정 파일 생성
    config_data = {
        'portfolio': {
            'target_weights': {'BTC': 0.4, 'ETH': 0.3, 'KRW': 0.3},
            'rebalance_threshold': 0.05,
            'min_trade_amount': 10000
        },
        'trading': {
            'fee_rate': 0.001,
            'max_order_size': 10000000,
            'slippage_tolerance': 0.005
        },
        'risk': {
            'max_position_size': 0.5,
            'max_daily_trades': 10
        }
    }
    
    config_file = temp_dir / "test_config.yaml"
    import yaml
    with open(config_file, 'w') as f:
        yaml.dump(config_data, f)
    
    # 테스트용 계정 데이터
    accounts_data = {
        "accounts": [
            {
                "id": "test_account_1",
                "name": "Test Account 1",
                "strategy": "balanced",
                "target_allocation": {"BTC": 0.4, "ETH": 0.3, "KRW": 0.3},
                "risk_level": "medium"
            }
        ]
    }
    
    accounts_file = temp_dir / "test_accounts.json"
    import json
    with open(accounts_file, 'w') as f:
        json.dump(accounts_data, f)
    
    # 환경 반환
    return {
        'config_file': str(config_file),
        'accounts_file': str(accounts_file),
        'client': mock_coinone_client,
        'temp_dir': temp_dir
    }


@pytest.fixture
def error_simulation():
    """다양한 오류 상황 시뮬레이션"""
    def simulate_error(error_type, **kwargs):
        if error_type == 'network_timeout':
            return asyncio.TimeoutError("Network timeout")
        elif error_type == 'api_error':
            return Exception(f"API Error: {kwargs.get('message', 'Unknown error')}")
        elif error_type == 'rate_limit':
            return APIRateLimitException("coinone", kwargs.get('retry_after', 60))
        elif error_type == 'insufficient_balance':
            return InsufficientBalanceException(
                kwargs.get('requested', 1000000),
                kwargs.get('available', 500000),
                kwargs.get('asset', 'KRW')
            )
        else:
            return Exception("Unknown error type")
    
    return simulate_error


# ============================================================================
# Performance Test Fixtures
# ============================================================================

@pytest.fixture
def performance_benchmarks():
    """성능 벤치마크 기준값들"""
    return {
        'portfolio_status_query': {'max_time': 1.0, 'target_time': 0.5},
        'rebalancing_analysis': {'max_time': 2.0, 'target_time': 1.0},
        'trade_execution': {'max_time': 5.0, 'target_time': 3.0},
        'multi_account_sync': {'max_time': 10.0, 'target_time': 5.0}
    }


@pytest.fixture
def load_test_scenarios():
    """부하 테스트 시나리오"""
    return {
        'light_load': {
            'concurrent_requests': 5,
            'request_rate': 10,  # per second
            'duration': 30  # seconds
        },
        'medium_load': {
            'concurrent_requests': 20,
            'request_rate': 50,
            'duration': 60
        },
        'heavy_load': {
            'concurrent_requests': 100,
            'request_rate': 200,
            'duration': 120
        }
    }