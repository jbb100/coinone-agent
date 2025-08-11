"""
Async Client Tests

비동기 클라이언트 핵심 기능 테스트
"""

import pytest
import pytest_asyncio
import asyncio
import aiohttp
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import json

from src.core.async_client import AsyncHTTPClient, AsyncCache
from src.core.exceptions import *


@pytest.mark.async_test
class TestAsyncHTTPClient:
    """AsyncHTTPClient 핵심 기능 테스트"""
    
    @pytest_asyncio.fixture
    async def client(self):
        """AsyncHTTPClient 인스턴스"""
        client = AsyncHTTPClient(
            base_url="https://api.test.com"
        )
        try:
            yield client
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_initialization(self):
        """초기화 테스트"""
        client = AsyncHTTPClient()
        assert client is not None
        assert hasattr(client, 'connection_pool')
        assert hasattr(client, 'cache')
        await client.close()
    
    @pytest.mark.asyncio
    async def test_get_request(self, client):
        """GET 요청 테스트"""
        mock_response = {
            'status': 200,
            'data': {'message': 'success'}
        }
        
        with patch.object(client, '_make_request', return_value=mock_response) as mock_request:
            response = await client.get('/test-endpoint')
            
            assert response['status'] == 200
            assert response['data']['message'] == 'success'
            mock_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_post_request(self, client):
        """POST 요청 테스트"""
        test_data = {'key': 'value', 'number': 123}
        mock_response = {
            'status': 201,
            'data': {'created': True, 'id': 'test123'}
        }
        
        with patch.object(client, '_make_request', return_value=mock_response) as mock_request:
            response = await client.post('/create', data=test_data)
            
            assert response['status'] == 201
            assert response['data']['created'] is True
            mock_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_request_with_headers(self, client):
        """헤더가 포함된 요청 테스트"""
        headers = {
            'Authorization': 'Bearer test-token',
            'Content-Type': 'application/json'
        }
        
        with patch.object(client, '_make_request', return_value={'status': 200}) as mock_request:
            await client.get('/protected', headers=headers)
            
            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert 'headers' in call_args[1]
    
    @pytest.mark.asyncio
    async def test_request_timeout(self, client):
        """요청 타임아웃 테스트"""
        with patch.object(client.session, 'request') as mock_request:
            mock_request.side_effect = asyncio.TimeoutError()
            
            with pytest.raises(APITimeoutException):
                await client.get('/slow-endpoint')
    
    @pytest.mark.asyncio
    async def test_retry_mechanism(self, client):
        """재시도 메커니즘 테스트"""
        call_count = 0
        
        def mock_failing_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise aiohttp.ClientError("Connection failed")
            
            # Mock response 객체 - context manager로 사용
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={'success': True})
            mock_response.text = AsyncMock(return_value='{"success": true}')
            
            # async context manager 구현
            async def async_enter(self):
                return mock_response
            async def async_exit(self, *args):
                return None
                
            mock_response.__aenter__ = async_enter
            mock_response.__aexit__ = async_exit
            return mock_response
        
        with patch.object(client.session, 'request', side_effect=mock_failing_request):
            response = await client.get('/flaky-endpoint')
            
            assert call_count == 3  # 2번 실패 후 3번째 성공
            assert 'success' in response
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, client):
        """요청 속도 제한 테스트"""
        client.rate_limit = 2  # 초당 2요청
        client.rate_window = 1  # 1초
        
        start_time = datetime.now()
        
        # Mock _make_request to return success
        with patch.object(client, '_make_request', return_value={'status': 200}) as mock_request:
            # 연속으로 여러 요청 보내기
            tasks = []
            for i in range(3):
                tasks.append(client.get(f'/endpoint-{i}'))
            
            await asyncio.gather(*tasks)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # 속도 제한으로 인해 최소 0.5초는 걸려야 함 (3개 요청, 초당 2개 허용)
        assert duration >= 0.5
    
    @pytest.mark.asyncio
    async def test_session_management(self):
        """세션 관리 테스트"""
        client = AsyncHTTPClient()
        
        # 세션이 자동으로 생성되는지 확인
        assert client.session is not None
        
        # 세션 닫기
        await client.close()
        assert client.session is None or client.session.closed
    
    @pytest.mark.asyncio
    async def test_error_handling(self, client):
        """오류 처리 테스트"""
        # 4xx 클라이언트 오류
        with patch.object(client.session, 'request') as mock_request:
            mock_response = AsyncMock()
            mock_response.status = 400
            mock_response.text = AsyncMock(return_value='Bad Request')
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)
            mock_request.return_value = mock_response
            
            with pytest.raises(APIClientException):
                await client.get('/bad-request')
        
        # 5xx 서버 오류
        with patch.object(client.session, 'request') as mock_request:
            mock_response = AsyncMock()
            mock_response.status = 500
            mock_response.text = AsyncMock(return_value='Internal Server Error')
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)
            mock_request.return_value = mock_response
            
            with pytest.raises(APIServerException):
                await client.get('/server-error')


