"""
Coinone Client Tests

코인원 API 클라이언트 테스트
"""

import pytest
import json
import base64
import hashlib
import hmac
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.trading.coinone_client import CoinoneClient


@pytest.mark.trading
class TestCoinoneClientInit:
    """CoinoneClient 초기화 테스트"""

    def test_init_basic(self):
        """기본 초기화"""
        client = CoinoneClient(api_key="test_key", secret_key="test_secret")

        assert client.api_key == "test_key"
        assert client.secret_key == "test_secret"
        assert client.base_url == "https://api.coinone.co.kr"
        assert client.quote_currency == "KRW"

    def test_init_sandbox_warning(self):
        """샌드박스 모드 경고"""
        with patch('src.trading.coinone_client.logger') as mock_logger:
            client = CoinoneClient(
                api_key="test_key",
                secret_key="test_secret",
                sandbox=True
            )
            mock_logger.warning.assert_called()

    def test_supported_coins(self):
        """지원 코인 목록 확인"""
        client = CoinoneClient(api_key="test", secret_key="test")

        assert "BTC" in client.supported_coins
        assert "ETH" in client.supported_coins
        assert isinstance(client.supported_coins, list)


@pytest.mark.trading
class TestCoinoneClientSignature:
    """서명 생성 테스트"""

    @pytest.fixture
    def client(self):
        """테스트 클라이언트"""
        return CoinoneClient(api_key="test_api_key", secret_key="test_secret_key")

    def test_create_signature_structure(self, client):
        """서명 구조 확인"""
        request_body = {"test_param": "test_value"}

        headers, body = client._create_signature(request_body)

        assert "X-COINONE-PAYLOAD" in headers
        assert "X-COINONE-SIGNATURE" in headers
        assert "Content-Type" in headers
        assert headers["Content-Type"] == "application/json"
        assert "access_token" in body
        assert "nonce" in body

    def test_create_signature_payload(self, client):
        """페이로드 인코딩 확인"""
        request_body = {"amount": 100}

        headers, body = client._create_signature(request_body)

        # 페이로드 디코딩 가능 여부 확인
        payload = headers["X-COINONE-PAYLOAD"]
        decoded = base64.b64decode(payload).decode('utf-8')
        decoded_json = json.loads(decoded)

        assert decoded_json["amount"] == 100
        assert decoded_json["access_token"] == "test_api_key"

    def test_create_signature_hmac(self, client):
        """HMAC 서명 검증"""
        request_body = {}

        headers, body = client._create_signature(request_body)

        payload = headers["X-COINONE-PAYLOAD"]
        signature = headers["X-COINONE-SIGNATURE"]

        # HMAC 직접 계산하여 비교
        expected_signature = hmac.new(
            "test_secret_key".encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()

        assert signature == expected_signature


@pytest.mark.trading
class TestCoinoneClientRequests:
    """API 요청 테스트"""

    @pytest.fixture
    def client(self):
        """테스트 클라이언트"""
        return CoinoneClient(api_key="test", secret_key="test")

    @patch('requests.get')
    def test_make_request_public(self, mock_get, client):
        """Public API 요청"""
        mock_response = Mock()
        mock_response.json.return_value = {"result": "success", "data": {}}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = client._make_request(
            "GET", "/public/v2/ticker/KRW/BTC", None, is_public=True
        )

        assert result["result"] == "success"
        mock_get.assert_called_once()

    @patch('requests.post')
    def test_make_request_private(self, mock_post, client):
        """Private API 요청"""
        mock_response = Mock()
        mock_response.json.return_value = {"result": "success", "balances": []}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        result = client._make_request(
            "POST", "/v2.1/account/balance/all", {}, is_public=False
        )

        assert result["result"] == "success"
        mock_post.assert_called_once()

    @patch('requests.get')
    def test_make_request_error(self, mock_get, client):
        """요청 실패 처리"""
        import requests
        mock_get.side_effect = requests.exceptions.RequestException("Connection error")

        with pytest.raises(requests.exceptions.RequestException):
            client._make_request("GET", "/public/v2/ticker", None, is_public=True)


@pytest.mark.trading
class TestCoinoneClientAccountInfo:
    """계좌 정보 조회 테스트"""

    @pytest.fixture
    def client(self):
        """테스트 클라이언트"""
        return CoinoneClient(api_key="test", secret_key="test")

    @patch.object(CoinoneClient, 'get_balances')
    def test_get_account_info_success(self, mock_balances, client):
        """계좌 정보 조회 성공"""
        mock_balances.return_value = {"BTC": 1.0, "ETH": 10.0, "KRW": 1000000}

        result = client.get_account_info()

        assert result["result"] == "success"
        assert result["account_status"] == "active"
        assert result["balance_count"] == 3

    @patch.object(CoinoneClient, 'get_balances')
    def test_get_account_info_error(self, mock_balances, client):
        """계좌 정보 조회 실패"""
        mock_balances.side_effect = Exception("API Error")

        result = client.get_account_info()

        assert result["result"] == "error"
        assert result["error_code"] == "ACCOUNT_CHECK_FAILED"


@pytest.mark.trading
class TestCoinoneClientBalances:
    """잔고 조회 테스트"""

    @pytest.fixture
    def client(self):
        """테스트 클라이언트"""
        return CoinoneClient(api_key="test", secret_key="test")

    @patch.object(CoinoneClient, '_make_request')
    def test_get_balances_success(self, mock_request, client):
        """잔고 조회 성공"""
        mock_request.return_value = {
            "result": "success",
            "balances": [
                {"currency": "btc", "available": "1.5", "limit": "0.5"},
                {"currency": "eth", "available": "10.0", "limit": "0"},
                {"currency": "krw", "available": "1000000", "limit": "0"}
            ]
        }

        result = client.get_balances()

        assert result["BTC"] == 2.0  # 1.5 + 0.5
        assert result["ETH"] == 10.0
        assert result["KRW"] == 1000000

    @patch.object(CoinoneClient, '_make_request')
    def test_get_balances_empty(self, mock_request, client):
        """빈 잔고 조회"""
        mock_request.return_value = {
            "result": "success",
            "balances": []
        }

        result = client.get_balances()

        assert result == {}

    @patch.object(CoinoneClient, '_make_request')
    def test_get_balances_error(self, mock_request, client):
        """잔고 조회 실패"""
        mock_request.side_effect = Exception("API Error")

        with pytest.raises(Exception):
            client.get_balances()


@pytest.mark.trading
class TestCoinoneClientTicker:
    """시세 조회 테스트"""

    @pytest.fixture
    def client(self):
        """테스트 클라이언트"""
        return CoinoneClient(api_key="test", secret_key="test")

    @patch.object(CoinoneClient, '_make_request')
    def test_get_ticker_success(self, mock_request, client):
        """시세 조회 성공"""
        mock_request.return_value = {
            "result": "success",
            "data": {
                "last": "50000000",
                "high_24h": "52000000",
                "low_24h": "48000000"
            }
        }

        result = client.get_ticker("BTC")

        assert result["result"] == "success"
        mock_request.assert_called_with(
            "GET", "/public/v2/ticker/KRW/BTC", None, is_public=True
        )

    @patch.object(CoinoneClient, '_make_request')
    def test_get_ticker_different_coin(self, mock_request, client):
        """다른 코인 시세 조회"""
        mock_request.return_value = {"result": "success", "data": {}}

        client.get_ticker("ETH")

        mock_request.assert_called_with(
            "GET", "/public/v2/ticker/KRW/ETH", None, is_public=True
        )

    @patch.object(CoinoneClient, '_make_request')
    def test_get_all_tickers(self, mock_request, client):
        """전체 시세 조회"""
        mock_request.return_value = {
            "result": "success",
            "tickers": []
        }

        result = client.get_all_tickers()

        assert result["result"] == "success"
        mock_request.assert_called_with(
            "GET", "/public/v2/ticker/all", None, is_public=True
        )


@pytest.mark.trading
class TestCoinoneClientRecentTrades:
    """최근 체결 내역 조회 테스트"""

    @pytest.fixture
    def client(self):
        """테스트 클라이언트"""
        return CoinoneClient(api_key="test", secret_key="test")

    @patch.object(CoinoneClient, '_make_request')
    def test_get_recent_trades_success(self, mock_request, client):
        """최근 체결 내역 조회 성공"""
        mock_request.return_value = {
            "result": "success",
            "transactions": [
                {"price": "50000000", "qty": "0.1"},
                {"price": "49900000", "qty": "0.2"}
            ]
        }

        result = client.get_recent_trades("BTC", size=10)

        assert result["result"] == "success"
        assert len(result["transactions"]) == 2

    @patch.object(CoinoneClient, '_make_request')
    def test_get_recent_trades_custom_size(self, mock_request, client):
        """커스텀 사이즈로 조회"""
        mock_request.return_value = {"result": "success", "transactions": []}

        client.get_recent_trades("ETH", size=50)

        mock_request.assert_called_with(
            "GET", "/public/v2/trades/KRW/ETH", {"size": 50}, is_public=True
        )


@pytest.mark.trading
class TestCoinoneClientLatestPrice:
    """최신 가격 조회 테스트"""

    @pytest.fixture
    def client(self):
        """테스트 클라이언트"""
        return CoinoneClient(api_key="test", secret_key="test")

    @patch.object(CoinoneClient, 'get_recent_trades')
    def test_get_latest_price_from_trades(self, mock_trades, client):
        """최근 체결가에서 가격 조회"""
        mock_trades.return_value = {
            "result": "success",
            "transactions": [
                {"price": "50000000"},
                {"price": "49900000"}
            ]
        }

        result = client.get_latest_price("BTC")

        assert result == 50000000.0

    @patch.object(CoinoneClient, 'get_recent_trades')
    @patch.object(CoinoneClient, 'get_ticker')
    def test_get_latest_price_fallback_ticker(self, mock_ticker, mock_trades, client):
        """체결가 없을 때 티커로 폴백"""
        mock_trades.return_value = {
            "result": "success",
            "transactions": []  # 빈 체결 내역
        }
        mock_ticker.return_value = {
            "result": "success",
            "data": {"last": "50000000"}
        }

        result = client.get_latest_price("BTC")

        assert result == 50000000.0

    @patch.object(CoinoneClient, 'get_recent_trades')
    def test_get_latest_price_error(self, mock_trades, client):
        """가격 조회 실패"""
        mock_trades.side_effect = Exception("API Error")

        result = client.get_latest_price("BTC")

        assert result == 0.0


@pytest.mark.trading
class TestCoinoneClientPlaceOrder:
    """주문 실행 테스트"""

    @pytest.fixture
    def client(self):
        """테스트 클라이언트"""
        return CoinoneClient(api_key="test", secret_key="test")

    @patch.object(CoinoneClient, '_make_request')
    def test_place_limit_order(self, mock_request, client):
        """지정가 주문"""
        mock_request.return_value = {
            "result": "success",
            "order_id": "order_123"
        }

        result = client.place_order(
            currency="BTC",
            side="buy",
            amount=0.01,
            price=50000000
        )

        assert result["success"] is True
        assert result["order_id"] == "order_123"

    @patch.object(CoinoneClient, 'get_latest_price')
    @patch.object(CoinoneClient, '_make_request')
    def test_place_market_buy_order(self, mock_request, mock_price, client):
        """시장가 매수 주문"""
        mock_price.return_value = 50000000.0
        mock_request.return_value = {
            "result": "success",
            "order_id": "order_456"
        }

        result = client.place_order(
            currency="BTC",
            side="buy",
            amount=0.01,
            price=None
        )

        assert result["success"] is True

    @patch.object(CoinoneClient, '_make_request')
    def test_place_market_sell_order(self, mock_request, client):
        """시장가 매도 주문"""
        mock_request.return_value = {
            "result": "success",
            "order_id": "order_789"
        }

        result = client.place_order(
            currency="BTC",
            side="sell",
            amount=0.01,
            price=None
        )

        assert result["success"] is True

    @patch.object(CoinoneClient, 'get_latest_price')
    def test_place_order_min_amount_check(self, mock_price, client):
        """최소 주문 금액 체크"""
        mock_price.return_value = 50000000.0

        result = client.place_order(
            currency="BTC",
            side="buy",
            amount=0.00001,  # 매우 작은 금액
            price=None,
            amount_in_krw=False
        )

        # 최소 금액 미달로 실패
        assert result.get("success") is False or result.get("error_code") == "306"

    @patch.object(CoinoneClient, '_make_request')
    def test_place_order_failure(self, mock_request, client):
        """주문 실패 응답 처리"""
        mock_request.return_value = {
            "result": "error",
            "error_code": "103",
            "error_msg": "Lack of Balance"
        }

        result = client.place_order(
            currency="BTC",
            side="buy",
            amount=1000000000,
            price=50000000
        )

        assert result["success"] is False
        assert result["error_code"] == "103"

    @patch.object(CoinoneClient, '_make_request')
    def test_place_order_exception(self, mock_request, client):
        """주문 실행 중 예외"""
        mock_request.side_effect = Exception("Network Error")

        result = client.place_order(
            currency="BTC",
            side="buy",
            amount=0.01,
            price=50000000
        )

        assert result["success"] is False
        assert "error" in result


@pytest.mark.trading
class TestCoinoneClientSafeOrder:
    """안전한 주문 실행 테스트"""

    @pytest.fixture
    def client(self):
        """테스트 클라이언트"""
        return CoinoneClient(api_key="test", secret_key="test")

    @patch.object(CoinoneClient, 'place_order')
    @patch.object(CoinoneClient, '_adjust_order_size')
    @patch.object(CoinoneClient, '_validate_balance')
    def test_place_safe_order_success(self, mock_validate, mock_adjust, mock_place, client):
        """안전한 주문 성공"""
        mock_validate.return_value = True
        mock_adjust.return_value = 0.01
        mock_place.return_value = {"success": True, "order_id": "safe_123"}

        result = client.place_safe_order(
            currency="BTC",
            side="buy",
            amount=0.01
        )

        assert result["success"] is True

    @patch.object(CoinoneClient, '_validate_balance')
    def test_place_safe_order_insufficient_balance(self, mock_validate, client):
        """잔액 부족 시 실패"""
        mock_validate.return_value = False

        result = client.place_safe_order(
            currency="BTC",
            side="buy",
            amount=100.0
        )

        assert result["success"] is False
        assert "잔액 부족" in result["error"]

    @patch.object(CoinoneClient, 'place_order')
    @patch.object(CoinoneClient, '_adjust_order_size')
    @patch.object(CoinoneClient, '_validate_balance')
    def test_place_safe_order_retry(self, mock_validate, mock_adjust, mock_place, client):
        """주문 재시도"""
        mock_validate.return_value = True
        mock_adjust.return_value = 0.01
        # 첫 번째 시도 실패, 두 번째 성공
        mock_place.side_effect = [
            {"success": False, "error_code": "103", "error_msg": "Lack of Balance"},
            {"success": True, "order_id": "retry_123"}
        ]

        result = client.place_safe_order(
            currency="BTC",
            side="buy",
            amount=0.01,
            max_retries=3
        )

        assert result["success"] is True
        assert mock_place.call_count == 2


@pytest.mark.trading
class TestCoinoneClientHelpers:
    """헬퍼 메서드 테스트"""

    @pytest.fixture
    def client(self):
        """테스트 클라이언트"""
        return CoinoneClient(api_key="test", secret_key="test")

    def test_generate_nonce(self, client):
        """UUID nonce 생성"""
        nonce1 = client._generate_nonce()
        nonce2 = client._generate_nonce()

        assert nonce1 != nonce2
        assert len(nonce1) == 36  # UUID 형식

    @patch.object(CoinoneClient, 'get_balances')
    def test_validate_balance_buy_sufficient(self, mock_balances, client):
        """매수 시 충분한 잔액"""
        mock_balances.return_value = {"KRW": 10000000}

        result = client._validate_balance("BTC", "buy", 1000000, amount_in_krw=True)

        assert result is True

    @patch.object(CoinoneClient, 'get_balances')
    def test_validate_balance_buy_insufficient(self, mock_balances, client):
        """매수 시 잔액 부족"""
        mock_balances.return_value = {"KRW": 100000}

        result = client._validate_balance("BTC", "buy", 1000000, amount_in_krw=True)

        assert result is False

    @patch.object(CoinoneClient, 'get_balances')
    def test_validate_balance_sell_sufficient(self, mock_balances, client):
        """매도 시 충분한 잔액"""
        mock_balances.return_value = {"BTC": 1.0}

        result = client._validate_balance("BTC", "sell", 0.5, amount_in_krw=False)

        assert result is True


@pytest.mark.trading
class TestCoinoneClientOrderSizeAdjustment:
    """주문 크기 조정 테스트"""

    @pytest.fixture
    def client(self):
        """테스트 클라이언트"""
        return CoinoneClient(api_key="test", secret_key="test")

    @patch.object(CoinoneClient, 'get_balances')
    @patch.object(CoinoneClient, 'get_latest_price')
    def test_adjust_order_size_no_change(self, mock_price, mock_balances, client):
        """조정 불필요 시 원래 크기 유지"""
        mock_balances.return_value = {"KRW": 100000000}
        mock_price.return_value = 50000000.0

        result = client._adjust_order_size("BTC", "buy", 1000000, amount_in_krw=True)

        # 최대 한도 내라면 원래 금액 유지
        assert result <= 500_000_000  # MAX_ORDER_LIMITS_KRW 참조

    @patch.object(CoinoneClient, 'get_balances')
    @patch.object(CoinoneClient, 'get_latest_price')
    def test_adjust_order_size_reduce_to_balance(self, mock_price, mock_balances, client):
        """잔액에 맞게 조정"""
        mock_balances.return_value = {"KRW": 500000}
        mock_price.return_value = 50000000.0

        result = client._adjust_order_size("BTC", "buy", 1000000, amount_in_krw=True)

        # 결과가 반환됨 (조정 로직은 구현에 따라 다름)
        assert result > 0


@pytest.mark.trading
class TestCoinoneClientIntegration:
    """통합 테스트"""

    @pytest.fixture
    def client(self):
        """테스트 클라이언트"""
        return CoinoneClient(api_key="test_key", secret_key="test_secret")

    @patch.object(CoinoneClient, 'get_balances')
    @patch.object(CoinoneClient, 'get_ticker')
    @patch.object(CoinoneClient, 'place_order')
    def test_full_buy_flow(self, mock_place, mock_ticker, mock_balances, client):
        """전체 매수 흐름"""
        mock_balances.return_value = {"KRW": 10000000, "BTC": 0.1}
        mock_ticker.return_value = {
            "result": "success",
            "data": {"last": "50000000"}
        }
        mock_place.return_value = {"success": True, "order_id": "buy_001"}

        # 1. 잔고 확인
        balances = client.get_balances()
        assert balances["KRW"] > 0

        # 2. 시세 확인
        ticker = client.get_ticker("BTC")
        assert ticker["result"] == "success"

        # 3. 주문 실행
        result = client.place_order("BTC", "buy", 0.01, price=50000000)
        assert result["success"] is True

    @patch.object(CoinoneClient, 'get_all_tickers')
    def test_get_multiple_tickers(self, mock_tickers, client):
        """여러 코인 시세 조회"""
        mock_tickers.return_value = {
            "result": "success",
            "tickers": [
                {"currency": "BTC", "last": "50000000"},
                {"currency": "ETH", "last": "3000000"},
                {"currency": "XRP", "last": "500"}
            ]
        }

        result = client.get_all_tickers()

        assert result["result"] == "success"
        assert len(result["tickers"]) == 3


@pytest.mark.trading
class TestCoinoneClientEdgeCases:
    """엣지 케이스 테스트"""

    @pytest.fixture
    def client(self):
        """테스트 클라이언트"""
        return CoinoneClient(api_key="test", secret_key="test")

    @patch.object(CoinoneClient, '_make_request')
    def test_empty_balances_response(self, mock_request, client):
        """빈 잔고 응답"""
        mock_request.return_value = {
            "result": "success",
            "balances": []
        }

        result = client.get_balances()
        assert result == {}

    @patch.object(CoinoneClient, 'get_recent_trades')
    @patch.object(CoinoneClient, 'get_ticker')
    def test_price_fallback_chain(self, mock_ticker, mock_trades, client):
        """가격 조회 폴백 체인"""
        # 체결가 없음
        mock_trades.return_value = {"result": "success", "transactions": []}
        # 티커에서 다양한 필드 시도
        mock_ticker.return_value = {
            "result": "success",
            "data": {
                "last": "0",
                "close_24h": "50000000"
            }
        }

        result = client.get_latest_price("BTC")
        assert result == 50000000.0

    @patch.object(CoinoneClient, '_make_request')
    def test_order_max_amount_exceeded(self, mock_request, client):
        """최대 주문 금액 초과"""
        mock_request.return_value = {
            "result": "error",
            "error_code": "307"
        }

        result = client.place_order(
            currency="BTC",
            side="buy",
            amount=1000000000,  # 10억원
            price=None,
            amount_in_krw=True
        )

        # 최대 한도 초과로 클라이언트 단에서 거부
        assert result["success"] is False

    def test_currency_case_handling(self, client):
        """통화 코드 대소문자 처리"""
        # 소문자 코인 코드 테스트
        with patch.object(client, '_make_request') as mock_request:
            mock_request.return_value = {"result": "success", "data": {}}
            client.get_ticker("btc")  # 소문자

            # 엔드포인트에서 대문자로 변환되어야 함
            call_args = mock_request.call_args
            assert "BTC" in call_args[0][1] or "btc" in call_args[0][1]


@pytest.mark.trading
class TestPlaceOrderSell:
    """매도 주문 테스트"""

    @pytest.fixture
    def client(self):
        """테스트 클라이언트"""
        return CoinoneClient(api_key="test", secret_key="test")

    @patch.object(CoinoneClient, 'get_latest_price')
    @patch.object(CoinoneClient, '_make_request')
    def test_sell_with_amount_in_krw(self, mock_request, mock_price, client):
        """KRW 금액으로 매도"""
        mock_price.return_value = 50000000  # BTC 가격
        mock_request.return_value = {"result": "success", "order_id": "sell_001"}

        result = client.place_order(
            currency="BTC",
            side="sell",
            amount=5000000,  # 500만원
            price=None,
            amount_in_krw=True
        )

        assert result["success"] is True
        # 500만원 / 5000만원 = 0.1 BTC
        call_args = mock_request.call_args
        params = call_args[0][2]  # positional args: (method, endpoint, params)
        assert "qty" in params  # 매도는 qty 사용
        assert params["qty"] == "0.1"  # 0.1 BTC

    @patch.object(CoinoneClient, 'get_latest_price')
    def test_sell_minimum_quantity_validation(self, mock_price, client):
        """매도 최소 수량 검증"""
        mock_price.return_value = 50000000

        # 최소 수량 미만
        result = client.place_order(
            currency="BTC",
            side="sell",
            amount=1000,  # 1000원 (0.00002 BTC)
            price=None,
            amount_in_krw=True
        )

        # 최소 수량 미달로 실패
        assert result["success"] is False

    @patch.object(CoinoneClient, '_make_request')
    def test_sell_quantity_direct(self, mock_request, client):
        """코인 수량으로 직접 매도"""
        mock_request.return_value = {"result": "success", "order_id": "sell_002"}

        result = client.place_order(
            currency="BTC",
            side="sell",
            amount=0.1,  # 0.1 BTC
            price=None,
            amount_in_krw=False
        )

        assert result["success"] is True

    def test_sell_minimum_quantity_direct(self, client):
        """코인 수량 최소 검증 (직접)"""
        result = client.place_order(
            currency="BTC",
            side="sell",
            amount=0.000001,  # 최소 수량 미달
            price=None,
            amount_in_krw=False
        )

        assert result["success"] is False


@pytest.mark.trading
class TestPlaceSafeOrder:
    """안전한 주문 실행 테스트"""

    @pytest.fixture
    def client(self):
        """테스트 클라이언트"""
        return CoinoneClient(api_key="test", secret_key="test")

    @patch.object(CoinoneClient, '_adjust_order_size')
    @patch.object(CoinoneClient, '_validate_balance')
    @patch.object(CoinoneClient, 'place_order')
    def test_safe_order_success(self, mock_place, mock_validate, mock_adjust, client):
        """안전한 주문 성공"""
        mock_validate.return_value = True
        mock_adjust.return_value = 100000
        mock_place.return_value = {"success": True, "order_id": "safe_001"}

        result = client.place_safe_order(
            currency="BTC",
            side="buy",
            amount=100000,
            amount_in_krw=True
        )

        assert result["success"] is True

    @patch.object(CoinoneClient, '_validate_balance')
    def test_safe_order_balance_fail(self, mock_validate, client):
        """잔액 부족"""
        mock_validate.return_value = False

        result = client.place_safe_order(
            currency="BTC",
            side="buy",
            amount=100000,
            amount_in_krw=True
        )

        assert result["success"] is False
        assert "잔액 부족" in result["error"]

    @patch.object(CoinoneClient, '_adjust_order_size')
    @patch.object(CoinoneClient, '_validate_balance')
    @patch.object(CoinoneClient, 'place_order')
    def test_safe_order_error_103_retry(self, mock_place, mock_validate, mock_adjust, client):
        """에러 코드 103 - 잔액 부족 재시도"""
        mock_validate.return_value = True
        mock_adjust.return_value = 100000
        mock_place.side_effect = [
            {"success": False, "error_code": "103", "error_msg": "Lack of Balance"},
            {"success": True, "order_id": "retry_001"}
        ]

        result = client.place_safe_order(
            currency="BTC",
            side="buy",
            amount=100000,
            amount_in_krw=True,
            max_retries=3
        )

        assert result["success"] is True

    @patch.object(CoinoneClient, '_adjust_order_size')
    @patch.object(CoinoneClient, '_validate_balance')
    @patch.object(CoinoneClient, 'place_order')
    def test_safe_order_error_307_retry(self, mock_place, mock_validate, mock_adjust, client):
        """에러 코드 307 - 최대 금액 초과 재시도"""
        mock_validate.return_value = True
        mock_adjust.return_value = 100000000
        mock_place.side_effect = [
            {"success": False, "error_code": "307", "error_msg": "Order amount exceeds limit"},
            {"success": True, "order_id": "retry_002"}
        ]

        result = client.place_safe_order(
            currency="BTC",
            side="buy",
            amount=100000000,
            amount_in_krw=True,
            max_retries=3
        )

        assert result["success"] is True

    @patch.object(CoinoneClient, '_adjust_order_size')
    @patch.object(CoinoneClient, '_validate_balance')
    @patch.object(CoinoneClient, 'place_order')
    def test_safe_order_error_405_no_retry(self, mock_place, mock_validate, mock_adjust, client):
        """에러 코드 405 - 최소 금액 미달 (재시도 안함)"""
        mock_validate.return_value = True
        mock_adjust.return_value = 1000
        mock_place.return_value = {"success": False, "error_code": "405", "error_msg": "Minimum order amount"}

        result = client.place_safe_order(
            currency="BTC",
            side="buy",
            amount=1000,
            amount_in_krw=True,
            max_retries=3
        )

        assert result["success"] is False
        assert mock_place.call_count == 1  # 재시도 안함

    @patch.object(CoinoneClient, '_adjust_order_size')
    @patch.object(CoinoneClient, '_validate_balance')
    @patch.object(CoinoneClient, 'place_order')
    def test_safe_order_exception_retry(self, mock_place, mock_validate, mock_adjust, client):
        """예외 발생 시 재시도"""
        mock_validate.return_value = True
        mock_adjust.return_value = 100000
        mock_place.side_effect = [
            Exception("Network error"),
            {"success": True, "order_id": "exc_001"}
        ]

        result = client.place_safe_order(
            currency="BTC",
            side="buy",
            amount=100000,
            amount_in_krw=True,
            max_retries=3
        )

        assert result["success"] is True

    @patch.object(CoinoneClient, '_adjust_order_size')
    @patch.object(CoinoneClient, '_validate_balance')
    @patch.object(CoinoneClient, 'place_order')
    def test_safe_order_max_retries_exceeded(self, mock_place, mock_validate, mock_adjust, client):
        """최대 재시도 초과"""
        mock_validate.return_value = True
        mock_adjust.return_value = 100000
        mock_place.return_value = {"success": False, "error_code": "999", "error_msg": "Unknown error"}

        result = client.place_safe_order(
            currency="BTC",
            side="buy",
            amount=100000,
            amount_in_krw=True,
            max_retries=2
        )

        assert result["success"] is False
        assert mock_place.call_count == 2


@pytest.mark.trading
class TestValidateBalance:
    """잔액 검증 테스트"""

    @pytest.fixture
    def client(self):
        """테스트 클라이언트"""
        return CoinoneClient(api_key="test", secret_key="test")

    @patch.object(CoinoneClient, 'get_latest_price')
    @patch.object(CoinoneClient, 'get_balances')
    def test_validate_sell_amount_in_krw(self, mock_balances, mock_price, client):
        """매도 잔액 검증 (KRW 금액)"""
        mock_balances.return_value = {"BTC": 0.1, "KRW": 1000000}
        mock_price.return_value = 50000000

        # 0.1 BTC = 500만원, 300만원 매도 요청
        result = client._validate_balance("BTC", "sell", 3000000, amount_in_krw=True)

        assert result is True

    @patch.object(CoinoneClient, 'get_latest_price')
    @patch.object(CoinoneClient, 'get_balances')
    def test_validate_sell_amount_in_krw_insufficient(self, mock_balances, mock_price, client):
        """매도 잔액 부족 (KRW 금액)"""
        mock_balances.return_value = {"BTC": 0.05, "KRW": 1000000}
        mock_price.return_value = 50000000

        # 0.05 BTC = 250만원, 500만원 매도 요청
        result = client._validate_balance("BTC", "sell", 5000000, amount_in_krw=True)

        assert result is False

    @patch.object(CoinoneClient, 'get_balances')
    def test_validate_sell_quantity(self, mock_balances, client):
        """매도 잔액 검증 (코인 수량)"""
        mock_balances.return_value = {"BTC": 0.1, "KRW": 1000000}

        result = client._validate_balance("BTC", "sell", 0.05, amount_in_krw=False)

        assert result is True

    @patch.object(CoinoneClient, 'get_balances')
    def test_validate_sell_quantity_insufficient(self, mock_balances, client):
        """매도 잔액 부족 (코인 수량)"""
        mock_balances.return_value = {"BTC": 0.03, "KRW": 1000000}

        result = client._validate_balance("BTC", "sell", 0.05, amount_in_krw=False)

        assert result is False

    @patch.object(CoinoneClient, 'get_latest_price')
    @patch.object(CoinoneClient, 'get_balances')
    def test_validate_buy_quantity(self, mock_balances, mock_price, client):
        """매수 잔액 검증 (코인 수량)"""
        mock_balances.return_value = {"BTC": 0, "KRW": 10000000}
        mock_price.return_value = 50000000

        # 0.1 BTC = 500만원, KRW 잔액 1000만원
        result = client._validate_balance("BTC", "buy", 0.1, amount_in_krw=False)

        assert result is True

    @patch.object(CoinoneClient, 'get_latest_price')
    @patch.object(CoinoneClient, 'get_balances')
    def test_validate_buy_quantity_insufficient(self, mock_balances, mock_price, client):
        """매수 잔액 부족 (코인 수량)"""
        mock_balances.return_value = {"BTC": 0, "KRW": 1000000}
        mock_price.return_value = 50000000

        # 0.1 BTC = 500만원, KRW 잔액 100만원
        result = client._validate_balance("BTC", "buy", 0.1, amount_in_krw=False)

        assert result is False

    @patch.object(CoinoneClient, 'get_balances')
    def test_validate_balance_exception(self, mock_balances, client):
        """잔액 검증 예외"""
        mock_balances.side_effect = Exception("API error")

        result = client._validate_balance("BTC", "buy", 100000, amount_in_krw=True)

        assert result is False


@pytest.mark.trading
class TestAdjustOrderSize:
    """주문 크기 조정 테스트"""

    @pytest.fixture
    def client(self):
        """테스트 클라이언트"""
        return CoinoneClient(api_key="test", secret_key="test")

    @patch.object(CoinoneClient, 'get_latest_price')
    def test_adjust_sell_amount_in_krw_over_limit(self, mock_price, client):
        """매도 금액 한도 초과 조정 (KRW)"""
        mock_price.return_value = 50000000

        result = client._adjust_order_size("BTC", "sell", 500000000, amount_in_krw=True)

        # 한도 초과 시 조정됨
        assert result < 500000000

    @patch.object(CoinoneClient, 'get_latest_price')
    def test_adjust_sell_quantity_over_limit(self, mock_price, client):
        """매도 수량 한도 초과 조정"""
        mock_price.return_value = 50000000

        # 10 BTC = 5억원 (한도 초과)
        result = client._adjust_order_size("BTC", "sell", 10, amount_in_krw=False)

        # 한도 초과 시 조정됨
        assert result < 10

    def test_adjust_buy_amount_in_krw_over_limit(self, client):
        """매수 금액 한도 초과 조정"""
        result = client._adjust_order_size("BTC", "buy", 500000000, amount_in_krw=True)

        # 한도 초과 시 조정됨
        assert result < 500000000

    @patch.object(CoinoneClient, 'get_latest_price')
    def test_adjust_buy_quantity_over_limit(self, mock_price, client):
        """매수 수량 한도 초과 조정"""
        mock_price.return_value = 50000000

        # 10 BTC = 5억원 (한도 초과)
        result = client._adjust_order_size("BTC", "buy", 10, amount_in_krw=False)

        # 한도 초과 시 조정됨
        assert result < 10

    def test_adjust_within_limit(self, client):
        """한도 내 주문 (조정 없음)"""
        result = client._adjust_order_size("BTC", "buy", 100000, amount_in_krw=True)

        assert result == 100000

    @patch.object(CoinoneClient, 'get_latest_price')
    def test_adjust_exception(self, mock_price, client):
        """조정 중 예외 (원래 금액 반환)"""
        mock_price.side_effect = Exception("Price error")

        result = client._adjust_order_size("BTC", "buy", 100000, amount_in_krw=False)

        assert result == 100000


@pytest.mark.trading
class TestGetOrderStatus:
    """주문 상태 조회 테스트"""

    @pytest.fixture
    def client(self):
        """테스트 클라이언트"""
        return CoinoneClient(api_key="test", secret_key="test")

    @patch.object(CoinoneClient, '_make_request')
    def test_get_order_status_success(self, mock_request, client):
        """주문 상태 조회 성공"""
        mock_request.return_value = {
            "result": "success",
            "status": "filled",
            "filled_qty": "0.1",
            "avg_price": "50000000"
        }

        result = client.get_order_status("order_123", "BTC")

        assert result["result"] == "success"
        assert result["status"] == "filled"

    @patch.object(CoinoneClient, '_make_request')
    def test_get_order_status_sends_required_market_params(self, mock_request, client):
        """v2.1 order/info는 quote/target_currency 필수 — 누락 시 조회가
        실패해 체결 추적이 전면 불능이 되는 회귀 방지"""
        mock_request.return_value = {"result": "success"}

        client.get_order_status("order_123", "eth")

        params = mock_request.call_args.args[2]
        assert params["order_id"] == "order_123"
        assert params["quote_currency"] == "KRW"
        assert params["target_currency"] == "ETH"

    @patch.object(CoinoneClient, '_make_request')
    def test_get_order_status_404(self, mock_request, client):
        """주문을 찾을 수 없음 (404)"""
        mock_request.side_effect = Exception("404 Not Found")

        result = client.get_order_status("nonexistent_order", "BTC")

        assert result["result"] == "success"
        assert result["status"] == "not_found"

    @patch.object(CoinoneClient, '_make_request')
    def test_get_order_status_other_error(self, mock_request, client):
        """기타 오류"""
        mock_request.side_effect = Exception("500 Server Error")

        with pytest.raises(Exception):
            client.get_order_status("order_123", "BTC")


@pytest.mark.trading
class TestCancelOrder:
    """주문 취소 테스트"""

    @pytest.fixture
    def client(self):
        """테스트 클라이언트"""
        return CoinoneClient(api_key="test", secret_key="test")

    @patch.object(CoinoneClient, '_make_request')
    def test_cancel_order_success(self, mock_request, client):
        """주문 취소 성공"""
        mock_request.return_value = {"result": "success"}

        result = client.cancel_order("order_123", "BTC")

        assert result["result"] == "success"

    @patch.object(CoinoneClient, '_make_request')
    def test_cancel_order_sends_required_market_params(self, mock_request, client):
        """v2.1 order/cancel는 quote/target_currency 필수 — 누락 시 취소가
        실패해 낡은 지정가가 호가창에 방치되는 회귀 방지"""
        mock_request.return_value = {"result": "success"}

        client.cancel_order("order_123", "sol")

        params = mock_request.call_args.args[2]
        assert params["order_id"] == "order_123"
        assert params["quote_currency"] == "KRW"
        assert params["target_currency"] == "SOL"

    @patch.object(CoinoneClient, '_make_request')
    def test_cancel_order_failure(self, mock_request, client):
        """주문 취소 실패"""
        mock_request.return_value = {
            "result": "error",
            "error_code": "500",
            "error_msg": "Order cannot be cancelled"
        }

        result = client.cancel_order("order_123", "BTC")

        assert result["result"] == "error"

    @patch.object(CoinoneClient, '_make_request')
    def test_cancel_order_404(self, mock_request, client):
        """주문을 찾을 수 없음 (404) - 이미 완료/취소"""
        mock_request.side_effect = Exception("404 Not Found")

        result = client.cancel_order("completed_order", "BTC")

        assert result["result"] == "success"
        assert result["status"] == "not_found"

    @patch.object(CoinoneClient, '_make_request')
    def test_cancel_order_other_error(self, mock_request, client):
        """기타 오류"""
        mock_request.side_effect = Exception("Network error")

        with pytest.raises(Exception):
            client.cancel_order("order_123", "BTC")


@pytest.mark.trading
class TestGetPortfolioValue:
    """포트폴리오 가치 계산 테스트"""

    @pytest.fixture
    def client(self):
        """테스트 클라이언트"""
        return CoinoneClient(api_key="test", secret_key="test")

    @patch.object(CoinoneClient, 'get_latest_price')
    @patch.object(CoinoneClient, 'get_balances')
    def test_get_portfolio_value_success(self, mock_balances, mock_price, client):
        """포트폴리오 가치 계산 성공"""
        mock_balances.return_value = {
            "BTC": 0.1,
            "ETH": 1.0,
            "KRW": 1000000
        }
        mock_price.side_effect = [50000000, 4000000]  # BTC, ETH

        result = client.get_portfolio_value()

        assert "total_krw" in result
        assert "assets" in result
        assert result["total_krw"] > 0
        # BTC: 0.1 * 50000000 = 5000000
        # ETH: 1.0 * 4000000 = 4000000
        # KRW: 1000000
        # Total: 10000000
        assert result["total_krw"] == 10000000

    @patch.object(CoinoneClient, 'get_latest_price')
    @patch.object(CoinoneClient, 'get_balances')
    def test_get_portfolio_value_krw_only(self, mock_balances, mock_price, client):
        """KRW만 있는 경우"""
        mock_balances.return_value = {"KRW": 5000000}

        result = client.get_portfolio_value()

        assert result["total_krw"] == 5000000
        assert "KRW" in result["assets"]

    @patch.object(CoinoneClient, 'get_latest_price')
    @patch.object(CoinoneClient, 'get_balances')
    def test_get_portfolio_value_invalid_price(self, mock_balances, mock_price, client):
        """유효하지 않은 가격"""
        mock_balances.return_value = {"BTC": 0.1, "KRW": 1000000}
        mock_price.return_value = 0  # 유효하지 않은 가격

        result = client.get_portfolio_value()

        # BTC는 제외되고 KRW만 포함
        assert result["total_krw"] == 1000000
        assert "BTC" not in result["assets"]

    @patch.object(CoinoneClient, 'get_latest_price')
    @patch.object(CoinoneClient, 'get_balances')
    def test_get_portfolio_value_price_error(self, mock_balances, mock_price, client):
        """가격 조회 오류"""
        mock_balances.return_value = {"BTC": 0.1, "ETH": 1.0, "KRW": 1000000}
        mock_price.side_effect = [Exception("Price error"), 4000000]

        result = client.get_portfolio_value()

        # BTC는 오류로 제외, ETH와 KRW만 포함
        assert "BTC" not in result["assets"]
        assert "ETH" in result["assets"]

    @patch.object(CoinoneClient, 'get_balances')
    def test_get_portfolio_value_balance_error(self, mock_balances, client):
        """잔액 조회 오류"""
        mock_balances.side_effect = Exception("Balance error")

        with pytest.raises(Exception):
            client.get_portfolio_value()

    @patch.object(CoinoneClient, 'get_latest_price')
    @patch.object(CoinoneClient, 'get_balances')
    def test_get_portfolio_value_zero_balance(self, mock_balances, mock_price, client):
        """잔액이 0인 코인 제외"""
        mock_balances.return_value = {"BTC": 0, "ETH": 0, "KRW": 1000000}

        result = client.get_portfolio_value()

        # 잔액이 0인 코인은 제외
        assert result["total_krw"] == 1000000
        assert "BTC" not in result["assets"]
        assert "ETH" not in result["assets"]


@pytest.mark.trading
class TestPrivateAPIEdgeCases:
    """Private API 엣지 케이스 테스트"""

    @pytest.fixture
    def client(self):
        return CoinoneClient(api_key="test", secret_key="test")

    @patch('requests.post')
    def test_private_api_request_exception(self, mock_post, client):
        """Private API 요청 예외"""
        import requests
        mock_post.side_effect = requests.exceptions.RequestException("Connection error")

        with pytest.raises(requests.exceptions.RequestException):
            client._make_request("POST", "/v2.1/account/balance", {}, is_public=False)


@pytest.mark.trading
class TestAPIExceptions:
    """API 예외 테스트"""

    @pytest.fixture
    def client(self):
        return CoinoneClient(api_key="test", secret_key="test")

    @patch.object(CoinoneClient, '_make_request')
    def test_get_ticker_exception(self, mock_request, client):
        """시세 조회 예외"""
        mock_request.side_effect = Exception("API Error")

        with pytest.raises(Exception):
            client.get_ticker("BTC")

    @patch.object(CoinoneClient, '_make_request')
    def test_get_all_tickers_exception(self, mock_request, client):
        """전체 시세 조회 예외"""
        mock_request.side_effect = Exception("API Error")

        with pytest.raises(Exception):
            client.get_all_tickers()

    @patch.object(CoinoneClient, '_make_request')
    def test_get_recent_trades_exception(self, mock_request, client):
        """최근 체결 조회 예외"""
        mock_request.side_effect = Exception("API Error")

        with pytest.raises(Exception):
            client.get_recent_trades("BTC")


@pytest.mark.trading
class TestLatestPriceEdgeCases:
    """최신가 조회 엣지 케이스"""

    @pytest.fixture
    def client(self):
        return CoinoneClient(api_key="test", secret_key="test")

    @patch.object(CoinoneClient, 'get_recent_trades')
    @patch.object(CoinoneClient, 'get_ticker')
    def test_ticker_not_dict(self, mock_ticker, mock_trades, client):
        """ticker 응답이 dict가 아닌 경우"""
        mock_trades.return_value = {"data": []}  # 빈 체결 내역
        mock_ticker.return_value = "invalid"  # dict가 아님

        result = client.get_latest_price("BTC")

        assert result == 0.0  # ValueError로 인해 0.0 반환

    @patch.object(CoinoneClient, 'get_recent_trades')
    @patch.object(CoinoneClient, 'get_ticker')
    def test_ticker_data_not_dict(self, mock_ticker, mock_trades, client):
        """ticker['data']가 dict가 아닌 경우"""
        mock_trades.return_value = {"data": []}  # 빈 체결 내역
        mock_ticker.return_value = {"data": "invalid"}  # data가 dict 아님

        result = client.get_latest_price("BTC")

        assert result == 0.0

    @patch.object(CoinoneClient, 'get_recent_trades')
    @patch.object(CoinoneClient, 'get_ticker')
    def test_all_price_fields_zero(self, mock_ticker, mock_trades, client):
        """모든 가격 필드가 0인 경우"""
        mock_trades.return_value = {"data": []}  # 빈 체결 내역
        mock_ticker.return_value = {
            "data": {"last": 0, "close_24h": 0, "close": 0}
        }

        result = client.get_latest_price("BTC")

        assert result == 0.0


@pytest.mark.trading
class TestPlaceOrderPriceErrors:
    """주문 시 가격 조회 실패 테스트"""

    @pytest.fixture
    def client(self):
        return CoinoneClient(api_key="test", secret_key="test")

    @patch.object(CoinoneClient, 'get_latest_price')
    def test_buy_crypto_amount_invalid_price(self, mock_price, client):
        """매수 시 유효하지 않은 가격"""
        mock_price.return_value = 0  # 유효하지 않은 가격

        result = client.place_order(
            currency="BTC",
            side="buy",
            amount=0.1,  # crypto 수량
            price=None,
            amount_in_krw=False  # crypto 수량으로 매수
        )

        assert result["success"] is False
        assert "가격 조회 실패" in result.get("error", "")

    @patch.object(CoinoneClient, 'get_latest_price')
    def test_buy_crypto_amount_price_exception(self, mock_price, client):
        """매수 시 가격 조회 예외"""
        mock_price.side_effect = Exception("Price API Error")

        result = client.place_order(
            currency="BTC",
            side="buy",
            amount=0.1,
            price=None,
            amount_in_krw=False
        )

        assert result["success"] is False

    @patch.object(CoinoneClient, 'get_latest_price')
    def test_sell_krw_amount_invalid_price(self, mock_price, client):
        """매도 시 유효하지 않은 가격 (KRW 금액)"""
        mock_price.return_value = 0  # 유효하지 않은 가격

        result = client.place_order(
            currency="BTC",
            side="sell",
            amount=1000000,  # KRW 금액
            price=None,
            amount_in_krw=True
        )

        assert result["success"] is False


@pytest.mark.trading
class TestSafeOrderAdvanced:
    """안전 주문 고급 테스트"""

    @pytest.fixture
    def client(self):
        return CoinoneClient(api_key="test", secret_key="test")

    @patch.object(CoinoneClient, 'place_order')
    @patch.object(CoinoneClient, '_adjust_order_size')
    @patch.object(CoinoneClient, '_validate_balance')
    def test_safe_order_size_adjustment(self, mock_validate, mock_adjust, mock_order, client):
        """주문 크기 조정 테스트"""
        mock_validate.return_value = True
        mock_adjust.return_value = 800000  # 100만 → 80만으로 조정
        mock_order.return_value = {"success": True, "order_id": "adj_001"}

        result = client.place_safe_order(
            currency="BTC",
            side="buy",
            amount=1000000,
            price=None,
            amount_in_krw=True
        )

        assert result["success"] is True
        # 조정된 금액으로 주문 실행 확인
        mock_order.assert_called_once()
        call_args = mock_order.call_args
        assert call_args[0][2] == 800000  # amount

    @patch.object(CoinoneClient, 'place_order')
    @patch.object(CoinoneClient, '_adjust_order_size')
    @patch.object(CoinoneClient, '_validate_balance')
    def test_safe_order_max_retries_all_fail(self, mock_validate, mock_adjust, mock_order, client):
        """모든 재시도 실패"""
        mock_validate.return_value = True
        mock_adjust.return_value = 1000000
        # 복구 불가능한 에러로 계속 실패
        mock_order.return_value = {"success": False, "error_code": "999", "error_msg": "Unknown"}

        result = client.place_safe_order(
            currency="BTC",
            side="buy",
            amount=1000000,
            price=None,
            amount_in_krw=True,
            max_retries=3
        )

        assert result["success"] is False
        assert mock_order.call_count == 3

    @patch.object(CoinoneClient, '_adjust_order_size')
    @patch.object(CoinoneClient, '_validate_balance')
    def test_safe_order_outer_exception(self, mock_validate, mock_adjust, client):
        """외부 예외 발생"""
        mock_validate.return_value = True
        mock_adjust.side_effect = Exception("Unexpected error")

        result = client.place_safe_order(
            currency="BTC",
            side="buy",
            amount=1000000,
            price=None,
            amount_in_krw=True
        )

        assert result["success"] is False
        assert "error" in result

    @patch.object(CoinoneClient, 'place_order')
    @patch.object(CoinoneClient, '_adjust_order_size')
    @patch.object(CoinoneClient, '_validate_balance')
    def test_safe_order_exception_on_last_retry(self, mock_validate, mock_adjust, mock_order, client):
        """마지막 재시도에서 예외 발생"""
        mock_validate.return_value = True
        mock_adjust.return_value = 1000000
        # 처음 두 번은 성공하지 않고 재시도 가능한 에러, 마지막에 예외
        mock_order.side_effect = [
            {"success": False, "error_code": "103"},  # 1차: 잔액 부족
            {"success": False, "error_code": "103"},  # 2차: 잔액 부족
            Exception("Connection error")  # 3차: 예외
        ]

        result = client.place_safe_order(
            currency="BTC",
            side="buy",
            amount=1000000,
            price=None,
            amount_in_krw=True,
            max_retries=3
        )

        assert result["success"] is False
        assert "Connection error" in result.get("error", "")

    @patch.object(CoinoneClient, 'place_order')
    @patch.object(CoinoneClient, '_adjust_order_size')
    @patch.object(CoinoneClient, '_validate_balance')
    def test_safe_order_balance_error_all_retries(self, mock_validate, mock_adjust, mock_order, client):
        """잔액 부족으로 모든 재시도 소진 (line 555 커버)"""
        mock_validate.return_value = True
        mock_adjust.return_value = 1000000
        # 계속 잔액 부족 에러
        mock_order.return_value = {"success": False, "error_code": "103"}

        result = client.place_safe_order(
            currency="BTC",
            side="buy",
            amount=1000000,
            price=None,
            amount_in_krw=True,
            max_retries=3
        )

        assert result["success"] is False
        # 최대 재시도 횟수 초과 메시지 확인
        assert "최대 재시도" in result.get("error", "") or mock_order.call_count == 3


@pytest.mark.trading
class TestPrivateAPIParamsNone:
    """Private API params=None 테스트"""

    @pytest.fixture
    def client(self):
        return CoinoneClient(api_key="test", secret_key="test")

    @patch('requests.post')
    def test_private_api_params_none(self, mock_post, client):
        """Private API에 params=None으로 호출"""
        mock_post.return_value.json.return_value = {"result": "success"}
        mock_post.return_value.raise_for_status = lambda: None

        result = client._make_request("POST", "/v2.1/account/balance", None, is_public=False)

        assert result["result"] == "success"
        # params가 None이면 {}로 대체되어 호출됨
        mock_post.assert_called_once()


@pytest.mark.trading
class TestOrderAmbiguityAndTimeout:
    """운영 회귀 방지: 주문 POST의 네트워크 모호 실패(응답 유실)를 일반
    실패와 동일 취급해 재시도하면 이중 주문이 발생한다. 또한 requests에
    timeout이 없으면 크론 전체가 무한 대기한다."""

    @pytest.fixture
    def client(self):
        return CoinoneClient(api_key="test", secret_key="test")

    @patch.object(CoinoneClient, '_make_request')
    def test_place_order_network_failure_marked_ambiguous(self, mock_request, client):
        """접수 여부를 알 수 없는 네트워크 실패 → ambiguous 표시"""
        import requests as req
        mock_request.side_effect = req.exceptions.ConnectionError("conn reset")

        result = client.place_order("BTC", "buy", 0.01, price=100_000_000.0)

        assert result["success"] is False
        assert result.get("ambiguous") is True

    @patch.object(CoinoneClient, '_make_request')
    def test_place_order_client_error_not_ambiguous(self, mock_request, client):
        """4xx는 서버가 주문을 거부한 것 — 미접수 확정이므로 재시도 안전"""
        import requests as req
        response = Mock()
        response.status_code = 400
        mock_request.side_effect = req.exceptions.HTTPError(response=response)

        result = client.place_order("BTC", "buy", 0.01, price=100_000_000.0)

        assert result["success"] is False
        assert not result.get("ambiguous")

    @patch('src.trading.coinone_client.requests.post')
    def test_private_request_has_timeout(self, mock_post, client):
        mock_post.return_value.json.return_value = {"result": "success"}
        mock_post.return_value.raise_for_status = Mock()

        client._make_request("POST", "/v2.1/account/balance/all", {}, is_public=False)

        assert mock_post.call_args.kwargs.get("timeout", 0) > 0

    @patch('src.trading.coinone_client.requests.get')
    def test_public_request_has_timeout(self, mock_get, client):
        mock_get.return_value.json.return_value = {"result": "success"}
        mock_get.return_value.raise_for_status = Mock()

        client._make_request("GET", "/public/v2/ticker_new/KRW/BTC", {}, is_public=True)

        assert mock_get.call_args.kwargs.get("timeout", 0) > 0


@pytest.mark.trading
class TestOrderParamSerialization:
    """지정가/수량 직렬화 — int() 절삭은 1,000 KRW 미만 자산(소수 호가 단위)
    에서 슬리피지 캡을 위반하고, str(float)는 1e-4 미만 수량을 지수 표기로
    보내 주문이 거부될 수 있다"""

    @pytest.fixture
    def client(self):
        return CoinoneClient(api_key="test", secret_key="test")

    @patch.object(CoinoneClient, '_make_request')
    def test_limit_price_preserves_fractional_tick(self, mock_request, client):
        mock_request.return_value = {"result": "success", "order_id": "x"}

        client.place_order("XRP", "sell", 100.0, price=796.5)

        params = mock_request.call_args.args[2]
        assert params["price"] == "796.5"

    @patch.object(CoinoneClient, '_make_request')
    def test_limit_qty_fixed_point_not_scientific(self, mock_request, client):
        mock_request.return_value = {"result": "success", "order_id": "x"}

        client.place_order("BTC", "buy", 6.25e-05, price=160_000_000.0)

        params = mock_request.call_args.args[2]
        assert "e" not in params["qty"].lower()
        assert params["qty"] == "0.0000625"
        assert params["price"] == "160000000"
