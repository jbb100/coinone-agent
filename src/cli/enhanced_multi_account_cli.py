"""
Enhanced Multi-Account CLI Interface for KAIROS-1 System

모든 기능을 멀티 계정에서 제공하는 확장된 CLI 인터페이스
"""

import asyncio
import sys
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from tabulate import tabulate
import click
from loguru import logger

# 프로젝트 루트 경로 추가
sys.path.append('/Users/jongdal100/git/coinone-agent')

from src.core.multi_account_manager import (
    get_multi_account_manager, AccountConfig, AccountStatus
)
from src.core.multi_account_feature_manager import get_multi_account_feature_manager
from src.core.multi_account_coordinator import get_multi_account_coordinator, TaskPriority
from src.core.types import AccountID, AccountName, RiskLevel, KRWAmount


class EnhancedMultiAccountCLI:
    """확장된 멀티 계정 관리 CLI - 모든 기능 지원"""
    
    def __init__(self):
        self.account_manager = get_multi_account_manager()
        self.feature_manager = get_multi_account_feature_manager()
        self.coordinator = get_multi_account_coordinator()
        self.initialized = False
    
    async def ensure_initialized(self):
        """초기화 확인"""
        if not self.initialized:
            try:
                await self.coordinator.start()  # coordinator.start()가 모든 초기화를 수행
                self.initialized = True
                click.echo("✅ 시스템 초기화 완료")
            except Exception as e:
                logger.error(f"❌ 초기화 실패: {e}")
                click.echo(f"❌ 초기화 실패: {e}")
                raise
    
    async def list_accounts(self, detailed: bool = False) -> None:
        """계정 목록 조회"""
        try:
            await self.ensure_initialized()
            accounts = await self.account_manager.get_all_accounts()
            
            if not accounts:
                click.echo("📭 등록된 계정이 없습니다.")
                return
            
            click.echo(f"🏦 총 {len(accounts)}개 계정 등록")
            
            if detailed:
                for account in accounts:
                    click.echo(f"\n{'='*50}")
                    click.echo(f"🏢 계정ID: {account.account_id}")
                    click.echo(f"📛 계정명: {account.account_name}")
                    click.echo(f"📝 설명: {account.description}")
                    click.echo(f"🎯 리스크 레벨: {account.risk_level.name}")
                    click.echo(f"📊 상태: {account.status.name}")
                    click.echo(f"💰 현재 가치: ₩{float(account.current_value):,.0f}")
                    click.echo(f"📈 총 수익률: {float(account.total_return):+.2%}")
                    click.echo(f"🔄 자동 리밸런싱: {'ON' if account.auto_rebalance else 'OFF'}")
            else:
                table_data = []
                for account in accounts:
                    table_data.append([
                        account.account_id,
                        account.account_name,
                        account.status.name,
                        account.risk_level.name,
                        f"₩{float(account.current_value):,.0f}",
                        f"{float(account.total_return):+.2%}",
                        "ON" if account.auto_rebalance else "OFF"
                    ])
                
                headers = ["계정ID", "계정명", "상태", "리스크", "현재가치", "수익률", "자동리밸런싱"]
                click.echo(tabulate(table_data, headers=headers, tablefmt="grid"))
                
        except Exception as e:
            click.echo(f"❌ 계정 목록 조회 실패: {e}")
    
    async def portfolio_optimization(self, account_id: Optional[str] = None) -> None:
        """포트폴리오 최적화 실행"""
        try:
            await self.ensure_initialized()
            
            target_accounts = [AccountID(account_id)] if account_id else None
            
            if account_id:
                click.echo(f"🎯 계정 '{account_id}' 포트폴리오 최적화 시작...")
            else:
                click.echo("🎯 전체 계정 포트폴리오 최적화 시작...")
            
            result = await self.feature_manager.run_portfolio_optimization_for_all(target_accounts)
            
            click.echo(f"✅ 포트폴리오 최적화 완료")
            click.echo(f"   📊 성공률: {result.success_rate:.1%}")
            click.echo(f"   ⏱️ 실행시간: {result.execution_time:.2f}초")
            click.echo(f"   ✅ 성공: {len(result.successful_accounts)}개 계정")
            
            if result.failed_accounts:
                click.echo(f"   ❌ 실패: {len(result.failed_accounts)}개 계정")
                for failed_account in result.failed_accounts:
                    error = result.errors.get(failed_account, "Unknown error")
                    click.echo(f"      - {failed_account}: {error}")
            
            # 성공한 계정들의 최적화 결과 요약
            if result.successful_accounts:
                click.echo("\n📈 최적화 결과 요약:")
                for account_id in result.successful_accounts:
                    account_result = result.results[account_id]
                    optimal_weights = account_result.get('optimal_weights', {})
                    if optimal_weights:
                        click.echo(f"   🏢 {account_id}: {optimal_weights}")
                        
        except Exception as e:
            click.echo(f"❌ 포트폴리오 최적화 실패: {e}")
    
    async def rebalance_all(self, account_id: Optional[str] = None, dry_run: bool = True) -> None:
        """리밸런싱 실행"""
        try:
            await self.ensure_initialized()
            
            target_accounts = [AccountID(account_id)] if account_id else None
            
            if account_id:
                click.echo(f"⚖️ 계정 '{account_id}' 리밸런싱 시작...")
            else:
                click.echo("⚖️ 전체 계정 리밸런싱 시작...")
            
            if dry_run:
                click.echo("🧪 테스트 모드로 실행 중...")
            
            result = await self.feature_manager.execute_rebalancing_for_all(target_accounts, dry_run)
            
            click.echo(f"✅ 리밸런싱 완료")
            click.echo(f"   📊 성공률: {result.success_rate:.1%}")
            click.echo(f"   ⏱️ 실행시간: {result.execution_time:.2f}초")
            click.echo(f"   ✅ 성공: {len(result.successful_accounts)}개 계정")
            
            if result.failed_accounts:
                click.echo(f"   ❌ 실패: {len(result.failed_accounts)}개 계정")
                for failed_account in result.failed_accounts:
                    error = result.errors.get(failed_account, "Unknown error")
                    click.echo(f"      - {failed_account}: {error}")
                        
        except Exception as e:
            click.echo(f"❌ 리밸런싱 실패: {e}")
    
    async def risk_analysis(self, account_id: Optional[str] = None) -> None:
        """리스크 분석 실행"""
        try:
            await self.ensure_initialized()
            
            target_accounts = [AccountID(account_id)] if account_id else None
            
            if account_id:
                click.echo(f"⚠️ 계정 '{account_id}' 리스크 분석 시작...")
            else:
                click.echo("⚠️ 전체 계정 리스크 분석 시작...")
            
            result = await self.feature_manager.run_risk_analysis_for_all(target_accounts)
            
            click.echo(f"✅ 리스크 분석 완료")
            click.echo(f"   📊 성공률: {result.success_rate:.1%}")
            click.echo(f"   ⏱️ 실행시간: {result.execution_time:.2f}초")
            
            # 리스크 분석 결과 요약
            if result.successful_accounts:
                click.echo("\n⚠️ 리스크 분석 결과:")
                table_data = []
                
                for account_id in result.successful_accounts:
                    account_result = result.results[account_id]
                    volatility = account_result.get('volatility', 0)
                    var = account_result.get('value_at_risk', 0)
                    
                    table_data.append([
                        account_id,
                        f"{volatility:.2%}" if isinstance(volatility, (int, float)) else str(volatility),
                        f"₩{var:,.0f}" if isinstance(var, (int, float)) else str(var)
                    ])
                
                headers = ["계정ID", "변동성", "VaR(95%)"]
                click.echo(tabulate(table_data, headers=headers, tablefmt="grid"))
                        
        except Exception as e:
            click.echo(f"❌ 리스크 분석 실패: {e}")
    
    async def performance_analysis(self, account_id: Optional[str] = None) -> None:
        """성과 분석 실행"""
        try:
            await self.ensure_initialized()
            
            target_accounts = [AccountID(account_id)] if account_id else None
            
            if account_id:
                click.echo(f"📈 계정 '{account_id}' 성과 분석 시작...")
            else:
                click.echo("📈 전체 계정 성과 분석 시작...")
            
            result = await self.feature_manager.run_performance_analysis_for_all(target_accounts)
            
            click.echo(f"✅ 성과 분석 완료")
            click.echo(f"   📊 성공률: {result.success_rate:.1%}")
            click.echo(f"   ⏱️ 실행시간: {result.execution_time:.2f}초")
            
            # 성과 분석 결과 요약 (실제 데이터 구조에 따라 조정 필요)
            if result.successful_accounts:
                click.echo("\n📈 성과 분석 결과:")
                for account_id in result.successful_accounts:
                    click.echo(f"   🏢 {account_id}: 분석 완료")
                        
        except Exception as e:
            click.echo(f"❌ 성과 분석 실패: {e}")
    
    async def dca_strategy(self, account_id: Optional[str] = None, amount: Optional[float] = None) -> None:
        """DCA+ 전략 실행"""
        try:
            await self.ensure_initialized()
            
            target_accounts = [AccountID(account_id)] if account_id else None
            amount_krw = KRWAmount(amount) if amount else None
            
            if account_id:
                click.echo(f"📊 계정 '{account_id}' DCA+ 전략 실행...")
            else:
                click.echo("📊 전체 계정 DCA+ 전략 실행...")
            
            if amount_krw:
                click.echo(f"💰 투자 금액: ₩{float(amount_krw):,.0f}")
            
            result = await self.feature_manager.run_dca_strategy_for_all(target_accounts, amount_krw)
            
            click.echo(f"✅ DCA+ 전략 완료")
            click.echo(f"   📊 성공률: {result.success_rate:.1%}")
            click.echo(f"   ⏱️ 실행시간: {result.execution_time:.2f}초")
                        
        except Exception as e:
            click.echo(f"❌ DCA+ 전략 실패: {e}")
    
    async def tax_optimization(self, account_id: Optional[str] = None) -> None:
        """세금 최적화 분석 실행"""
        try:
            await self.ensure_initialized()
            
            target_accounts = [AccountID(account_id)] if account_id else None
            
            if account_id:
                click.echo(f"💸 계정 '{account_id}' 세금 최적화 분석...")
            else:
                click.echo("💸 전체 계정 세금 최적화 분석...")
            
            result = await self.feature_manager.run_tax_optimization_for_all(target_accounts)
            
            click.echo(f"✅ 세금 최적화 분석 완료")
            click.echo(f"   📊 성공률: {result.success_rate:.1%}")
            click.echo(f"   ⏱️ 실행시간: {result.execution_time:.2f}초")
                        
        except Exception as e:
            click.echo(f"❌ 세금 최적화 분석 실패: {e}")
    
    async def aggregate_analytics(self) -> None:
        """통합 분석 정보 조회"""
        try:
            await self.ensure_initialized()
            
            click.echo("📊 통합 분석 정보 생성 중...")
            analytics = await self.feature_manager.get_aggregate_analytics()
            
            if not analytics:
                click.echo("📭 분석 정보가 없습니다.")
                return
            
            # 포트폴리오 개요
            if 'portfolio_overview' in analytics:
                overview = analytics['portfolio_overview']
                click.echo("💼 포트폴리오 개요:")
                click.echo(f"   💰 총 자산 가치: ₩{overview.get('total_value', 0):,.0f}")
                click.echo(f"   📈 총 수익률: {overview.get('total_return', 0):+.2%}")
                click.echo(f"   🏢 활성 계정 수: {overview.get('active_accounts', 0)}개")
            
            # 리스크 분석
            if 'risk_analysis' in analytics:
                risk = analytics['risk_analysis']
                click.echo(f"\n⚠️ 리스크 분석 성공률: {risk.get('success_rate', 0):.1%}")
            
            # 성과 분석
            if 'performance_analysis' in analytics:
                performance = analytics['performance_analysis']
                click.echo(f"📈 성과 분석 성공률: {performance.get('success_rate', 0):.1%}")
            
            # 거시경제 분석
            if 'macro_analysis' in analytics:
                click.echo("\n🌍 거시경제 분석 완료")
            
            # 온체인 분석
            if 'onchain_analysis' in analytics:
                click.echo("⛓️ 온체인 분석 완료")
            
            click.echo(f"\n📅 생성시간: {analytics.get('generated_at', 'Unknown')}")
                        
        except Exception as e:
            click.echo(f"❌ 통합 분석 정보 조회 실패: {e}")
    
    async def coordinator_status(self) -> None:
        """코디네이터 상태 조회"""
        try:
            await self.ensure_initialized()
            
            status = await self.coordinator.get_system_status()
            
            click.echo("🎬 멀티 계정 코디네이터 상태:")
            click.echo(f"   📊 상태: {status['coordinator_status']}")
            click.echo(f"   🔄 활성 작업: {status['resource_pool']['active_tasks']}개")
            click.echo(f"   📈 최대 동시 작업: {status['resource_pool']['max_concurrent_tasks']}개")
            click.echo(f"   📞 분당 API 호출: {status['resource_pool']['api_calls_this_minute']}/{status['resource_pool']['max_api_calls_per_minute']}")
            
            # 작업 통계
            task_stats = status['task_statistics']
            click.echo(f"\n📋 작업 통계:")
            click.echo(f"   📊 총 스케줄: {task_stats['total_scheduled']}개")
            click.echo(f"   ⏳ 대기 중: {task_stats['pending']}개")
            click.echo(f"   🚀 실행 중: {task_stats['running']}개")
            click.echo(f"   ✅ 완료: {task_stats['completed']}개")
            click.echo(f"   ❌ 실패: {task_stats['failed']}개")
            click.echo(f"   🚫 취소: {task_stats['cancelled']}개")
            
            # 실행 통계
            exec_stats = status['execution_stats']
            click.echo(f"\n⚡ 실행 통계:")
            click.echo(f"   📊 총 실행: {exec_stats['total_tasks_executed']}개")
            click.echo(f"   ✅ 성공: {exec_stats['successful_tasks']}개")
            click.echo(f"   ❌ 실패: {exec_stats['failed_tasks']}개")
            click.echo(f"   ⏱️ 평균 실행시간: {exec_stats['avg_execution_time']:.2f}초")
            
            click.echo(f"\n🔄 대기열 크기: {status['queue_size']}")
            click.echo(f"📅 마지막 업데이트: {status['last_update']}")
                        
        except Exception as e:
            click.echo(f"❌ 코디네이터 상태 조회 실패: {e}")
    
    async def schedule_task(
        self, 
        task_name: str, 
        account_id: Optional[str] = None,
        priority: str = "medium",
        delay_minutes: int = 0
    ) -> None:
        """작업 스케줄링"""
        try:
            await self.ensure_initialized()
            
            # 우선순위 매핑
            priority_map = {
                "critical": TaskPriority.CRITICAL,
                "high": TaskPriority.HIGH,
                "medium": TaskPriority.MEDIUM,
                "low": TaskPriority.LOW
            }
            
            task_priority = priority_map.get(priority.lower(), TaskPriority.MEDIUM)
            target_accounts = [AccountID(account_id)] if account_id else None
            
            # 작업 함수 매핑
            task_functions = {
                "portfolio_optimization": self.feature_manager.run_portfolio_optimization_for_all,
                "rebalancing": lambda accounts: self.feature_manager.execute_rebalancing_for_all(accounts, dry_run=False),
                "risk_analysis": self.feature_manager.run_risk_analysis_for_all,
                "performance_analysis": self.feature_manager.run_performance_analysis_for_all,
                "dca_strategy": self.feature_manager.run_dca_strategy_for_all,
                "tax_optimization": self.feature_manager.run_tax_optimization_for_all
            }
            
            if task_name not in task_functions:
                click.echo(f"❌ 지원하지 않는 작업: {task_name}")
                click.echo(f"📋 지원 작업: {', '.join(task_functions.keys())}")
                return
            
            function = task_functions[task_name]
            scheduled_time = datetime.now() if delay_minutes == 0 else None
            
            task_id = await self.coordinator.schedule_task(
                name=task_name,
                function=function,
                target_accounts=target_accounts,
                priority=task_priority,
                scheduled_time=scheduled_time
            )
            
            click.echo(f"✅ 작업 스케줄링 완료")
            click.echo(f"   📋 작업ID: {task_id}")
            click.echo(f"   🎯 작업명: {task_name}")
            click.echo(f"   📊 우선순위: {priority}")
            if account_id:
                click.echo(f"   🏢 대상 계정: {account_id}")
            else:
                click.echo(f"   🏢 대상: 모든 계정")
                        
        except Exception as e:
            click.echo(f"❌ 작업 스케줄링 실패: {e}")
    
    async def health_check(self) -> None:
        """시스템 상태 확인"""
        try:
            await self.ensure_initialized()
            
            click.echo("🏥 시스템 헬스체크 시작...")
            
            # 각 컴포넌트 헬스체크
            account_health = await self.account_manager.health_check()
            feature_health = await self.feature_manager.health_check()
            coordinator_health = await self.coordinator.health_check()
            
            click.echo("✅ 헬스체크 완료")
            
            click.echo("\n🏦 계정 관리자:")
            click.echo(f"   📊 상태: {account_health['status']}")
            click.echo(f"   🏢 총 계정: {account_health['total_accounts']}개")
            click.echo(f"   ✅ 활성 계정: {account_health['active_accounts']}개")
            
            click.echo("\n🎯 기능 관리자:")
            click.echo(f"   📊 상태: {feature_health['status']}")
            click.echo(f"   ⚙️ 기능 인스턴스: {feature_health['total_feature_instances']}개")
            
            click.echo("\n🎬 코디네이터:")
            click.echo(f"   📊 상태: {coordinator_health['status']}")
                        
        except Exception as e:
            click.echo(f"❌ 헬스체크 실패: {e}")