@pytest.mark.async_test
class TestAsyncCache:
    """AsyncCache 기능 테스트"""
    
    @pytest_asyncio.fixture
    async def cache(self):
        """AsyncCache 인스턴스"""
        cache = AsyncCache(max_memory_items=100)
        try:
            yield cache
        finally:
            cache.clear_cache()
    
    @pytest.mark.asyncio
    async def test_basic_cache_operations(self, cache):
        """기본 캐시 작업 테스트"""
        # 데이터 저장
        await cache.set('test_key', {'data': 'test_value'})
        
        # 데이터 조회
        value = await cache.get('test_key')
        assert value == {'data': 'test_value'}
        
        # 존재하지 않는 키
        none_value = await cache.get('nonexistent_key')
        assert none_value is None
    
    @pytest.mark.asyncio
    async def test_cache_expiration(self, cache):
        """캐시 만료 테스트"""
        # 짧은 TTL로 데이터 저장
        await cache.set('expire_key', 'expire_value', ttl=1)
        
        # 즉시 조회하면 값이 있어야 함
        value = await cache.get('expire_key')
        assert value == 'expire_value'
        
        # 1.1초 후 조회하면 만료되어야 함
        await asyncio.sleep(1.1)
        expired_value = await cache.get('expire_key')
        assert expired_value is None
    
    @pytest.mark.asyncio
    async def test_cache_hit_miss_stats(self, cache):
        """캐시 히트/미스 통계 테스트"""
        initial_stats = cache.get_stats()
        
        # 미스 (키가 없음)
        await cache.get('miss_key')
        
        # 히트 (키 저장 후 조회)
        await cache.set('hit_key', 'hit_value')
        await cache.get('hit_key')
        
        final_stats = cache.get_stats()
        
        assert final_stats['misses'] == initial_stats['misses'] + 1
        assert final_stats['hits'] == initial_stats['hits'] + 1
    
    @pytest.mark.asyncio
    async def test_cache_size_limit(self):
        """캐시 크기 제한 테스트"""
        # 작은 캐시 생성
        small_cache = AsyncCache(max_memory_items=3)
        
        # 한계를 초과하여 데이터 저장
        for i in range(5):
            await small_cache.set(f'key_{i}', f'value_{i}')
        
        # 오래된 데이터가 제거되었는지 확인
        stats = small_cache.get_stats()
        assert stats['size'] <= 3
        
        # 가장 최근 데이터는 남아있어야 함
        recent_value = await small_cache.get('key_4')
        assert recent_value == 'value_4'
        
        small_cache.clear_cache()
    
    @pytest.mark.asyncio
    async def test_cache_delete(self, cache):
        """캐시 삭제 테스트"""
        # 데이터 저장
        await cache.set('delete_key', 'delete_value')
        
        # 존재 확인
        value = await cache.get('delete_key')
        assert value == 'delete_value'
        
        # 삭제
        await cache.delete('delete_key')
        
        # 삭제 확인
        deleted_value = await cache.get('delete_key')
        assert deleted_value is None
    
    @pytest.mark.asyncio
    async def test_cache_clear(self, cache):
        """캐시 전체 삭제 테스트"""
        # 여러 데이터 저장
        for i in range(5):
            await cache.set(f'clear_key_{i}', f'clear_value_{i}')
        
        # 캐시에 데이터가 있는지 확인
        stats_before = cache.get_stats()
        assert stats_before['size'] == 5
        
        # 전체 삭제
        cache.clear_cache()
        
        # 삭제 확인
        stats_after = cache.get_stats()
        assert stats_after['size'] == 0
    
    @pytest.mark.asyncio
    async def test_concurrent_cache_access(self, cache):
        """동시 캐시 접근 테스트"""
        async def cache_worker(worker_id):
            for i in range(10):
                key = f'worker_{worker_id}_key_{i}'
                value = f'worker_{worker_id}_value_{i}'
                await cache.set(key, value)
                retrieved = await cache.get(key)
                assert retrieved == value
        
        # 여러 워커가 동시에 캐시 접근
        workers = [cache_worker(i) for i in range(5)]
        await asyncio.gather(*workers)
        
        # 최종 상태 확인
        stats = cache.get_stats()
        assert stats['size'] <= 100  # 최대 크기 제한 내
        assert stats['hits'] >= 50   # 모든 조회가 성공했어야 함


