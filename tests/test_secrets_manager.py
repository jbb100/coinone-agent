"""
Secrets Manager Tests

비밀 정보 관리 시스템 테스트
"""

import pytest
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from src.security.secrets_manager import (
    SecretsManager, APIKeyManager,
    get_secrets_manager, get_api_key_manager
)


@pytest.fixture
def temp_secrets_path(tmp_path):
    """임시 비밀 저장소 경로"""
    return str(tmp_path / '.secrets')


@pytest.fixture
def master_key():
    """테스트용 마스터 키"""
    return "test_master_key_12345678"


class TestSecretsManager:
    """SecretsManager 테스트"""

    def test_init_with_master_key(self, temp_secrets_path, master_key):
        """마스터 키로 초기화"""
        manager = SecretsManager(
            master_key=master_key,
            secrets_path=temp_secrets_path
        )

        assert manager is not None
        assert manager.secrets_path == Path(temp_secrets_path)

    def test_init_without_master_key(self, temp_secrets_path):
        """마스터 키 없이 초기화 - 환경변수 또는 개발키 사용"""
        manager = SecretsManager(secrets_path=temp_secrets_path)

        assert manager is not None
        assert manager.master_key is not None

    def test_init_with_env_master_key(self, temp_secrets_path):
        """환경변수 마스터 키로 초기화"""
        test_key = "env_test_key_12345678901234"
        os.environ['KAIROS_MASTER_KEY'] = test_key

        try:
            manager = SecretsManager(secrets_path=temp_secrets_path)
            assert manager.master_key == test_key.encode()
        finally:
            del os.environ['KAIROS_MASTER_KEY']

    def test_generate_dev_key(self, temp_secrets_path, master_key):
        """개발용 키 생성"""
        manager = SecretsManager(
            master_key=master_key,
            secrets_path=temp_secrets_path
        )

        dev_key = manager._generate_dev_key()

        assert isinstance(dev_key, str)
        assert len(dev_key) == 32

    def test_store_secret_success(self, temp_secrets_path, master_key):
        """비밀 정보 저장 성공"""
        manager = SecretsManager(
            master_key=master_key,
            secrets_path=temp_secrets_path
        )

        result = manager.store_secret('test_key', 'test_value')

        assert result is True
        assert 'test_key' in manager._encrypted_cache

    def test_store_secret_with_metadata(self, temp_secrets_path, master_key):
        """메타데이터와 함께 비밀 정보 저장"""
        manager = SecretsManager(
            master_key=master_key,
            secrets_path=temp_secrets_path
        )

        metadata = {'service': 'coinone', 'version': '1.0'}
        result = manager.store_secret('api_key', 'secret123', metadata)

        assert result is True

    def test_store_secret_persist_failure(self, temp_secrets_path, master_key):
        """비밀 정보 저장 실패 - 파일 저장 실패"""
        manager = SecretsManager(
            master_key=master_key,
            secrets_path=temp_secrets_path
        )

        with patch.object(manager, '_persist_secrets', return_value=False):
            result = manager.store_secret('test_key', 'test_value')

        assert result is False

    def test_get_secret_success(self, temp_secrets_path, master_key):
        """비밀 정보 조회 성공"""
        manager = SecretsManager(
            master_key=master_key,
            secrets_path=temp_secrets_path
        )

        # 먼저 저장
        manager.store_secret('my_secret', 'my_value')

        # 조회
        result = manager.get_secret('my_secret')

        assert result == 'my_value'

    def test_get_secret_not_found(self, temp_secrets_path, master_key):
        """비밀 정보 없음"""
        manager = SecretsManager(
            master_key=master_key,
            secrets_path=temp_secrets_path
        )

        result = manager.get_secret('nonexistent_key')

        assert result is None

    def test_get_secret_expired(self, temp_secrets_path, master_key):
        """만료된 비밀 정보"""
        manager = SecretsManager(
            master_key=master_key,
            secrets_path=temp_secrets_path
        )

        # 과거 만료일로 저장
        past_date = (datetime.now() - timedelta(days=1)).isoformat()
        metadata = {'expires_at': past_date}
        manager.store_secret('expired_key', 'expired_value', metadata)

        # 조회
        result = manager.get_secret('expired_key')

        assert result is None

    def test_rotate_key_success(self, temp_secrets_path, master_key):
        """키 로테이션 성공"""
        manager = SecretsManager(
            master_key=master_key,
            secrets_path=temp_secrets_path
        )

        # 초기 값 저장
        manager.store_secret('rotate_test', 'old_value')

        # 로테이션
        result = manager.rotate_key('rotate_test', 'new_value')

        assert result is True
        assert manager.get_secret('rotate_test') == 'new_value'

    def test_rotate_key_no_existing(self, temp_secrets_path, master_key):
        """존재하지 않는 키 로테이션"""
        manager = SecretsManager(
            master_key=master_key,
            secrets_path=temp_secrets_path
        )

        result = manager.rotate_key('nonexistent', 'new_value')

        assert result is True  # 새로운 값으로 저장

    def test_delete_secret_success(self, temp_secrets_path, master_key):
        """비밀 정보 삭제 성공"""
        manager = SecretsManager(
            master_key=master_key,
            secrets_path=temp_secrets_path
        )

        manager.store_secret('delete_me', 'value')
        result = manager.delete_secret('delete_me')

        assert result is True
        assert manager.get_secret('delete_me') is None

    def test_delete_secret_not_found(self, temp_secrets_path, master_key):
        """존재하지 않는 비밀 정보 삭제"""
        manager = SecretsManager(
            master_key=master_key,
            secrets_path=temp_secrets_path
        )

        result = manager.delete_secret('nonexistent')

        assert result is False

    def test_persist_and_load_secrets(self, temp_secrets_path, master_key):
        """비밀 정보 저장 및 로드"""
        # 첫 번째 매니저로 저장
        manager1 = SecretsManager(
            master_key=master_key,
            secrets_path=temp_secrets_path
        )
        manager1.store_secret('persist_test', 'persist_value')

        # 두 번째 매니저로 로드
        manager2 = SecretsManager(
            master_key=master_key,
            secrets_path=temp_secrets_path
        )
        result = manager2.get_secret('persist_test')

        assert result == 'persist_value'

    def test_is_expired_no_expiry(self, temp_secrets_path, master_key):
        """만료일 없는 메타데이터"""
        manager = SecretsManager(
            master_key=master_key,
            secrets_path=temp_secrets_path
        )

        result = manager._is_expired({})

        assert result is False

    def test_is_expired_future_date(self, temp_secrets_path, master_key):
        """미래 만료일"""
        manager = SecretsManager(
            master_key=master_key,
            secrets_path=temp_secrets_path
        )

        future_date = (datetime.now() + timedelta(days=30)).isoformat()
        result = manager._is_expired({'expires_at': future_date})

        assert result is False

    def test_log_access(self, temp_secrets_path, master_key):
        """접근 로그 기록"""
        manager = SecretsManager(
            master_key=master_key,
            secrets_path=temp_secrets_path
        )

        manager._log_access('GET', 'test_key', True)
        manager._log_access('STORE', 'test_key', False, 'Test error')

        logs = manager.get_access_log()

        assert len(logs) == 2
        assert logs[0]['action'] == 'GET'
        assert logs[1]['success'] is False

    def test_clear_cache(self, temp_secrets_path, master_key):
        """캐시 정리"""
        manager = SecretsManager(
            master_key=master_key,
            secrets_path=temp_secrets_path
        )

        manager.store_secret('cache_test', 'value')
        assert len(manager._encrypted_cache) > 0

        manager.clear_cache()

        assert len(manager._encrypted_cache) == 0

    def test_store_secret_exception(self, temp_secrets_path, master_key):
        """비밀 정보 저장 예외"""
        manager = SecretsManager(
            master_key=master_key,
            secrets_path=temp_secrets_path
        )

        with patch.object(manager.cipher_suite, 'encrypt', side_effect=Exception("Encrypt error")):
            result = manager.store_secret('error_key', 'error_value')

        assert result is False

    def test_get_secret_exception(self, temp_secrets_path, master_key):
        """비밀 정보 조회 예외"""
        manager = SecretsManager(
            master_key=master_key,
            secrets_path=temp_secrets_path
        )

        # 잘못된 암호화 데이터 삽입
        manager._encrypted_cache['bad_key'] = b'invalid_encrypted_data'

        result = manager.get_secret('bad_key')

        assert result is None

    def test_rotate_key_exception(self, temp_secrets_path, master_key):
        """키 로테이션 예외"""
        manager = SecretsManager(
            master_key=master_key,
            secrets_path=temp_secrets_path
        )

        with patch.object(manager, 'store_secret', side_effect=Exception("Store error")):
            result = manager.rotate_key('error_key', 'new_value')

        assert result is False

    def test_delete_secret_exception(self, temp_secrets_path, master_key):
        """비밀 정보 삭제 예외"""
        manager = SecretsManager(
            master_key=master_key,
            secrets_path=temp_secrets_path
        )

        manager.store_secret('delete_error', 'value')

        with patch.object(manager, '_persist_secrets', side_effect=Exception("Persist error")):
            result = manager.delete_secret('delete_error')

        assert result is False

    def test_load_secrets_no_file(self, temp_secrets_path, master_key):
        """파일 없을 때 로드"""
        manager = SecretsManager(
            master_key=master_key,
            secrets_path=temp_secrets_path
        )

        # 파일이 없으면 캐시가 비어있음
        assert len(manager._encrypted_cache) == 0

    def test_load_secrets_corrupted_file(self, temp_secrets_path, master_key):
        """손상된 파일 로드"""
        # 손상된 파일 생성
        Path(temp_secrets_path).parent.mkdir(parents=True, exist_ok=True)
        with open(temp_secrets_path, 'wb') as f:
            f.write(b'corrupted data')

        manager = SecretsManager(
            master_key=master_key,
            secrets_path=temp_secrets_path
        )

        # 손상된 파일 로드 시 캐시는 비어있어야 함
        assert len(manager._encrypted_cache) == 0

    def test_init_directory_creation_error(self, master_key):
        """디렉토리 생성 실패"""
        # 읽기 전용 경로 시뮬레이션
        with patch('pathlib.Path.mkdir', side_effect=OSError("Permission denied")):
            manager = SecretsManager(
                master_key=master_key,
                secrets_path='/readonly/path/.secrets'
            )

        # 초기화는 성공해야 함 (경고만 로그)
        assert manager is not None


