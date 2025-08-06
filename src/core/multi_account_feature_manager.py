"""
Multi-Account Feature Manager for KAIROS-1 System

모든 기존 기능을 멀티 계정에서 동일하게 제공하는 통합 관리자
"""

import asyncio
import json
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger
from dataclasses import dataclass
from decimal import Decimal

from .types import AccountID, AccountName, KRWAmount, Percentage
from .base_service import BaseService, ServiceConfig
from .exceptions import KairosException, ConfigurationException
from .multi_account_manager import MultiAccountManager, get_multi_account_manager
from .market_season_filter import MarketSeasonFilter
from ..utils.database_manager import DatabaseManager

# 기존 단일 계정 매니저들 import
from .portfolio_manager import PortfolioManager, AssetAllocation
from .rebalancer import Rebalancer
from .adaptive_portfolio_manager import AdaptivePortfolioManager
from .dca_plus_strategy import DCAPlus
from .risk_parity_model import RiskParityModel
from .tax_optimization_system import TaxOptimizationSystem
from .macro_economic_analyzer import MacroEconomicAnalyzer
from .onchain_data_analyzer import OnchainDataAnalyzer
from .scenario_response_system import ScenarioResponseSystem
from .behavioral_bias_prevention import BehavioralBiasPrevention
from .advanced_performance_analytics import AdvancedPerformanceAnalytics
from .dynamic_execution_engine import DynamicExecutionEngine
from .smart_execution_engine import SmartExecutionEngine

from ..risk.risk_manager import RiskManager
from ..monitoring.alert_system import AlertSystem
from ..monitoring.performance_tracker import PerformanceTracker
from ..trading.order_manager import OrderManager


@dataclass
class MultiAccountOperationResult:
    """멀티 계정 작업 결과"""
    total_accounts: int
    successful_accounts: List[AccountID]
    failed_accounts: List[AccountID]
    results: Dict[AccountID, Any]
    errors: Dict[AccountID, str]
    execution_time: float
    started_at: datetime
    completed_at: datetime

    @property
    def success_rate(self) -> float:
        """성공률"""
        return len(self.successful_accounts) / self.total_accounts if self.total_accounts > 0 else 0.0

    @property
    def is_fully_successful(self) -> bool:
        """전체 성공 여부"""
        return len(self.failed_accounts) == 0