@pytest.mark.async_test
class TestAsyncClientIntegration:
    """AsyncHTTPClient와 AsyncCache 통합 테스트"""
    
    @pytest.mark.asyncio
    async def test_cached_requests(self):
        """캐시된 요청 테스트"""
        cache = AsyncCache()
        client = AsyncHTTPClient()
        
        # 캐시 적용된 클라이언트 생성
        client.cache = cache
        
        try:
            # Mock 응답
            mock_response_data = {'api_data': 'test_response', 'timestamp': '2024-01-01'}
            
            with patch.object(client, '_make_request', return_value=mock_response_data) as mock_request:
                # 첫 번째 요청 (캐시 미스)
                response1 = await client.get_cached('/cached-endpoint')
                assert response1 == mock_response_data
                
                # 두 번째 요청 (캐시 히트, 실제 HTTP 요청 없음)
                response2 = await client.get_cached('/cached-endpoint')
                assert response2 == mock_response_data
                
                # HTTP 요청은 한 번만 발생해야 함
                mock_request.assert_called_once()
                
                # 캐시 통계 확인
                stats = cache.get_stats()
                assert stats['hits'] >= 1
        
        finally:
            await client.close()
            cache.clear_cache()
    
    @pytest.mark.asyncio
    async def test_request_batching(self):
        """요청 배치 처리 테스트"""
        client = AsyncHTTPClient()
        
        try:
            # 동일한 엔드포인트에 대한 여러 요청을 배치로 처리
            mock_responses = [
                {'id': 1, 'data': 'response1'},
                {'id': 2, 'data': 'response2'},
                {'id': 3, 'data': 'response3'}
            ]
            
            call_count = 0
            
            async def mock_request(*args, **kwargs):
                nonlocal call_count
                response = mock_responses[call_count]
                call_count += 1
                return response
            
            with patch.object(client, '_make_request', side_effect=mock_request):
                # 동시에 여러 요청 실행
                tasks = [
                    client.get('/batch-endpoint', params={'id': 1}),
                    client.get('/batch-endpoint', params={'id': 2}),
                    client.get('/batch-endpoint', params={'id': 3})
                ]
                
                responses = await asyncio.gather(*tasks)
                
                assert len(responses) == 3
                assert responses[0]['data'] == 'response1'
                assert responses[1]['data'] == 'response2'
                assert responses[2]['data'] == 'response3'
        
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_connection_pooling(self):
        """연결 풀링 테스트"""
        # 연결 풀 크기 제한된 클라이언트 생성
        client = AsyncHTTPClient()
        
        try:
            # 동시에 여러 요청을 보내 연결 풀 동작 확인
            with patch.object(client, '_make_request', return_value={'status': 'ok'}) as mock_request:
                tasks = []
                for i in range(5):
                    tasks.append(client.get(f'/pool-test-{i}'))
                
                responses = await asyncio.gather(*tasks)
                
                assert len(responses) == 5
                assert all(response['status'] == 'ok' for response in responses)
                assert mock_request.call_count == 5
        
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_real_world_scenario(self):
        """실제 사용 시나리오 테스트"""
        cache = AsyncCache()
        client = AsyncHTTPClient(
            base_url="https://api.example.com"
        )
        client.cache = cache
        
        try:
            # 실제 API 호출 시뮬레이션
            mock_api_responses = {
                '/ticker/BTC': {'price': 50000, 'volume': 1000},
                '/ticker/ETH': {'price': 3000, 'volume': 2000},
                '/balance': {'BTC': 0.1, 'ETH': 1.0, 'KRW': 1000000}
            }
            
            async def mock_request(method, url, **kwargs):
                for endpoint, response in mock_api_responses.items():
                    if endpoint in url:
                        return response
                return {'error': 'Not found'}
            
            with patch.object(client, '_make_request', side_effect=mock_request):
                # 가격 정보 조회 (캐시됨)
                btc_price = await client.get_cached('/ticker/BTC')
                eth_price = await client.get_cached('/ticker/ETH')
                
                # 잔고 조회 (실시간)
                balance = await client.get('/balance')
                
                assert btc_price['price'] == 50000
                assert eth_price['price'] == 3000
                assert balance['KRW'] == 1000000
                
                # 캐시 효과 확인 (동일한 가격 정보 재조회)
                btc_price_cached = await client.get_cached('/ticker/BTC')
                assert btc_price_cached == btc_price
        
        finally:
            await client.close()
            cache.clear_cache()