class TestAPIKeyManager:
    """APIKeyManager 테스트"""

    @pytest.fixture
    def api_manager(self, temp_secrets_path, master_key):
        """APIKeyManager 인스턴스"""
        secrets_manager = SecretsManager(
            master_key=master_key,
            secrets_path=temp_secrets_path
        )
        return APIKeyManager(secrets_manager)

    def test_init_default(self):
        """기본 초기화"""
        manager = APIKeyManager()

        assert manager.secrets is not None
        assert manager.key_prefix == "api_key_"

    def test_init_with_secrets_manager(self, temp_secrets_path, master_key):
        """SecretsManager와 함께 초기화"""
        secrets = SecretsManager(
            master_key=master_key,
            secrets_path=temp_secrets_path
        )
        manager = APIKeyManager(secrets)

        assert manager.secrets == secrets

    def test_store_api_key_success(self, api_manager):
        """API 키 저장 성공"""
        result = api_manager.store_api_key(
            service='coinone',
            api_key='test_api_key',
            secret_key='test_secret_key'
        )

        assert result is True

    def test_store_api_key_with_expiry(self, api_manager):
        """만료일 있는 API 키 저장"""
        result = api_manager.store_api_key(
            service='binance',
            api_key='binance_api_key',
            secret_key='binance_secret',
            expires_days=90
        )

        assert result is True

    def test_store_api_key_without_secret(self, api_manager):
        """시크릿 없이 API 키 저장"""
        result = api_manager.store_api_key(
            service='public_api',
            api_key='public_key_only'
        )

        assert result is True

    def test_get_api_keys_success(self, api_manager):
        """API 키 조회 성공"""
        api_manager.store_api_key(
            service='test_service',
            api_key='my_api_key',
            secret_key='my_secret_key'
        )

        keys = api_manager.get_api_keys('test_service')

        assert keys is not None
        assert keys['api_key'] == 'my_api_key'
        assert keys['secret_key'] == 'my_secret_key'

    def test_get_api_keys_not_found(self, api_manager):
        """API 키 없음"""
        keys = api_manager.get_api_keys('nonexistent_service')

        assert keys is None

    def test_delete_api_keys_success(self, api_manager):
        """API 키 삭제 성공"""
        api_manager.store_api_key('delete_service', 'key', 'secret')

        result = api_manager.delete_api_keys('delete_service')

        assert result is True
        assert api_manager.get_api_keys('delete_service') is None

    def test_delete_api_keys_not_found(self, api_manager):
        """없는 API 키 삭제"""
        result = api_manager.delete_api_keys('nonexistent')

        assert result is False

    def test_rotate_api_keys_success(self, api_manager):
        """API 키 로테이션 성공"""
        api_manager.store_api_key('rotate_service', 'old_key', 'old_secret')

        result = api_manager.rotate_api_keys(
            service='rotate_service',
            new_api_key='new_key',
            new_secret_key='new_secret'
        )

        assert result is True

        keys = api_manager.get_api_keys('rotate_service')
        assert keys['api_key'] == 'new_key'

    def test_check_expiration(self, api_manager):
        """API 키 만료 확인"""
        # 현재 구현은 None 반환
        result = api_manager.check_expiration('test_service')

        assert result is None


