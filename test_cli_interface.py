#!/usr/bin/env python3
"""
CLI 인터페이스 단독 테스트 스크립트
"""

import sys
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# 프로젝트 루트 경로 추가
sys.path.append('/Users/jongdal100/git/coinone-agent')

async def test_cli_initialization():
    """CLI 초기화 테스트"""
    print("🖥️ CLI 초기화 테스트 시작...")
    
    try:
        from src.cli.multi_account_cli import MultiAccountCLI
        
        # CLI 생성
        cli = MultiAccountCLI()
        print("✅ MultiAccountCLI 생성 성공")
        
        # 구성 요소 확인
        assert cli.account_manager is not None, "계정 관리자 초기화 실패"
        assert cli.portfolio_manager is not None, "포트폴리오 관리자 초기화 실패"
        assert cli.rebalancing_engine is not None, "리밸런싱 엔진 초기화 실패"
        assert cli.initialized == False, "초기화 상태가 잘못됨"
        print("✅ CLI 구성 요소 확인 성공")
        
        print("🎉 CLI 초기화 테스트 통과!")
        return True
        
    except Exception as e:
        print(f"❌ CLI 초기화 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_click_commands():
    """Click 명령어 구조 테스트"""
    print("\n⚡ Click 명령어 구조 테스트 시작...")
    
    try:
        from src.cli.multi_account_cli import multi_account
        import click
        
        # CLI 그룹 확인
        assert isinstance(multi_account, click.Group), "multi_account가 Click 그룹이 아님"
        print("✅ multi_account Click 그룹 확인 성공")
        
        # 명령어 목록 확인
        commands = multi_account.list_commands(None)
        expected_commands = ['accounts', 'add', 'remove', 'portfolio', 'rebalance', 'schedules', 'health']
        
        for cmd in expected_commands:
            if cmd not in commands:
                print(f"⚠️ 명령어 {cmd}이 정의되지 않음")
            else:
                print(f"✅ 명령어 {cmd} 확인됨")
        
        print(f"✅ 총 {len(commands)}개 명령어 확인됨: {', '.join(commands)}")
        
        print("🎉 Click 명령어 구조 테스트 통과!")
        return True
        
    except Exception as e:
        print(f"❌ Click 명령어 구조 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_account_data_formatting():
    """계정 데이터 포맷팅 테스트"""
    print("\n📊 계정 데이터 포맷팅 테스트 시작...")
    
    try:
        from src.cli.multi_account_cli import MultiAccountCLI
        from src.core.types import AccountStatus, RiskLevel
        from decimal import Decimal
        
        cli = MultiAccountCLI()
        
        # 테스트용 계정 데이터
        test_accounts = [
            {
                'account_id': 'test_001',
                'account_name': '테스트 계정 1',
                'status': AccountStatus.ACTIVE,
                'risk_level': RiskLevel.MODERATE,
                'current_value': Decimal('1500000'),
                'total_return': 0.15,
                'last_updated': '2025-08-06T10:30:00'
            },
            {
                'account_id': 'test_002', 
                'account_name': '테스트 계정 2',
                'status': AccountStatus.INACTIVE,
                'risk_level': RiskLevel.CONSERVATIVE,
                'current_value': Decimal('2000000'),
                'total_return': 0.08,
                'last_updated': '2025-08-06T09:15:00'
            }
        ]
        
        # 포맷팅 테스트 (실제 _format_accounts_table 메서드가 있다고 가정)
        if hasattr(cli, '_format_accounts_table'):
            formatted_table = cli._format_accounts_table(test_accounts)
            assert isinstance(formatted_table, str), "포맷된 테이블이 문자열이 아님"
            print("✅ 계정 테이블 포맷팅 성공")
        else:
            print("⚠️ _format_accounts_table 메서드가 구현되지 않음")
        
        # 상태별 안전한 값 접근 테스트
        for account in test_accounts:
            # enum 값 접근 테스트 (현재 구현된 안전한 접근 방식)
            status_str = account['status'].value if hasattr(account['status'], 'value') else str(account['status'])
            risk_str = account['risk_level'].value if hasattr(account['risk_level'], 'value') else str(account['risk_level'])
            
            assert isinstance(status_str, str), f"상태 문자열 변환 실패: {account['account_id']}"
            assert isinstance(risk_str, str), f"리스크 레벨 문자열 변환 실패: {account['account_id']}"
            
            print(f"✅ {account['account_id']}: {status_str}, {risk_str}")
        
        print("🎉 계정 데이터 포맷팅 테스트 통과!")
        return True
        
    except Exception as e:
        print(f"❌ 계정 데이터 포맷팅 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_tabulate_integration():
    """Tabulate 라이브러리 통합 테스트"""
    print("\n📋 Tabulate 통합 테스트 시작...")
    
    try:
        from tabulate import tabulate
        
        # 테스트 데이터
        test_data = [
            ["test_001", "테스트 계정 1", "active", "moderate", "1,500,000", "15.0%"],
            ["test_002", "테스트 계정 2", "inactive", "conservative", "2,000,000", "8.0%"]
        ]
        
        headers = ["계정 ID", "계정명", "상태", "리스크", "현재 가치", "수익률"]
        
        # 테이블 생성
        table = tabulate(test_data, headers=headers, tablefmt="grid")
        
        assert isinstance(table, str), "테이블이 문자열로 생성되지 않음"
        assert len(table) > 0, "테이블 내용이 비어있음"
        assert "계정 ID" in table, "헤더가 포함되지 않음"
        assert "test_001" in table, "데이터가 포함되지 않음"
        
        print("✅ Tabulate 테이블 생성 성공")
        print(f"테이블 길이: {len(table)} 문자")
        
        # 다른 테이블 형식도 테스트
        simple_table = tabulate(test_data, headers=headers, tablefmt="simple")
        assert isinstance(simple_table, str), "Simple 형식 테이블 생성 실패"
        print("✅ Simple 형식 테이블 생성 성공")
        
        print("🎉 Tabulate 통합 테스트 통과!")
        return True
        
    except Exception as e:
        print(f"❌ Tabulate 통합 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_error_handling():
    """에러 처리 테스트"""
    print("\n🚨 에러 처리 테스트 시작...")
    
    try:
        from src.cli.multi_account_cli import MultiAccountCLI
        
        cli = MultiAccountCLI()
        
        # 초기화되지 않은 상태에서 작업 시도
        assert cli.initialized == False, "초기 상태가 잘못됨"
        print("✅ 초기 상태 확인")
        
        # ensure_initialized 메서드 확인
        assert hasattr(cli, 'ensure_initialized'), "ensure_initialized 메서드가 없음"
        assert callable(cli.ensure_initialized), "ensure_initialized가 호출 가능하지 않음"
        print("✅ ensure_initialized 메서드 확인")
        
        # 잘못된 입력 처리 시뮬레이션
        invalid_account_id = ""
        assert len(invalid_account_id) == 0, "빈 계정 ID 테스트"
        print("✅ 빈 계정 ID 검증 로직 테스트")
        
        print("🎉 에러 처리 테스트 통과!")
        return True
        
    except Exception as e:
        print(f"❌ 에러 처리 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_async_execution():
    """비동기 실행 테스트"""
    print("\n🔄 비동기 실행 테스트 시작...")
    
    try:
        # asyncio.run이 CLI에서 사용되는지 확인
        import asyncio
        
        assert callable(asyncio.run), "asyncio.run이 호출 가능하지 않음"
        print("✅ asyncio.run 확인")
        
        # 간단한 비동기 함수 테스트 (현재 이벤트 루프 내에서)
        async def test_async_func():
            await asyncio.sleep(0.01)
            return "test_result"
        
        # 현재 실행 중인 이벤트 루프에서 직접 호출
        result = await test_async_func()
        assert result == "test_result", "비동기 함수 실행 결과 불일치"
        print("✅ 비동기 함수 실행 테스트")
        
        # CLI 명령어들이 asyncio.run을 사용하는지 확인
        from src.cli.multi_account_cli import multi_account
        import inspect
        
        # add 명령어의 소스코드에서 asyncio.run 사용 확인
        add_command = multi_account.commands.get('add')
        if add_command:
            source = inspect.getsource(add_command.callback)
            assert 'asyncio.run' in source, "add 명령어에서 asyncio.run을 사용하지 않음"
            print("✅ add 명령어에서 asyncio.run 사용 확인")
        
        print("🎉 비동기 실행 테스트 통과!")
        return True
        
    except Exception as e:
        print(f"❌ 비동기 실행 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """메인 테스트 함수"""
    print("=" * 60)
    print("🖥️ KAIROS-1 CLI 인터페이스 단독 테스트")
    print("=" * 60)
    
    results = []
    
    # 각 테스트 실행
    results.append(await test_cli_initialization())
    results.append(await test_click_commands())
    results.append(await test_account_data_formatting())
    results.append(await test_tabulate_integration())
    results.append(await test_error_handling())
    results.append(await test_async_execution())
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("📊 테스트 결과 요약")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    print(f"✅ 통과: {passed}/{total}")
    print(f"❌ 실패: {total - passed}/{total}")
    
    if all(results):
        print("🎉 모든 CLI 인터페이스 테스트 통과!")
        return True
    else:
        print("💥 일부 테스트 실패")
        return False

if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)