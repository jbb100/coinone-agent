#!/usr/bin/env python3
"""
멀티 리밸런싱 엔진 단독 테스트 스크립트
"""

import sys
import asyncio
import os
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

# 프로젝트 루트 경로 추가
sys.path.append('/Users/jongdal100/git/coinone-agent')

async def test_rebalancing_task():
    """RebalanceTask 테스트"""
    print("⚖️ RebalanceTask 테스트 시작...")
    
    try:
        from src.core.multi_rebalancing_engine import RebalanceTask, RebalanceScheduleType
        from src.core.types import AccountID, MarketSeason
        
        # RebalanceTask 생성
        task = RebalanceTask(
            account_id=AccountID("test_account"),
            schedule_type=RebalanceScheduleType.WEEKLY,
            cron_expression="0 9 * * 1",  # 매주 월요일 오전 9시
            next_run=datetime.now() + timedelta(days=1),
            enabled=True,
            deviation_threshold=0.05,
            market_condition=MarketSeason.RISK_ON
        )
        print("✅ RebalanceTask 생성 성공")
        
        # 필드 확인
        assert task.account_id == "test_account", "계정 ID 불일치"
        assert task.schedule_type == RebalanceScheduleType.WEEKLY, "스케줄 타입 불일치"
        assert task.cron_expression == "0 9 * * 1", "크론 표현식 불일치"
        assert task.enabled == True, "활성화 상태 불일치"
        assert task.deviation_threshold == 0.05, "편차 임계값 불일치"
        assert task.market_condition == MarketSeason.RISK_ON, "시장 상황 불일치"
        print("✅ RebalanceTask 필드 확인 성공")
        
        print("🎉 RebalanceTask 테스트 통과!")
        return True
        
    except Exception as e:
        print(f"❌ RebalanceTask 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_rebalancing_engine_init():
    """MultiRebalancingEngine 초기화 테스트"""
    print("\n🏗️ MultiRebalancingEngine 초기화 테스트 시작...")
    
    try:
        from src.core.multi_rebalancing_engine import MultiRebalancingEngine, RebalanceScheduleType
        from src.core.types import MarketSeason
        
        # MultiRebalancingEngine 초기화 (의존성 모킹)
        engine = MultiRebalancingEngine()
        print("✅ MultiRebalancingEngine 생성 성공")
        
        # 구성 요소 확인
        assert engine.config.name == "multi_rebalancing_engine", "서비스명 불일치"
        assert engine.config.enabled == True, "활성화 상태 불일치"
        assert engine.config.health_check_interval == 60, "헬스체크 간격 불일치"
        print("✅ MultiRebalancingEngine 기본 설정 확인 성공")
        
        # 초기 상태 확인
        assert engine.rebalance_tasks == {}, "리밸런싱 작업 딕셔너리 초기화 오류"
        assert engine.running_tasks == set(), "실행 중인 작업 셋 초기화 오류"
        assert engine.max_concurrent_rebalancing == 3, "동시 리밸런싱 수 설정 오류"
        assert engine.current_market_season == MarketSeason.NEUTRAL, "초기 시장 상황 설정 오류"
        print("✅ MultiRebalancingEngine 초기 상태 확인 성공")
        
        # 통계 초기화 확인
        stats = engine.rebalance_stats
        assert stats['total_runs'] == 0, "총 실행 횟수 초기화 오류"
        assert stats['successful_runs'] == 0, "성공 실행 횟수 초기화 오류"
        assert stats['failed_runs'] == 0, "실패 실행 횟수 초기화 오류"
        assert stats['last_successful_run'] is None, "마지막 성공 실행 초기화 오류"
        assert stats['last_failed_run'] is None, "마지막 실패 실행 초기화 오류"
        print("✅ 리밸런싱 통계 초기화 확인 성공")
        
        print("🎉 MultiRebalancingEngine 초기화 테스트 통과!")
        return True
        
    except Exception as e:
        print(f"❌ MultiRebalancingEngine 초기화 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_cron_parsing():
    """Cron 표현식 파싱 테스트"""
    print("\n📅 Cron 표현식 파싱 테스트 시작...")
    
    try:
        from croniter import croniter
        from datetime import datetime
        
        # 다양한 크론 표현식 테스트
        cron_expressions = [
            ("0 9 * * 1", "매주 월요일 오전 9시"),
            ("0 0 * * *", "매일 자정"),
            ("0 12 1 * *", "매월 1일 정오"),
            ("*/15 * * * *", "15분마다"),
        ]
        
        base_time = datetime.now()
        
        for cron_expr, description in cron_expressions:
            cron = croniter(cron_expr, base_time)
            next_time = cron.get_next(datetime)
            
            assert isinstance(next_time, datetime), f"크론 파싱 실패: {cron_expr}"
            assert next_time > base_time, f"다음 실행 시간이 현재보다 과거: {cron_expr}"
            
            print(f"✅ {description}: {cron_expr} -> {next_time}")
        
        print("🎉 Cron 표현식 파싱 테스트 통과!")
        return True
        
    except Exception as e:
        print(f"❌ Cron 표현식 파싱 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_schedule_management():
    """스케줄 관리 테스트 (의존성 모킹)"""
    print("\n📋 스케줄 관리 테스트 시작...")
    
    try:
        from src.core.multi_rebalancing_engine import MultiRebalancingEngine, RebalanceTask, RebalanceScheduleType
        from src.core.types import AccountID
        
        # 엔진 생성 (의존성은 나중에 모킹)
        engine = MultiRebalancingEngine()
        
        # 테스트용 리밸런싱 작업 추가
        test_task = RebalanceTask(
            account_id=AccountID("test_account_001"),
            schedule_type=RebalanceScheduleType.DAILY,
            cron_expression="0 10 * * *",  # 매일 오전 10시
            next_run=datetime.now() + timedelta(hours=1),
            enabled=True
        )
        
        # 수동으로 작업 추가 (실제로는 add_rebalance_schedule 메서드 사용)
        engine.rebalance_tasks[test_task.account_id] = test_task
        print("✅ 테스트 리밸런싱 작업 추가 성공")
        
        # 작업 확인
        assert len(engine.rebalance_tasks) == 1, "리밸런싱 작업 개수 불일치"
        assert "test_account_001" in engine.rebalance_tasks, "추가된 작업을 찾을 수 없음"
        
        stored_task = engine.rebalance_tasks["test_account_001"]
        assert stored_task.account_id == "test_account_001", "저장된 작업의 계정 ID 불일치"
        assert stored_task.schedule_type == RebalanceScheduleType.DAILY, "저장된 작업의 스케줄 타입 불일치"
        print("✅ 리밸런싱 작업 저장 확인 성공")
        
        # 작업 제거
        del engine.rebalance_tasks["test_account_001"]
        assert len(engine.rebalance_tasks) == 0, "리밸런싱 작업 제거 실패"
        print("✅ 리밸런싱 작업 제거 성공")
        
        print("🎉 스케줄 관리 테스트 통과!")
        return True
        
    except Exception as e:
        print(f"❌ 스케줄 관리 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_concurrent_control():
    """동시성 제어 테스트"""
    print("\n🔄 동시성 제어 테스트 시작...")
    
    try:
        from src.core.multi_rebalancing_engine import MultiRebalancingEngine
        
        # 엔진 생성
        engine = MultiRebalancingEngine()
        
        # Semaphore 확인
        assert engine.rebalance_semaphore is not None, "리밸런싱 세마포어 초기화 실패"
        assert engine.rebalance_semaphore._value == 3, "세마포어 초기값 설정 오류"
        print("✅ 리밸런싱 세마포어 초기화 확인 성공")
        
        # 실행 중인 작업 추적 확인
        assert isinstance(engine.running_tasks, set), "실행 중인 작업 추적을 위한 셋 초기화 실패"
        assert len(engine.running_tasks) == 0, "초기 실행 중인 작업이 비어있지 않음"
        print("✅ 실행 중인 작업 추적 초기화 확인 성공")
        
        # 세마포어 동작 테스트
        await engine.rebalance_semaphore.acquire()
        assert engine.rebalance_semaphore._value == 2, "세마포어 획득 후 값 변화 확인 실패"
        
        engine.rebalance_semaphore.release()
        assert engine.rebalance_semaphore._value == 3, "세마포어 해제 후 값 복원 확인 실패"
        print("✅ 세마포어 동작 테스트 성공")
        
        print("🎉 동시성 제어 테스트 통과!")
        return True
        
    except Exception as e:
        print(f"❌ 동시성 제어 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_service_lifecycle():
    """서비스 라이프사이클 테스트"""
    print("\n🔄 서비스 라이프사이클 테스트 시작...")
    
    try:
        from src.core.multi_rebalancing_engine import MultiRebalancingEngine
        
        # 엔진 생성
        engine = MultiRebalancingEngine()
        
        # start 메서드 확인 (BaseService에서 상속)
        assert hasattr(engine, 'start'), "start 메서드가 없음"
        assert hasattr(engine, 'stop'), "stop 메서드가 없음"
        assert hasattr(engine, 'health_check'), "health_check 메서드가 없음"
        print("✅ 서비스 라이프사이클 메서드 확인 성공")
        
        # 초기 상태 확인 (_scheduler_task는 initialize() 호출 시에만 설정됨)
        assert not hasattr(engine, '_scheduler_task'), "스케줄러 태스크가 초기화 전에 존재함"
        print("✅ 초기 상태 확인 성공")
        
        print("🎉 서비스 라이프사이클 테스트 통과!")
        return True
        
    except Exception as e:
        print(f"❌ 서비스 라이프사이클 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """메인 테스트 함수"""
    print("=" * 60)
    print("⚖️ KAIROS-1 멀티 리밸런싱 엔진 단독 테스트")
    print("=" * 60)
    
    results = []
    
    # 각 테스트 실행
    results.append(await test_rebalancing_task())
    results.append(await test_rebalancing_engine_init())
    results.append(await test_cron_parsing())
    results.append(await test_schedule_management())
    results.append(await test_concurrent_control())
    results.append(await test_service_lifecycle())
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("📊 테스트 결과 요약")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    print(f"✅ 통과: {passed}/{total}")
    print(f"❌ 실패: {total - passed}/{total}")
    
    if all(results):
        print("🎉 모든 멀티 리밸런싱 엔진 테스트 통과!")
        return True
    else:
        print("💥 일부 테스트 실패")
        return False

if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)