class TestSingletonFunctions:
    """싱글톤 함수 테스트"""

    def test_get_secrets_manager_singleton(self):
        """SecretsManager 싱글톤"""
        # 글로벌 상태 초기화
        import src.security.secrets_manager as sm
        sm._secrets_manager = None

        manager1 = get_secrets_manager()
        manager2 = get_secrets_manager()

        assert manager1 is manager2

    def test_get_api_key_manager_singleton(self):
        """APIKeyManager 싱글톤"""
        # 글로벌 상태 초기화
        import src.security.secrets_manager as sm
        sm._api_key_manager = None
        sm._secrets_manager = None

        manager1 = get_api_key_manager()
        manager2 = get_api_key_manager()

        assert manager1 is manager2


class TestSecretsManagerEdgeCases:
    """SecretsManager 엣지 케이스 테스트"""

    def test_store_empty_value(self, temp_secrets_path, master_key):
        """빈 값 저장"""
        manager = SecretsManager(
            master_key=master_key,
            secrets_path=temp_secrets_path
        )

        result = manager.store_secret('empty_key', '')

        assert result is True
        assert manager.get_secret('empty_key') == ''

    def test_store_unicode_value(self, temp_secrets_path, master_key):
        """유니코드 값 저장"""
        manager = SecretsManager(
            master_key=master_key,
            secrets_path=temp_secrets_path
        )

        unicode_value = "한글 API 키 테스트 🔑"
        result = manager.store_secret('unicode_key', unicode_value)

        assert result is True
        assert manager.get_secret('unicode_key') == unicode_value

    def test_store_long_value(self, temp_secrets_path, master_key):
        """긴 값 저장"""
        manager = SecretsManager(
            master_key=master_key,
            secrets_path=temp_secrets_path
        )

        long_value = 'x' * 10000
        result = manager.store_secret('long_key', long_value)

        assert result is True
        assert manager.get_secret('long_key') == long_value

    def test_multiple_keys(self, temp_secrets_path, master_key):
        """여러 키 저장 및 조회"""
        manager = SecretsManager(
            master_key=master_key,
            secrets_path=temp_secrets_path
        )

        for i in range(10):
            manager.store_secret(f'key_{i}', f'value_{i}')

        for i in range(10):
            assert manager.get_secret(f'key_{i}') == f'value_{i}'

    def test_overwrite_key(self, temp_secrets_path, master_key):
        """키 덮어쓰기"""
        manager = SecretsManager(
            master_key=master_key,
            secrets_path=temp_secrets_path
        )

        manager.store_secret('overwrite_key', 'original_value')
        manager.store_secret('overwrite_key', 'new_value')

        assert manager.get_secret('overwrite_key') == 'new_value'

    def test_concurrent_access(self, temp_secrets_path, master_key):
        """동시 접근 시뮬레이션"""
        manager = SecretsManager(
            master_key=master_key,
            secrets_path=temp_secrets_path
        )

        # 여러 작업 연속 수행
        manager.store_secret('key1', 'value1')
        manager.store_secret('key2', 'value2')
        manager.get_secret('key1')
        manager.delete_secret('key1')
        manager.get_secret('key2')

        assert manager.get_secret('key1') is None
        assert manager.get_secret('key2') == 'value2'

    def test_access_log_limit(self, temp_secrets_path, master_key):
        """접근 로그 (현재 제한 없음)"""
        manager = SecretsManager(
            master_key=master_key,
            secrets_path=temp_secrets_path
        )

        for i in range(100):
            manager._log_access('TEST', f'key_{i}', True)

        logs = manager.get_access_log()
        assert len(logs) == 100


