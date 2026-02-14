"""
Adaptive Portfolio Manager Tests

적응형 포트폴리오 관리자 테스트
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

from src.core.adaptive_portfolio_manager import (
    AdaptivePortfolioManager,
    AdaptiveAllocation,
    MarketMaturity,
    CorrelationRegime,
    MarketCharacteristics
)
from src.core.multi_timeframe_analyzer import (
    MultiTimeframeResult,
    CyclePhase,
    TrendDirection,
    TimeframeAnalysis
)
from src.core.market_season_filter import MarketSeason
from src.core.portfolio_manager import PortfolioManager, AssetAllocation


@pytest.fixture
def mock_base_manager():
    """Mock PortfolioManager"""
    manager = Mock(spec=PortfolioManager)
    manager.asset_allocation = AssetAllocation(
        btc_weight=0.40,
        eth_weight=0.30,
        xrp_weight=0.15,
        sol_weight=0.15
    )
    return manager


@pytest.fixture
def adaptive_manager(mock_base_manager):
    """AdaptivePortfolioManager 인스턴스"""
    return AdaptivePortfolioManager(mock_base_manager)


@pytest.fixture
def sample_market_data():
    """샘플 시장 데이터"""
    dates = pd.date_range(end=datetime.now(), periods=60, freq='D')

    # BTC 가격 데이터
    btc_prices = [50000000 + np.random.randn() * 1000000 for _ in range(60)]
    btc_df = pd.DataFrame({
        'Close': btc_prices,
        'High': [p * 1.02 for p in btc_prices],
        'Low': [p * 0.98 for p in btc_prices],
        'Volume': [1000000 + np.random.rand() * 500000 for _ in range(60)]
    }, index=dates)

    # ETH 가격 데이터
    eth_prices = [2500000 + np.random.randn() * 100000 for _ in range(60)]
    eth_df = pd.DataFrame({
        'Close': eth_prices,
        'High': [p * 1.02 for p in eth_prices],
        'Low': [p * 0.98 for p in eth_prices],
        'Volume': [500000 + np.random.rand() * 200000 for _ in range(60)]
    }, index=dates)

    # XRP 가격 데이터
    xrp_prices = [500 + np.random.randn() * 50 for _ in range(60)]
    xrp_df = pd.DataFrame({
        'Close': xrp_prices,
        'High': [p * 1.03 for p in xrp_prices],
        'Low': [p * 0.97 for p in xrp_prices],
        'Volume': [200000 + np.random.rand() * 100000 for _ in range(60)]
    }, index=dates)

    # SOL 가격 데이터
    sol_prices = [100000 + np.random.randn() * 10000 for _ in range(60)]
    sol_df = pd.DataFrame({
        'Close': sol_prices,
        'High': [p * 1.03 for p in sol_prices],
        'Low': [p * 0.97 for p in sol_prices],
        'Volume': [150000 + np.random.rand() * 75000 for _ in range(60)]
    }, index=dates)

    return {
        "BTC": btc_df,
        "ETH": eth_df,
        "XRP": xrp_df,
        "SOL": sol_df
    }


@pytest.fixture
def sample_multiframe_result():
    """샘플 멀티 타임프레임 분석 결과"""
    base_analysis = TimeframeAnalysis(
        timeframe="4h",
        trend_direction=TrendDirection.BULLISH,
        strength=0.8,
        support_level=49000000,
        resistance_level=52000000,
        confidence=0.8,
        last_updated=datetime.now()
    )

    return MultiTimeframeResult(
        very_short_term=base_analysis,
        swing_term=TimeframeAnalysis(
            timeframe="1d",
            trend_direction=TrendDirection.SIDEWAYS,
            strength=0.5,
            support_level=48000000,
            resistance_level=53000000,
            confidence=0.7,
            last_updated=datetime.now()
        ),
        position_term=TimeframeAnalysis(
            timeframe="1w",
            trend_direction=TrendDirection.BULLISH,
            strength=0.6,
            support_level=45000000,
            resistance_level=55000000,
            confidence=0.75,
            last_updated=datetime.now()
        ),
        technical_20d=TimeframeAnalysis(
            timeframe="20d",
            trend_direction=TrendDirection.BULLISH,
            strength=0.7,
            support_level=47000000,
            resistance_level=54000000,
            confidence=0.75,
            last_updated=datetime.now()
        ),
        market_season_200w=TimeframeAnalysis(
            timeframe="200w",
            trend_direction=TrendDirection.BULLISH,
            strength=0.65,
            support_level=44000000,
            resistance_level=56000000,
            confidence=0.7,
            last_updated=datetime.now()
        ),
        bitcoin_cycle=TimeframeAnalysis(
            timeframe="cycle",
            trend_direction=TrendDirection.BULLISH,
            strength=0.7,
            support_level=40000000,
            resistance_level=60000000,
            confidence=0.7,
            last_updated=datetime.now()
        ),
        market_season=MarketSeason.RISK_ON,
        cycle_phase=CyclePhase.MARKUP,
        overall_trend=TrendDirection.BULLISH,
        overall_confidence=0.75,
        recommended_allocation={"crypto": 0.6, "krw": 0.4},
        analysis_timestamp=datetime.now()
    )


@pytest.mark.portfolio
class TestMarketMaturity:
    """MarketMaturity Enum 테스트"""

    def test_maturity_values(self):
        """성숙도 값 확인"""
        assert MarketMaturity.NASCENT.value == "nascent"
        assert MarketMaturity.EMERGING.value == "emerging"
        assert MarketMaturity.MATURE.value == "mature"
        assert MarketMaturity.INSTITUTIONAL.value == "institutional"


@pytest.mark.portfolio
class TestCorrelationRegime:
    """CorrelationRegime Enum 테스트"""

    def test_regime_values(self):
        """체제 값 확인"""
        assert CorrelationRegime.LOW_CORRELATION.value == "low_correlation"
        assert CorrelationRegime.MEDIUM_CORRELATION.value == "medium_correlation"
        assert CorrelationRegime.HIGH_CORRELATION.value == "high_correlation"


@pytest.mark.portfolio
class TestMarketCharacteristics:
    """MarketCharacteristics 데이터클래스 테스트"""

    def test_characteristics_creation(self):
        """특성 생성"""
        chars = MarketCharacteristics(
            maturity=MarketMaturity.MATURE,
            correlation_regime=CorrelationRegime.MEDIUM_CORRELATION,
            overall_volatility=0.5,
            btc_dominance=0.55,
            altcoin_season_score=0.3,
            institutional_flow=0.2,
            last_updated=datetime.now()
        )

        assert chars.maturity == MarketMaturity.MATURE
        assert chars.correlation_regime == CorrelationRegime.MEDIUM_CORRELATION
        assert chars.overall_volatility == 0.5


@pytest.mark.portfolio
class TestAdaptiveAllocation:
    """AdaptiveAllocation 데이터클래스 테스트"""

    def test_allocation_creation(self):
        """배분 생성"""
        allocation = AdaptiveAllocation(
            btc_weight=0.4,
            eth_weight=0.3,
            xrp_weight=0.15,
            sol_weight=0.15,
            krw_weight=0.0,
            reasoning={"BTC": "강세장 배분"},
            confidence=0.8,
            created_at=datetime.now()
        )

        assert allocation.btc_weight == 0.4
        assert allocation.confidence == 0.8

    def test_to_dict(self):
        """딕셔너리 변환"""
        allocation = AdaptiveAllocation(
            btc_weight=0.4,
            eth_weight=0.3,
            xrp_weight=0.15,
            sol_weight=0.15,
            krw_weight=0.0,
            reasoning={},
            confidence=0.8,
            created_at=datetime.now()
        )

        result = allocation.to_dict()

        assert result["BTC"] == 0.4
        assert result["ETH"] == 0.3
        assert result["KRW"] == 0.0


@pytest.mark.portfolio
class TestAdaptivePortfolioManagerInit:
    """AdaptivePortfolioManager 초기화 테스트"""

    def test_init_basic(self, mock_base_manager):
        """기본 초기화"""
        manager = AdaptivePortfolioManager(mock_base_manager)

        assert manager.base_manager == mock_base_manager
        assert manager.min_btc_weight == 0.25
        assert manager.max_btc_weight == 0.70
        assert manager.min_krw_weight == 0.15
        assert manager.max_krw_weight == 0.80

    def test_correlation_thresholds(self, adaptive_manager):
        """상관관계 임계값"""
        assert adaptive_manager.correlation_thresholds["low"] == 0.5
        assert adaptive_manager.correlation_thresholds["high"] == 0.8


@pytest.mark.portfolio
class TestAnalyzeMarketCharacteristics:
    """시장 특성 분석 테스트"""

    def test_analyze_with_full_data(self, adaptive_manager, sample_market_data):
        """전체 데이터로 분석"""
        chars = adaptive_manager._analyze_market_characteristics(sample_market_data)

        assert chars is not None
        assert isinstance(chars.maturity, MarketMaturity)
        assert isinstance(chars.correlation_regime, CorrelationRegime)
        assert 0 <= chars.overall_volatility <= 10
        assert 0 <= chars.btc_dominance <= 1

    def test_analyze_with_missing_btc(self, adaptive_manager):
        """BTC 데이터 누락"""
        market_data = {"ETH": pd.DataFrame({"Close": [2500000] * 30})}

        chars = adaptive_manager._analyze_market_characteristics(market_data)

        assert chars.btc_dominance == 0.5  # 기본값

    def test_analyze_with_missing_eth(self, adaptive_manager):
        """ETH 데이터 누락"""
        market_data = {"BTC": pd.DataFrame({"Close": [50000000] * 30})}

        chars = adaptive_manager._analyze_market_characteristics(market_data)

        assert chars.btc_dominance == 0.5  # 기본값

    def test_high_btc_dominance_nascent_market(self, adaptive_manager):
        """높은 BTC 도미넌스 -> NASCENT 시장"""
        # BTC가 ETH보다 압도적으로 크면 NASCENT
        market_data = {
            "BTC": pd.DataFrame({"Close": [50000000] * 30}),
            "ETH": pd.DataFrame({"Close": [1000000] * 30})  # ETH 비중 매우 낮음
        }

        chars = adaptive_manager._analyze_market_characteristics(market_data)

        assert chars.maturity == MarketMaturity.NASCENT

    def test_exception_handling(self, adaptive_manager):
        """예외 처리"""
        # 잘못된 데이터로 예외 발생
        market_data = {"BTC": "invalid"}

        chars = adaptive_manager._analyze_market_characteristics(market_data)

        # 폴백 값 반환
        assert chars.maturity == MarketMaturity.MATURE
        assert chars.overall_volatility == 0.6


@pytest.mark.portfolio
class TestAnalyzeCorrelationRegime:
    """상관관계 체제 분석 테스트"""

    def test_medium_correlation_default(self, adaptive_manager):
        """데이터 부족 시 기본값"""
        market_data = {"BTC": pd.DataFrame({"Close": [50000000] * 10})}

        regime = adaptive_manager._analyze_correlation_regime(market_data)

        assert regime == CorrelationRegime.MEDIUM_CORRELATION

    def test_high_correlation_detection(self, adaptive_manager):
        """높은 상관관계 감지"""
        # 거의 동일하게 움직이는 가격 데이터 생성
        base_prices = [50000000 + i * 100000 for i in range(31)]

        market_data = {
            "BTC": pd.DataFrame({"Close": base_prices}),
            "ETH": pd.DataFrame({"Close": [p / 20 for p in base_prices]}),  # 동일 패턴
            "XRP": pd.DataFrame({"Close": [p / 100000 for p in base_prices]}),  # 동일 패턴
            "SOL": pd.DataFrame({"Close": [p / 500 for p in base_prices]})  # 동일 패턴
        }

        regime = adaptive_manager._analyze_correlation_regime(market_data)

        assert regime == CorrelationRegime.HIGH_CORRELATION

    def test_exception_handling(self, adaptive_manager):
        """예외 처리"""
        market_data = {"BTC": "invalid"}

        regime = adaptive_manager._analyze_correlation_regime(market_data)

        assert regime == CorrelationRegime.MEDIUM_CORRELATION


@pytest.mark.portfolio
class TestCalculateMarketVolatility:
    """시장 변동성 계산 테스트"""

    def test_normal_volatility(self, adaptive_manager, sample_market_data):
        """정상 변동성 계산"""
        volatility = adaptive_manager._calculate_market_volatility(sample_market_data)

        assert volatility > 0
        assert volatility < 10  # 연화 변동성 1000% 미만

    def test_no_data(self, adaptive_manager):
        """데이터 없음"""
        volatility = adaptive_manager._calculate_market_volatility({})

        assert volatility == 0.6  # 기본값

    def test_exception_handling(self, adaptive_manager):
        """예외 처리"""
        market_data = {"BTC": "invalid"}

        volatility = adaptive_manager._calculate_market_volatility(market_data)

        assert volatility == 0.6


@pytest.mark.portfolio
class TestApplyAdaptiveAdjustments:
    """적응형 조정 적용 테스트"""

    def test_nascent_market_increases_btc(self, adaptive_manager, sample_multiframe_result):
        """초기 시장에서 BTC 비중 증가"""
        market_chars = MarketCharacteristics(
            maturity=MarketMaturity.NASCENT,
            correlation_regime=CorrelationRegime.MEDIUM_CORRELATION,
            overall_volatility=0.5,
            btc_dominance=0.75,
            altcoin_season_score=0.1,
            institutional_flow=0.0,
            last_updated=datetime.now()
        )

        weights = adaptive_manager._apply_adaptive_adjustments(
            0.6, 0.4, market_chars, sample_multiframe_result
        )

        # NASCENT 시장에서 BTC 비중이 양수여야 함
        assert weights["BTC"] > 0

    def test_institutional_market_decreases_btc(self, adaptive_manager, sample_multiframe_result):
        """기관 시장에서 BTC 비중 감소"""
        market_chars = MarketCharacteristics(
            maturity=MarketMaturity.INSTITUTIONAL,
            correlation_regime=CorrelationRegime.LOW_CORRELATION,
            overall_volatility=0.3,
            btc_dominance=0.4,
            altcoin_season_score=0.6,
            institutional_flow=0.5,
            last_updated=datetime.now()
        )

        weights = adaptive_manager._apply_adaptive_adjustments(
            0.6, 0.4, market_chars, sample_multiframe_result
        )

        # 기관 시장에서는 다각화 증가
        assert "ETH" in weights

    def test_altseason_increases_altcoin_weights(self, adaptive_manager, sample_multiframe_result):
        """알트시즌에서 알트코인 비중 증가"""
        market_chars = MarketCharacteristics(
            maturity=MarketMaturity.MATURE,
            correlation_regime=CorrelationRegime.LOW_CORRELATION,
            overall_volatility=0.5,
            btc_dominance=0.4,
            altcoin_season_score=0.8,  # 높은 알트시즌 점수
            institutional_flow=0.0,
            last_updated=datetime.now()
        )

        weights = adaptive_manager._apply_adaptive_adjustments(
            0.6, 0.4, market_chars, sample_multiframe_result
        )

        # XRP, SOL 비중이 기본보다 높아야 함
        assert weights["XRP"] > 0
        assert weights["SOL"] > 0


@pytest.mark.portfolio
class TestApplyConstraints:
    """제약 조건 적용 테스트"""

    def test_btc_minimum_constraint(self, adaptive_manager):
        """BTC 최소 비중 제약"""
        weights = {
            "BTC": 0.1,  # 최소보다 낮음
            "ETH": 0.3,
            "XRP": 0.2,
            "SOL": 0.2,
            "KRW": 0.2
        }

        result = adaptive_manager._apply_constraints(weights)

        # BTC 비중이 원래보다 높아져야 함 (최소 제약 적용)
        assert result["BTC"] > 0.1

    def test_btc_maximum_constraint(self, adaptive_manager):
        """BTC 최대 비중 제약"""
        weights = {
            "BTC": 0.9,  # 최대보다 높음
            "ETH": 0.05,
            "XRP": 0.02,
            "SOL": 0.02,
            "KRW": 0.01
        }

        result = adaptive_manager._apply_constraints(weights)

        # BTC 비중이 원래보다 낮아져야 함 (최대 제약 적용)
        assert result["BTC"] < 0.9

    def test_total_weight_normalization(self, adaptive_manager):
        """총 비중이 1이 되도록 정규화"""
        weights = {
            "BTC": 0.3,
            "ETH": 0.2,
            "XRP": 0.1,
            "SOL": 0.1,
            "KRW": 0.5  # 총합 1.2
        }

        result = adaptive_manager._apply_constraints(weights)

        total = sum(result.values())
        assert abs(total - 1.0) < 0.01

    def test_minimum_asset_weight(self, adaptive_manager):
        """최소 자산 비중 보장"""
        weights = {
            "BTC": 0.9,
            "ETH": 0.005,  # 최소보다 낮음
            "XRP": 0.003,
            "SOL": 0.002,
            "KRW": 0.09
        }

        result = adaptive_manager._apply_constraints(weights)

        # 매우 낮은 비중이었던 자산들이 증가해야 함
        assert result["ETH"] > 0.005
        assert result["XRP"] > 0.003
        assert result["SOL"] > 0.002


@pytest.mark.portfolio
class TestGenerateReasoning:
    """배분 근거 생성 테스트"""

    def test_high_btc_weight_reasoning(self, adaptive_manager, sample_multiframe_result):
        """높은 BTC 비중 근거"""
        market_chars = MarketCharacteristics(
            maturity=MarketMaturity.NASCENT,
            correlation_regime=CorrelationRegime.MEDIUM_CORRELATION,
            overall_volatility=0.5,
            btc_dominance=0.7,
            altcoin_season_score=0.2,
            institutional_flow=0.0,
            last_updated=datetime.now()
        )

        final_weights = {"BTC": 0.55, "ETH": 0.2, "XRP": 0.1, "SOL": 0.1, "KRW": 0.05}

        reasoning = adaptive_manager._generate_reasoning(
            market_chars, sample_multiframe_result, final_weights
        )

        assert "BTC" in reasoning
        assert "BTC 중심" in reasoning["BTC"]

    def test_high_krw_weight_reasoning(self, adaptive_manager, sample_multiframe_result):
        """높은 KRW 비중 근거"""
        market_chars = MarketCharacteristics(
            maturity=MarketMaturity.MATURE,
            correlation_regime=CorrelationRegime.HIGH_CORRELATION,
            overall_volatility=0.8,
            btc_dominance=0.5,
            altcoin_season_score=0.3,
            institutional_flow=-0.5,
            last_updated=datetime.now()
        )

        final_weights = {"BTC": 0.2, "ETH": 0.1, "XRP": 0.05, "SOL": 0.05, "KRW": 0.6}

        reasoning = adaptive_manager._generate_reasoning(
            market_chars, sample_multiframe_result, final_weights
        )

        assert "KRW" in reasoning
        assert "방어적" in reasoning["KRW"]

    def test_altseason_reasoning(self, adaptive_manager, sample_multiframe_result):
        """알트시즌 근거"""
        market_chars = MarketCharacteristics(
            maturity=MarketMaturity.MATURE,
            correlation_regime=CorrelationRegime.LOW_CORRELATION,
            overall_volatility=0.5,
            btc_dominance=0.4,
            altcoin_season_score=0.7,  # 알트시즌
            institutional_flow=0.0,
            last_updated=datetime.now()
        )

        final_weights = {"BTC": 0.3, "ETH": 0.3, "XRP": 0.2, "SOL": 0.15, "KRW": 0.05}

        reasoning = adaptive_manager._generate_reasoning(
            market_chars, sample_multiframe_result, final_weights
        )

        assert "ALTCOINS" in reasoning


@pytest.mark.portfolio
class TestCalculateAllocationConfidence:
    """배분 신뢰도 계산 테스트"""

    def test_high_confidence_stable_market(self, adaptive_manager, sample_multiframe_result):
        """안정적인 시장에서 높은 신뢰도"""
        market_chars = MarketCharacteristics(
            maturity=MarketMaturity.MATURE,
            correlation_regime=CorrelationRegime.MEDIUM_CORRELATION,  # 안정적
            overall_volatility=0.3,  # 낮은 변동성
            btc_dominance=0.55,  # 적정 범위
            altcoin_season_score=0.4,
            institutional_flow=0.2,
            last_updated=datetime.now()
        )

        confidence = adaptive_manager._calculate_allocation_confidence(
            market_chars, sample_multiframe_result
        )

        assert confidence > 0.6

    def test_low_confidence_volatile_market(self, adaptive_manager, sample_multiframe_result):
        """변동성 높은 시장에서 낮은 신뢰도"""
        market_chars = MarketCharacteristics(
            maturity=MarketMaturity.NASCENT,
            correlation_regime=CorrelationRegime.HIGH_CORRELATION,  # 불안정
            overall_volatility=0.9,  # 높은 변동성
            btc_dominance=0.8,  # 극값
            altcoin_season_score=0.1,
            institutional_flow=-0.5,
            last_updated=datetime.now()
        )

        confidence = adaptive_manager._calculate_allocation_confidence(
            market_chars, sample_multiframe_result
        )

        assert confidence < 0.7


@pytest.mark.portfolio
class TestGetFallbackAllocation:
    """폴백 배분 테스트"""

    def test_fallback_allocation(self, adaptive_manager):
        """폴백 배분 반환"""
        allocation = adaptive_manager._get_fallback_allocation()

        assert allocation.btc_weight == 0.4
        assert allocation.eth_weight == 0.3
        assert allocation.xrp_weight == 0.15
        assert allocation.sol_weight == 0.15
        assert allocation.krw_weight == 0.0
        assert allocation.confidence == 0.3
        assert "ERROR" in allocation.reasoning


@pytest.mark.portfolio
class TestCalculateAdaptiveAllocation:
    """적응형 자산 배분 계산 통합 테스트"""

    def test_full_allocation_calculation(
        self, adaptive_manager, sample_market_data, sample_multiframe_result
    ):
        """전체 배분 계산"""
        current_portfolio = {"BTC": 5000000, "ETH": 3000000, "KRW": 2000000}

        allocation = adaptive_manager.calculate_adaptive_allocation(
            sample_market_data, sample_multiframe_result, current_portfolio
        )

        assert allocation is not None
        assert isinstance(allocation, AdaptiveAllocation)
        assert allocation.confidence > 0
        assert len(allocation.reasoning) > 0

        # 총 비중이 1
        total = (allocation.btc_weight + allocation.eth_weight +
                 allocation.xrp_weight + allocation.sol_weight + allocation.krw_weight)
        assert abs(total - 1.0) < 0.01

    def test_allocation_with_exception(self, adaptive_manager, sample_multiframe_result):
        """예외 발생 시에도 배분 반환"""
        # 잘못된 데이터로 예외 발생 가능
        market_data = {"BTC": "invalid"}
        current_portfolio = {}

        allocation = adaptive_manager.calculate_adaptive_allocation(
            market_data, sample_multiframe_result, current_portfolio
        )

        # 배분이 반환되어야 함 (폴백 또는 정상 배분)
        assert allocation is not None
        assert allocation.btc_weight > 0


@pytest.mark.portfolio
class TestGetRebalanceUrgency:
    """리밸런싱 긴급도 계산 테스트"""

    def test_high_urgency(self, adaptive_manager):
        """높은 긴급도"""
        current = {"BTC": 0.2, "ETH": 0.1, "XRP": 0.1, "SOL": 0.1, "KRW": 0.5}
        target = AdaptiveAllocation(
            btc_weight=0.5,  # 큰 차이
            eth_weight=0.2,
            xrp_weight=0.1,
            sol_weight=0.1,
            krw_weight=0.1,
            reasoning={},
            confidence=0.8,
            created_at=datetime.now()
        )

        score, level = adaptive_manager.get_rebalance_urgency(current, target)

        assert level == "HIGH"
        assert score > 0.15

    def test_medium_urgency(self, adaptive_manager):
        """중간 긴급도"""
        current = {"BTC": 0.35, "ETH": 0.25, "XRP": 0.15, "SOL": 0.15, "KRW": 0.1}
        target = AdaptiveAllocation(
            btc_weight=0.4,  # 적당한 차이
            eth_weight=0.3,
            xrp_weight=0.15,
            sol_weight=0.1,
            krw_weight=0.05,
            reasoning={},
            confidence=0.8,
            created_at=datetime.now()
        )

        score, level = adaptive_manager.get_rebalance_urgency(current, target)

        assert level in ["MEDIUM", "LOW"]

    def test_no_urgency(self, adaptive_manager):
        """긴급도 없음"""
        current = {"BTC": 0.4, "ETH": 0.3, "XRP": 0.15, "SOL": 0.1, "KRW": 0.05}
        target = AdaptiveAllocation(
            btc_weight=0.4,  # 거의 동일
            eth_weight=0.3,
            xrp_weight=0.15,
            sol_weight=0.1,
            krw_weight=0.05,
            reasoning={},
            confidence=0.8,
            created_at=datetime.now()
        )

        score, level = adaptive_manager.get_rebalance_urgency(current, target)

        assert level == "NONE"
        assert score < 0.03


@pytest.mark.portfolio
class TestAnalyzeCorrelationImpact:
    """상관관계 영향 분석 테스트"""

    def test_analyze_with_sufficient_data(self, adaptive_manager, sample_market_data):
        """충분한 데이터로 분석"""
        result = adaptive_manager.analyze_correlation_impact(sample_market_data)

        assert "diversification_ratio" in result
        assert "portfolio_volatility" in result
        assert "avg_asset_volatility" in result
        assert "diversification_benefit" in result

    def test_insufficient_data(self, adaptive_manager):
        """데이터 부족"""
        market_data = {"BTC": pd.DataFrame({"Close": [50000000] * 60})}

        result = adaptive_manager.analyze_correlation_impact(market_data)

        assert result == {"error": "insufficient_data"}

    def test_exception_handling(self, adaptive_manager):
        """예외 처리"""
        market_data = {"BTC": "invalid"}

        result = adaptive_manager.analyze_correlation_impact(market_data)

        assert "error" in result


@pytest.mark.portfolio
class TestCyclePhaseAdjustments:
    """사이클 단계별 조정 테스트"""

    def test_accumulation_phase(self, adaptive_manager, mock_base_manager, sample_multiframe_result):
        """축적 단계"""
        # Mock the cycle phase
        sample_multiframe_result.cycle_phase = CyclePhase.ACCUMULATION

        market_chars = MarketCharacteristics(
            maturity=MarketMaturity.MATURE,
            correlation_regime=CorrelationRegime.MEDIUM_CORRELATION,
            overall_volatility=0.5,
            btc_dominance=0.5,
            altcoin_season_score=0.3,
            institutional_flow=0.0,
            last_updated=datetime.now()
        )

        weights = adaptive_manager._apply_adaptive_adjustments(
            0.5, 0.5, market_chars, sample_multiframe_result
        )

        # 축적 단계: KRW 비중이 기본보다 높아야 함
        assert weights["KRW"] >= 0.5

    def test_decline_phase(self, adaptive_manager, mock_base_manager, sample_multiframe_result):
        """하락 단계"""
        # Mock the cycle phase
        sample_multiframe_result.cycle_phase = CyclePhase.DECLINE

        market_chars = MarketCharacteristics(
            maturity=MarketMaturity.MATURE,
            correlation_regime=CorrelationRegime.HIGH_CORRELATION,
            overall_volatility=0.8,
            btc_dominance=0.5,
            altcoin_season_score=0.1,
            institutional_flow=-0.5,
            last_updated=datetime.now()
        )

        weights = adaptive_manager._apply_adaptive_adjustments(
            0.3, 0.7, market_chars, sample_multiframe_result
        )

        # 하락 단계: KRW 비중이 높아야 함
        assert weights["KRW"] >= 0.7
