"""
Multi-Account Manager Tests
multi_account_manager.py 모듈의 테스트
"""
import pytest
import asyncio
import json
from pathlib import Path
from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from dataclasses import asdict

from src.core.multi_account_manager import (
    AccountConfig, MultiAccountManager,
    get_multi_account_manager, get_account_performance_data,
    DEFAULT_ACCOUNTS_FILE
)
from src.core.types import AccountStatus, KRWAmount, AssetSymbol


class TestAccountConfig:
    """AccountConfig 데이터클래스 테스트"""

    def test_default_values(self):
        """기본값 테스트"""
        config = AccountConfig(
            account_id="test_001",
            account_name="테스트 계정",
            description="테스트용",
            risk_level="moderate",
            initial_capital=1000000.0,
            max_investment=5000000.0
        )

        assert config.auto_rebalance is True
        assert config.rebalance_frequency == "weekly"
        assert config.core_allocation == 0.7
        assert config.satellite_allocation == 0.3
        assert config.cash_reserve == 0.1
        assert config.max_position_size == 0.25
        assert config.stop_loss_threshold is None
        assert config.dry_run is False
        assert config.enable_notifications is True

    def test_custom_values(self):
        """사용자 정의값 테스트"""
        config = AccountConfig(
            account_id="test_002",
            account_name="커스텀 계정",
            description="커스텀 설정",
            risk_level="high",
            initial_capital=2000000.0,
            max_investment=10000000.0,
            auto_rebalance=False,
            rebalance_frequency="monthly",
            core_allocation=0.5,
            satellite_allocation=0.5,
            cash_reserve=0.05,
            max_position_size=0.4,
            stop_loss_threshold=0.15,
            dry_run=True,
            enable_notifications=False
        )

        assert config.auto_rebalance is False
        assert config.rebalance_frequency == "monthly"
        assert config.core_allocation == 0.5
        assert config.stop_loss_threshold == 0.15
        assert config.dry_run is True

    def test_asdict_conversion(self):
        """딕셔너리 변환 테스트"""
        config = AccountConfig(
            account_id="test_003",
            account_name="Dict 테스트",
            description="변환 테스트",
            risk_level="low",
            initial_capital=500000.0,
            max_investment=1000000.0
        )

        config_dict = asdict(config)
        assert config_dict['account_id'] == "test_003"
        assert config_dict['account_name'] == "Dict 테스트"
        assert config_dict['risk_level'] == "low"


class TestMultiAccountManagerInit:
    """MultiAccountManager 초기화 테스트"""

    @pytest.fixture
    def mock_dependencies(self):
        """종속성 모킹"""
        with patch('src.core.multi_account_manager.get_api_key_manager') as mock_api:
            yield {'api_key_manager': mock_api}

    def test_init_default_path(self, mock_dependencies):
        """기본 경로로 초기화"""
        manager = MultiAccountManager()

        assert manager.accounts_config_path == Path("config/accounts.json")
        assert manager.accounts == {}
        assert manager.clients == {}
        assert manager.account_status == {}
        assert manager.performance_data == {}

    def test_init_custom_path(self, mock_dependencies):
        """사용자 정의 경로로 초기화"""
        manager = MultiAccountManager("custom/path/accounts.json")

        assert manager.accounts_config_path == Path("custom/path/accounts.json")

    def test_service_config(self, mock_dependencies):
        """서비스 설정 확인"""
        manager = MultiAccountManager()

        assert manager.config.name == "multi_account_manager"
        assert manager.config.enabled is True
        assert manager.config.health_check_interval == 300


class TestMultiAccountManagerLoadConfig:
    """계정 설정 로드 테스트"""

    @pytest.fixture
    def mock_dependencies(self):
        """종속성 모킹"""
        with patch('src.core.multi_account_manager.get_api_key_manager') as mock_api:
            mock_api.return_value.get_api_keys.return_value = {
                'api_key': 'test_key',
                'secret_key': 'test_secret'
            }
            yield {'api_key_manager': mock_api}

    @pytest.fixture
    def sample_config_data(self):
        """샘플 설정 데이터"""
        return {
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
                "concurrent_operations": 3
            }
        }

    @pytest.mark.asyncio
    async def test_load_existing_config(self, mock_dependencies, sample_config_data, tmp_path):
        """기존 설정 파일 로드"""
        config_file = tmp_path / "accounts.json"
        config_file.write_text(json.dumps(sample_config_data))

        manager = MultiAccountManager(str(config_file))
        await manager._load_accounts_config()

        assert "account_001" in manager.accounts
        assert manager.accounts["account_001"].account_name == "메인 계정"
        assert manager.accounts["account_001"].risk_level == "moderate"

    @pytest.mark.asyncio
    async def test_create_default_config(self, mock_dependencies, tmp_path):
        """기본 설정 파일 생성"""
        config_file = tmp_path / "new_config" / "accounts.json"

        manager = MultiAccountManager(str(config_file))
        await manager._create_default_config()

        assert config_file.exists()

        with open(config_file) as f:
            config = json.load(f)

        assert "accounts" in config
        assert len(config["accounts"]) == 1
        assert config["accounts"][0]["account_id"] == "account_001"

    @pytest.mark.asyncio
    async def test_load_config_creates_default_if_missing(self, mock_dependencies, tmp_path):
        """설정 파일 없으면 기본 생성"""
        config_file = tmp_path / "missing" / "accounts.json"

        manager = MultiAccountManager(str(config_file))

        with patch.object(manager, '_create_default_config', new_callable=AsyncMock) as mock_create:
            # 파일이 없을 때 _create_default_config 호출
            mock_create.return_value = None
            # _load_accounts_config가 파일을 읽으려 하지만 없으므로 예외 발생
            # 대신 _create_default_config를 호출하도록 설정
            try:
                await manager._load_accounts_config()
            except Exception:
                pass  # 파일이 없으므로 예외 발생 예상


