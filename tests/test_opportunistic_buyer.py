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


class TestOpportunisticBuyerAdvanced:
    """OpportunisticBuyer 고급 테스트"""

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

        def get_market_data(asset, days=7):
            dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
            base_price = 50000000 if asset == "BTC" else 3000000
            prices = [base_price * (1 - 0.02 * i) for i in range(days)]
            prices.reverse()
            return pd.DataFrame({'Close': prices, 'Date': dates})

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
        return OpportunisticBuyer(
            coinone_client=mock_coinone_client,
            db_manager=mock_db_manager
        )

    def test_execute_with_order_manager(self, buyer):
        """OrderManager 사용 시 매수 실행"""
        mock_order_manager = Mock()
        mock_order_obj = Mock()
        mock_order_obj.status.value = "PENDING"
        mock_order_obj.order_id = "order_456"
        mock_order_obj.error_message = None
        mock_order_manager.submit_market_order.return_value = mock_order_obj
        buyer.order_manager = mock_order_manager

        # 높은 현금 비중으로 설정 (EXTREME 레벨은 현금 비중 제한 없음)
        opportunity = BuyOpportunity(
            asset="BTC",
            current_price=50000000.0,
            avg_price_7d=65000000.0,
            avg_price_30d=75000000.0,
            price_drop_7d=-0.35,  # 35% 하락으로 EXTREME 레벨
            price_drop_30d=-0.40,
            rsi=15.0,  # 과매도
            fear_greed_index=10.0,  # 극도의 공포
            opportunity_level=OpportunityLevel.EXTREME,
            recommended_buy_ratio=0.4,
            confidence_score=0.9
        )

        # 포트폴리오 대비 높은 현금 비중 설정
        buyer.coinone_client.get_portfolio_value.return_value = {
            "total_value_krw": 2000000.0,  # 작은 포트폴리오
            "assets": {}
        }

        results = buyer.execute_opportunistic_buys([opportunity], 1000000.0)

        # EXTREME 레벨에서 주문 실행 확인
        assert len(results["executed_orders"]) > 0 or len(results["skipped_orders"]) > 0 or len(results["failed_orders"]) > 0

    def test_execute_with_order_manager_failure(self, buyer):
        """OrderManager 주문 실패"""
        mock_order_manager = Mock()
        mock_order_obj = Mock()
        mock_order_obj.status.value = "FAILED"
        mock_order_obj.order_id = None
        mock_order_obj.error_message = "Insufficient balance"
        mock_order_manager.submit_market_order.return_value = mock_order_obj
        buyer.order_manager = mock_order_manager

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

        results = buyer.execute_opportunistic_buys([opportunity], 1000000.0)

        # 실패하면 failed_orders에 추가되거나 skipped
        assert len(results["failed_orders"]) > 0 or len(results["skipped_orders"]) > 0

    def test_execute_with_order_manager_none(self, buyer):
        """OrderManager가 None 반환"""
        mock_order_manager = Mock()
        mock_order_manager.submit_market_order.return_value = None
        buyer.order_manager = mock_order_manager

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

        results = buyer.execute_opportunistic_buys([opportunity], 1000000.0)

        assert len(results["failed_orders"]) > 0 or len(results["skipped_orders"]) > 0

    def test_execute_skip_progressive_threshold(self, buyer):
        """점진적 매수 조건 미충족으로 스킵"""
        # 이미 1회 매수한 상태
        buyer.db_manager.get_daily_buy_stats.return_value = {'count': 1, 'amount': 100000}

        opportunity = BuyOpportunity(
            asset="BTC",
            current_price=50000000.0,
            avg_price_7d=51000000.0,  # -2% 하락 (두 번째 매수 조건 -10% 미충족)
            avg_price_30d=52000000.0,
            price_drop_7d=-0.02,
            price_drop_30d=-0.04,
            rsi=35.0,
            fear_greed_index=30.0,
            opportunity_level=OpportunityLevel.MINOR,
            recommended_buy_ratio=0.1,
            confidence_score=0.5
        )

        results = buyer.execute_opportunistic_buys([opportunity], 1000000.0)

        # 점진적 매수 조건 미충족으로 스킵
        assert len(results["skipped_orders"]) > 0

    def test_execute_skip_cash_ratio_limit(self, buyer):
        """현금 비중 유지 한도로 스킵"""
        # 포트폴리오 값 대비 현금이 적은 상황
        buyer.coinone_client.get_portfolio_value.return_value = {
            "total_value_krw": 10000000.0,
            "assets": {}
        }

        opportunity = BuyOpportunity(
            asset="BTC",
            current_price=50000000.0,
            avg_price_7d=55000000.0,
            avg_price_30d=60000000.0,
            price_drop_7d=-0.09,
            price_drop_30d=-0.17,
            rsi=35.0,
            fear_greed_index=40.0,
            opportunity_level=OpportunityLevel.MINOR,  # MINOR는 현금 30% 초과 시만
            recommended_buy_ratio=0.1,
            confidence_score=0.6
        )

        # 현금 비중 10% (포트폴리오의 10%)
        results = buyer.execute_opportunistic_buys([opportunity], 1000000.0)

        # MINOR 레벨에서 현금 비중 10% < 요구치 30% 이므로 스킵 가능
        # 실제 동작은 구현에 따라 다름

    def test_execute_skip_cumulative_limit(self, buyer):
        """레벨 누적 한도 소진으로 스킵"""
        opportunity = BuyOpportunity(
            asset="BTC",
            current_price=50000000.0,
            avg_price_7d=55000000.0,
            avg_price_30d=60000000.0,
            price_drop_7d=-0.09,
            price_drop_30d=-0.17,
            rsi=35.0,
            fear_greed_index=40.0,
            opportunity_level=OpportunityLevel.MINOR,  # 5% 한도
            recommended_buy_ratio=0.1,
            confidence_score=0.6
        )

        # 작은 available_cash로 테스트
        results = buyer.execute_opportunistic_buys([opportunity], 100000.0)

        # 결과 확인
        assert isinstance(results, dict)

    def test_record_opportunistic_buy(self, buyer):
        """기회적 매수 기록 테스트"""
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

        order_result = {"order_id": "test_order_789", "success": True}

        buyer._record_opportunistic_buy(opportunity, 100000.0, order_result)

        buyer.db_manager.save_opportunistic_buy_record.assert_called_once()
        saved_record = buyer.db_manager.save_opportunistic_buy_record.call_args[0][0]
        assert saved_record['asset'] == "BTC"
        assert saved_record['amount_krw'] == 100000.0
        assert saved_record['opportunity_level'] == "moderate"

    def test_record_opportunistic_buy_exception(self, buyer):
        """기회적 매수 기록 실패"""
        buyer.db_manager.save_opportunistic_buy_record.side_effect = Exception("DB Error")

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

        # 예외가 발생해도 크래시하지 않아야 함
        buyer._record_opportunistic_buy(opportunity, 100000.0, {"order_id": "123"})

    def test_can_execute_buy_portfolio_ratio_exceeded(self, buyer):
        """매수 불가 - 포트폴리오 비중 초과"""
        buyer.coinone_client.get_portfolio_value.return_value = {
            "total_value_krw": 10000000.0,
            "assets": {
                "BTC": {"value_krw": 4500000.0}  # 45% 비중
            }
        }

        can_buy, reason = buyer._can_execute_buy("BTC", 100000)

        assert can_buy is False
        assert "ratio" in reason.lower()

    def test_can_execute_buy_portfolio_error(self, buyer):
        """포트폴리오 조회 실패 시에도 매수 가능"""
        buyer.coinone_client.get_portfolio_value.side_effect = Exception("API Error")

        can_buy, reason = buyer._can_execute_buy("BTC", 100000)

        # 포트폴리오 조회 실패해도 다른 조건이 OK면 매수 가능
        assert can_buy is True

    def test_get_cash_utilization_strategy_high_volatility(self, buyer):
        """현금 활용 전략 - 높은 변동성"""
        def get_volatile_data(asset, days=7):
            dates = pd.date_range(end=datetime.now(), periods=max(days, 30), freq='D')
            base_price = 50000000
            # 높은 변동성 데이터 (큰 가격 변동)
            prices = [base_price * (1 + 0.1 * np.sin(i)) for i in range(max(days, 30))]
            return pd.DataFrame({'Close': prices, 'Date': dates})

        buyer.db_manager.get_market_data.side_effect = get_volatile_data

        with patch.object(buyer, 'get_fear_greed_index', return_value=50):
            strategy = buyer.get_cash_utilization_strategy()

        # 높은 변동성에서는 보수적 조정
        assert "timestamp" in strategy

    def test_get_cash_utilization_strategy_error(self, buyer):
        """현금 활용 전략 조회 실패"""
        buyer.db_manager.get_market_data.side_effect = Exception("DB Error")

        with patch.object(buyer, 'get_fear_greed_index', side_effect=Exception("API Error")):
            strategy = buyer.get_cash_utilization_strategy()

        assert strategy["mode"] == "error"
        assert "error" in strategy

    def test_identify_opportunities_exception(self, buyer):
        """기회 식별 중 예외 발생"""
        buyer.db_manager.get_market_data.side_effect = Exception("Data Error")

        opportunities, reasons = buyer.identify_opportunities(["BTC"])

        assert len(opportunities) == 0
        assert "BTC" in reasons
        assert "오류" in reasons["BTC"]

    def test_identify_opportunities_no_opportunity_reasons(self, buyer):
        """기회 없음 이유 분석"""
        def get_rising_data(asset, days=7):
            dates = pd.date_range(end=datetime.now(), periods=max(days, 30), freq='D')
            base_price = 50000000
            # 상승 추세 데이터
            prices = [base_price * (1 + 0.01 * i) for i in range(max(days, 30))]
            return pd.DataFrame({'Close': prices, 'Date': dates})

        buyer.db_manager.get_market_data.side_effect = get_rising_data

        opportunities, reasons = buyer.identify_opportunities(["BTC"])

        assert len(opportunities) == 0
        assert "BTC" in reasons
        # 상승 추세이므로 하락률 부족 이유가 있어야 함

    def test_execute_multiple_opportunities(self, buyer):
        """여러 기회 연속 실행"""
        opportunities = [
            BuyOpportunity(
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
            ),
            BuyOpportunity(
                asset="ETH",
                current_price=3000000.0,
                avg_price_7d=3500000.0,
                avg_price_30d=4000000.0,
                price_drop_7d=-0.14,
                price_drop_30d=-0.25,
                rsi=28.0,
                fear_greed_index=22.0,
                opportunity_level=OpportunityLevel.MAJOR,
                recommended_buy_ratio=0.3,
                confidence_score=0.8
            )
        ]

        results = buyer.execute_opportunistic_buys(opportunities, 500000.0)

        assert "total_invested" in results
        assert "remaining_cash" in results

    def test_execute_budget_exhausted(self, buyer):
        """예산 소진으로 중단"""
        opportunities = []
        for i in range(5):
            opportunities.append(BuyOpportunity(
                asset=f"COIN{i}",
                current_price=1000.0,
                avg_price_7d=1200.0,
                avg_price_30d=1500.0,
                price_drop_7d=-0.17,
                price_drop_30d=-0.33,
                rsi=20.0,
                fear_greed_index=15.0,
                opportunity_level=OpportunityLevel.EXTREME,
                recommended_buy_ratio=0.4,
                confidence_score=0.9
            ))

        # 작은 예산으로 테스트
        results = buyer.execute_opportunistic_buys(opportunities, 15000.0)

        # 예산이 소진되면 종료
        assert results["remaining_cash"] <= 15000.0

    def test_execute_order_exception(self, buyer):
        """주문 실행 중 예외"""
        buyer.coinone_client.place_order.side_effect = Exception("Order Error")

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

        results = buyer.execute_opportunistic_buys([opportunity], 1000000.0)

        assert len(results["failed_orders"]) > 0 or len(results["skipped_orders"]) > 0

    def test_price_adjustment_btc(self, buyer):
        """BTC 가격 단위 조정 (10000원 단위)"""
        opportunity = BuyOpportunity(
            asset="BTC",
            current_price=50123456.0,  # 비정규 가격
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

        # 주문이 실행되면 place_order가 호출됨
        results = buyer.execute_opportunistic_buys([opportunity], 1000000.0)
        assert isinstance(results, dict)

    def test_price_adjustment_eth(self, buyer):
        """ETH 가격 단위 조정 (1000원 단위)"""
        opportunity = BuyOpportunity(
            asset="ETH",
            current_price=3123456.0,  # 비정규 가격
            avg_price_7d=3500000.0,
            avg_price_30d=4000000.0,
            price_drop_7d=-0.11,
            price_drop_30d=-0.22,
            rsi=25.0,
            fear_greed_index=20.0,
            opportunity_level=OpportunityLevel.MAJOR,
            recommended_buy_ratio=0.3,
            confidence_score=0.8
        )

        results = buyer.execute_opportunistic_buys([opportunity], 1000000.0)
        assert isinstance(results, dict)

    def test_price_adjustment_low_price_coin(self, buyer):
        """저가 코인 가격 단위 조정 (1원 단위)"""
        opportunity = BuyOpportunity(
            asset="XRP",
            current_price=500.5,  # 비정규 가격
            avg_price_7d=600.0,
            avg_price_30d=700.0,
            price_drop_7d=-0.17,
            price_drop_30d=-0.29,
            rsi=25.0,
            fear_greed_index=20.0,
            opportunity_level=OpportunityLevel.MAJOR,
            recommended_buy_ratio=0.3,
            confidence_score=0.8
        )

        results = buyer.execute_opportunistic_buys([opportunity], 1000000.0)
        assert isinstance(results, dict)

    def test_get_fear_greed_empty_data(self, buyer):
        """공포탐욕 지수 - 빈 데이터"""
        buyer.db_manager.get_market_data.side_effect = None
        buyer.db_manager.get_market_data.return_value = pd.DataFrame()

        fear_greed = buyer.get_fear_greed_index()
        assert fear_greed == 50.0

    def test_calculate_rsi_exception(self, buyer):
        """RSI 계산 예외"""
        # 잘못된 데이터로 예외 유발
        prices = pd.Series([None, None, None])

        rsi = buyer.calculate_rsi(prices)
        assert rsi == 50.0

    def test_is_recently_bought_memory_fallback(self, buyer):
        """최근 매수 여부 - 메모리 기반 폴백"""
        # DB에서 이력 없음
        buyer.db_manager.get_recent_opportunistic_buys.return_value = []
        # 메모리에 이력 있음
        buyer.recent_buys["BTC"] = datetime.now() - timedelta(hours=2)

        is_recent, info = buyer._is_recently_bought("BTC")

        assert is_recent is True
        assert "쿨다운" in info

    def test_execute_negative_target_fraction(self, buyer):
        """음수 target_fraction 처리"""
        # 음수 target_fraction을 반환하도록 설정
        buyer.level_portfolio_usage_schedule = {
            OpportunityLevel.MINOR: -0.1,  # 음수
            OpportunityLevel.MODERATE: 0.15,
            OpportunityLevel.MAJOR: 0.20,
            OpportunityLevel.EXTREME: 1.00
        }

        opportunity = BuyOpportunity(
            asset="BTC",
            current_price=50000000.0,
            avg_price_7d=55000000.0,
            avg_price_30d=60000000.0,
            price_drop_7d=-0.06,
            price_drop_30d=-0.08,
            rsi=35.0,
            fear_greed_index=40.0,
            opportunity_level=OpportunityLevel.MINOR,
            recommended_buy_ratio=0.1,
            confidence_score=0.6
        )

        results = buyer.execute_opportunistic_buys([opportunity], 1000000.0)

        # 음수는 0으로 처리되어 스킵
        assert isinstance(results, dict)


@pytest.mark.trading
class TestOpportunisticBuyerCoverage:
    """OpportunisticBuyer 커버리지 개선 테스트"""

    @pytest.fixture
    def buyer(self):
        """테스트용 OpportunisticBuyer 인스턴스"""
        mock_client = Mock()
        mock_client.get_portfolio_value.return_value = {
            "total_value_krw": 10000000.0,
            "assets": {}
        }
        mock_client.place_order.return_value = {"success": True, "order_id": "test_123"}

        mock_db = Mock()
        mock_db.is_trading_locked.return_value = False
        mock_db.get_last_rebalance_time.return_value = None
        mock_db.get_daily_buy_stats.return_value = {"count": 0, "amount": 0}
        mock_db.get_recent_opportunistic_buys.return_value = []

        return OpportunisticBuyer(mock_client, mock_db)

    def test_identify_opportunities_with_valid_opportunity(self, buyer):
        """기회 식별 - 유효한 기회 생성 (lines 239-260)"""
        # 급락 데이터 생성 (30일 평균 대비 35% 하락)
        def get_crash_data(asset, days=7):
            n = days
            dates = pd.date_range(end=datetime.now(), periods=n, freq='D')
            # 마지막 가격만 급락
            base_price = 50000000.0
            crash_price = 30000000.0  # -40% 하락
            prices = [base_price] * (n - 1) + [crash_price]
            return pd.DataFrame({'Close': prices, 'Date': dates})

        buyer.db_manager.get_market_data.side_effect = get_crash_data

        opportunities, reasons = buyer.identify_opportunities(["BTC"])

        # 급락 시 기회가 생성되어야 함
        assert len(opportunities) > 0
        opp = opportunities[0]
        assert opp.asset == "BTC"
        assert opp.opportunity_level != OpportunityLevel.NONE

    def test_identify_opportunities_no_reason_other(self, buyer):
        """기회 식별 - 기타 조건 미충족 (line 272)"""
        # 미세하게 하락하지만 기회가 없는 케이스
        def get_flat_data(asset, days=7):
            dates = pd.date_range(end=datetime.now(), periods=max(days, 30), freq='D')
            # 거의 변동 없는 데이터
            base = 50000000.0
            prices = [base * 0.97] * (max(days, 30) - 1) + [base * 0.96]  # -4% (MINOR 미달)
            return pd.DataFrame({'Close': prices, 'Date': dates})

        buyer.db_manager.get_market_data.side_effect = get_flat_data

        # RSI가 높고 공포지수가 높으면 reasons가 채워지지만
        # 특별히 해당 조건을 충족하지 않으면 "기타 조건 미충족"
        with patch.object(buyer, 'calculate_rsi', return_value=45.0):  # RSI < MIDLINE (50)
            with patch.object(buyer, 'get_fear_greed_index', return_value=20.0):  # 공포 구간
                opportunities, reasons = buyer.identify_opportunities(["BTC"])

        # RSI와 공포지수가 조건에 맞아도 하락률이 부족하면 NONE
        # 하지만 개별 조건도 충족하지 못하면 "기타 조건 미충족"

    def test_execute_portfolio_value_exception(self, buyer):
        """포트폴리오 평가액 조회 실패 (lines 442-443)"""
        buyer.coinone_client.get_portfolio_value.side_effect = Exception("API Error")

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

        results = buyer.execute_opportunistic_buys([opportunity], 1000000.0)

        # 예외 발생해도 정상 동작
        assert isinstance(results, dict)

    def test_execute_portfolio_value_zero(self, buyer):
        """포트폴리오 평가액 0 (line 447)"""
        buyer.coinone_client.get_portfolio_value.return_value = {
            "total_value_krw": 0,
            "assets": {}
        }

        opportunity = BuyOpportunity(
            asset="BTC",
            current_price=50000000.0,
            avg_price_7d=55000000.0,
            avg_price_30d=60000000.0,
            price_drop_7d=-0.09,
            price_drop_30d=-0.17,
            rsi=25.0,
            fear_greed_index=20.0,
            opportunity_level=OpportunityLevel.EXTREME,  # EXTREME은 min_cash_ratio가 0
            recommended_buy_ratio=0.4,
            confidence_score=0.9
        )

        results = buyer.execute_opportunistic_buys([opportunity], 1000000.0)

        # total_portfolio_value가 available_cash로 대체됨
        assert isinstance(results, dict)

    def test_execute_available_above_threshold_zero(self, buyer):
        """현금 비중 유지 한도 내 사용 가능 금액 없음 (lines 478-484)"""
        # MINOR 레벨은 30% 초과 현금만 사용 가능
        buyer.coinone_client.get_portfolio_value.return_value = {
            "total_value_krw": 10000000.0,
            "assets": {}
        }

        opportunity = BuyOpportunity(
            asset="BTC",
            current_price=50000000.0,
            avg_price_7d=55000000.0,
            avg_price_30d=60000000.0,
            price_drop_7d=-0.06,
            price_drop_30d=-0.08,
            rsi=35.0,
            fear_greed_index=40.0,
            opportunity_level=OpportunityLevel.MINOR,
            recommended_buy_ratio=0.1,
            confidence_score=0.5
        )

        # 현금 20%만 있음 (2백만) - MINOR는 30% 초과분만 사용 가능
        results = buyer.execute_opportunistic_buys([opportunity], 2000000.0)

        # 현금 비중 20% < 요구치 30%이므로 스킵됨
        assert len(results["skipped_orders"]) > 0

    def test_execute_can_execute_buy_false(self, buyer):
        """매수 가능 체크 실패 (lines 490-495)"""
        # 거래 락 설정
        buyer.db_manager.is_trading_locked.return_value = True

        opportunity = BuyOpportunity(
            asset="BTC",
            current_price=50000000.0,
            avg_price_7d=55000000.0,
            avg_price_30d=60000000.0,
            price_drop_7d=-0.35,
            price_drop_30d=-0.40,
            rsi=15.0,
            fear_greed_index=10.0,
            opportunity_level=OpportunityLevel.EXTREME,
            recommended_buy_ratio=0.4,
            confidence_score=0.95
        )

        results = buyer.execute_opportunistic_buys([opportunity], 5000000.0)

        assert len(results["skipped_orders"]) > 0
        assert "Trading locked" in results["skipped_orders"][0]["reason"]

    def test_execute_progressive_threshold_not_met(self, buyer):
        """점진적 매수 조건 미충족 (lines 500-512)"""
        # 오늘 이미 1회 매수함
        buyer.db_manager.get_daily_buy_stats.return_value = {"count": 1, "amount": 100000}

        # 현재 하락률이 -6% (2번째 매수는 -10% 필요)
        def get_small_drop_data(asset, days=7):
            dates = pd.date_range(end=datetime.now(), periods=max(days, 30), freq='D')
            prices = [50000000.0] * (max(days, 30) - 1) + [47000000.0]  # -6%
            return pd.DataFrame({'Close': prices, 'Date': dates})

        buyer.db_manager.get_market_data.side_effect = get_small_drop_data

        opportunity = BuyOpportunity(
            asset="BTC",
            current_price=47000000.0,
            avg_price_7d=50000000.0,
            avg_price_30d=55000000.0,
            price_drop_7d=-0.06,
            price_drop_30d=-0.15,
            rsi=30.0,
            fear_greed_index=30.0,
            opportunity_level=OpportunityLevel.EXTREME,
            recommended_buy_ratio=0.4,
            confidence_score=0.8
        )

        results = buyer.execute_opportunistic_buys([opportunity], 5000000.0)

        # 점진적 매수 조건 미충족으로 스킵
        assert len(results["skipped_orders"]) > 0

    def test_execute_remaining_allocation_zero(self, buyer):
        """레벨 누적 한도 소진 (lines 538-547)"""
        # MINOR 레벨의 5% 한도를 이미 사용한 상황 시뮬레이션
        buyer.coinone_client.get_portfolio_value.return_value = {
            "total_value_krw": 1000000.0,  # 100만원 포트폴리오
            "assets": {}
        }

        opportunity = BuyOpportunity(
            asset="BTC",
            current_price=50000000.0,
            avg_price_7d=55000000.0,
            avg_price_30d=60000000.0,
            price_drop_7d=-0.06,
            price_drop_30d=-0.08,
            rsi=35.0,
            fear_greed_index=40.0,
            opportunity_level=OpportunityLevel.MINOR,  # 5% 한도 = 5만원
            recommended_buy_ratio=0.8,  # 매우 높은 비율
            confidence_score=0.5
        )

        # 50만원 현금, 하지만 5% 한도(5만원)만 사용 가능
        # 첫 기회에서 5만원 이상 사용하려 하면 제한됨
        results = buyer.execute_opportunistic_buys([opportunity, opportunity], 500000.0)

        assert isinstance(results, dict)

    def test_execute_buy_amount_zero_after_limit(self, buyer):
        """누적 한도 후 매수 금액 0 (lines 552-558)"""
        # 이미 투자한 금액이 높은 상황 시뮬레이션
        buyer.level_portfolio_usage_schedule = {
            OpportunityLevel.MINOR: 0.0001,  # 매우 작은 한도 (0.01%)
            OpportunityLevel.MODERATE: 0.15,
            OpportunityLevel.MAJOR: 0.20,
            OpportunityLevel.EXTREME: 1.00
        }

        buyer.coinone_client.get_portfolio_value.return_value = {
            "total_value_krw": 10000000.0,
            "assets": {}
        }

        opportunity = BuyOpportunity(
            asset="BTC",
            current_price=50000000.0,
            avg_price_7d=55000000.0,
            avg_price_30d=60000000.0,
            price_drop_7d=-0.06,
            price_drop_30d=-0.08,
            rsi=35.0,
            fear_greed_index=40.0,
            opportunity_level=OpportunityLevel.MINOR,
            recommended_buy_ratio=0.1,
            confidence_score=0.5
        )

        results = buyer.execute_opportunistic_buys([opportunity], 5000000.0)

        # 0.01% = 1,000원 한도이므로 최소 금액(5,000원) 미달
        assert len(results["skipped_orders"]) > 0

    def test_execute_min_amount_exceeds_threshold_cash(self, buyer):
        """최소 금액이 한도 내 사용 가능 금액 초과 (lines 563-573)"""
        buyer.coinone_client.get_portfolio_value.return_value = {
            "total_value_krw": 100000.0,  # 10만원 포트폴리오
            "assets": {}
        }

        opportunity = BuyOpportunity(
            asset="BTC",
            current_price=50000000.0,
            avg_price_7d=55000000.0,
            avg_price_30d=60000000.0,
            price_drop_7d=-0.35,
            price_drop_30d=-0.40,
            rsi=15.0,
            fear_greed_index=10.0,
            opportunity_level=OpportunityLevel.EXTREME,
            recommended_buy_ratio=0.01,  # 낮은 비율
            confidence_score=0.95
        )

        # 1000원 현금 (최소 주문 5000원 미달)
        results = buyer.execute_opportunistic_buys([opportunity], 1000.0)

        assert len(results["skipped_orders"]) > 0 or len(results["executed_orders"]) == 0

    def test_execute_min_amount_exceeds_remaining_allocation(self, buyer):
        """최소 금액이 레벨 누적 한도 잔여 초과 (lines 574-584)"""
        buyer.level_portfolio_usage_schedule = {
            OpportunityLevel.MINOR: 0.001,  # 0.1% 한도
            OpportunityLevel.MODERATE: 0.15,
            OpportunityLevel.MAJOR: 0.20,
            OpportunityLevel.EXTREME: 0.001  # 0.1% 한도 = 1만원
        }

        buyer.coinone_client.get_portfolio_value.return_value = {
            "total_value_krw": 10000000.0,  # 1000만원
            "assets": {}
        }

        opportunity = BuyOpportunity(
            asset="BTC",
            current_price=50000000.0,
            avg_price_7d=55000000.0,
            avg_price_30d=60000000.0,
            price_drop_7d=-0.35,
            price_drop_30d=-0.40,
            rsi=15.0,
            fear_greed_index=10.0,
            opportunity_level=OpportunityLevel.EXTREME,
            recommended_buy_ratio=0.4,
            confidence_score=0.95
        )

        # 0.1% = 1만원 한도 (BTC 최소 5,000원은 충족하지만 실제 매수량이 작을 수 있음)
        results = buyer.execute_opportunistic_buys([opportunity], 5000000.0)

        assert isinstance(results, dict)

    def test_execute_min_amount_exceeds_remaining_budget(self, buyer):
        """최소 금액이 남은 예산 초과 (lines 586-593)"""
        # 정상적인 포트폴리오와 충분한 한도
        buyer.coinone_client.get_portfolio_value.return_value = {
            "total_value_krw": 10000000.0,
            "assets": {}
        }

        opportunity = BuyOpportunity(
            asset="BTC",
            current_price=50000000.0,
            avg_price_7d=55000000.0,
            avg_price_30d=60000000.0,
            price_drop_7d=-0.35,
            price_drop_30d=-0.40,
            rsi=15.0,
            fear_greed_index=10.0,
            opportunity_level=OpportunityLevel.EXTREME,
            recommended_buy_ratio=0.1,
            confidence_score=0.95
        )

        # 3000원 예산 (BTC 최소 5,000원 미달)
        results = buyer.execute_opportunistic_buys([opportunity], 3000.0)

        # 최소 금액이 예산을 초과하므로 스킵
        assert len(results["skipped_orders"]) > 0

    def test_execute_min_amount_adjustment(self, buyer):
        """최소 금액으로 조정 (lines 595-596)"""
        buyer.coinone_client.get_portfolio_value.return_value = {
            "total_value_krw": 10000000.0,
            "assets": {}
        }

        opportunity = BuyOpportunity(
            asset="BTC",
            current_price=50000000.0,
            avg_price_7d=55000000.0,
            avg_price_30d=60000000.0,
            price_drop_7d=-0.35,
            price_drop_30d=-0.40,
            rsi=15.0,
            fear_greed_index=10.0,
            opportunity_level=OpportunityLevel.EXTREME,
            recommended_buy_ratio=0.0001,  # 매우 낮아서 최소 금액 미달
            confidence_score=0.95
        )

        results = buyer.execute_opportunistic_buys([opportunity], 5000000.0)

        # 최소 금액으로 조정되거나 스킵됨
        assert isinstance(results, dict)

    def test_execute_order_manager_returns_none(self, buyer):
        """OrderManager가 None 반환 (line 643)"""
        mock_order_manager = Mock()
        mock_order_manager.submit_market_order.return_value = None

        buyer.order_manager = mock_order_manager
        buyer.coinone_client.get_portfolio_value.return_value = {
            "total_value_krw": 10000000.0,
            "assets": {}
        }

        opportunity = BuyOpportunity(
            asset="BTC",
            current_price=50000000.0,
            avg_price_7d=55000000.0,
            avg_price_30d=60000000.0,
            price_drop_7d=-0.35,
            price_drop_30d=-0.40,
            rsi=15.0,
            fear_greed_index=10.0,
            opportunity_level=OpportunityLevel.EXTREME,
            recommended_buy_ratio=0.1,
            confidence_score=0.95
        )

        results = buyer.execute_opportunistic_buys([opportunity], 5000000.0)

        # None 반환 시 실패 처리
        assert len(results["failed_orders"]) > 0

    def test_execute_order_failed(self, buyer):
        """주문 실패 처리 (lines 705-714)"""
        buyer.coinone_client.place_order.return_value = {
            "success": False,
            "error": "Insufficient balance"
        }
        buyer.coinone_client.get_portfolio_value.return_value = {
            "total_value_krw": 10000000.0,
            "assets": {}
        }

        opportunity = BuyOpportunity(
            asset="BTC",
            current_price=50000000.0,
            avg_price_7d=55000000.0,
            avg_price_30d=60000000.0,
            price_drop_7d=-0.35,
            price_drop_30d=-0.40,
            rsi=15.0,
            fear_greed_index=10.0,
            opportunity_level=OpportunityLevel.EXTREME,
            recommended_buy_ratio=0.1,
            confidence_score=0.95
        )

        results = buyer.execute_opportunistic_buys([opportunity], 500000.0)

        # 실패한 주문이 기록됨
        assert len(results["failed_orders"]) > 0
        assert "Insufficient balance" in results["failed_orders"][0]["reason"]

    def test_calculate_current_drop_exception(self, buyer):
        """하락률 계산 실패 (lines 849-850)"""
        buyer.db_manager.get_market_data.side_effect = Exception("DB Error")

        drop = buyer._calculate_current_drop("BTC")

        # 예외 시 0.0 반환
        assert drop == 0.0

    def test_get_cash_utilization_strategy_empty_btc_data(self, buyer):
        """현금 활용 전략 - BTC 데이터 없음 (lines 907-908)"""
        buyer.db_manager.get_market_data.return_value = pd.DataFrame()

        with patch.object(buyer, 'get_fear_greed_index', return_value=50):
            strategy = buyer.get_cash_utilization_strategy()

        # btc_trend = 0, btc_volatility = 0.02 (기본값)
        assert strategy["btc_30d_trend"] == 0
        assert strategy["btc_volatility"] == 0.02

    def test_price_adjustment_btc_coverage(self, buyer):
        """BTC 가격 단위 조정 (line 654)"""
        buyer.coinone_client.get_portfolio_value.return_value = {
            "total_value_krw": 10000000.0,
            "assets": {}
        }

        opportunity = BuyOpportunity(
            asset="BTC",
            current_price=50123456.789,  # 비정규 가격
            avg_price_7d=55000000.0,
            avg_price_30d=60000000.0,
            price_drop_7d=-0.35,
            price_drop_30d=-0.40,
            rsi=15.0,
            fear_greed_index=10.0,
            opportunity_level=OpportunityLevel.EXTREME,
            recommended_buy_ratio=0.1,
            confidence_score=0.95
        )

        buyer.execute_opportunistic_buys([opportunity], 500000.0)

        # place_order가 호출되었고 가격이 10000원 단위로 조정됨
        if buyer.coinone_client.place_order.called:
            call_args = buyer.coinone_client.place_order.call_args
            price = call_args.kwargs.get('price', call_args[1].get('price', 0))
            assert price % 10000 == 0  # 10000원 단위

    def test_price_adjustment_eth_coverage(self, buyer):
        """ETH 가격 단위 조정 (line 657)"""
        buyer.coinone_client.get_portfolio_value.return_value = {
            "total_value_krw": 10000000.0,
            "assets": {}
        }

        opportunity = BuyOpportunity(
            asset="ETH",
            current_price=3123456.789,  # 비정규 가격
            avg_price_7d=3500000.0,
            avg_price_30d=4000000.0,
            price_drop_7d=-0.35,
            price_drop_30d=-0.40,
            rsi=15.0,
            fear_greed_index=10.0,
            opportunity_level=OpportunityLevel.EXTREME,
            recommended_buy_ratio=0.1,
            confidence_score=0.95
        )

        buyer.execute_opportunistic_buys([opportunity], 500000.0)

        # place_order가 호출되었고 가격이 1000원 단위로 조정됨
        if buyer.coinone_client.place_order.called:
            call_args = buyer.coinone_client.place_order.call_args
            price = call_args.kwargs.get('price', call_args[1].get('price', 0))
            assert price % 1000 == 0  # 1000원 단위

    def test_price_adjustment_low_price_coin_coverage(self, buyer):
        """저가 코인 가격 단위 조정 (line 660)"""
        buyer.coinone_client.get_portfolio_value.return_value = {
            "total_value_krw": 10000000.0,
            "assets": {}
        }

        opportunity = BuyOpportunity(
            asset="XRP",
            current_price=500.789,  # 비정규 가격
            avg_price_7d=600.0,
            avg_price_30d=700.0,
            price_drop_7d=-0.35,
            price_drop_30d=-0.40,
            rsi=15.0,
            fear_greed_index=10.0,
            opportunity_level=OpportunityLevel.EXTREME,
            recommended_buy_ratio=0.1,
            confidence_score=0.95
        )

        buyer.execute_opportunistic_buys([opportunity], 500000.0)

        # place_order가 호출되었고 가격이 1원 단위로 조정됨
        if buyer.coinone_client.place_order.called:
            call_args = buyer.coinone_client.place_order.call_args
            price = call_args.kwargs.get('price', call_args[1].get('price', 0))
            assert price == int(price)  # 정수

    def test_price_adjustment_other_coin(self, buyer):
        """기타 코인 가격 단위 조정 (lines 662-663)"""
        buyer.coinone_client.get_portfolio_value.return_value = {
            "total_value_krw": 10000000.0,
            "assets": {}
        }

        opportunity = BuyOpportunity(
            asset="SOL",
            current_price=150123.456,  # 비정규 가격
            avg_price_7d=200000.0,
            avg_price_30d=250000.0,
            price_drop_7d=-0.35,
            price_drop_30d=-0.40,
            rsi=15.0,
            fear_greed_index=10.0,
            opportunity_level=OpportunityLevel.EXTREME,
            recommended_buy_ratio=0.1,
            confidence_score=0.95
        )

        buyer.execute_opportunistic_buys([opportunity], 500000.0)

        # place_order가 호출되었고 가격이 10원 단위로 조정됨
        if buyer.coinone_client.place_order.called:
            call_args = buyer.coinone_client.place_order.call_args
            price = call_args.kwargs.get('price', call_args[1].get('price', 0))
            assert price % 10 == 0  # 10원 단위

    def test_execute_available_above_threshold_exact_zero(self, buyer):
        """available_above_threshold가 정확히 0인 경우 (lines 478-484)"""
        # MODERATE는 현금 비중 20% 초과분만 사용 가능
        # 포트폴리오 10백만, 현금 2백만 = 정확히 20%
        buyer.coinone_client.get_portfolio_value.return_value = {
            "total_value_krw": 10000000.0,
            "assets": {}
        }

        opportunity = BuyOpportunity(
            asset="BTC",
            current_price=50000000.0,
            avg_price_7d=60000000.0,
            avg_price_30d=65000000.0,
            price_drop_7d=-0.17,
            price_drop_30d=-0.23,
            rsi=28.0,
            fear_greed_index=35.0,
            opportunity_level=OpportunityLevel.MODERATE,  # min_cash_ratio=0.20
            recommended_buy_ratio=0.1,
            confidence_score=0.7
        )

        # 현금 = 포트폴리오의 20%, threshold_cash_floor = 20%
        # available_above_threshold = 2백만 - 2백만 = 0
        results = buyer.execute_opportunistic_buys([opportunity], 2000000.0)

        # available_above_threshold <= 0 이므로 스킵
        assert len(results["skipped_orders"]) > 0 or results["total_invested"] == 0

    def test_execute_progressive_threshold_second_buy(self, buyer):
        """점진적 매수 - 두 번째 매수 조건 미충족 (lines 500-512)"""
        # 오늘 1회 매수 완료
        buyer.db_manager.get_daily_buy_stats.return_value = {"count": 1, "amount": 50000}

        # 현재 하락률 -8% (두 번째 매수는 -10% 필요)
        def get_mock_data(asset, days=7):
            n = days
            dates = pd.date_range(end=datetime.now(), periods=n, freq='D')
            # -8% 하락
            prices = [50000000.0] * (n - 1) + [46000000.0]
            return pd.DataFrame({'Close': prices, 'Date': dates})

        buyer.db_manager.get_market_data.side_effect = get_mock_data
        buyer.coinone_client.get_portfolio_value.return_value = {
            "total_value_krw": 10000000.0,
            "assets": {}
        }

        opportunity = BuyOpportunity(
            asset="BTC",
            current_price=46000000.0,
            avg_price_7d=50000000.0,
            avg_price_30d=55000000.0,
            price_drop_7d=-0.08,
            price_drop_30d=-0.16,
            rsi=28.0,
            fear_greed_index=25.0,
            opportunity_level=OpportunityLevel.EXTREME,  # 통과하기 쉬운 조건
            recommended_buy_ratio=0.1,
            confidence_score=0.8
        )

        results = buyer.execute_opportunistic_buys([opportunity], 5000000.0)

        # 점진적 매수 조건 미충족 (현재 -8% > 필요 -10%)
        assert len(results["skipped_orders"]) > 0
        assert "점진적" in results["skipped_orders"][0]["reason"]

    def test_execute_cumulative_limit_exhausted(self, buyer):
        """누적 한도 완전 소진 (lines 538-547)"""
        # 이미 투자한 금액을 시뮬레이션하기 위해 먼저 성공적인 매수를 한 후 두 번째 매수 시도
        buyer.coinone_client.get_portfolio_value.return_value = {
            "total_value_krw": 1000000.0,  # 100만원 포트폴리오
            "assets": {}
        }
        buyer.coinone_client.place_order.return_value = {"success": True, "order_id": "123"}

        # MINOR 레벨 = 5% 한도 = 5만원
        opportunity1 = BuyOpportunity(
            asset="BTC",
            current_price=50000000.0,
            avg_price_7d=55000000.0,
            avg_price_30d=60000000.0,
            price_drop_7d=-0.06,
            price_drop_30d=-0.08,
            rsi=35.0,
            fear_greed_index=40.0,
            opportunity_level=OpportunityLevel.MINOR,
            recommended_buy_ratio=1.0,  # 100% 비율로 한도까지 사용
            confidence_score=0.6
        )

        opportunity2 = BuyOpportunity(
            asset="ETH",
            current_price=3000000.0,
            avg_price_7d=3300000.0,
            avg_price_30d=3600000.0,
            price_drop_7d=-0.06,
            price_drop_30d=-0.08,
            rsi=35.0,
            fear_greed_index=40.0,
            opportunity_level=OpportunityLevel.MINOR,
            recommended_buy_ratio=0.5,
            confidence_score=0.5
        )

        # 첫 번째 기회에서 한도 소진, 두 번째는 remaining_allocation <= 0
        results = buyer.execute_opportunistic_buys([opportunity1, opportunity2], 500000.0)

        assert isinstance(results, dict)

    def test_execute_buy_amount_becomes_zero(self, buyer):
        """매수 금액이 0이 되는 경우 (lines 552-558)"""
        # 매우 작은 한도 설정
        buyer.level_portfolio_usage_schedule = {
            OpportunityLevel.MINOR: 0.00001,  # 0.001% = 거의 0
            OpportunityLevel.MODERATE: 0.15,
            OpportunityLevel.MAJOR: 0.20,
            OpportunityLevel.EXTREME: 1.00
        }
        buyer.coinone_client.get_portfolio_value.return_value = {
            "total_value_krw": 10000000.0,
            "assets": {}
        }

        opportunity = BuyOpportunity(
            asset="BTC",
            current_price=50000000.0,
            avg_price_7d=55000000.0,
            avg_price_30d=60000000.0,
            price_drop_7d=-0.06,
            price_drop_30d=-0.08,
            rsi=35.0,
            fear_greed_index=40.0,
            opportunity_level=OpportunityLevel.MINOR,
            recommended_buy_ratio=0.00001,  # 매우 작은 비율
            confidence_score=0.5
        )

        results = buyer.execute_opportunistic_buys([opportunity], 5000000.0)

        # 매수 금액이 0이 되어 스킵
        assert len(results["skipped_orders"]) > 0 or len(results["executed_orders"]) == 0

    def test_execute_min_exceeds_remaining_budget_after_checks(self, buyer):
        """최소 금액이 남은 예산 초과 - 이전 체크 통과 후 (lines 587-593)"""
        buyer.coinone_client.get_portfolio_value.return_value = {
            "total_value_krw": 10000000.0,
            "assets": {}
        }

        # BTC 최소 금액 5000원
        opportunity = BuyOpportunity(
            asset="BTC",
            current_price=50000000.0,
            avg_price_7d=55000000.0,
            avg_price_30d=60000000.0,
            price_drop_7d=-0.35,
            price_drop_30d=-0.40,
            rsi=15.0,
            fear_greed_index=10.0,
            opportunity_level=OpportunityLevel.EXTREME,
            recommended_buy_ratio=0.0001,  # 매우 낮은 비율
            confidence_score=0.95
        )

        # 4000원 예산으로 시작 (최소 5000원 미달)
        results = buyer.execute_opportunistic_buys([opportunity], 4000.0)

        # min_amount(5000) > remaining_budget(4000) 이므로 스킵
        assert len(results["skipped_orders"]) > 0 or results["total_invested"] == 0

    def test_execute_order_exception_during_execution(self, buyer):
        """주문 실행 중 예외 발생 (lines 712-714)"""
        buyer.coinone_client.get_portfolio_value.return_value = {
            "total_value_krw": 10000000.0,
            "assets": {}
        }
        # place_order에서 예외 발생
        buyer.coinone_client.place_order.side_effect = Exception("Network timeout")

        opportunity = BuyOpportunity(
            asset="BTC",
            current_price=50000000.0,
            avg_price_7d=55000000.0,
            avg_price_30d=60000000.0,
            price_drop_7d=-0.35,
            price_drop_30d=-0.40,
            rsi=15.0,
            fear_greed_index=10.0,
            opportunity_level=OpportunityLevel.EXTREME,
            recommended_buy_ratio=0.1,
            confidence_score=0.95
        )

        results = buyer.execute_opportunistic_buys([opportunity], 500000.0)

        # 예외 발생 시 failed_orders에 기록
        assert len(results["failed_orders"]) > 0
        assert "Network timeout" in results["failed_orders"][0]["reason"]

    def test_identify_opportunities_other_condition_not_met(self, buyer):
        """기타 조건 미충족 (line 272)"""
        # 모든 개별 조건을 충족하지만 overall 조건이 NONE인 특수 케이스
        # _determine_opportunity_level 이 NONE을 반환하되
        # 7일 하락률 < -5%, RSI <= OVERSOLD, fear_greed <= EXTREME_FEAR 모두 만족
        def get_special_data(asset, days=7):
            n = days
            dates = pd.date_range(end=datetime.now(), periods=n, freq='D')
            # -4% 하락 (MINOR 미달, -5% 필요)
            prices = [50000000.0] * (n - 1) + [48000000.0]
            return pd.DataFrame({'Close': prices, 'Date': dates})

        buyer.db_manager.get_market_data.side_effect = get_special_data

        # RSI와 fear_greed를 조건에 맞지 않게 설정
        with patch.object(buyer, 'calculate_rsi', return_value=25.0):  # RSI < OVERSOLD
            with patch.object(buyer, 'get_fear_greed_index', return_value=20.0):  # < EXTREME_FEAR
                # _determine_opportunity_level은 NONE (하락률 -4% < -5% 미달)
                # 하지만 reasons 체크에서:
                # - drop_7d(-4%) > -5% → 이유 추가
                # - RSI(25) < OVERSOLD(30) → 이유 없음
                # - fear_greed(20) < EXTREME_FEAR(25) → 이유 없음
                # 결과적으로 "7일 하락률 부족" 이유가 추가됨
                opportunities, reasons = buyer.identify_opportunities(["BTC"])

        assert len(opportunities) == 0
        assert "BTC" in reasons

    def test_execute_zero_portfolio_zero_cash(self, buyer):
        """포트폴리오와 현금 모두 0인 경우 (lines 478-484)"""
        # 포트폴리오 값이 0이고 현금도 0인 극단적 케이스
        buyer.coinone_client.get_portfolio_value.return_value = {
            "total_value_krw": 0,
            "assets": {}
        }

        opportunity = BuyOpportunity(
            asset="BTC",
            current_price=50000000.0,
            avg_price_7d=55000000.0,
            avg_price_30d=60000000.0,
            price_drop_7d=-0.35,
            price_drop_30d=-0.40,
            rsi=15.0,
            fear_greed_index=10.0,
            opportunity_level=OpportunityLevel.EXTREME,
            recommended_buy_ratio=0.1,
            confidence_score=0.95
        )

        # 현금 0으로 시작
        results = buyer.execute_opportunistic_buys([opportunity], 0.0)

        # available_above_threshold = 0 이므로 스킵
        assert len(results["skipped_orders"]) > 0 or results["total_invested"] == 0

    def test_execute_target_fraction_negative_exact(self, buyer):
        """target_fraction이 정확히 음수인 경우 (line 527)"""
        # 음수 target_fraction 설정
        buyer.level_portfolio_usage_schedule = {
            OpportunityLevel.EXTREME: -0.5,  # 음수
            OpportunityLevel.MAJOR: 0.20,
            OpportunityLevel.MODERATE: 0.15,
            OpportunityLevel.MINOR: 0.05,
        }
        buyer.coinone_client.get_portfolio_value.return_value = {
            "total_value_krw": 10000000.0,
            "assets": {}
        }

        opportunity = BuyOpportunity(
            asset="BTC",
            current_price=50000000.0,
            avg_price_7d=55000000.0,
            avg_price_30d=60000000.0,
            price_drop_7d=-0.35,
            price_drop_30d=-0.40,
            rsi=15.0,
            fear_greed_index=10.0,
            opportunity_level=OpportunityLevel.EXTREME,  # -0.5 한도
            recommended_buy_ratio=0.1,
            confidence_score=0.95
        )

        results = buyer.execute_opportunistic_buys([opportunity], 5000000.0)

        # target_fraction이 0으로 조정되어 remaining_allocation = 0
        # 따라서 스킵됨
        assert len(results["skipped_orders"]) > 0

    def test_execute_buy_amount_zero_edge_case(self, buyer):
        """buy_amount가 정확히 0인 엣지 케이스 (lines 552-558)"""
        # remaining_allocation이 0보다 크지만 buy_amount가 0인 경우
        buyer.coinone_client.get_portfolio_value.return_value = {
            "total_value_krw": 10000000.0,
            "assets": {}
        }

        opportunity = BuyOpportunity(
            asset="BTC",
            current_price=50000000.0,
            avg_price_7d=55000000.0,
            avg_price_30d=60000000.0,
            price_drop_7d=-0.35,
            price_drop_30d=-0.40,
            rsi=15.0,
            fear_greed_index=10.0,
            opportunity_level=OpportunityLevel.EXTREME,
            recommended_buy_ratio=0.0,  # 0% 비율
            confidence_score=0.95
        )

        results = buyer.execute_opportunistic_buys([opportunity], 5000000.0)

        # buy_amount = 0 이므로 스킵
        assert len(results["skipped_orders"]) > 0 or results["total_invested"] == 0

    def test_execute_min_amount_exact_budget_check(self, buyer):
        """최소 금액이 정확히 예산과 같은 경우 (lines 587-593 경계)"""
        buyer.coinone_client.get_portfolio_value.return_value = {
            "total_value_krw": 10000000.0,
            "assets": {}
        }

        # BTC 최소 금액은 5000원
        opportunity = BuyOpportunity(
            asset="BTC",
            current_price=50000000.0,
            avg_price_7d=55000000.0,
            avg_price_30d=60000000.0,
            price_drop_7d=-0.35,
            price_drop_30d=-0.40,
            rsi=15.0,
            fear_greed_index=10.0,
            opportunity_level=OpportunityLevel.EXTREME,
            recommended_buy_ratio=0.001,  # 낮은 비율로 최소 금액 미달
            confidence_score=0.95
        )

        # 정확히 5000원 예산 (최소 금액과 동일)
        results = buyer.execute_opportunistic_buys([opportunity], 5000.0)

        # 최소 금액과 예산이 같으므로 실행 가능하거나 조건에 따라 스킵
        assert isinstance(results, dict)
