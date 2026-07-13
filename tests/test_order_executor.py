"""src/execution/executor.py 테스트 — 지정가·재시도·TWAP 분할."""
from unittest.mock import MagicMock

import pytest

from src.execution.executor import OrderExecutor
from src.risk.guard import OrderRequest


def make_executor(price=100_000_000.0, **kw):
    coinone = MagicMock()
    coinone.get_latest_price.return_value = price
    coinone.get_price_unit.return_value = 1000.0  # 기본 호가 단위 (테스트 가격과 정렬됨)
    coinone.place_order.return_value = {"success": True, "order_id": "oid-1"}
    coinone.get_order_status.return_value = {"order": {"status": "filled"}}
    defaults = dict(twap_slice_krw=5_000_000, max_retries=3, retry_wait=0,
                    fill_timeout=0, poll_interval=0)
    defaults.update(kw)
    return OrderExecutor(coinone, **defaults), coinone


def test_small_order_executes_once():
    ex, coinone = make_executor()
    report = ex.execute(OrderRequest("BTC", "buy", 1_000_000, "dca"))
    assert report.success and coinone.place_order.call_count == 1
    assert report.filled_krw == pytest.approx(1_000_000)


def test_buy_uses_limit_price_with_slippage_cap_and_qty():
    ex, coinone = make_executor(price=100_000_000.0)
    ex.execute(OrderRequest("BTC", "buy", 1_000_000, "dca"))
    kwargs = coinone.place_order.call_args.kwargs
    limit = 100_000_000.0 * 1.005  # 매수: 슬리피지 상한 +0.5%
    assert kwargs["currency"] == "BTC"
    assert kwargs["side"] == "buy"
    assert kwargs["price"] == pytest.approx(limit)
    assert kwargs["amount"] == pytest.approx(1_000_000 / limit)  # KRW → 수량 변환


def test_sell_limit_price_below_market():
    ex, coinone = make_executor(price=100_000_000.0)
    ex.execute(OrderRequest("BTC", "sell", 1_000_000, "rebalance"))
    assert coinone.place_order.call_args.kwargs["price"] == pytest.approx(
        100_000_000.0 * 0.995
    )


def test_large_order_split_into_twap_slices():
    ex, coinone = make_executor()
    report = ex.execute(OrderRequest("BTC", "buy", 12_000_000, "rebalance"))
    assert report.success
    assert coinone.place_order.call_count == 3  # 12M / 5M → 3 슬라이스 (4M씩)
    limit = 100_000_000.0 * 1.005
    qtys = [c.kwargs["amount"] for c in coinone.place_order.call_args_list]
    assert sum(qtys) * limit == pytest.approx(12_000_000)


def test_retry_on_exception_then_success():
    ex, coinone = make_executor()
    coinone.place_order.side_effect = [
        Exception("timeout"),
        {"success": True, "order_id": "oid-2"},
    ]
    report = ex.execute(OrderRequest("BTC", "buy", 1_000_000, "dca"))
    assert report.success and coinone.place_order.call_count == 2


def test_exhausted_retries_reports_failure():
    ex, coinone = make_executor(max_retries=2)
    coinone.place_order.side_effect = Exception("down")
    report = ex.execute(OrderRequest("BTC", "buy", 1_000_000, "dca"))
    assert not report.success and coinone.place_order.call_count == 2


def test_api_error_result_counts_as_failure():
    ex, coinone = make_executor(max_retries=1)
    coinone.place_order.return_value = {"success": False, "error_code": "113"}
    report = ex.execute(OrderRequest("BTC", "buy", 1_000_000, "dca"))
    assert not report.success


def test_partial_fill_reported_on_mid_slice_failure():
    """TWAP 도중 실패 시 체결된 금액이 filled_krw로 보고되어야 함"""
    ex, coinone = make_executor(max_retries=1)
    coinone.place_order.side_effect = [
        {"success": True, "order_id": "a"},
        {"success": False, "error_code": "500"},
    ]
    report = ex.execute(OrderRequest("BTC", "buy", 10_000_000, "rebalance"))
    assert not report.success
    assert report.filled_krw == pytest.approx(5_000_000)


class TestPriceUnitRounding:
    """운영 회귀 방지: 코인원 오류 310 — 지정가는 호가 단위에 맞춰야 함"""

    def test_buy_limit_floored_to_price_unit(self):
        # BTC 94,560,000 → 캡 95,032,800 → 단위 10,000원 → 95,030,000으로 내림
        ex, coinone = make_executor(price=94_560_000.0)
        coinone.get_price_unit.return_value = 10_000.0
        ex.execute(OrderRequest("BTC", "buy", 1_000_000, "rebalance"))
        kwargs = coinone.place_order.call_args.kwargs
        assert kwargs["price"] == pytest.approx(95_030_000.0)
        assert kwargs["price"] % 10_000 == 0
        # 수량은 반올림된 지정가 기준으로 계산
        assert kwargs["amount"] == pytest.approx(1_000_000 / 95_030_000.0)

    def test_sell_limit_ceiled_to_price_unit(self):
        # SOL 116,800 → 하한 116,216 → 단위 100원 → 116,300으로 올림
        ex, coinone = make_executor(price=116_800.0)
        coinone.get_price_unit.return_value = 100.0
        ex.execute(OrderRequest("SOL", "sell", 1_000_000, "rebalance"))
        kwargs = coinone.place_order.call_args.kwargs
        assert kwargs["price"] == pytest.approx(116_300.0)
        assert kwargs["price"] % 100 == 0


