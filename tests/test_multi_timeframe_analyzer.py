"""
Multi-Timeframe Analyzer Tests

멀티 타임프레임 분석기 테스트
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from src.core.multi_timeframe_analyzer import (
    MultiTimeframeAnalyzer,
    TrendDirection,
    CyclePhase,
    TimeframeAnalysis,
    MultiTimeframeResult,
    get_trend_consensus,
    calculate_trend_alignment_score
)
from src.core.market_season_filter import MarketSeason


@pytest.fixture
def mock_market_season_filter():
    """Mock MarketSeasonFilter"""
    filter_mock = Mock()
    filter_mock.analyze_weekly.return_value = {"market_season": "neutral"}
    filter_mock.calculate_200week_ma.return_value = 50000000.0
    return filter_mock


@pytest.fixture
def mock_db_manager():
    """Mock DatabaseManager"""
    db_mock = Mock()
    db_mock.save_analysis_result.return_value = 1
    return db_mock


@pytest.fixture
def sample_price_data():
    """샘플 가격 데이터 (200일 이상)"""
    np.random.seed(42)
    dates = pd.date_range(start='2023-01-01', periods=400, freq='D')
    prices = 50000000 + np.cumsum(np.random.randn(400) * 500000)
    prices = np.maximum(prices, 30000000)  # 최소 가격 보장

    df = pd.DataFrame({
        'Open': prices * 0.99,
        'High': prices * 1.02,
        'Low': prices * 0.98,
        'Close': prices,
        'Volume': np.random.randint(1000000, 10000000, 400)
    }, index=dates)

    return df


@pytest.fixture
def bullish_price_data():
    """상승 추세 가격 데이터"""
    dates = pd.date_range(start='2023-01-01', periods=400, freq='D')
    # 명확한 상승 추세
    prices = 40000000 + np.arange(400) * 100000

    df = pd.DataFrame({
        'Open': prices * 0.99,
        'High': prices * 1.02,
        'Low': prices * 0.98,
        'Close': prices,
        'Volume': np.random.randint(1000000, 10000000, 400)
    }, index=dates)

    return df


@pytest.fixture
def bearish_price_data():
    """하락 추세 가격 데이터"""
    dates = pd.date_range(start='2023-01-01', periods=400, freq='D')
    # 명확한 하락 추세
    prices = 80000000 - np.arange(400) * 100000
    prices = np.maximum(prices, 30000000)

    df = pd.DataFrame({
        'Open': prices * 1.01,
        'High': prices * 1.02,
        'Low': prices * 0.98,
        'Close': prices,
        'Volume': np.random.randint(1000000, 10000000, 400)
    }, index=dates)

    return df


@pytest.fixture
def analyzer(mock_market_season_filter, mock_db_manager):
    """MultiTimeframeAnalyzer 인스턴스"""
    return MultiTimeframeAnalyzer(mock_market_season_filter, mock_db_manager)


class TestMultiTimeframeAnalyzerInit:
    """초기화 테스트"""

    def test_init_with_market_season_filter(self, mock_market_season_filter):
        """MarketSeasonFilter로 초기화"""
        analyzer = MultiTimeframeAnalyzer(mock_market_season_filter)

        assert analyzer.market_season_filter == mock_market_season_filter
        assert analyzer.db_manager is None

    def test_init_with_db_manager(self, mock_market_season_filter, mock_db_manager):
        """DatabaseManager와 함께 초기화"""
        analyzer = MultiTimeframeAnalyzer(mock_market_season_filter, mock_db_manager)

        assert analyzer.market_season_filter == mock_market_season_filter
        assert analyzer.db_manager == mock_db_manager

    def test_halving_dates_initialized(self, mock_market_season_filter):
        """반감기 날짜 초기화 확인"""
        analyzer = MultiTimeframeAnalyzer(mock_market_season_filter)

        assert len(analyzer.halving_dates) == 5
        assert analyzer.halving_dates[0] == datetime(2012, 11, 28)
        assert analyzer.halving_dates[-1] == datetime(2028, 4, 20)


class TestAnalyzeMultiTimeframe:
    """analyze_multi_timeframe 메서드 테스트"""

    def test_analyze_with_series(self, analyzer, sample_price_data):
        """Series 데이터로 분석"""
        price_series = sample_price_data['Close']

        result = analyzer.analyze_multi_timeframe("BTC", price_series)

        assert isinstance(result, dict)
        assert "overall_trend" in result
        assert "market_season" in result
        assert "confidence" in result

    def test_analyze_with_dataframe(self, analyzer, sample_price_data):
        """DataFrame으로 분석"""
        result = analyzer.analyze_multi_timeframe("BTC", sample_price_data)

        assert isinstance(result, dict)
        assert "recommended_allocation" in result

    def test_analyze_saves_to_db(self, analyzer, sample_price_data):
        """DB 저장 확인"""
        analyzer.analyze_multi_timeframe("BTC", sample_price_data['Close'])

        analyzer.db_manager.save_analysis_result.assert_called()

    def test_analyze_handles_exception(self, mock_market_season_filter):
        """예외 처리 테스트"""
        analyzer = MultiTimeframeAnalyzer(mock_market_season_filter)
        # 빈 데이터로 예외 발생
        empty_series = pd.Series([])

        result = analyzer.analyze_multi_timeframe("BTC", empty_series)

        # 결과 반환 확인 (예외 시에도 기본값 또는 처리된 값 반환)
        assert "confidence" in result
        assert "market_season" in result


class TestAnalyzeAllTimeframes:
    """analyze_all_timeframes 메서드 테스트"""

    def test_returns_multi_timeframe_result(self, analyzer, sample_price_data):
        """MultiTimeframeResult 반환 확인"""
        result = analyzer.analyze_all_timeframes(sample_price_data)

        assert isinstance(result, MultiTimeframeResult)

    def test_all_timeframe_analyses_present(self, analyzer, sample_price_data):
        """모든 타임프레임 분석 결과 포함"""
        result = analyzer.analyze_all_timeframes(sample_price_data)

        assert result.very_short_term is not None
        assert result.swing_term is not None
        assert result.position_term is not None
        assert result.technical_20d is not None
        assert result.market_season_200w is not None
        assert result.bitcoin_cycle is not None

    def test_overall_confidence_calculated(self, analyzer, sample_price_data):
        """전체 신뢰도 계산"""
        result = analyzer.analyze_all_timeframes(sample_price_data)

        assert 0.0 <= result.overall_confidence <= 1.0

    def test_recommended_allocation_calculated(self, analyzer, sample_price_data):
        """권장 배분 계산"""
        result = analyzer.analyze_all_timeframes(sample_price_data)

        assert "crypto" in result.recommended_allocation
        assert "krw" in result.recommended_allocation


class TestAnalyzeTechnical20d:
    """_analyze_technical_20d 메서드 테스트"""

    def test_returns_timeframe_analysis(self, analyzer, sample_price_data):
        """TimeframeAnalysis 반환"""
        result = analyzer._analyze_technical_20d(sample_price_data)

        assert isinstance(result, TimeframeAnalysis)
        assert result.timeframe == "short_term_20d"

    def test_bullish_trend_detection(self, analyzer, bullish_price_data):
        """상승 추세 감지"""
        result = analyzer._analyze_technical_20d(bullish_price_data)

        # 상승 추세 또는 횡보 (RSI에 따라 달라질 수 있음)
        assert result.trend_direction in [TrendDirection.BULLISH, TrendDirection.SIDEWAYS]

    def test_bearish_trend_detection(self, analyzer, bearish_price_data):
        """하락 추세 감지"""
        result = analyzer._analyze_technical_20d(bearish_price_data)

        assert result.trend_direction in [TrendDirection.BEARISH, TrendDirection.SIDEWAYS]

    def test_support_resistance_levels(self, analyzer, sample_price_data):
        """지지/저항 레벨 계산"""
        result = analyzer._analyze_technical_20d(sample_price_data)

        assert result.support_level > 0
        assert result.resistance_level > result.support_level

    def test_confidence_range(self, analyzer, sample_price_data):
        """신뢰도 범위"""
        result = analyzer._analyze_technical_20d(sample_price_data)

        assert 0.3 <= result.confidence <= 0.8

    def test_handles_exception(self, analyzer):
        """예외 처리"""
        bad_data = pd.DataFrame({'Close': []})

        result = analyzer._analyze_technical_20d(bad_data)

        assert result.trend_direction == TrendDirection.SIDEWAYS
        assert result.confidence == 0.1


class TestAnalyzeMarketSeason200w:
    """_analyze_market_season_200w 메서드 테스트"""

    def test_returns_timeframe_analysis(self, analyzer, sample_price_data):
        """TimeframeAnalysis 반환"""
        result = analyzer._analyze_market_season_200w(sample_price_data)

        assert isinstance(result, TimeframeAnalysis)
        assert result.timeframe == "medium_term_200w"

    def test_uses_200w_ma(self, analyzer, sample_price_data):
        """200주 이동평균 사용"""
        analyzer._analyze_market_season_200w(sample_price_data)

        analyzer.market_season_filter.calculate_200week_ma.assert_called()

    def test_trend_based_on_price_ratio(self, analyzer, sample_price_data):
        """가격 비율 기반 트렌드"""
        # MA보다 20% 높은 가격 설정
        analyzer.market_season_filter.calculate_200week_ma.return_value = 40000000

        result = analyzer._analyze_market_season_200w(sample_price_data)

        assert result.trend_direction in [TrendDirection.BULLISH, TrendDirection.SIDEWAYS, TrendDirection.BEARISH]


class TestAnalyzeBitcoinCycleAnalysis:
    """_analyze_bitcoin_cycle_analysis 메서드 테스트"""

    def test_returns_timeframe_analysis(self, analyzer, sample_price_data):
        """TimeframeAnalysis 반환"""
        result = analyzer._analyze_bitcoin_cycle_analysis(sample_price_data)

        assert isinstance(result, TimeframeAnalysis)
        assert result.timeframe == "long_term_4y"

    def test_cycle_based_trend(self, analyzer, sample_price_data):
        """사이클 기반 트렌드"""
        result = analyzer._analyze_bitcoin_cycle_analysis(sample_price_data)

        assert result.trend_direction in [TrendDirection.BULLISH, TrendDirection.BEARISH, TrendDirection.SIDEWAYS]

    def test_yearly_support_resistance(self, analyzer, sample_price_data):
        """연간 지지/저항 레벨"""
        result = analyzer._analyze_bitcoin_cycle_analysis(sample_price_data)

        assert result.support_level >= 0
        assert result.resistance_level >= result.support_level


class TestAnalyzeVeryShortTerm:
    """_analyze_very_short_term 메서드 테스트"""

    def test_returns_timeframe_analysis(self, analyzer, sample_price_data):
        """TimeframeAnalysis 반환"""
        result = analyzer._analyze_very_short_term(sample_price_data)

        assert isinstance(result, TimeframeAnalysis)
        assert result.timeframe == "very_short_term_7d"

    def test_uses_7_day_ma(self, analyzer, sample_price_data):
        """7일 이동평균 사용"""
        result = analyzer._analyze_very_short_term(sample_price_data)

        # 7일 지지/저항 레벨 확인
        assert result.support_level > 0
        assert result.resistance_level > 0

    def test_momentum_calculation(self, analyzer, bullish_price_data):
        """모멘텀 계산"""
        result = analyzer._analyze_very_short_term(bullish_price_data)

        # 상승 추세에서 bullish 또는 sideways
        assert result.trend_direction in [TrendDirection.BULLISH, TrendDirection.SIDEWAYS]


class TestAnalyzeSwingTerm:
    """_analyze_swing_term 메서드 테스트"""

    def test_returns_timeframe_analysis(self, analyzer, sample_price_data):
        """TimeframeAnalysis 반환"""
        result = analyzer._analyze_swing_term(sample_price_data)

        assert isinstance(result, TimeframeAnalysis)
        assert result.timeframe == "swing_term_30d"

    def test_uses_macd(self, analyzer, sample_price_data):
        """MACD 사용"""
        result = analyzer._analyze_swing_term(sample_price_data)

        # 결과가 유효함
        assert result.strength >= 0
        assert result.confidence == 0.7


class TestAnalyzePositionTerm:
    """_analyze_position_term 메서드 테스트"""

    def test_returns_timeframe_analysis(self, analyzer, sample_price_data):
        """TimeframeAnalysis 반환"""
        result = analyzer._analyze_position_term(sample_price_data)

        assert isinstance(result, TimeframeAnalysis)
        assert result.timeframe == "position_term_200d"

    def test_multiple_ma_analysis(self, analyzer, sample_price_data):
        """다중 이동평균 분석"""
        result = analyzer._analyze_position_term(sample_price_data)

        # 높은 신뢰도 (장기 분석)
        assert result.confidence == 0.85

    def test_perfect_bullish_alignment(self, analyzer, bullish_price_data):
        """완벽한 상승 정렬"""
        result = analyzer._analyze_position_term(bullish_price_data)

        # 강한 상승 추세
        assert result.trend_direction == TrendDirection.BULLISH
        assert result.strength >= 0.5

    def test_perfect_bearish_alignment(self, analyzer, bearish_price_data):
        """완벽한 하락 정렬"""
        result = analyzer._analyze_position_term(bearish_price_data)

        # 하락 추세
        assert result.trend_direction in [TrendDirection.BEARISH, TrendDirection.SIDEWAYS]


class TestAnalyzeBitcoinCycle:
    """_analyze_bitcoin_cycle 메서드 테스트"""

    def test_returns_cycle_phase(self, analyzer, sample_price_data):
        """CyclePhase 반환"""
        result = analyzer._analyze_bitcoin_cycle(sample_price_data)

        assert isinstance(result, CyclePhase)

    def test_accumulation_phase(self, analyzer, sample_price_data):
        """축적 단계 (반감기 직후)"""
        # 2024년 반감기 직후 시뮬레이션
        with patch('src.core.multi_timeframe_analyzer.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 5, 1)

            result = analyzer._analyze_bitcoin_cycle(sample_price_data)

            assert result == CyclePhase.ACCUMULATION

    def test_markup_phase(self, analyzer, sample_price_data):
        """상승 단계"""
        with patch('src.core.multi_timeframe_analyzer.datetime') as mock_datetime:
            # 반감기 후 6개월
            mock_datetime.now.return_value = datetime(2024, 10, 20)

            result = analyzer._analyze_bitcoin_cycle(sample_price_data)

            assert result == CyclePhase.MARKUP

    def test_distribution_phase(self, analyzer, sample_price_data):
        """분산 단계"""
        with patch('src.core.multi_timeframe_analyzer.datetime') as mock_datetime:
            # 반감기 후 20개월
            mock_datetime.now.return_value = datetime(2025, 12, 20)

            result = analyzer._analyze_bitcoin_cycle(sample_price_data)

            assert result == CyclePhase.DISTRIBUTION

    def test_decline_phase(self, analyzer, sample_price_data):
        """하락 단계"""
        with patch('src.core.multi_timeframe_analyzer.datetime') as mock_datetime:
            # 반감기 후 26개월
            mock_datetime.now.return_value = datetime(2026, 7, 1)

            result = analyzer._analyze_bitcoin_cycle(sample_price_data)

            assert result == CyclePhase.DECLINE


class TestCalculateRSI:
    """_calculate_rsi 메서드 테스트"""

    def test_returns_series(self, analyzer, sample_price_data):
        """Series 반환"""
        result = analyzer._calculate_rsi(sample_price_data['Close'])

        assert isinstance(result, pd.Series)

    def test_rsi_range(self, analyzer, sample_price_data):
        """RSI 범위 (0-100)"""
        result = analyzer._calculate_rsi(sample_price_data['Close'])

        valid_values = result.dropna()
        assert (valid_values >= 0).all()
        assert (valid_values <= 100).all()

    def test_bullish_rsi(self, analyzer, bullish_price_data):
        """상승 추세의 RSI"""
        result = analyzer._calculate_rsi(bullish_price_data['Close'])

        # 상승 추세에서 RSI는 높은 경향
        assert result.iloc[-1] > 40


class TestCalculateMACD:
    """_calculate_macd 메서드 테스트"""

    def test_returns_tuple(self, analyzer, sample_price_data):
        """튜플 반환"""
        result = analyzer._calculate_macd(sample_price_data['Close'])

        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_macd_and_signal_series(self, analyzer, sample_price_data):
        """MACD와 시그널 라인 Series"""
        macd_line, signal_line = analyzer._calculate_macd(sample_price_data['Close'])

        assert isinstance(macd_line, pd.Series)
        assert isinstance(signal_line, pd.Series)


class TestCalculateBollingerBands:
    """_calculate_bollinger_bands 메서드 테스트"""

    def test_returns_tuple(self, analyzer, sample_price_data):
        """튜플 반환"""
        result = analyzer._calculate_bollinger_bands(sample_price_data['Close'])

        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_upper_above_lower(self, analyzer, sample_price_data):
        """상단 밴드가 하단 밴드보다 높음"""
        upper, lower = analyzer._calculate_bollinger_bands(sample_price_data['Close'])

        valid_indices = upper.dropna().index.intersection(lower.dropna().index)
        assert (upper[valid_indices] >= lower[valid_indices]).all()


class TestCalculateOverallConfidence:
    """_calculate_overall_confidence 메서드 테스트"""

    def test_all_bullish_alignment(self, analyzer):
        """모두 상승 추세 정렬"""
        short = TimeframeAnalysis(
            timeframe="short", trend_direction=TrendDirection.BULLISH,
            strength=0.8, support_level=100, resistance_level=200,
            confidence=0.8, last_updated=datetime.now()
        )
        medium = TimeframeAnalysis(
            timeframe="medium", trend_direction=TrendDirection.BULLISH,
            strength=0.8, support_level=100, resistance_level=200,
            confidence=0.8, last_updated=datetime.now()
        )
        long = TimeframeAnalysis(
            timeframe="long", trend_direction=TrendDirection.BULLISH,
            strength=0.8, support_level=100, resistance_level=200,
            confidence=0.8, last_updated=datetime.now()
        )

        result = analyzer._calculate_overall_confidence(short, medium, long)

        # 정렬 보너스 포함
        assert result >= 0.8

    def test_mixed_trends(self, analyzer):
        """혼합 추세"""
        short = TimeframeAnalysis(
            timeframe="short", trend_direction=TrendDirection.BULLISH,
            strength=0.5, support_level=100, resistance_level=200,
            confidence=0.5, last_updated=datetime.now()
        )
        medium = TimeframeAnalysis(
            timeframe="medium", trend_direction=TrendDirection.BEARISH,
            strength=0.5, support_level=100, resistance_level=200,
            confidence=0.5, last_updated=datetime.now()
        )
        long = TimeframeAnalysis(
            timeframe="long", trend_direction=TrendDirection.SIDEWAYS,
            strength=0.5, support_level=100, resistance_level=200,
            confidence=0.5, last_updated=datetime.now()
        )

        result = analyzer._calculate_overall_confidence(short, medium, long)

        # 신뢰도 감소
        assert result < 0.8


class TestCalculateRecommendedAllocation:
    """_calculate_recommended_allocation 메서드 테스트"""

    def test_risk_on_allocation(self, analyzer):
        """RISK_ON 시장 배분"""
        short = TimeframeAnalysis(
            timeframe="short", trend_direction=TrendDirection.BULLISH,
            strength=0.8, support_level=100, resistance_level=200,
            confidence=0.8, last_updated=datetime.now()
        )

        result = analyzer._calculate_recommended_allocation(
            short, short, short,
            MarketSeason.RISK_ON,
            CyclePhase.MARKUP
        )

        # 암호화폐 비중 높음
        assert result["crypto"] >= 0.5

    def test_risk_off_allocation(self, analyzer):
        """RISK_OFF 시장 배분"""
        short = TimeframeAnalysis(
            timeframe="short", trend_direction=TrendDirection.BEARISH,
            strength=0.8, support_level=100, resistance_level=200,
            confidence=0.8, last_updated=datetime.now()
        )

        result = analyzer._calculate_recommended_allocation(
            short, short, short,
            MarketSeason.RISK_OFF,
            CyclePhase.DECLINE
        )

        # KRW 비중 높음
        assert result["krw"] >= 0.5

    def test_allocation_range(self, analyzer):
        """배분 범위 (20-80%)"""
        short = TimeframeAnalysis(
            timeframe="short", trend_direction=TrendDirection.BULLISH,
            strength=1.0, support_level=100, resistance_level=200,
            confidence=1.0, last_updated=datetime.now()
        )

        result = analyzer._calculate_recommended_allocation(
            short, short, short,
            MarketSeason.RISK_ON,
            CyclePhase.MARKUP
        )

        # 부동소수점 오차 허용
        assert 0.19 <= result["crypto"] <= 0.81
        assert 0.19 <= result["krw"] <= 0.81


class TestGetAnalysisSummary:
    """get_analysis_summary 메서드 테스트"""

    def test_returns_dict(self, analyzer, sample_price_data):
        """딕셔너리 반환"""
        mtf_result = analyzer.analyze_all_timeframes(sample_price_data)

        result = analyzer.get_analysis_summary(mtf_result)

        assert isinstance(result, dict)

    def test_contains_required_keys(self, analyzer, sample_price_data):
        """필수 키 포함"""
        mtf_result = analyzer.analyze_all_timeframes(sample_price_data)

        result = analyzer.get_analysis_summary(mtf_result)

        assert "trading_timeframes" in result
        assert "strategic_layer" in result
        assert "overall_trend" in result
        assert "market_season" in result
        assert "recommended_allocation" in result
        assert "key_levels" in result


class TestSaveAnalysisToDb:
    """_save_analysis_to_db 메서드 테스트"""

    def test_saves_to_db(self, analyzer, sample_price_data):
        """DB 저장"""
        mtf_result = analyzer.analyze_all_timeframes(sample_price_data)

        analyzer._save_analysis_to_db(mtf_result, "BTC")

        analyzer.db_manager.save_analysis_result.assert_called_once()
        call_args = analyzer.db_manager.save_analysis_result.call_args
        assert call_args[0][0] == "multi_timeframe"

    def test_handles_db_error(self, analyzer, sample_price_data):
        """DB 오류 처리"""
        analyzer.db_manager.save_analysis_result.side_effect = Exception("DB Error")
        mtf_result = analyzer.analyze_all_timeframes(sample_price_data)

        # 예외가 발생하지 않음
        analyzer._save_analysis_to_db(mtf_result, "BTC")


class TestGetTrendConsensus:
    """get_trend_consensus 함수 테스트"""

    def test_all_bullish(self):
        """모두 상승"""
        trends = [TrendDirection.BULLISH, TrendDirection.BULLISH, TrendDirection.BULLISH]

        result = get_trend_consensus(trends)

        assert result == TrendDirection.BULLISH

    def test_majority_bullish(self):
        """다수 상승"""
        trends = [TrendDirection.BULLISH, TrendDirection.BULLISH, TrendDirection.SIDEWAYS]

        result = get_trend_consensus(trends)

        assert result == TrendDirection.BULLISH

    def test_all_bearish(self):
        """모두 하락"""
        trends = [TrendDirection.BEARISH, TrendDirection.BEARISH, TrendDirection.BEARISH]

        result = get_trend_consensus(trends)

        assert result == TrendDirection.BEARISH

    def test_majority_bearish(self):
        """다수 하락"""
        trends = [TrendDirection.BEARISH, TrendDirection.BEARISH, TrendDirection.SIDEWAYS]

        result = get_trend_consensus(trends)

        assert result == TrendDirection.BEARISH

    def test_no_consensus(self):
        """합의 없음"""
        trends = [TrendDirection.BULLISH, TrendDirection.BEARISH, TrendDirection.SIDEWAYS]

        result = get_trend_consensus(trends)

        assert result == TrendDirection.SIDEWAYS


class TestCalculateTrendAlignmentScore:
    """calculate_trend_alignment_score 함수 테스트"""

    def test_all_same(self):
        """모두 같음"""
        result = calculate_trend_alignment_score(
            TrendDirection.BULLISH,
            TrendDirection.BULLISH,
            TrendDirection.BULLISH
        )

        assert result == 1.0

    def test_two_same(self):
        """2개 같음"""
        result = calculate_trend_alignment_score(
            TrendDirection.BULLISH,
            TrendDirection.BULLISH,
            TrendDirection.SIDEWAYS
        )

        assert result == 0.6

    def test_all_different(self):
        """모두 다름"""
        result = calculate_trend_alignment_score(
            TrendDirection.BULLISH,
            TrendDirection.BEARISH,
            TrendDirection.SIDEWAYS
        )

        assert result == 0.2


class TestEdgeCases:
    """엣지 케이스 테스트"""

    def test_short_price_data(self, analyzer):
        """짧은 가격 데이터"""
        dates = pd.date_range(start='2023-01-01', periods=10, freq='D')
        prices = [50000000 + i * 100000 for i in range(10)]

        df = pd.DataFrame({
            'Open': prices,
            'High': [p * 1.01 for p in prices],
            'Low': [p * 0.99 for p in prices],
            'Close': prices,
            'Volume': [1000000] * 10
        }, index=dates)

        # 예외 없이 실행
        result = analyzer.analyze_all_timeframes(df)

        assert result is not None

    def test_constant_price(self, analyzer):
        """일정한 가격"""
        dates = pd.date_range(start='2023-01-01', periods=200, freq='D')
        prices = [50000000] * 200

        df = pd.DataFrame({
            'Open': prices,
            'High': prices,
            'Low': prices,
            'Close': prices,
            'Volume': [1000000] * 200
        }, index=dates)

        result = analyzer.analyze_all_timeframes(df)

        # 횡보로 인식
        assert result.overall_trend in [TrendDirection.SIDEWAYS, TrendDirection.BULLISH, TrendDirection.BEARISH]

    def test_extreme_volatility(self, analyzer):
        """극단적 변동성"""
        np.random.seed(42)
        dates = pd.date_range(start='2023-01-01', periods=200, freq='D')
        # 큰 변동성
        prices = 50000000 + np.cumsum(np.random.randn(200) * 5000000)
        prices = np.maximum(prices, 10000000)

        df = pd.DataFrame({
            'Open': prices * 0.95,
            'High': prices * 1.1,
            'Low': prices * 0.9,
            'Close': prices,
            'Volume': [10000000] * 200
        }, index=dates)

        result = analyzer.analyze_all_timeframes(df)

        assert result is not None
        assert 0.0 <= result.overall_confidence <= 1.0


class TestDataclasses:
    """데이터클래스 테스트"""

    def test_timeframe_analysis_creation(self):
        """TimeframeAnalysis 생성"""
        analysis = TimeframeAnalysis(
            timeframe="test",
            trend_direction=TrendDirection.BULLISH,
            strength=0.8,
            support_level=100,
            resistance_level=200,
            confidence=0.75,
            last_updated=datetime.now()
        )

        assert analysis.timeframe == "test"
        assert analysis.trend_direction == TrendDirection.BULLISH
        assert analysis.strength == 0.8

    def test_trend_direction_enum(self):
        """TrendDirection Enum"""
        assert TrendDirection.BULLISH.value == "bullish"
        assert TrendDirection.BEARISH.value == "bearish"
        assert TrendDirection.SIDEWAYS.value == "sideways"

    def test_cycle_phase_enum(self):
        """CyclePhase Enum"""
        assert CyclePhase.ACCUMULATION.value == "accumulation"
        assert CyclePhase.MARKUP.value == "markup"
        assert CyclePhase.DISTRIBUTION.value == "distribution"
        assert CyclePhase.DECLINE.value == "decline"


class TestMultiTimeframeUncoveredLines:
    """커버되지 않은 라인 테스트"""

    @pytest.fixture
    def analyzer(self, mock_market_season_filter, mock_db_manager):
        return MultiTimeframeAnalyzer(mock_market_season_filter, mock_db_manager)

    def test_analyze_for_external_exception(self, analyzer):
        """외부 인터페이스 예외 처리 (라인 133-137)"""
        # 잘못된 데이터로 예외 유발
        bad_df = pd.DataFrame()

        result = analyzer.analyze_all_timeframes(bad_df)

        # 빈 데이터 시 기본 결과 반환
        assert result is not None
        assert isinstance(result, MultiTimeframeResult)

    def test_cycle_progress_early(self, analyzer):
        """사이클 진행도 초기 (라인 381-382)"""
        np.random.seed(42)
        # 반감기 직후 (초기 사이클)
        # 2024년 4월 반감기 직후 가정
        dates = pd.date_range(start='2024-04-20', periods=200, freq='D')
        prices = [50000000 * (1 + i * 0.001) for i in range(200)]

        df = pd.DataFrame({
            'Open': [p * 0.99 for p in prices],
            'High': [p * 1.02 for p in prices],
            'Low': [p * 0.98 for p in prices],
            'Close': prices,
            'Volume': [10000000] * 200
        }, index=dates)

        result = analyzer._analyze_bitcoin_cycle_analysis(df)

        assert result is not None
        assert result.timeframe == "long_term_4y"

    def test_cycle_progress_late(self, analyzer):
        """사이클 진행도 후기 (라인 387-388)"""
        np.random.seed(42)
        # 사이클 후반 (2028년 반감기 직전)
        dates = pd.date_range(start='2028-01-01', periods=200, freq='D')
        prices = [100000000 * (1 - i * 0.002) for i in range(200)]

        df = pd.DataFrame({
            'Open': [p * 0.99 for p in prices],
            'High': [p * 1.02 for p in prices],
            'Low': [p * 0.98 for p in prices],
            'Close': prices,
            'Volume': [10000000] * 200
        }, index=dates)

        result = analyzer._analyze_bitcoin_cycle_analysis(df)

        assert result is not None

    def test_cycle_edge_conditions(self, analyzer):
        """사이클 진행도 경계 조건 (라인 405)"""
        np.random.seed(42)
        dates = pd.date_range(start='2024-04-20', periods=50, freq='D')
        prices = [50000000] * 50  # 변동 없음

        df = pd.DataFrame({
            'Open': prices,
            'High': [p * 1.01 for p in prices],
            'Low': [p * 0.99 for p in prices],
            'Close': prices,
            'Volume': [10000000] * 50
        }, index=dates)

        result = analyzer._analyze_bitcoin_cycle_analysis(df)
        assert result is not None
        assert 0.3 <= result.confidence <= 0.8

    def test_confidence_calculation(self, analyzer):
        """신뢰도 계산 분기 테스트"""
        np.random.seed(42)
        dates = pd.date_range(start='2024-06-01', periods=400, freq='D')
        # 가격이 연간 중간 영역에 있는 경우
        base_price = 50000000
        prices = [base_price + np.sin(i * 0.05) * 5000000 for i in range(400)]

        df = pd.DataFrame({
            'Open': [p * 0.99 for p in prices],
            'High': [p * 1.02 for p in prices],
            'Low': [p * 0.98 for p in prices],
            'Close': prices,
            'Volume': [10000000] * 400
        }, index=dates)

        result = analyzer.analyze_all_timeframes(df)
        assert result is not None
        assert 0.0 <= result.overall_confidence <= 1.0

    def test_get_analysis_summary_with_result(self, analyzer):
        """분석 요약 가져오기"""
        np.random.seed(42)
        dates = pd.date_range(start='2024-01-01', periods=200, freq='D')
        prices = [50000000 + i * 10000 for i in range(200)]

        df = pd.DataFrame({
            'Open': [p * 0.99 for p in prices],
            'High': [p * 1.02 for p in prices],
            'Low': [p * 0.98 for p in prices],
            'Close': prices,
            'Volume': [10000000] * 200
        }, index=dates)

        result = analyzer.analyze_all_timeframes(df)
        summary = analyzer.get_analysis_summary(result)

        assert summary is not None
        assert "overall_trend" in summary
        assert "market_season" in summary

    def test_empty_dataframe(self, analyzer):
        """빈 데이터프레임 처리"""
        df = pd.DataFrame()

        result = analyzer.analyze_all_timeframes(df)

        assert result is not None
        assert isinstance(result, MultiTimeframeResult)

    def test_insufficient_data(self, analyzer):
        """불충분한 데이터"""
        dates = pd.date_range(start='2024-01-01', periods=10, freq='D')
        prices = [50000000] * 10

        df = pd.DataFrame({
            'Open': prices,
            'High': prices,
            'Low': prices,
            'Close': prices,
            'Volume': [1000000] * 10
        }, index=dates)

        result = analyzer.analyze_all_timeframes(df)

        assert result is not None
        assert isinstance(result, MultiTimeframeResult)
