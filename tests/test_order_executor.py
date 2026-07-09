"""src/execution/executor.py 테스트 — 지정가·재시도·TWAP 분할."""
from unittest.mock import MagicMock

import pytest

from src.execution.executor import OrderExecutor
from src.risk.guard import OrderRequest


def make_executor(price=100_000_000.0, **kw):
    coinone = MagicMock()
    coinone.get_latest_price.return_value = price
    coinone.place_order.return_value = {"success": True, "order_id": "oid-1"}
    defaults = dict(twap_slice_krw=5_000_000, max_retries=3, retry_wait=0)
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