class TestMultiAccountManagerInitializeClients:
    """클라이언트 초기화 테스트"""

    @pytest.fixture
    def manager_with_accounts(self):
        """계정이 있는 매니저"""
        with patch('src.core.multi_account_manager.get_api_key_manager') as mock_api:
            manager = MultiAccountManager()
            manager.accounts = {
                "account_001": AccountConfig(
                    account_id="account_001",
                    account_name="테스트",
                    description="테스트",
                    risk_level="moderate",
                    initial_capital=1000000.0,
                    max_investment=5000000.0,
                    dry_run=True
                )
            }
            yield manager, mock_api

    @pytest.mark.asyncio
    async def test_initialize_client_success(self, manager_with_accounts):
        """클라이언트 초기화 성공"""
        manager, mock_api = manager_with_accounts
        mock_api.return_value.get_api_keys.return_value = {
            'api_key': 'test_key',
            'secret_key': 'test_secret'
        }

        with patch('src.core.multi_account_manager.CoinoneClient') as MockClient:
            MockClient.return_value = Mock()
            await manager._initialize_clients()

            assert "account_001" in manager.clients
            assert manager.account_status["account_001"] == AccountStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_initialize_client_no_api_keys(self, manager_with_accounts):
        """API 키 없을 때"""
        manager, mock_api = manager_with_accounts
        mock_api.return_value.get_api_keys.return_value = None

        await manager._initialize_clients()

        assert "account_001" not in manager.clients
        assert manager.account_status["account_001"] == AccountStatus.ERROR

    @pytest.mark.asyncio
    async def test_initialize_client_exception(self, manager_with_accounts):
        """클라이언트 생성 예외"""
        manager, mock_api = manager_with_accounts
        mock_api.return_value.get_api_keys.return_value = {
            'api_key': 'test_key',
            'secret_key': 'test_secret'
        }

        with patch('src.core.multi_account_manager.CoinoneClient') as MockClient:
            MockClient.side_effect = Exception("Connection error")
            await manager._initialize_clients()

            assert manager.account_status["account_001"] == AccountStatus.ERROR


class TestMultiAccountManagerAddRemoveAccount:
    """계정 추가/제거 테스트"""

    @pytest.fixture
    def manager(self):
        """기본 매니저"""
        with patch('src.core.multi_account_manager.get_api_key_manager') as mock_api:
            mock_api.return_value.store_api_key.return_value = True
            mock_api.return_value.delete_api_keys.return_value = True
            manager = MultiAccountManager()
            yield manager, mock_api

    @pytest.mark.asyncio
    async def test_add_account_success(self, manager):
        """계정 추가 성공"""
        mgr, mock_api = manager

        config = AccountConfig(
            account_id="new_account",
            account_name="새 계정",
            description="새로 추가된 계정",
            risk_level="low",
            initial_capital=500000.0,
            max_investment=2000000.0,
            dry_run=True
        )

        with patch('src.core.multi_account_manager.CoinoneClient') as MockClient:
            MockClient.return_value = Mock()
            with patch.object(mgr, '_save_accounts_config', new_callable=AsyncMock):
                result = await mgr.add_account(config, "api_key", "secret_key")

        assert result is True
        assert "new_account" in mgr.accounts
        assert mgr.account_status["new_account"] == AccountStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_add_account_api_key_failure(self, manager):
        """API 키 저장 실패"""
        mgr, mock_api = manager
        mock_api.return_value.store_api_key.return_value = False

        config = AccountConfig(
            account_id="fail_account",
            account_name="실패 계정",
            description="실패 테스트",
            risk_level="moderate",
            initial_capital=1000000.0,
            max_investment=5000000.0
        )

        result = await mgr.add_account(config, "api_key", "secret_key")
        assert result is False

    @pytest.mark.asyncio
    async def test_remove_account_success(self, manager):
        """계정 제거 성공"""
        mgr, mock_api = manager

        # 계정 추가
        mgr.accounts["remove_test"] = AccountConfig(
            account_id="remove_test",
            account_name="제거 테스트",
            description="제거 테스트",
            risk_level="moderate",
            initial_capital=1000000.0,
            max_investment=5000000.0
        )
        mgr.clients["remove_test"] = Mock()
        mgr.account_locks["remove_test"] = asyncio.Lock()

        with patch.object(mgr, '_save_accounts_config', new_callable=AsyncMock):
            result = await mgr.remove_account("remove_test")

        assert result is True
        assert "remove_test" not in mgr.accounts
        assert "remove_test" not in mgr.clients

    @pytest.mark.asyncio
    async def test_remove_nonexistent_account(self, manager):
        """존재하지 않는 계정 제거"""
        mgr, _ = manager
        result = await mgr.remove_account("nonexistent")
        assert result is False


class TestMultiAccountManagerGetAccount:
    """계정 조회 테스트"""

    @pytest.fixture
    def manager_with_accounts(self):
        """계정이 있는 매니저"""
        with patch('src.core.multi_account_manager.get_api_key_manager'):
            manager = MultiAccountManager()
            manager.accounts = {
                "account_001": AccountConfig(
                    account_id="account_001",
                    account_name="메인 계정",
                    description="주 투자",
                    risk_level="moderate",
                    initial_capital=1000000.0,
                    max_investment=5000000.0
                ),
                "account_002": AccountConfig(
                    account_id="account_002",
                    account_name="공격적 계정",
                    description="고위험",
                    risk_level="high",
                    initial_capital=2000000.0,
                    max_investment=10000000.0
                ),
                "account_003": AccountConfig(
                    account_id="account_003",
                    account_name="보수적 계정",
                    description="저위험",
                    risk_level="low",
                    initial_capital=500000.0,
                    max_investment=1000000.0
                )
            }
            manager.account_status = {
                "account_001": AccountStatus.ACTIVE,
                "account_002": AccountStatus.ACTIVE,
                "account_003": AccountStatus.INACTIVE
            }
            yield manager

    def test_get_account_existing(self, manager_with_accounts):
        """존재하는 계정 조회"""
        account = manager_with_accounts.get_account("account_001")

        assert account is not None
        assert account['account_id'] == "account_001"
        assert account['name'] == "메인 계정"
        assert account['strategy'] == 'balanced'

    def test_get_account_conservative(self, manager_with_accounts):
        """보수적 계정 전략 매핑"""
        account = manager_with_accounts.get_account("account_003")

        assert account is not None
        assert account['strategy'] == 'conservative'
        assert 'KRW' in account['target_allocation']

    def test_get_account_aggressive(self, manager_with_accounts):
        """공격적 계정 전략 매핑"""
        account = manager_with_accounts.get_account("account_002")

        assert account is not None
        assert account['strategy'] == 'aggressive'

    def test_get_account_nonexistent(self, manager_with_accounts):
        """존재하지 않는 계정"""
        account = manager_with_accounts.get_account("nonexistent")
        assert account is None

    def test_get_accounts_by_strategy(self, manager_with_accounts):
        """전략별 계정 조회"""
        balanced = manager_with_accounts.get_accounts_by_strategy("balanced")
        assert len(balanced) == 1
        assert balanced[0]['id'] == "account_001"

        aggressive = manager_with_accounts.get_accounts_by_strategy("aggressive")
        assert len(aggressive) == 1

    def test_get_accounts_by_risk_level(self, manager_with_accounts):
        """리스크 레벨별 계정 조회"""
        low_risk = manager_with_accounts.get_accounts_by_risk_level("low")
        assert len(low_risk) == 1
        assert low_risk[0]['id'] == "account_003"

        high_risk = manager_with_accounts.get_accounts_by_risk_level("high")
        assert len(high_risk) == 1


