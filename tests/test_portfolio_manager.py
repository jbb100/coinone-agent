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


@pytest.mark.portfolio
class TestAssetAllocation:
    """AssetAllocation 데이터클래스 테스트"""

    def test_default_allocation(self):
        """기본 자산 배분 테스트"""
        from src.core.portfolio_manager import AssetAllocation

        allocation = AssetAllocation()

        assert allocation.btc_weight == 0.40
        assert allocation.eth_weight == 0.30
        assert allocation.xrp_weight == 0.15
        assert allocation.sol_weight == 0.15

    def test_custom_allocation(self):
        """커스텀 자산 배분 테스트"""
        from src.core.portfolio_manager import AssetAllocation

        allocation = AssetAllocation(
            btc_weight=0.50,
            eth_weight=0.25,
            xrp_weight=0.15,
            sol_weight=0.10
        )

        assert allocation.btc_weight == 0.50
        assert allocation.eth_weight == 0.25
        assert allocation.xrp_weight == 0.15
        assert allocation.sol_weight == 0.10

    def test_get_crypto_weights(self):
        """암호화폐 비중 딕셔너리 반환 테스트"""
        from src.core.portfolio_manager import AssetAllocation

        allocation = AssetAllocation()
        weights = allocation.get_crypto_weights()

        assert isinstance(weights, dict)
        assert weights['BTC'] == 0.40
        assert weights['ETH'] == 0.30
        assert weights['XRP'] == 0.15
        assert weights['SOL'] == 0.15

    def test_validate_weights_valid(self):
        """유효한 비중 검증 테스트"""
        from src.core.portfolio_manager import AssetAllocation

        allocation = AssetAllocation(
            btc_weight=0.40,
            eth_weight=0.30,
            xrp_weight=0.15,
            sol_weight=0.15
        )

        assert allocation.validate_weights() is True

    def test_validate_weights_invalid(self):
        """유효하지 않은 비중 검증 테스트"""
        from src.core.portfolio_manager import AssetAllocation

        allocation = AssetAllocation(
            btc_weight=0.50,
            eth_weight=0.30,
            xrp_weight=0.15,
            sol_weight=0.15  # 합계 1.1
        )

        assert allocation.validate_weights() is False

    def test_validate_weights_tolerance(self):
        """비중 검증 허용 오차 테스트"""
        from src.core.portfolio_manager import AssetAllocation

        # 작은 오차는 허용
        allocation = AssetAllocation(
            btc_weight=0.4001,
            eth_weight=0.30,
            xrp_weight=0.15,
            sol_weight=0.15
        )

        assert allocation.validate_weights() is True


@pytest.mark.portfolio
class TestPortfolioManagerInit:
    """PortfolioManager 초기화 상세 테스트"""

    def test_init_with_default_allocation(self):
        """기본 배분으로 초기화"""
        from src.core.portfolio_manager import PortfolioManager

        manager = PortfolioManager()

        assert manager.asset_allocation is not None
        assert manager.coinone_client is None
        assert manager.use_dynamic_optimization is False

    def test_init_with_invalid_allocation_raises_error(self):
        """유효하지 않은 배분으로 초기화 시 에러"""
        from src.core.portfolio_manager import PortfolioManager, AssetAllocation

        invalid_allocation = AssetAllocation(
            btc_weight=0.50,
            eth_weight=0.50,
            xrp_weight=0.20,
            sol_weight=0.10  # 합계 1.3
        )

        with pytest.raises(ValueError, match="100%"):
            PortfolioManager(asset_allocation=invalid_allocation)

    def test_core_satellite_configuration(self):
        """Core/Satellite 구성 확인"""
        from src.core.portfolio_manager import PortfolioManager

        manager = PortfolioManager()

        assert manager.core_assets == ["BTC", "ETH"]
        assert manager.satellite_assets == ["XRP", "SOL"]
        assert manager.core_weight == 0.70
        assert manager.satellite_weight == 0.30

    def test_init_with_dynamic_optimization_no_client(self):
        """클라이언트 없이 동적 최적화 활성화"""
        from src.core.portfolio_manager import PortfolioManager

        manager = PortfolioManager(use_dynamic_optimization=True)

        # 클라이언트 없으면 동적 최적화가 비활성화됨
        assert manager.dynamic_optimizer is None


