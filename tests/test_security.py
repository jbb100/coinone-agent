"""
Security Tests for KAIROS-1 System

보안 기능 테스트
"""

import pytest
import os
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from src.security.secrets_manager import SecretsManager, APIKeyManager
from src.core.exceptions import KairosException


class TestSecretsManager:
    """SecretsManager 테스트"""
    
    def test_initialization(self, temp_dir):
        """초기화 테스트"""
        secrets_path = temp_dir / "secrets"
        
        with pytest.MonkeyPatch().context() as m:
            m.setenv('KAIROS_MASTER_KEY', 'test_master_key_1234567890123456')
            
            manager = SecretsManager(secrets_path=str(secrets_path))
            assert manager is not None
            assert manager.secrets_path == secrets_path
    
    def test_store_and_retrieve_secret(self, mock_secrets_manager):
        """비밀 정보 저장 및 조회 테스트"""
        # 저장
        success = mock_secrets_manager.store_secret(
            'test_key',
            'test_value',
            {'description': 'Test secret'}
        )
        assert success is True
        
        # 조회
        retrieved_value = mock_secrets_manager.get_secret('test_key')
        assert retrieved_value == 'test_value'
    
    def test_nonexistent_secret(self, mock_secrets_manager):
        """존재하지 않는 비밀 정보 조회"""
        result = mock_secrets_manager.get_secret('nonexistent_key')
        assert result is None
    
    def test_secret_expiration(self, mock_secrets_manager):
        """비밀 정보 만료 테스트"""
        # 이미 만료된 비밀 정보 저장
        expired_time = (datetime.now() - timedelta(hours=1)).isoformat()
        
        success = mock_secrets_manager.store_secret(
            'expired_key',
            'expired_value',
            {'expires_at': expired_time}
        )
        assert success is True
        
        # 조회 시 None 반환되어야 함
        result = mock_secrets_manager.get_secret('expired_key')
        assert result is None
    
    def test_key_rotation(self, mock_secrets_manager):
        """키 로테이션 테스트"""
        # 원본 저장
        mock_secrets_manager.store_secret('rotate_key', 'original_value')
        
        # 로테이션
        success = mock_secrets_manager.rotate_key('rotate_key', 'new_value')
        assert success is True
        
        # 새 값 확인
        retrieved_value = mock_secrets_manager.get_secret('rotate_key')
        assert retrieved_value == 'new_value'
    
    def test_delete_secret(self, mock_secrets_manager):
        """비밀 정보 삭제 테스트"""
        # 저장
        mock_secrets_manager.store_secret('delete_key', 'delete_value')
        
        # 삭제 전 확인
        assert mock_secrets_manager.get_secret('delete_key') == 'delete_value'
        
        # 삭제
        success = mock_secrets_manager.delete_secret('delete_key')
        assert success is True
        
        # 삭제 후 확인
        assert mock_secrets_manager.get_secret('delete_key') is None
    
    def test_access_logging(self, mock_secrets_manager):
        """접근 로깅 테스트"""
        # 초기 로그 개수
        initial_log_count = len(mock_secrets_manager.get_access_log())
        
        # 몇 가지 작업 수행
        mock_secrets_manager.store_secret('log_key', 'log_value')
        mock_secrets_manager.get_secret('log_key')
        mock_secrets_manager.get_secret('nonexistent')
        
        # 로그 증가 확인
        final_log_count = len(mock_secrets_manager.get_access_log())
        assert final_log_count > initial_log_count
        
        # 로그 내용 확인
        logs = mock_secrets_manager.get_access_log()
        actions = [log['action'] for log in logs[-3:]]
        assert 'STORE' in actions
        assert 'GET' in actions
    
    def test_cache_management(self, mock_secrets_manager):
        """캐시 관리 테스트"""
        # 데이터 저장
        mock_secrets_manager.store_secret('cache_key', 'cache_value')
        
        # 캐시에 있는지 확인
        assert 'cache_key' in mock_secrets_manager._encrypted_cache
        
        # 캐시 정리
        mock_secrets_manager.clear_cache()
        
        # 캐시가 비워졌는지 확인
        assert len(mock_secrets_manager._encrypted_cache) == 0


class TestAPIKeyManager:
    """APIKeyManager 테스트"""
    
    def test_store_api_keys(self, mock_api_key_manager):
        """API 키 저장 테스트"""
        success = mock_api_key_manager.store_api_key(
            'test_service',
            'test_api_key',
            'test_secret_key'
        )
        assert success is True
    
    def test_retrieve_api_keys(self, mock_api_key_manager):
        """API 키 조회 테스트"""
        keys = mock_api_key_manager.get_api_keys('coinone')
        
        assert keys is not None
        assert 'api_key' in keys
        assert 'secret_key' in keys
        assert keys['api_key'] == 'test_api_key'
        assert keys['secret_key'] == 'test_secret_key'
    
    def test_nonexistent_service_keys(self, mock_api_key_manager):
        """존재하지 않는 서비스의 API 키 조회"""
        keys = mock_api_key_manager.get_api_keys('nonexistent_service')
        assert keys is None
    
    def test_api_key_rotation(self, mock_api_key_manager):
        """API 키 로테이션 테스트"""
        # 로테이션 수행
        success = mock_api_key_manager.rotate_api_keys(
            'coinone',
            'new_api_key',
            'new_secret_key'
        )
        assert success is True
        
        # 새 키 확인
        keys = mock_api_key_manager.get_api_keys('coinone')
        assert keys['api_key'] == 'new_api_key'
        assert keys['secret_key'] == 'new_secret_key'
    
    def test_api_key_without_secret(self, mock_api_key_manager):
        """시크릿 키 없이 API 키만 저장"""
        success = mock_api_key_manager.store_api_key(
            'simple_service',
            'simple_api_key'
        )
        assert success is True
        
        keys = mock_api_key_manager.get_api_keys('simple_service')
        assert keys['api_key'] == 'simple_api_key'
        assert keys['secret_key'] is None