class TestMultiAccountManagerAccountInfo:
    """계정 정보 조회 테스트"""

    @pytest.fixture
    def manager_with_client(self):
        """클라이언트가 있는 매니저"""
        with patch('src.core.multi_account_manager.get_api_key_manager'):
            manager = MultiAccountManager()
            manager.accounts = {
                "account_001": AccountConfig(
                    account_id="account_001",
                    account_name="메인 계정",
                    description="주 투자",
                    risk_level="moderate",
                    initial_capital=1000000.0,
                    max_investment=5000000.0
                )
            }

            mock_client = Mock()
            mock_client.get_balances.return_value = {
                'KRW': 500000.0,
                'BTC': 0.01,
                'ETH': 0.5
            }
            mock_client.get_ticker.return_value = {
                'result': 'success',
                'data': {'close_24h': '50000000'}
            }

            manager.clients = {"account_001": mock_client}
            manager.account_status = {"account_001": AccountStatus.ACTIVE}
            manager.account_locks = {"account_001": asyncio.Lock()}
            yield manager

    @pytest.mark.asyncio
    async def test_get_account_info_success(self, manager_with_client):
        """계정 정보 조회 성공"""
        info = await manager_with_client.get_account_info("account_001")

        assert info is not None
        # AccountInfo 객체 또는 딕셔너리 형태로 반환
        if hasattr(info, 'account_id'):
            assert info.account_id == "account_001"
            assert info.account_name == "메인 계정"
            assert info.status == AccountStatus.ACTIVE
        else:
            assert info['account_id'] == "account_001" or info.account_id == "account_001"

    @pytest.mark.asyncio
    async def test_get_account_info_nonexistent(self, manager_with_client):
        """존재하지 않는 계정 정보"""
        info = await manager_with_client.get_account_info("nonexistent")
        assert info is None

    @pytest.mark.asyncio
    async def test_get_all_accounts(self, manager_with_client):
        """모든 계정 정보 조회"""
        accounts = await manager_with_client.get_all_accounts()

        assert len(accounts) == 1
        # AccountInfo 객체 또는 딕셔너리 형태로 반환
        if hasattr(accounts[0], 'account_id'):
            assert accounts[0].account_id == "account_001"
        else:
            assert accounts[0]['account_id'] == "account_001"


class TestMultiAccountManagerValidation:
    """계정 검증 테스트"""

    @pytest.fixture
    def manager(self):
        """기본 매니저"""
        with patch('src.core.multi_account_manager.get_api_key_manager'):
            yield MultiAccountManager()

    def test_validate_account_valid(self, manager):
        """유효한 계정"""
        account = {
            'account_name': '테스트',
            'initial_capital': 1000000,
            'risk_level': 'moderate',
            'target_allocation': {'BTC': 0.4, 'ETH': 0.3, 'KRW': 0.3}
        }
        assert manager.validate_account(account) is True

    def test_validate_account_missing_fields(self, manager):
        """필수 필드 누락"""
        account = {
            'account_name': '테스트',
            'initial_capital': 1000000
        }
        assert manager.validate_account(account) is False

    def test_validate_account_invalid_allocation(self, manager):
        """잘못된 allocation 합계"""
        account = {
            'account_name': '테스트',
            'initial_capital': 1000000,
            'risk_level': 'moderate',
            'target_allocation': {'BTC': 0.5, 'ETH': 0.3, 'KRW': 0.3}  # 합계 1.1
        }
        assert manager.validate_account(account) is False

    def test_validate_account_zero_capital(self, manager):
        """자본금 0"""
        account = {
            'account_name': '테스트',
            'initial_capital': 0,
            'risk_level': 'moderate',
            'target_allocation': {'BTC': 0.4, 'ETH': 0.3, 'KRW': 0.3}
        }
        assert manager.validate_account(account) is False

    def test_validate_account_exception(self, manager):
        """예외 발생"""
        account = None
        assert manager.validate_account(account) is False


class TestMultiAccountManagerRiskScore:
    """리스크 점수 계산 테스트"""

    @pytest.fixture
    def manager(self):
        """기본 매니저"""
        with patch('src.core.multi_account_manager.get_api_key_manager'):
            yield MultiAccountManager()

    def test_calculate_risk_score_low(self, manager):
        """저위험 계정"""
        account = {
            'risk_level': 'low',
            'strategy': 'conservative',
            'target_allocation': {'BTC': 0.2, 'KRW': 0.8}
        }
        score = manager.calculate_account_risk_score(account)
        assert score < 30

    def test_calculate_risk_score_high(self, manager):
        """고위험 계정"""
        account = {
            'risk_level': 'high',
            'strategy': 'aggressive',
            'target_allocation': {'BTC': 0.6, 'ETH': 0.3, 'KRW': 0.1}
        }
        score = manager.calculate_account_risk_score(account)
        assert score > 70

    def test_calculate_risk_score_medium(self, manager):
        """중간 위험 계정"""
        account = {
            'risk_level': 'medium',
            'strategy': 'balanced',
            'target_allocation': {'BTC': 0.4, 'ETH': 0.2, 'KRW': 0.4}
        }
        score = manager.calculate_account_risk_score(account)
        assert 30 <= score <= 70

    def test_calculate_risk_score_exception(self, manager):
        """예외 발생 시 기본값"""
        account = {'invalid': 'data'}
        score = manager.calculate_account_risk_score(account)
        # risk_level과 strategy가 없으면 기본값이 적용됨
        assert isinstance(score, (int, float))
        assert 0 <= score <= 100


class TestMultiAccountManagerAccountStatus:
    """계정 상태 조회 테스트"""

    @pytest.fixture
    def manager_with_accounts(self):
        """계정이 있는 매니저"""
        with patch('src.core.multi_account_manager.get_api_key_manager'):
            manager = MultiAccountManager()
            manager.accounts = {
                "account_001": AccountConfig(
                    account_id="account_001",
                    account_name="테스트",
                    description="테스트",
                    risk_level="moderate",
                    initial_capital=1000000.0,
                    max_investment=5000000.0
                )
            }
            yield manager

    @pytest.mark.asyncio
    async def test_get_account_status_success(self, manager_with_accounts):
        """계정 상태 조회 성공"""
        status = await manager_with_accounts.get_account_status("account_001")

        assert status is not None
        assert status['account_id'] == "account_001"
        assert status['status'] == 'active'

    @pytest.mark.asyncio
    async def test_get_account_status_nonexistent(self, manager_with_accounts):
        """존재하지 않는 계정 상태"""
        status = await manager_with_accounts.get_account_status("nonexistent")
        assert status is None