@pytest.mark.portfolio
class TestCalculateTargetWeights:
    """목표 비중 계산 테스트"""

    @pytest.fixture
    def manager(self):
        from src.core.portfolio_manager import PortfolioManager
        return PortfolioManager()

    def test_calculate_target_weights_70_30(self, manager):
        """70% 암호화폐 / 30% 원화 비중"""
        weights = manager.calculate_target_weights(0.7, 0.3)

        assert weights['KRW'] == 0.3
        assert weights['BTC'] == 0.7 * 0.40  # 0.28
        assert weights['ETH'] == 0.7 * 0.30  # 0.21
        assert weights['XRP'] == 0.7 * 0.15  # 0.105
        assert weights['SOL'] == 0.7 * 0.15  # 0.105

        # 총합 검증
        assert sum(weights.values()) == pytest.approx(1.0, rel=1e-3)

    def test_calculate_target_weights_30_70(self, manager):
        """30% 암호화폐 / 70% 원화 비중"""
        weights = manager.calculate_target_weights(0.3, 0.7)

        assert weights['KRW'] == 0.7
        assert weights['BTC'] == 0.3 * 0.40  # 0.12
        assert weights['ETH'] == 0.3 * 0.30  # 0.09

    def test_calculate_target_weights_invalid_sum_raises_error(self, manager):
        """비중 합이 100%가 아닌 경우"""
        with pytest.raises(ValueError, match="100%"):
            manager.calculate_target_weights(0.5, 0.3)  # 합계 0.8


@pytest.mark.portfolio
class TestGetCurrentWeights:
    """현재 비중 계산 테스트"""

    @pytest.fixture
    def manager(self):
        from src.core.portfolio_manager import PortfolioManager
        return PortfolioManager()

    def test_get_current_weights_valid(self, manager):
        """유효한 포트폴리오에서 현재 비중"""
        portfolio = {
            "total_krw": 1000000,
            "assets": {
                "KRW": {"value_krw": 300000},
                "BTC": {"value_krw": 400000},
                "ETH": {"value_krw": 200000},
                "XRP": {"value_krw": 50000},
                "SOL": {"value_krw": 50000}
            }
        }

        weights = manager.get_current_weights(portfolio)

        assert weights['KRW'] == pytest.approx(0.3, rel=1e-3)
        assert weights['BTC'] == pytest.approx(0.4, rel=1e-3)
        assert weights['ETH'] == pytest.approx(0.2, rel=1e-3)

    def test_get_current_weights_zero_total(self, manager):
        """총 가치가 0인 경우"""
        portfolio = {
            "total_krw": 0,
            "assets": {}
        }

        weights = manager.get_current_weights(portfolio)

        assert weights == {}

    def test_get_current_weights_negative_total(self, manager):
        """총 가치가 음수인 경우"""
        portfolio = {
            "total_krw": -1000,
            "assets": {}
        }

        weights = manager.get_current_weights(portfolio)

        assert weights == {}

    def test_get_current_weights_numeric_values(self, manager):
        """숫자 형태 자산 값"""
        portfolio = {
            "total_krw": 1000000,
            "assets": {
                "KRW": 300000,
                "BTC": 400000,
                "ETH": 200000,
                "XRP": 50000,
                "SOL": 50000
            }
        }

        weights = manager.get_current_weights(portfolio)

        assert weights['KRW'] == pytest.approx(0.3, rel=1e-3)
        assert weights['BTC'] == pytest.approx(0.4, rel=1e-3)


@pytest.mark.portfolio
class TestCalculateRebalanceAmounts:
    """리밸런싱 금액 계산 테스트"""

    @pytest.fixture
    def manager(self):
        from src.core.portfolio_manager import PortfolioManager
        return PortfolioManager()

    def test_calculate_rebalance_amounts_buy_needed(self, manager):
        """매수가 필요한 경우"""
        current_portfolio = {
            "total_krw": 1000000,
            "assets": {
                "KRW": {"value_krw": 500000},  # 50%
                "BTC": {"value_krw": 300000},  # 30%
                "ETH": {"value_krw": 100000},  # 10%
                "XRP": {"value_krw": 50000},   # 5%
                "SOL": {"value_krw": 50000}    # 5%
            }
        }

        target_weights = {
            "KRW": 0.3,
            "BTC": 0.40,
            "ETH": 0.20,
            "XRP": 0.05,
            "SOL": 0.05
        }

        result = manager.calculate_rebalance_amounts(current_portfolio, target_weights)

        assert result['total_value_krw'] == 1000000
        assert 'rebalance_orders' in result
        assert 'summary' in result

    def test_calculate_rebalance_amounts_sell_needed(self, manager):
        """매도가 필요한 경우"""
        current_portfolio = {
            "total_krw": 1000000,
            "assets": {
                "KRW": {"value_krw": 100000},  # 10%
                "BTC": {"value_krw": 600000},  # 60% - 과다
                "ETH": {"value_krw": 200000},  # 20%
                "XRP": {"value_krw": 50000},
                "SOL": {"value_krw": 50000}
            }
        }

        target_weights = {
            "KRW": 0.3,
            "BTC": 0.40,
            "ETH": 0.20,
            "XRP": 0.05,
            "SOL": 0.05
        }

        result = manager.calculate_rebalance_amounts(current_portfolio, target_weights)

        # KRW 매수 필요
        if 'KRW' in result['rebalance_orders']:
            assert result['rebalance_orders']['KRW']['action'] == 'buy'