class TestCoinoneGetPriceUnit:
    """CoinoneClient.get_price_unit — Range Unit API 조회·캐시·폴백"""

    def make_client(self):
        from src.trading.coinone_client import CoinoneClient
        client = CoinoneClient(api_key="k", secret_key="s")
        return client

    def test_price_unit_from_api(self):
        from unittest.mock import patch
        client = self.make_client()
        api_response = {
            "result": "success",
            "range_price_units": [
                {"range_min": 100000, "next_range_min": 500000, "price_unit": 100},
                {"range_min": 1000000, "next_range_min": 5000000, "price_unit": 1000},
            ],
        }
        with patch.object(client, "_make_request", return_value=api_response):
            assert client.get_price_unit("SOL", 116_216.0) == 100
            assert client.get_price_unit("SOL", 2_625_059.0) == 1000

    def test_price_unit_cached_per_currency(self):
        from unittest.mock import patch
        client = self.make_client()
        api_response = {
            "result": "success",
            "range_price_units": [
                {"range_min": 0, "next_range_min": 10000000000, "price_unit": 100},
            ],
        }
        with patch.object(client, "_make_request", return_value=api_response) as mock_req:
            client.get_price_unit("SOL", 100_000.0)
            client.get_price_unit("SOL", 200_000.0)
            assert mock_req.call_count == 1  # 두 번째는 캐시

    def test_price_unit_static_fallback_on_api_failure(self):
        from unittest.mock import patch
        client = self.make_client()
        with patch.object(client, "_make_request", side_effect=Exception("down")):
            # 코인원 표준 호가 테이블 폴백
            assert client.get_price_unit("BTC", 94_560_000.0) == 10_000
            assert client.get_price_unit("ETH", 2_612_000.0) == 1_000
            assert client.get_price_unit("SOL", 116_800.0) == 100
            assert client.get_price_unit("XRP", 1_638.0) == 1


class TestFillConfirmation:
    """체결 확인 — 주문 접수(success) ≠ 체결. 미체결 잔량은 취소한다.

    ±0.5% 지정가는 급변동 장에서 미체결로 남을 수 있고, 방치하면 몇 시간
    뒤 낡은 판단으로 낸 주문이 뒤늦게 체결된다. 타임아웃 내 미체결분은
    취소하고 실제 체결분만 보고한다."""

    def make(self, statuses):
        ex, coinone = make_executor(fill_timeout=0, poll_interval=0)
        coinone.get_order_status.side_effect = statuses
        return ex, coinone

    def test_filled_immediately_no_cancel(self):
        ex, coinone = self.make([{"order": {"status": "filled"}}])
        report = ex.execute(OrderRequest("BTC", "buy", 1_000_000, "dca"))
        assert report.success
        assert report.filled_krw == pytest.approx(1_000_000)
        coinone.cancel_order.assert_not_called()

    def test_unfilled_after_timeout_canceled_zero_filled(self):
        live = {"order": {"status": "live", "remain_qty": "0.00995"}}
        # qty = 1M / (100M*1.005) ≈ 0.00995 → 전량 미체결
        ex, coinone = self.make([live, live])
        report = ex.execute(OrderRequest("BTC", "buy", 1_000_000, "dca"))
        coinone.cancel_order.assert_called_once()
        assert not report.success
        assert report.filled_krw == pytest.approx(0.0, abs=1_000)

    def test_partial_fill_on_timeout_reports_filled_portion(self):
        qty = 1_000_000 / (100_000_000.0 * 1.005)
        half_live = {"order": {"status": "live", "remain_qty": str(qty / 2)}}
        canceled = {"order": {"status": "canceled", "remain_qty": str(qty / 2)}}
        ex, coinone = self.make([half_live, canceled])
        report = ex.execute(OrderRequest("BTC", "buy", 1_000_000, "dca"))
        coinone.cancel_order.assert_called_once()
        assert not report.success
        assert report.filled_krw == pytest.approx(500_000, rel=0.01)

    def test_not_found_before_cancel_treated_as_filled(self):
        # 체결 완료된 주문은 조회에서 사라질 수 있음 (클라이언트가 not_found 반환)
        ex, coinone = self.make([{"result": "success", "status": "not_found"}])
        report = ex.execute(OrderRequest("BTC", "buy", 1_000_000, "dca"))
        assert report.success
        assert report.filled_krw == pytest.approx(1_000_000)
        coinone.cancel_order.assert_not_called()
