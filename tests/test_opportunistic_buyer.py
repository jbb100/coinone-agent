"""
Opportunistic Buyer 테스트 모듈

시장 하락 시 기회적 매수 시스템 테스트
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

from src.core.opportunistic_buyer import (
    OpportunisticBuyer,
    OpportunityLevel,
    BuyOpportunity
)
from src.utils.constants import (
    RSI_OVERSOLD,
    RSI_MIDLINE,
    FEAR_GREED_EXTREME_FEAR,
    FEAR_GREED_FEAR,
    FEAR_GREED_EXTREME_GREED
)


class TestOpportunityLevel:
    """OpportunityLevel Enum 테스트"""

    def test_opportunity_levels_exist(self):
        """모든 기회 수준이 정의되어 있는지 확인"""
        assert OpportunityLevel.NONE.value == "none"
        assert OpportunityLevel.MINOR.value == "minor"
        assert OpportunityLevel.MODERATE.value == "moderate"
        assert OpportunityLevel.MAJOR.value == "major"
        assert OpportunityLevel.EXTREME.value == "extreme"

    def test_opportunity_level_count(self):
        """기회 수준 개수 확인"""
        assert len(OpportunityLevel) == 5


class TestBuyOpportunity:
    """BuyOpportunity Dataclass 테스트"""

    def test_buy_opportunity_creation(self):
        """BuyOpportunity 생성 테스트"""
        opportunity = BuyOpportunity(
            asset="BTC",
            current_price=50000000.0,
            avg_price_7d=55000000.0,
            avg_price_30d=60000000.0,
            price_drop_7d=-0.09,
            price_drop_30d=-0.17,
            rsi=25.0,
            fear_greed_index=20.0,
            opportunity_level=OpportunityLevel.MODERATE,
            recommended_buy_ratio=0.2,
            confidence_score=0.75
        )

        assert opportunity.asset == "BTC"
        assert opportunity.current_price == 50000000.0
        assert opportunity.opportunity_level == OpportunityLevel.MODERATE
        assert opportunity.confidence_score == 0.75

    def test_buy_opportunity_timestamp_default(self):
        """타임스탬프 기본값 테스트"""
        opportunity = BuyOpportunity(
            asset="ETH",
            current_price=3000000.0,
            avg_price_7d=3500000.0,
            avg_price_30d=4000000.0,
            price_drop_7d=-0.14,
            price_drop_30d=-0.25,
            rsi=20.0,
            fear_greed_index=15.0,
            opportunity_level=OpportunityLevel.MAJOR,
            recommended_buy_ratio=0.3,
            confidence_score=0.85
        )

        assert opportunity.timestamp is not None
        assert isinstance(opportunity.timestamp, datetime)


class TestOpportunisticBuyer:
    """OpportunisticBuyer 클래스 테스트"""

    @pytest.fixture
    def mock_coinone_client(self):
        """Coinone 클라이언트 Mock"""
        client = Mock()
        client.get_portfolio_value.return_value = {
            "total_value_krw": 10000000.0,
            "assets": {
                "BTC": {"value_krw": 3000000.0},
                "ETH": {"value_krw": 2000000.0}
            }
        }
        client.place_order.return_value = {
            "success": True,
            "order_id": "test_order_123"
        }
        return client

    @pytest.fixture
    def mock_db_manager(self):
        """데이터베이스 매니저 Mock"""
        db = Mock()

        # 기본 가격 데이터 생성
        def get_market_data(asset, days=7):
            dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
            # 하락 추세 데이터
            base_price = 50000000 if asset == "BTC" else 3000000
            prices = [base_price * (1 - 0.02 * i) for i in range(days)]
            prices.reverse()
            return pd.DataFrame({
                'Close': prices,
                'Date': dates
            })

        db.get_market_data.side_effect = get_market_data
        db.get_daily_buy_stats.return_value = {'count': 0, 'amount': 0}
        db.is_trading_locked.return_value = False
        db.get_last_rebalance_time.return_value = None
        db.get_recent_opportunistic_buys.return_value = []
        db.update_daily_buy_limits.return_value = None
        db.save_opportunistic_buy_record.return_value = None

        return db

    @pytest.fixture
    def buyer(self, mock_coinone_client, mock_db_manager):
        """OpportunisticBuyer 인스턴스"""
        return OpportunisticBuyer(
            coinone_client=mock_coinone_client,
            db_manager=mock_db_manager,
            cash_reserve_ratio=0.15,
            min_opportunity_threshold=0.05,
            max_buy_per_opportunity=0.3
        )

    def test_init(self, buyer):
        """초기화 테스트"""
        assert buyer.cash_reserve_ratio == 0.15
        assert buyer.min_opportunity_threshold == 0.05
        assert buyer.max_buy_per_opportunity == 0.3
        assert buyer.min_buy_interval_hours == 4

    def test_init_default_schedules(self, buyer):
        """기본 스케줄 초기화 테스트"""
        assert OpportunityLevel.MINOR in buyer.level_portfolio_usage_schedule
        assert OpportunityLevel.EXTREME in buyer.level_portfolio_usage_schedule
        assert buyer.level_portfolio_usage_schedule[OpportunityLevel.EXTREME] == 1.00

    def test_calculate_rsi_basic(self, buyer):
        """RSI 계산 기본 테스트"""
        # 상승 추세 데이터
        prices = pd.Series([100, 102, 104, 106, 108, 110, 112, 114, 116, 118,
                           120, 122, 124, 126, 128, 130])
        rsi = buyer.calculate_rsi(prices)

        # 상승 추세에서 RSI는 50 이상이어야 함
        assert rsi > 50

    def test_calculate_rsi_oversold(self, buyer):
        """RSI 과매도 구간 테스트"""
        # 하락 추세 데이터
        prices = pd.Series([130, 128, 126, 124, 122, 120, 118, 116, 114, 112,
                           110, 108, 106, 104, 102, 100])
        rsi = buyer.calculate_rsi(prices)

        # 하락 추세에서 RSI는 50 이하이어야 함
        assert rsi < 50

    def test_calculate_rsi_empty_series(self, buyer):
        """빈 시리즈 RSI 계산 테스트"""
        prices = pd.Series([])
        rsi = buyer.calculate_rsi(prices)

        # 빈 데이터에서는 중립값 반환
        assert rsi == 50.0

    def test_determine_opportunity_level_none(self, buyer):
        """기회 없음 수준 판단 테스트"""
        level = buyer._determine_opportunity_level(
            drop_7d=0.02,  # 2% 상승
            drop_30d=0.05,  # 5% 상승
            rsi=60,  # 중립
            fear_greed=55  # 중립
        )

        assert level == OpportunityLevel.NONE

    def test_determine_opportunity_level_minor(self, buyer):
        """소폭 하락 수준 판단 테스트"""
        level = buyer._determine_opportunity_level(
            drop_7d=-0.06,  # 6% 하락
            drop_30d=-0.04,
            rsi=45,
            fear_greed=45
        )

        assert level == OpportunityLevel.MINOR

    def test_determine_opportunity_level_moderate(self, buyer):
        """중간 하락 수준 판단 테스트"""
        level = buyer._determine_opportunity_level(
            drop_7d=-0.12,  # 12% 하락
            drop_30d=-0.15,
            rsi=40,  # RSI < 45
            fear_greed=40
        )

        assert level == OpportunityLevel.MODERATE

    def test_determine_opportunity_level_major(self, buyer):
        """대폭 하락 수준 판단 테스트"""
        level = buyer._determine_opportunity_level(
            drop_7d=-0.22,  # 22% 하락
            drop_30d=-0.25,
            rsi=35,  # RSI < FEAR_GREED_FEAR
            fear_greed=30
        )

        assert level == OpportunityLevel.MAJOR

    def test_determine_opportunity_level_extreme(self, buyer):
        """극단적 하락 수준 판단 테스트"""
        level = buyer._determine_opportunity_level(
            drop_7d=-0.35,  # 35% 하락
            drop_30d=-0.40,
            rsi=15,  # 과매도
            fear_greed=10  # 극도의 공포
        )

        assert level == OpportunityLevel.EXTREME

    def test_calculate_buy_ratio_minor(self, buyer):
        """MINOR 레벨 매수 비율 테스트"""
        ratio = buyer._calculate_buy_ratio(
            level=OpportunityLevel.MINOR,
            rsi=45,
            fear_greed=45
        )

        # 기본 비율은 0.1
        assert ratio >= 0.1
        assert ratio <= buyer.max_buy_per_opportunity

    def test_calculate_buy_ratio_extreme(self, buyer):
        """EXTREME 레벨 매수 비율 테스트"""
        ratio = buyer._calculate_buy_ratio(
            level=OpportunityLevel.EXTREME,
            rsi=15,  # 과매도
            fear_greed=10  # 극도의 공포
        )

        # EXTREME 레벨은 최대 50%까지 허용
        assert ratio > 0.1
        assert ratio <= 0.5

    def test_calculate_buy_ratio_with_bonus(self, buyer):
        """RSI/공포지수 보너스 적용 테스트"""
        # 높은 RSI, 높은 공포지수 (보너스 없음)
        ratio_no_bonus = buyer._calculate_buy_ratio(
            level=OpportunityLevel.MODERATE,
            rsi=50,
            fear_greed=50
        )

        # 낮은 RSI, 낮은 공포지수 (보너스 있음)
        ratio_with_bonus = buyer._calculate_buy_ratio(
            level=OpportunityLevel.MODERATE,
            rsi=20,
            fear_greed=15
        )

        assert ratio_with_bonus > ratio_no_bonus

    def test_calculate_confidence_score(self, buyer):
        """신뢰도 점수 계산 테스트"""
        score = buyer._calculate_confidence_score(
            drop_7d=-0.15,
            drop_30d=-0.20,
            rsi=25,
            fear_greed=20
        )

        assert 0 <= score <= 1

    def test_calculate_confidence_score_high(self, buyer):
        """높은 신뢰도 점수 테스트"""
        score = buyer._calculate_confidence_score(
            drop_7d=-0.30,
            drop_30d=-0.35,
            rsi=10,  # 매우 낮은 RSI
            fear_greed=5  # 극도의 공포
        )

        # 모든 조건이 좋으면 높은 점수
        assert score > 0.5

    def test_calculate_confidence_score_low(self, buyer):
        """낮은 신뢰도 점수 테스트"""
        score = buyer._calculate_confidence_score(
            drop_7d=-0.01,  # 거의 하락 없음
            drop_30d=-0.02,
            rsi=55,  # 중립
            fear_greed=50  # 중립
        )

        # 조건이 좋지 않으면 낮은 점수
        assert score < 0.5

    def test_can_execute_buy_success(self, buyer):
        """매수 가능 여부 - 성공 케이스"""
        can_buy, reason = buyer._can_execute_buy("BTC", 100000)

        assert can_buy is True
        assert reason == "OK"

    def test_can_execute_buy_trading_locked(self, buyer):
        """매수 불가 - 거래 잠김"""
        buyer.db_manager.is_trading_locked.return_value = True

        can_buy, reason = buyer._can_execute_buy("BTC", 100000)

        assert can_buy is False
        assert "locked" in reason.lower()

    def test_can_execute_buy_recent_rebalance(self, buyer):
        """매수 불가 - 최근 리밸런싱"""
        buyer.db_manager.get_last_rebalance_time.return_value = datetime.now() - timedelta(hours=12)

        can_buy, reason = buyer._can_execute_buy("BTC", 100000)

        assert can_buy is False
        assert "rebalancing" in reason.lower()

    def test_can_execute_buy_daily_count_limit(self, buyer):
        """매수 불가 - 일일 횟수 제한"""
        buyer.db_manager.get_daily_buy_stats.return_value = {'count': 3, 'amount': 500000}

        can_buy, reason = buyer._can_execute_buy("BTC", 100000)

        assert can_buy is False
        assert "count limit" in reason.lower()

    def test_can_execute_buy_daily_amount_limit(self, buyer):
        """매수 불가 - 일일 금액 제한"""
        buyer.db_manager.get_daily_buy_stats.return_value = {'count': 1, 'amount': 950000}

        # 100000 추가하면 1050000이 되어 1000000 초과
        can_buy, reason = buyer._can_execute_buy("BTC", 100000)

        assert can_buy is False
        assert "amount limit" in reason.lower()

    def test_can_execute_buy_cooldown(self, buyer):
        """매수 불가 - 쿨다운 기간"""
        # 최근 매수 이력 설정
        buyer.recent_buys["BTC"] = datetime.now() - timedelta(hours=2)

        can_buy, reason = buyer._can_execute_buy("BTC", 100000)

        assert can_buy is False
        assert "쿨다운" in reason

    def test_identify_opportunities(self, buyer):
        """매수 기회 식별 테스트"""
        # 하락 추세 데이터 설정
        def get_declining_data(asset, days=7):
            dates = pd.date_range(end=datetime.now(), periods=max(days, 30), freq='D')
            base_price = 50000000 if asset == "BTC" else 3000000
            # 15% 하락 추세
            prices = [base_price * (1 - 0.15 * i / max(days, 30)) for i in range(max(days, 30))]
            prices.reverse()
            return pd.DataFrame({
                'Close': prices,
                'Date': dates
            })

        buyer.db_manager.get_market_data.side_effect = get_declining_data

        opportunities, no_opportunity_reasons = buyer.identify_opportunities(["BTC", "ETH", "KRW"])

        # KRW는 제외되어야 함
        assert "KRW" not in [o.asset for o in opportunities]
        assert "KRW" not in no_opportunity_reasons

    def test_identify_opportunities_empty_data(self, buyer):
        """빈 데이터로 기회 식별 테스트"""
        # side_effect를 None으로 리셋하고 return_value 설정
        buyer.db_manager.get_market_data.side_effect = None
        buyer.db_manager.get_market_data.return_value = pd.DataFrame()

        opportunities, no_opportunity_reasons = buyer.identify_opportunities(["BTC"])

        assert len(opportunities) == 0
        assert "BTC" in no_opportunity_reasons
        assert "데이터 없음" in no_opportunity_reasons["BTC"]

    def test_execute_opportunistic_buys_success(self, buyer):
        """기회적 매수 실행 - 성공 케이스"""
        opportunity = BuyOpportunity(
            asset="BTC",
            current_price=50000000.0,
            avg_price_7d=55000000.0,
            avg_price_30d=60000000.0,
            price_drop_7d=-0.09,
            price_drop_30d=-0.17,
            rsi=25.0,
            fear_greed_index=20.0,
            opportunity_level=OpportunityLevel.MODERATE,
            recommended_buy_ratio=0.2,
            confidence_score=0.75
        )

        results = buyer.execute_opportunistic_buys(
            opportunities=[opportunity],
            available_cash=1000000.0
        )

        assert "executed_orders" in results
        assert "failed_orders" in results
        assert "skipped_orders" in results
        assert "total_invested" in results

    def test_execute_opportunistic_buys_insufficient_budget(self, buyer):
        """기회적 매수 - 예산 부족"""
        opportunity = BuyOpportunity(
            asset="BTC",
            current_price=50000000.0,
            avg_price_7d=55000000.0,
            avg_price_30d=60000000.0,
            price_drop_7d=-0.09,
            price_drop_30d=-0.17,
            rsi=25.0,
            fear_greed_index=20.0,
            opportunity_level=OpportunityLevel.MODERATE,
            recommended_buy_ratio=0.2,
            confidence_score=0.75
        )

        # 매우 적은 예산
        results = buyer.execute_opportunistic_buys(
            opportunities=[opportunity],
            available_cash=1000.0  # 1000원
        )

        # 최소 주문 금액 미달로 스킵
        assert len(results["skipped_orders"]) > 0 or len(results["executed_orders"]) == 0

    def test_get_cash_utilization_strategy_extreme_fear(self, buyer):
        """현금 활용 전략 - 극도의 공포"""
        with patch.object(buyer, 'get_fear_greed_index', return_value=15):
            strategy = buyer.get_cash_utilization_strategy()

        assert strategy["mode"] == "aggressive_buying"
        assert strategy["cash_deploy_ratio"] > 0.3

    def test_get_cash_utilization_strategy_fear(self, buyer):
        """현금 활용 전략 - 공포"""
        with patch.object(buyer, 'get_fear_greed_index', return_value=35):
            strategy = buyer.get_cash_utilization_strategy()

        assert strategy["mode"] == "moderate_buying"

    def test_get_cash_utilization_strategy_extreme_greed(self, buyer):
        """현금 활용 전략 - 탐욕"""
        with patch.object(buyer, 'get_fear_greed_index', return_value=85):
            strategy = buyer.get_cash_utilization_strategy()

        assert strategy["mode"] == "defensive"
        assert strategy["cash_deploy_ratio"] < 0.2

    def test_get_cash_utilization_strategy_neutral(self, buyer):
        """현금 활용 전략 - 중립"""
        with patch.object(buyer, 'get_fear_greed_index', return_value=50):
            strategy = buyer.get_cash_utilization_strategy()

        assert strategy["mode"] == "balanced"

    def test_calculate_current_drop(self, buyer):
        """현재 하락률 계산 테스트"""
        # 하락 추세 데이터 명시적 설정
        def get_declining_data(asset, days=7):
            dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
            base_price = 50000000
            # 시간순으로 하락: 첫날 50M -> 마지막날 45M
            prices = [base_price * (1 - 0.01 * i) for i in range(days)]
            return pd.DataFrame({
                'Close': prices,
                'Date': dates
            })

        buyer.db_manager.get_market_data.side_effect = get_declining_data
        drop = buyer._calculate_current_drop("BTC")

        # 하락 추세이므로 음수여야 함
        assert drop < 0

    def test_calculate_current_drop_no_data(self, buyer):
        """하락률 계산 - 데이터 없음"""
        # side_effect를 None으로 리셋하고 return_value 설정
        buyer.db_manager.get_market_data.side_effect = None
        buyer.db_manager.get_market_data.return_value = pd.DataFrame()

        drop = buyer._calculate_current_drop("BTC")

        assert drop == 0.0

    def test_is_recently_bought_no_history(self, buyer):
        """최근 매수 여부 - 이력 없음"""
        is_recent, info = buyer._is_recently_bought("BTC")

        assert is_recent is False
        assert info == ""

    def test_is_recently_bought_with_db_history(self, buyer):
        """최근 매수 여부 - DB 이력 있음"""
        buyer.db_manager.get_recent_opportunistic_buys.return_value = [{
            'opportunity_level': 'minor',
            'timestamp': (datetime.now() - timedelta(hours=2)).isoformat()
        }]

        is_recent, info = buyer._is_recently_bought("BTC")

        assert is_recent is True
        assert "쿨다운" in info

    def test_is_recently_bought_cooldown_passed(self, buyer):
        """최근 매수 여부 - 쿨다운 경과"""
        buyer.db_manager.get_recent_opportunistic_buys.return_value = [{
            'opportunity_level': 'minor',
            'timestamp': (datetime.now() - timedelta(hours=10)).isoformat()
        }]

        is_recent, info = buyer._is_recently_bought("BTC")

        # MINOR 레벨 쿨다운은 6시간이므로 10시간 후에는 False
        assert is_recent is False


class TestOpportunisticBuyerEdgeCases:
    """OpportunisticBuyer 엣지 케이스 테스트"""

    @pytest.fixture
    def mock_coinone_client(self):
        client = Mock()
        client.get_portfolio_value.return_value = {
            "total_value_krw": 10000000.0,
            "assets": {}
        }
        return client

    @pytest.fixture
    def mock_db_manager(self):
        db = Mock()
        db.get_market_data.return_value = pd.DataFrame()
        db.get_daily_buy_stats.return_value = {'count': 0, 'amount': 0}
        db.is_trading_locked.return_value = False
        db.get_last_rebalance_time.return_value = None
        db.get_recent_opportunistic_buys.return_value = []
        return db

    def test_custom_level_schedules(self, mock_coinone_client, mock_db_manager):
        """사용자 정의 레벨 스케줄 테스트"""
        custom_schedule = {
            OpportunityLevel.MINOR: 0.10,
            OpportunityLevel.MODERATE: 0.25,
            OpportunityLevel.MAJOR: 0.40,
            OpportunityLevel.EXTREME: 0.80
        }

        buyer = OpportunisticBuyer(
            coinone_client=mock_coinone_client,
            db_manager=mock_db_manager,
            level_portfolio_usage_schedule=custom_schedule
        )

        assert buyer.level_portfolio_usage_schedule[OpportunityLevel.MINOR] == 0.10
        assert buyer.level_portfolio_usage_schedule[OpportunityLevel.EXTREME] == 0.80

    def test_custom_min_cash_ratio(self, mock_coinone_client, mock_db_manager):
        """사용자 정의 최소 현금 비율 테스트"""
        custom_ratio = {
            OpportunityLevel.MINOR: 0.40,
            OpportunityLevel.MODERATE: 0.30,
            OpportunityLevel.MAJOR: 0.20,
            OpportunityLevel.EXTREME: 0.05
        }

        buyer = OpportunisticBuyer(
            coinone_client=mock_coinone_client,
            db_manager=mock_db_manager,
            level_min_cash_ratio=custom_ratio
        )

        assert buyer.level_min_cash_ratio[OpportunityLevel.MINOR] == 0.40
        assert buyer.level_min_cash_ratio[OpportunityLevel.EXTREME] == 0.05

    def test_get_fear_greed_index_error_handling(self, mock_coinone_client, mock_db_manager):
        """공포탐욕 지수 에러 핸들링"""
        mock_db_manager.get_market_data.side_effect = Exception("DB Error")

        buyer = OpportunisticBuyer(
            coinone_client=mock_coinone_client,
            db_manager=mock_db_manager
        )

        # 에러 시 중립값 반환
        fear_greed = buyer.get_fear_greed_index()
        assert fear_greed == 50.0

    def test_multiple_opportunities_sorted_by_confidence(self, mock_coinone_client, mock_db_manager):
        """여러 기회가 신뢰도 순으로 정렬되는지 테스트"""
        # 다른 자산에 대해 다른 데이터 반환
        def get_varied_data(asset, days=7):
            dates = pd.date_range(end=datetime.now(), periods=max(days, 30), freq='D')
            if asset == "BTC":
                base_price = 50000000
                drop_rate = 0.25  # 25% 하락 (높은 신뢰도)
            else:
                base_price = 3000000
                drop_rate = 0.10  # 10% 하락 (낮은 신뢰도)

            prices = [base_price * (1 - drop_rate * i / max(days, 30)) for i in range(max(days, 30))]
            prices.reverse()
            return pd.DataFrame({'Close': prices, 'Date': dates})

        mock_db_manager.get_market_data.side_effect = get_varied_data

        buyer = OpportunisticBuyer(
            coinone_client=mock_coinone_client,
            db_manager=mock_db_manager
        )

        opportunities, _ = buyer.identify_opportunities(["BTC", "ETH"])

        if len(opportunities) >= 2:
            # 높은 신뢰도가 먼저 와야 함
            assert opportunities[0].confidence_score >= opportunities[1].confidence_score
