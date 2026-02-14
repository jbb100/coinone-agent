"""
Multi-Account Portfolio Manager for KAIROS-1 System

계정별 포트폴리오를 개별적으로 관리하면서 전체적인 조율도 수행
"""

import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from loguru import logger
from decimal import Decimal

from .types import (
    AccountID, AssetSymbol, KRWAmount, Percentage, 
    MarketSeason, RiskLevel, PortfolioSnapshot, OrderInfo
)
from .base_service import BaseService, ServiceConfig
from .exceptions import KairosException, TradingException
from .multi_account_manager import get_multi_account_manager, AccountConfig
from ..trading.coinone_client import CoinoneClient


class AccountPortfolioManager:
    """개별 계정 포트폴리오 관리자"""
    
    def __init__(self, account_id: AccountID, config: AccountConfig, client: CoinoneClient):
        self.account_id = account_id
        self.config = config
        self.client = client
        self.last_rebalance = None
        self.performance_metrics = {}
    
    async def calculate_target_weights(self, market_season: MarketSeason) -> Dict[AssetSymbol, Percentage]:
        """시장 상황과 리스크 수준에 따른 목표 비중 계산"""
        try:
            # 리스크 수준별 기본 배분
            if self.config.risk_level == RiskLevel.CONSERVATIVE:
                base_crypto_allocation = 0.3
                cash_allocation = 0.7
            elif self.config.risk_level == RiskLevel.MODERATE:
                base_crypto_allocation = 0.5
                cash_allocation = 0.5
            else:  # AGGRESSIVE
                base_crypto_allocation = 0.7
                cash_allocation = 0.3
            
            # 시장 계절에 따른 조정
            if market_season == MarketSeason.RISK_ON:
                crypto_multiplier = 1.2
            elif market_season == MarketSeason.RISK_OFF:
                crypto_multiplier = 0.8
            else:  # NEUTRAL
                crypto_multiplier = 1.0
            
            adjusted_crypto_allocation = min(base_crypto_allocation * crypto_multiplier, 0.9)
            adjusted_cash_allocation = 1.0 - adjusted_crypto_allocation
            
            # 암호화폐 내 배분
            core_allocation = adjusted_crypto_allocation * self.config.core_allocation
            satellite_allocation = adjusted_crypto_allocation * self.config.satellite_allocation
            
            target_weights = {
                AssetSymbol('KRW'): Percentage(adjusted_cash_allocation),
                AssetSymbol('BTC'): Percentage(core_allocation * 0.6),  # 비트코인 60%
                AssetSymbol('ETH'): Percentage(core_allocation * 0.4),  # 이더리움 40%
                AssetSymbol('XRP'): Percentage(satellite_allocation * 0.5),  # 리플 50%
                AssetSymbol('SOL'): Percentage(satellite_allocation * 0.5),  # 솔라나 50%
            }
            
            # 최대 포지션 크기 제한 적용
            max_position = self.config.max_position_size
            for asset, weight in target_weights.items():
                if asset != AssetSymbol('KRW') and weight > max_position:
                    # 초과분을 현금으로 이동
                    excess = weight - max_position
                    target_weights[asset] = Percentage(max_position)
                    target_weights[AssetSymbol('KRW')] += Percentage(excess)
            
            logger.info(f"📊 계정 {self.account_id} 목표 비중 계산 완료: {target_weights}")
            return target_weights
            
        except Exception as e:
            logger.error(f"❌ 계정 {self.account_id} 목표 비중 계산 실패: {e}")
            raise TradingException(f"목표 비중 계산 실패: {e}", "TARGET_WEIGHT_CALC_FAILED")
    
    async def get_current_portfolio(self) -> PortfolioSnapshot:
        """현재 포트폴리오 스냅샷 조회"""
        try:
            balances = await asyncio.to_thread(self.client.get_balances)
            
            total_value = KRWAmount(Decimal('0'))
            assets = {}
            weights = {}
            
            # balances는 Dict[str, float] 형태
            for currency, balance_amount in balances.items():
                if balance_amount == 0:
                    continue
                    
                asset = AssetSymbol(currency)
                
                # 현재 시세 조회 (KRW 값 계산용)
                if currency != 'KRW':
                    ticker = await asyncio.to_thread(self.client.get_ticker, currency)
                    current_price = Decimal(str(ticker.get('last', 0)))
                    value_krw = KRWAmount(Decimal(str(balance_amount)) * current_price)
                else:
                    value_krw = KRWAmount(Decimal(str(balance_amount)))
                
                total_value += value_krw
                
                assets[asset] = {
                    'asset': asset,
                    'total': Decimal(str(balance_amount)),
                    'available': Decimal(str(balance_amount)),  # TODO: 실제 available 값 구분 필요
                    'locked': Decimal('0'),  # TODO: 실제 locked 값 구분 필요
                    'value_krw': value_krw
                }
            
            # 비중 계산
            for asset, balance in assets.items():
                weights[asset] = Percentage(
                    float(balance['value_krw'] / total_value) if total_value > 0 else 0.0
                )
            
            return PortfolioSnapshot(
                timestamp=datetime.now(),
                total_value_krw=total_value,
                assets=assets,
                weights=weights,
                daily_return=None,  # TODO: 일일 수익률 계산
                total_return=Percentage(
                    float((total_value - self.config.initial_capital) / self.config.initial_capital)
                    if self.config.initial_capital > 0 else 0.0
                )
            )
            
        except Exception as e:
            logger.error(f"❌ 계정 {self.account_id} 포트폴리오 조회 실패: {e}")
            raise TradingException(f"포트폴리오 조회 실패: {e}", "PORTFOLIO_FETCH_FAILED")
    
    async def needs_rebalancing(self, target_weights: Dict[AssetSymbol, Percentage], 
                              threshold: float = 0.05) -> bool:
        """리밸런싱 필요 여부 확인"""
        try:
            current_portfolio = await self.get_current_portfolio()
            current_weights = current_portfolio['weights']
            
            for asset, target_weight in target_weights.items():
                current_weight = current_weights.get(asset, Percentage(0.0))
                weight_diff = abs(target_weight - current_weight)
                
                if weight_diff > threshold:
                    logger.info(f"📊 계정 {self.account_id} 리밸런싱 필요: {asset} {current_weight:.3f} -> {target_weight:.3f}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ 계정 {self.account_id} 리밸런싱 필요성 확인 실패: {e}")
            return False
    
    async def execute_rebalancing(self, target_weights: Dict[AssetSymbol, Percentage]) -> List[OrderInfo]:
        """리밸런싱 실행"""
        try:
            logger.info(f"⚖️ 계정 {self.account_id} 리밸런싱 시작")
            
            if self.config.dry_run:
                logger.info(f"🔄 계정 {self.account_id} 드라이런 모드: 실제 주문 없이 시뮬레이션")
                return []
            
            current_portfolio = await self.get_current_portfolio()
            total_value = current_portfolio['total_value_krw']
            current_weights = current_portfolio['weights']
            
            orders = []
            
            # 매도 주문부터 실행 (현금 확보)
            for asset, current_weight in current_weights.items():
                if asset == AssetSymbol('KRW'):
                    continue
                
                target_weight = target_weights.get(asset, Percentage(0.0))
                
                if current_weight > target_weight:
                    # 매도 필요
                    sell_value = (current_weight - target_weight) * float(total_value)
                    
                    if sell_value > 10000:  # 최소 주문 금액
                        # 현재 가격 조회
                        ticker = await asyncio.to_thread(self.client.get_ticker, str(asset))
                        current_price = Decimal(str(ticker['last']))
                        
                        # 매도 수량 계산
                        sell_quantity = Decimal(str(sell_value)) / current_price
                        
                        # 매도 주문 실행
                        order = await asyncio.to_thread(
                            self.client.sell_market_order,
                            str(asset),
                            float(sell_quantity)
                        )
                        orders.append(order)
                        
                        logger.info(f"💰 계정 {self.account_id} 매도: {asset} {sell_quantity:.6f} (₩{sell_value:,.0f})")
            
            # 매수 주문 실행
            await asyncio.sleep(2)  # 매도 주문 정산 대기
            
            for asset, target_weight in target_weights.items():
                if asset == AssetSymbol('KRW'):
                    continue
                
                current_weight = current_weights.get(asset, Percentage(0.0))
                
                if target_weight > current_weight:
                    # 매수 필요
                    buy_value = (target_weight - current_weight) * float(total_value)
                    
                    if buy_value > 10000:  # 최소 주문 금액
                        # 매수 주문 실행 (KRW로 직접 매수)
                        order = await asyncio.to_thread(
                            self.client.buy_market_order_krw,
                            str(asset),
                            int(buy_value)
                        )
                        orders.append(order)
                        
                        logger.info(f"🛒 계정 {self.account_id} 매수: {asset} ₩{buy_value:,.0f}")
            
            self.last_rebalance = datetime.now()
            logger.info(f"✅ 계정 {self.account_id} 리밸런싱 완료: {len(orders)}개 주문")
            
            return orders
            
        except Exception as e:
            logger.error(f"❌ 계정 {self.account_id} 리밸런싱 실패: {e}")
            raise TradingException(f"리밸런싱 실패: {e}", "REBALANCING_FAILED")