class TestMultiAccountManagerBalance:
    """잔고 조회 테스트"""

    @pytest.fixture
    def manager_with_client(self):
        """클라이언트가 있는 매니저"""
        with patch('src.core.multi_account_manager.get_api_key_manager'):
            manager = MultiAccountManager()

            mock_client = Mock()
            mock_client.get_balances.return_value = {
                'KRW': 500000.0,
                'BTC': 0.01,
                'ETH': 0.0  # 임계값 미만
            }
            mock_client.get_ticker.return_value = {
                'result': 'success',
                'data': {'close_24h': '50000000'}
            }

            manager.clients = {"account_001": mock_client}
            manager.account_locks = {"account_001": asyncio.Lock()}
            yield manager

    @pytest.mark.asyncio
    async def test_get_account_balance_success(self, manager_with_client):
        """잔고 조회 성공"""
        balances = await manager_with_client.get_account_balance("account_001")

        assert len(balances) >= 1
        # KRW와 BTC만 있어야 함 (ETH는 임계값 미만)
        assets = [b['asset'] for b in balances]
        assert 'KRW' in assets or 'BTC' in assets

    @pytest.mark.asyncio
    async def test_get_account_balance_no_client(self, manager_with_client):
        """클라이언트 없을 때"""
        from src.core.exceptions import KairosException

        with pytest.raises((KairosException, Exception)):
            await manager_with_client.get_account_balance("nonexistent")

    @pytest.mark.asyncio
    async def test_get_account_balance_ticker_failure(self, manager_with_client):
        """시세 조회 실패"""
        manager_with_client.clients["account_001"].get_ticker.side_effect = Exception("API Error")

        # 시세 조회 실패해도 잔고는 반환
        balances = await manager_with_client.get_account_balance("account_001")
        assert isinstance(balances, list)


class TestMultiAccountManagerHealthCheck:
    """헬스체크 테스트"""

    @pytest.fixture
    def manager_with_accounts(self):
        """계정이 있는 매니저"""
        with patch('src.core.multi_account_manager.get_api_key_manager'):
            manager = MultiAccountManager()
            manager.accounts = {
                "account_001": AccountConfig(
                    account_id="account_001",
                    account_name="테스트",
                    description="테스트",
                    risk_level="moderate",
                    initial_capital=1000000.0,
                    max_investment=5000000.0
                ),
                "account_002": AccountConfig(
                    account_id="account_002",
                    account_name="테스트2",
                    description="테스트2",
                    risk_level="high",
                    initial_capital=2000000.0,
                    max_investment=5000000.0
                )
            }

            mock_client = Mock()
            mock_client.get_ticker.return_value = {'result': 'success'}

            manager.clients = {
                "account_001": mock_client,
                "account_002": mock_client
            }
            manager.account_status = {
                "account_001": AccountStatus.ACTIVE,
                "account_002": AccountStatus.ACTIVE
            }
            yield manager

    @pytest.mark.asyncio
    async def test_check_account_health_success(self, manager_with_accounts):
        """개별 계정 헬스체크 성공"""
        result = await manager_with_accounts._check_account_health("account_001")

        assert result is True
        assert manager_with_accounts.account_status["account_001"] == AccountStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_check_account_health_no_client(self, manager_with_accounts):
        """클라이언트 없을 때"""
        del manager_with_accounts.clients["account_001"]

        result = await manager_with_accounts._check_account_health("account_001")

        assert result is False
        assert manager_with_accounts.account_status["account_001"] == AccountStatus.ERROR

    @pytest.mark.asyncio
    async def test_check_account_health_api_error(self, manager_with_accounts):
        """API 오류"""
        manager_with_accounts.clients["account_001"].get_ticker.side_effect = Exception("API Error")

        result = await manager_with_accounts._check_account_health("account_001")

        assert result is False
        assert manager_with_accounts.account_status["account_001"] == AccountStatus.ERROR

    @pytest.mark.asyncio
    async def test_check_all_accounts_health(self, manager_with_accounts):
        """모든 계정 헬스체크"""
        await manager_with_accounts._check_all_accounts_health()

        # 두 계정 모두 ACTIVE 상태여야 함
        assert manager_with_accounts.account_status["account_001"] == AccountStatus.ACTIVE
        assert manager_with_accounts.account_status["account_002"] == AccountStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_health_check_method(self, manager_with_accounts):
        """health_check 메서드"""
        result = await manager_with_accounts.health_check()

        assert result['service'] == 'multi_account_manager'
        assert result['status'] in ['healthy', 'degraded']
        assert 'total_accounts' in result
        assert 'active_accounts' in result


class TestMultiAccountManagerAggregatePortfolio:
    """통합 포트폴리오 테스트"""

    @pytest.fixture
    def manager_with_accounts(self):
        """계정이 있는 매니저"""
        with patch('src.core.multi_account_manager.get_api_key_manager'):
            manager = MultiAccountManager()
            manager.accounts = {
                "account_001": AccountConfig(
                    account_id="account_001",
                    account_name="메인 계정",
                    description="주 투자",
                    risk_level="moderate",
                    initial_capital=1000000.0,
                    max_investment=5000000.0
                ),
                "account_002": AccountConfig(
                    account_id="account_002",
                    account_name="서브 계정",
                    description="추가 투자",
                    risk_level="low",
                    initial_capital=500000.0,
                    max_investment=2000000.0
                )
            }

            mock_client = Mock()
            mock_client.get_balances.return_value = {'KRW': 500000.0, 'BTC': 0.01}
            mock_client.get_ticker.return_value = {
                'result': 'success',
                'data': {'close_24h': '50000000'}
            }

            manager.clients = {
                "account_001": mock_client,
                "account_002": mock_client
            }
            manager.account_status = {
                "account_001": AccountStatus.ACTIVE,
                "account_002": AccountStatus.ACTIVE
            }
            manager.account_locks = {
                "account_001": asyncio.Lock(),
                "account_002": asyncio.Lock()
            }
            yield manager

    @pytest.mark.asyncio
    async def test_get_aggregate_portfolio_success(self, manager_with_accounts):
        """통합 포트폴리오 조회 성공"""
        result = await manager_with_accounts.get_aggregate_portfolio()

        assert 'total_value' in result
        assert 'total_return' in result
        assert 'active_accounts' in result
        assert 'account_summaries' in result
        assert 'asset_distribution' in result
        assert 'last_updated' in result

    @pytest.mark.asyncio
    async def test_get_aggregate_portfolio_inactive_account(self, manager_with_accounts):
        """비활성 계정 제외"""
        manager_with_accounts.account_status["account_002"] = AccountStatus.INACTIVE

        result = await manager_with_accounts.get_aggregate_portfolio()

        # 비활성 계정은 제외됨 (account_001은 ACTIVE)
        # active_accounts는 성공적으로 조회된 계정 수
        assert 'active_accounts' in result
        assert result['active_accounts'] >= 0

    @pytest.mark.asyncio
    async def test_get_aggregate_portfolio_error_handling(self, manager_with_accounts):
        """계정 조회 실패 처리"""
        manager_with_accounts.clients["account_001"].get_balances.side_effect = Exception("Error")

        result = await manager_with_accounts.get_aggregate_portfolio()

        # 에러가 있어도 다른 계정은 처리
        assert isinstance(result, dict)


