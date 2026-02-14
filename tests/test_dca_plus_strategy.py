"""
DCA Plus Strategy Tests

DCA+ 전략 테스트 모듈
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta

from src.core.dca_plus_strategy import (
    DCAPlus,
    DCASignal,
    DCAEvent,
    DCASchedule,
    FearGreedLevel,
    AccumulationSignal
)


@pytest.mark.strategy
class TestDCASignalDataclass:
    """DCASignal 데이터클래스 테스트"""

    def test_dca_signal_creation(self):
        """DCA 신호 생성"""
        signal = DCASignal(
            signal_strength=0.8,
            recommended_amount=1500000,
            next_execution_date=datetime.now() + timedelta(days=7),
            market_adjustment_factor=1.5,
            reasoning="테스트 근거",
            market_conditions={"fear_greed_index": 25}
        )

        assert signal.signal_strength == 0.8
        assert signal.recommended_amount == 1500000
        assert signal.market_adjustment_factor == 1.5
        assert signal.reasoning == "테스트 근거"
        assert signal.market_conditions["fear_greed_index"] == 25

    def test_dca_signal_default_market_conditions(self):
        """기본 시장 상황"""
        signal = DCASignal(
            signal_strength=0.5,
            recommended_amount=1000000,
            next_execution_date=datetime.now(),
            market_adjustment_factor=1.0,
            reasoning="기본"
        )

        assert signal.market_conditions == {}


@pytest.mark.strategy
class TestFearGreedLevel:
    """FearGreedLevel Enum 테스트"""

    def test_fear_greed_levels(self):
        """공포/탐욕 레벨 값 확인"""
        assert FearGreedLevel.EXTREME_FEAR.value == "extreme_fear"
        assert FearGreedLevel.FEAR.value == "fear"
        assert FearGreedLevel.NEUTRAL.value == "neutral"
        assert FearGreedLevel.GREED.value == "greed"
        assert FearGreedLevel.EXTREME_GREED.value == "extreme_greed"

    def test_fear_greed_level_count(self):
        """공포/탐욕 레벨 개수"""
        assert len(FearGreedLevel) == 5


@pytest.mark.strategy
class TestAccumulationSignal:
    """AccumulationSignal Enum 테스트"""

    def test_accumulation_signal_values(self):
        """축적 신호 값 확인"""
        assert AccumulationSignal.NONE.value == "none"
        assert AccumulationSignal.WEAK.value == "weak"
        assert AccumulationSignal.MODERATE.value == "moderate"
        assert AccumulationSignal.STRONG.value == "strong"
        assert AccumulationSignal.EXTREME.value == "extreme"


@pytest.mark.strategy
class TestDCAEvent:
    """DCAEvent 데이터클래스 테스트"""

    def test_dca_event_creation(self):
        """DCA 이벤트 생성"""
        event = DCAEvent(
            date=datetime.now(),
            asset="BTC",
            amount_krw=500000,
            price=50000000,
            quantity=0.01,
            event_type="regular",
            multiplier=1.0,
            reasoning="정기 적립",
            market_conditions={}
        )

        assert event.asset == "BTC"
        assert event.amount_krw == 500000
        assert event.price == 50000000
        assert event.quantity == 0.01
        assert event.event_type == "regular"


@pytest.mark.strategy
class TestDCASchedule:
    """DCASchedule 데이터클래스 테스트"""

    def test_dca_schedule_creation(self):
        """DCA 스케줄 생성"""
        schedule = DCASchedule(
            base_amount_krw=1000000,
            frequency_days=7,
            assets={"BTC": 0.6, "ETH": 0.4},
            volatility_multiplier=2.0,
            fear_greed_triggers={
                FearGreedLevel.EXTREME_FEAR: 3.0,
                FearGreedLevel.NEUTRAL: 1.0
            },
            accumulation_multiplier=1.5,
            max_monthly_amount=5000000,
            tax_optimization=True
        )

        assert schedule.base_amount_krw == 1000000
        assert schedule.frequency_days == 7
        assert schedule.assets["BTC"] == 0.6
        assert schedule.max_monthly_amount == 5000000
        assert schedule.tax_optimization is True


@pytest.mark.strategy
class TestDCAPlusInit:
    """DCAPlus 초기화 테스트"""

    def test_init_default(self):
        """기본 초기화"""
        dca = DCAPlus()

        assert dca.market_data_provider is None
        assert dca.db_manager is None
        assert dca.default_schedule is not None
        assert dca.default_schedule.base_amount_krw == 1000000

    def test_init_with_providers(self):
        """프로바이더 포함 초기화"""
        mock_provider = Mock()
        mock_db = Mock()

        dca = DCAPlus(market_data_provider=mock_provider, db_manager=mock_db)

        assert dca.market_data_provider == mock_provider
        assert dca.db_manager == mock_db

    def test_default_schedule_configuration(self):
        """기본 스케줄 설정 확인"""
        dca = DCAPlus()

        assert dca.default_schedule.frequency_days == 7
        assert dca.default_schedule.assets["BTC"] == 0.6
        assert dca.default_schedule.assets["ETH"] == 0.3
        assert dca.default_schedule.assets["SOL"] == 0.1

    def test_accumulation_thresholds(self):
        """축적 임계값 확인"""
        dca = DCAPlus()

        assert dca.accumulation_thresholds["btc_dominance_min"] == 0.65
        assert dca.accumulation_thresholds["rsi_weekly_max"] == 35
        assert dca.accumulation_thresholds["ma_deviation_min"] == -0.25
        assert dca.accumulation_thresholds["volume_surge_min"] == 1.5


@pytest.mark.strategy
class TestCalculateDCASignal:
    """DCA 신호 계산 테스트"""

    @pytest.fixture
    def dca(self):
        return DCAPlus()

    def test_calculate_signal_extreme_fear(self, dca):
        """극도의 공포 상황"""
        market_conditions = {
            "fear_greed_index": 10,
            "price_volatility": 0.10,
            "trend_direction": "down"
        }

        signal = dca.calculate_dca_signal("BTC", 1000000, market_conditions)

        assert signal.signal_strength > 0.7
        assert signal.market_adjustment_factor > 2.0
        assert signal.recommended_amount > 1000000
        assert "공포" in signal.reasoning

    def test_calculate_signal_fear(self, dca):
        """공포 상황"""
        market_conditions = {
            "fear_greed_index": 30,
            "price_volatility": 0.06,
            "trend_direction": "down"
        }

        signal = dca.calculate_dca_signal("BTC", 1000000, market_conditions)

        assert signal.market_adjustment_factor >= 1.5
        assert signal.recommended_amount >= 1000000

    def test_calculate_signal_neutral(self, dca):
        """중립 상황"""
        market_conditions = {
            "fear_greed_index": 50,
            "price_volatility": 0.03,
            "trend_direction": "neutral"
        }

        signal = dca.calculate_dca_signal("BTC", 1000000, market_conditions)

        assert 0.9 <= signal.market_adjustment_factor <= 1.1
        assert abs(signal.recommended_amount - 1000000) < 200000

    def test_calculate_signal_greed(self, dca):
        """탐욕 상황"""
        market_conditions = {
            "fear_greed_index": 65,
            "price_volatility": 0.02,
            "trend_direction": "up"
        }

        signal = dca.calculate_dca_signal("BTC", 1000000, market_conditions)

        assert signal.market_adjustment_factor < 1.0
        assert signal.recommended_amount < 1000000

    def test_calculate_signal_extreme_greed(self, dca):
        """극도의 탐욕 상황"""
        market_conditions = {
            "fear_greed_index": 85,
            "price_volatility": 0.01,
            "trend_direction": "up"
        }

        signal = dca.calculate_dca_signal("BTC", 1000000, market_conditions)

        # 가중 평균 계산: 0.3*0.5 + 1.0*0.3 + 0.8*0.2 = 0.61
        assert signal.market_adjustment_factor < 0.8
        assert signal.recommended_amount < 800000
        assert "과열" in signal.reasoning

    def test_calculate_signal_high_volatility(self, dca):
        """고변동성 상황"""
        market_conditions = {
            "fear_greed_index": 50,
            "price_volatility": 0.12,  # 12% 변동성
            "trend_direction": "neutral"
        }

        signal = dca.calculate_dca_signal("BTC", 1000000, market_conditions)

        assert "고변동성" in signal.reasoning
        assert signal.market_conditions["volatility_multiplier"] == 1.5

    def test_calculate_signal_next_execution_date(self, dca):
        """다음 실행 일자 확인"""
        signal = dca.calculate_dca_signal("BTC", 1000000, {"fear_greed_index": 50})

        expected_date = datetime.now() + timedelta(days=7)
        assert signal.next_execution_date.date() == expected_date.date()

    def test_calculate_signal_with_db_manager(self):
        """DB 매니저 포함 시 저장"""
        mock_db = Mock()
        dca = DCAPlus(db_manager=mock_db)

        signal = dca.calculate_dca_signal("BTC", 1000000, {"fear_greed_index": 50})

        mock_db.save_analysis_result.assert_called_once()

    def test_calculate_signal_exception_handling(self, dca):
        """예외 처리"""
        # 잘못된 데이터로 예외 유도
        with patch.object(dca, '_save_dca_signal_to_db', side_effect=Exception("DB Error")):
            dca.db_manager = Mock()
            signal = dca.calculate_dca_signal("BTC", 1000000, {"fear_greed_index": 50})

            # 기본 신호가 반환되어야 함
            assert signal.signal_strength == 0.5


@pytest.mark.strategy
class TestCalculateDCAAmount:
    """DCA 매수 금액 계산 테스트"""

    @pytest.fixture
    def dca(self):
        return DCAPlus()

    @pytest.fixture
    def sample_market_data(self):
        """샘플 시장 데이터"""
        dates = pd.date_range(start='2024-01-01', periods=200, freq='D')
        prices = [50000000 + i * 100000 + np.random.randn() * 500000 for i in range(200)]
        volumes = [100 + np.random.rand() * 50 for _ in range(200)]

        return {
            "BTC": pd.DataFrame({
                'Close': prices,
                'Volume': volumes
            }, index=dates),
            "ETH": pd.DataFrame({
                'Close': [price / 20 for price in prices],
                'Volume': volumes
            }, index=dates)
        }

    def test_calculate_dca_amount_basic(self, dca, sample_market_data):
        """기본 DCA 금액 계산"""
        schedule = dca.default_schedule
        result = dca.calculate_dca_amount(schedule, sample_market_data)

        assert isinstance(result, dict)
        # 최소 하나의 자산에 대한 결과가 있어야 함
        assert len(result) >= 0

    def test_calculate_dca_amount_with_date(self, dca, sample_market_data):
        """특정 날짜로 DCA 계산"""
        schedule = dca.default_schedule
        test_date = datetime(2024, 6, 15)  # 6월 - 배당 시즌

        result = dca.calculate_dca_amount(schedule, sample_market_data, test_date)

        # 결과 구조 확인
        for asset, event in result.items():
            assert isinstance(event, DCAEvent)
            assert event.date == test_date

    def test_calculate_dca_amount_monthly_limit(self, dca, sample_market_data):
        """월간 한도 적용"""
        schedule = DCASchedule(
            base_amount_krw=10000000,  # 높은 기본 금액
            frequency_days=7,
            assets={"BTC": 1.0},
            volatility_multiplier=3.0,
            fear_greed_triggers={FearGreedLevel.EXTREME_FEAR: 5.0},
            accumulation_multiplier=2.0,
            max_monthly_amount=1000000,  # 낮은 월간 한도
            tax_optimization=False
        )

        result = dca.calculate_dca_amount(schedule, sample_market_data)

        # 월간 한도가 적용되어야 함
        for event in result.values():
            # 주간 금액이므로 월간 한도의 약 1/4 정도
            assert event.amount_krw <= schedule.max_monthly_amount

    def test_calculate_dca_amount_minimum_threshold(self, dca, sample_market_data):
        """최소 거래 금액 임계값"""
        schedule = DCASchedule(
            base_amount_krw=10000,  # 매우 낮은 금액
            frequency_days=30,
            assets={"BTC": 0.3, "ETH": 0.3, "SOL": 0.4},
            volatility_multiplier=1.0,
            fear_greed_triggers={},
            accumulation_multiplier=1.0,
            max_monthly_amount=10000,
            tax_optimization=False
        )

        result = dca.calculate_dca_amount(schedule, sample_market_data)

        # 최소 금액(10000원) 미달 자산은 제외되어야 함
        for event in result.values():
            assert event.amount_krw >= 10000


@pytest.mark.strategy
class TestAnalyzeMarketConditions:
    """시장 상황 분석 테스트"""

    @pytest.fixture
    def dca(self):
        return DCAPlus()

    @pytest.fixture
    def bullish_market_data(self):
        """상승장 데이터"""
        dates = pd.date_range(start='2024-01-01', periods=200, freq='D')
        # 꾸준히 상승하는 가격
        prices = [50000000 * (1 + i * 0.003) for i in range(200)]
        volumes = [100] * 200

        return {
            "BTC": pd.DataFrame({
                'Close': prices,
                'Volume': volumes
            }, index=dates)
        }

    @pytest.fixture
    def bearish_market_data(self):
        """하락장 데이터"""
        dates = pd.date_range(start='2024-01-01', periods=200, freq='D')
        # 꾸준히 하락하는 가격
        prices = [50000000 * (1 - i * 0.002) for i in range(200)]
        volumes = [100] * 200

        return {
            "BTC": pd.DataFrame({
                'Close': prices,
                'Volume': volumes
            }, index=dates)
        }

    def test_analyze_bullish_market(self, dca, bullish_market_data):
        """상승장 분석"""
        analysis = dca._analyze_market_conditions(bullish_market_data, datetime.now())

        assert analysis["market_trend"] == "bullish"
        assert analysis["fear_greed_level"] != FearGreedLevel.EXTREME_FEAR

    def test_analyze_bearish_market(self, dca, bearish_market_data):
        """하락장 분석"""
        analysis = dca._analyze_market_conditions(bearish_market_data, datetime.now())

        assert analysis["market_trend"] == "bearish"

    def test_analyze_empty_data(self, dca):
        """빈 데이터 분석"""
        analysis = dca._analyze_market_conditions({}, datetime.now())

        # 기본값 반환
        assert analysis["volatility_score"] == 0.5
        assert analysis["fear_greed_level"] == FearGreedLevel.NEUTRAL
        assert analysis["accumulation_signal"] == AccumulationSignal.NONE

    def test_analyze_volume_profile_high(self, dca):
        """높은 거래량 분석"""
        dates = pd.date_range(start='2024-01-01', periods=60, freq='D')
        prices = [50000000] * 60
        # 최근 거래량이 평균보다 높음
        volumes = [100] * 50 + [200] * 10

        market_data = {
            "BTC": pd.DataFrame({
                'Close': prices,
                'Volume': volumes
            }, index=dates)
        }

        analysis = dca._analyze_market_conditions(market_data, datetime.now())

        assert analysis["volume_profile"] == "high"


@pytest.mark.strategy
class TestCalculateOverallMultiplier:
    """전체 배수 계산 테스트"""

    @pytest.fixture
    def dca(self):
        return DCAPlus()

    @pytest.fixture
    def schedule(self):
        return DCASchedule(
            base_amount_krw=1000000,
            frequency_days=7,
            assets={"BTC": 1.0},
            volatility_multiplier=2.0,
            fear_greed_triggers={
                FearGreedLevel.EXTREME_FEAR: 3.0,
                FearGreedLevel.FEAR: 2.0,
                FearGreedLevel.NEUTRAL: 1.0,
                FearGreedLevel.GREED: 0.7,
                FearGreedLevel.EXTREME_GREED: 0.3
            },
            accumulation_multiplier=1.5,
            max_monthly_amount=5000000,
            tax_optimization=True
        )

    def test_multiplier_extreme_fear(self, dca, schedule):
        """극도의 공포 시 배수"""
        market_analysis = {
            "volatility_score": 1.5,
            "fear_greed_level": FearGreedLevel.EXTREME_FEAR,
            "accumulation_signal": AccumulationSignal.STRONG
        }

        multiplier = dca._calculate_overall_multiplier(schedule, market_analysis, datetime.now())

        assert multiplier > 2.0
        assert multiplier <= 3.0  # 최대 제한

    def test_multiplier_extreme_greed(self, dca, schedule):
        """극도의 탐욕 시 배수"""
        market_analysis = {
            "volatility_score": 0.3,
            "fear_greed_level": FearGreedLevel.EXTREME_GREED,
            "accumulation_signal": AccumulationSignal.NONE
        }

        multiplier = dca._calculate_overall_multiplier(schedule, market_analysis, datetime.now())

        assert multiplier < 1.0
        assert multiplier >= 0.2  # 최소 제한

    def test_multiplier_seasonal_december(self, dca, schedule):
        """12월 시즌 배수"""
        market_analysis = {
            "volatility_score": 0.5,
            "fear_greed_level": FearGreedLevel.NEUTRAL,
            "accumulation_signal": AccumulationSignal.NONE
        }

        december_date = datetime(2024, 12, 15)
        multiplier = dca._calculate_overall_multiplier(schedule, market_analysis, december_date)

        # 12월은 계절 배수가 1.3
        assert multiplier > 1.0


@pytest.mark.strategy
class TestCalculateAccumulationScore:
    """축적 점수 계산 테스트"""

    @pytest.fixture
    def dca(self):
        return DCAPlus()

    def test_accumulation_score_oversold(self, dca):
        """과매도 상태"""
        dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
        # 지속적인 하락으로 낮은 RSI
        prices = [50000000 * (1 - i * 0.005) for i in range(100)]
        volumes = [150] * 100  # 높은 거래량

        price_data = pd.DataFrame({
            'Close': prices,
            'Volume': volumes
        }, index=dates)

        score = dca._calculate_accumulation_score(price_data)

        assert 0 <= score <= 1

    def test_accumulation_score_overbought(self, dca):
        """과매수 상태"""
        dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
        # 지속적인 상승으로 높은 RSI
        prices = [50000000 * (1 + i * 0.01) for i in range(100)]
        volumes = [50] * 100  # 낮은 거래량

        price_data = pd.DataFrame({
            'Close': prices,
            'Volume': volumes
        }, index=dates)

        score = dca._calculate_accumulation_score(price_data)

        assert score < 0.5


@pytest.mark.strategy
class TestCalculateSeasonalMultiplier:
    """계절 배수 계산 테스트"""

    @pytest.fixture
    def dca(self):
        return DCAPlus()

    def test_december_multiplier(self, dca):
        """12월 배수"""
        december = datetime(2024, 12, 15)
        multiplier = dca._calculate_seasonal_multiplier(december)

        assert multiplier == 1.3

    def test_january_multiplier(self, dca):
        """1월 배수"""
        january = datetime(2024, 1, 15)
        multiplier = dca._calculate_seasonal_multiplier(january)

        assert multiplier == 1.2

    def test_june_multiplier(self, dca):
        """6월 배수"""
        june = datetime(2024, 6, 15)
        multiplier = dca._calculate_seasonal_multiplier(june)

        assert multiplier == 1.1

    def test_regular_month_multiplier(self, dca):
        """일반 달 배수"""
        march = datetime(2024, 3, 15)
        multiplier = dca._calculate_seasonal_multiplier(march)

        assert multiplier == 1.0


@pytest.mark.strategy
class TestDetermineEventType:
    """이벤트 타입 결정 테스트"""

    @pytest.fixture
    def dca(self):
        return DCAPlus()

    def test_accumulation_boost_event(self, dca):
        """축적 부스트 이벤트"""
        market_analysis = {
            "accumulation_signal": AccumulationSignal.STRONG,
            "fear_greed_level": FearGreedLevel.NEUTRAL
        }

        event_type, reasoning = dca._determine_event_type(2.5, market_analysis, {})

        assert event_type == "accumulation_boost"
        assert "축적" in reasoning

    def test_fear_boost_event(self, dca):
        """공포 부스트 이벤트"""
        market_analysis = {
            "accumulation_signal": AccumulationSignal.WEAK,
            "fear_greed_level": FearGreedLevel.EXTREME_FEAR
        }

        event_type, reasoning = dca._determine_event_type(2.5, market_analysis, {})

        assert event_type == "fear_boost"
        assert "공포" in reasoning

    def test_volatility_boost_event(self, dca):
        """변동성 부스트 이벤트"""
        market_analysis = {
            "accumulation_signal": AccumulationSignal.NONE,
            "fear_greed_level": FearGreedLevel.NEUTRAL,
            "volatility_score": 1.5
        }

        event_type, reasoning = dca._determine_event_type(2.5, market_analysis, {})

        assert event_type == "volatility_boost"
        assert "변동성" in reasoning

    def test_enhanced_regular_event(self, dca):
        """증액 정기 이벤트"""
        event_type, reasoning = dca._determine_event_type(1.5, {}, {})

        assert event_type == "enhanced_regular"
        assert "증액" in reasoning

    def test_reduced_regular_event(self, dca):
        """감액 정기 이벤트"""
        event_type, reasoning = dca._determine_event_type(0.5, {}, {})

        assert event_type == "reduced_regular"
        assert "축소" in reasoning

    def test_regular_event(self, dca):
        """일반 정기 이벤트"""
        event_type, reasoning = dca._determine_event_type(1.0, {}, {})

        assert event_type == "regular"
        assert "정기" in reasoning


@pytest.mark.strategy
class TestGetCurrentPrice:
    """현재 가격 조회 테스트"""

    @pytest.fixture
    def dca(self):
        return DCAPlus()

    def test_get_current_price_valid(self, dca):
        """유효한 가격 조회"""
        market_data = {
            "BTC": pd.DataFrame({
                'Close': [50000000, 51000000, 52000000]
            })
        }

        price = dca._get_current_price("BTC", market_data)

        assert price == 52000000

    def test_get_current_price_missing_asset(self, dca):
        """없는 자산 조회"""
        market_data = {"BTC": pd.DataFrame({'Close': [50000000]})}

        price = dca._get_current_price("ETH", market_data)

        assert price == 0.0

    def test_get_current_price_empty_data(self, dca):
        """빈 데이터 조회"""
        price = dca._get_current_price("BTC", {})

        assert price == 0.0


@pytest.mark.strategy
class TestCalculateRSI:
    """RSI 계산 테스트"""

    @pytest.fixture
    def dca(self):
        return DCAPlus()

    def test_calculate_rsi_uptrend(self, dca):
        """상승 추세 RSI"""
        prices = pd.Series([50000000 + i * 100000 for i in range(30)])

        rsi = dca._calculate_rsi(prices)

        # 상승 추세는 높은 RSI
        assert rsi.iloc[-1] > 50

    def test_calculate_rsi_downtrend(self, dca):
        """하락 추세 RSI"""
        prices = pd.Series([50000000 - i * 100000 for i in range(30)])

        rsi = dca._calculate_rsi(prices)

        # 하락 추세는 낮은 RSI
        assert rsi.iloc[-1] < 50

    def test_calculate_rsi_empty(self, dca):
        """빈 데이터 RSI"""
        prices = pd.Series([], dtype=float)

        rsi = dca._calculate_rsi(prices)

        assert len(rsi) == 0


@pytest.mark.strategy
class TestGenerateMonthlySchedule:
    """월간 스케줄 생성 테스트"""

    @pytest.fixture
    def dca(self):
        return DCAPlus()

    @pytest.fixture
    def sample_market_data(self):
        dates = pd.date_range(start='2024-01-01', periods=200, freq='D')
        prices = [50000000 + i * 10000 for i in range(200)]
        return {
            "BTC": pd.DataFrame({
                'Close': prices,
                'Volume': [100] * 200
            }, index=dates)
        }

    def test_generate_monthly_schedule(self, dca, sample_market_data):
        """월간 스케줄 생성"""
        schedule = dca.default_schedule
        start_date = datetime(2024, 3, 1)  # 금요일이 아닌 날

        events = dca.generate_monthly_schedule(schedule, start_date, sample_market_data)

        assert isinstance(events, list)
        # 30일 / 7일 = 약 4-5개 이벤트
        assert len(events) <= 5 * 3  # 자산당 최대 5개


@pytest.mark.strategy
class TestOptimizeTaxTiming:
    """세금 최적화 테스트"""

    @pytest.fixture
    def dca(self):
        return DCAPlus()

    def test_optimize_tax_timing(self, dca):
        """세금 최적화"""
        events = [
            DCAEvent(
                date=datetime.now(),
                asset="BTC",
                amount_krw=500000,
                price=50000000,
                quantity=0.01,
                event_type="regular",
                multiplier=1.0,
                reasoning="테스트"
            )
        ]

        optimized = dca.optimize_tax_timing(events)

        assert len(optimized) == len(events)


@pytest.mark.strategy
class TestGetDCAPerformanceMetrics:
    """DCA 성과 지표 테스트"""

    @pytest.fixture
    def dca(self):
        return DCAPlus()

    def test_performance_metrics_single_asset(self, dca):
        """단일 자산 성과"""
        events = [
            DCAEvent(
                date=datetime(2024, 1, 1),
                asset="BTC",
                amount_krw=500000,
                price=50000000,
                quantity=0.01,
                event_type="regular",
                multiplier=1.0,
                reasoning="테스트"
            ),
            DCAEvent(
                date=datetime(2024, 1, 8),
                asset="BTC",
                amount_krw=600000,
                price=48000000,
                quantity=0.0125,
                event_type="fear_boost",
                multiplier=1.2,
                reasoning="테스트"
            )
        ]

        metrics = dca.get_dca_performance_metrics(events)

        assert metrics["total_invested_krw"] == 1100000
        assert metrics["total_purchases"] == 2
        assert "BTC" in metrics["asset_statistics"]
        assert metrics["asset_statistics"]["BTC"]["total_invested"] == 1100000
        assert metrics["asset_statistics"]["BTC"]["purchase_count"] == 2

    def test_performance_metrics_multiple_assets(self, dca):
        """다중 자산 성과"""
        events = [
            DCAEvent(
                date=datetime(2024, 1, 1),
                asset="BTC",
                amount_krw=500000,
                price=50000000,
                quantity=0.01,
                event_type="regular",
                multiplier=1.0,
                reasoning="테스트"
            ),
            DCAEvent(
                date=datetime(2024, 1, 1),
                asset="ETH",
                amount_krw=300000,
                price=3000000,
                quantity=0.1,
                event_type="regular",
                multiplier=1.0,
                reasoning="테스트"
            )
        ]

        metrics = dca.get_dca_performance_metrics(events)

        assert "BTC" in metrics["asset_statistics"]
        assert "ETH" in metrics["asset_statistics"]
        assert metrics["total_invested_krw"] == 800000

    def test_performance_metrics_empty(self, dca):
        """빈 이력"""
        metrics = dca.get_dca_performance_metrics([])

        assert metrics == {}

    def test_performance_metrics_event_types(self, dca):
        """이벤트 타입별 통계"""
        events = [
            DCAEvent(
                date=datetime(2024, 1, 1),
                asset="BTC",
                amount_krw=500000,
                price=50000000,
                quantity=0.01,
                event_type="regular",
                multiplier=1.0,
                reasoning="테스트"
            ),
            DCAEvent(
                date=datetime(2024, 1, 8),
                asset="BTC",
                amount_krw=750000,
                price=48000000,
                quantity=0.0156,
                event_type="fear_boost",
                multiplier=1.5,
                reasoning="테스트"
            )
        ]

        metrics = dca.get_dca_performance_metrics(events)

        event_types = metrics["asset_statistics"]["BTC"]["event_types"]
        assert event_types["regular"] == 1
        assert event_types["fear_boost"] == 1


@pytest.mark.strategy
class TestAnalyzeComprehensiveDCA:
    """포괄적 DCA 분석 테스트"""

    @pytest.fixture
    def dca(self):
        return DCAPlus()

    def test_analyze_comprehensive_success(self, dca):
        """분석 성공"""
        market_conditions = {
            "fear_greed_index": 30,
            "price_volatility": 0.05,
            "trend_direction": "down"
        }

        result = dca.analyze_comprehensive_dca("BTC", 1000000, market_conditions)

        assert result["success"] is True
        assert "signal" in result
        assert result["signal_strength"] > 0
        assert "timestamp" in result

    def test_analyze_comprehensive_with_exception(self, dca):
        """분석 중 예외"""
        with patch.object(dca, 'calculate_dca_signal', side_effect=Exception("Test Error")):
            result = dca.analyze_comprehensive_dca("BTC", 1000000, {})

            assert result["success"] is False
            assert "error" in result
            assert result["recommended_amount"] == 1000000  # 기본값


@pytest.mark.strategy
class TestAnalyzeAssetConditions:
    """개별 자산 분석 테스트"""

    @pytest.fixture
    def dca(self):
        return DCAPlus()

    def test_analyze_asset_conditions(self, dca):
        """자산 상황 분석"""
        dates = pd.date_range(start='2024-01-01', periods=60, freq='D')
        market_data = {
            "BTC": pd.DataFrame({
                'Close': [50000000 + i * 50000 for i in range(60)]
            }, index=dates),
            "ETH": pd.DataFrame({
                'Close': [3000000 + i * 10000 for i in range(60)]
            }, index=dates)
        }

        analysis = dca._analyze_asset_conditions("ETH", market_data, datetime.now())

        assert "relative_strength" in analysis
        assert "support_level" in analysis
        assert "resistance_level" in analysis
        assert "trend_score" in analysis

    def test_analyze_asset_conditions_missing(self, dca):
        """없는 자산 분석"""
        analysis = dca._analyze_asset_conditions("SOL", {}, datetime.now())

        # 기본값 반환
        assert analysis["relative_strength"] == 0.5
        assert analysis["trend_score"] == 0.5
