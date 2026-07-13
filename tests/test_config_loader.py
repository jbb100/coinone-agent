"""
Config Loader 테스트 모듈

설정 파일 로더 테스트
"""

import pytest
import os
import tempfile
import yaml
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.utils.config_loader import ConfigLoader, REQUIRED_CONFIG_KEYS


class TestConfigLoader:
    """ConfigLoader 클래스 테스트"""

    @pytest.fixture
    def temp_config_file(self):
        """임시 설정 파일 생성"""
        config_data = {
            'logging': {
                'level': 'INFO'
            },
            'api': {
                'coinone': {
                    'api_key': 'test_key',
                    'secret_key': 'test_secret',
                    'sandbox': True
                }
            },
            'strategy': {
                'rebalancing': {
                    'threshold': 1.0
                }
            },
            'risk_management': {
                'max_position_size': 0.25
            },
            'notifications': {
                'slack': {
                    'enabled': True
                }
            },
            'development': {
                'debug': True,
                'paper_trading': {
                    'enabled': True
                }
            },
            'security': {
                'encryption': {
                    'enabled': False
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        yield temp_path

        # 정리
        os.unlink(temp_path)

    @pytest.fixture
    def loader(self, temp_config_file):
        """ConfigLoader 인스턴스"""
        return ConfigLoader(temp_config_file)

    def test_init(self, loader):
        """초기화 테스트"""
        assert loader._config_data is not None
        assert 'logging' in loader._config_data

    def test_file_not_found(self):
        """파일 없음 에러"""
        with pytest.raises(FileNotFoundError):
            ConfigLoader('/nonexistent/path/config.yaml')

    def test_get_simple_key(self, loader):
        """단순 키 조회"""
        result = loader.get('logging.level')
        assert result == 'INFO'

    def test_get_nested_key(self, loader):
        """중첩 키 조회"""
        result = loader.get('api.coinone.api_key')
        assert result == 'test_key'

    def test_get_default_value(self, loader):
        """기본값 반환"""
        result = loader.get('nonexistent.key', 'default')
        assert result == 'default'

    def test_get_none_for_missing(self, loader):
        """없는 키에 None 반환"""
        result = loader.get('nonexistent.key')
        assert result is None

    def test_set_value(self, loader):
        """값 설정"""
        loader.set('new.key.path', 'new_value')
        result = loader.get('new.key.path')
        assert result == 'new_value'

    def test_set_nested_value(self, loader):
        """중첩 값 설정"""
        loader.set('deep.nested.key', {'data': 'value'})
        result = loader.get('deep.nested.key')
        assert result == {'data': 'value'}

    def test_get_api_config(self, loader):
        """API 설정 조회"""
        api_config = loader.get_api_config()
        assert 'coinone' in api_config

    def test_get_strategy_config(self, loader):
        """전략 설정 조회"""
        strategy_config = loader.get_strategy_config()
        assert 'rebalancing' in strategy_config

    def test_get_risk_config(self, loader):
        """리스크 설정 조회"""
        risk_config = loader.get_risk_config()
        assert 'max_position_size' in risk_config

    def test_get_notification_config(self, loader):
        """알림 설정 조회"""
        notification_config = loader.get_notification_config()
        assert 'slack' in notification_config

    def test_is_sandbox_mode(self, loader):
        """샌드박스 모드 확인"""
        result = loader.is_sandbox_mode()
        assert result is True

    def test_is_debug_mode(self, loader):
        """디버그 모드 확인"""
        result = loader.is_debug_mode()
        assert result is True

    def test_is_paper_trading(self, loader):
        """페이퍼 트레이딩 모드 확인"""
        result = loader.is_paper_trading()
        assert result is True

    def test_get_config(self, loader):
        """전체 설정 조회"""
        config = loader.get_config()
        assert isinstance(config, dict)
        assert 'logging' in config

    def test_validate_required_config_pass(self, loader):
        """필수 설정 검증 통과"""
        result = loader.validate_required_config()
        assert result is True

    def test_validate_required_config_skip(self):
        """API 검증 건너뛰기"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({'logging': {'level': 'INFO'}}, f)
            temp_path = f.name

        try:
            loader = ConfigLoader(temp_path, skip_api_validation=True)
            result = loader.validate_required_config()
            assert result is True
        finally:
            os.unlink(temp_path)

    def test_validate_required_config_fail(self):
        """필수 설정 검증 실패"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({'empty': {}}, f)
            temp_path = f.name

        try:
            loader = ConfigLoader(temp_path)
            result = loader.validate_required_config()
            assert result is False
        finally:
            os.unlink(temp_path)

    def test_to_dict_masks_sensitive(self, loader):
        """민감 정보 마스킹"""
        result = loader.to_dict()

        # api_key가 마스킹되어야 함
        api_key = result.get('api', {}).get('coinone', {}).get('api_key', '')
        if len(api_key) > 4:
            assert '*' in api_key


class TestConfigLoaderEnvVars:
    """환경 변수 치환 테스트"""

    def test_substitute_env_var(self):
        """환경 변수 치환"""
        config_data = {
            'api': {
                'key': '${TEST_API_KEY}'
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        try:
            os.environ['TEST_API_KEY'] = 'substituted_value'
            loader = ConfigLoader(temp_path)
            result = loader.get('api.key')
            assert result == 'substituted_value'
        finally:
            os.unlink(temp_path)
            del os.environ['TEST_API_KEY']

    def test_substitute_env_var_with_default(self):
        """기본값 있는 환경 변수"""
        config_data = {
            'api': {
                'key': '${NONEXISTENT_VAR:default_value}'
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        try:
            loader = ConfigLoader(temp_path)
            result = loader.get('api.key')
            assert result == 'default_value'
        finally:
            os.unlink(temp_path)


class TestConfigLoaderEncryption:
    """암호화 기능 테스트"""

    @pytest.fixture
    def loader_with_encryption(self, tmp_path):
        """암호화 활성화 로더"""
        config_data = {
            'logging': {'level': 'INFO'},
            'security': {
                'encryption': {
                    'enabled': True,
                    'key_file': str(tmp_path / '.encryption_key')
                }
            }
        }

        config_path = tmp_path / 'config.yaml'
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)

        return ConfigLoader(str(config_path))

    def test_is_encrypted_value_false(self, loader_with_encryption):
        """비암호화 값 확인"""
        result = loader_with_encryption._is_encrypted_value('plain_text')
        assert result is False

    def test_is_encrypted_value_true(self, loader_with_encryption):
        """암호화 값 확인 (키 없으면 False)"""
        # 암호화 키가 없으므로 False
        result = loader_with_encryption._is_encrypted_value('encrypted:abc123')
        assert result is False

    def test_encrypt_and_decrypt(self, loader_with_encryption):
        """암호화 및 복호화"""
        plain_value = 'secret_data'

        # 암호화
        encrypted = loader_with_encryption.encrypt_value(plain_value)

        # 복호화
        decrypted = loader_with_encryption._decrypt_value(encrypted)

        assert decrypted == plain_value


class TestConfigLoaderReload:
    """설정 다시 로드 테스트"""

    def test_reload_config(self):
        """설정 다시 로드"""
        config_data = {'logging': {'level': 'INFO'}}

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        try:
            loader = ConfigLoader(temp_path)
            assert loader.get('logging.level') == 'INFO'

            # 설정 파일 변경
            with open(temp_path, 'w') as f:
                yaml.dump({'logging': {'level': 'DEBUG'}}, f)

            # 다시 로드
            loader.reload_config()

            assert loader.get('logging.level') == 'DEBUG'
        finally:
            os.unlink(temp_path)


class TestRequiredConfigKeys:
    """필수 설정 키 테스트"""

    def test_required_keys_exist(self):
        """필수 키 목록 존재"""
        assert isinstance(REQUIRED_CONFIG_KEYS, list)
        assert len(REQUIRED_CONFIG_KEYS) > 0

    def test_logging_level_required(self):
        """logging.level이 필수 키에 포함"""
        assert 'logging.level' in REQUIRED_CONFIG_KEYS


class TestConfigLoaderEnvVarSubstitution:
    """환경 변수 치환 추가 테스트"""

    def test_substitute_env_var_in_list(self):
        """리스트 내 환경 변수 치환 (라인 68-70)"""
        config_data = {
            'items': ['${TEST_LIST_VAR}', 'normal_item']
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        try:
            os.environ['TEST_LIST_VAR'] = 'list_substituted'
            loader = ConfigLoader(temp_path)
            result = loader.get('items')
            assert result[0] == 'list_substituted'
            assert result[1] == 'normal_item'
        finally:
            os.unlink(temp_path)
            del os.environ['TEST_LIST_VAR']

    def test_substitute_env_var_no_substitution(self):
        """환경 변수 패턴이 아닌 문자열"""
        config_data = {
            'normal': 'not_a_variable',
            'partial': '$NOT_COMPLETE'
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        try:
            loader = ConfigLoader(temp_path)
            assert loader.get('normal') == 'not_a_variable'
            assert loader.get('partial') == '$NOT_COMPLETE'
        finally:
            os.unlink(temp_path)


class TestConfigLoaderEncryptionKeyLoading:
    """암호화 키 로딩 테스트"""

    def test_encryption_key_file_not_found(self, tmp_path):
        """암호화 키 파일 없음 (라인 100-101)"""
        config_data = {
            'logging': {'level': 'INFO'},
            'security': {
                'encryption': {
                    'enabled': True,
                    'key_file': str(tmp_path / 'nonexistent_key')
                }
            }
        }

        config_path = tmp_path / 'config.yaml'
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)

        loader = ConfigLoader(str(config_path))
        # 암호화 키가 없어야 함
        assert loader._encryption_key is None

    def test_encryption_key_load_exception(self, tmp_path):
        """암호화 키 로드 예외 (라인 103-104)"""
        config_data = {
            'logging': {'level': 'INFO'},
            'security': {
                'encryption': {
                    'enabled': True,
                    'key_file': str(tmp_path / 'bad_key')
                }
            }
        }

        # 읽을 수 없는 파일 생성 (디렉토리로 생성)
        bad_key_path = tmp_path / 'bad_key'
        bad_key_path.mkdir()

        config_path = tmp_path / 'config.yaml'
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)

        loader = ConfigLoader(str(config_path))
        # 예외 발생해도 초기화 성공
        assert loader is not None


class TestConfigLoaderGetSetExceptions:
    """get/set 메서드 예외 처리 테스트"""

    def test_get_exception_handling(self, tmp_path):
        """get 메서드 예외 처리 (라인 133-135)"""
        config_data = {'logging': {'level': 'INFO'}}

        config_path = tmp_path / 'config.yaml'
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)

        loader = ConfigLoader(str(config_path))

        # _config_data를 예외를 발생시키는 객체로 교체
        class BadDict:
            def __getitem__(self, key):
                raise Exception("Get error")

        loader._config_data = BadDict()

        result = loader.get('any.key', 'default')
        assert result == 'default'

    def test_set_exception_handling(self, tmp_path):
        """set 메서드 예외 처리 (라인 158-159)"""
        config_data = {'logging': {'level': 'INFO'}}

        config_path = tmp_path / 'config.yaml'
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)

        loader = ConfigLoader(str(config_path))

        # _config_data를 예외를 발생시키는 객체로 교체
        class BadDict:
            def __setitem__(self, key, value):
                raise Exception("Set error")
            def __contains__(self, key):
                return False

        loader._config_data = BadDict()

        # 예외 발생해도 크래시 안함
        loader.set('any.key', 'value')


class TestConfigLoaderDecryption:
    """복호화 테스트"""

    def test_decrypt_value_no_key(self, tmp_path):
        """암호화 키 없이 복호화 시도 (라인 170-172)"""
        config_data = {'logging': {'level': 'INFO'}}

        config_path = tmp_path / 'config.yaml'
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)

        loader = ConfigLoader(str(config_path))
        loader._encryption_key = None

        result = loader._decrypt_value('encrypted:abc123')
        assert result == 'encrypted:abc123'

    def test_decrypt_value_exception(self, tmp_path):
        """복호화 예외 (라인 182-184)"""
        config_data = {
            'logging': {'level': 'INFO'},
            'security': {
                'encryption': {
                    'enabled': True,
                    'key_file': str(tmp_path / '.key')
                }
            }
        }

        config_path = tmp_path / 'config.yaml'
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)

        loader = ConfigLoader(str(config_path))

        # 암호화 키 수동 설정
        from cryptography.fernet import Fernet
        loader._encryption_key = Fernet.generate_key()

        # 잘못된 암호화 데이터로 복호화 시도
        result = loader._decrypt_value('encrypted:invalid_data')
        assert result == 'encrypted:invalid_data'


class TestConfigLoaderEncryptValue:
    """암호화 테스트"""

    def test_encrypt_value_success(self, tmp_path):
        """값 암호화 성공"""
        config_data = {
            'logging': {'level': 'INFO'},
            'security': {
                'encryption': {
                    'enabled': True,
                    'key_file': str(tmp_path / '.key')
                }
            }
        }

        config_path = tmp_path / 'config.yaml'
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)

        loader = ConfigLoader(str(config_path))

        encrypted = loader.encrypt_value('my_secret')
        assert encrypted.startswith('encrypted:')

    def test_encrypt_value_exception(self, tmp_path):
        """암호화 예외 (라인 206-208)"""
        config_data = {'logging': {'level': 'INFO'}}

        config_path = tmp_path / 'config.yaml'
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)

        loader = ConfigLoader(str(config_path))
        loader._encryption_key = b'invalid_key'  # 잘못된 키

        result = loader.encrypt_value('my_secret')
        assert result == 'my_secret'  # 실패 시 원본 반환


