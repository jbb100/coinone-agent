"""
Config Factory for KAIROS-1 Trading System

모든 모듈에서 사용하는 기본 설정을 중앙집중화하여 관리합니다.
constants.py의 상수를 기반으로 일관된 설정을 제공합니다.

Usage:
    from src.utils.config_factory import get_default_rebalancer_config
    config = get_default_rebalancer_config()
"""

from typing import Dict, Any

from .constants import (
    # Trading
    REBALANCE_THRESHOLD, MAX_SLIPPAGE, ORDER_TIMEOUT_SECONDS,
    SAFETY_MARGIN, MIN_TRADE_AMOUNT_KRW, MAX_RETRIES,
    # Risk
    MAX_POSITION_SIZE, MAX_DAILY_LOSS_THRESHOLD,
    # Portfolio
    CORE_WEIGHT, SATELLITE_WEIGHT, DEFAULT_CRYPTO_ALLOCATION,
    # Supported assets
    SUPPORTED_CRYPTOCURRENCIES, CORE_ASSETS, SATELLITE_ASSETS
)


def get_default_rebalancer_config() -> Dict[str, Any]:
    """
    기본 리밸런싱 설정

    constants.py의 상수를 기반으로 일관된 설정을 반환합니다.
    테스트와 프로덕션에서 동일한 기본값을 사용합니다.
    """
    return {
        'strategy': {
            'rebalancing': {
                'threshold': REBALANCE_THRESHOLD * 100,  # 1.0 (percent)
                'max_trade_amount': 10_000_000,  # 10M KRW
                'frequency': 'weekly',
                'min_trade_amount': MIN_TRADE_AMOUNT_KRW
            },
            'portfolio': {
                'core': {
                    'BTC': 40,
                    'ETH': 30,
                    'XRP': 15,
                    'SOL': 15
                }
            }
        },
        'risk_management': {
            'max_position_size': MAX_POSITION_SIZE,
            'stop_loss': -0.15,
            'max_slippage': MAX_SLIPPAGE,
            'max_daily_loss': MAX_DAILY_LOSS_THRESHOLD
        },
        'execution': {
            'order_timeout': ORDER_TIMEOUT_SECONDS,
            'retry_attempts': MAX_RETRIES,
            'safety_margin': SAFETY_MARGIN
        }
    }


def get_default_portfolio_config() -> Dict[str, Any]:
    """
    기본 포트폴리오 설정

    constants.py의 상수를 기반으로 일관된 설정을 반환합니다.
    """
    return {
        'strategy': {
            'portfolio': {
                'core': {
                    'BTC': 40,
                    'ETH': 30,
                    'XRP': 15,
                    'SOL': 15
                },
                'core_weight': CORE_WEIGHT,
                'satellite_weight': SATELLITE_WEIGHT
            },
            'rebalancing': {
                'threshold': REBALANCE_THRESHOLD * 100,
                'max_trade_amount': 10_000_000,
                'min_trade_amount': MIN_TRADE_AMOUNT_KRW
            }
        },
        'risk_management': {
            'max_position_size': MAX_POSITION_SIZE,
            'stop_loss': -0.15
        },
        'assets': {
            'supported': SUPPORTED_CRYPTOCURRENCIES,
            'core': CORE_ASSETS,
            'satellite': SATELLITE_ASSETS
        }
    }


def get_default_risk_config() -> Dict[str, Any]:
    """
    기본 리스크 관리 설정
    """
    return {
        'trading_limits': {
            'max_single_trade': 10_000_000,
            'max_daily_volume': 50_000_000,
            'max_position_size': MAX_POSITION_SIZE
        },
        'loss_limits': {
            'max_daily_loss': MAX_DAILY_LOSS_THRESHOLD,
            'max_monthly_loss': 0.15,
            'drawdown_threshold': 0.20
        }
    }


def get_default_execution_config() -> Dict[str, Any]:
    """
    기본 주문 실행 설정
    """
    return {
        'order_timeout': ORDER_TIMEOUT_SECONDS,
        'retry_attempts': MAX_RETRIES,
        'safety_margin': SAFETY_MARGIN,
        'max_slippage': MAX_SLIPPAGE,
        'min_trade_amount': MIN_TRADE_AMOUNT_KRW
    }