@pytest.mark.portfolio
class TestRebalancePriority:
    """리밸런싱 우선순위 테스트"""

    @pytest.fixture
    def manager(self):
        from src.core.portfolio_manager import PortfolioManager
        return PortfolioManager()

    def test_get_rebalance_priority_krw(self, manager):
        """KRW 우선순위"""
        priority = manager._get_rebalance_priority("KRW")
        assert priority == 1

    def test_get_rebalance_priority_btc(self, manager):
        """BTC 우선순위"""
        priority = manager._get_rebalance_priority("BTC")
        assert priority == 2

    def test_get_rebalance_priority_eth(self, manager):
        """ETH 우선순위"""
        priority = manager._get_rebalance_priority("ETH")
        assert priority == 3

    def test_get_rebalance_priority_satellite(self, manager):
        """Satellite 자산 우선순위"""
        assert manager._get_rebalance_priority("XRP") == 4
        assert manager._get_rebalance_priority("SOL") == 5

    def test_get_rebalance_priority_unknown(self, manager):
        """알 수 없는 자산 우선순위"""
        priority = manager._get_rebalance_priority("UNKNOWN")
        assert priority == 999


@pytest.mark.portfolio
class TestValidateRebalanceFeasibility:
    """리밸런싱 실행 가능성 검증 테스트"""

    @pytest.fixture
    def manager(self):
        from src.core.portfolio_manager import PortfolioManager
        return PortfolioManager()

    def test_validate_sufficient_amount(self, manager):
        """충분한 금액"""
        rebalance_info = {
            "rebalance_orders": {
                "BTC": {"amount_diff_krw": 50000},
                "ETH": {"amount_diff_krw": -30000}
            }
        }

        results = manager.validate_rebalance_feasibility(rebalance_info, min_trade_amount=10000)

        assert results['BTC'] is True
        assert results['ETH'] is True

    def test_validate_insufficient_amount(self, manager):
        """불충분한 금액"""
        rebalance_info = {
            "rebalance_orders": {
                "BTC": {"amount_diff_krw": 5000},  # 최소 미달
                "ETH": {"amount_diff_krw": -3000}  # 최소 미달
            }
        }

        results = manager.validate_rebalance_feasibility(rebalance_info, min_trade_amount=10000)

        assert results['BTC'] is False
        assert results['ETH'] is False


@pytest.mark.portfolio
class TestGetOptimalPortfolioWeights:
    """최적 포트폴리오 비중 조회 테스트"""

    @pytest.fixture
    def manager(self):
        from src.core.portfolio_manager import PortfolioManager
        return PortfolioManager(use_dynamic_optimization=False)

    def test_get_optimal_weights_no_optimization(self, manager):
        """동적 최적화 비활성화 시"""
        weights = manager.get_optimal_portfolio_weights()

        assert weights['BTC'] == 0.40
        assert weights['ETH'] == 0.30
        assert weights['XRP'] == 0.15
        assert weights['SOL'] == 0.15