class TestConfigLoaderReloadException:
    """설정 재로드 예외 테스트"""

    def test_reload_config_exception(self, tmp_path):
        """reload_config 예외 (라인 303-305)"""
        config_data = {'logging': {'level': 'INFO'}}

        config_path = tmp_path / 'config.yaml'
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)

        loader = ConfigLoader(str(config_path))

        # 파일 삭제
        os.unlink(config_path)

        with pytest.raises(FileNotFoundError):
            loader.reload_config()


class TestConfigLoaderMaskSensitiveData:
    """민감 정보 마스킹 테스트"""

    def test_mask_sensitive_data_in_list(self, tmp_path):
        """리스트 내 민감 정보 마스킹 (라인 337-339)"""
        config_data = {
            'logging': {'level': 'INFO'},
            'accounts': [
                {'api_key': 'secret_key_1234', 'name': 'account1'},
                {'api_key': 'another_key_5678', 'name': 'account2'}
            ]
        }

        config_path = tmp_path / 'config.yaml'
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)

        loader = ConfigLoader(str(config_path))
        result = loader.to_dict()

        # 리스트 내 api_key가 마스킹되어야 함
        for account in result['accounts']:
            if len(account['api_key']) > 4:
                assert '*' in account['api_key']

    def test_mask_sensitive_data_short_value(self, tmp_path):
        """짧은 민감 값 마스킹 (라인 333-334)"""
        config_data = {
            'logging': {'level': 'INFO'},
            'api': {
                'api_key': 'ab'  # 4자 이하
            }
        }

        config_path = tmp_path / 'config.yaml'
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)

        loader = ConfigLoader(str(config_path))
        result = loader.to_dict()

        # 짧은 값은 ***로 마스킹
        assert result['api']['api_key'] == '***'

    def test_mask_sensitive_data_nested_list(self, tmp_path):
        """중첩된 리스트 마스킹"""
        config_data = {
            'logging': {'level': 'INFO'},
            'configs': [
                [{'password': 'nested_secret_123'}],
                {'token': 'token_value_456'}
            ]
        }

        config_path = tmp_path / 'config.yaml'
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)

        loader = ConfigLoader(str(config_path))
        result = loader.to_dict()

        # 중첩 구조도 마스킹
        assert '*' in result['configs'][0][0]['password']
        assert '*' in result['configs'][1]['token']