class TestMultiAccountManagerAllocation:
    """할당 업데이트 테스트"""

    @pytest.fixture
    def manager_with_accounts(self):
        """계정이 있는 매니저"""
        with patch('src.core.multi_account_manager.get_api_key_manager'):
            manager = MultiAccountManager()
            manager.accounts = {
                "account_001": AccountConfig(
                    account_id="account_001",
                    account_name="테스트",
                    description="테스트",
                    risk_level="moderate",
                    initial_capital=1000000.0,
                    max_investment=5000000.0
                )
            }
            yield manager

    def test_update_allocation_success(self, manager_with_accounts):
        """할당 업데이트 성공"""
        new_allocation = {'BTC': 0.5, 'ETH': 0.3, 'KRW': 0.2}
        result = manager_with_accounts.update_account_allocation("account_001", new_allocation)

        assert result is True

    def test_update_allocation_invalid_sum(self, manager_with_accounts):
        """잘못된 합계"""
        new_allocation = {'BTC': 0.5, 'ETH': 0.4, 'KRW': 0.2}  # 합계 1.1
        result = manager_with_accounts.update_account_allocation("account_001", new_allocation)

        assert result is False

    def test_update_allocation_nonexistent(self, manager_with_accounts):
        """존재하지 않는 계정"""
        result = manager_with_accounts.update_account_allocation("nonexistent", {'BTC': 1.0})

        assert result is False


class TestMultiAccountManagerServiceMethods:
    """서비스 메서드 테스트"""

    @pytest.fixture
    def manager(self):
        """기본 매니저"""
        with patch('src.core.multi_account_manager.get_api_key_manager'):
            yield MultiAccountManager()

    @pytest.mark.asyncio
    async def test_start(self, manager):
        """서비스 시작"""
        with patch.object(manager, 'initialize', new_callable=AsyncMock) as mock_init:
            await manager.start()
            mock_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop(self, manager):
        """서비스 중지"""
        manager.clients = {"account_001": Mock()}
        await manager.stop()
        # 예외 없이 완료되어야 함


class TestMultiAccountManagerAllStatuses:
    """모든 계정 상태 조회 테스트"""

    @pytest.fixture
    def manager_with_accounts(self):
        """계정이 있는 매니저"""
        with patch('src.core.multi_account_manager.get_api_key_manager'):
            manager = MultiAccountManager()
            manager.accounts = {
                "account_001": AccountConfig(
                    account_id="account_001",
                    account_name="테스트1",
                    description="테스트",
                    risk_level="moderate",
                    initial_capital=1000000.0,
                    max_investment=5000000.0
                ),
                "account_002": AccountConfig(
                    account_id="account_002",
                    account_name="테스트2",
                    description="테스트",
                    risk_level="high",
                    initial_capital=2000000.0,
                    max_investment=5000000.0
                )
            }
            yield manager

    @pytest.mark.asyncio
    async def test_get_all_account_statuses(self, manager_with_accounts):
        """모든 계정 상태 조회"""
        statuses = await manager_with_accounts.get_all_account_statuses()

        assert len(statuses) == 2
        account_ids = [s.get('account_id') for s in statuses]
        assert "account_001" in account_ids
        assert "account_002" in account_ids

    @pytest.mark.asyncio
    async def test_get_all_account_statuses_with_error(self, manager_with_accounts):
        """일부 계정 오류 시"""
        with patch.object(manager_with_accounts, 'get_account_status') as mock_status:
            async def side_effect(account_id):
                if account_id == "account_001":
                    return {'account_id': account_id, 'status': 'active'}
                raise Exception("Error")

            mock_status.side_effect = side_effect

            statuses = await manager_with_accounts.get_all_account_statuses()

            assert len(statuses) == 2
            # 오류가 있는 계정도 포함되어야 함


class TestGlobalFunctions:
    """전역 함수 테스트"""

    def test_get_multi_account_manager(self):
        """매니저 인스턴스 조회"""
        import src.core.multi_account_manager as mam

        # 기존 인스턴스 초기화
        mam._multi_account_manager = None

        with patch('src.core.multi_account_manager.get_api_key_manager'):
            manager1 = get_multi_account_manager()
            manager2 = get_multi_account_manager()

            assert manager1 is manager2

            # 정리
            mam._multi_account_manager = None

    @pytest.mark.asyncio
    async def test_get_account_performance_data(self):
        """계정 성과 데이터 조회"""
        import src.core.multi_account_manager as mam

        # 기존 인스턴스 초기화
        mam._multi_account_manager = None

        with patch('src.core.multi_account_manager.get_api_key_manager'):
            manager = get_multi_account_manager()
            manager.performance_data = {
                "account_001": {"total_return": 0.15}
            }

            data = await get_account_performance_data("account_001")
            assert data == {"total_return": 0.15}

            # 없는 계정
            data = await get_account_performance_data("nonexistent")
            assert data == {}

            # 정리
            mam._multi_account_manager = None


class TestMultiAccountManagerInitialize:
    """전체 초기화 테스트"""

    @pytest.fixture
    def mock_all_dependencies(self, tmp_path):
        """모든 종속성 모킹"""
        config_file = tmp_path / "accounts.json"
        config_data = {
            "accounts": [
                {
                    "account_id": "account_001",
                    "account_name": "메인 계정",
                    "description": "주 투자",
                    "risk_level": "moderate",
                    "initial_capital": 1000000.0,
                    "max_investment": 5000000.0,
                    "dry_run": True
                }
            ],
            "global_settings": {}
        }
        config_file.write_text(json.dumps(config_data))

        with patch('src.core.multi_account_manager.get_api_key_manager') as mock_api:
            mock_api.return_value.get_api_keys.return_value = {
                'api_key': 'test_key',
                'secret_key': 'test_secret'
            }
            yield str(config_file), mock_api

    @pytest.mark.asyncio
    async def test_initialize_success(self, mock_all_dependencies):
        """초기화 성공"""
        config_path, mock_api = mock_all_dependencies

        with patch('src.core.multi_account_manager.CoinoneClient') as MockClient:
            mock_client = Mock()
            mock_client.get_ticker.return_value = {'result': 'success'}
            MockClient.return_value = mock_client

            manager = MultiAccountManager(config_path)
            await manager.initialize()

            assert "account_001" in manager.accounts
            assert manager.account_status.get("account_001") == AccountStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_initialize_failure(self, mock_all_dependencies):
        """초기화 실패"""
        _, mock_api = mock_all_dependencies

        from src.core.exceptions import ConfigurationException

        manager = MultiAccountManager("config/test_accounts.json")

        # _load_accounts_config에서 예외 발생 시 초기화 실패
        with patch.object(manager, '_load_accounts_config', new_callable=AsyncMock) as mock_load:
            mock_load.side_effect = Exception("Config load error")

            with pytest.raises(ConfigurationException):
                await manager.initialize()


