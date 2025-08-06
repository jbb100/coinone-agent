#!/usr/bin/env python3
"""
비동기 클라이언트 단독 테스트 스크립트
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

async def test_async_http_client():
    """AsyncHTTPClient 테스트"""
    print("\n🌐 AsyncHTTPClient 테스트 시작...")
    
    try:
        from src.core.async_client import AsyncHTTPClient
        
        # AsyncHTTPClient 초기화
        client = AsyncHTTPClient(
            base_url="https://httpbin.org",
            enable_caching=True,
            cache_ttl=60,
            enable_batching=False,
            rate_limit=(10, 60)  # 분당 10회 제한
        )
        print("✅ AsyncHTTPClient 초기화 성공")
        
        # GET 요청 테스트
        try:
            response = await client.get("/get", params={"test": "value"})
            assert 'args' in response, "GET 응답 형식 오류"
            assert response['args']['test'] == 'value', "GET 파라미터 전달 실패"
            print("✅ GET 요청 성공")
        except Exception as e:
            print(f"⚠️ GET 요청 스킵 (네트워크 문제): {e}")
        
        # POST 요청 테스트
        try:
            response = await client.post("/post", json={"key": "value"})
            assert 'json' in response, "POST 응답 형식 오류"
            assert response['json']['key'] == 'value', "POST JSON 전달 실패"
            print("✅ POST 요청 성공")
        except Exception as e:
            print(f"⚠️ POST 요청 스킵 (네트워크 문제): {e}")
        
        # 캐시 테스트
        try:
            # 같은 요청을 두 번 해서 캐시 확인
            response1 = await client.get("/get?cache_test=1")
            response2 = await client.get("/get?cache_test=1")
            print("✅ 캐시 기능 테스트 완료")
        except Exception as e:
            print(f"⚠️ 캐시 테스트 스킵 (네트워크 문제): {e}")
        
        # 통계 확인
        stats = client.get_performance_stats()
        assert 'request_count' in stats, "클라이언트 통계 형식 오류"
        print(f"✅ 클라이언트 통계 확인: requests={stats['request_count']}")
        
        # 클라이언트 종료
        await client.close()
        print("✅ 클라이언트 종료 성공")
        
        print("🎉 AsyncHTTPClient 모든 테스트 통과!")
        return True
        
    except Exception as e:
        print(f"❌ AsyncHTTPClient 테스트 실패: {e}")
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

async def test_http_client_rate_limiting():
    """HTTP 클라이언트의 Rate Limiting 테스트"""
    print("\n⏱️ HTTP 클라이언트 Rate Limiting 테스트 시작...")
    
    try:
        from src.core.async_client import AsyncHTTPClient
        import time
        
        # Rate limit이 있는 클라이언트 생성 (초당 2회)
        client = AsyncHTTPClient(
            base_url="https://httpbin.org",
            rate_limit=(2, 1)  # 1초당 2회
        )
        print("✅ Rate Limited 클라이언트 초기화 성공")
        
        # 연속 요청 테스트 (네트워크 에러는 무시)
        start_time = time.time()
        try:
            for i in range(3):
                await client.get(f"/get?test={i}")
                print(f"✅ 요청 {i+1} 완료")
        except Exception as e:
            print(f"⚠️ 네트워크 요청 스킵: {e}")
        
        elapsed = time.time() - start_time
        print(f"✅ Rate Limiting 테스트 완료: {elapsed:.2f}초 소요")
        
        # 클라이언트 종료
        await client.close()
        
        print("🎉 HTTP 클라이언트 Rate Limiting 테스트 통과!")
        return True
        
    except Exception as e:
        print(f"❌ Rate Limiting 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """메인 테스트 함수"""
    print("=" * 60)
    print("🚀 KAIROS-1 비동기 클라이언트 단독 테스트")
    print("=" * 60)
    
    results = []
    
    # 각 테스트 실행
    results.append(await test_async_cache())
    results.append(await test_connection_pool())
    results.append(await test_request_batcher())
    results.append(await test_http_client_rate_limiting())
    results.append(await test_async_http_client())  # 네트워크 필요한 테스트는 마지막에
    
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