class MultiPortfolioManager(BaseService):
    """멀티 계정 포트폴리오 통합 관리자"""
    
    def __init__(self):
        super().__init__(ServiceConfig(
            name="multi_portfolio_manager",
            enabled=True,
            health_check_interval=600  # 10분마다 헬스체크
        ))
        
        self.account_managers: Dict[AccountID, AccountPortfolioManager] = {}
        self.multi_account_manager = get_multi_account_manager()
        
        # 글로벌 설정
        self.rebalance_threshold = 0.05  # 5% 이상 차이날 때 리밸런싱
        self.max_concurrent_rebalancing = 2  # 동시 리밸런싱 계정 수
    
    async def initialize(self):
        """멀티 포트폴리오 관리자 초기화"""
        try:
            logger.info("📊 멀티 포트폴리오 관리자 초기화 시작")
            
            # 멀티 계정 관리자 초기화
            await self.multi_account_manager.initialize()
            
            # 각 계정별 포트폴리오 관리자 생성
            await self._create_account_managers()
            
            logger.info(f"✅ 멀티 포트폴리오 관리자 초기화 완료: {len(self.account_managers)}개 계정")
            
        except Exception as e:
            logger.error(f"❌ 멀티 포트폴리오 관리자 초기화 실패: {e}")
            raise
    
    async def _create_account_managers(self):
        """계정별 포트폴리오 관리자 생성"""
        for account_id, config in self.multi_account_manager.accounts.items():
            if account_id in self.multi_account_manager.clients:
                client = self.multi_account_manager.clients[account_id]
                manager = AccountPortfolioManager(account_id, config, client)
                self.account_managers[account_id] = manager
                logger.info(f"📊 계정 {account_id} 포트폴리오 관리자 생성")
    
    async def get_market_season(self) -> MarketSeason:
        """현재 시장 계절 판단"""
        # TODO: 실제 시장 분석 로직 구현
        # 임시로 NEUTRAL 반환
        return MarketSeason.NEUTRAL
    
    async def rebalance_account(self, account_id: AccountID, 
                              force: bool = False) -> Dict[str, Any]:
        """특정 계정 리밸런싱"""
        try:
            if account_id not in self.account_managers:
                raise KairosException(f"계정 {account_id} 관리자 없음", "ACCOUNT_MANAGER_NOT_FOUND")
            
            manager = self.account_managers[account_id]
            market_season = await self.get_market_season()
            
            # 목표 비중 계산
            target_weights = await manager.calculate_target_weights(market_season)
            
            # 리밸런싱 필요성 확인
            if not force:
                needs_rebalancing = await manager.needs_rebalancing(
                    target_weights, self.rebalance_threshold
                )
                if not needs_rebalancing:
                    logger.info(f"📊 계정 {account_id} 리밸런싱 불필요")
                    return {
                        'account_id': account_id,
                        'action': 'skipped',
                        'reason': '리밸런싱 임계값 미달성',
                        'target_weights': {str(k): float(v) for k, v in target_weights.items()}
                    }
            
            # 리밸런싱 실행
            orders = await manager.execute_rebalancing(target_weights)
            
            return {
                'account_id': account_id,
                'action': 'completed',
                'orders_count': len(orders),
                'target_weights': {str(k): float(v) for k, v in target_weights.items()},
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ 계정 {account_id} 리밸런싱 실패: {e}")
            return {
                'account_id': account_id,
                'action': 'failed',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def rebalance_all_accounts(self, force: bool = False) -> List[Dict[str, Any]]:
        """모든 활성 계정 리밸런싱"""
        try:
            logger.info("⚖️ 전체 계정 리밸런싱 시작")
            
            # 활성 계정 필터링
            active_accounts = [
                account_id for account_id, status in self.multi_account_manager.account_status.items()
                if status.value == "active"
            ]
            
            if not active_accounts:
                logger.warning("⚠️ 활성 계정이 없습니다")
                return []
            
            # 동시 실행 제한을 위한 세마포어
            semaphore = asyncio.Semaphore(self.max_concurrent_rebalancing)
            
            async def rebalance_with_semaphore(account_id):
                async with semaphore:
                    return await self.rebalance_account(account_id, force)
            
            # 모든 계정 병렬 리밸런싱
            results = await asyncio.gather(*[
                rebalance_with_semaphore(account_id) for account_id in active_accounts
            ], return_exceptions=True)
            
            # 결과 정리
            successful_rebalances = [r for r in results if isinstance(r, dict) and r.get('action') == 'completed']
            failed_rebalances = [r for r in results if isinstance(r, dict) and r.get('action') == 'failed']
            
            logger.info(f"✅ 전체 계정 리밸런싱 완료: 성공 {len(successful_rebalances)}, 실패 {len(failed_rebalances)}")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ 전체 계정 리밸런싱 실패: {e}")
            return []
    
    async def get_aggregate_performance(self) -> Dict[str, Any]:
        """전체 계정 통합 성과 분석"""
        try:
            total_value = Decimal('0')
            total_initial = Decimal('0')
            account_performances = []
            
            for account_id, manager in self.account_managers.items():
                try:
                    portfolio = await manager.get_current_portfolio()
                    config = manager.config
                    
                    account_value = portfolio['total_value_krw']
                    initial_capital = config.initial_capital
                    
                    total_value += account_value
                    total_initial += initial_capital
                    
                    account_return = float((account_value - initial_capital) / initial_capital) if initial_capital > 0 else 0.0
                    
                    account_performances.append({
                        'account_id': account_id,
                        'account_name': config.account_name,
                        'current_value': float(account_value),
                        'initial_capital': float(initial_capital),
                        'return_rate': account_return,
                        'risk_level': config.risk_level.value
                    })
                    
                except Exception as e:
                    logger.warning(f"⚠️ 계정 {account_id} 성과 조회 실패: {e}")
                    continue
            
            overall_return = float((total_value - total_initial) / total_initial) if total_initial > 0 else 0.0
            
            return {
                'total_value': float(total_value),
                'total_initial': float(total_initial),
                'overall_return': overall_return,
                'active_accounts': len(account_performances),
                'account_performances': account_performances,
                'last_updated': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ 통합 성과 분석 실패: {e}")
            return None
    
    async def start(self):
        """서비스 시작"""
        await self.initialize()
        logger.info("📊 멀티 포트폴리오 관리자 시작")
    
    async def stop(self):
        """서비스 중지"""
        self.account_managers.clear()
        logger.info("📊 멀티 포트폴리오 관리자 중지")
    
    async def health_check(self) -> Dict[str, Any]:
        """헬스체크"""
        healthy_accounts = 0
        total_accounts = len(self.account_managers)
        
        for account_id, manager in self.account_managers.items():
            try:
                # 간단한 포트폴리오 조회로 건강 상태 확인
                await manager.get_current_portfolio()
                healthy_accounts += 1
            except Exception:
                pass
        
        return {
            'service': 'multi_portfolio_manager',
            'status': 'healthy' if healthy_accounts > 0 else 'degraded',
            'healthy_accounts': healthy_accounts,
            'total_accounts': total_accounts,
            'last_check': datetime.now().isoformat()
        }


# 전역 멀티 포트폴리오 관리자 인스턴스
_multi_portfolio_manager: Optional[MultiPortfolioManager] = None

def get_multi_portfolio_manager() -> MultiPortfolioManager:
    """멀티 포트폴리오 관리자 인스턴스 반환"""
    global _multi_portfolio_manager
    if _multi_portfolio_manager is None:
        _multi_portfolio_manager = MultiPortfolioManager()
    return _multi_portfolio_manager