# CLI 인스턴스
_cli = EnhancedMultiAccountCLI()


@click.group()
def enhanced_multi_account():
    """KAIROS-1 Enhanced Multi-Account Management System"""
    pass


@enhanced_multi_account.command()
@click.option('-d', '--detailed', is_flag=True, help='상세 정보 표시')
def accounts(detailed):
    """계정 목록 조회"""
    asyncio.run(_cli.list_accounts(detailed))


@enhanced_multi_account.command()
@click.option('-a', '--account', help='특정 계정 ID')
def optimize(account):
    """포트폴리오 최적화 실행"""
    asyncio.run(_cli.portfolio_optimization(account))


@enhanced_multi_account.command()
@click.option('-a', '--account', help='특정 계정 ID')
@click.option('--live', is_flag=True, help='실제 거래 실행')
def rebalance(account, live):
    """리밸런싱 실행"""
    dry_run = not live
    asyncio.run(_cli.rebalance_all(account, dry_run))


@enhanced_multi_account.command()
@click.option('-a', '--account', help='특정 계정 ID')
def risk(account):
    """리스크 분석 실행"""
    asyncio.run(_cli.risk_analysis(account))


@enhanced_multi_account.command()
@click.option('-a', '--account', help='특정 계정 ID')
def performance(account):
    """성과 분석 실행"""
    asyncio.run(_cli.performance_analysis(account))