@pytest.mark.portfolio
class TestShouldRebalancePortfolio:
    """포트폴리오 리밸런싱 필요 여부 판단 테스트"""

    @pytest.fixture
    def manager(self):
        from src.core.portfolio_manager import PortfolioManager
        return PortfolioManager()

    def test_should_rebalance_exceeds_threshold(self, manager):
        """임계값 초과 시 리밸런싱 필요"""
        current_portfolio = {
            "total_krw": 1000000,
            "assets": {
                "KRW": {"value_krw": 300000},
                "BTC": {"value_krw": 500000},  # 50% - 목표 대비 10% 초과
                "ETH": {"value_krw": 100000},
                "XRP": {"value_krw": 50000},
                "SOL": {"value_krw": 50000}
            }
        }

        needs_rebalancing, info = manager.should_rebalance_portfolio(current_portfolio, rebalance_threshold=0.05)

        assert needs_rebalancing is True
        assert info['max_deviation'] > 0.05

    def test_should_not_rebalance_within_threshold(self, manager):
        """임계값 이내 시 리밸런싱 불필요"""
        # 최적 비중: BTC 40%, ETH 30%, XRP 15%, SOL 15%
        # 모든 자산이 5% 임계값 이내여야 함
        current_portfolio = {
            "total_krw": 1000000,
            "assets": {
                "KRW": {"value_krw": 0},
                "BTC": {"value_krw": 420000},  # 42% - 목표 40% 대비 2% 차이
                "ETH": {"value_krw": 280000},  # 28% - 목표 30% 대비 2% 차이
                "XRP": {"value_krw": 160000},  # 16% - 목표 15% 대비 1% 차이
                "SOL": {"value_krw": 140000}   # 14% - 목표 15% 대비 1% 차이
            }
        }

        needs_rebalancing, info = manager.should_rebalance_portfolio(current_portfolio, rebalance_threshold=0.05)

        assert needs_rebalancing is False
        assert info['max_deviation'] < 0.05


@pytest.mark.portfolio
class TestCalculateDynamicTargetWeights:
    """동적 목표 비중 계산 테스트"""

    @pytest.fixture
    def manager(self):
        from src.core.portfolio_manager import PortfolioManager
        return PortfolioManager(use_dynamic_optimization=False)

    def test_calculate_dynamic_target_weights_basic(self, manager):
        """기본 동적 목표 비중 계산"""
        weights = manager.calculate_dynamic_target_weights(0.7, 0.3, use_optimization=False)

        assert weights['KRW'] == 0.3
        assert weights['BTC'] == pytest.approx(0.28, rel=1e-2)
        assert weights['ETH'] == pytest.approx(0.21, rel=1e-2)

    def test_calculate_dynamic_target_weights_invalid_sum(self, manager):
        """유효하지 않은 비중 합계"""
        # 오류 시 기본 방식으로 폴백
        with pytest.raises(ValueError):
            manager.calculate_dynamic_target_weights(0.5, 0.3)


@pytest.mark.portfolio
class TestGetPortfolioOptimizationStatus:
    """포트폴리오 최적화 상태 조회 테스트"""

    @pytest.fixture
    def manager(self):
        from src.core.portfolio_manager import PortfolioManager
        return PortfolioManager()

    def test_get_status_initial(self, manager):
        """초기 상태 조회"""
        status = manager.get_portfolio_optimization_status()

        assert status['dynamic_optimization_enabled'] is False
        assert status['optimizer_available'] is False
        assert status['last_optimization_time'] is None
        assert status['cache_available'] is False


@pytest.mark.portfolio
class TestForcePortfolioOptimization:
    """포트폴리오 강제 최적화 테스트"""

    @pytest.fixture
    def manager(self):
        from src.core.portfolio_manager import PortfolioManager
        return PortfolioManager(use_dynamic_optimization=False)

    def test_force_optimization_without_enabled_raises_error(self, manager):
        """동적 최적화 미활성화 상태에서 강제 최적화"""
        with pytest.raises(ValueError, match="활성화되지 않았습니다"):
            manager.force_portfolio_optimization()


@pytest.mark.portfolio
class TestGetPortfolioMetrics:
    """포트폴리오 메트릭 계산 테스트"""

    @pytest.fixture
    def manager(self):
        from src.core.portfolio_manager import PortfolioManager
        return PortfolioManager()

    def test_get_portfolio_metrics(self, manager):
        """포트폴리오 메트릭 계산"""
        current_portfolio = {
            "total_krw": 1000000,
            "assets": {
                "KRW": {"value_krw": 300000},
                "BTC": {"value_krw": 400000},
                "ETH": {"value_krw": 200000},
                "XRP": {"value_krw": 50000},
                "SOL": {"value_krw": 50000}
            }
        }

        metrics = manager.get_portfolio_metrics(current_portfolio)

        assert metrics['total_value_krw'] == 1000000
        assert 'weights' in metrics
        assert metrics['weights']['crypto_total'] == pytest.approx(0.7, rel=1e-2)
        assert metrics['weights']['krw'] == pytest.approx(0.3, rel=1e-2)
        assert 'portfolio_health' in metrics

    def test_get_portfolio_metrics_with_zero_satellite(self, manager):
        """Satellite 비중이 0인 경우"""
        current_portfolio = {
            "total_krw": 1000000,
            "assets": {
                "KRW": {"value_krw": 300000},
                "BTC": {"value_krw": 500000},
                "ETH": {"value_krw": 200000},
                "XRP": {"value_krw": 0},
                "SOL": {"value_krw": 0}
            }
        }

        metrics = manager.get_portfolio_metrics(current_portfolio)

        assert metrics['portfolio_health']['core_satellite_ratio'] == float('inf')


