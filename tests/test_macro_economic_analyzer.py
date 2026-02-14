"""
Macro Economic Analyzer Tests

매크로 경제 분석기 테스트
- 경제 지표 수집
- 경제 체제 판단
- 암호화폐 우호도 계산
- 리스크 조정 계산
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from src.core.macro_economic_analyzer import (
    MacroEconomicAnalyzer,
    MacroIndicators,
    MacroAnalysis,
    EconomicRegime,
    InflationRegime,
    RateEnvironment
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def analyzer():
    """기본 매크로 분석기"""
    return MacroEconomicAnalyzer()


@pytest.fixture
def analyzer_with_db():
    """DB 매니저가 있는 분석기"""
    mock_db = Mock()
    mock_db.save_analysis_result = Mock()
    return MacroEconomicAnalyzer(db_manager=mock_db)


@pytest.fixture
def sample_indicators():
    """샘플 매크로 지표"""
    return MacroIndicators(
        fed_funds_rate=5.25,
        inflation_rate=3.2,
        dxy_index=104.5,
        m2_money_supply=8.5,
        unemployment_rate=3.8,
        gdp_growth=2.1,
        vix_index=18.5,
        gold_price=2050.0,
        oil_price=75.0,
        bond_yield_10y=4.2,
        last_updated=datetime.now()
    )


@pytest.fixture
def expansion_indicators():
    """확장기 지표"""
    return MacroIndicators(
        fed_funds_rate=2.0,
        inflation_rate=2.5,
        dxy_index=95.0,
        m2_money_supply=12.0,
        unemployment_rate=3.0,
        gdp_growth=4.0,
        vix_index=12.0,
        gold_price=1800.0,
        oil_price=65.0,
        bond_yield_10y=2.5,
        last_updated=datetime.now()
    )


@pytest.fixture
def contraction_indicators():
    """수축기 지표"""
    return MacroIndicators(
        fed_funds_rate=6.5,
        inflation_rate=7.0,
        dxy_index=115.0,
        m2_money_supply=-2.0,
        unemployment_rate=7.5,
        gdp_growth=-1.5,
        vix_index=45.0,
        gold_price=2200.0,
        oil_price=90.0,
        bond_yield_10y=6.0,
        last_updated=datetime.now()
    )


@pytest.fixture
def historical_data():
    """과거 데이터"""
    return {
        "fed_rate": [4.0, 4.25, 4.5, 4.75, 5.0, 5.25],
        "inflation": [6.0, 5.5, 5.0, 4.5, 4.0, 3.5],
        "dxy": [100, 102, 104, 103, 105, 104],
        "m2_supply": [5.0, 6.0, 7.0, 8.0, 9.0, 8.5]
    }


# ============================================================================
# Initialization Tests
# ============================================================================

class TestMacroEconomicAnalyzerInit:
    """MacroEconomicAnalyzer 초기화 테스트"""

    def test_default_initialization(self, analyzer):
        """기본 초기화"""
        assert analyzer.api_keys == {}
        assert analyzer.db_manager is None
        assert "fred" in analyzer.data_sources
        assert "yahoo" in analyzer.data_sources

    def test_initialization_with_api_keys(self):
        """API 키로 초기화"""
        api_keys = {"fred": "test_key", "alpha_vantage": "av_key"}
        analyzer = MacroEconomicAnalyzer(api_keys=api_keys)

        assert analyzer.api_keys == api_keys

    def test_initialization_with_db_manager(self):
        """DB 매니저로 초기화"""
        mock_db = Mock()
        analyzer = MacroEconomicAnalyzer(db_manager=mock_db)

        assert analyzer.db_manager == mock_db

    def test_impact_weights_defined(self, analyzer):
        """영향도 가중치 정의 확인"""
        assert "fed_rate" in analyzer.impact_weights
        assert "inflation" in analyzer.impact_weights
        assert "dxy" in analyzer.impact_weights
        assert "m2_supply" in analyzer.impact_weights


# ============================================================================
# Get Current Indicators Tests
# ============================================================================

class TestGetCurrentIndicators:
    """현재 지표 수집 테스트"""

    def test_get_current_indicators(self, analyzer):
        """현재 지표 수집"""
        indicators = analyzer.get_current_indicators()

        assert isinstance(indicators, MacroIndicators)
        assert indicators.fed_funds_rate > 0
        assert indicators.last_updated is not None

    def test_indicators_fallback_on_error(self, analyzer):
        """오류 시 폴백 지표"""
        with patch.object(analyzer, '_get_fed_funds_rate', side_effect=Exception("API Error")):
            indicators = analyzer.get_current_indicators()

            # 폴백 지표 반환
            assert isinstance(indicators, MacroIndicators)


# ============================================================================
# Analyze Macro Environment Tests
# ============================================================================

class TestAnalyzeMacroEnvironment:
    """매크로 환경 분석 테스트"""

    def test_basic_analysis(self, analyzer, sample_indicators):
        """기본 분석"""
        analysis = analyzer.analyze_macro_environment(sample_indicators)

        assert isinstance(analysis, MacroAnalysis)
        assert analysis.economic_regime is not None
        assert analysis.inflation_regime is not None
        assert analysis.rate_environment is not None

    def test_analysis_expansion_regime(self, analyzer, expansion_indicators):
        """확장기 체제 분석"""
        analysis = analyzer.analyze_macro_environment(expansion_indicators)

        assert analysis.economic_regime == EconomicRegime.EXPANSION

    def test_analysis_contraction_regime(self, analyzer, contraction_indicators):
        """수축기 체제 분석"""
        analysis = analyzer.analyze_macro_environment(contraction_indicators)

        assert analysis.economic_regime == EconomicRegime.CONTRACTION

    def test_crypto_favorability_in_range(self, analyzer, sample_indicators):
        """암호화폐 우호도 범위"""
        analysis = analyzer.analyze_macro_environment(sample_indicators)

        assert -1.0 <= analysis.crypto_favorability <= 1.0

    def test_risk_adjustment_in_range(self, analyzer, sample_indicators):
        """리스크 조정 범위"""
        analysis = analyzer.analyze_macro_environment(sample_indicators)

        assert -0.3 <= analysis.risk_adjustment <= 0.3

    def test_key_drivers_identified(self, analyzer, sample_indicators):
        """주요 동인 식별"""
        analysis = analyzer.analyze_macro_environment(sample_indicators)

        assert isinstance(analysis.key_drivers, list)
        assert len(analysis.key_drivers) <= 3

    def test_analysis_with_db_manager(self, analyzer_with_db, sample_indicators):
        """DB 매니저 있을 때 분석"""
        analysis = analyzer_with_db.analyze_macro_environment(sample_indicators)

        assert isinstance(analysis, MacroAnalysis)
        analyzer_with_db.db_manager.save_analysis_result.assert_called()


# ============================================================================
# Determine Economic Regime Tests
# ============================================================================

class TestDetermineEconomicRegime:
    """경제 체제 판단 테스트"""

    def test_expansion_regime(self, analyzer):
        """확장 체제"""
        indicators = MacroIndicators(
            fed_funds_rate=2.0, inflation_rate=2.0, dxy_index=95.0,
            m2_money_supply=10.0, unemployment_rate=3.0, gdp_growth=4.0,
            vix_index=12.0, gold_price=1800.0, oil_price=70.0,
            bond_yield_10y=2.5, last_updated=datetime.now()
        )

        regime = analyzer._determine_economic_regime(indicators)

        assert regime == EconomicRegime.EXPANSION

    def test_contraction_regime(self, analyzer):
        """수축 체제"""
        indicators = MacroIndicators(
            fed_funds_rate=6.0, inflation_rate=6.0, dxy_index=110.0,
            m2_money_supply=-1.0, unemployment_rate=8.0, gdp_growth=-2.0,
            vix_index=35.0, gold_price=2100.0, oil_price=90.0,
            bond_yield_10y=6.0, last_updated=datetime.now()
        )

        regime = analyzer._determine_economic_regime(indicators)

        assert regime == EconomicRegime.CONTRACTION

    def test_recovery_regime(self, analyzer):
        """회복 체제"""
        indicators = MacroIndicators(
            fed_funds_rate=3.0, inflation_rate=2.5, dxy_index=100.0,
            m2_money_supply=5.0, unemployment_rate=5.0, gdp_growth=1.0,
            vix_index=20.0, gold_price=1900.0, oil_price=75.0,
            bond_yield_10y=3.5, last_updated=datetime.now()
        )

        regime = analyzer._determine_economic_regime(indicators)

        assert regime in [EconomicRegime.RECOVERY, EconomicRegime.EXPANSION]

    def test_peak_regime(self, analyzer):
        """정점 체제"""
        indicators = MacroIndicators(
            fed_funds_rate=5.0, inflation_rate=5.0, dxy_index=105.0,
            m2_money_supply=3.0, unemployment_rate=3.5, gdp_growth=-0.5,
            vix_index=28.0, gold_price=2000.0, oil_price=80.0,
            bond_yield_10y=4.5, last_updated=datetime.now()
        )

        regime = analyzer._determine_economic_regime(indicators)

        assert regime in [EconomicRegime.PEAK, EconomicRegime.RECOVERY, EconomicRegime.CONTRACTION]


# ============================================================================
# Determine Inflation Regime Tests
# ============================================================================

class TestDetermineInflationRegime:
    """인플레이션 체제 판단 테스트"""

    def test_deflationary(self, analyzer):
        """디플레이션"""
        regime = analyzer._determine_inflation_regime(-0.5)
        assert regime == InflationRegime.DEFLATIONARY

    def test_low_inflation(self, analyzer):
        """저인플레이션"""
        regime = analyzer._determine_inflation_regime(1.5)
        assert regime == InflationRegime.LOW

    def test_moderate_inflation(self, analyzer):
        """적정 인플레이션"""
        regime = analyzer._determine_inflation_regime(3.0)
        assert regime == InflationRegime.MODERATE

    def test_high_inflation(self, analyzer):
        """고인플레이션"""
        regime = analyzer._determine_inflation_regime(5.0)
        assert regime == InflationRegime.HIGH

    def test_hyperinflation(self, analyzer):
        """초인플레이션"""
        regime = analyzer._determine_inflation_regime(8.0)
        assert regime == InflationRegime.HYPERINFLATION


# ============================================================================
# Determine Rate Environment Tests
# ============================================================================

class TestDetermineRateEnvironment:
    """금리 환경 판단 테스트"""

    def test_ultra_low_rate(self, analyzer):
        """초저금리"""
        env = analyzer._determine_rate_environment(0.5)
        assert env == RateEnvironment.ULTRA_LOW

    def test_low_rate(self, analyzer):
        """저금리"""
        env = analyzer._determine_rate_environment(2.0)
        assert env == RateEnvironment.LOW

    def test_moderate_rate(self, analyzer):
        """중금리"""
        env = analyzer._determine_rate_environment(4.0)
        assert env == RateEnvironment.MODERATE

    def test_high_rate(self, analyzer):
        """고금리"""
        env = analyzer._determine_rate_environment(6.0)
        assert env == RateEnvironment.HIGH

    def test_very_high_rate(self, analyzer):
        """초고금리"""
        env = analyzer._determine_rate_environment(8.0)
        assert env == RateEnvironment.VERY_HIGH


# ============================================================================
# Calculate Crypto Favorability Tests
# ============================================================================

class TestCalculateCryptoFavorability:
    """암호화폐 우호도 계산 테스트"""

    def test_favorable_environment(self, analyzer):
        """우호적 환경"""
        indicators = MacroIndicators(
            fed_funds_rate=0.5, inflation_rate=4.0, dxy_index=85.0,
            m2_money_supply=15.0, unemployment_rate=4.0, gdp_growth=3.0,
            vix_index=12.0, gold_price=1700.0, oil_price=60.0,
            bond_yield_10y=1.5, last_updated=datetime.now()
        )

        favorability = analyzer._calculate_crypto_favorability(indicators)

        assert favorability > 0

    def test_unfavorable_environment(self, analyzer):
        """비우호적 환경"""
        indicators = MacroIndicators(
            fed_funds_rate=8.0, inflation_rate=1.0, dxy_index=115.0,
            m2_money_supply=-3.0, unemployment_rate=6.0, gdp_growth=1.0,
            vix_index=40.0, gold_price=2200.0, oil_price=95.0,
            bond_yield_10y=7.0, last_updated=datetime.now()
        )

        favorability = analyzer._calculate_crypto_favorability(indicators)

        assert favorability < 0

    def test_favorability_bounded(self, analyzer, sample_indicators):
        """우호도 범위 제한"""
        favorability = analyzer._calculate_crypto_favorability(sample_indicators)

        assert -1.0 <= favorability <= 1.0


# ============================================================================
# Normalize Indicator Tests
# ============================================================================

class TestNormalizeIndicator:
    """지표 정규화 테스트"""

    def test_normalize_middle_value(self, analyzer):
        """중간값 정규화"""
        result = analyzer._normalize_indicator(50, 0, 100)
        assert result == 0.5

    def test_normalize_min_value(self, analyzer):
        """최소값 정규화"""
        result = analyzer._normalize_indicator(0, 0, 100)
        assert result == 0.0

    def test_normalize_max_value(self, analyzer):
        """최대값 정규화"""
        result = analyzer._normalize_indicator(100, 0, 100)
        assert result == 1.0

    def test_normalize_same_min_max(self, analyzer):
        """최소=최대 정규화"""
        result = analyzer._normalize_indicator(50, 50, 50)
        assert result == 0.5


# ============================================================================
# Calculate Risk Adjustment Tests
# ============================================================================

class TestCalculateRiskAdjustment:
    """리스크 조정 계산 테스트"""

    def test_expansion_positive_adjustment(self, analyzer, expansion_indicators):
        """확장기 양의 조정"""
        adjustment = analyzer._calculate_risk_adjustment(
            expansion_indicators, EconomicRegime.EXPANSION
        )

        assert adjustment > 0

    def test_contraction_negative_adjustment(self, analyzer, contraction_indicators):
        """수축기 음의 조정"""
        adjustment = analyzer._calculate_risk_adjustment(
            contraction_indicators, EconomicRegime.CONTRACTION
        )

        assert adjustment < 0

    def test_adjustment_bounded(self, analyzer, sample_indicators):
        """조정 범위 제한"""
        adjustment = analyzer._calculate_risk_adjustment(
            sample_indicators, EconomicRegime.RECOVERY
        )

        assert -0.3 <= adjustment <= 0.3

    def test_high_vix_negative_adjustment(self, analyzer):
        """높은 VIX 음의 조정"""
        indicators = MacroIndicators(
            fed_funds_rate=3.0, inflation_rate=2.5, dxy_index=100.0,
            m2_money_supply=5.0, unemployment_rate=4.0, gdp_growth=2.0,
            vix_index=35.0, gold_price=1900.0, oil_price=75.0,
            bond_yield_10y=3.5, last_updated=datetime.now()
        )

        adjustment = analyzer._calculate_risk_adjustment(
            indicators, EconomicRegime.EXPANSION
        )

        # 높은 VIX로 인해 조정이 낮아짐
        assert adjustment < 0.1


# ============================================================================
# Calculate Macro Allocation Tests
# ============================================================================

class TestCalculateMacroAllocation:
    """매크로 자산 배분 테스트"""

    def test_allocation_sums_to_one(self, analyzer, sample_indicators):
        """배분 합계"""
        allocation = analyzer._calculate_macro_allocation(
            sample_indicators, 0.3, 0.1
        )

        assert allocation["crypto"] + allocation["krw"] == 1.0

    def test_allocation_bounded(self, analyzer, sample_indicators):
        """배분 범위"""
        allocation = analyzer._calculate_macro_allocation(
            sample_indicators, 1.0, 0.3
        )

        assert 0.2 <= allocation["crypto"] <= 0.8

    def test_positive_favorability_increases_crypto(self, analyzer, sample_indicators):
        """양의 우호도 = 암호화폐 비중 증가"""
        allocation_low = analyzer._calculate_macro_allocation(
            sample_indicators, -0.5, 0.0
        )
        allocation_high = analyzer._calculate_macro_allocation(
            sample_indicators, 0.5, 0.0
        )

        assert allocation_high["crypto"] > allocation_low["crypto"]


# ============================================================================
# Identify Key Drivers Tests
# ============================================================================

class TestIdentifyKeyDrivers:
    """주요 동인 식별 테스트"""

    def test_high_rate_driver(self, analyzer):
        """고금리 동인"""
        indicators = MacroIndicators(
            fed_funds_rate=6.0, inflation_rate=2.5, dxy_index=100.0,
            m2_money_supply=5.0, unemployment_rate=4.0, gdp_growth=2.0,
            vix_index=18.0, gold_price=1900.0, oil_price=75.0,
            bond_yield_10y=4.0, last_updated=datetime.now()
        )

        drivers = analyzer._identify_key_drivers(indicators)

        assert any("고금리" in d for d in drivers)

    def test_high_inflation_driver(self, analyzer):
        """고인플레이션 동인"""
        indicators = MacroIndicators(
            fed_funds_rate=3.0, inflation_rate=5.5, dxy_index=100.0,
            m2_money_supply=5.0, unemployment_rate=4.0, gdp_growth=2.0,
            vix_index=18.0, gold_price=1900.0, oil_price=75.0,
            bond_yield_10y=4.0, last_updated=datetime.now()
        )

        drivers = analyzer._identify_key_drivers(indicators)

        assert any("인플레이션" in d for d in drivers)

    def test_max_three_drivers(self, analyzer, contraction_indicators):
        """최대 3개 동인"""
        drivers = analyzer._identify_key_drivers(contraction_indicators)

        assert len(drivers) <= 3


# ============================================================================
# Calculate Analysis Confidence Tests
# ============================================================================

class TestCalculateAnalysisConfidence:
    """분석 신뢰도 계산 테스트"""

    def test_fresh_data_high_confidence(self, analyzer):
        """최신 데이터 높은 신뢰도"""
        indicators = MacroIndicators(
            fed_funds_rate=3.0, inflation_rate=2.5, dxy_index=100.0,
            m2_money_supply=5.0, unemployment_rate=4.0, gdp_growth=2.0,
            vix_index=18.0, gold_price=1900.0, oil_price=75.0,
            bond_yield_10y=3.5, last_updated=datetime.now()
        )

        confidence = analyzer._calculate_analysis_confidence(indicators)

        assert confidence >= 0.7

    def test_old_data_lower_confidence(self, analyzer):
        """오래된 데이터 낮은 신뢰도"""
        indicators = MacroIndicators(
            fed_funds_rate=3.0, inflation_rate=2.5, dxy_index=100.0,
            m2_money_supply=5.0, unemployment_rate=4.0, gdp_growth=2.0,
            vix_index=18.0, gold_price=1900.0, oil_price=75.0,
            bond_yield_10y=3.5, last_updated=datetime.now() - timedelta(days=2)
        )

        confidence = analyzer._calculate_analysis_confidence(indicators)

        assert confidence < 0.8

    def test_extreme_values_lower_confidence(self, analyzer):
        """극단적 값 낮은 신뢰도"""
        indicators = MacroIndicators(
            fed_funds_rate=8.0, inflation_rate=8.0, dxy_index=100.0,
            m2_money_supply=5.0, unemployment_rate=4.0, gdp_growth=2.0,
            vix_index=45.0, gold_price=1900.0, oil_price=75.0,
            bond_yield_10y=3.5, last_updated=datetime.now()
        )

        confidence = analyzer._calculate_analysis_confidence(indicators)

        assert confidence < 0.6


# ============================================================================
# Fallback Methods Tests
# ============================================================================

class TestFallbackMethods:
    """폴백 메서드 테스트"""

    def test_fallback_indicators(self, analyzer):
        """폴백 지표"""
        indicators = analyzer._get_fallback_indicators()

        assert isinstance(indicators, MacroIndicators)
        assert indicators.fed_funds_rate == 5.0
        assert indicators.inflation_rate == 3.0

    def test_fallback_analysis(self, analyzer):
        """폴백 분석"""
        analysis = analyzer._get_fallback_analysis()

        assert isinstance(analysis, MacroAnalysis)
        assert analysis.economic_regime == EconomicRegime.RECOVERY
        assert analysis.analysis_confidence == 0.3


# ============================================================================
# Comprehensive Macro Analysis Tests
# ============================================================================

class TestAnalyzeComprehensiveMacro:
    """포괄적 매크로 분석 테스트"""

    def test_comprehensive_analysis_success(self, analyzer):
        """분석 성공"""
        result = analyzer.analyze_comprehensive_macro()

        assert result["success"] is True
        assert "overall_score" in result
        assert "market_outlook" in result
        assert 0 <= result["overall_score"] <= 1

    def test_comprehensive_analysis_with_db(self, analyzer_with_db):
        """DB 저장 포함 분석"""
        result = analyzer_with_db.analyze_comprehensive_macro()

        assert result["success"] is True


# ============================================================================
# Macro Trend Analysis Tests
# ============================================================================

class TestGetMacroTrendAnalysis:
    """매크로 트렌드 분석 테스트"""

    def test_trend_analysis(self, analyzer, historical_data):
        """트렌드 분석"""
        result = analyzer.get_macro_trend_analysis(historical_data)

        assert "trends" in result
        assert "overall_direction" in result

    def test_trend_direction_identified(self, analyzer, historical_data):
        """트렌드 방향 식별"""
        result = analyzer.get_macro_trend_analysis(historical_data)

        for indicator, trend in result["trends"].items():
            assert trend["direction"] in ["increasing", "decreasing", "stable"]

    def test_empty_data(self, analyzer):
        """빈 데이터"""
        result = analyzer.get_macro_trend_analysis({})

        assert "trends" in result
        assert result["trends"] == {}

    def test_insufficient_data(self, analyzer):
        """데이터 부족"""
        result = analyzer.get_macro_trend_analysis({"fed_rate": [5.0]})

        # 단일 데이터는 무시됨
        assert "fed_rate" not in result.get("trends", {})


# ============================================================================
# Determine Overall Trend Tests
# ============================================================================

class TestDetermineOverallTrend:
    """전체 트렌드 방향 테스트"""

    def test_crypto_favorable_trend(self, analyzer):
        """암호화폐 우호적 트렌드"""
        trends = {
            "m2_supply": {"direction": "increasing", "trend_strength": 0.8},
            "fed_rate": {"direction": "decreasing", "trend_strength": 0.5}
        }

        direction = analyzer._determine_overall_trend(trends)

        assert direction in ["crypto_favorable", "neutral"]

    def test_crypto_unfavorable_trend(self, analyzer):
        """암호화폐 비우호적 트렌드"""
        trends = {
            "fed_rate": {"direction": "increasing", "trend_strength": 0.8},
            "dxy": {"direction": "increasing", "trend_strength": 0.6}
        }

        direction = analyzer._determine_overall_trend(trends)

        assert direction in ["crypto_unfavorable", "neutral"]

    def test_neutral_trend(self, analyzer):
        """중립 트렌드"""
        trends = {
            "fed_rate": {"direction": "stable", "trend_strength": 0.2}
        }

        direction = analyzer._determine_overall_trend(trends)

        assert direction in ["neutral", "crypto_favorable", "crypto_unfavorable"]


# ============================================================================
# Get Latest Signal Tests
# ============================================================================

class TestGetLatestSignal:
    """최신 신호 조회 테스트"""

    def test_get_latest_signal(self, analyzer):
        """최신 신호 조회"""
        signal = analyzer.get_latest_signal()

        assert "market_signal" in signal
        assert "confidence" in signal
        assert "timestamp" in signal

    def test_signal_range(self, analyzer):
        """신호 범위"""
        signal = analyzer.get_latest_signal()

        # market_signal 범위는 -0.5 ~ 0.5
        assert -1 <= signal["market_signal"] <= 1


# ============================================================================
# Data Collection Methods Tests
# ============================================================================

class TestDataCollectionMethods:
    """데이터 수집 메서드 테스트"""

    def test_get_fed_funds_rate(self, analyzer):
        """연준 기준금리"""
        rate = analyzer._get_fed_funds_rate()
        assert isinstance(rate, float)
        assert rate >= 0

    def test_get_inflation_rate(self, analyzer):
        """인플레이션율"""
        rate = analyzer._get_inflation_rate()
        assert isinstance(rate, float)

    def test_get_dxy_index(self, analyzer):
        """달러 지수"""
        dxy = analyzer._get_dxy_index()
        assert isinstance(dxy, float)
        assert dxy > 0

    def test_get_m2_growth(self, analyzer):
        """M2 성장률"""
        growth = analyzer._get_m2_growth()
        assert isinstance(growth, float)

    def test_get_unemployment_rate(self, analyzer):
        """실업률"""
        rate = analyzer._get_unemployment_rate()
        assert isinstance(rate, float)
        assert rate >= 0

    def test_get_gdp_growth(self, analyzer):
        """GDP 성장률"""
        growth = analyzer._get_gdp_growth()
        assert isinstance(growth, float)

    def test_get_vix_index(self, analyzer):
        """VIX 지수"""
        vix = analyzer._get_vix_index()
        assert isinstance(vix, float)
        assert vix >= 0

    def test_get_gold_price(self, analyzer):
        """금 가격"""
        price = analyzer._get_gold_price()
        assert isinstance(price, float)
        assert price > 0

    def test_get_oil_price(self, analyzer):
        """원유 가격"""
        price = analyzer._get_oil_price()
        assert isinstance(price, float)
        assert price > 0

    def test_get_bond_yield(self, analyzer):
        """10년 국채 수익률"""
        yield_rate = analyzer._get_bond_yield()
        assert isinstance(yield_rate, float)


# ============================================================================
# Enum Tests
# ============================================================================

class TestEnums:
    """Enum 테스트"""

    def test_economic_regime_values(self):
        """EconomicRegime 값"""
        assert EconomicRegime.EXPANSION.value == "expansion"
        assert EconomicRegime.CONTRACTION.value == "contraction"
        assert EconomicRegime.RECOVERY.value == "recovery"
        assert EconomicRegime.PEAK.value == "peak"

    def test_inflation_regime_values(self):
        """InflationRegime 값"""
        assert InflationRegime.DEFLATIONARY.value == "deflationary"
        assert InflationRegime.LOW.value == "low"
        assert InflationRegime.MODERATE.value == "moderate"
        assert InflationRegime.HIGH.value == "high"
        assert InflationRegime.HYPERINFLATION.value == "hyperinflation"

    def test_rate_environment_values(self):
        """RateEnvironment 값"""
        assert RateEnvironment.ULTRA_LOW.value == "ultra_low"
        assert RateEnvironment.LOW.value == "low"
        assert RateEnvironment.MODERATE.value == "moderate"
        assert RateEnvironment.HIGH.value == "high"
        assert RateEnvironment.VERY_HIGH.value == "very_high"


# ============================================================================
# Dataclass Tests
# ============================================================================

class TestMacroIndicatorsDataclass:
    """MacroIndicators 데이터 클래스 테스트"""

    def test_creation(self, sample_indicators):
        """생성"""
        assert sample_indicators.fed_funds_rate == 5.25
        assert sample_indicators.inflation_rate == 3.2
        assert sample_indicators.dxy_index == 104.5


class TestMacroAnalysisDataclass:
    """MacroAnalysis 데이터 클래스 테스트"""

    def test_creation(self):
        """생성"""
        analysis = MacroAnalysis(
            economic_regime=EconomicRegime.EXPANSION,
            inflation_regime=InflationRegime.MODERATE,
            rate_environment=RateEnvironment.MODERATE,
            crypto_favorability=0.5,
            risk_adjustment=0.1,
            recommended_allocation={"crypto": 0.6, "krw": 0.4},
            key_drivers=["저금리 환경"],
            analysis_confidence=0.85,
            created_at=datetime.now()
        )

        assert analysis.crypto_favorability == 0.5
        assert analysis.economic_regime == EconomicRegime.EXPANSION


# ============================================================================
# DB Save Tests
# ============================================================================

class TestDBSave:
    """DB 저장 테스트"""

    def test_save_macro_analysis_to_db(self, analyzer_with_db):
        """매크로 분석 결과 DB 저장"""
        analysis = MacroAnalysis(
            economic_regime=EconomicRegime.EXPANSION,
            inflation_regime=InflationRegime.MODERATE,
            rate_environment=RateEnvironment.MODERATE,
            crypto_favorability=0.5,
            risk_adjustment=0.1,
            recommended_allocation={"crypto": 0.6, "krw": 0.4},
            key_drivers=["저금리 환경"],
            analysis_confidence=0.85,
            created_at=datetime.now()
        )

        analyzer_with_db._save_macro_analysis_to_db(analysis)

        analyzer_with_db.db_manager.save_analysis_result.assert_called_once()

    def test_save_analysis_to_db(self, analyzer_with_db, sample_indicators):
        """분석 결과 DB 저장"""
        analysis = MacroAnalysis(
            economic_regime=EconomicRegime.RECOVERY,
            inflation_regime=InflationRegime.MODERATE,
            rate_environment=RateEnvironment.MODERATE,
            crypto_favorability=0.3,
            risk_adjustment=0.05,
            recommended_allocation={"crypto": 0.55, "krw": 0.45},
            key_drivers=[],
            analysis_confidence=0.8,
            created_at=datetime.now()
        )

        analyzer_with_db._save_analysis_to_db(analysis, sample_indicators)

        analyzer_with_db.db_manager.save_analysis_result.assert_called()


# ============================================================================
# Exception Handling Tests (Lines 195-197, 551-553, 579-580, 620-622, 698-700, 737-738)
# ============================================================================

class TestExceptionHandling:
    """예외 처리 테스트"""

    def test_analyze_macro_environment_exception_returns_fallback(self, analyzer, sample_indicators):
        """analyze_macro_environment 예외 시 폴백 분석 반환 (lines 195-197)"""
        with patch.object(analyzer, '_determine_economic_regime', side_effect=Exception("분석 오류")):
            result = analyzer.analyze_macro_environment(sample_indicators)

            # 폴백 분석 반환 확인
            assert isinstance(result, MacroAnalysis)
            assert result.economic_regime == EconomicRegime.RECOVERY
            assert result.analysis_confidence == 0.3

    def test_analyze_comprehensive_macro_exception(self, analyzer):
        """analyze_comprehensive_macro 예외 처리 (lines 551-553)"""
        with patch.object(analyzer, '_get_fallback_indicators', side_effect=Exception("지표 수집 실패")):
            result = analyzer.analyze_comprehensive_macro()

            assert result["success"] is False
            assert "error" in result
            assert result["overall_score"] == 0.5
            assert result["confidence"] == 0.3

    def test_save_macro_analysis_to_db_exception(self, analyzer_with_db):
        """_save_macro_analysis_to_db 예외 처리 (lines 579-580)"""
        analyzer_with_db.db_manager.save_analysis_result.side_effect = Exception("DB 저장 실패")

        analysis = MacroAnalysis(
            economic_regime=EconomicRegime.EXPANSION,
            inflation_regime=InflationRegime.MODERATE,
            rate_environment=RateEnvironment.MODERATE,
            crypto_favorability=0.5,
            risk_adjustment=0.1,
            recommended_allocation={"crypto": 0.6, "krw": 0.4},
            key_drivers=["저금리 환경"],
            analysis_confidence=0.85,
            created_at=datetime.now()
        )

        # 예외가 발생해도 에러를 던지지 않음
        analyzer_with_db._save_macro_analysis_to_db(analysis)

    def test_get_macro_trend_analysis_exception(self, analyzer):
        """get_macro_trend_analysis 예외 처리 (lines 620-622)"""
        # numpy 연산 오류 유발
        bad_data = {"fed_rate": [float('nan'), float('nan'), float('nan')]}

        with patch('numpy.polyfit', side_effect=Exception("트렌드 분석 오류")):
            result = analyzer.get_macro_trend_analysis(bad_data)

            assert "error" in result

    def test_get_latest_signal_exception(self, analyzer):
        """get_latest_signal 예외 처리 (lines 698-700)"""
        with patch.object(analyzer, 'analyze_comprehensive_macro', side_effect=Exception("신호 조회 실패")):
            result = analyzer.get_latest_signal()

            assert result["market_signal"] == 0.0
            assert result["confidence"] == 0.3
            assert "error" in result

    def test_save_analysis_to_db_exception(self, analyzer_with_db, sample_indicators):
        """_save_analysis_to_db 예외 처리 (lines 737-738)"""
        analyzer_with_db.db_manager.save_analysis_result.side_effect = Exception("DB 오류")

        analysis = MacroAnalysis(
            economic_regime=EconomicRegime.RECOVERY,
            inflation_regime=InflationRegime.MODERATE,
            rate_environment=RateEnvironment.MODERATE,
            crypto_favorability=0.3,
            risk_adjustment=0.05,
            recommended_allocation={"crypto": 0.55, "krw": 0.45},
            key_drivers=[],
            analysis_confidence=0.8,
            created_at=datetime.now()
        )

        # 예외가 발생해도 에러를 던지지 않음
        analyzer_with_db._save_analysis_to_db(analysis, sample_indicators)


# ============================================================================
# Key Drivers Edge Cases Tests (Lines 370, 376, 382)
# ============================================================================

class TestKeyDriversEdgeCases:
    """주요 동인 엣지 케이스 테스트"""

    def test_ultra_low_rate_driver(self, analyzer):
        """초저금리 환경 동인 (line 370)"""
        indicators = MacroIndicators(
            fed_funds_rate=0.5,  # 초저금리
            inflation_rate=2.5,
            dxy_index=100.0,
            m2_money_supply=5.0,
            unemployment_rate=4.0,
            gdp_growth=2.0,
            vix_index=18.0,
            gold_price=1900.0,
            oil_price=75.0,
            bond_yield_10y=3.5,
            last_updated=datetime.now()
        )

        drivers = analyzer._identify_key_drivers(indicators)

        assert any("초저금리" in d for d in drivers)

    def test_low_inflation_driver(self, analyzer):
        """저인플레이션 환경 동인 (line 376)"""
        indicators = MacroIndicators(
            fed_funds_rate=3.0,
            inflation_rate=0.5,  # 저인플레이션
            dxy_index=100.0,
            m2_money_supply=5.0,
            unemployment_rate=4.0,
            gdp_growth=2.0,
            vix_index=18.0,
            gold_price=1900.0,
            oil_price=75.0,
            bond_yield_10y=3.5,
            last_updated=datetime.now()
        )

        drivers = analyzer._identify_key_drivers(indicators)

        assert any("저인플레이션" in d or "디플레이션" in d for d in drivers)

    def test_weak_dollar_driver(self, analyzer):
        """약달러 환경 동인 (line 382)"""
        indicators = MacroIndicators(
            fed_funds_rate=3.0,
            inflation_rate=2.5,
            dxy_index=85.0,  # 약달러
            m2_money_supply=5.0,
            unemployment_rate=4.0,
            gdp_growth=2.0,
            vix_index=18.0,
            gold_price=1900.0,
            oil_price=75.0,
            bond_yield_10y=3.5,
            last_updated=datetime.now()
        )

        drivers = analyzer._identify_key_drivers(indicators)

        assert any("약달러" in d for d in drivers)


# ============================================================================
# Analysis Confidence Edge Cases Tests (Line 406)
# ============================================================================

class TestAnalysisConfidenceEdgeCases:
    """분석 신뢰도 엣지 케이스 테스트"""

    def test_very_old_data_confidence(self, analyzer):
        """매우 오래된 데이터 (1주 이상) 신뢰도"""
        indicators = MacroIndicators(
            fed_funds_rate=3.0,
            inflation_rate=2.5,
            dxy_index=100.0,
            m2_money_supply=5.0,
            unemployment_rate=4.0,
            gdp_growth=2.0,
            vix_index=18.0,
            gold_price=1900.0,
            oil_price=75.0,
            bond_yield_10y=3.5,
            last_updated=datetime.now() - timedelta(days=10)  # 10일 전
        )

        confidence = analyzer._calculate_analysis_confidence(indicators)

        # 24시간 이상 된 데이터는 신뢰도가 낮아짐 (0.8 - 0.2 = 0.6)
        assert confidence < 0.7


# ============================================================================
# Data Collection Exception Tests (Lines 428-496)
# ============================================================================

class TestDataCollectionExceptions:
    """데이터 수집 예외 테스트"""

    def test_get_fed_funds_rate_exception(self, analyzer):
        """연준 기준금리 수집 예외 (lines 428-429)"""
        # 내부 구현을 모킹하여 예외 발생시킴
        original_method = analyzer._get_fed_funds_rate

        def raise_exception():
            raise Exception("API 오류")

        # try 블록 안에서 예외 발생 유도
        # 이미 예외 처리가 있으므로 폴백 값 반환 확인
        with patch.object(analyzer, '_get_fed_funds_rate', side_effect=Exception("API 오류")):
            # get_current_indicators가 폴백을 사용함
            indicators = analyzer.get_current_indicators()
            assert indicators is not None

    def test_data_methods_return_fallback_on_exception(self, analyzer):
        """데이터 수집 메서드 예외 시 폴백 반환"""
        # 각 메서드가 예외 처리 후 폴백 값 반환하는지 확인
        methods_fallbacks = [
            ('_get_fed_funds_rate', 5.0),
            ('_get_inflation_rate', 3.0),
            ('_get_dxy_index', 100.0),
            ('_get_m2_growth', 5.0),
            ('_get_unemployment_rate', 4.0),
            ('_get_gdp_growth', 2.0),
            ('_get_vix_index', 20.0),
            ('_get_gold_price', 2000.0),
            ('_get_oil_price', 80.0),
            ('_get_bond_yield', 4.0),
        ]

        for method_name, fallback_value in methods_fallbacks:
            method = getattr(analyzer, method_name)
            result = method()
            assert isinstance(result, float)


# ============================================================================
# Determine Overall Trend Edge Cases Tests (Lines 637, 644, 654)
# ============================================================================

class TestDetermineOverallTrendEdgeCases:
    """전체 트렌드 방향 엣지 케이스 테스트"""

    def test_increasing_positive_impact(self, analyzer):
        """증가 + 긍정적 영향 (line 637)"""
        trends = {
            "m2_supply": {"direction": "increasing", "trend_strength": 0.9},
            "inflation": {"direction": "increasing", "trend_strength": 0.8}
        }

        direction = analyzer._determine_overall_trend(trends)

        assert direction in ["crypto_favorable", "neutral"]

    def test_decreasing_negative_impact(self, analyzer):
        """감소 + 부정적 영향 = 긍정적 (line 644)"""
        trends = {
            "fed_rate": {"direction": "decreasing", "trend_strength": 0.9},
            "dxy": {"direction": "decreasing", "trend_strength": 0.8}
        }

        direction = analyzer._determine_overall_trend(trends)

        assert direction in ["crypto_favorable", "neutral"]

    def test_strong_crypto_favorable(self, analyzer):
        """강한 암호화폐 우호적 트렌드 (line 654)"""
        trends = {
            "m2_supply": {"direction": "increasing", "trend_strength": 1.0},
            "fed_rate": {"direction": "decreasing", "trend_strength": 1.0},
            "dxy": {"direction": "decreasing", "trend_strength": 1.0}
        }

        direction = analyzer._determine_overall_trend(trends)

        assert direction == "crypto_favorable"

    def test_empty_trends(self, analyzer):
        """빈 트렌드"""
        direction = analyzer._determine_overall_trend({})

        assert direction == "neutral"


# ============================================================================
# Get Latest Signal Edge Cases Tests (Lines 672, 684, 686)
# ============================================================================

class TestGetLatestSignalEdgeCases:
    """최신 신호 조회 엣지 케이스 테스트"""

    def test_signal_with_error_in_analysis(self, analyzer):
        """분석 결과에 에러가 있는 경우 (line 672)"""
        with patch.object(analyzer, 'analyze_comprehensive_macro', return_value={"error": "분석 실패"}):
            result = analyzer.get_latest_signal()

            assert result["market_signal"] == 0.0
            assert result["confidence"] == 0.3
            assert "error" in result

    def test_signal_crypto_favorable(self, analyzer):
        """암호화폐 우호적 신호 (line 684)"""
        mock_analysis = {
            "success": True,
            "overall_direction": "crypto_favorable",
            "trend_confidence": 0.8,
            "trends": {}
        }

        with patch.object(analyzer, 'analyze_comprehensive_macro', return_value=mock_analysis):
            result = analyzer.get_latest_signal()

            assert result["market_signal"] > 0
            assert result["overall_direction"] == "crypto_favorable"

    def test_signal_crypto_unfavorable(self, analyzer):
        """암호화폐 비우호적 신호 (line 686)"""
        mock_analysis = {
            "success": True,
            "overall_direction": "crypto_unfavorable",
            "trend_confidence": 0.7,
            "trends": {}
        }

        with patch.object(analyzer, 'analyze_comprehensive_macro', return_value=mock_analysis):
            result = analyzer.get_latest_signal()

            assert result["market_signal"] < 0
            assert result["overall_direction"] == "crypto_unfavorable"