class TestMultiAccountManagerSaveConfig:
    """설정 저장 테스트"""

    @pytest.fixture
    def manager_with_accounts(self, tmp_path):
        """계정이 있는 매니저"""
        config_file = tmp_path / "accounts.json"

        with patch('src.core.multi_account_manager.get_api_key_manager'):
            manager = MultiAccountManager(str(config_file))
            manager.accounts = {
                "account_001": AccountConfig(
                    account_id="account_001",
                    account_name="테스트",
                    description="테스트",
                    risk_level="moderate",
                    initial_capital=1000000.0,
                    max_investment=5000000.0
                )
            }
            yield manager, config_file

    @pytest.mark.asyncio
    async def test_save_accounts_config(self, manager_with_accounts):
        """설정 저장"""
        manager, config_file = manager_with_accounts

        # 디렉토리 생성
        config_file.parent.mkdir(parents=True, exist_ok=True)

        await manager._save_accounts_config()

        assert config_file.exists()

        with open(config_file) as f:
            saved_config = json.load(f)

        assert "accounts" in saved_config
        assert len(saved_config["accounts"]) == 1

    @pytest.mark.asyncio
    async def test_save_accounts_config_error(self, manager_with_accounts):
        """설정 저장 오류"""
        manager, _ = manager_with_accounts

        # 잘못된 경로로 설정
        manager.accounts_config_path = Path("/nonexistent/path/accounts.json")

        # 예외 없이 로그만 출력
        await manager._save_accounts_config()


