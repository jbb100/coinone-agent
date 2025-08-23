"""
Portfolio Manager Tests

포트폴리오 매니저 핵심 기능 테스트
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import pandas as pd
from decimal import Decimal

from src.core.portfolio_manager import PortfolioManager
from src.core.exceptions import *
from src.trading.coinone_client import CoinoneClient


@pytest.mark.portfolio
class TestPortfolioManager:
    """PortfolioManager 핵심 기능 테스트"""
    
    @pytest.fixture
    def mock_config(self):
        """Mock 설정"""
        return {
            'portfolio': {
                'target_weights': {
                    'BTC': 0.4,
                    'ETH': 0.3,
                    'KRW': 0.3
                },
                'min_trade_amount': 10000,
                'rebalance_threshold': 0.05,
                'max_slippage': 0.01
            },
            'trading': {
                'fee_rate': 0.001,
                'max_order_size': 1000000
            }
        }
    
    @pytest.fixture
    def mock_client(self):
        """Mock Coinone 클라이언트"""
        client = Mock(spec=CoinoneClient)
        client.get_balance = AsyncMock(return_value={
            'KRW': {'balance': '1000000', 'locked': '0'},
            'BTC': {'balance': '0.02', 'locked': '0'},
            'ETH': {'balance': '0.5', 'locked': '0'}
        })
        client.get_ticker = AsyncMock(return_value={
            'BTC': {'last': '50000000'},
            'ETH': {'last': '2500000'}
        })
        client.create_order = AsyncMock(return_value={
            'order_id': 'test_order_123',
            'status': 'filled',
            'filled_qty': '0.01',
            'filled_amount': '500000'
        })
        return client
    
    @pytest.fixture
    def portfolio_manager(self, mock_config, mock_client):
        """PortfolioManager 인스턴스"""
        from src.core.portfolio_manager import AssetAllocation
        allocation = AssetAllocation(
            btc_weight=mock_config['portfolio']['target_weights']['BTC'],
            eth_weight=mock_config['portfolio']['target_weights']['ETH'],
            xrp_weight=0.15,  # Fix: Add XRP weight to make sum = 1.0
            sol_weight=0.15   # Fix: Add SOL weight to make sum = 1.0
        )
        manager = PortfolioManager(
            asset_allocation=allocation,
            coinone_client=mock_client
        )
        return manager
    
    def test_initialization(self, portfolio_manager):
        """초기화 테스트"""
        assert portfolio_manager is not None
        assert hasattr(portfolio_manager, 'coinone_client')
        assert hasattr(portfolio_manager, 'asset_allocation')
    
    @pytest.mark.asyncio
    async def test_get_portfolio_status(self, portfolio_manager):
        """포트폴리오 현황 조회 테스트"""
        status = await portfolio_manager.get_portfolio_status()
        
        assert status is not None
        assert 'total_value' in status
        assert 'assets' in status
        assert 'weights' in status
        assert status['total_value'] > 0
    
    @pytest.mark.asyncio
    async def test_calculate_target_amounts(self, portfolio_manager):
        """목표 금액 계산 테스트"""
        portfolio_value = 3000000  # 300만원
        target_amounts = portfolio_manager.calculate_target_amounts(portfolio_value)
        
        assert target_amounts['BTC'] == 1200000  # 40%
        assert target_amounts['ETH'] == 900000   # 30%
        assert target_amounts['KRW'] == 900000   # 30%
    
    def test_calculate_rebalance_trades(self, portfolio_manager):
        """리밸런싱 거래 계산 테스트"""
        current_weights = {'BTC': 0.5, 'ETH': 0.2, 'KRW': 0.3}
        target_weights = {'BTC': 0.4, 'ETH': 0.3, 'KRW': 0.3}
        portfolio_value = 3000000
        
        trades = portfolio_manager.calculate_rebalance_trades(
            current_weights, target_weights, portfolio_value
        )
        
        # BTC는 10% 감소 (매도)
        # ETH는 10% 증가 (매수)
        assert any(trade['action'] == 'sell' and trade['asset'] == 'BTC' for trade in trades)
        assert any(trade['action'] == 'buy' and trade['asset'] == 'ETH' for trade in trades)
    
    def test_should_rebalance(self, portfolio_manager):
        """리밸런싱 필요성 판단 테스트"""
        # 임계값을 초과하는 경우
        current_weights = {'BTC': 0.5, 'ETH': 0.2, 'KRW': 0.3}
        target_weights = {'BTC': 0.4, 'ETH': 0.3, 'KRW': 0.3}
        
        should_rebalance = portfolio_manager.should_rebalance(current_weights, target_weights)
        assert should_rebalance is True
        
        # 임계값 이하인 경우
        current_weights = {'BTC': 0.41, 'ETH': 0.29, 'KRW': 0.3}
        should_rebalance = portfolio_manager.should_rebalance(current_weights, target_weights)
        assert should_rebalance is False
    
    @pytest.mark.asyncio
    async def test_execute_trade(self, portfolio_manager, mock_client):
        """거래 실행 테스트"""
        trade = {
            'asset': 'BTC',
            'action': 'buy',
            'amount': 500000,
            'quantity': 0.01
        }
        
        result = await portfolio_manager.execute_trade(trade)
        
        assert result is not None
        assert result['status'] == 'filled'
        mock_client.create_order.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_rebalancing(self, portfolio_manager, mock_client):
        """리밸런싱 실행 테스트"""
        with patch.object(portfolio_manager, 'should_rebalance', return_value=True):
            with patch.object(portfolio_manager, 'calculate_rebalance_trades', 
                            return_value=[{
                                'asset': 'BTC',
                                'action': 'sell',
                                'amount': 100000,
                                'quantity': 0.002
                            }]):
                results = await portfolio_manager.execute_rebalancing()
                
                assert results['success'] is True
                assert len(results['trades']) > 0
                assert results['trades_executed'] > 0
    
    def test_validate_trade(self, portfolio_manager):
        """거래 유효성 검증 테스트"""
        # 유효한 거래
        valid_trade = {
            'asset': 'BTC',
            'action': 'buy',
            'amount': 50000,
            'quantity': 0.001
        }
        assert portfolio_manager.validate_trade(valid_trade) is True
        
        # 최소 거래 금액 미달
        invalid_trade = {
            'asset': 'BTC',
            'action': 'buy',
            'amount': 5000,  # 최소 금액 미달
            'quantity': 0.0001
        }
        assert portfolio_manager.validate_trade(invalid_trade) is False
    
    @pytest.mark.asyncio
    async def test_get_asset_allocation(self, portfolio_manager):
        """자산 배분 조회 테스트"""
        allocation = await portfolio_manager.get_asset_allocation()
        
        assert isinstance(allocation, dict)
        assert sum(allocation.values()) == pytest.approx(1.0, rel=1e-2)
        assert all(0 <= weight <= 1 for weight in allocation.values())
    
    def test_calculate_portfolio_metrics(self, portfolio_manager):
        """포트폴리오 지표 계산 테스트"""
        portfolio_history = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=30, freq='D'),
            'total_value': [1000000 + i * 10000 for i in range(30)],
            'BTC_weight': [0.4 + (i % 5) * 0.01 for i in range(30)],
            'ETH_weight': [0.3 + (i % 3) * 0.01 for i in range(30)]
        })
        
        metrics = portfolio_manager.calculate_portfolio_metrics(portfolio_history)
        
        assert 'total_return' in metrics
        assert 'volatility' in metrics
        assert 'max_drawdown' in metrics
        assert 'sharpe_ratio' in metrics
        assert isinstance(metrics['total_return'], float)
    
    @pytest.mark.asyncio
    async def test_error_handling(self, portfolio_manager, mock_client):
        """오류 처리 테스트"""
        # API 오류 시뮬레이션
        mock_client.get_balance.side_effect = Exception("API Error")
        
        # get_portfolio_status returns error dict instead of raising exception
        result = await portfolio_manager.get_portfolio_status()
        assert 'error' in result
        assert "API Error" in result['error']
    
    @pytest.mark.asyncio
    async def test_risk_management(self, portfolio_manager):
        """리스크 관리 테스트"""
        # 과도한 집중 위험
        high_concentration_weights = {'BTC': 0.9, 'ETH': 0.05, 'KRW': 0.05}
        risk_level = portfolio_manager.assess_concentration_risk(high_concentration_weights)
        assert risk_level == 'HIGH'
        
        # 균형잡힌 포트폴리오
        balanced_weights = {'BTC': 0.4, 'ETH': 0.3, 'KRW': 0.3}
        risk_level = portfolio_manager.assess_concentration_risk(balanced_weights)
        assert risk_level == 'LOW'


@pytest.mark.portfolio
class TestPortfolioManagerIntegration:
    """PortfolioManager 통합 테스트"""
    
    @pytest.mark.asyncio
    async def test_full_rebalancing_workflow(self):
        """전체 리밸런싱 워크플로우 테스트"""
        mock_client = Mock(spec=CoinoneClient)
        mock_client.get_balance = AsyncMock(return_value={
            'KRW': {'balance': '500000', 'locked': '0'},
            'BTC': {'balance': '0.03', 'locked': '0'},  # 150만원 상당
            'ETH': {'balance': '0.6', 'locked': '0'}    # 150만원 상당
        })
        mock_client.get_ticker = AsyncMock(return_value={
            'BTC': {'last': '50000000'},
            'ETH': {'last': '2500000'}
        })
        mock_client.create_order = AsyncMock(return_value={
            'order_id': 'test_order',
            'status': 'filled',
            'filled_qty': '0.01',
            'filled_amount': '500000'
        })
        
        config = {
            'portfolio': {
                'target_weights': {'BTC': 0.4, 'ETH': 0.3, 'KRW': 0.3},
                'rebalance_threshold': 0.05,
                'min_trade_amount': 10000
            }
        }
        
        with patch('src.core.portfolio_manager.load_config', return_value=config):
            manager = PortfolioManager(coinone_client=mock_client)
            
            # 1. 현재 상태 확인
            status = await manager.get_portfolio_status()
            assert status['total_value'] > 0
            
            # 2. 리밸런싱 실행
            results = await manager.execute_rebalancing()
            
            # 3. 결과 검증
            assert isinstance(results, dict)
            assert 'success' in results
            assert results['success'] is True
    
    @pytest.mark.asyncio 
    async def test_portfolio_performance_tracking(self):
        """포트폴리오 성과 추적 테스트"""
        mock_client = Mock(spec=CoinoneClient)
        mock_client.get_balance = AsyncMock(return_value={
            'KRW': {'balance': '1000000', 'locked': '0'},
            'BTC': {'balance': '0.02', 'locked': '0'},
            'ETH': {'balance': '0.4', 'locked': '0'}
        })
        mock_client.get_ticker = AsyncMock(return_value={
            'BTC': {'last': '50000000'},
            'ETH': {'last': '2500000'}
        })
        
        config = {
            'portfolio': {
                'target_weights': {'BTC': 0.4, 'ETH': 0.3, 'KRW': 0.3},
                'rebalance_threshold': 0.05
            }
        }
        
        with patch('src.core.portfolio_manager.load_config', return_value=config):
            manager = PortfolioManager(coinone_client=mock_client)
            
            # 여러 시점의 포트폴리오 상태 시뮬레이션
            portfolio_snapshots = []
            for i in range(5):
                # 가격 변동 시뮬레이션
                mock_client.get_ticker.return_value = {
                    'BTC': {'last': str(50000000 + i * 1000000)},
                    'ETH': {'last': str(2500000 + i * 50000)}
                }
                
                status = await manager.get_portfolio_status()
                portfolio_snapshots.append(status)
            
            # 성과 지표 계산
            assert len(portfolio_snapshots) == 5
            assert all('total_value' in snapshot for snapshot in portfolio_snapshots)