class TestSecretsManagerIntegration:
    """SecretsManager 통합 테스트"""
    
    def test_persistence_across_instances(self, temp_dir):
        """인스턴스 간 데이터 지속성 테스트"""
        secrets_path = temp_dir / "persistent_secrets"
        master_key = 'test_master_key_1234567890123456'
        
        # 첫 번째 인스턴스에서 데이터 저장
        manager1 = SecretsManager(master_key=master_key, secrets_path=str(secrets_path))
        manager1.store_secret('persistent_key', 'persistent_value')
        
        # 두 번째 인스턴스에서 데이터 조회
        manager2 = SecretsManager(master_key=master_key, secrets_path=str(secrets_path))
        retrieved_value = manager2.get_secret('persistent_key')
        
        assert retrieved_value == 'persistent_value'
    
    def test_wrong_master_key(self, temp_dir):
        """잘못된 마스터 키로 복호화 시도"""
        secrets_path = temp_dir / "wrong_key_secrets"
        
        # 올바른 키로 저장
        manager1 = SecretsManager(
            master_key='correct_key_1234567890123456',
            secrets_path=str(secrets_path)
        )
        manager1.store_secret('test_key', 'test_value')
        
        # 잘못된 키로 조회 시도
        manager2 = SecretsManager(
            master_key='wrong_key_123456789012345',
            secrets_path=str(secrets_path)
        )
        
        # 복호화 실패로 None 반환되어야 함
        result = manager2.get_secret('test_key')
        assert result is None
    
    def test_file_corruption_recovery(self, temp_dir):
        """파일 손상 시 복구 테스트"""
        secrets_path = temp_dir / "corrupt_secrets"
        master_key = 'test_master_key_1234567890123456'
        
        # 정상 데이터 저장
        manager = SecretsManager(master_key=master_key, secrets_path=str(secrets_path))
        manager.store_secret('test_key', 'test_value')
        
        # 파일 손상 시뮬레이션
        with open(secrets_path, 'w') as f:
            f.write("corrupted data")
        
        # 새 인스턴스에서 복구 확인
        manager2 = SecretsManager(master_key=master_key, secrets_path=str(secrets_path))
        
        # 손상된 파일로 인해 기존 데이터는 손실되지만 새 데이터 저장 가능해야 함
        success = manager2.store_secret('new_key', 'new_value')
        assert success is True
        
        retrieved_value = manager2.get_secret('new_key')
        assert retrieved_value == 'new_value'


class TestSecurityBestPractices:
    """보안 모범 사례 테스트"""
    
    def test_no_plaintext_in_memory(self, mock_secrets_manager):
        """메모리에 평문 저장 방지 확인"""
        mock_secrets_manager.store_secret('memory_key', 'sensitive_data')
        
        # 캐시에는 암호화된 데이터만 있어야 함
        for cached_value in mock_secrets_manager._encrypted_cache.values():
            assert isinstance(cached_value, bytes)
            assert b'sensitive_data' not in cached_value
    
    def test_access_log_no_sensitive_data(self, mock_secrets_manager):
        """접근 로그에 민감한 데이터 미포함 확인"""
        mock_secrets_manager.store_secret('sensitive_key', 'super_secret_password')
        mock_secrets_manager.get_secret('sensitive_key')
        
        logs = mock_secrets_manager.get_access_log()
        
        # 로그에 실제 값이 포함되지 않았는지 확인
        log_content = json.dumps(logs)
        assert 'super_secret_password' not in log_content
    
    def test_file_permissions(self, temp_dir):
        """파일 권한 테스트 (Unix 시스템에서만)"""
        if os.name != 'posix':
            pytest.skip("Unix 시스템에서만 실행")
        
        secrets_path = temp_dir / "permission_test_secrets"
        manager = SecretsManager(
            master_key='test_key_1234567890123456',
            secrets_path=str(secrets_path)
        )
        
        manager.store_secret('perm_key', 'perm_value')
        
        # 파일 권한 확인 (600 = 소유자만 읽기/쓰기)
        file_stat = secrets_path.stat()
        file_mode = oct(file_stat.st_mode)[-3:]  # 마지막 3자리 (권한)
        
        assert file_mode == '600'
    
    def test_error_handling_no_leaks(self, temp_dir):
        """에러 처리 시 정보 누출 방지"""
        secrets_path = temp_dir / "error_test_secrets"
        
        # 잘못된 파일 경로 시뮬레이션
        invalid_path = "/root/inaccessible_secrets"  # 접근 불가능한 경로
        
        manager = SecretsManager(
            master_key='test_key_1234567890123456',
            secrets_path=invalid_path
        )
        
        # 실패해도 민감한 정보가 노출되지 않아야 함
        result = manager.store_secret('test_key', 'test_value')
        
        # 실패는 하되, 예외가 발생하지 않아야 함
        assert result is False