class TestAPIKeyManagerEdgeCases:
    """APIKeyManager 엣지 케이스 테스트"""

    @pytest.fixture
    def api_manager(self, temp_secrets_path, master_key):
        """APIKeyManager 인스턴스"""
        secrets_manager = SecretsManager(
            master_key=master_key,
            secrets_path=temp_secrets_path
        )
        return APIKeyManager(secrets_manager)

    def test_store_multiple_services(self, api_manager):
        """여러 서비스 API 키 저장"""
        services = ['coinone', 'binance', 'upbit', 'bithumb']

        for service in services:
            api_manager.store_api_key(
                service=service,
                api_key=f'{service}_api_key',
                secret_key=f'{service}_secret'
            )

        for service in services:
            keys = api_manager.get_api_keys(service)
            assert keys['api_key'] == f'{service}_api_key'

    def test_rotate_nonexistent_key(self, api_manager):
        """없는 키 로테이션"""
        result = api_manager.rotate_api_keys(
            service='nonexistent',
            new_api_key='new_key'
        )

        # 새로운 키로 저장됨
        assert result is True

    def test_special_characters_in_service_name(self, api_manager):
        """특수 문자가 있는 서비스 이름"""
        result = api_manager.store_api_key(
            service='service_with-special.chars',
            api_key='test_key'
        )

        assert result is True
        keys = api_manager.get_api_keys('service_with-special.chars')
        assert keys is not None
