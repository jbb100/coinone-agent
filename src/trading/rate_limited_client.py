"""
Rate Limited Client
CoinoneClient에 API 속도 제한을 적용하는 래퍼 클래스입니다.
기존 코드 변경 없이 속도 제한 기능을 추가할 수 있습니다.
"""
import asyncio
from typing import Any, Dict
from loguru import logger
from .coinone_client import CoinoneClient
from ..core.system_coordinator import get_system_coordinator
class RateLimitedCoinoneClient:
    """
    속도 제한이 적용된 CoinoneClient 래퍼
    기존 CoinoneClient의 모든 메서드를 동일하게 제공하면서
    API 호출에 속도 제한을 적용합니다.
    """
    def __init__(self, original_client: CoinoneClient):
        """
        Args:
            original_client: 원본 CoinoneClient 인스턴스
        """
        self.original_client = original_client
        self.system_coordinator = get_system_coordinator()
        logger.info("RateLimitedCoinoneClient 초기화 완료")
    def __getattr__(self, name):
        """
        원본 클라이언트의 속성/메서드에 대한 프록시
        API 호출 메서드는 속도 제한을 적용하고, 나머지는 그대로 전달
        """
        attr = getattr(self.original_client, name)
        # 메서드인 경우 속도 제한 래핑
        if callable(attr):
            # API 호출 메서드들 (실제 네트워크 요청을 하는 메서드들)
            api_methods = {
                'get_account_info', 'get_balances', 'get_portfolio_value',
                'place_order', 'cancel_order', 'get_order_status',
                'get_latest_price', 'get_orderbook', 'get_ticker',
                'get_orders_history', 'get_order_info', 'get_user_info',
                'submit_market_order', 'submit_limit_order'
            }
            if name in api_methods:
                return self._wrap_api_method(attr, name)
        return attr
    def _wrap_api_method(self, method, method_name: str):
        """API 메서드를 속도 제한 래퍼로 감싸기"""
        def wrapped_method(*args, **kwargs):
            try:
                # 동기 방식으로 속도 제한 적용
                loop = None
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    # 이벤트 루프가 없으면 새로 생성
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                # 비동기 컨텍스트에서 실행
                if loop.is_running():
                    # 이미 실행 중인 루프에서는 동기적으로 처리
                    logger.debug(f"API 호출: {method_name} (동기 모드)")
                    return method(*args, **kwargs)
                else:
                    # 새 루프에서 비동기 처리
                    return loop.run_until_complete(
                        self._async_api_call(method, method_name, *args, **kwargs)
                    )
            except Exception as e:
                logger.error(f"속도 제한 API 호출 실패 ({method_name}): {e}")
                # 실패 시 원본 메서드 직접 호출
                return method(*args, **kwargs)
        return wrapped_method
    async def _async_api_call(self, method, method_name: str, *args, **kwargs):
        """비동기 API 호출 (속도 제한 적용)"""
        logger.debug(f"API 호출 대기 중: {method_name}")
        # 속도 제한 적용
        await self.system_coordinator.api_rate_limiter.acquire()
        logger.debug(f"API 호출 실행: {method_name}")
        return method(*args, **kwargs)
    # 주요 메서드들을 명시적으로 정의 (IDE 지원 및 타입 힌트)
    def get_account_info(self) -> Dict[str, Any]:
        """계정 정보 조회"""
        return self.original_client.get_account_info()
    def get_balances(self) -> Dict[str, float]:
        """잔고 조회"""
        return self.original_client.get_balances()
    def get_portfolio_value(self) -> Dict[str, Any]:
        """포트폴리오 가치 조회"""
        return self.original_client.get_portfolio_value()
    def place_order(self, *args, **kwargs) -> Dict[str, Any]:
        """주문 실행"""
        return self.original_client.place_order(*args, **kwargs)
    def get_latest_price(self, currency: str) -> float:
        """최신 가격 조회"""
        return self.original_client.get_latest_price(currency)
    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """주문 취소"""
        return self.original_client.cancel_order(order_id)
    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """주문 상태 조회"""
        return self.original_client.get_order_status(order_id)
def create_rate_limited_client(original_client: CoinoneClient) -> RateLimitedCoinoneClient:
    """
    기존 CoinoneClient를 속도 제한 적용 클라이언트로 래핑
    Args:
        original_client: 원본 CoinoneClient
    Returns:
        속도 제한이 적용된 클라이언트
    """
    return RateLimitedCoinoneClient(original_client)
