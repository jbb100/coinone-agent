#!/usr/bin/env python3
"""
멀티 계정 관리자 단독 테스트 스크립트
"""

import sys
import os
import asyncio
import json
from pathlib import Path
from decimal import Decimal

# 프로젝트 루트 경로 추가
sys.path.append('/Users/jongdal100/git/coinone-agent')

async def test_multi_account_manager():
    """MultiAccountManager 테스트"""
    print("🏦 MultiAccountManager 테스트 시작...")
    
    try:
        from src.core.multi_account_manager import (
            MultiAccountManager, AccountConfig
        )
        from src.core.types import AccountID, AccountName, RiskLevel, KRWAmount
        
        # 임시 설정 파일 경로
        test_config_path = "/tmp/test_accounts.json"
        
        # MultiAccountManager 초기화
        manager = MultiAccountManager(test_config_path)
        print("✅ MultiAccountManager 초기화 성공")
        
        # 초기화 실행
        await manager.initialize()
        print("✅ MultiAccountManager 서비스 초기화 성공")
        
        # 기본 설정 파일이 생성되었는지 확인
        assert Path(test_config_path).exists(), "설정 파일이 생성되지 않음"
        print("✅ 기본 설정 파일 생성 확인")
        
        # 계정 추가 테스트 (API 키 없이 설정만)
        test_config = AccountConfig(
            account_id=AccountID("test_account"),
            account_name=AccountName("테스트 계정"),
            description="테스트용 계정",
            risk_level=RiskLevel.MODERATE,
            initial_capital=KRWAmount(Decimal('1000000')),
            max_investment=KRWAmount(Decimal('5000000')),
            dry_run=True
        )
        
        # 더미 API 키로 계정 추가 (실제 API 호출 없이)
        success = await manager.add_account(test_config, "dummy_api_key", "dummy_secret_key")
        assert success, "계정 추가 실패"
        print("✅ 계정 추가 성공")
        
        # 계정 목록 조회
        accounts = await manager.get_all_accounts()
        assert len(accounts) > 0, "추가된 계정이 조회되지 않음"
        print(f"✅ 계정 목록 조회 성공: {len(accounts)}개 계정")
        
        # 특정 계정 정보 조회
        account_info = await manager.get_account_info(AccountID("test_account"))
        assert account_info is not None, "계정 정보 조회 실패"
        assert account_info['account_id'] == "test_account", "계정 ID 불일치"
        print("✅ 계정 정보 조회 성공")
        
        # 헬스체크 테스트
        health = await manager.health_check()
        assert 'service' in health, "헬스체크 결과 형식 오류"
        assert health['service'] == 'multi_account_manager', "서비스명 불일치"
        print("✅ 헬스체크 성공")
        
        # 통합 포트폴리오 조회 (잔고가 없어도 구조 확인)
        portfolio = await manager.get_aggregate_portfolio()
        assert 'total_value' in portfolio, "포트폴리오 구조 오류"
        print("✅ 통합 포트폴리오 조회 성공")
        
        # 계정 제거 테스트
        success = await manager.remove_account(AccountID("test_account"))
        assert success, "계정 제거 실패"
        print("✅ 계정 제거 성공")
        
        # 서비스 종료
        await manager.stop()
        print("✅ 서비스 종료 성공")
        
        # 임시 파일 정리
        if Path(test_config_path).exists():
            Path(test_config_path).unlink()
        
        print("🎉 MultiAccountManager 모든 테스트 통과!")
        return True
        
    except Exception as e:
        print(f"❌ MultiAccountManager 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_account_config():
    """AccountConfig 테스트"""
    print("\n⚙️ AccountConfig 테스트 시작...")
    
    try:
        from src.core.multi_account_manager import AccountConfig
        from src.core.types import AccountID, AccountName, RiskLevel, KRWAmount
        from decimal import Decimal
        
        # AccountConfig 생성
        config = AccountConfig(
            account_id=AccountID("config_test"),
            account_name=AccountName("설정 테스트"),
            description="설정 테스트 계정",
            risk_level=RiskLevel.CONSERVATIVE,
            initial_capital=KRWAmount(Decimal('2000000')),
            max_investment=KRWAmount(Decimal('10000000')),
            auto_rebalance=True,
            rebalance_frequency="daily",
            core_allocation=0.8,
            satellite_allocation=0.2,
            cash_reserve=0.15,
            max_position_size=0.3,
            dry_run=False
        )
        
        # 설정값 확인
        assert config.account_id == "config_test", "계정 ID 불일치"
        assert config.risk_level == RiskLevel.CONSERVATIVE, "리스크 레벨 불일치"
        assert config.initial_capital == KRWAmount(Decimal('2000000')), "초기 자본 불일치"
        assert config.core_allocation == 0.8, "코어 자산 비중 불일치"
        assert config.auto_rebalance == True, "자동 리밸런싱 설정 불일치"
        
        print("✅ AccountConfig 생성 및 설정 확인 성공")
        
        # dataclasses.asdict 테스트
        from dataclasses import asdict
        config_dict = asdict(config)
        assert 'account_id' in config_dict, "딕셔너리 변환 실패"
        print("✅ AccountConfig 딕셔너리 변환 성공")
        
        print("🎉 AccountConfig 모든 테스트 통과!")
        return True
        
    except Exception as e:
        print(f"❌ AccountConfig 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_json_serialization():
    """JSON 직렬화 테스트"""
    print("\n📄 JSON 직렬화 테스트 시작...")
    
    try:
        from src.core.multi_account_manager import AccountConfig
        from src.core.types import AccountID, AccountName, RiskLevel, KRWAmount
        from decimal import Decimal
        from dataclasses import asdict
        
        # AccountConfig 생성
        config = AccountConfig(
            account_id=AccountID("json_test"),
            account_name=AccountName("JSON 테스트"),
            description="JSON 직렬화 테스트",
            risk_level=RiskLevel.MODERATE,
            initial_capital=KRWAmount(Decimal('1500000')),
            max_investment=KRWAmount(Decimal('7500000'))
        )
        
        # 딕셔너리로 변환
        config_dict = asdict(config)
        
        # JSON 직렬화
        json_str = json.dumps(config_dict, default=str, ensure_ascii=False)
        assert len(json_str) > 0, "JSON 직렬화 실패"
        print("✅ JSON 직렬화 성공")
        
        # JSON 역직렬화
        loaded_dict = json.loads(json_str)
        assert loaded_dict['account_id'] == "json_test", "JSON 역직렬화 데이터 불일치"
        print("✅ JSON 역직렬화 성공")
        
        print("🎉 JSON 직렬화 모든 테스트 통과!")
        return True
        
    except Exception as e:
        print(f"❌ JSON 직렬화 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """메인 테스트 함수"""
    print("=" * 60)
    print("🏦 KAIROS-1 멀티 계정 관리자 단독 테스트")
    print("=" * 60)
    
    results = []
    
    # 각 테스트 실행
    results.append(await test_account_config())
    results.append(await test_json_serialization())
    results.append(await test_multi_account_manager())
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("📊 테스트 결과 요약")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    print(f"✅ 통과: {passed}/{total}")
    print(f"❌ 실패: {total - passed}/{total}")
    
    if all(results):
        print("🎉 모든 멀티 계정 관리자 테스트 통과!")
        return True
    else:
        print("💥 일부 테스트 실패")
        return False

if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)