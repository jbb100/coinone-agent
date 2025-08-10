"""
Multi-Account Manager for KAIROS-1 System

여러 코인원 계정을 동시에 관리하는 시스템
"""

import asyncio
import json
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger
from dataclasses import dataclass, asdict
from decimal import Decimal

from .types import (
    AccountID, AccountName, AccountInfo, AccountStatus, RiskLevel,
    KRWAmount, Percentage, AssetSymbol, BalanceInfo, OrderInfo, PortfolioSnapshot
)
from .base_service import BaseService, ServiceConfig
from .exceptions import KairosException, ConfigurationException, APIException
from ..security.secrets_manager import get_api_key_manager
from ..trading.coinone_client import CoinoneClient


@dataclass
class AccountConfig:
    """개별 계정 설정"""
    account_id: AccountID
    account_name: AccountName
    description: str
    risk_level: RiskLevel
    initial_capital: KRWAmount
    max_investment: KRWAmount
    auto_rebalance: bool = True
    rebalance_frequency: str = "weekly"
    
    # 포트폴리오 설정
    core_allocation: float = 0.7  # 코어 자산 비중
    satellite_allocation: float = 0.3  # 위성 자산 비중
    cash_reserve: float = 0.1  # 현금 보유 비중
    
    # 리스크 관리
    max_position_size: float = 0.4  # 단일 자산 최대 비중
    stop_loss_threshold: Optional[float] = None
    
    # 실행 설정
    dry_run: bool = False
    enable_notifications: bool = True