class MultiAccountFeatureManager(BaseService):
    """멀티 계정 기능 관리자
    
    모든 기존 KAIROS-1 기능들을 멀티 계정 환경에서 동일하게 제공합니다.
    각 계정별로 독립적인 기능 실행과 통합 관리를 동시에 지원합니다.
    """
    
    def __init__(self, db_manager=None, market_season_filter=None):
        super().__init__(ServiceConfig(
            name="multi_account_feature_manager",
            enabled=True,
            health_check_interval=300
        ))
        
        self.multi_account_manager = get_multi_account_manager()
        self.db_manager = db_manager
        self.market_season_filter = market_season_filter
        
        # 필수 의존성 검증
        if self.db_manager is None:
            logger.warning("⚠️ DatabaseManager가 제공되지 않음 - 일부 기능이 제한될 수 있습니다")
        if self.market_season_filter is None:
            logger.warning("⚠️ MarketSeasonFilter가 제공되지 않음 - 일부 기능이 제한될 수 있습니다")
        
        # 계정별 기능 인스턴스 캐시
        self.portfolio_managers: Dict[AccountID, PortfolioManager] = {}
        self.rebalancers: Dict[AccountID, Rebalancer] = {}
        self.risk_managers: Dict[AccountID, RiskManager] = {}
        self.order_managers: Dict[AccountID, OrderManager] = {}
        self.performance_trackers: Dict[AccountID, PerformanceTracker] = {}
        
        # 고급 기능 인스턴스 캐시
        self.adaptive_managers: Dict[AccountID, AdaptivePortfolioManager] = {}
        self.dca_strategies: Dict[AccountID, DCAPlus] = {}
        self.risk_parity_models: Dict[AccountID, RiskParityModel] = {}
        self.tax_optimizers: Dict[AccountID, TaxOptimizationSystem] = {}
        self.execution_engines: Dict[AccountID, DynamicExecutionEngine] = {}
        
        # 공통 분석 도구 (계정 독립적)
        self.macro_analyzer = MacroEconomicAnalyzer()
        self.onchain_analyzer = OnchainDataAnalyzer()
        self.scenario_system = ScenarioResponseSystem()
        self.bias_prevention = BehavioralBiasPrevention()
        
        # 동시성 제어
        self.operation_locks: Dict[str, asyncio.Lock] = {}
        self.max_concurrent_operations = 5
    
    async def initialize(self):
        """멀티 계정 기능 관리자 초기화"""
        try:
            logger.info("🎯 멀티 계정 기능 관리자 초기화 시작")
            
            # 멀티 계정 관리자 초기화
            if not hasattr(self.multi_account_manager, '_initialized') or not self.multi_account_manager._initialized:
                await self.multi_account_manager.initialize()
            
            # 계정별 기능 인스턴스 초기화
            await self._initialize_account_features()
            
            # 공통 분석 도구 초기화
            await self._initialize_shared_analyzers()
            
            logger.info("✅ 멀티 계정 기능 관리자 초기화 완료")
            
        except Exception as e:
            logger.error(f"❌ 멀티 계정 기능 관리자 초기화 실패: {e}")
            raise ConfigurationException("multi_account_feature_manager", str(e))
    
    async def _initialize_account_features(self):
        """각 계정별 기능 인스턴스 초기화"""
        accounts = await self.multi_account_manager.get_all_accounts()
        
        for account_info in accounts:
            account_id = account_info["account_id"]
            client = self.multi_account_manager.clients.get(account_id)
            
            if not client:
                logger.warning(f"⚠️ 계정 {account_id} 클라이언트 없음, 기능 초기화 건너뛰기")
                continue
            
            try:
                # 핵심 기능들 초기화
                self.portfolio_managers[account_id] = PortfolioManager(
                    coinone_client=client,
                    use_dynamic_optimization=True
                )
                
                # Rebalancer는 market_season_filter와 db_manager가 필요함
                if self.market_season_filter is not None and self.db_manager is not None:
                    self.rebalancers[account_id] = Rebalancer(
                        coinone_client=client,
                        portfolio_manager=self.portfolio_managers[account_id],
                        market_season_filter=self.market_season_filter,
                        db_manager=self.db_manager
                    )
                else:
                    logger.warning(f"⚠️ 계정 {account_id} Rebalancer 초기화 건너뛰기 (필수 의존성 없음)")
                
                self.risk_managers[account_id] = RiskManager(
                    coinone_client=client
                )
                
                self.order_managers[account_id] = OrderManager(
                    coinone_client=client
                )
                
                self.performance_trackers[account_id] = PerformanceTracker(
                    account_id=account_id
                )
                
                # 고급 기능들 초기화
                self.adaptive_managers[account_id] = AdaptivePortfolioManager(
                    base_portfolio_manager=self.portfolio_managers[account_id]
                )
                
                self.dca_strategies[account_id] = DCAPlus()
                
                self.risk_parity_models[account_id] = RiskParityModel()
                
                self.tax_optimizers[account_id] = TaxOptimizationSystem()
                
                # DynamicExecutionEngine은 db_manager가 필요함
                if self.db_manager is not None:
                    self.execution_engines[account_id] = DynamicExecutionEngine(
                        coinone_client=client,
                        db_manager=self.db_manager
                    )
                else:
                    logger.warning(f"⚠️ 계정 {account_id} DynamicExecutionEngine 초기화 건너뛰기 (db_manager 없음)")
                
                logger.info(f"✅ 계정 {account_id} 기능 초기화 완료")
                
            except Exception as e:
                logger.error(f"❌ 계정 {account_id} 기능 초기화 실패: {e}")
                continue
    
    async def _initialize_shared_analyzers(self):
        """공통 분석 도구 초기화"""
        try:
            # 이미 초기화된 분석 도구들은 그대로 사용
            logger.info("✅ 공통 분석 도구 초기화 완료")
        except Exception as e:
            logger.error(f"❌ 공통 분석 도구 초기화 실패: {e}")
    
    async def run_portfolio_optimization_for_all(
        self, 
        target_accounts: Optional[List[AccountID]] = None
    ) -> MultiAccountOperationResult:
        """모든 계정에 대해 포트폴리오 최적화 실행"""
        return await self._execute_for_all_accounts(
            "portfolio_optimization",
            self._run_portfolio_optimization_for_account,
            target_accounts
        )
    
    async def _run_portfolio_optimization_for_account(self, account_id: AccountID) -> Dict[str, Any]:
        """개별 계정 포트폴리오 최적화"""
        if account_id not in self.portfolio_managers:
            raise KairosException(f"계정 {account_id} 포트폴리오 매니저 없음", "MANAGER_NOT_FOUND")
        
        manager = self.portfolio_managers[account_id]
        
        # 현재 포트폴리오 분석
        current_portfolio = await asyncio.to_thread(manager.get_current_portfolio)
        
        # 최적 포트폴리오 계산
        optimal_weights = await asyncio.to_thread(manager.get_optimal_allocation)
        
        return {
            "current_portfolio": current_portfolio,
            "optimal_weights": optimal_weights,
            "optimization_timestamp": datetime.now().isoformat()
        }
    
    async def execute_rebalancing_for_all(
        self,
        target_accounts: Optional[List[AccountID]] = None,
        dry_run: bool = False
    ) -> MultiAccountOperationResult:
        """모든 계정에 대해 리밸런싱 실행"""
        return await self._execute_for_all_accounts(
            "rebalancing",
            lambda account_id: self._execute_rebalancing_for_account(account_id, dry_run),
            target_accounts
        )
    
    async def _execute_rebalancing_for_account(self, account_id: AccountID, dry_run: bool) -> Dict[str, Any]:
        """개별 계정 리밸런싱 실행"""
        if account_id not in self.rebalancers:
            raise KairosException(f"계정 {account_id} 리밸런서 없음", "REBALANCER_NOT_FOUND")
        
        rebalancer = self.rebalancers[account_id]
        
        # 리밸런싱 실행
        result = await asyncio.to_thread(
            rebalancer.execute_rebalancing,
            dry_run=dry_run
        )
        
        return result
    
    async def run_risk_analysis_for_all(
        self,
        target_accounts: Optional[List[AccountID]] = None
    ) -> MultiAccountOperationResult:
        """모든 계정에 대해 리스크 분석 실행"""
        return await self._execute_for_all_accounts(
            "risk_analysis",
            self._run_risk_analysis_for_account,
            target_accounts
        )
    
    async def _run_risk_analysis_for_account(self, account_id: AccountID) -> Dict[str, Any]:
        """개별 계정 리스크 분석"""
        if account_id not in self.risk_managers:
            raise KairosException(f"계정 {account_id} 리스크 매니저 없음", "RISK_MANAGER_NOT_FOUND")
        
        risk_manager = self.risk_managers[account_id]
        
        # 리스크 분석 실행
        risk_metrics = await asyncio.to_thread(risk_manager.calculate_portfolio_risk)
        volatility = await asyncio.to_thread(risk_manager.calculate_volatility)
        var = await asyncio.to_thread(risk_manager.calculate_var)
        
        return {
            "risk_metrics": risk_metrics,
            "volatility": volatility,
            "value_at_risk": var,
            "analysis_timestamp": datetime.now().isoformat()
        }
    
    async def run_performance_analysis_for_all(
        self,
        target_accounts: Optional[List[AccountID]] = None
    ) -> MultiAccountOperationResult:
        """모든 계정에 대해 성과 분석 실행"""
        return await self._execute_for_all_accounts(
            "performance_analysis",
            self._run_performance_analysis_for_account,
            target_accounts
        )
    
    async def _run_performance_analysis_for_account(self, account_id: AccountID) -> Dict[str, Any]:
        """개별 계정 성과 분석"""
        if account_id not in self.performance_trackers:
            raise KairosException(f"계정 {account_id} 성과 추적기 없음", "TRACKER_NOT_FOUND")
        
        tracker = self.performance_trackers[account_id]
        
        # 성과 분석 실행
        performance_data = await asyncio.to_thread(tracker.generate_performance_report)
        
        return performance_data
    
    async def run_dca_strategy_for_all(
        self,
        target_accounts: Optional[List[AccountID]] = None,
        amount_krw: Optional[KRWAmount] = None
    ) -> MultiAccountOperationResult:
        """모든 계정에 대해 DCA+ 전략 실행"""
        return await self._execute_for_all_accounts(
            "dca_strategy",
            lambda account_id: self._run_dca_strategy_for_account(account_id, amount_krw),
            target_accounts
        )
    
    async def _run_dca_strategy_for_account(self, account_id: AccountID, amount_krw: Optional[KRWAmount]) -> Dict[str, Any]:
        """개별 계정 DCA+ 전략 실행"""
        if account_id not in self.dca_strategies:
            raise KairosException(f"계정 {account_id} DCA 전략 없음", "DCA_STRATEGY_NOT_FOUND")
        
        dca_strategy = self.dca_strategies[account_id]
        
        # DCA 전략 실행
        result = await asyncio.to_thread(
            dca_strategy.execute_dca_plus,
            amount_krw=amount_krw
        )
        
        return result
    
    async def run_tax_optimization_for_all(
        self,
        target_accounts: Optional[List[AccountID]] = None
    ) -> MultiAccountOperationResult:
        """모든 계정에 대해 세금 최적화 분석 실행"""
        return await self._execute_for_all_accounts(
            "tax_optimization",
            self._run_tax_optimization_for_account,
            target_accounts
        )
    
    async def _run_tax_optimization_for_account(self, account_id: AccountID) -> Dict[str, Any]:
        """개별 계정 세금 최적화"""
        if account_id not in self.tax_optimizers:
            raise KairosException(f"계정 {account_id} 세금 최적화 시스템 없음", "TAX_OPTIMIZER_NOT_FOUND")
        
        tax_optimizer = self.tax_optimizers[account_id]
        
        # 세금 최적화 분석
        optimization_result = await asyncio.to_thread(tax_optimizer.analyze_tax_efficiency)
        
        return optimization_result
    
    async def _execute_for_all_accounts(
        self,
        operation_name: str,
        account_operation_func,
        target_accounts: Optional[List[AccountID]] = None
    ) -> MultiAccountOperationResult:
        """모든 계정에 대해 특정 작업 실행"""
        start_time = datetime.now()
        
        # 대상 계정 결정
        if target_accounts is None:
            all_accounts = await self.multi_account_manager.get_all_accounts()
            target_accounts = [acc["account_id"] for acc in all_accounts if acc["status"].value == "active"]
        
        # 동시성 제어
        operation_key = f"{operation_name}_{int(start_time.timestamp())}"
        if operation_key not in self.operation_locks:
            self.operation_locks[operation_key] = asyncio.Lock()
        
        async with self.operation_locks[operation_key]:
            logger.info(f"🚀 {operation_name} 시작 - 대상 계정: {len(target_accounts)}개")
            
            # 세마포어로 동시 실행 수 제한
            semaphore = asyncio.Semaphore(self.max_concurrent_operations)
            
            async def execute_with_semaphore(account_id: AccountID):
                async with semaphore:
                    try:
                        result = await account_operation_func(account_id)
                        return account_id, True, result, None
                    except Exception as e:
                        logger.error(f"❌ 계정 {account_id} {operation_name} 실패: {e}")
                        return account_id, False, None, str(e)
            
            # 병렬 실행
            tasks = [execute_with_semaphore(account_id) for account_id in target_accounts]
            execution_results = await asyncio.gather(*tasks)
            
            # 결과 정리
            end_time = datetime.now()
            successful_accounts = []
            failed_accounts = []
            results = {}
            errors = {}
            
            for account_id, success, result, error in execution_results:
                if success:
                    successful_accounts.append(account_id)
                    results[account_id] = result
                else:
                    failed_accounts.append(account_id)
                    errors[account_id] = error
            
            operation_result = MultiAccountOperationResult(
                total_accounts=len(target_accounts),
                successful_accounts=successful_accounts,
                failed_accounts=failed_accounts,
                results=results,
                errors=errors,
                execution_time=(end_time - start_time).total_seconds(),
                started_at=start_time,
                completed_at=end_time
            )
            
            logger.info(
                f"✅ {operation_name} 완료 - "
                f"성공: {len(successful_accounts)}/{len(target_accounts)} "
                f"({operation_result.success_rate:.1%}) "
                f"실행시간: {operation_result.execution_time:.2f}초"
            )
            
            return operation_result
    
    async def get_aggregate_analytics(self) -> Dict[str, Any]:
        """모든 계정의 통합 분석 정보"""
        try:
            # 기본 포트폴리오 정보
            portfolio_data = await self.multi_account_manager.get_aggregate_portfolio()
            
            # 전체 리스크 분석
            risk_analysis = await self.run_risk_analysis_for_all()
            
            # 전체 성과 분석
            performance_analysis = await self.run_performance_analysis_for_all()
            
            # 거시경제 분석 (공통)
            macro_data = await asyncio.to_thread(self.macro_analyzer.get_market_sentiment)
            
            # 온체인 분석 (공통)
            onchain_data = await asyncio.to_thread(self.onchain_analyzer.get_network_health)
            
            return {
                "portfolio_overview": portfolio_data,
                "risk_analysis": {
                    "success_rate": risk_analysis.success_rate,
                    "account_risks": risk_analysis.results
                },
                "performance_analysis": {
                    "success_rate": performance_analysis.success_rate,
                    "account_performance": performance_analysis.results
                },
                "macro_analysis": macro_data,
                "onchain_analysis": onchain_data,
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ 통합 분석 정보 생성 실패: {e}")
            return {}
    
    async def start(self):
        """서비스 시작"""
        await self.initialize()
        logger.info("🎯 멀티 계정 기능 관리자 시작")
    
    async def stop(self):
        """서비스 중지"""
        # 리소스 정리
        self.operation_locks.clear()
        logger.info("🎯 멀티 계정 기능 관리자 중지")
    
    async def health_check(self) -> Dict[str, Any]:
        """헬스체크"""
        accounts_health = await self.multi_account_manager.health_check()
        
        total_features = sum([
            len(self.portfolio_managers),
            len(self.rebalancers),
            len(self.risk_managers),
            len(self.order_managers)
        ])
        
        return {
            'service': 'multi_account_feature_manager',
            'status': 'healthy' if accounts_health.get('active_accounts', 0) > 0 else 'degraded',
            'accounts_status': accounts_health,
            'total_feature_instances': total_features,
            'shared_analyzers': {
                'macro_analyzer': 'active',
                'onchain_analyzer': 'active',
                'scenario_system': 'active',
                'bias_prevention': 'active'
            },
            'last_check': datetime.now().isoformat()
        }


# 전역 인스턴스
_multi_account_feature_manager: Optional[MultiAccountFeatureManager] = None

def get_multi_account_feature_manager(db_manager=None, market_season_filter=None) -> MultiAccountFeatureManager:
    """멀티 계정 기능 관리자 인스턴스 반환"""
    global _multi_account_feature_manager
    if _multi_account_feature_manager is None:
        _multi_account_feature_manager = MultiAccountFeatureManager(db_manager, market_season_filter)
    return _multi_account_feature_manager