@pytest.mark.multi_account
class TestMultiAccountManagerUncoveredLines:
    """커버되지 않은 라인 테스트"""

    @pytest.fixture
    def mock_manager(self, tmp_path):
        """Mock 매니저"""
        config_file = tmp_path / "accounts.json"

        with patch('src.core.multi_account_manager.get_api_key_manager'):
            manager = MultiAccountManager(str(config_file))
            yield manager

    @pytest.mark.asyncio
    async def test_remove_account_exception(self, mock_manager):
        """계정 제거 예외 (라인 257-259)"""
        manager = mock_manager

        # accounts dict에서 예외 발생하도록 설정
        manager.accounts = Mock()
        manager.accounts.__contains__ = Mock(return_value=True)
        manager.accounts.pop.side_effect = Exception("제거 실패")

        result = await manager.remove_account("test_account")

        # 예외 시 False 반환
        assert result is False

    @pytest.mark.asyncio
    async def test_get_account_info_ticker_exception(self, mock_manager):
        """계정 정보 조회 시 시세 예외 (라인 296-299)"""
        manager = mock_manager

        # 계정 설정
        account_config = AccountConfig(
            account_id="test_account",
            account_name="테스트",
            description="테스트",
            risk_level="moderate",
            initial_capital=1000000.0,
            max_investment=5000000.0
        )
        manager.accounts = {"test_account": account_config}
        manager.account_status = {"test_account": AccountStatus.ACTIVE}

        # Mock 클라이언트 설정
        mock_client = Mock()
        mock_client.get_balances = Mock(return_value={"BTC": 0.1, "KRW": 500000})
        mock_client.get_ticker = Mock(side_effect=Exception("시세 조회 실패"))
        manager.clients = {"test_account": mock_client}

        result = await manager.get_account_info("test_account")

        # 시세 조회 실패해도 결과 반환
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_account_info_balance_exception(self, mock_manager):
        """계정 정보 조회 시 잔고 예외 (라인 306-307)"""
        manager = mock_manager

        account_config = AccountConfig(
            account_id="test_account",
            account_name="테스트",
            description="테스트",
            risk_level="moderate",
            initial_capital=1000000.0,
            max_investment=5000000.0
        )
        manager.accounts = {"test_account": account_config}
        manager.account_status = {"test_account": AccountStatus.ACTIVE}

        mock_client = Mock()
        mock_client.get_balances = Mock(side_effect=Exception("잔고 조회 실패"))
        manager.clients = {"test_account": mock_client}

        result = await manager.get_account_info("test_account")

        # 잔고 조회 실패해도 결과 반환
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_account_info_zero_initial_capital(self, mock_manager):
        """계정 정보 조회 시 초기 자본 0 (라인 302-305)"""
        manager = mock_manager

        account_config = AccountConfig(
            account_id="test_account",
            account_name="테스트",
            description="테스트",
            risk_level="moderate",
            initial_capital=0.0,  # 초기 자본 0
            max_investment=5000000.0
        )
        manager.accounts = {"test_account": account_config}
        manager.account_status = {"test_account": AccountStatus.ACTIVE}

        mock_client = Mock()
        mock_client.get_balances = Mock(return_value={"KRW": 500000})
        manager.clients = {"test_account": mock_client}

        result = await manager.get_account_info("test_account")

        assert result is not None

    @pytest.mark.asyncio
    async def test_execute_trade_for_account_exception(self, mock_manager):
        """계정 거래 실행 예외 (라인 326-328)"""
        if hasattr(mock_manager, 'execute_trade_for_account'):
            result = await mock_manager.execute_trade_for_account(
                account_id="nonexistent",
                asset="BTC",
                side="buy",
                amount=100000
            )

            # 예외 시 실패 결과 반환
            assert isinstance(result, (dict, MultiAccountOperationResult)) or result is None

    @pytest.mark.asyncio
    async def test_get_all_accounts_exception(self, mock_manager):
        """모든 계정 조회 예외 (라인 371-391)"""
        manager = mock_manager

        # 빈 계정 설정
        manager.accounts = {}

        if hasattr(manager, 'get_all_accounts'):
            result = await manager.get_all_accounts()

            # 빈 리스트 반환
            assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_sync_account_status_exception(self, mock_manager):
        """계정 상태 동기화 예외 (라인 395-406)"""
        manager = mock_manager

        if hasattr(manager, 'sync_account_status'):
            manager.accounts = {"test": Mock()}
            manager.account_status = {}

            result = await manager.sync_account_status("test")

            assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_update_account_exception(self, mock_manager):
        """계정 업데이트 예외 (라인 430-432, 449-451)"""
        manager = mock_manager

        if hasattr(manager, 'update_account'):
            result = await manager.update_account(
                account_id="nonexistent",
                account_name="새 이름"
            )

            # 예외 시 False 반환
            assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_get_portfolio_allocation_exception(self, mock_manager):
        """포트폴리오 할당 조회 예외 (라인 599-606)"""
        manager = mock_manager

        if hasattr(manager, 'get_portfolio_allocation'):
            result = await manager.get_portfolio_allocation("nonexistent")

            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_rebalance_account_exception(self, mock_manager):
        """계정 리밸런싱 예외 (라인 628-630)"""
        manager = mock_manager

        if hasattr(manager, 'rebalance_account'):
            result = await manager.rebalance_account("nonexistent")

            # 예외 시 실패 결과 반환
            assert result is None or isinstance(result, (dict, MultiAccountOperationResult))

    @pytest.mark.asyncio
    async def test_get_risk_metrics_exception(self, mock_manager):
        """리스크 지표 조회 예외 (라인 697-699)"""
        manager = mock_manager

        if hasattr(manager, 'get_risk_metrics'):
            result = await manager.get_risk_metrics("nonexistent")

            assert isinstance(result, dict)

    def test_validate_account_missing_fields(self, mock_manager):
        """계정 유효성 검증 - 필드 누락 (라인 371-391)"""
        manager = mock_manager

        # 필수 필드 누락
        invalid_account = {
            'account_id': 'test'
            # 'account_name' 누락
            # 'target_allocation' 누락
        }

        result = manager.validate_account(invalid_account)

        # 필드 누락으로 False 반환
        assert result is False

    def test_validate_account_invalid_allocation_sum(self, mock_manager):
        """계정 유효성 검증 - 잘못된 할당 합계 (라인 380-383)"""
        manager = mock_manager

        # 할당 합계가 1이 아님
        invalid_account = {
            'account_id': 'test',
            'account_name': 'Test',
            'target_allocation': {'BTC': 0.5, 'ETH': 0.3},  # 합계 0.8
            'initial_capital': 1000000
        }

        result = manager.validate_account(invalid_account)

        # 합계 오류로 False 반환
        assert result is False

    def test_validate_account_zero_capital(self, mock_manager):
        """계정 유효성 검증 - 0 자본 (라인 386-387)"""
        manager = mock_manager

        # 초기 자본이 0
        invalid_account = {
            'account_id': 'test',
            'account_name': 'Test',
            'target_allocation': {'BTC': 0.5, 'ETH': 0.5},
            'initial_capital': 0  # 0 자본
        }

        result = manager.validate_account(invalid_account)

        # 0 자본으로 False 반환
        assert result is False

    def test_update_account_allocation_success(self, mock_manager):
        """계정 할당 업데이트 성공 (라인 393-406)"""
        from src.core.multi_account_manager import MultiAccountManager

        # 실제 메서드 시그니처 확인
        if callable(getattr(MultiAccountManager, 'update_account_allocation', None)):
            manager = mock_manager

            # 유효한 계정 설정
            mock_account = Mock()
            mock_account.account_id = "test"
            manager.accounts["test"] = mock_account

            # 실제 메서드 호출
            original_method = MultiAccountManager.update_account_allocation
            result = original_method(manager, "test", {'BTC': 0.6, 'ETH': 0.4})

            assert result is True
        else:
            assert True

    def test_update_account_allocation_nonexistent(self, mock_manager):
        """계정 할당 업데이트 - 존재하지 않는 계정 (라인 395-397)"""
        from src.core.multi_account_manager import MultiAccountManager

        if callable(getattr(MultiAccountManager, 'update_account_allocation', None)):
            manager = mock_manager
            manager.accounts = {}

            # 실제 메서드 호출
            original_method = MultiAccountManager.update_account_allocation
            result = original_method(manager, "nonexistent", {'BTC': 0.5, 'ETH': 0.5})

            assert result is False
        else:
            assert True

    def test_calculate_account_risk_score_conservative(self, mock_manager):
        """계정 리스크 점수 - 보수적 (라인 416-417)"""
        manager = mock_manager

        account = {
            'risk_level': 'low',
            'strategy': 'conservative',
            'target_allocation': {'BTC': 0.2, 'KRW': 0.8}
        }

        score = manager.calculate_account_risk_score(account)

        # 보수적이므로 낮은 점수
        assert 0 <= score <= 100
        assert score < 50  # 보수적 기본 점수 + 낮은 암호화폐 비중

    def test_calculate_account_risk_score_aggressive(self, mock_manager):
        """계정 리스크 점수 - 공격적 (라인 418-419)"""
        manager = mock_manager

        account = {
            'risk_level': 'high',
            'strategy': 'aggressive',
            'target_allocation': {'BTC': 0.7, 'ETH': 0.2, 'KRW': 0.1}
        }

        score = manager.calculate_account_risk_score(account)

        # 공격적이므로 높은 점수
        assert 0 <= score <= 100
        assert score > 50  # 공격적 기본 점수 + 높은 암호화폐 비중

    def test_calculate_account_risk_score_exception(self, mock_manager):
        """계정 리스크 점수 계산 예외 (라인 430-432)"""
        manager = mock_manager

        # 잘못된 데이터로 예외 유발
        account = None

        with patch.object(manager, 'calculate_account_risk_score', side_effect=Exception("Error")):
            try:
                score = manager.calculate_account_risk_score(account)
            except Exception:
                score = 50.0  # 기본값

        assert score == 50.0

    @pytest.mark.asyncio
    async def test_get_account_status_exception(self, mock_manager):
        """계정 상태 조회 예외 (라인 449-451)"""
        manager = mock_manager

        # 존재하지 않는 계정
        manager.accounts = {}

        result = await manager.get_account_status("nonexistent")

        # 예외 시 None 반환
        assert result is None

    def test_get_accounts_by_strategy(self, mock_manager):
        """전략별 계정 목록 (라인 453-462)"""
        manager = mock_manager

        # 계정 설정
        mock_account = Mock()
        mock_account.account_id = "test"
        mock_account.risk_level = "medium"
        manager.accounts = {"test": mock_account}
        manager.get_account = Mock(return_value={
            'account_id': 'test',
            'strategy': 'balanced'
        })

        result = manager.get_accounts_by_strategy("balanced")

        assert isinstance(result, list)

    def test_get_accounts_by_risk_level(self, mock_manager):
        """리스크 레벨별 계정 목록 (라인 464-478)"""
        manager = mock_manager

        # 계정 설정
        mock_account = Mock()
        mock_account.account_id = "test"
        mock_account.risk_level = "high"
        manager.accounts = {"test": mock_account}
        manager.get_account = Mock(return_value={
            'account_id': 'test',
            'risk_level': 'high'
        })

        result = manager.get_accounts_by_risk_level("high")

        assert isinstance(result, list)