class MultiAccountManager(BaseService):
    """멀티 계정 관리자"""
    
    def __init__(self, accounts_config_path: str = "config/accounts.json"):
        super().__init__(ServiceConfig(
            name="multi_account_manager",
            enabled=True,
            health_check_interval=300  # 5분마다 헬스체크
        ))
        
        self.accounts_config_path = Path(accounts_config_path)
        self.accounts: Dict[AccountID, AccountConfig] = {}
        self.clients: Dict[AccountID, CoinoneClient] = {}
        self.account_status: Dict[AccountID, AccountStatus] = {}
        
        # 성과 추적
        self.performance_data: Dict[AccountID, Dict[str, Any]] = {}
        
        # 동시성 제어
        self.account_locks: Dict[AccountID, asyncio.Lock] = {}
        
    async def initialize(self):
        """멀티 계정 관리자 초기화"""
        try:
            logger.info("🏦 멀티 계정 관리자 초기화 시작")
            
            # 설정 파일 로드
            await self._load_accounts_config()
            
            # API 클라이언트 초기화
            await self._initialize_clients()
            
            # 계정 상태 확인
            await self._check_all_accounts_health()
            
            logger.info(f"✅ 멀티 계정 관리자 초기화 완료: {len(self.accounts)}개 계정")
            
        except Exception as e:
            logger.error(f"❌ 멀티 계정 관리자 초기화 실패: {e}")
            raise ConfigurationException("multi_account_manager", str(e))
    
    async def _load_accounts_config(self):
        """계정 설정 파일 로드"""
        try:
            if not self.accounts_config_path.exists():
                # 기본 설정 파일 생성
                await self._create_default_config()
            
            with open(self.accounts_config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            for account_data in config_data.get('accounts', []):
                account_config = AccountConfig(**account_data)
                self.accounts[account_config.account_id] = account_config
                self.account_locks[account_config.account_id] = asyncio.Lock()
            
            logger.info(f"📋 {len(self.accounts)}개 계정 설정 로드 완료")
            
        except Exception as e:
            logger.error(f"❌ 계정 설정 로드 실패: {e}")
            raise ConfigurationException("accounts_config", str(e))
    
    async def _create_default_config(self):
        """기본 설정 파일 생성"""
        default_config = {
            "accounts": [
                {
                    "account_id": "account_001",
                    "account_name": "메인 계정",
                    "description": "주 투자 계정",
                    "risk_level": "moderate",
                    "initial_capital": 1000000.0,
                    "max_investment": 5000000.0,
                    "auto_rebalance": True,
                    "rebalance_frequency": "weekly",
                    "dry_run": True
                }
            ],
            "global_settings": {
                "concurrent_operations": 3,
                "health_check_interval": 300,
                "notification_channels": ["slack", "email"]
            }
        }
        
        # 디렉토리 생성
        self.accounts_config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.accounts_config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, ensure_ascii=False, indent=2)
        
        logger.info(f"📝 기본 계정 설정 파일 생성: {self.accounts_config_path}")
    
    async def _initialize_clients(self):
        """각 계정의 API 클라이언트 초기화"""
        api_key_manager = get_api_key_manager()
        
        for account_id, config in self.accounts.items():
            try:
                # API 키 조회
                api_keys = api_key_manager.get_api_keys(f"coinone_{account_id}")
                
                if not api_keys:
                    logger.warning(f"⚠️ 계정 {account_id}의 API 키 없음")
                    self.account_status[account_id] = AccountStatus.ERROR
                    continue
                
                # 클라이언트 생성
                client = CoinoneClient(
                    api_key=api_keys['api_key'],
                    secret_key=api_keys['secret_key'],
                    sandbox=config.dry_run
                )
                
                self.clients[account_id] = client
                self.account_status[account_id] = AccountStatus.ACTIVE
                
                logger.info(f"✅ 계정 {account_id} 클라이언트 초기화 완료")
                
            except Exception as e:
                logger.error(f"❌ 계정 {account_id} 클라이언트 초기화 실패: {e}")
                self.account_status[account_id] = AccountStatus.ERROR
    
    async def add_account(self, account_config: AccountConfig, 
                         api_key: str, secret_key: str) -> bool:
        """새 계정 추가"""
        try:
            logger.info(f"➕ 새 계정 추가: {account_config.account_id}")
            
            # API 키 저장
            api_key_manager = get_api_key_manager()
            success = api_key_manager.store_api_key(
                f"coinone_{account_config.account_id}",
                api_key,
                secret_key
            )
            
            if not success:
                raise APIException("API 키 저장 실패", "API_KEY_STORE_FAILED")
            
            # 계정 설정 추가
            self.accounts[account_config.account_id] = account_config
            self.account_locks[account_config.account_id] = asyncio.Lock()
            
            # 클라이언트 생성
            client = CoinoneClient(
                api_key=api_key,
                secret_key=secret_key,
                sandbox=account_config.dry_run
            )
            self.clients[account_config.account_id] = client
            self.account_status[account_config.account_id] = AccountStatus.ACTIVE
            
            # 설정 파일 업데이트
            await self._save_accounts_config()
            
            logger.info(f"✅ 계정 {account_config.account_id} 추가 완료")
            return True
            
        except Exception as e:
            logger.error(f"❌ 계정 추가 실패: {e}")
            return False
    
    async def remove_account(self, account_id: AccountID) -> bool:
        """계정 제거"""
        try:
            logger.info(f"➖ 계정 제거: {account_id}")
            
            if account_id not in self.accounts:
                logger.warning(f"⚠️ 존재하지 않는 계정: {account_id}")
                return False
            
            # 계정 비활성화
            self.account_status[account_id] = AccountStatus.INACTIVE
            
            # 리소스 정리
            if account_id in self.clients:
                del self.clients[account_id]
            
            if account_id in self.accounts:
                del self.accounts[account_id]
            
            if account_id in self.account_locks:
                del self.account_locks[account_id]
            
            # API 키 제거
            api_key_manager = get_api_key_manager()
            api_key_manager.delete_api_keys(f"coinone_{account_id}")
            
            # 설정 파일 업데이트
            await self._save_accounts_config()
            
            logger.info(f"✅ 계정 {account_id} 제거 완료")
            return True
            
        except Exception as e:
            logger.error(f"❌ 계정 제거 실패: {e}")
            return False
    
    async def get_account_info(self, account_id: AccountID) -> Optional[AccountInfo]:
        """계정 정보 조회"""
        try:
            if account_id not in self.accounts:
                return None
            
            config = self.accounts[account_id]
            client = self.clients.get(account_id)
            
            # 현재 포트폴리오 값 계산
            current_value = KRWAmount(Decimal('0'))
            total_return = Percentage(0.0)
            
            if client and self.account_status[account_id] == AccountStatus.ACTIVE:
                try:
                    balances = await asyncio.to_thread(client.get_balances)
                    # get_balances returns Dict[str, float], need to calculate KRW value
                    krw_value = Decimal('0')
                    
                    # 잔고가 있는 코인들만 필터링 (최소 임계값 설정)
                    MIN_BALANCE_THRESHOLD = 0.00001  # 최소 잔고 임계값
                    
                    for currency, balance in balances.items():
                        if currency == 'KRW':
                            krw_value += Decimal(str(balance))
                        elif balance > MIN_BALANCE_THRESHOLD:  # 잔고가 있는 코인만 처리
                            # For crypto assets, we need to get current price and multiply
                            try:
                                ticker = client.get_ticker(currency)
                                if ticker.get('result') == 'success':
                                    # Coinone API returns price in data.close_24h
                                    ticker_data = ticker.get('data', {})
                                    price_str = ticker_data.get('close_24h', '0')
                                    price = Decimal(str(price_str))
                                    krw_value += price * Decimal(str(balance))
                            except Exception:
                                # Skip if unable to get price
                                logger.debug(f"시세 조회 실패 - {currency}: 건너뜀")
                                pass
                    current_value = KRWAmount(krw_value)
                    
                    if config.initial_capital > 0:
                        total_return = Percentage(
                            float(Decimal(str(current_value)) - Decimal(str(config.initial_capital))) / float(config.initial_capital)
                        )
                except Exception as e:
                    logger.warning(f"⚠️ 계정 {account_id} 잔고 조회 실패: {e}")
            
            return AccountInfo(
                account_id=account_id,
                account_name=config.account_name,
                description=config.description,
                status=self.account_status[account_id],
                risk_level=config.risk_level,
                created_at=datetime.now(),  # TODO: 실제 생성 시간 저장
                last_updated=datetime.now(),
                api_key_id=f"coinone_{account_id}",
                initial_capital=config.initial_capital,
                max_investment=config.max_investment,
                auto_rebalance=config.auto_rebalance,
                current_value=current_value,
                total_return=total_return,
                last_rebalance=None  # TODO: 마지막 리밸런싱 시간 추적
            )
            
        except Exception as e:
            logger.error(f"❌ 계정 정보 조회 실패: {e}")
            return None
    
    async def get_all_accounts(self) -> List[AccountInfo]:
        """모든 계정 정보 조회"""
        accounts = []
        for account_id in self.accounts.keys():
            account_info = await self.get_account_info(account_id)
            if account_info:
                accounts.append(account_info)
        return accounts
    
    async def get_account_balance(self, account_id: AccountID) -> List[BalanceInfo]:
        """계정 잔고 조회"""
        try:
            if account_id not in self.clients:
                raise KairosException(f"계정 {account_id} 클라이언트 없음", "CLIENT_NOT_FOUND")
            
            async with self.account_locks[account_id]:
                client = self.clients[account_id]
                balances = await asyncio.to_thread(client.get_balances)
                
                # get_balances returns Dict[str, float] format: {currency: balance}
                balance_infos = []
                MIN_BALANCE_THRESHOLD = 0.00001
                
                for currency, balance in balances.items():
                    if balance > MIN_BALANCE_THRESHOLD:  # 잔고가 있는 것만
                        # Get KRW value for crypto assets
                        value_krw = KRWAmount(Decimal('0'))
                        if currency == 'KRW':
                            value_krw = KRWAmount(Decimal(str(balance)))
                        else:
                            try:
                                ticker = client.get_ticker(currency)
                                if ticker.get('result') == 'success':
                                    # Coinone API returns price in data.close_24h
                                    ticker_data = ticker.get('data', {})
                                    price_str = ticker_data.get('close_24h', '0')
                                    price = Decimal(str(price_str))
                                    value_krw = KRWAmount(price * Decimal(str(balance)))
                            except Exception as e:
                                logger.debug(f"Failed to get price for {currency}: {e}")
                                pass  # Skip if price unavailable
                        
                        balance_infos.append({
                            'asset': AssetSymbol(currency),
                            'total': Decimal(str(balance)),
                            'available': Decimal(str(balance)),  # Assuming all available for now
                            'locked': Decimal('0'),  # Not available in current API response
                            'value_krw': value_krw
                        })
                
                return balance_infos
                
        except Exception as e:
            logger.error(f"❌ 계정 {account_id} 잔고 조회 실패: {e}")
            raise APIException(f"계정 잔고 조회 실패: {e}", "BALANCE_FETCH_FAILED")
    
    async def _check_all_accounts_health(self):
        """모든 계정의 건강 상태 확인"""
        logger.info("🏥 모든 계정 건강 상태 확인 시작")
        
        health_check_tasks = [
            self._check_account_health(account_id) 
            for account_id in self.accounts.keys()
        ]
        
        results = await asyncio.gather(*health_check_tasks, return_exceptions=True)
        
        healthy_count = sum(1 for result in results if result is True)
        logger.info(f"🏥 계정 건강 상태 확인 완료: {healthy_count}/{len(results)}개 정상")
    
    async def _check_account_health(self, account_id: AccountID) -> bool:
        """개별 계정 건강 상태 확인"""
        try:
            if account_id not in self.clients:
                self.account_status[account_id] = AccountStatus.ERROR
                return False
            
            # API 연결 테스트
            client = self.clients[account_id]
            await asyncio.to_thread(client.get_ticker, 'BTC')
            
            self.account_status[account_id] = AccountStatus.ACTIVE
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ 계정 {account_id} 건강 상태 이상: {e}")
            self.account_status[account_id] = AccountStatus.ERROR
            return False
    
    async def _save_accounts_config(self):
        """계정 설정 파일 저장"""
        try:
            config_data = {
                "accounts": [
                    asdict(config) for config in self.accounts.values()
                ],
                "global_settings": {
                    "concurrent_operations": 3,
                    "health_check_interval": 300,
                    "notification_channels": ["slack", "email"]
                }
            }
            
            with open(self.accounts_config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2, default=str)
            
            logger.info("💾 계정 설정 파일 저장 완료")
            
        except Exception as e:
            logger.error(f"❌ 계정 설정 파일 저장 실패: {e}")
    
    async def get_aggregate_portfolio(self) -> Dict[str, Any]:
        """모든 계정의 통합 포트폴리오 정보"""
        try:
            total_value = KRWAmount(Decimal('0'))
            total_initial = KRWAmount(Decimal('0'))
            asset_totals: Dict[AssetSymbol, Decimal] = {}
            account_summaries = []
            
            for account_id in self.accounts.keys():
                if self.account_status[account_id] != AccountStatus.ACTIVE:
                    continue
                
                try:
                    balances = await self.get_account_balance(account_id)
                    config = self.accounts[account_id]
                    
                    account_value = sum(balance['value_krw'] for balance in balances)
                    total_value += account_value
                    total_initial += config.initial_capital
                    
                    # 자산별 합계
                    for balance in balances:
                        asset = balance['asset']
                        if asset in asset_totals:
                            asset_totals[asset] += balance['total']
                        else:
                            asset_totals[asset] = balance['total']
                    
                    account_summaries.append({
                        'account_id': account_id,
                        'account_name': config.account_name,
                        'current_value': float(account_value),
                        'return_rate': float((Decimal(str(account_value)) - Decimal(str(config.initial_capital))) / Decimal(str(config.initial_capital))) if config.initial_capital > 0 else 0.0
                    })
                    
                except Exception as e:
                    logger.warning(f"⚠️ 계정 {account_id} 포트폴리오 조회 실패: {e}")
                    continue
            
            total_return = float((total_value - total_initial) / total_initial) if total_initial > 0 else 0.0
            
            return {
                'total_value': float(total_value),
                'total_return': total_return,
                'active_accounts': len([a for a in account_summaries]),
                'account_summaries': account_summaries,
                'asset_distribution': {str(asset): float(amount) for asset, amount in asset_totals.items()},
                'last_updated': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ 통합 포트폴리오 조회 실패: {e}")
            return {}
    
    async def start(self):
        """서비스 시작"""
        await self.initialize()
        logger.info("🏦 멀티 계정 관리자 시작")
    
    async def stop(self):
        """서비스 중지"""
        # 클라이언트 정리
        for client in self.clients.values():
            # 필요시 연결 정리 작업
            pass
        logger.info("🏦 멀티 계정 관리자 중지")
    
    async def health_check(self) -> Dict[str, Any]:
        """헬스체크"""
        await self._check_all_accounts_health()
        
        active_accounts = len([
            account_id for account_id, status in self.account_status.items()
            if status == AccountStatus.ACTIVE
        ])
        
        return {
            'service': 'multi_account_manager',
            'status': 'healthy' if active_accounts > 0 else 'degraded',
            'total_accounts': len(self.accounts),
            'active_accounts': active_accounts,
            'last_check': datetime.now().isoformat()
        }


# 전역 멀티 계정 관리자 인스턴스
_multi_account_manager: Optional[MultiAccountManager] = None

def get_multi_account_manager() -> MultiAccountManager:
    """멀티 계정 관리자 인스턴스 반환"""
    global _multi_account_manager
    if _multi_account_manager is None:
        _multi_account_manager = MultiAccountManager()
    return _multi_account_manager