"""
AllocationArbiter + OpportunisticSeller (Phase 3) 테스트

- 클로백 면제: 최근 기회적 매수분은 리밸런싱 매도에서 제외
- 허용 밴드: 기회적 매수/매도가 목표 비중 ± 밴드를 벗어나지 않음
- 단계적 익절: 과열 조건에서만, 실데이터가 있을 때만 트리거
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.allocation_arbiter import AllocationArbiter
from src.core.opportunistic_seller import OpportunisticSeller, SellLevel


# ---------------------------------------------------------------------------
# AllocationArbiter
# ---------------------------------------------------------------------------

class TestClawbackExemption:
    def _arbiter_with_buys(self, buys):
        db = MagicMock()
        db.get_recent_opportunistic_buys.return_value = buys
        return AllocationArbiter(db_manager=db)

    def test_recent_buy_exempt_from_rebalance_sell(self):
        """급락에 산 물량(300만원)은 리밸런싱 매도(500만원)에서 차감"""
        arbiter = self._arbiter_with_buys([
            {"asset": "BTC", "amount_krw": 3_000_000},
        ])
        adjusted = arbiter.adjust_rebalance_sell("BTC", 5_000_000)
        assert adjusted == pytest.approx(2_000_000)

    def test_full_exemption_blocks_sell(self):
        """면제 금액이 매도 금액 이상이면 매도 0"""
        arbiter = self._arbiter_with_buys([
            {"asset": "BTC", "amount_krw": 6_000_000},
        ])
        assert arbiter.adjust_rebalance_sell("BTC", 5_000_000) == 0.0

    def test_other_asset_not_affected(self):
        arbiter = self._arbiter_with_buys([
            {"asset": "ETH", "amount_krw": 3_000_000},
        ])
        assert arbiter.adjust_rebalance_sell("BTC", 5_000_000) == pytest.approx(5_000_000)

    def test_no_db_no_exemption(self):
        arbiter = AllocationArbiter(db_manager=None)
        assert arbiter.adjust_rebalance_sell("BTC", 5_000_000) == pytest.approx(5_000_000)


class TestAllocationBand:
    def setup_method(self):
        self.arbiter = AllocationArbiter(band_width=0.08)

    def test_buy_headroom(self):
        """총 1억, crypto 5천만(50%), 목표 65% → 밴드 상단 73% → 매수 여력 2,300만"""
        allowed = self.arbiter.max_opportunistic_buy(
            total_value_krw=100_000_000,
            crypto_value_krw=50_000_000,
            target_crypto_weight=0.65,
        )
        assert allowed == pytest.approx(23_000_000)

    def test_buy_blocked_above_band(self):
        """이미 밴드 상단을 초과하면 매수 여력 0"""
        allowed = self.arbiter.max_opportunistic_buy(
            total_value_krw=100_000_000,
            crypto_value_krw=80_000_000,
            target_crypto_weight=0.65,
        )
        assert allowed == 0.0

    def test_sell_headroom(self):
        """crypto 50%, 목표 35% → 밴드 하단 27% → 매도 여력 2,300만"""
        allowed = self.arbiter.max_opportunistic_sell(
            total_value_krw=100_000_000,
            crypto_value_krw=50_000_000,
            target_crypto_weight=0.35,
        )
        assert allowed == pytest.approx(23_000_000)

    def test_sell_blocked_below_band(self):
        allowed = self.arbiter.max_opportunistic_sell(
            total_value_krw=100_000_000,
            crypto_value_krw=20_000_000,
            target_crypto_weight=0.35,
        )
        assert allowed == 0.0

    def test_zero_total_value(self):
        assert self.arbiter.max_opportunistic_buy(0, 0, 0.5) == 0.0
        assert self.arbiter.max_opportunistic_sell(0, 0, 0.5) == 0.0


# ---------------------------------------------------------------------------
# OpportunisticSeller
# ---------------------------------------------------------------------------

def _make_seller(fear_greed=None, ma_ratio_price=None):
    db = MagicMock()
    db.get_recent_opportunistic_sells.return_value = []

    fg_provider = None
    if fear_greed is not None:
        fg_provider = MagicMock()
        fg_provider.get_index.return_value = fear_greed

    seller = OpportunisticSeller(
        coinone_client=MagicMock(),
        db_manager=db,
        fear_greed_provider=fg_provider,
        market_data_provider=None,
    )
    return seller, db


class TestSellLevelDetermination:
    def test_no_sell_in_normal_market(self):
        seller, _ = _make_seller()
        level = seller._determine_sell_level(rally=0.10, rsi=55, fear_greed=None, ma_ratio=None)
        assert level == SellLevel.NONE

    def test_minor_on_rally_and_overbought(self):
        seller, _ = _make_seller()
        level = seller._determine_sell_level(rally=0.28, rsi=72, fear_greed=None, ma_ratio=None)
        assert level == SellLevel.MINOR

    def test_moderate(self):
        seller, _ = _make_seller()
        level = seller._determine_sell_level(rally=0.45, rsi=78, fear_greed=None, ma_ratio=None)
        assert level == SellLevel.MODERATE

    def test_major_requires_real_greed_data(self):
        """탐욕지수 실데이터가 없으면 MAJOR는 트리거되지 않음 (추정 금지)"""
        seller, _ = _make_seller()
        level = seller._determine_sell_level(rally=0.70, rsi=60, fear_greed=None, ma_ratio=None)
        assert level == SellLevel.NONE

        level = seller._determine_sell_level(rally=0.70, rsi=60, fear_greed=80, ma_ratio=None)
        assert level == SellLevel.MAJOR

    def test_extreme_requires_both_r_and_greed(self):
        seller, _ = _make_seller()
        # R만 높고 탐욕지수 없음 → EXTREME 아님
        level = seller._determine_sell_level(rally=0.70, rsi=80, fear_greed=None, ma_ratio=3.0)
        assert level != SellLevel.EXTREME

        level = seller._determine_sell_level(rally=0.70, rsi=80, fear_greed=90, ma_ratio=3.0)
        assert level == SellLevel.EXTREME

    def test_sell_ratios_increase_with_level(self):
        seller, _ = _make_seller()
        ratios = [seller._sell_ratio_for_level(l) for l in
                  [SellLevel.MINOR, SellLevel.MODERATE, SellLevel.MAJOR, SellLevel.EXTREME]]
        assert ratios == sorted(ratios)
        assert ratios[0] == pytest.approx(0.05)
        assert ratios[-1] == pytest.approx(0.20)


class TestResellGates:
    def test_blocked_within_interval(self):
        seller, _ = _make_seller()
        seller.recent_sells["BTC"] = datetime.now() - timedelta(hours=1)
        assert seller._can_resell("BTC", 200.0) is False

    def test_blocked_without_additional_rise(self):
        seller, _ = _make_seller()
        seller.recent_sells["BTC"] = datetime.now() - timedelta(hours=5)
        seller.last_sell_prices["BTC"] = 100.0
        assert seller._can_resell("BTC", 102.0) is False

    def test_allowed_with_additional_rise(self):
        seller, _ = _make_seller()
        seller.recent_sells["BTC"] = datetime.now() - timedelta(hours=5)
        seller.last_sell_prices["BTC"] = 100.0
        assert seller._can_resell("BTC", 106.0) is True


class TestExecuteSells:
    def test_respects_total_limit(self):
        """총 매도 한도(밴드)를 넘지 않음"""
        from src.core.opportunistic_seller import SellOpportunity

        seller, db = _make_seller()
        order_manager = MagicMock()
        order_obj = MagicMock()
        order_obj.status.value = "FILLED"
        order_obj.order_id = "test-1"
        order_manager.submit_market_order.return_value = order_obj
        seller.order_manager = order_manager

        opp = SellOpportunity(
            asset="BTC",
            current_price=100_000_000,
            low_30d=70_000_000,
            rally_from_30d_low=0.43,
            rsi=80,
            fear_greed_index=None,
            price_to_ma200w_ratio=None,
            sell_level=SellLevel.MODERATE,
            recommended_sell_ratio=0.10,
        )
        holdings = {"BTC": {"amount": 1.0, "value_krw": 100_000_000}}

        # 보유분 10% = 1천만 원이지만 한도는 300만 원
        results = seller.execute_opportunistic_sells(
            [opp], holdings, max_total_sell_krw=3_000_000
        )

        assert len(results["executed_orders"]) == 1
        assert results["total_sold_krw"] <= 3_000_000 + 1

    def test_skips_zero_holdings(self):
        from src.core.opportunistic_seller import SellOpportunity

        seller, _ = _make_seller()
        opp = SellOpportunity(
            asset="ETH", current_price=5_000_000, low_30d=3_000_000,
            rally_from_30d_low=0.66, rsi=80, fear_greed_index=80,
            price_to_ma200w_ratio=None, sell_level=SellLevel.MAJOR,
            recommended_sell_ratio=0.15,
        )
        results = seller.execute_opportunistic_sells([opp], holdings={})
        assert results["executed_orders"] == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
