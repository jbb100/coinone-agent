"""
Secure Secrets Management System

API 키와 민감한 정보를 안전하게 관리하는 시스템
"""

import os
import json
import base64
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from pathlib import Path
import hashlib
from loguru import logger


class SecretsManager:
    """
    안전한 비밀 정보 관리 시스템
    
    Features:
    - 암호화된 저장소
    - 키 로테이션 지원
    - 접근 감사 로깅
    - 메모리 내 암호화
    """
    
    def __init__(self, master_key: Optional[str] = None, secrets_path: Optional[str] = None):
        """
        Args:
            master_key: 마스터 암호화 키 (환경변수에서 가져옴)
            secrets_path: 암호화된 비밀 저장 경로
        """
        self.secrets_path = Path(secrets_path or os.getenv('SECRETS_PATH', './data/.secrets'))
        self.secrets_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 마스터 키 초기화
        self._init_master_key(master_key)
        
        # 암호화 엔진 초기화
        self.cipher_suite = Fernet(self.encryption_key)
        
        # 메모리 내 캐시 (암호화된 상태로 보관)
        self._encrypted_cache: Dict[str, bytes] = {}
        
        # 접근 로그
        self.access_log: list = []
        
        # 키 로테이션 설정
        self.rotation_interval = timedelta(days=30)
        self.last_rotation = datetime.now()
        
    def _init_master_key(self, master_key: Optional[str] = None):
        """마스터 키 초기화 및 파생 키 생성"""
        if master_key:
            self.master_key = master_key.encode()
        else:
            # 환경변수 또는 하드웨어 보안 모듈에서 가져오기
            env_key = os.getenv('KAIROS_MASTER_KEY')
            if not env_key:
                # 개발 환경용 경고와 함께 기본 키 생성
                logger.warning("⚠️ 프로덕션 환경에서는 반드시 KAIROS_MASTER_KEY를 설정하세요!")
                env_key = self._generate_dev_key()
            self.master_key = env_key.encode()
        
        # PBKDF2를 사용하여 파생 키 생성
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'kairos1_salt_v1',  # 프로덕션에서는 랜덤 salt 사용
            iterations=100000,
        )
        self.encryption_key = base64.urlsafe_b64encode(
            kdf.derive(self.master_key)
        )
    
    def _generate_dev_key(self) -> str:
        """개발 환경용 키 생성"""
        hostname = os.uname().nodename
        return hashlib.sha256(f"kairos1_dev_{hostname}".encode()).hexdigest()[:32]
    
    def store_secret(self, key: str, value: str, metadata: Optional[Dict] = None) -> bool:
        """
        비밀 정보 저장
        
        Args:
            key: 비밀 정보 식별자
            value: 비밀 정보 값
            metadata: 추가 메타데이터 (만료일, 권한 등)
        
        Returns:
            저장 성공 여부
        """
        try:
            # 데이터 구조화
            secret_data = {
                'value': value,
                'created_at': datetime.now().isoformat(),
                'metadata': metadata or {},
                'version': 1
            }
            
            # JSON 직렬화 및 암호화
            json_data = json.dumps(secret_data)
            encrypted_data = self.cipher_suite.encrypt(json_data.encode())
            
            # 캐시에 저장
            self._encrypted_cache[key] = encrypted_data
            
            # 파일에 저장
            self._persist_secrets()
            
            # 감사 로그
            self._log_access('STORE', key, success=True)
            
            return True
            
        except Exception as e:
            logger.error(f"비밀 정보 저장 실패: {e}")
            self._log_access('STORE', key, success=False, error=str(e))
            return False
    
    def get_secret(self, key: str) -> Optional[str]:
        """
        비밀 정보 조회
        
        Args:
            key: 비밀 정보 식별자
            
        Returns:
            복호화된 비밀 정보 값
        """
        try:
            # 캐시 확인
            if key not in self._encrypted_cache:
                self._load_secrets()
            
            if key not in self._encrypted_cache:
                self._log_access('GET', key, success=False, error='Not found')
                return None
            
            # 복호화
            encrypted_data = self._encrypted_cache[key]
            decrypted_data = self.cipher_suite.decrypt(encrypted_data)
            secret_data = json.loads(decrypted_data.decode())
            
            # 만료 확인
            if self._is_expired(secret_data.get('metadata', {})):
                self._log_access('GET', key, success=False, error='Expired')
                return None
            
            # 감사 로그
            self._log_access('GET', key, success=True)
            
            return secret_data['value']
            
        except Exception as e:
            logger.error(f"비밀 정보 조회 실패: {e}")
            self._log_access('GET', key, success=False, error=str(e))
            return None
    
    def rotate_key(self, key: str, new_value: str) -> bool:
        """
        키 로테이션
        
        Args:
            key: 로테이션할 키
            new_value: 새로운 값
            
        Returns:
            로테이션 성공 여부
        """
        try:
            # 기존 데이터 가져오기
            old_secret = self.get_secret(key)
            if old_secret:
                # 히스토리 보관 (선택적)
                self.store_secret(
                    f"{key}_backup_{datetime.now().strftime('%Y%m%d')}",
                    old_secret,
                    {'rotated_from': key}
                )
            
            # 새 값 저장
            success = self.store_secret(
                key,
                new_value,
                {'rotated_at': datetime.now().isoformat()}
            )
            
            if success:
                logger.info(f"✅ 키 로테이션 완료: {key}")
                self._log_access('ROTATE', key, success=True)
            
            return success
            
        except Exception as e:
            logger.error(f"키 로테이션 실패: {e}")
            self._log_access('ROTATE', key, success=False, error=str(e))
            return False
    
    def delete_secret(self, key: str) -> bool:
        """
        비밀 정보 삭제
        
        Args:
            key: 삭제할 키
            
        Returns:
            삭제 성공 여부
        """
        try:
            if key in self._encrypted_cache:
                del self._encrypted_cache[key]
                self._persist_secrets()
                self._log_access('DELETE', key, success=True)
                return True
            
            self._log_access('DELETE', key, success=False, error='Not found')
            return False
            
        except Exception as e:
            logger.error(f"비밀 정보 삭제 실패: {e}")
            self._log_access('DELETE', key, success=False, error=str(e))
            return False
    
    def _persist_secrets(self):
        """암호화된 비밀 정보를 파일에 저장"""
        try:
            # 전체 캐시를 하나의 파일로 저장
            with open(self.secrets_path, 'wb') as f:
                # 캐시를 직렬화
                cache_data = {
                    k: base64.b64encode(v).decode()
                    for k, v in self._encrypted_cache.items()
                }
                
                # 전체를 다시 암호화
                json_data = json.dumps(cache_data)
                encrypted_file = self.cipher_suite.encrypt(json_data.encode())
                f.write(encrypted_file)
                
            # 파일 권한 설정 (읽기 전용)
            os.chmod(self.secrets_path, 0o600)
            
        except Exception as e:
            logger.error(f"비밀 정보 저장 실패: {e}")
    
    def _load_secrets(self):
        """파일에서 암호화된 비밀 정보 로드"""
        try:
            if not self.secrets_path.exists():
                return
            
            with open(self.secrets_path, 'rb') as f:
                encrypted_file = f.read()
                
            # 복호화
            decrypted_data = self.cipher_suite.decrypt(encrypted_file)
            cache_data = json.loads(decrypted_data.decode())
            
            # 캐시 복원
            self._encrypted_cache = {
                k: base64.b64decode(v.encode())
                for k, v in cache_data.items()
            }
            
        except Exception as e:
            logger.error(f"비밀 정보 로드 실패: {e}")
    
    def _is_expired(self, metadata: Dict) -> bool:
        """만료 여부 확인"""
        if 'expires_at' in metadata:
            expires_at = datetime.fromisoformat(metadata['expires_at'])
            return datetime.now() > expires_at
        return False
    
    def _log_access(self, action: str, key: str, success: bool, error: Optional[str] = None):
        """접근 감사 로그"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'key': key,
            'success': success,
            'error': error
        }
        
        self.access_log.append(log_entry)
        
        # 로그 파일에도 기록 (민감한 값은 제외)
        if not success:
            logger.warning(f"Secret access failed: {action} {key} - {error}")
        else:
            logger.debug(f"Secret access: {action} {key}")
    
    def get_access_log(self) -> list:
        """접근 로그 조회"""
        return self.access_log.copy()
    
    def clear_cache(self):
        """메모리 캐시 안전하게 정리"""
        # 메모리에서 완전히 제거
        for key in list(self._encrypted_cache.keys()):
            del self._encrypted_cache[key]
        
        self._encrypted_cache.clear()
        logger.info("메모리 캐시 정리 완료")


class APIKeyManager:
    """
    API 키 전용 관리자
    
    SecretsManager를 확장하여 API 키 특화 기능 제공
    """
    
    def __init__(self, secrets_manager: Optional[SecretsManager] = None):
        self.secrets = secrets_manager or SecretsManager()
        self.key_prefix = "api_key_"
        
    def store_api_key(
        self,
        service: str,
        api_key: str,
        secret_key: Optional[str] = None,
        expires_days: int = 90
    ) -> bool:
        """
        API 키 저장
        
        Args:
            service: 서비스 이름 (예: coinone, binance)
            api_key: API 키
            secret_key: API 시크릿 키
            expires_days: 만료 일수
        """
        key_data = {
            'api_key': api_key,
            'secret_key': secret_key
        }
        
        metadata = {
            'service': service,
            'expires_at': (datetime.now() + timedelta(days=expires_days)).isoformat()
        }
        
        return self.secrets.store_secret(
            f"{self.key_prefix}{service}",
            json.dumps(key_data),
            metadata
        )
    
    def get_api_keys(self, service: str) -> Optional[Dict[str, str]]:
        """
        API 키 조회
        
        Args:
            service: 서비스 이름
            
        Returns:
            {'api_key': str, 'secret_key': str} 또는 None
        """
        secret_data = self.secrets.get_secret(f"{self.key_prefix}{service}")
        
        if secret_data:
            return json.loads(secret_data)
        
        return None
    
    def delete_api_keys(self, service: str) -> bool:
        """
        API 키 삭제
        
        Args:
            service: 서비스 이름
            
        Returns:
            삭제 성공 여부
        """
        return self.secrets.delete_secret(f"{self.key_prefix}{service}")
    
    def rotate_api_keys(
        self,
        service: str,
        new_api_key: str,
        new_secret_key: Optional[str] = None
    ) -> bool:
        """API 키 로테이션"""
        new_data = {
            'api_key': new_api_key,
            'secret_key': new_secret_key
        }
        
        return self.secrets.rotate_key(
            f"{self.key_prefix}{service}",
            json.dumps(new_data)
        )
    
    def check_expiration(self, service: str) -> Optional[datetime]:
        """API 키 만료일 확인"""
        # 구현 필요
        pass


# 싱글톤 인스턴스
_secrets_manager = None
_api_key_manager = None


def get_secrets_manager() -> SecretsManager:
    """SecretsManager 싱글톤 인스턴스 반환"""
    global _secrets_manager
    if _secrets_manager is None:
        _secrets_manager = SecretsManager()
    return _secrets_manager


def get_api_key_manager() -> APIKeyManager:
    """APIKeyManager 싱글톤 인스턴스 반환"""
    global _api_key_manager
    if _api_key_manager is None:
        _api_key_manager = APIKeyManager(get_secrets_manager())
    return _api_key_manager