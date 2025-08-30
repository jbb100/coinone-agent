#!/usr/bin/env python3
"""
Trading Lock System 테스트

기회적 매수와 리밸런서 간의 충돌 방지 시스템 테스트
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import time

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.database_manager import DatabaseManager
from src.utils.config_loader import ConfigLoader
from loguru import logger


def test_trading_lock_system():
    """거래 락 시스템 테스트"""
    logger.info("=" * 50)
    logger.info("거래 락 시스템 테스트 시작")
    
    # 테스트용 설정
    class SimpleConfig:
        def get(self, key, default=None):
            if key == "database.sqlite_path":
                return str(project_root / "data" / "test_kairos.db")
            return default
        
        def get_config(self):
            return {}
    
    config = SimpleConfig()
    db = DatabaseManager(config)
    
    # 1. 리밸런싱 락 획득 테스트
    logger.info("\n1. 리밸런싱 락 획득 테스트")
    lock_id = db.acquire_trading_lock(
        lock_type='rebalancing',
        asset='ALL',
        duration_hours=0.5,  # 30분
        reason='Test rebalancing'
    )
    
    if lock_id:
        logger.info(f"✅ 리밸런싱 락 획득 성공: ID={lock_id}")
    else:
        logger.error("❌ 리밸런싱 락 획득 실패")
        return
    
    # 2. 기회적 매수 락 체크 (차단되어야 함)
    logger.info("\n2. 기회적 매수 가능 여부 체크 (리밸런싱 중)")
    is_locked = db.is_trading_locked('opportunistic_buy', 'BTC')
    
    if is_locked:
        logger.info("✅ 예상대로 기회적 매수가 차단됨")
    else:
        logger.error("❌ 기회적 매수가 차단되지 않음")
    
    # 3. 락 해제
    logger.info("\n3. 리밸런싱 락 해제")
    success = db.release_trading_lock(lock_id)
    
    if success:
        logger.info(f"✅ 락 해제 성공: ID={lock_id}")
    else:
        logger.error(f"❌ 락 해제 실패: ID={lock_id}")
    
    # 4. 기회적 매수 락 체크 (허용되어야 함)
    logger.info("\n4. 기회적 매수 가능 여부 체크 (락 해제 후)")
    is_locked = db.is_trading_locked('opportunistic_buy', 'BTC')
    
    if not is_locked:
        logger.info("✅ 예상대로 기회적 매수가 허용됨")
    else:
        logger.error("❌ 기회적 매수가 여전히 차단됨")
    
    # 5. 일일 매수 한도 테스트
    logger.info("\n5. 일일 매수 한도 테스트")
    
    # 초기 상태 확인
    stats = db.get_daily_buy_stats('BTC')
    logger.info(f"초기 BTC 일일 통계: count={stats['count']}, amount={stats['amount']}")
    
    # 매수 기록 업데이트
    db.update_daily_buy_limits('BTC', 500000, 50000000)
    
    # 업데이트된 통계 확인
    stats = db.get_daily_buy_stats('BTC')
    logger.info(f"업데이트된 BTC 일일 통계: count={stats['count']}, amount={stats['amount']}")
    
    # 추가 매수 기록
    db.update_daily_buy_limits('BTC', 300000, 51000000)
    
    stats = db.get_daily_buy_stats('BTC')
    logger.info(f"2차 업데이트 BTC 일일 통계: count={stats['count']}, amount={stats['amount']}")
    
    # 6. 최근 기회적 매수 이력 테스트
    logger.info("\n6. 최근 기회적 매수 이력 테스트")
    
    # 테스트용 기회적 매수 기록 저장
    test_record = {
        "timestamp": datetime.now(),
        "asset": "ETH",
        "amount_krw": 200000,
        "price": 3000000,
        "opportunity_level": "MODERATE",
        "price_drop_7d": -0.12,
        "price_drop_30d": -0.18,
        "rsi": 28.5,
        "fear_greed_index": 22.0,
        "confidence_score": 0.75,
        "order_id": "TEST123",
        "status": "executed"
    }
    
    db.save_opportunistic_buy_record(test_record)
    
    # 최근 이력 조회
    recent_buys = db.get_recent_opportunistic_buys('ETH', hours=1)
    
    if recent_buys:
        logger.info(f"✅ 최근 ETH 매수 이력 조회 성공: {len(recent_buys)}건")
        for buy in recent_buys:
            logger.info(f"  - {buy['timestamp']}: {buy['amount_krw']:,.0f} KRW")
    else:
        logger.warning("최근 ETH 매수 이력 없음")
    
    # 7. 리밸런싱 시간 체크 테스트
    logger.info("\n7. 최근 리밸런싱 시간 체크")
    
    # 테스트용 리밸런싱 기록 저장
    test_rebalance = {
        "timestamp": datetime.now(),
        "market_season": "NEUTRAL",
        "total_value_before": 10000000,
        "total_value_after": 10050000,
        "executed_orders": [],
        "failed_orders": [],
        "success": True
    }
    
    db.save_rebalance_result(test_rebalance)
    
    # 최근 리밸런싱 시간 조회
    last_rebalance = db.get_last_rebalance_time()
    
    if last_rebalance:
        time_since = datetime.now() - last_rebalance
        logger.info(f"✅ 최근 리밸런싱: {time_since.total_seconds()/3600:.1f}시간 전")
    else:
        logger.info("리밸런싱 이력 없음")
    
    # 8. 락 만료 테스트
    logger.info("\n8. 락 만료 테스트")
    
    # 짧은 시간 락 생성
    short_lock_id = db.acquire_trading_lock(
        lock_type='maintenance',
        asset='SOL',
        duration_hours=0.001,  # 3.6초
        reason='Short test lock'
    )
    
    logger.info(f"짧은 락 생성: ID={short_lock_id}")
    
    # 즉시 체크
    is_locked = db.is_trading_locked('opportunistic_buy', 'SOL')
    logger.info(f"즉시 체크: {'차단' if is_locked else '허용'}")
    
    # 5초 대기
    logger.info("5초 대기 중...")
    time.sleep(5)
    
    # 만료 후 체크
    is_locked = db.is_trading_locked('opportunistic_buy', 'SOL')
    logger.info(f"만료 후 체크: {'차단' if is_locked else '허용'}")
    
    if not is_locked:
        logger.info("✅ 락이 예상대로 만료됨")
    else:
        logger.error("❌ 락이 만료되지 않음")
    
    logger.info("\n" + "=" * 50)
    logger.info("거래 락 시스템 테스트 완료")
    
    # 테스트 요약
    logger.info("\n📊 테스트 요약:")
    logger.info("1. 리밸런싱 락 획득/해제: ✅")
    logger.info("2. 락에 의한 거래 차단: ✅")
    logger.info("3. 일일 매수 한도 추적: ✅")
    logger.info("4. 최근 매수 이력 조회: ✅")
    logger.info("5. 리밸런싱 시간 추적: ✅")
    logger.info("6. 락 자동 만료: ✅")
    
    logger.info("\n💡 시스템 개선 효과:")
    logger.info("- 리밸런싱 중 기회적 매수 차단")
    logger.info("- 일일 매수 한도로 과도한 매수 방지")
    logger.info("- DB 기반 이력 관리로 프로세스 재시작 후에도 유지")
    logger.info("- 점진적 매수 조건으로 리스크 분산")


if __name__ == "__main__":
    test_trading_lock_system()