@pytest.mark.portfolio
class TestCalculateMaxDrawdown:
    """최대 드로다운 계산 테스트"""

    @pytest.fixture
    def manager(self):
        from src.core.portfolio_manager import PortfolioManager
        return PortfolioManager()

    def test_calculate_max_drawdown_with_loss(self, manager):
        """손실이 있는 경우"""
        portfolio_history = [
            {'total_value': 1000000},
            {'total_value': 1100000},  # 피크
            {'total_value': 880000},   # 20% 하락
            {'total_value': 990000}
        ]

        max_dd = manager._calculate_max_drawdown(portfolio_history)

        assert max_dd == pytest.approx(0.2, rel=1e-2)

    def test_calculate_max_drawdown_no_loss(self, manager):
        """손실이 없는 경우 (계속 상승)"""
        portfolio_history = [
            {'total_value': 1000000},
            {'total_value': 1100000},
            {'total_value': 1200000},
            {'total_value': 1300000}
        ]

        max_dd = manager._calculate_max_drawdown(portfolio_history)

        assert max_dd == 0.0

    def test_calculate_max_drawdown_empty(self, manager):
        """빈 히스토리"""
        max_dd = manager._calculate_max_drawdown([])

        assert max_dd == 0.0


@pytest.mark.portfolio
class TestAssessConcentrationRisk:
    """집중 리스크 평가 테스트"""

    @pytest.fixture
    def manager(self):
        from src.core.portfolio_manager import PortfolioManager
        return PortfolioManager()

    def test_high_concentration(self, manager):
        """높은 집중도"""
        weights = {'BTC': 0.7, 'ETH': 0.2, 'KRW': 0.1}

        risk = manager.assess_concentration_risk(weights)

        assert risk == 'HIGH'

    def test_medium_concentration(self, manager):
        """중간 집중도"""
        weights = {'BTC': 0.5, 'ETH': 0.3, 'KRW': 0.2}

        risk = manager.assess_concentration_risk(weights)

        assert risk == 'MEDIUM'

    def test_low_concentration(self, manager):
        """낮은 집중도"""
        weights = {'BTC': 0.35, 'ETH': 0.25, 'XRP': 0.20, 'SOL': 0.20}

        risk = manager.assess_concentration_risk(weights)

        assert risk == 'LOW'

    def test_empty_weights(self, manager):
        """빈 비중"""
        risk = manager.assess_concentration_risk({})

        assert risk == 'LOW'


@pytest.mark.portfolio
class TestValidateTrade:
    """거래 유효성 검증 테스트"""

    @pytest.fixture
    def manager(self):
        from src.core.portfolio_manager import PortfolioManager
        return PortfolioManager()

    def test_validate_trade_valid_with_asset_key(self, manager):
        """유효한 거래 (asset 키 사용)"""
        trade = {
            'asset': 'BTC',
            'action': 'buy',
            'amount': 50000
        }

        assert manager.validate_trade(trade) is True

    def test_validate_trade_valid_with_symbol_key(self, manager):
        """유효한 거래 (symbol 키 사용)"""
        trade = {
            'symbol': 'BTC',
            'side': 'buy',
            'amount_krw': 50000
        }

        assert manager.validate_trade(trade) is True

    def test_validate_trade_missing_asset(self, manager):
        """자산 누락"""
        trade = {
            'action': 'buy',
            'amount': 50000
        }

        assert manager.validate_trade(trade) is False

    def test_validate_trade_missing_action(self, manager):
        """액션 누락"""
        trade = {
            'asset': 'BTC',
            'amount': 50000
        }

        assert manager.validate_trade(trade) is False

    def test_validate_trade_invalid_action(self, manager):
        """유효하지 않은 액션"""
        trade = {
            'asset': 'BTC',
            'action': 'hold',  # Invalid
            'amount': 50000
        }

        assert manager.validate_trade(trade) is False

    def test_validate_trade_zero_amount(self, manager):
        """금액 0"""
        trade = {
            'asset': 'BTC',
            'action': 'buy',
            'amount': 0
        }

        assert manager.validate_trade(trade) is False

    def test_validate_trade_negative_amount(self, manager):
        """음수 금액"""
        trade = {
            'asset': 'BTC',
            'action': 'buy',
            'amount': -50000
        }

        assert manager.validate_trade(trade) is False


