"""
Configuration Loader

YAML 설정 파일 로딩 및 관리를 담당하는 모듈
"""

import os
import yaml
from typing import Any, Dict, Optional
from pathlib import Path
from cryptography.fernet import Fernet
from loguru import logger


class ConfigLoader:
    """
    설정 파일 로더
    
    YAML 설정 파일을 로드하고 환경 변수 치환, 암호화된 값 복호화 등을 제공합니다.
    """
    
    def __init__(self, config_path: str):
        """
        Args:
            config_path: 설정 파일 경로
        """
        self.config_path = Path(config_path)
        self._config_data = {}
        self._encryption_key = None
        
        # 설정 파일 로드
        self._load_config()
        
        # 암호화 키 로드 (필요시)
        self._load_encryption_key()
        
        logger.info(f"ConfigLoader 초기화: {config_path}")
    
    def _load_config(self):
        """설정 파일 로드"""
        try:
            if not self.config_path.exists():
                raise FileNotFoundError(f"설정 파일을 찾을 수 없습니다: {self.config_path}")
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config_data = yaml.safe_load(f)
            
            # 환경 변수 치환
            self._substitute_env_vars(self._config_data)
            
            logger.info("설정 파일 로드 완료")
            
        except Exception as e:
            logger.error(f"설정 파일 로드 실패: {e}")
            raise
    
    def _substitute_env_vars(self, data: Any) -> Any:
        """
        환경 변수 치환
        
        ${ENV_VAR} 형태의 문자열을 환경 변수 값으로 치환합니다.
        """
        if isinstance(data, dict):
            for key, value in data.items():
                data[key] = self._substitute_env_vars(value)
        elif isinstance(data, list):
            for i, item in enumerate(data):
                data[i] = self._substitute_env_vars(item)
        elif isinstance(data, str):
            # ${VAR_NAME} 패턴 치환
            if data.startswith("${") and data.endswith("}"):
                env_var = data[2:-1]
                default_value = None
                
                # ${VAR_NAME:default_value} 패턴 지원
                if ":" in env_var:
                    env_var, default_value = env_var.split(":", 1)
                
                data = os.environ.get(env_var, default_value or data)
        
        return data
    
    def _load_encryption_key(self):
        """암호화 키 로드"""
        try:
            encryption_config = self.get("security.encryption", {})
            
            if not encryption_config.get("enabled", False):
                return
            
            key_file = encryption_config.get("key_file", "./config/.encryption_key")
            key_path = Path(key_file)
            
            if key_path.exists():
                with open(key_path, 'rb') as f:
                    self._encryption_key = f.read()
                logger.info("암호화 키 로드 완료")
            else:
                logger.warning(f"암호화 키 파일을 찾을 수 없습니다: {key_path}")
                
        except Exception as e:
            logger.error(f"암호화 키 로드 실패: {e}")
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        설정 값 조회
        
        Args:
            key_path: 점(.)으로 구분된 키 경로 (예: "api.coinone.api_key")
            default: 기본값
            
        Returns:
            설정 값
        """
        try:
            keys = key_path.split('.')
            current = self._config_data
            
            for key in keys:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    return default
            
            # 암호화된 값인지 확인하고 복호화
            if self._is_encrypted_value(current):
                return self._decrypt_value(current)
            
            return current
            
        except Exception as e:
            logger.error(f"설정 값 조회 실패: {key_path} - {e}")
            return default
    
    def set(self, key_path: str, value: Any):
        """
        설정 값 설정 (런타임 전용)
        
        Args:
            key_path: 점(.)으로 구분된 키 경로
            value: 설정할 값
        """
        try:
            keys = key_path.split('.')
            current = self._config_data
            
            # 중간 딕셔너리들 생성
            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]
            
            # 최종 값 설정
            current[keys[-1]] = value
            
        except Exception as e:
            logger.error(f"설정 값 설정 실패: {key_path} - {e}")
    
    def _is_encrypted_value(self, value: str) -> bool:
        """암호화된 값인지 확인"""
        return (isinstance(value, str) and 
                value.startswith("encrypted:") and 
                self._encryption_key is not None)
    
    def _decrypt_value(self, encrypted_value: str) -> str:
        """암호화된 값 복호화"""
        try:
            if not self._encryption_key:
                logger.warning("암호화 키가 없어 복호화할 수 없습니다.")
                return encrypted_value
            
            # "encrypted:" 접두사 제거
            encrypted_data = encrypted_value[10:]  # len("encrypted:") = 10
            
            fernet = Fernet(self._encryption_key)
            decrypted = fernet.decrypt(encrypted_data.encode()).decode()
            
            return decrypted
            
        except Exception as e:
            logger.error(f"값 복호화 실패: {e}")
            return encrypted_value
    
    def encrypt_value(self, plain_value: str) -> str:
        """
        값 암호화
        
        Args:
            plain_value: 평문 값
            
        Returns:
            암호화된 값 ("encrypted:" 접두사 포함)
        """
        try:
            if not self._encryption_key:
                # 암호화 키가 없으면 새로 생성
                self._generate_encryption_key()
            
            fernet = Fernet(self._encryption_key)
            encrypted = fernet.encrypt(plain_value.encode())
            
            return f"encrypted:{encrypted.decode()}"
            
        except Exception as e:
            logger.error(f"값 암호화 실패: {e}")
            return plain_value
    
    def _generate_encryption_key(self):
        """새 암호화 키 생성 및 저장"""
        try:
            encryption_config = self.get("security.encryption", {})
            key_file = encryption_config.get("key_file", "./config/.encryption_key")
            key_path = Path(key_file)
            
            # 디렉토리 생성
            key_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 새 키 생성
            self._encryption_key = Fernet.generate_key()
            
            # 키 파일 저장
            with open(key_path, 'wb') as f:
                f.write(self._encryption_key)
            
            # 파일 권한 설정 (Unix 계열)
            if os.name != 'nt':  # Windows가 아닌 경우
                os.chmod(key_path, 0o600)  # 소유자만 읽기/쓰기
            
            logger.info(f"새 암호화 키 생성 및 저장: {key_path}")
            
        except Exception as e:
            logger.error(f"암호화 키 생성 실패: {e}")
    
    def validate_required_config(self, required_keys: list) -> bool:
        """
        필수 설정 값 검증
        
        Args:
            required_keys: 필수 키 목록
            
        Returns:
            검증 통과 여부
        """
        missing_keys = []
        
        for key in required_keys:
            value = self.get(key)
            if value is None or value == "":
                missing_keys.append(key)
        
        if missing_keys:
            logger.error(f"필수 설정 값 누락: {missing_keys}")
            return False
        
        logger.info("필수 설정 값 검증 통과")
        return True
    
    def get_api_config(self) -> Dict[str, Any]:
        """API 설정 반환"""
        return self.get("api", {})
    
    def get_strategy_config(self) -> Dict[str, Any]:
        """투자 전략 설정 반환"""
        return self.get("strategy", {})
    
    def get_risk_config(self) -> Dict[str, Any]:
        """리스크 관리 설정 반환"""
        return self.get("risk_management", {})
    
    def get_notification_config(self) -> Dict[str, Any]:
        """알림 설정 반환"""
        return self.get("notifications", {})
    
    def is_sandbox_mode(self) -> bool:
        """샌드박스 모드 여부 확인"""
        return self.get("api.coinone.sandbox", True)
    
    def is_debug_mode(self) -> bool:
        """디버그 모드 여부 확인"""
        return self.get("development.debug", False)
    
    def is_paper_trading(self) -> bool:
        """페이퍼 트레이딩 모드 여부 확인"""
        return self.get("development.paper_trading.enabled", False)
    
    def reload_config(self):
        """설정 파일 다시 로드"""
        try:
            logger.info("설정 파일 다시 로드 시작")
            self._load_config()
            self._load_encryption_key()
            logger.info("설정 파일 다시 로드 완료")
            
        except Exception as e:
            logger.error(f"설정 파일 다시 로드 실패: {e}")
            raise
    
    def to_dict(self) -> Dict[str, Any]:
        """설정을 딕셔너리로 반환 (민감한 정보 제외)"""
        config_copy = self._config_data.copy()
        
        # 민감한 정보 마스킹
        self._mask_sensitive_data(config_copy)
        
        return config_copy
    
    def _mask_sensitive_data(self, data: Any, sensitive_keys: list = None):
        """민감한 데이터 마스킹"""
        if sensitive_keys is None:
            sensitive_keys = [
                "api_key", "secret_key", "password", "token", 
                "webhook_url", "private_key", "secret"
            ]
        
        if isinstance(data, dict):
            for key, value in data.items():
                if any(sensitive in key.lower() for sensitive in sensitive_keys):
                    if isinstance(value, str) and len(value) > 4:
                        data[key] = value[:4] + "*" * (len(value) - 4)
                    else:
                        data[key] = "***"
                else:
                    self._mask_sensitive_data(value, sensitive_keys)
        elif isinstance(data, list):
            for item in data:
                self._mask_sensitive_data(item, sensitive_keys)


# 설정 검증을 위한 필수 키 목록
REQUIRED_CONFIG_KEYS = [
    "api.coinone.api_key",
    "api.coinone.secret_key",
    "strategy.market_season.buffer_band",
    "strategy.portfolio.core.BTC",
    "strategy.portfolio.core.ETH",
    "logging.level"
] 