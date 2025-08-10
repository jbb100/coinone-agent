#!/usr/bin/env python3
"""
비동기 클라이언트 간단 테스트 스크립트 (네트워크 연결 없음)
"""

import sys
import asyncio
from pathlib import Path

# 프로젝트 루트 경로 추가
sys.path.append('/Users/jongdal100/git/coinone-agent')

async def test_async_cache():
    """AsyncCache 테스트"""
    print("💾 AsyncCache 테스트 시작...")
    
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
        
        print("🎉 AsyncCache 모든 테스트 통과!")
        return True
        
    except Exception as e:
        print(f"❌ AsyncCache 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_connection_pool():
    """ConnectionPool 테스트"""
    print("\n🔗 ConnectionPool 테스트 시작...")
    
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
        
        # 세션 획득 테스트
        session = await pool.get_session()
        assert session is not None, "세션 획득 실패"
        print("✅ 세션 획득 성공")
        
        # 동일한 세션이 반환되는지 확인 (싱글톤)
        session2 = await pool.get_session()
        assert session is session2, "싱글톤 세션이 아님"
        print("✅ 싱글톤 세션 확인 성공")
        
        # 연결 풀 정리
        await pool.close()
        print("✅ 연결 풀 정리 성공")
        
        print("🎉 ConnectionPool 모든 테스트 통과!")
        return True
        
    except Exception as e:
        print(f"❌ ConnectionPool 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_request_batcher():
    """RequestBatcher 테스트"""
    print("\n📦 RequestBatcher 테스트 시작...")
    
    try:
        from src.core.async_client import RequestBatcher
        import time
        
        # RequestBatcher 초기화
        batcher = RequestBatcher(batch_size=2, batch_timeout=0.5)
        print("✅ RequestBatcher 초기화 성공")
        
        # 테스트용 요청 함수
        async def test_request():
            await asyncio.sleep(0.1)
            return "test_result"
        
        # 배치 요청 테스트
        start_time = time.time()
        result1 = await batcher.add_request(test_request)
        result2 = await batcher.add_request(test_request)
        elapsed = time.time() - start_time
        
        assert result1 == "test_result", "배치 요청 결과 불일치"
        assert result2 == "test_result", "배치 요청 결과 불일치"
        print(f"✅ 배치 요청 처리 성공: {elapsed:.2f}초")
        
        print("🎉 RequestBatcher 모든 테스트 통과!")
        return True
        
    except Exception as e:
        print(f"❌ RequestBatcher 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_async_http_client_structure():
    """AsyncHTTPClient 구조 테스트 (네트워크 없음)"""
    print("\n🌐 AsyncHTTPClient 구조 테스트 시작...")
    
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
        
        # Rate limit 설정 확인
        assert client.rate_limit_calls == 10, "Rate limit 호출 수 설정 오류"
        assert client.rate_limit_window == 60, "Rate limit 윈도우 설정 오류"
        assert client.rate_limit_requests == [], "Rate limit 요청 리스트 초기화 오류"
        print("✅ Rate limit 설정 확인 성공")
        
        # 통계 확인
        stats = client.get_performance_stats()
        assert 'request_count' in stats, "클라이언트 통계 형식 오류"
        assert 'cache_hit_rate' in stats, "캐시 통계 형식 오류"
        print(f"✅ 클라이언트 통계 확인: requests={stats['request_count']}, cache_hit_rate={stats['cache_hit_rate']}")
        
        # 클라이언트 종료
        await client.close()
        print("✅ 클라이언트 종료 성공")
        
        print("🎉 AsyncHTTPClient 구조 테스트 통과!")
        return True
        
    except Exception as e:
        print(f"❌ AsyncHTTPClient 구조 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """메인 테스트 함수"""
    print("=" * 60)
    print("🚀 KAIROS-1 비동기 클라이언트 간단 테스트")
    print("=" * 60)
    
    results = []
    
    # 각 테스트 실행 (내부 구조만 테스트)
    results.append(await test_async_cache())
    results.append(await test_connection_pool())
    results.append(await test_request_batcher())
    results.append(await test_async_http_client_structure())
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("📊 테스트 결과 요약")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    print(f"✅ 통과: {passed}/{total}")
    print(f"❌ 실패: {total - passed}/{total}")
    
    if all(results):
        print("🎉 모든 비동기 클라이언트 테스트 통과!")
        return True
    else:
        print("💥 일부 테스트 실패")
        return False

if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)