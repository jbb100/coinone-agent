#!/usr/bin/env python3
"""
비동기 클라이언트 컴포넌트별 테스트 (aiohttp 세션 생성 제외)
"""

import sys
import asyncio
from pathlib import Path

# 프로젝트 루트 경로 추가
sys.path.append('/Users/jongdal100/git/coinone-agent')

async def test_async_cache_only():
    """AsyncCache만 테스트"""
    print("💾 AsyncCache 단독 테스트 시작...")
    
    try:
        from src.core.async_client import AsyncCache
        
        # AsyncCache 초기화
        cache = AsyncCache(max_memory_items=5)
        print("✅ AsyncCache 초기화 성공")
        
        # 캐시에 데이터 저장
        await cache.set("test_key", "test_value", 30)
        print("✅ 캐시 데이터 저장 성공")
        
        # 캐시에서 데이터 조회
        value = await cache.get("test_key")
        assert value == "test_value", f"캐시 조회 실패: expected 'test_value', got '{value}'"
        print("✅ 캐시 데이터 조회 성공")
        
        # 존재하지 않는 키 조회
        nonexistent = await cache.get("nonexistent_key")
        assert nonexistent is None, "존재하지 않는 키에서 None이 반환되지 않음"
        print("✅ 존재하지 않는 키 처리 성공")
        
        # 캐시 통계 확인
        stats = cache.get_stats()
        assert 'memory_items' in stats, "캐시 통계 형식 오류"
        assert 'max_memory_items' in stats, "캐시 통계 형식 오류"
        print(f"✅ 캐시 통계 확인: items={stats['memory_items']}, max={stats['max_memory_items']}")
        
        # 만료된 캐시 정리
        await cache.clear_expired()
        print("✅ 만료된 캐시 정리 성공")
        
        print("🎉 AsyncCache 단독 테스트 통과!")
        return True
        
    except Exception as e:
        print(f"❌ AsyncCache 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_connection_pool_init_only():
    """ConnectionPool 초기화만 테스트"""
    print("\n🔗 ConnectionPool 초기화 테스트 시작...")
    
    try:
        from src.core.async_client import ConnectionPool
        
        # ConnectionPool 초기화
        pool = ConnectionPool(
            max_connections=5,
            max_keepalive_connections=3,
            keepalive_expiry=30,
            timeout=10
        )
        print("✅ ConnectionPool 초기화 성공")
        
        # 구성 요소 확인
        assert pool.connector is not None, "TCPConnector 초기화 실패"
        assert pool.timeout is not None, "Timeout 설정 실패"
        assert pool.session is None, "Session이 초기화되면 안됨"
        print("✅ ConnectionPool 구성 요소 확인 성공")
        
        # 바로 연결 풀 정리 (세션 생성 안함)
        await pool.close()
        print("✅ 연결 풀 정리 성공")
        
        print("🎉 ConnectionPool 초기화 테스트 통과!")
        return True
        
    except Exception as e:
        print(f"❌ ConnectionPool 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_request_batcher_only():
    """RequestBatcher만 테스트"""
    print("\n📦 RequestBatcher 단독 테스트 시작...")
    
    try:
        from src.core.async_client import RequestBatcher
        
        # RequestBatcher 초기화
        batcher = RequestBatcher(batch_size=2, batch_timeout=0.5)
        print("✅ RequestBatcher 초기화 성공")
        
        # 구성 요소 확인
        assert batcher.batch_size == 2, "배치 크기 설정 오류"
        assert batcher.batch_timeout == 0.5, "배치 타임아웃 설정 오류"
        assert batcher.pending_requests == [], "펜딩 요청 리스트 초기화 오류"
        assert batcher._batch_task is None, "배치 태스크 초기화 오류"
        print("✅ RequestBatcher 구성 요소 확인 성공")
        
        print("🎉 RequestBatcher 단독 테스트 통과!")
        return True
        
    except Exception as e:
        print(f"❌ RequestBatcher 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_http_client_init_only():
    """AsyncHTTPClient 초기화만 테스트"""
    print("\n🌐 AsyncHTTPClient 초기화 테스트 시작...")
    
    try:
        from src.core.async_client import AsyncHTTPClient
        
        # AsyncHTTPClient 초기화
        client = AsyncHTTPClient(
            base_url="https://api.coinone.co.kr",
            enable_caching=True,
            cache_ttl=60,
            enable_batching=False,
            rate_limit=(10, 60)  # 분당 10회 제한
        )
        print("✅ AsyncHTTPClient 초기화 성공")
        
        # 구성 요소 확인
        assert client.base_url == "https://api.coinone.co.kr", "베이스 URL 설정 오류"
        assert client.enable_caching == True, "캐싱 활성화 설정 오류"
        assert client.cache_ttl == 60, "캐시 TTL 설정 오류"
        assert client.enable_batching == False, "배치 처리 설정 오류"
        assert client.rate_limit_calls == 10, "Rate limit 호출 수 설정 오류"
        assert client.rate_limit_window == 60, "Rate limit 윈도우 설정 오류"
        print("✅ AsyncHTTPClient 구성 요소 확인 성공")
        
        # 캐시와 연결 풀 확인
        assert client.cache is not None, "캐시 초기화 실패"
        assert client.connection_pool is not None, "연결 풀 초기화 실패"
        assert client.batcher is None, "배치 처리기가 비활성화되어야 함"
        print("✅ AsyncHTTPClient 하위 구성 요소 확인 성공")
        
        # URL 빌드 테스트
        full_url = client._build_url("/public/orderbook")
        assert full_url == "https://api.coinone.co.kr/public/orderbook", "URL 빌드 실패"
        print("✅ URL 빌드 테스트 성공")
        
        # 캐시 키 생성 테스트
        cache_key = client._generate_cache_key(
            "GET",
            "https://api.coinone.co.kr/public/ticker",
            {"currency": "BTC"},
            {"Authorization": "Bearer test_token"}
        )
        assert isinstance(cache_key, str) and len(cache_key) == 32, "캐시 키 생성 실패"
        print("✅ 캐시 키 생성 테스트 성공")
        
        # 통계 확인
        stats = client.get_performance_stats()
        assert 'request_count' in stats, "클라이언트 통계 형식 오류"
        assert 'cache_hit_rate' in stats, "캐시 통계 형식 오류"
        assert stats['request_count'] == 0, "초기 요청 수가 0이 아님"
        print(f"✅ 클라이언트 통계 확인: requests={stats['request_count']}, cache_hit_rate={stats['cache_hit_rate']}")
        
        # 클라이언트 종료 (세션 생성 안했으므로 안전)
        await client.close()
        print("✅ 클라이언트 종료 성공")
        
        print("🎉 AsyncHTTPClient 초기화 테스트 통과!")
        return True
        
    except Exception as e:
        print(f"❌ AsyncHTTPClient 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_cache_entry():
    """CacheEntry 테스트"""
    print("\n📝 CacheEntry 테스트 시작...")
    
    try:
        from src.core.async_client import CacheEntry
        from datetime import datetime
        
        # CacheEntry 생성
        entry = CacheEntry(
            data="test_data",
            timestamp=datetime.now(),
            ttl=60
        )
        print("✅ CacheEntry 생성 성공")
        
        # 만료 여부 확인 (생성한지 얼마 안되므로 만료되지 않음)
        assert not entry.is_expired(), "새로 생성된 엔트리가 만료됨"
        print("✅ CacheEntry 만료 확인 성공")
        
        print("🎉 CacheEntry 테스트 통과!")
        return True
        
    except Exception as e:
        print(f"❌ CacheEntry 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """메인 테스트 함수"""
    print("=" * 60)
    print("🧪 KAIROS-1 비동기 클라이언트 컴포넌트별 테스트")
    print("=" * 60)
    
    results = []
    
    # 각 테스트 실행 (aiohttp 세션 생성 제외)
    results.append(await test_cache_entry())
    results.append(await test_async_cache_only())
    results.append(await test_connection_pool_init_only())
    results.append(await test_request_batcher_only())
    results.append(await test_http_client_init_only())
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("📊 테스트 결과 요약")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    print(f"✅ 통과: {passed}/{total}")
    print(f"❌ 실패: {total - passed}/{total}")
    
    if all(results):
        print("🎉 모든 비동기 클라이언트 컴포넌트 테스트 통과!")
        return True
    else:
        print("💥 일부 테스트 실패")
        return False

if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)