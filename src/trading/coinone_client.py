"""
Coinone API Client

코인원 거래소 API 연동을 위한 클라이언트 클래스
코인원 공식 API v2 (Public) / v2.1 (Private) 명세 준수
Reference: https://docs.coinone.co.kr/reference
"""

import hashlib
import hmac
import time
import json
import base64
import uuid
from typing import Dict, List, Optional, Any
from urllib.parse import urlencode
import requests
from loguru import logger


class CoinoneClient:
    """
    코인원 거래소 API 클라이언트
    
    코인원 공식 API v2 (Public) / v2.1 (Private) 명세 준수
    - Public API: GET 방식, /public/v2/...
    - Private API: POST 방식, v2.1
    """
    
    def __init__(self, api_key: str, secret_key: str, sandbox: bool = False):
        """
        Args:
            api_key: 코인원 API 키
            secret_key: 코인원 시크릿 키
            sandbox: 테스트 환경 사용 여부 (현재 지원하지 않음)
        """
        self.api_key = api_key
        self.secret_key = secret_key
        
        # 코인원 실제 API 엔드포인트 사용
        self.base_url = "https://api.coinone.co.kr"
        
        if sandbox:
            logger.warning("샌드박스 모드는 현재 지원하지 않습니다. 실제 API를 사용합니다.")
        
        logger.info("CoinoneClient 초기화: 실제 API 모드")
        
        # 지원하는 코인 리스트 (코인원 상장 기준)
        # KRW 마켓 기준으로 주요 코인들
        self.supported_coins = ["BTC", "ETH", "XRP", "SOL", "ADA", "DOT", "MATIC", "LINK"]
        self.quote_currency = "KRW"  # 기준 통화
    
    def _create_signature(self, request_body: Dict) -> Dict[str, str]:
        """
        API 요청 서명 생성 (코인원 공식 v2.1 Private API 방식)
        
        Args:
            request_body: 요청 Body 딕셔너리
            
        Returns:
            헤더 딕셔너리
        """
        import uuid
        
        # 공식 문서 명세: access_token과 nonce 추가
        body = {
            'access_token': self.api_key,
            'nonce': str(uuid.uuid4()),  # UUID nonce 생성
            **request_body
        }
        
        # 1. Request body → JSON string → base64
        payload_json = json.dumps(body, separators=(',', ':'))
        payload_base64 = base64.b64encode(payload_json.encode('utf-8')).decode('utf-8')
        
        # 2. HMAC(X-COINONE-PAYLOAD, SECRET_KEY, SHA512).hexdigest()
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            payload_base64.encode('utf-8'),
            hashlib.sha512  # 공식 문서: SHA512 사용
        ).hexdigest()
        
        # 3. 공식 문서 헤더 구조
        headers = {
            "Content-Type": "application/json",
            "X-COINONE-PAYLOAD": payload_base64,
            "X-COINONE-SIGNATURE": signature
        }
        
        return headers, body
    
    def _make_request(self, method: str, endpoint: str, params: Dict = None, is_public: bool = False) -> Dict:
        """
        API 요청 실행
        
        Args:
            method: HTTP 메서드
            endpoint: API 엔드포인트  
            params: 요청 파라미터
            is_public: Public API 여부
            
        Returns:
            응답 데이터
        """
        url = f"{self.base_url}{endpoint}"
        
        if is_public:
            # Public API는 인증 헤더 없이 GET 요청
            headers = {"Content-Type": "application/json"}
            try:
                response = requests.get(url, headers=headers, params=params)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                logger.error(f"Public API 요청 실패: {e}")
                raise
        else:
            # Private API v2.1: 공식 인증 방식 사용
            if params is None:
                params = {}
            
            headers, body = self._create_signature(params)
            try:
                response = requests.post(url, headers=headers, json=body)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                logger.error(f"Private API 요청 실패: {e}")
                raise

    def get_account_info(self) -> Dict:
        """
        계좌 정보 조회
        
        Note: 코인원 공식 API에는 사용자 정보 조회 API가 명시되어 있지 않음
        대신 잔고 조회로 계좌 활성 상태를 확인
        
        Returns:
            계좌 정보 딕셔너리
        """
        try:
            # 잔고 조회로 계좌 접근 가능 여부 확인
            balances = self.get_balances()
            
            logger.info("계좌 정보 조회 성공 (잔고 조회로 확인)")
            return {
                "result": "success",
                "account_status": "active",
                "balance_count": len(balances),
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error(f"계좌 정보 조회 실패: {e}")
            return {
                "result": "error", 
                "error_code": "ACCOUNT_CHECK_FAILED",
                "message": str(e)
            }
    
    def get_balances(self) -> Dict[str, float]:
        """
        자산 잔고 조회 (Private API v2.1)
        
        Returns:
            코인별 잔고 딕셔너리
        """
        try:
            # Private API v2.1: POST 방식으로 전체 잔고 조회 (공식 문서 엔드포인트)
            response = self._make_request("POST", "/v2.1/account/balance/all", {}, is_public=False)
            
            balances = {}
            if response.get("result") == "success":
                # 공식 문서 응답 구조: "balances" 배열
                balance_data = response.get("balances", [])
                
                for asset in balance_data:
                    currency = asset.get("currency", "").upper()
                    available = float(asset.get("available", 0))
                    limit = float(asset.get("limit", 0))
                    # 전체 잔고 = available + limit (주문 대기 중)
                    total_balance = available + limit
                    balances[currency] = total_balance
            
            logger.info(f"잔고 조회 성공: {len(balances)}개 자산")
            return balances
            
        except Exception as e:
            logger.error(f"잔고 조회 실패: {e}")
            raise
    
    def get_ticker(self, currency: str = "BTC") -> Dict:
        """
        시세 정보 조회 (Public API v2)
        
        Args:
            currency: 조회할 코인 (기본값: BTC)
            
        Returns:
            시세 정보 딕셔너리
        """
        try:
            # Public API v2: GET 방식, 경로 파라미터 사용
            endpoint = f"/public/v2/ticker/{self.quote_currency}/{currency}"
            
            response = self._make_request("GET", endpoint, None, is_public=True)
            logger.debug(f"{currency} 시세 조회 성공")
            return response
            
        except Exception as e:
            logger.error(f"{currency} 시세 조회 실패: {e}")
            raise

    def get_all_tickers(self) -> Dict:
        """
        전체 티커 정보 조회 (Public API v2)
        
        Returns:
            전체 시세 정보 딕셔너리
        """
        try:
            # Public API v2: 전체 티커 정보
            endpoint = "/public/v2/ticker/all"
            
            response = self._make_request("GET", endpoint, None, is_public=True)
            logger.debug("전체 티커 조회 성공")
            return response
            
        except Exception as e:
            logger.error(f"전체 티커 조회 실패: {e}")
            raise

    def _generate_nonce(self) -> str:
        """UUID nonce 생성"""
        return str(uuid.uuid4())

    def place_order(
        self,
        currency: str,
        side: str,  # "buy" or "sell"
        amount: float,
        price: Optional[float] = None,
        amount_in_krw: bool = False  # True이면 amount를 KRW 금액으로 처리
    ) -> Dict:
        """
        주문 실행 (Private API v2.1)
        코인원 공식 API 명세: https://docs.coinone.co.kr/reference/place-order
        
        Args:
            currency: 거래할 코인
            side: 매수/매도 ("buy" or "sell")
            amount: 주문 수량
            price: 지정가 (None인 경우 시장가)
            
        Returns:
            주문 결과 딕셔너리
        """
        try:
            # 코인원 공식 API v2.1 엔드포인트: /v2.1/order
            endpoint = "/v2.1/order"
            
            if price is not None:
                # 지정가 주문 (LIMIT)
                params = {
                    "access_token": self.api_key,
                    "nonce": self._generate_nonce(),
                    "side": side.upper(),
                    "quote_currency": "KRW",
                    "target_currency": currency.upper(),
                    "type": "LIMIT",
                    "price": str(int(price)),
                    "qty": str(amount),
                    "post_only": False
                }
                logger.info(f"지정가 주문: {side} {amount} {currency} @ {price}")
                
            else:
                # 시장가 주문 (MARKET)
                if side.lower() == "buy":
                    # 시장가 매수: amount 필드 사용 (주문 총액)
                    if amount_in_krw:
                        # amount가 이미 KRW 금액인 경우
                        total_amount = amount
                        logger.info(f"시장가 매수: {total_amount:,.0f} KRW → {currency}")
                    else:
                        # amount가 암호화폐 수량인 경우 (기존 로직)
                        try:
                            ticker = self.get_ticker(currency)
                            # 코인원 API 응답 구조: data.close_24h에 현재가 포함
                            current_price = float(ticker.get("data", {}).get("close_24h", 0))
                            if current_price <= 0:
                                raise ValueError(f"잘못된 현재가: {current_price}")
                            total_amount = amount * current_price
                            logger.info(f"현재가 조회 성공: {currency} = {current_price:,.0f} KRW")
                            logger.info(f"시장가 매수: {amount} {currency} (총액: {total_amount:,.0f} KRW)")
                        except Exception as e:
                            logger.error(f"시장가 매수 중 현재가 조회 실패: {e}")
                            raise Exception(f"현재가 조회 실패로 시장가 매수 불가: {e}")
                    
                    params = {
                        "access_token": self.api_key,
                        "nonce": self._generate_nonce(),
                        "side": "BUY",
                        "quote_currency": "KRW",
                        "target_currency": currency.upper(),
                        "type": "MARKET",
                        "amount": str(int(total_amount))
                    }
                    
                else:
                    # 시장가 매도: qty 필드 사용 (주문 수량)
                    params = {
                        "access_token": self.api_key,
                        "nonce": self._generate_nonce(),
                        "side": "SELL",
                        "quote_currency": "KRW",
                        "target_currency": currency.upper(),
                        "type": "MARKET",
                        "qty": str(amount)
                    }
                    logger.info(f"시장가 매도: {amount} {currency}")
            
            response = self._make_request("POST", endpoint, params, is_public=False)
            
            if response.get("result") == "success":
                order_id = response.get("order_id", "unknown")
                logger.info(f"✅ 주문 성공: {side} {amount} {currency} (주문ID: {order_id})")
            else:
                error_code = response.get("error_code", "unknown")
                logger.error(f"❌ 주문 실패: {response}")
                
            return response
            
        except Exception as e:
            logger.error(f"주문 실행 실패: {e}")
            raise

    def get_order_status(self, order_id: str) -> Dict:
        """
        주문 상태 조회 (Private API v2.1)
        
        Args:
            order_id: 주문 ID
            
        Returns:
            주문 상태 정보
        """
        try:
            # Private API v2.1: 특정 주문 정보 조회
            params = {"order_id": order_id}
            
            response = self._make_request("POST", "/private/v2.1/order/info", params, is_public=False)
            logger.debug(f"주문 상태 조회: {order_id}")
            return response
            
        except Exception as e:
            logger.error(f"주문 상태 조회 실패: {e}")
            raise
    
    def cancel_order(self, order_id: str) -> Dict:
        """
        주문 취소 (Private API v2.1)
        
        Args:
            order_id: 주문 ID
            
        Returns:
            주문 취소 결과
        """
        try:
            # Private API v2.1: 개별 주문 취소
            params = {"order_id": order_id}
            
            response = self._make_request("POST", "/private/v2.1/order/cancel", params, is_public=False)
            
            if response.get("result") == "success":
                logger.info(f"주문 취소 성공: {order_id}")
            else:
                logger.error(f"주문 취소 실패: {response}")
                
            return response
            
        except Exception as e:
            logger.error(f"주문 취소 실패: {e}")
            raise
    
    def get_portfolio_value(self) -> Dict[str, float]:
        """
        포트폴리오 총 가치 계산 (KRW 기준)
        
        Returns:
            포트폴리오 가치 정보
        """
        try:
            balances = self.get_balances()
            portfolio_value = {"total_krw": 0, "assets": {}}
            
            # KRW 잔고
            krw_balance = balances.get("KRW", 0)
            portfolio_value["assets"]["KRW"] = krw_balance
            portfolio_value["total_krw"] += krw_balance
            
            # 암호화폐 잔고를 KRW로 환산
            for coin in self.supported_coins:
                coin_balance = balances.get(coin, 0)
                if coin_balance > 0:
                    ticker = self.get_ticker(coin)
                    # 코인원 API 응답 구조에 맞게 수정: data.close_24h에서 현재가 추출
                    price_krw = float(ticker.get("data", {}).get("close_24h", 0))
                    value_krw = coin_balance * price_krw
                    
                    portfolio_value["assets"][coin] = {
                        "balance": coin_balance,
                        "price_krw": price_krw,
                        "value_krw": value_krw
                    }
                    portfolio_value["total_krw"] += value_krw
                    
                    logger.debug(f"{coin} 가치 계산: {coin_balance} * {price_krw:,.0f} = {value_krw:,.0f} KRW")
            
            logger.info(f"포트폴리오 총 가치: {portfolio_value['total_krw']:,.0f} KRW")
            return portfolio_value
            
        except Exception as e:
            logger.error(f"포트폴리오 가치 계산 실패: {e}")
            raise


# 설정 상수
SUPPORTED_CRYPTOCURRENCIES = ["BTC", "ETH", "XRP", "SOL"]
DEFAULT_ORDER_TIMEOUT = 30  # 주문 타임아웃 (초)
API_RATE_LIMIT = 100  # API 호출 제한 (분당) 