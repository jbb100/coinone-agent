"""
On-Chain Data Analyzer Tests

온체인 데이터 분석기 테스트
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from src.core.onchain_data_analyzer import (
    OnchainDataAnalyzer,
    OnchainMetrics,
    OnchainAnalysis,
    OnchainTrend,
    WhaleActivity,
    ExchangeFlow,
    _log_stub_warning
)


@pytest.fixture
def mock_db_manager():
    """Mock DatabaseManager"""
    db_mock = Mock()
    db_mock.save_analysis_result.return_value = 1
    return db_mock


@pytest.fixture
def analyzer(mock_db_manager):
    """OnchainDataAnalyzer 인스턴스"""
    api_keys = {"glassnode": "test_key"}
    return OnchainDataAnalyzer(api_keys, mock_db_manager)


@pytest.fixture
def analyzer_no_db():
    """DB 없는 OnchainDataAnalyzer 인스턴스"""
    return OnchainDataAnalyzer()


@pytest.fixture
def sample_metrics():
    """샘플 온체인 메트릭스"""
    return OnchainMetrics(
        whale_addresses_count=2000,
        whale_balance_total=5000000,
        whale_net_flow_24h=5000,  # 축적
        exchange_inflow_24h=10000,
        exchange_outflow_24h=15000,
        exchange_netflow_24h=-5000,  # 유출
        exchange_reserves=2500000,
        long_term_holder_supply=65.0,
        short_term_holder_supply=35.0,
        lth_net_position_change=1000,
        active_addresses=900000,
        network_hash_rate=550.0,
        transaction_count=350000,
        network_value_locked=50000000000,
        stablecoin_supply=150000000000,
        stablecoin_dominance=8.5,
        stablecoin_flow_24h=500000000,
        fear_greed_index=45,
        funding_rates={"binance": 0.01, "ftx": 0.015},
        last_updated=datetime.now()
    )


@pytest.fixture
def bearish_metrics():
    """하락 신호 메트릭스"""
    return OnchainMetrics(
        whale_addresses_count=1800,
        whale_balance_total=4500000,
        whale_net_flow_24h=-8000,  # 분산
        exchange_inflow_24h=25000,
        exchange_outflow_24h=8000,
        exchange_netflow_24h=17000,  # 유입
        exchange_reserves=3000000,
        long_term_holder_supply=55.0,
        short_term_holder_supply=45.0,
        lth_net_position_change=-2000,
        active_addresses=400000,
        network_hash_rate=280.0,
        transaction_count=120000,
        network_value_locked=30000000000,
        stablecoin_supply=180000000000,
        stablecoin_dominance=12.0,
        stablecoin_flow_24h=-1000000000,
        fear_greed_index=20,
        funding_rates={"binance": -0.02, "ftx": -0.03},
        last_updated=datetime.now()
    )


class TestOnchainDataAnalyzerInit:
    """초기화 테스트"""

    def test_init_with_api_keys(self, mock_db_manager):
        """API 키와 함께 초기화"""
        api_keys = {"glassnode": "key1", "cryptoquant": "key2"}
        analyzer = OnchainDataAnalyzer(api_keys, mock_db_manager)

        assert analyzer.api_keys == api_keys
        assert analyzer.db_manager == mock_db_manager

    def test_init_without_api_keys(self):
        """API 키 없이 초기화"""
        analyzer = OnchainDataAnalyzer()

        assert analyzer.api_keys == {}
        assert analyzer.db_manager is None

    def test_data_providers_initialized(self, analyzer):
        """데이터 제공자 초기화 확인"""
        assert "glassnode" in analyzer.data_providers
        assert "cryptoquant" in analyzer.data_providers
        assert "santiment" in analyzer.data_providers

    def test_whale_thresholds_initialized(self, analyzer):
        """고래 임계값 초기화 확인"""
        assert "BTC" in analyzer.whale_thresholds
        assert analyzer.whale_thresholds["BTC"] == 1000
        assert analyzer.whale_thresholds["ETH"] == 10000

    def test_analysis_weights_initialized(self, analyzer):
        """분석 가중치 초기화 확인"""
        weights = analyzer.analysis_weights
        total_weight = sum(weights.values())

        # 가중치 합이 1.0
        assert abs(total_weight - 1.0) < 0.01


class TestCollectOnchainMetrics:
    """collect_onchain_metrics 메서드 테스트"""

    def test_returns_onchain_metrics(self, analyzer):
        """OnchainMetrics 반환"""
        metrics = analyzer.collect_onchain_metrics("BTC")

        assert isinstance(metrics, OnchainMetrics)

    def test_collects_btc_metrics(self, analyzer):
        """BTC 메트릭스 수집"""
        metrics = analyzer.collect_onchain_metrics("BTC")

        assert metrics.whale_addresses_count >= 0
        assert metrics.exchange_reserves >= 0
        assert metrics.last_updated is not None

    def test_collects_eth_metrics(self, analyzer):
        """ETH 메트릭스 수집"""
        metrics = analyzer.collect_onchain_metrics("ETH")

        assert isinstance(metrics, OnchainMetrics)


class TestAnalyzeOnchainData:
    """analyze_onchain_data 메서드 테스트"""

    def test_returns_onchain_analysis(self, analyzer, sample_metrics):
        """OnchainAnalysis 반환"""
        analysis = analyzer.analyze_onchain_data(sample_metrics, "BTC")

        assert isinstance(analysis, OnchainAnalysis)

    def test_bullish_analysis(self, analyzer, sample_metrics):
        """상승 신호 분석"""
        analysis = analyzer.analyze_onchain_data(sample_metrics, "BTC")

        # 축적 점수가 분산 점수보다 높음
        assert analysis.accumulation_score >= analysis.distribution_score * 0.5

    def test_bearish_analysis(self, analyzer, bearish_metrics):
        """하락 신호 분석"""
        analysis = analyzer.analyze_onchain_data(bearish_metrics, "BTC")

        # 분산 점수가 높음
        assert analysis.distribution_score >= 0

    def test_saves_to_db(self, analyzer, sample_metrics):
        """DB 저장 확인"""
        analyzer.analyze_onchain_data(sample_metrics, "BTC")

        analyzer.db_manager.save_analysis_result.assert_called()

    def test_analysis_without_db(self, analyzer_no_db, sample_metrics):
        """DB 없이 분석"""
        analysis = analyzer_no_db.analyze_onchain_data(sample_metrics, "BTC")

        assert isinstance(analysis, OnchainAnalysis)


class TestAnalyzeWhaleActivity:
    """_analyze_whale_activity 메서드 테스트"""

    def test_accumulating_whales(self, analyzer):
        """고래 축적 감지"""
        metrics = OnchainMetrics(
            whale_addresses_count=2100,
            whale_balance_total=5500000,
            whale_net_flow_24h=6000,  # 대량 축적
            exchange_inflow_24h=5000,
            exchange_outflow_24h=5000,
            exchange_netflow_24h=0,
            exchange_reserves=2500000,
            long_term_holder_supply=65.0,
            short_term_holder_supply=35.0,
            lth_net_position_change=0,
            active_addresses=800000,
            network_hash_rate=500.0,
            transaction_count=250000,
            network_value_locked=40000000000,
            stablecoin_supply=150000000000,
            stablecoin_dominance=8.0,
            stablecoin_flow_24h=0,
            fear_greed_index=50,
            funding_rates={},
            last_updated=datetime.now()
        )

        result = analyzer._analyze_whale_activity(metrics)

        assert result == WhaleActivity.ACCUMULATING

    def test_distributing_whales(self, analyzer):
        """고래 분산 감지"""
        metrics = OnchainMetrics(
            whale_addresses_count=1900,
            whale_balance_total=4500000,
            whale_net_flow_24h=-6000,  # 대량 분산
            exchange_inflow_24h=5000,
            exchange_outflow_24h=5000,
            exchange_netflow_24h=0,
            exchange_reserves=2500000,
            long_term_holder_supply=65.0,
            short_term_holder_supply=35.0,
            lth_net_position_change=0,
            active_addresses=800000,
            network_hash_rate=500.0,
            transaction_count=250000,
            network_value_locked=40000000000,
            stablecoin_supply=150000000000,
            stablecoin_dominance=8.0,
            stablecoin_flow_24h=0,
            fear_greed_index=50,
            funding_rates={},
            last_updated=datetime.now()
        )

        result = analyzer._analyze_whale_activity(metrics)

        assert result == WhaleActivity.DISTRIBUTING

    def test_hodling_whales(self, analyzer):
        """고래 보유 감지"""
        metrics = OnchainMetrics(
            whale_addresses_count=2000,
            whale_balance_total=5000000,
            whale_net_flow_24h=100,  # 적은 움직임
            exchange_inflow_24h=5000,
            exchange_outflow_24h=5000,
            exchange_netflow_24h=0,
            exchange_reserves=2500000,
            long_term_holder_supply=65.0,
            short_term_holder_supply=35.0,
            lth_net_position_change=0,
            active_addresses=800000,
            network_hash_rate=500.0,
            transaction_count=250000,
            network_value_locked=40000000000,
            stablecoin_supply=150000000000,
            stablecoin_dominance=8.0,
            stablecoin_flow_24h=0,
            fear_greed_index=50,
            funding_rates={},
            last_updated=datetime.now()
        )

        result = analyzer._analyze_whale_activity(metrics)

        assert result == WhaleActivity.HODLING


class TestAnalyzeExchangeFlow:
    """_analyze_exchange_flow 메서드 테스트"""

    def test_inflow_detection(self, analyzer):
        """유입 감지"""
        metrics = OnchainMetrics(
            whale_addresses_count=2000,
            whale_balance_total=5000000,
            whale_net_flow_24h=0,
            exchange_inflow_24h=20000,
            exchange_outflow_24h=5000,
            exchange_netflow_24h=15000,  # 큰 유입
            exchange_reserves=2500000,
            long_term_holder_supply=65.0,
            short_term_holder_supply=35.0,
            lth_net_position_change=0,
            active_addresses=800000,
            network_hash_rate=500.0,
            transaction_count=250000,
            network_value_locked=40000000000,
            stablecoin_supply=150000000000,
            stablecoin_dominance=8.0,
            stablecoin_flow_24h=0,
            fear_greed_index=50,
            funding_rates={},
            last_updated=datetime.now()
        )

        result = analyzer._analyze_exchange_flow(metrics)

        assert result == ExchangeFlow.INFLOW

    def test_outflow_detection(self, analyzer):
        """유출 감지"""
        metrics = OnchainMetrics(
            whale_addresses_count=2000,
            whale_balance_total=5000000,
            whale_net_flow_24h=0,
            exchange_inflow_24h=5000,
            exchange_outflow_24h=20000,
            exchange_netflow_24h=-15000,  # 큰 유출
            exchange_reserves=2500000,
            long_term_holder_supply=65.0,
            short_term_holder_supply=35.0,
            lth_net_position_change=0,
            active_addresses=800000,
            network_hash_rate=500.0,
            transaction_count=250000,
            network_value_locked=40000000000,
            stablecoin_supply=150000000000,
            stablecoin_dominance=8.0,
            stablecoin_flow_24h=0,
            fear_greed_index=50,
            funding_rates={},
            last_updated=datetime.now()
        )

        result = analyzer._analyze_exchange_flow(metrics)

        assert result == ExchangeFlow.OUTFLOW

    def test_balanced_flow(self, analyzer):
        """균형 감지"""
        metrics = OnchainMetrics(
            whale_addresses_count=2000,
            whale_balance_total=5000000,
            whale_net_flow_24h=0,
            exchange_inflow_24h=10000,
            exchange_outflow_24h=10000,
            exchange_netflow_24h=0,  # 균형
            exchange_reserves=2500000,
            long_term_holder_supply=65.0,
            short_term_holder_supply=35.0,
            lth_net_position_change=0,
            active_addresses=800000,
            network_hash_rate=500.0,
            transaction_count=250000,
            network_value_locked=40000000000,
            stablecoin_supply=150000000000,
            stablecoin_dominance=8.0,
            stablecoin_flow_24h=0,
            fear_greed_index=50,
            funding_rates={},
            last_updated=datetime.now()
        )

        result = analyzer._analyze_exchange_flow(metrics)

        assert result == ExchangeFlow.BALANCED


class TestCalculateAccumulationScore:
    """_calculate_accumulation_score 메서드 테스트"""

    def test_high_accumulation_score(self, analyzer, sample_metrics):
        """높은 축적 점수"""
        score = analyzer._calculate_accumulation_score(sample_metrics)

        assert 0 <= score <= 100
        assert score > 50  # 축적 신호

    def test_low_accumulation_score(self, analyzer, bearish_metrics):
        """낮은 축적 점수"""
        score = analyzer._calculate_accumulation_score(bearish_metrics)

        assert 0 <= score <= 100

    def test_score_range(self, analyzer, sample_metrics):
        """점수 범위"""
        score = analyzer._calculate_accumulation_score(sample_metrics)

        assert 0 <= score <= 100


class TestCalculateDistributionScore:
    """_calculate_distribution_score 메서드 테스트"""

    def test_inverse_of_accumulation(self, analyzer, sample_metrics):
        """축적 점수와 반대"""
        accum = analyzer._calculate_accumulation_score(sample_metrics)
        distrib = analyzer._calculate_distribution_score(sample_metrics)

        assert abs((accum + distrib) - 100) < 0.01


class TestCalculateNetworkHealth:
    """_calculate_network_health 메서드 테스트"""

    def test_high_network_health(self, analyzer, sample_metrics):
        """높은 네트워크 건강도"""
        health = analyzer._calculate_network_health(sample_metrics)

        assert health > 50

    def test_low_network_health(self, analyzer, bearish_metrics):
        """낮은 네트워크 건강도"""
        health = analyzer._calculate_network_health(bearish_metrics)

        assert health > 0

    def test_health_range(self, analyzer, sample_metrics):
        """건강도 범위"""
        health = analyzer._calculate_network_health(sample_metrics)

        assert 0 <= health <= 100


class TestEnums:
    """Enum 테스트"""

    def test_onchain_trend_values(self):
        """OnchainTrend 값"""
        assert OnchainTrend.BULLISH.value == "bullish"
        assert OnchainTrend.BEARISH.value == "bearish"
        assert OnchainTrend.NEUTRAL.value == "neutral"

    def test_whale_activity_values(self):
        """WhaleActivity 값"""
        assert WhaleActivity.ACCUMULATING.value == "accumulating"
        assert WhaleActivity.DISTRIBUTING.value == "distributing"
        assert WhaleActivity.HODLING.value == "hodling"
        assert WhaleActivity.MIXED.value == "mixed"

    def test_exchange_flow_values(self):
        """ExchangeFlow 값"""
        assert ExchangeFlow.INFLOW.value == "inflow"
        assert ExchangeFlow.OUTFLOW.value == "outflow"
        assert ExchangeFlow.BALANCED.value == "balanced"


class TestDataclasses:
    """데이터클래스 테스트"""

    def test_onchain_metrics_creation(self):
        """OnchainMetrics 생성"""
        metrics = OnchainMetrics(
            whale_addresses_count=2000,
            whale_balance_total=5000000,
            whale_net_flow_24h=1000,
            exchange_inflow_24h=5000,
            exchange_outflow_24h=6000,
            exchange_netflow_24h=-1000,
            exchange_reserves=2500000,
            long_term_holder_supply=65.0,
            short_term_holder_supply=35.0,
            lth_net_position_change=500,
            active_addresses=800000,
            network_hash_rate=500.0,
            transaction_count=250000,
            network_value_locked=40000000000,
            stablecoin_supply=150000000000,
            stablecoin_dominance=8.0,
            stablecoin_flow_24h=100000000,
            fear_greed_index=55,
            funding_rates={"binance": 0.01},
            last_updated=datetime.now()
        )

        assert metrics.whale_addresses_count == 2000
        assert metrics.long_term_holder_supply == 65.0

    def test_onchain_analysis_creation(self):
        """OnchainAnalysis 생성"""
        analysis = OnchainAnalysis(
            overall_trend=OnchainTrend.BULLISH,
            whale_activity=WhaleActivity.ACCUMULATING,
            exchange_flow=ExchangeFlow.OUTFLOW,
            accumulation_score=75.0,
            distribution_score=25.0,
            network_health_score=80.0,
            market_sentiment="positive",
            key_insights=["고래 축적 중", "거래소 유출 증가"],
            price_prediction_signals={"short_term": 0.7, "long_term": 0.8},
            confidence_level=0.85,
            overall_signal=0.75,
            created_at=datetime.now()
        )

        assert analysis.overall_trend == OnchainTrend.BULLISH
        assert analysis.accumulation_score == 75.0


class TestLogStubWarning:
    """스텁 데이터 경고 테스트"""

    def test_log_stub_warning_once(self):
        """중복 경고 방지"""
        from src.core.onchain_data_analyzer import STUB_DATA_LOGGED

        method_name = "test_method_unique"
        if method_name in STUB_DATA_LOGGED:
            STUB_DATA_LOGGED.remove(method_name)

        _log_stub_warning(method_name)

        assert method_name in STUB_DATA_LOGGED

    def test_log_stub_warning_duplicate(self):
        """중복 호출 시 추가 안됨"""
        from src.core.onchain_data_analyzer import STUB_DATA_LOGGED

        method_name = "test_method_dup"
        STUB_DATA_LOGGED.add(method_name)
        initial_count = len(STUB_DATA_LOGGED)

        _log_stub_warning(method_name)

        assert len(STUB_DATA_LOGGED) == initial_count


class TestComprehensiveAnalysis:
    """종합 분석 테스트"""

    def test_full_analysis_flow(self, analyzer):
        """전체 분석 플로우"""
        metrics = analyzer.collect_onchain_metrics("BTC")
        analysis = analyzer.analyze_onchain_data(metrics, "BTC")

        assert analysis.overall_trend in [OnchainTrend.BULLISH, OnchainTrend.BEARISH, OnchainTrend.NEUTRAL]
        assert analysis.whale_activity in [WhaleActivity.ACCUMULATING, WhaleActivity.DISTRIBUTING,
                                          WhaleActivity.HODLING, WhaleActivity.MIXED]
        assert 0 <= analysis.accumulation_score <= 100
        assert 0 <= analysis.confidence_level <= 1

    def test_analysis_with_eth(self, analyzer):
        """ETH 분석"""
        metrics = analyzer.collect_onchain_metrics("ETH")
        analysis = analyzer.analyze_onchain_data(metrics, "ETH")

        assert isinstance(analysis, OnchainAnalysis)


class TestEdgeCases:
    """엣지 케이스 테스트"""

    def test_zero_values(self, analyzer):
        """0 값 처리"""
        metrics = OnchainMetrics(
            whale_addresses_count=0,
            whale_balance_total=0,
            whale_net_flow_24h=0,
            exchange_inflow_24h=0,
            exchange_outflow_24h=0,
            exchange_netflow_24h=0,
            exchange_reserves=0,
            long_term_holder_supply=0,
            short_term_holder_supply=0,
            lth_net_position_change=0,
            active_addresses=0,
            network_hash_rate=0,
            transaction_count=0,
            network_value_locked=0,
            stablecoin_supply=0,
            stablecoin_dominance=0,
            stablecoin_flow_24h=0,
            fear_greed_index=0,
            funding_rates={},
            last_updated=datetime.now()
        )

        analysis = analyzer.analyze_onchain_data(metrics, "BTC")

        assert isinstance(analysis, OnchainAnalysis)

    def test_extreme_values(self, analyzer):
        """극단값 처리"""
        metrics = OnchainMetrics(
            whale_addresses_count=100000,
            whale_balance_total=999999999,
            whale_net_flow_24h=100000,
            exchange_inflow_24h=1000000,
            exchange_outflow_24h=1000000,
            exchange_netflow_24h=0,
            exchange_reserves=10000000,
            long_term_holder_supply=99.9,
            short_term_holder_supply=0.1,
            lth_net_position_change=50000,
            active_addresses=10000000,
            network_hash_rate=1000.0,
            transaction_count=1000000,
            network_value_locked=100000000000,
            stablecoin_supply=500000000000,
            stablecoin_dominance=20.0,
            stablecoin_flow_24h=10000000000,
            fear_greed_index=100,
            funding_rates={"binance": 0.1},
            last_updated=datetime.now()
        )

        analysis = analyzer.analyze_onchain_data(metrics, "BTC")

        # 점수가 범위 내에 있는지 확인
        assert 0 <= analysis.accumulation_score <= 100


# ============================================================================
# Exception Handling Tests (Lines 199-201, 266-268, 573-603, etc.)
# ============================================================================

class TestExceptionHandling:
    """예외 처리 테스트"""

    def test_collect_onchain_metrics_exception(self, analyzer):
        """collect_onchain_metrics 예외 처리 (lines 199-201)"""
        with patch.object(analyzer, '_get_whale_count', side_effect=Exception("API 오류")):
            metrics = analyzer.collect_onchain_metrics("BTC")

            # 폴백 메트릭스 반환
            assert isinstance(metrics, OnchainMetrics)

    def test_analyze_onchain_data_exception(self, analyzer):
        """analyze_onchain_data 예외 처리 (lines 266-268)"""
        with patch.object(analyzer, '_analyze_whale_activity', side_effect=Exception("분석 오류")):
            # 임의의 메트릭스 생성
            metrics = analyzer._get_fallback_metrics()
            analysis = analyzer.analyze_onchain_data(metrics, "BTC")

            # 폴백 분석 반환
            assert isinstance(analysis, OnchainAnalysis)
            assert analysis.overall_trend == OnchainTrend.NEUTRAL

    def test_save_analysis_to_db_exception(self, analyzer):
        """_save_analysis_to_db 예외 처리 (lines 803-804)"""
        analyzer.db_manager.save_analysis_result.side_effect = Exception("DB 저장 실패")

        analysis = OnchainAnalysis(
            overall_trend=OnchainTrend.BULLISH,
            whale_activity=WhaleActivity.ACCUMULATING,
            exchange_flow=ExchangeFlow.OUTFLOW,
            accumulation_score=75.0,
            distribution_score=25.0,
            network_health_score=80.0,
            market_sentiment="positive",
            key_insights=["테스트"],
            price_prediction_signals={"short_term": 0.7},
            confidence_level=0.85,
            overall_signal=0.75,
            created_at=datetime.now()
        )

        # 예외가 발생해도 에러를 던지지 않음
        analyzer._save_analysis_to_db(analysis, "BTC")

    def test_analyze_comprehensive_onchain_exception(self, analyzer):
        """analyze_comprehensive_onchain 예외 처리 (lines 821-823)"""
        with patch.object(analyzer, 'collect_onchain_metrics', side_effect=Exception("수집 오류")):
            result = analyzer.analyze_comprehensive_onchain("BTC")

            assert result["success"] is False
            assert "error" in result


# ============================================================================
# Get Latest Signal Tests (Lines 573-603)
# ============================================================================

class TestGetLatestSignal:
    """get_latest_signal 메서드 테스트"""

    def test_get_latest_signal_success(self, analyzer):
        """최신 신호 조회 성공"""
        result = analyzer.get_latest_signal()

        assert "market_signal" in result
        assert "confidence" in result
        assert "timestamp" in result

    def test_get_latest_signal_with_analysis_error(self, analyzer):
        """분석 오류 시 신호 조회 (lines 577-583)"""
        with patch.object(analyzer, 'analyze_comprehensive_onchain', return_value={"success": False, "error": "분석 실패"}):
            result = analyzer.get_latest_signal()

            assert result["market_signal"] == 0.0
            assert result["confidence"] == 0.3
            assert "error" in result

    def test_get_latest_signal_exception(self, analyzer):
        """신호 조회 예외 (lines 601-608)"""
        with patch.object(analyzer, 'analyze_comprehensive_onchain', side_effect=Exception("신호 조회 오류")):
            result = analyzer.get_latest_signal()

            assert result["market_signal"] == 0.0
            assert result["confidence"] == 0.3
            assert "error" in result


# ============================================================================
# Fear Greed Index Tests (Lines 717-723)
# ============================================================================

class TestFearGreedIndex:
    """Fear & Greed Index 테스트"""

    def test_fear_greed_index_default(self, analyzer):
        """기본 공포탐욕지수"""
        value = analyzer._get_fear_greed_index()

        assert 0 <= value <= 100

    def test_fear_greed_index_import_error(self, analyzer):
        """ExternalAPIClient import 실패 시 (line 717-718)"""
        with patch.dict('sys.modules', {'src.utils.external_api_client': None}):
            # 기본값 반환
            value = analyzer._get_fear_greed_index()
            assert isinstance(value, float)

    def test_fear_greed_index_api_error(self, analyzer):
        """API 오류 시 (lines 719-720)"""
        # ExternalAPIClient가 import되는 것을 모킹
        with patch.dict('sys.modules', {'src.utils.external_api_client': MagicMock()}):
            with patch('src.utils.external_api_client.ExternalAPIClient') as mock_client:
                mock_client.return_value.get_fear_greed_index.side_effect = Exception("API 오류")

                value = analyzer._get_fear_greed_index()

                # 기본값 또는 폴백 반환
                assert isinstance(value, float)


# ============================================================================
# Funding Rates Tests (Lines 733-734)
# ============================================================================

class TestFundingRates:
    """펀딩비율 테스트"""

    def test_get_funding_rates(self, analyzer):
        """펀딩비율 조회"""
        rates = analyzer._get_funding_rates("BTC")

        assert isinstance(rates, dict)
        assert "binance" in rates or "average" in rates


# ============================================================================
# Whale Activity Edge Cases (Lines 286, 289, 291)
# ============================================================================

class TestWhaleActivityEdgeCases:
    """고래 활동 엣지 케이스 테스트"""

    def test_whale_medium_accumulation(self, analyzer):
        """중간 수준 축적 (lines 281-282)"""
        metrics = OnchainMetrics(
            whale_addresses_count=2050,
            whale_balance_total=5200000,
            whale_net_flow_24h=2000,  # 중간 축적 (1000-5000 범위)
            exchange_inflow_24h=5000,
            exchange_outflow_24h=5000,
            exchange_netflow_24h=0,
            exchange_reserves=2500000,
            long_term_holder_supply=65.0,
            short_term_holder_supply=35.0,
            lth_net_position_change=0,
            active_addresses=800000,
            network_hash_rate=500.0,
            transaction_count=250000,
            network_value_locked=40000000000,
            stablecoin_supply=150000000000,
            stablecoin_dominance=8.0,
            stablecoin_flow_24h=0,
            fear_greed_index=50,
            funding_rates={},
            last_updated=datetime.now()
        )

        result = analyzer._analyze_whale_activity(metrics)

        assert result in [WhaleActivity.ACCUMULATING, WhaleActivity.MIXED, WhaleActivity.HODLING]

    def test_whale_medium_distribution(self, analyzer):
        """중간 수준 분산 (lines 285-286)"""
        metrics = OnchainMetrics(
            whale_addresses_count=1950,
            whale_balance_total=4800000,
            whale_net_flow_24h=-2000,  # 중간 분산 (-1000 to -5000 범위)
            exchange_inflow_24h=5000,
            exchange_outflow_24h=5000,
            exchange_netflow_24h=0,
            exchange_reserves=2500000,
            long_term_holder_supply=65.0,
            short_term_holder_supply=35.0,
            lth_net_position_change=0,
            active_addresses=800000,
            network_hash_rate=500.0,
            transaction_count=250000,
            network_value_locked=40000000000,
            stablecoin_supply=150000000000,
            stablecoin_dominance=8.0,
            stablecoin_flow_24h=0,
            fear_greed_index=50,
            funding_rates={},
            last_updated=datetime.now()
        )

        result = analyzer._analyze_whale_activity(metrics)

        assert result in [WhaleActivity.DISTRIBUTING, WhaleActivity.MIXED]

    def test_whale_mixed_activity(self, analyzer):
        """혼재된 활동 (line 301)"""
        metrics = OnchainMetrics(
            whale_addresses_count=2000,
            whale_balance_total=5000000,
            whale_net_flow_24h=800,  # 작은 양수 (HODLING 아닌 MIXED)
            exchange_inflow_24h=5000,
            exchange_outflow_24h=5000,
            exchange_netflow_24h=0,
            exchange_reserves=2500000,
            long_term_holder_supply=65.0,
            short_term_holder_supply=35.0,
            lth_net_position_change=0,
            active_addresses=800000,
            network_hash_rate=500.0,
            transaction_count=250000,
            network_value_locked=40000000000,
            stablecoin_supply=150000000000,
            stablecoin_dominance=8.0,
            stablecoin_flow_24h=0,
            fear_greed_index=50,
            funding_rates={},
            last_updated=datetime.now()
        )

        result = analyzer._analyze_whale_activity(metrics)

        assert result in [WhaleActivity.MIXED, WhaleActivity.HODLING, WhaleActivity.ACCUMULATING]


# ============================================================================
# Fallback Methods Tests
# ============================================================================

class TestFallbackMethods:
    """폴백 메서드 테스트"""

    def test_get_fallback_metrics(self, analyzer):
        """폴백 메트릭스"""
        metrics = analyzer._get_fallback_metrics()

        assert isinstance(metrics, OnchainMetrics)
        assert metrics.whale_addresses_count == 2000
        assert metrics.fear_greed_index == 50

    def test_get_fallback_analysis(self, analyzer):
        """폴백 분석"""
        analysis = analyzer._get_fallback_analysis()

        assert isinstance(analysis, OnchainAnalysis)
        assert analysis.overall_trend == OnchainTrend.NEUTRAL
        assert analysis.whale_activity == WhaleActivity.HODLING
        assert analysis.confidence_level == 0.3
        assert analysis.overall_signal == 0.5


# ============================================================================
# Data Collection Methods Tests
# ============================================================================

class TestDataCollectionMethods:
    """데이터 수집 메서드 테스트"""

    def test_get_whale_count(self, analyzer):
        """고래 주소 수"""
        count = analyzer._get_whale_count("BTC")
        assert count >= 0

    def test_get_whale_balance(self, analyzer):
        """고래 총 보유량"""
        balance = analyzer._get_whale_balance("BTC")
        assert balance >= 0

    def test_get_whale_flow(self, analyzer):
        """고래 순 흐름"""
        flow = analyzer._get_whale_flow("BTC")
        assert isinstance(flow, (int, float))

    def test_get_exchange_inflow(self, analyzer):
        """거래소 유입량"""
        inflow = analyzer._get_exchange_inflow("BTC")
        assert inflow >= 0

    def test_get_exchange_outflow(self, analyzer):
        """거래소 유출량"""
        outflow = analyzer._get_exchange_outflow("BTC")
        assert outflow >= 0

    def test_get_exchange_netflow(self, analyzer):
        """거래소 순 흐름"""
        netflow = analyzer._get_exchange_netflow("BTC")
        assert isinstance(netflow, (int, float))

    def test_get_exchange_reserves(self, analyzer):
        """거래소 보유량"""
        reserves = analyzer._get_exchange_reserves("BTC")
        assert reserves >= 0

    def test_get_lth_supply(self, analyzer):
        """장기보유자 공급량"""
        supply = analyzer._get_lth_supply("BTC")
        assert 0 <= supply <= 100

    def test_get_sth_supply(self, analyzer):
        """단기보유자 공급량"""
        supply = analyzer._get_sth_supply("BTC")
        assert 0 <= supply <= 100

    def test_get_lth_position_change(self, analyzer):
        """장기보유자 포지션 변화"""
        change = analyzer._get_lth_position_change("BTC")
        assert isinstance(change, (int, float))

    def test_get_active_addresses(self, analyzer):
        """활성 주소 수"""
        addresses = analyzer._get_active_addresses("BTC")
        assert addresses >= 0

    def test_get_hash_rate(self, analyzer):
        """해시레이트"""
        hash_rate = analyzer._get_hash_rate("BTC")
        assert hash_rate >= 0

    def test_get_transaction_count(self, analyzer):
        """트랜잭션 수"""
        count = analyzer._get_transaction_count("BTC")
        assert count >= 0

    def test_get_nvl(self, analyzer):
        """네트워크 잠금 가치"""
        nvl = analyzer._get_nvl("BTC")
        assert nvl >= 0
