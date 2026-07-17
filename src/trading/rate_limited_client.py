"""
Rate Limited Client
CoinoneClient에 API 속도 제한을 적용하는 래퍼 클래스입니다.
기존 코드 변경 없이 속도 제한 기능을 추가할 수 있습니다.

주의: API 메서드를 클래스에 명시적으로 정의하면 __getattr__이 호출되지
않아 래핑이 무력화된다 (과거 버그). 모든 프록시는 __getattr__로만 한다.
"""
import asyncio
from loguru import logger
from .coinone_client import CoinoneClient
from ..core.system_coordinator import get_system_coordinator

# 실제 네트워크 요청을 하는 메서드들 — 속도 제한 적용 대상
API_METHODS = {
    'get_account_info', 'get_balances', 'get_portfolio_value',
    'place_order', 'cancel_order', 'get_order_status',
    'get_latest_price', 'get_orderbook', 'get_ticker',
    'get_orders_history', 'get_order_info', 'get_user_info',
    'submit_market_order', 'submit_limit_order'
}


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
        if callable(attr) and name in API_METHODS:
            return self._wrap_api_method(attr, name)
        return attr

    def _wrap_api_method(self, method, method_name: str):
        """API 메서드를 속도 제한 래퍼로 감싸기.

        원본 메서드는 정확히 1회만 호출한다 — 실패 시 재호출 폴백은
        주문 같은 부작용 있는 호출을 이중 실행할 수 있어 금지."""
        def wrapped_method(*args, **kwargs):
            self._throttle(method_name)
            return method(*args, **kwargs)
        return wrapped_method

    def _throttle(self, method_name: str) -> None:
        """속도 제한 획득 — 리미터 문제가 실제 호출을 막으면 안 됨."""
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            if loop.is_running():
                # 실행 중인 루프 안에서는 동기 대기 불가 — 제한 없이 통과
                logger.debug(f"API 호출 (루프 내 동기 모드): {method_name}")
                return
            loop.run_until_complete(
                self.system_coordinator.api_rate_limiter.acquire()
            )
        except Exception as e:
            logger.warning(f"속도 제한 획득 실패 (호출은 계속): {method_name} — {e}")


def create_rate_limited_client(original_client: CoinoneClient) -> RateLimitedCoinoneClient:
    """
    기존 CoinoneClient를 속도 제한 적용 클라이언트로 래핑
    Args:
        original_client: 원본 CoinoneClient
    Returns:
        속도 제한이 적용된 클라이언트
    """
    return RateLimitedCoinoneClient(original_client)