@pytest.mark.portfolio
class TestExecuteTradeEdgeCases:
    """거래 실행 엣지 케이스 테스트"""

    @pytest.mark.asyncio
    async def test_execute_trade_no_client(self):
        """클라이언트 없이 거래 실행"""
        from src.core.portfolio_manager import PortfolioManager

        manager = PortfolioManager()  # 클라이언트 없음

        trade = {'asset': 'BTC', 'action': 'buy', 'amount': 50000}
        result = await manager.execute_trade(trade)

        assert result['success'] is False
        assert 'error' in result


@pytest.mark.portfolio
class TestExecuteRebalancingEdgeCases:
    """리밸런싱 실행 엣지 케이스 테스트"""

    @pytest.mark.asyncio
    async def test_execute_rebalancing_no_client(self):
        """클라이언트 없이 리밸런싱"""
        from src.core.portfolio_manager import PortfolioManager

        manager = PortfolioManager()  # 클라이언트 없음

        result = await manager.execute_rebalancing()

        assert 'error' in result


@pytest.mark.portfolio
class TestCalculatePortfolioMetricsDataFrame:
    """DataFrame 기반 포트폴리오 메트릭 계산 테스트"""

    @pytest.fixture
    def manager(self):
        from src.core.portfolio_manager import PortfolioManager
        return PortfolioManager()

    def test_metrics_from_dataframe(self, manager):
        """DataFrame에서 메트릭 계산"""
        import pandas as pd

        df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=10, freq='D'),
            'total_value': [1000000 + i * 10000 for i in range(10)]
        })

        metrics = manager.calculate_portfolio_metrics(df)

        assert 'total_return' in metrics
        assert 'volatility' in metrics
        assert 'sharpe_ratio' in metrics
        assert 'max_drawdown' in metrics

    def test_metrics_from_list(self, manager):
        """리스트에서 메트릭 계산 (폴백)"""
        data = [1000000, 1100000, 1200000]

        metrics = manager.calculate_portfolio_metrics(data)

        # 리스트 입력 시 기본값 반환
        assert metrics['total_return'] == 0.15
        assert metrics['volatility'] == 0.12


@pytest.mark.portfolio
class TestLoadConfig:
    """설정 로드 테스트"""

    def test_load_config(self):
        """설정 로드"""
        from src.core.portfolio_manager import load_config

        config = load_config()

        assert 'strategy' in config
        assert 'risk_management' in config
        assert config['strategy']['portfolio']['core']['BTC'] == 40
        assert config['strategy']['portfolio']['core']['ETH'] == 30


@pytest.mark.portfolio
class TestExpandCryptoOrders:
    """crypto 주문 분해 테스트"""

    @pytest.fixture
    def manager(self):
        from src.core.portfolio_manager import PortfolioManager
        return PortfolioManager()

    def test_expand_crypto_buy_order(self, manager):
        """crypto 매수 주문 분해"""
        rebalance_info = {
            "total_value_krw": 1000000,
            "rebalance_orders": {
                "crypto": {
                    "asset": "crypto",
                    "amount_diff_krw": 100000,
                    "action": "buy"
                }
            },
            "summary": {
                "buy_orders": ["crypto"],
                "sell_orders": [],
                "total_buy_amount": 100000,
                "total_sell_amount": 0
            }
        }

        result = manager._expand_crypto_orders(rebalance_info)

        # crypto 주문이 분해됨
        assert "crypto" not in result["rebalance_orders"]
        # 개별 암호화폐 주문이 생성됨
        assert any(asset in result["rebalance_orders"] for asset in ["BTC", "ETH", "XRP", "SOL"])

    def test_expand_crypto_no_crypto_order(self, manager):
        """crypto 주문이 없는 경우"""
        rebalance_info = {
            "total_value_krw": 1000000,
            "rebalance_orders": {
                "BTC": {
                    "asset": "BTC",
                    "amount_diff_krw": 50000,
                    "action": "buy"
                }
            },
            "summary": {
                "buy_orders": ["BTC"],
                "sell_orders": [],
                "total_buy_amount": 50000,
                "total_sell_amount": 0
            }
        }

        result = manager._expand_crypto_orders(rebalance_info)

        # 변경 없음
        assert "BTC" in result["rebalance_orders"]