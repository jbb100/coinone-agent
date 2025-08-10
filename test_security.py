#!/usr/bin/env python3
"""
보안 모듈 단독 테스트 스크립트
"""

import sys
import os
from pathlib import Path

# 프로젝트 루트 경로 추가
sys.path.append('/Users/jongdal100/git/coinone-agent')

def test_secrets_manager():
    """SecretsManager 테스트"""
    print("🔐 SecretsManager 테스트 시작...")
    
    try:
        from src.security.secrets_manager import SecretsManager, get_secrets_manager
        
        # 임시 테스트 파일 경로
        test_secrets_path = "/tmp/test_secrets"
        
        # SecretsManager 초기화
        manager = SecretsManager(
            master_key="test_master_key_32_characters_long!!",
            secrets_path=test_secrets_path
        )
        
        print("✅ SecretsManager 초기화 성공")
        
        # 비밀 정보 저장 테스트
        success = manager.store_secret("test_key", "test_value", {"description": "테스트 비밀"})
        assert success, "비밀 정보 저장 실패"
        print("✅ 비밀 정보 저장 성공")
        
        # 비밀 정보 조회 테스트
        retrieved = manager.get_secret("test_key")
        assert retrieved == "test_value", f"비밀 정보 조회 실패: expected 'test_value', got '{retrieved}'"
        print("✅ 비밀 정보 조회 성공")
        
        # 키 로테이션 테스트
        success = manager.rotate_key("test_key", "new_test_value")
        assert success, "키 로테이션 실패"
        
        rotated = manager.get_secret("test_key")
        assert rotated == "new_test_value", f"로테이션된 값 조회 실패: expected 'new_test_value', got '{rotated}'"
        print("✅ 키 로테이션 성공")
        
        # 접근 로그 확인
        logs = manager.get_access_log()
        assert len(logs) > 0, "접근 로그가 비어있음"
        print(f"✅ 접근 로그 확인: {len(logs)}개 기록")
        
        # 정리
        if os.path.exists(test_secrets_path):
            os.remove(test_secrets_path)
        
        print("🎉 SecretsManager 모든 테스트 통과!")
        return True
        
    except Exception as e:
        print(f"❌ SecretsManager 테스트 실패: {e}")
        return False

def test_api_key_manager():
    """APIKeyManager 테스트"""
    print("\n🔑 APIKeyManager 테스트 시작...")
    
    try:
        from src.security.secrets_manager import APIKeyManager, SecretsManager
        
        # SecretsManager 먼저 생성
        test_secrets_path = "/tmp/test_api_secrets"
        secrets_manager = SecretsManager(
            master_key="test_master_key_32_characters_long!!",
            secrets_path=test_secrets_path
        )
        
        # APIKeyManager 생성
        api_manager = APIKeyManager(secrets_manager)
        print("✅ APIKeyManager 초기화 성공")
        
        # API 키 저장 테스트
        success = api_manager.store_api_key("test_service", "test_api_key", "test_secret_key")
        assert success, "API 키 저장 실패"
        print("✅ API 키 저장 성공")
        
        # API 키 조회 테스트
        keys = api_manager.get_api_keys("test_service")
        assert keys is not None, "API 키 조회 실패"
        assert keys["api_key"] == "test_api_key", "API 키 불일치"
        assert keys["secret_key"] == "test_secret_key", "Secret 키 불일치"
        print("✅ API 키 조회 성공")
        
        # API 키 로테이션 테스트
        success = api_manager.rotate_api_keys("test_service", "new_api_key", "new_secret_key")
        assert success, "API 키 로테이션 실패"
        
        rotated_keys = api_manager.get_api_keys("test_service")
        assert rotated_keys["api_key"] == "new_api_key", "로테이션된 API 키 불일치"
        assert rotated_keys["secret_key"] == "new_secret_key", "로테이션된 Secret 키 불일치"
        print("✅ API 키 로테이션 성공")
        
        # 없는 서비스 조회 테스트
        nonexistent = api_manager.get_api_keys("nonexistent_service")
        assert nonexistent is None, "존재하지 않는 서비스에서 None이 반환되지 않음"
        print("✅ 존재하지 않는 서비스 처리 성공")
        
        # 정리
        if os.path.exists(test_secrets_path):
            os.remove(test_secrets_path)
        
        print("🎉 APIKeyManager 모든 테스트 통과!")
        return True
        
    except Exception as e:
        print(f"❌ APIKeyManager 테스트 실패: {e}")
        return False

def test_global_instances():
    """전역 인스턴스 테스트"""
    print("\n🌐 전역 인스턴스 테스트 시작...")
    
    try:
        from src.security.secrets_manager import get_secrets_manager, get_api_key_manager
        
        # 전역 SecretsManager 테스트
        manager1 = get_secrets_manager()
        manager2 = get_secrets_manager()
        assert manager1 is manager2, "전역 SecretsManager 인스턴스가 동일하지 않음"
        print("✅ 전역 SecretsManager 싱글톤 확인")
        
        # 전역 APIKeyManager 테스트  
        api_manager1 = get_api_key_manager()
        api_manager2 = get_api_key_manager()
        assert api_manager1 is api_manager2, "전역 APIKeyManager 인스턴스가 동일하지 않음"
        print("✅ 전역 APIKeyManager 싱글톤 확인")
        
        print("🎉 전역 인스턴스 모든 테스트 통과!")
        return True
        
    except Exception as e:
        print(f"❌ 전역 인스턴스 테스트 실패: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("🔐 KAIROS-1 보안 모듈 단독 테스트")
    print("=" * 60)
    
    results = []
    
    # 각 테스트 실행
    results.append(test_secrets_manager())
    results.append(test_api_key_manager())
    results.append(test_global_instances())
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("📊 테스트 결과 요약")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    print(f"✅ 통과: {passed}/{total}")
    print(f"❌ 실패: {total - passed}/{total}")
    
    if all(results):
        print("🎉 모든 보안 모듈 테스트 통과!")
        exit(0)
    else:
        print("💥 일부 테스트 실패")
        exit(1)