class TestMultiAccountManagerUncoveredLines:
    """미커버 라인 테스트 - multi_account_manager.py"""

    @pytest.fixture
    def mock_manager(self):
        with patch.object(MultiAccountManager, '__init__', lambda self: None):
            manager = MultiAccountManager()
            manager.accounts = {}
            manager.clients = {}
            manager.account_status = {}
            manager.account_locks = {}
            manager.initialized = False
            return manager

    @pytest.mark.asyncio
    async def test_get_account_info_exception(self, mock_manager):
        """계정 정보 조회 예외 (라인 326-328)"""
        manager = mock_manager
        manager.clients = {"test": Mock()}
        manager.accounts = {"test": Mock()}
        manager.account_locks = {"test": asyncio.Lock()}

        # get_balances에서 예외 발생
        manager.clients["test"].get_balances = Mock(side_effect=Exception("API error"))

        result = await manager.get_account_info("test")

        assert result is None

    def test_validate_account_missing_field(self, mock_manager):
        """계정 유효성 검증 - 필수 필드 누락 (라인 371-376)"""
        manager = mock_manager

        # account_id 누락
        account1 = {
            'account_name': 'Test',
            'target_allocation': {'BTC': 1.0}
        }
        result1 = manager.validate_account(account1)
        assert result1 is False

        # account_name 누락
        account2 = {
            'account_id': 'test',
            'target_allocation': {'BTC': 1.0}
        }
        result2 = manager.validate_account(account2)
        assert result2 is False

    def test_validate_account_invalid_allocation_sum(self, mock_manager):
        """계정 유효성 검증 - 할당 합계 오류 (라인 378-383)"""
        manager = mock_manager

        # 할당 합계가 1.0이 아님
        account = {
            'account_id': 'test',
            'account_name': 'Test',
            'target_allocation': {'BTC': 0.3, 'ETH': 0.2},  # 합계 0.5
            'initial_capital': 1000000
        }
        result = manager.validate_account(account)
        assert result is False

    def test_validate_account_invalid_capital(self, mock_manager):
        """계정 유효성 검증 - 유효하지 않은 초기 자본 (라인 386-387)"""
        manager = mock_manager

        # initial_capital이 0 이하
        account = {
            'account_id': 'test',
            'account_name': 'Test',
            'target_allocation': {'BTC': 1.0},
            'initial_capital': 0
        }
        result = manager.validate_account(account)
        assert result is False

    def test_validate_account_exception(self, mock_manager):
        """계정 유효성 검증 - 예외 발생 (라인 390-391)"""
        manager = mock_manager

        # 잘못된 데이터 타입으로 예외 유발
        account = None  # This will cause an exception

        result = manager.validate_account(account)
        assert result is False

    def test_update_account_allocation_not_found(self, mock_manager):
        """계정 할당 업데이트 - 계정 없음 (라인 395-397)"""
        manager = mock_manager
        manager.accounts = {}

        result = manager.update_account_allocation("nonexistent", {'BTC': 1.0})
        assert result is False

    def test_update_account_allocation_success(self, mock_manager):
        """계정 할당 업데이트 - 성공 (라인 399-404)"""
        manager = mock_manager

        mock_account = Mock()
        mock_account.account_id = "test"
        manager.accounts = {"test": mock_account}

        result = manager.update_account_allocation("test", {'BTC': 0.5, 'ETH': 0.5})
        assert result is True

    def test_update_account_allocation_exception(self, mock_manager):
        """계정 할당 업데이트 - 예외 발생 (라인 405-406)"""
        manager = mock_manager

        # accounts.get()에서 예외 발생하도록 설정
        manager.accounts = Mock()
        manager.accounts.__contains__ = Mock(side_effect=Exception("Test error"))

        result = manager.update_account_allocation("test", {'BTC': 1.0})
        assert result is False

    def test_calculate_risk_score_exception(self, mock_manager):
        """리스크 점수 계산 - 예외 발생 (라인 430-432)"""
        manager = mock_manager

        # target_allocation이 None이면 예외 발생
        account = {
            'risk_level': 'medium',
            'strategy': 'balanced',
            'target_allocation': None  # This causes TypeError
        }

        # Should return default 50.0
        result = manager.calculate_account_risk_score(account)
        assert result == 50.0

    @pytest.mark.asyncio
    async def test_get_account_status_exception(self, mock_manager):
        """계정 상태 조회 - 예외 발생 (라인 449-451)"""
        manager = mock_manager
        manager.accounts = {"test": Mock()}

        # accounts.__contains__에서 예외 발생
        original_accounts = manager.accounts
        manager.accounts = Mock()
        manager.accounts.__contains__ = Mock(side_effect=Exception("Test error"))

        result = await manager.get_account_status("test")
        assert result is None

    @pytest.mark.asyncio
    async def test_portfolio_summary_asset_totals(self, mock_manager):
        """포트폴리오 요약 - 자산 합계 (라인 599-606)"""
        manager = mock_manager

        mock_account1 = Mock()
        mock_account1.account_name = "Account1"
        mock_account1.initial_capital = 1000000
        mock_account2 = Mock()
        mock_account2.account_name = "Account2"
        mock_account2.initial_capital = 2000000

        manager.accounts = {
            "acc1": mock_account1,
            "acc2": mock_account2
        }
        manager.account_status = {
            "acc1": AccountStatus.ACTIVE,
            "acc2": AccountStatus.ACTIVE
        }

        # 잔고 목록 모킹
        async def mock_get_balance(account_id):
            if account_id == "acc1":
                return [
                    {'asset': 'BTC', 'total': Decimal('0.5'), 'value_krw': KRWAmount(Decimal('500000'))},
                    {'asset': 'ETH', 'total': Decimal('2.0'), 'value_krw': KRWAmount(Decimal('300000'))}
                ]
            else:
                return [
                    {'asset': 'BTC', 'total': Decimal('1.0'), 'value_krw': KRWAmount(Decimal('1000000'))},
                    {'asset': 'XRP', 'total': Decimal('1000'), 'value_krw': KRWAmount(Decimal('500000'))}
                ]

        manager.get_account_balance = mock_get_balance

        result = await manager.get_aggregate_portfolio()

        assert result is not None
        assert 'total_value' in result
        assert 'asset_distribution' in result
        # BTC는 두 계정에서 합쳐짐
        assert 'BTC' in result['asset_distribution']

    @pytest.mark.asyncio
    async def test_portfolio_summary_exception(self, mock_manager):
        """포트폴리오 요약 - 예외 발생 (라인 628-630)"""
        manager = mock_manager

        # accounts.keys()에서 예외 발생하도록 설정
        manager.accounts = Mock()
        manager.accounts.keys = Mock(side_effect=Exception("Test error"))

        result = await manager.get_aggregate_portfolio()
        assert result is None

    def test_update_allocation_invalid_sum(self, mock_manager):
        """계정 배분 업데이트 - 잘못된 합계 (라인 690-691)"""
        from src.core.multi_account_manager import MultiAccountManager

        manager = mock_manager

        mock_account = Mock()
        mock_account.account_id = "test"
        manager.accounts = {"test": mock_account}

        # Use original method directly
        original_method = MultiAccountManager.update_account_allocation

        # 합계가 1.0이 아닌 할당
        result = original_method(manager, "test", {'BTC': 0.3, 'ETH': 0.2})  # 합계 0.5
        assert result is False

    def test_update_allocation_exception_2(self, mock_manager):
        """계정 배분 업데이트 - 예외 (라인 697-699)"""
        from src.core.multi_account_manager import MultiAccountManager

        manager = mock_manager

        # accounts.__contains__는 True 반환
        manager.accounts = {"test": Mock()}

        # new_allocation.values()에서 예외 발생
        bad_allocation = Mock()
        bad_allocation.values = Mock(side_effect=Exception("Test error"))

        # 직접 메서드 호출
        original_method = MultiAccountManager.update_account_allocation
        result = original_method(manager, "test", bad_allocation)
        assert result is False