@enhanced_multi_account.command()
@click.option('-a', '--account', help='특정 계정 ID')
@click.option('--amount', type=float, help='투자 금액 (KRW)')
def dca(account, amount):
    """DCA+ 전략 실행"""
    asyncio.run(_cli.dca_strategy(account, amount))


@enhanced_multi_account.command()
@click.option('-a', '--account', help='특정 계정 ID')
def tax(account):
    """세금 최적화 분석"""
    asyncio.run(_cli.tax_optimization(account))


@enhanced_multi_account.command()
def analytics():
    """통합 분석 정보 조회"""
    asyncio.run(_cli.aggregate_analytics())


@enhanced_multi_account.command()
def status():
    """코디네이터 상태 조회"""
    asyncio.run(_cli.coordinator_status())


@enhanced_multi_account.command()
@click.argument('task_name')
@click.option('-a', '--account', help='특정 계정 ID')
@click.option('-p', '--priority', default='medium', help='우선순위 (critical/high/medium/low)')
@click.option('-d', '--delay', default=0, help='지연 시간 (분)')
def schedule(task_name, account, priority, delay):
    """작업 스케줄링"""
    asyncio.run(_cli.schedule_task(task_name, account, priority, delay))


@enhanced_multi_account.command()
def health():
    """시스템 헬스체크"""
    asyncio.run(_cli.health_check())


if __name__ == '__main__':
    enhanced_multi_account()