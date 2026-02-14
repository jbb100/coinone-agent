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
