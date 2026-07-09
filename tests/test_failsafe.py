"""
Fail-safe 및 real-data-only 원칙 검증 테스트

핵심 원칙:
1. 시장 데이터를 얻을 수 없으면 "판단 불가"이지 "강세장"이 아니다 (임의 fallback 금지)
2. 완충 밴드 내에서는 직전 시장 계절을 유지한다 (히스테리시스)
3. NEUTRAL은 "기존 비중 유지"를 의미한다
4. 목업/추정 지표(가짜 공포탐욕지수 등)는 사용하지 않는다
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.market_season_filter import MarketSeasonFilter, MarketSeason, season_from_string
from src.core.exceptions import MarketDataUnavailableError


# ---------------------------------------------------------------------------
# MarketSeasonFilter: 200주 MA 계산 fail-safe
# ---------------------------------------------------------------------------

class TestCalculate200WeekMA:
    def setup_method(self):
        self.filter = MarketSeasonFilter()

    def test_empty_dataframe_returns_none(self):
        assert self.filter.calculate_200week_ma(pd.DataFrame()) is None

    def test_missing_close_column_returns_none(self):
        df = pd.DataFrame({"Open": [1, 2, 3]})
        assert self.filter.calculate_200week_ma(df) is None

    def test_insufficient_weekly_data_returns_none(self):
        """200주 미만 데이터는 짧은 MA로 대체하지 않고 None"""
        dates = pd.date_range(end=datetime.now(), periods=100, freq="W")
        df = pd.DataFrame({"Close": np.linspace(100, 200, 100)}, index=dates)
        assert self.filter.calculate_200week_ma(df) is None

    def test_non_datetime_index_returns_none(self):
        df = pd.DataFrame({"Close": np.linspace(100, 200, 300)})
        assert self.filter.calculate_200week_ma(df) is None

    def test_sufficient_data_returns_value(self):
        dates = pd.date_range(end=datetime.now(), periods=250, freq="W")
        df = pd.DataFrame({"Close": np.full(250, 100.0)}, index=dates)
        ma = self.filter.calculate_200week_ma(df)
        assert ma is not None
        assert ma == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# MarketSeasonFilter: 완충 밴드 히스테리시스
# ---------------------------------------------------------------------------

class TestBufferBandHysteresis:
    def setup_method(self):
        self.filter = MarketSeasonFilter(buffer_band=0.05)

    def test_in_band_keeps_previous_risk_on(self):
        """ratio 1.06(RISK_ON) → 1.04(밴드 내)로 내려와도 RISK_ON 유지"""
        season, _ = self.filter.determine_market_season(
            current_price=104, ma_200w=100, previous_season=MarketSeason.RISK_ON
        )
        assert season == MarketSeason.RISK_ON

    def test_in_band_keeps_previous_risk_off(self):
        season, _ = self.filter.determine_market_season(
            current_price=96, ma_200w=100, previous_season=MarketSeason.RISK_OFF
        )
        assert season == MarketSeason.RISK_OFF

    def test_in_band_without_previous_is_neutral(self):
        season, _ = self.filter.determine_market_season(
            current_price=100, ma_200w=100, previous_season=None
        )
        assert season == MarketSeason.NEUTRAL

    def test_band_exit_switches_season(self):
        season, _ = self.filter.determine_market_season(
            current_price=94, ma_200w=100, previous_season=MarketSeason.RISK_ON
        )
        assert season == MarketSeason.RISK_OFF

    def test_invalid_data_keeps_previous_season(self):
        """데이터 오류 시 직전 계절 유지 (임의로 NEUTRAL 전환 금지)"""
        season, info = self.filter.determine_market_season(
            current_price=float("nan"), ma_200w=100, previous_season=MarketSeason.RISK_OFF
        )
        assert season == MarketSeason.RISK_OFF
        assert info.get("error")

    def test_invalid_ma_keeps_previous_season(self):
        season, info = self.filter.determine_market_season(
            current_price=100, ma_200w=None, previous_season=MarketSeason.RISK_ON
        )
        assert season == MarketSeason.RISK_ON
        assert info.get("error")


# ---------------------------------------------------------------------------
# MarketSeasonFilter: NEUTRAL = 기존 비중 유지
# ---------------------------------------------------------------------------

class TestNeutralAllocation:
    def setup_method(self):
        self.filter = MarketSeasonFilter()

    def test_neutral_holds_current_weight(self):
        weights = self.filter.get_allocation_weights(
            MarketSeason.NEUTRAL, current_crypto_weight=0.65
        )
        assert weights["crypto"] == pytest.approx(0.65)
        assert weights["krw"] == pytest.approx(0.35)

    def test_neutral_without_current_weight_is_50_50(self):
        weights = self.filter.get_allocation_weights(MarketSeason.NEUTRAL)
        assert weights["crypto"] == pytest.approx(0.50)

    def test_neutral_clamps_extreme_weight(self):
        weights = self.filter.get_allocation_weights(
            MarketSeason.NEUTRAL, current_crypto_weight=0.95
        )
        assert weights["crypto"] == pytest.approx(0.70)

    def test_risk_on_allocation(self):
        weights = self.filter.get_allocation_weights(MarketSeason.RISK_ON)
        assert weights["crypto"] == pytest.approx(0.70)

    def test_risk_off_allocation(self):
        weights = self.filter.get_allocation_weights(MarketSeason.RISK_OFF)
        assert weights["crypto"] == pytest.approx(0.30)


# ---------------------------------------------------------------------------
# analyze_weekly: 데이터 부족 시 판단하지 않음
# ---------------------------------------------------------------------------

class TestAnalyzeWeeklyFailSafe:
    def test_insufficient_data_returns_failure(self):
        f = MarketSeasonFilter()
        dates = pd.date_range(end=datetime.now(), periods=50, freq="W")
        df = pd.DataFrame({"Close": np.full(50, 100.0)}, index=dates)

        result = f.analyze_weekly(df)

        assert result["success"] is False
        assert "allocation_weights" not in result

    def test_previous_season_passed_through(self):
        """밴드 내 가격이면 previous_season이 결과에 반영되어야 함"""
        f = MarketSeasonFilter()
        dates = pd.date_range(end=datetime.now(), periods=250, freq="W")
        # MA ≈ 100, 마지막 가격 103 (밴드 내)
        prices = np.full(250, 100.0)
        prices[-1] = 103.0
        df = pd.DataFrame({"Close": prices}, index=dates)

        result = f.analyze_weekly(df, previous_season=MarketSeason.RISK_ON)

        assert result["success"] is True
        assert result["market_season"] == MarketSeason.RISK_ON.value


# ---------------------------------------------------------------------------
# MarketDataProvider: 임의 fallback 없이 예외 발생
# ---------------------------------------------------------------------------

class TestMarketDataProviderFailSafe:
    def test_raises_when_no_cache_and_binance_fails(self):
        from src.utils.market_data_provider import MarketDataProvider

        provider = MarketDataProvider(db_manager=None)
        with patch.object(provider, "_calculate_200w_ma_from_binance", return_value=None):
            with pytest.raises(MarketDataUnavailableError):
                provider.get_btc_200w_ma()

    def test_uses_cache_when_available(self):
        from src.utils.market_data_provider import MarketDataProvider

        provider = MarketDataProvider(db_manager=MagicMock())
        with patch.object(provider, "_get_cached_200w_ma", return_value=123456.0):
            ma, source = provider.get_btc_200w_ma()
        assert ma == 123456.0
        assert source == "cache"


# ---------------------------------------------------------------------------
# season_from_string 유틸리티
# ---------------------------------------------------------------------------

class TestSeasonFromString:
    def test_valid_values(self):
        assert season_from_string("risk_on") == MarketSeason.RISK_ON
        assert season_from_string("RISK_OFF") == MarketSeason.RISK_OFF
        assert season_from_string("neutral") == MarketSeason.NEUTRAL

    def test_invalid_values(self):
        assert season_from_string(None) is None
        assert season_from_string("") is None
        assert season_from_string("bullish") is None


# ---------------------------------------------------------------------------
# OpportunisticBuyer: 고점 대비 하락률 + 재매수 조건 + 공포지수 None 처리
# ---------------------------------------------------------------------------

def _make_buyer(**kwargs):
    from src.core.opportunistic_buyer import OpportunisticBuyer

    db = MagicMock()
    db.get_recent_opportunistic_buys.return_value = []
    return OpportunisticBuyer(
        coinone_client=MagicMock(),
        db_manager=db,
        **kwargs
    ), db


class TestOpportunisticBuyerRealData:
    def test_no_fake_fear_greed_index(self):
        """공포탐욕 제공자가 없으면 추정치 대신 None을 반환해야 함"""
        buyer, _ = _make_buyer()
        assert buyer.get_fear_greed_index() is None

    def test_drawdown_measured_from_high_not_mean(self):
        """지속 하락장에서 평균 대비가 아닌 고점 대비 하락률을 사용해야 함"""
        buyer, db = _make_buyer()

        # 7일: 100 → 99로 완만한 하락 (고점 대비 -1%, 평균 대비도 소폭)
        dates_7d = pd.date_range(end=datetime.now(), periods=7, freq="D")
        df_7d = pd.DataFrame({"Close": np.linspace(100, 99, 7)}, index=dates_7d)
        dates_30d = pd.date_range(end=datetime.now(), periods=30, freq="D")
        df_30d = pd.DataFrame({"Close": np.linspace(101, 99, 30)}, index=dates_30d)

        db.get_market_data.side_effect = lambda asset, days: df_7d if days == 7 else df_30d

        opportunities, reasons = buyer.identify_opportunities(["BTC"])

        # 고점 대비 -1~-2% 수준이므로 기회로 판정되면 안 됨
        assert opportunities == []
        assert "BTC" in reasons

    def test_crash_triggers_opportunity(self):
        buyer, db = _make_buyer()

        # 고점 100에서 78로 -22% 급락
        dates_30d = pd.date_range(end=datetime.now(), periods=30, freq="D")
        prices_30d = np.concatenate([np.full(15, 100.0), np.linspace(100, 78, 15)])
        df_30d = pd.DataFrame({"Close": prices_30d}, index=dates_30d)
        df_7d = df_30d.tail(7)

        db.get_market_data.side_effect = lambda asset, days: df_7d if days == 7 else df_30d

        opportunities, _ = buyer.identify_opportunities(["BTC"])

        assert len(opportunities) == 1
        assert opportunities[0].price_drop_30d == pytest.approx(-0.22, abs=0.01)

    def test_rebuy_blocked_within_interval(self):
        buyer, _ = _make_buyer()
        buyer.recent_buys["BTC"] = datetime.now() - timedelta(hours=1)
        buyer.last_buy_prices["BTC"] = 100.0
        assert buyer._can_rebuy("BTC", 90.0) is False

    def test_rebuy_blocked_without_additional_drop(self):
        """4시간이 지나도 직전 매수가 대비 -3% 추가 하락이 없으면 재매수 금지"""
        buyer, _ = _make_buyer()
        buyer.recent_buys["BTC"] = datetime.now() - timedelta(hours=5)
        buyer.last_buy_prices["BTC"] = 100.0
        assert buyer._can_rebuy("BTC", 99.0) is False

    def test_rebuy_allowed_with_additional_drop(self):
        buyer, _ = _make_buyer()
        buyer.recent_buys["BTC"] = datetime.now() - timedelta(hours=5)
        buyer.last_buy_prices["BTC"] = 100.0
        assert buyer._can_rebuy("BTC", 96.5) is True

    def test_opportunity_level_handles_none_fear_greed(self):
        from src.core.opportunistic_buyer import OpportunityLevel

        buyer, _ = _make_buyer()
        level = buyer._determine_opportunity_level(
            drop_7d=-0.35, drop_30d=-0.35, rsi=25, fear_greed=None
        )
        assert level == OpportunityLevel.EXTREME  # RSI 과매도만으로 성립

        ratio = buyer._calculate_buy_ratio(OpportunityLevel.MINOR, rsi=40, fear_greed=None)
        assert ratio > 0


# ---------------------------------------------------------------------------
# DCA+: 월 한도가 누적 집행액 기준으로 동작
# ---------------------------------------------------------------------------

class TestDCAMonthlyCap:
    def _make_dca(self):
        from src.core.dca_plus_strategy import DCAPlus
        return DCAPlus()

    def _market_data(self):
        dates = pd.date_range(end=datetime.now(), periods=60, freq="D")
        df = pd.DataFrame({
            "Close": np.full(60, 100000.0),
            "Volume": np.full(60, 1000.0)
        }, index=dates)
        return {"BTC": df, "ETH": df, "SOL": df}

    def test_monthly_cap_exhausted_skips_dca(self):
        dca = self._make_dca()
        schedule = dca.default_schedule  # max_monthly_amount=5,000,000

        events = dca.calculate_dca_amount(
            schedule, self._market_data(), month_spent_krw=5_000_000
        )
        assert events == {}

    def test_monthly_cap_limits_remaining_budget(self):
        dca = self._make_dca()
        schedule = dca.default_schedule

        events = dca.calculate_dca_amount(
            schedule, self._market_data(), month_spent_krw=4_900_000
        )
        total = sum(e.amount_krw for e in events.values())
        assert total <= 100_000 + 1  # 잔여 한도 이내

    def test_no_spent_allows_normal_dca(self):
        dca = self._make_dca()
        schedule = dca.default_schedule

        events = dca.calculate_dca_amount(
            schedule, self._market_data(), month_spent_krw=0
        )
        assert len(events) > 0
        total = sum(e.amount_krw for e in events.values())
        assert total <= schedule.max_monthly_amount


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
