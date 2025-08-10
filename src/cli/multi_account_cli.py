"""
Multi-Account CLI Interface for KAIROS-1 System

멀티 계정 관리를 위한 CLI 명령어 인터페이스
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
from src.core.multi_portfolio_manager import get_multi_portfolio_manager
from src.core.multi_rebalancing_engine import (
    get_multi_rebalancing_engine, RebalanceScheduleType
)
from src.core.multi_account_feature_manager import get_multi_account_feature_manager
from src.core.multi_account_coordinator import get_multi_account_coordinator, TaskPriority
from src.core.types import AccountID, AccountName, RiskLevel, KRWAmount


class MultiAccountCLI:
    """멀티 계정 관리 CLI"""
    
    def __init__(self):
        self.account_manager = get_multi_account_manager()
        self.portfolio_manager = get_multi_portfolio_manager()
        self.rebalancing_engine = get_multi_rebalancing_engine()
        self.feature_manager = get_multi_account_feature_manager()
        self.coordinator = get_multi_account_coordinator()
        self.initialized = False
    
    async def ensure_initialized(self):
        """초기화 확인"""
        if not self.initialized:
            try:
                await self.account_manager.initialize()
                await self.portfolio_manager.initialize()
                await self.rebalancing_engine.initialize()
                await self.feature_manager.initialize()
                await self.coordinator.initialize()
                self.initialized = True
            except Exception as e:
                logger.error(f"❌ 초기화 실패: {e}")
                raise
    
    async def list_accounts(self, detailed: bool = False) -> None:
        """계정 목록 조회"""
        try:
            await self.ensure_initialized()
            accounts = await self.account_manager.get_all_accounts()
            
            if not accounts:
                click.echo("📭 등록된 계정이 없습니다.")
                return
            
            if detailed:
                # 상세 정보 표시
                for account in accounts:
                    click.echo(f"\n🏦 계정: {account['account_name']} ({account['account_id']})")
                    status_str = account['status'].value if hasattr(account['status'], 'value') else str(account['status'])
                    risk_str = account['risk_level'].value if hasattr(account['risk_level'], 'value') else str(account['risk_level'])
                    click.echo(f"   상태: {status_str}")
                    click.echo(f"   리스크 수준: {risk_str}")
                    click.echo(f"   초기 자본: ₩{account['initial_capital']:,.0f}")
                    click.echo(f"   현재 가치: ₩{account['current_value']:,.0f}")
                    click.echo(f"   수익률: {account['total_return']:.2%}")
                    click.echo(f"   자동 리밸런싱: {'활성화' if account['auto_rebalance'] else '비활성화'}")
            else:
                # 테이블 형태로 표시
                table_data = []
                for account in accounts:
                    status_str = account['status'].value if hasattr(account['status'], 'value') else str(account['status'])
                    risk_str = account['risk_level'].value if hasattr(account['risk_level'], 'value') else str(account['risk_level'])
                    
                    status_emoji = {
                        AccountStatus.ACTIVE: "✅",
                        AccountStatus.INACTIVE: "⏸️",
                        AccountStatus.SUSPENDED: "🚫", 
                        AccountStatus.ERROR: "❌"
                    }.get(account['status'], "❓")
                    
                    table_data.append([
                        account['account_id'],
                        account['account_name'],
                        f"{status_emoji} {status_str}",
                        risk_str,
                        f"₩{account['current_value']:,.0f}",
                        f"{account['total_return']:+.2%}",
                        "✅" if account['auto_rebalance'] else "❌"
                    ])
                
                headers = ["계정ID", "계정명", "상태", "리스크", "현재가치", "수익률", "자동리밸런싱"]
                click.echo(tabulate(table_data, headers=headers, tablefmt="grid"))
                
        except Exception as e:
            click.echo(f"❌ 계정 목록 조회 실패: {e}")
    
    async def add_account(self, account_id: str, account_name: str, 
                         api_key: str, secret_key: str, 
                         risk_level: str = "moderate",
                         initial_capital: float = 1000000.0,
                         max_investment: float = 5000000.0,
                         dry_run: bool = True) -> None:
        """새 계정 추가"""
        try:
            await self.ensure_initialized()
            
            # 계정 설정 생성
            config = AccountConfig(
                account_id=AccountID(account_id),
                account_name=AccountName(account_name),
                description=f"{account_name} 투자 계정",
                risk_level=RiskLevel(risk_level),
                initial_capital=KRWAmount(initial_capital),
                max_investment=KRWAmount(max_investment),
                dry_run=dry_run
            )
            
            success = await self.account_manager.add_account(config, api_key, secret_key)
            
            if success:
                click.echo(f"✅ 계정 '{account_name}' ({account_id}) 추가 완료")
                
                # 리밸런싱 스케줄 자동 추가
                await self.rebalancing_engine.add_account_schedule(
                    AccountID(account_id),
                    RebalanceScheduleType.WEEKLY,
                    "0 9 * * 1"  # 매주 월요일 9시
                )
                click.echo("📅 주간 리밸런싱 스케줄 추가됨")
            else:
                click.echo(f"❌ 계정 추가 실패")
                
        except Exception as e:
            click.echo(f"❌ 계정 추가 실패: {e}")
    
    async def remove_account(self, account_id: str) -> None:
        """계정 제거"""
        try:
            await self.ensure_initialized()
            
            # 확인 요청
            if not click.confirm(f"계정 '{account_id}'를 정말 제거하시겠습니까?"):
                click.echo("❌ 계정 제거 취소됨")
                return
            
            success = await self.account_manager.remove_account(AccountID(account_id))
            
            if success:
                # 리밸런싱 스케줄도 제거
                await self.rebalancing_engine.remove_account_schedule(AccountID(account_id))
                click.echo(f"✅ 계정 '{account_id}' 제거 완료")
            else:
                click.echo(f"❌ 계정 제거 실패")
                
        except Exception as e:
            click.echo(f"❌ 계정 제거 실패: {e}")
    
    async def show_portfolio(self, account_id: Optional[str] = None) -> None:
        """포트폴리오 현황 조회"""
        try:
            await self.ensure_initialized()
            
            if account_id:
                # 특정 계정 포트폴리오
                balances = await self.account_manager.get_account_balance(AccountID(account_id))
                
                if not balances:
                    click.echo(f"📭 계정 '{account_id}'의 잔고 정보가 없습니다.")
                    return
                
                click.echo(f"💼 계정 '{account_id}' 포트폴리오:")
                
                table_data = []
                total_value = 0
                
                for balance in balances:
                    # Handle both dict and object formats
                    if isinstance(balance, dict):
                        value_krw = float(balance['value_krw'])
                        asset = balance['asset']
                        total_amount = balance['total']
                        available = balance['available']
                    else:
                        value_krw = float(balance.value_krw)
                        asset = balance.asset
                        total_amount = balance.total
                        available = balance.available
                    
                    total_value += value_krw
                    
                    table_data.append([
                        asset,
                        f"{total_amount:,.6f}",
                        f"{available:,.6f}",
                        f"₩{value_krw:,.0f}"
                    ])
                
                # 비중 계산 및 추가
                for i, balance in enumerate(balances):
                    if isinstance(balance, dict):
                        weight = float(balance['value_krw']) / total_value * 100 if total_value > 0 else 0
                    else:
                        weight = float(balance.value_krw) / total_value * 100 if total_value > 0 else 0
                    table_data[i].append(f"{weight:.1f}%")
                
                headers = ["자산", "총 보유량", "사용가능", "가치(KRW)", "비중"]
                click.echo(tabulate(table_data, headers=headers, tablefmt="grid"))
                click.echo(f"\n💰 총 포트폴리오 가치: ₩{total_value:,.0f}")
                
            else:
                # 통합 포트폴리오
                aggregate = await self.account_manager.get_aggregate_portfolio()
                
                if not aggregate:
                    click.echo("📭 포트폴리오 정보가 없습니다.")
                    return
                
                click.echo("🏦 통합 포트폴리오 현황:")
                click.echo(f"💰 총 자산 가치: ₩{aggregate['total_value']:,.0f}")
                click.echo(f"📈 총 수익률: {aggregate['total_return']:+.2%}")
                click.echo(f"🏢 활성 계정 수: {aggregate['active_accounts']}개")
                
                if 'account_summaries' in aggregate:
                    click.echo("\n📊 계정별 요약:")
                    table_data = []
                    for summary in aggregate['account_summaries']:
                        table_data.append([
                            summary['account_id'],
                            summary['account_name'],
                            f"₩{summary['current_value']:,.0f}",
                            f"{summary['return_rate']:+.2%}"
                        ])
                    
                    headers = ["계정ID", "계정명", "현재가치", "수익률"]
                    click.echo(tabulate(table_data, headers=headers, tablefmt="grid"))
                
        except Exception as e:
            click.echo(f"❌ 포트폴리오 조회 실패: {e}")
    
    async def rebalance(self, account_id: Optional[str] = None, force: bool = False) -> None:
        """리밸런싱 실행"""
        try:
            await self.ensure_initialized()
            
            if account_id:
                click.echo(f"⚖️ 계정 '{account_id}' 리밸런싱 시작...")
                result = await self.rebalancing_engine.trigger_manual_rebalance(
                    AccountID(account_id), force
                )
                
                if 'single_account' in result:
                    account_result = result['single_account']
                    if account_result['action'] == 'completed':
                        click.echo(f"✅ 리밸런싱 완료: {account_result['orders_count']}개 주문 실행")
                    elif account_result['action'] == 'skipped':
                        click.echo(f"⏭️ 리밸런싱 스킵: {account_result['reason']}")
                    else:
                        click.echo(f"❌ 리밸런싱 실패: {account_result.get('error', 'Unknown error')}")
            else:
                click.echo("⚖️ 전체 계정 리밸런싱 시작...")
                result = await self.rebalancing_engine.trigger_manual_rebalance(force=force)
                
                if 'all_accounts' in result:
                    results = result['all_accounts']
                    completed = len([r for r in results if isinstance(r, dict) and r.get('action') == 'completed'])
                    failed = len([r for r in results if isinstance(r, dict) and r.get('action') == 'failed'])
                    skipped = len([r for r in results if isinstance(r, dict) and r.get('action') == 'skipped'])
                    
                    click.echo(f"✅ 리밸런싱 완료: 성공 {completed}개, 실패 {failed}개, 스킵 {skipped}개")
                
        except Exception as e:
            click.echo(f"❌ 리밸런싱 실패: {e}")
    
    async def show_schedules(self) -> None:
        """리밸런싱 스케줄 현황"""
        try:
            await self.ensure_initialized()
            status = await self.rebalancing_engine.get_schedule_status()
            
            click.echo("📅 리밸런싱 스케줄 현황:")
            click.echo(f"   총 스케줄: {status['total_schedules']}개")
            click.echo(f"   활성 스케줄: {status['enabled_schedules']}개")
            click.echo(f"   실행 중 작업: {status['running_tasks']}개")
            click.echo(f"   현재 시장 상황: {status['current_market_season']}")
            
            if 'statistics' in status:
                stats = status['statistics']
                click.echo(f"\n📊 실행 통계:")
                click.echo(f"   총 실행 횟수: {stats['total_runs']}회")
                click.echo(f"   성공: {stats['successful_runs']}회")
                click.echo(f"   실패: {stats['failed_runs']}회")
                
                if stats['last_successful_run']:
                    click.echo(f"   마지막 성공: {stats['last_successful_run']}")
            
            if 'schedules' in status and status['schedules']:
                click.echo("\n📋 스케줄 목록:")
                table_data = []
                for schedule in status['schedules']:
                    table_data.append([
                        schedule['account_id'],
                        schedule['schedule_type'],
                        "✅" if schedule['enabled'] else "❌",
                        schedule['next_run'][:16] if schedule['next_run'] else "N/A",
                        schedule['last_run'][:16] if schedule['last_run'] else "N/A"
                    ])
                
                headers = ["계정ID", "스케줄타입", "활성화", "다음실행", "마지막실행"]
                click.echo(tabulate(table_data, headers=headers, tablefmt="grid"))
                
        except Exception as e:
            click.echo(f"❌ 스케줄 현황 조회 실패: {e}")
    
    async def health_check(self) -> None:
        """시스템 헬스체크"""
        try:
            await self.ensure_initialized()
            
            # 각 서비스 헬스체크
            account_health = await self.account_manager.health_check()
            portfolio_health = await self.portfolio_manager.health_check()
            rebalancing_health = await self.rebalancing_engine.health_check()
            
            click.echo("🏥 시스템 헬스체크 결과:")
            
            services = [
                ("멀티 계정 관리자", account_health),
                ("멀티 포트폴리오 관리자", portfolio_health),
                ("리밸런싱 엔진", rebalancing_health)
            ]
            
            for name, health in services:
                status_emoji = "✅" if health['status'] == 'healthy' else "⚠️"
                click.echo(f"   {status_emoji} {name}: {health['status']}")
                
                # 상세 정보 표시
                if 'active_accounts' in health:
                    click.echo(f"      활성 계정: {health['active_accounts']}개")
                if 'total_accounts' in health:
                    click.echo(f"      총 계정: {health['total_accounts']}개")
                    
        except Exception as e:
            click.echo(f"❌ 헬스체크 실패: {e}")


# CLI 인스턴스
cli = MultiAccountCLI()


# Click CLI 명령어들
@click.group()
def multi_account():
    """KAIROS-1 멀티 계정 관리 CLI"""
    pass


@multi_account.command()
@click.option('--detailed', '-d', is_flag=True, help='상세 정보 표시')
def accounts(detailed):
    """계정 목록 조회"""
    asyncio.run(cli.list_accounts(detailed))


@multi_account.command()
@click.argument('account_id')
@click.argument('account_name')
@click.argument('api_key')
@click.argument('secret_key')
@click.option('--risk-level', default='moderate', type=click.Choice(['conservative', 'moderate', 'aggressive']))
@click.option('--initial-capital', default=1000000.0, type=float)
@click.option('--max-investment', default=5000000.0, type=float)
@click.option('--dry-run/--live', default=True)
def add(account_id, account_name, api_key, secret_key, risk_level, initial_capital, max_investment, dry_run):
    """새 계정 추가"""
    asyncio.run(cli.add_account(
        account_id, account_name, api_key, secret_key,
        risk_level, initial_capital, max_investment, dry_run
    ))


@multi_account.command()
@click.argument('account_id')
def remove(account_id):
    """계정 제거"""
    asyncio.run(cli.remove_account(account_id))


@multi_account.command()
@click.option('--account', '-a', help='특정 계정 ID')
def portfolio(account):
    """포트폴리오 현황 조회"""
    asyncio.run(cli.show_portfolio(account))


@multi_account.command()
@click.option('--account', '-a', help='특정 계정 ID')
@click.option('--force', '-f', is_flag=True, help='강제 실행')
def rebalance(account, force):
    """리밸런싱 실행"""
    asyncio.run(cli.rebalance(account, force))


@multi_account.command()
def schedules():
    """리밸런싱 스케줄 현황"""
    asyncio.run(cli.show_schedules())


@multi_account.command()
def health():
    """시스템 헬스체크"""
    asyncio.run(cli.health_check())


if __name__ == '__main__':
    multi_account()