class TestConfigLoaderValidation:
    """설정 검증 추가 테스트"""

    def test_validate_with_custom_keys(self, tmp_path):
        """커스텀 필수 키로 검증"""
        config_data = {
            'logging': {'level': 'INFO'},
            'custom': {'required_key': 'present'}
        }

        config_path = tmp_path / 'config.yaml'
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)

        loader = ConfigLoader(str(config_path))

        # 커스텀 키 검증 - 존재하는 키
        result = loader.validate_required_config(['custom.required_key'])
        assert result is True

        # 커스텀 키 검증 - 없는 키
        result = loader.validate_required_config(['nonexistent.key'])
        assert result is False

    def test_validate_with_empty_value(self, tmp_path):
        """빈 값 검증"""
        config_data = {
            'logging': {'level': ''}
        }

        config_path = tmp_path / 'config.yaml'
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)

        loader = ConfigLoader(str(config_path))
        result = loader.validate_required_config(['logging.level'])

        assert result is False


class TestEncryptionKeyWarning:
    """암호화 키 부재 경고 — 실제로 암호화된 값이 있을 때만 경고.

    운영 로그에 매 실행마다 무의미한 WARNING이 찍히는 것 방지
    (API 키는 crontab 환경변수로 주입, config에 encrypted: 값 없음)."""

    def _load_with_capture(self, tmp_path, config_data):
        import yaml
        from loguru import logger as loguru_logger
        path = tmp_path / "config.yaml"
        with open(path, "w") as f:
            yaml.dump(config_data, f)
        records = []
        sink = loguru_logger.add(
            lambda m: records.append(m.record), level="DEBUG"
        )
        try:
            ConfigLoader(str(path))
        finally:
            loguru_logger.remove(sink)
        return records

    def test_no_encrypted_values_no_warning(self, tmp_path):
        records = self._load_with_capture(tmp_path, {
            "security": {"encryption": {"enabled": True,
                                        "key_file": "/nonexistent/key"}},
            "api": {"coinone": {"api_key": "plain-value"}},
        })
        warnings = [r for r in records
                    if r["level"].name == "WARNING" and "암호화 키" in r["message"]]
        assert warnings == []

    def test_encrypted_values_present_warns(self, tmp_path):
        records = self._load_with_capture(tmp_path, {
            "security": {"encryption": {"enabled": True,
                                        "key_file": "/nonexistent/key"}},
            "api": {"coinone": {"api_key": "encrypted:abc123"}},
        })
        warnings = [r for r in records
                    if r["level"].name == "WARNING" and "암호화 키" in r["message"]]
        assert warnings
