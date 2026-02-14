"""
Market Season Filter 테스트 모듈

BTC 200주 이동평균선 기반 시장 계절 판단 테스트
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.core.market_season_filter import (
    MarketSeasonFilter,
    MarketSeason,
    DEFAULT_BUFFER_BAND
)


class TestMarketSeason:
    """MarketSeason Enum 테스트"""

    def test_season_values(self):
        """시장 계절 값 확인"""
        assert MarketSeason.RISK_ON.value == "risk_on"
        assert MarketSeason.RISK_OFF.value == "risk_off"
        assert MarketSeason.NEUTRAL.value == "neutral"

    def test_season_count(self):
        """시장 계절 개수 확인"""
        assert len(MarketSeason) == 3


class TestMarketSeasonFilter:
    """MarketSeasonFilter 클래스 테스트"""

    @pytest.fixture
    def filter(self):
        """MarketSeasonFilter 인스턴스"""
        return MarketSeasonFilter(buffer_band=0.05)

    @pytest.fixture
    def price_data_uptrend(self):
        """상승 추세 가격 데이터"""
        dates = pd.date_range(end=datetime.now(), periods=250, freq='D')
        base_price = 50000000
        prices = [base_price * (1 + 0.001 * i) for i in range(250)]
        return pd.DataFrame({
            'Close': prices
        }, index=dates)

    @pytest.fixture
    def price_data_downtrend(self):
        """하락 추세 가격 데이터"""
        dates = pd.date_range(end=datetime.now(), periods=250, freq='D')
        base_price = 70000000
        prices = [base_price * (1 - 0.001 * i) for i in range(250)]
        return pd.DataFrame({
            'Close': prices
        }, index=dates)

    def test_init(self, filter):
        """초기화 테스트"""
        assert filter.buffer_band == 0.05
        assert filter.risk_on_threshold == 1.05
        assert filter.risk_off_threshold == 0.95

    def test_init_custom_buffer(self):
        """커스텀 버퍼 밴드 초기화"""
        custom_filter = MarketSeasonFilter(buffer_band=0.10)
        assert custom_filter.risk_on_threshold == 1.10
        assert custom_filter.risk_off_threshold == 0.90

    def test_calculate_200week_ma_empty_data(self, filter):
        """빈 데이터로 200주 이동평균 계산"""
        empty_df = pd.DataFrame()
        ma = filter.calculate_200week_ma(empty_df)

        # 빈 데이터에서는 기본값 반환
        assert ma == 50000000.0

    def test_calculate_200week_ma_no_close_column(self, filter):
        """Close 컬럼 없는 데이터"""
        df = pd.DataFrame({'Open': [100, 200, 300]})
        ma = filter.calculate_200week_ma(df)

        assert ma == 50000000.0

    def test_calculate_200week_ma_insufficient_data(self, filter):
        """데이터 부족 시 평균 반환"""
        dates = pd.date_range(end=datetime.now(), periods=100, freq='D')
        df = pd.DataFrame({
            'Close': [50000000] * 100
        }, index=dates)

        ma = filter.calculate_200week_ma(df)

        # 데이터가 부족하면 단순 평균 반환
        assert ma == 50000000.0

    def test_calculate_200week_ma_with_sufficient_data(self, filter, price_data_uptrend):
        """충분한 데이터로 200주 이동평균 계산"""
        ma = filter.calculate_200week_ma(price_data_uptrend)

        # 유효한 숫자여야 함
        assert isinstance(ma, (int, float))
        assert ma > 0
        assert not pd.isna(ma)

    def test_determine_market_season_risk_on(self, filter):
        """강세장 판단 테스트"""
        current_price = 60000000  # 200주 MA의 110%
        ma_200w = 54545454  # price / 1.10

        season, info = filter.determine_market_season(current_price, ma_200w)

        assert season == MarketSeason.RISK_ON
        assert info['price_ratio'] >= filter.risk_on_threshold

    def test_determine_market_season_risk_off(self, filter):
        """약세장 판단 테스트"""
        current_price = 45000000
        ma_200w = 50000000  # price / 0.90

        season, info = filter.determine_market_season(current_price, ma_200w)

        assert season == MarketSeason.RISK_OFF
        assert info['price_ratio'] <= filter.risk_off_threshold

    def test_determine_market_season_neutral(self, filter):
        """횡보장 판단 테스트"""
        current_price = 50000000
        ma_200w = 50000000  # 정확히 1.0

        season, info = filter.determine_market_season(current_price, ma_200w)

        assert season == MarketSeason.NEUTRAL
        assert 0.95 < info['price_ratio'] < 1.05

    def test_determine_market_season_with_previous(self, filter):
        """이전 계절 유지 테스트"""
        current_price = 51000000  # 1.02 비율 (밴드 내)
        ma_200w = 50000000
        previous_season = MarketSeason.RISK_ON

        season, info = filter.determine_market_season(
            current_price, ma_200w, previous_season
        )

        # 밴드 내에서는 이전 상태 유지
        assert season == MarketSeason.RISK_ON

    def test_determine_market_season_invalid_data(self, filter):
        """잘못된 데이터 처리"""
        season, info = filter.determine_market_season(None, 0)

        assert season == MarketSeason.NEUTRAL
        assert 'error' in info

    def test_determine_market_season_nan(self, filter):
        """NaN 데이터 처리"""
        season, info = filter.determine_market_season(float('nan'), 50000000)

        assert season == MarketSeason.NEUTRAL
        assert 'error' in info

    def test_get_allocation_weights_risk_on(self, filter):
        """RISK_ON 배분 비중"""
        weights = filter.get_allocation_weights(MarketSeason.RISK_ON)

        assert weights['crypto'] == 0.70
        assert weights['krw'] == 0.30

    def test_get_allocation_weights_risk_off(self, filter):
        """RISK_OFF 배분 비중"""
        weights = filter.get_allocation_weights(MarketSeason.RISK_OFF)

        assert weights['crypto'] == 0.30
        assert weights['krw'] == 0.70

    def test_get_allocation_weights_neutral(self, filter):
        """NEUTRAL 배분 비중"""
        weights = filter.get_allocation_weights(MarketSeason.NEUTRAL)

        assert weights['crypto'] == 0.50
        assert weights['krw'] == 0.50

    def test_analyze_weekly(self, filter, price_data_uptrend):
        """주간 분석 테스트"""
        result = filter.analyze_weekly(price_data_uptrend)

        assert result['success'] is True
        assert 'market_season' in result
        assert 'allocation_weights' in result
        assert 'analysis_info' in result

    def test_analyze_weekly_error(self, filter):
        """주간 분석 에러 처리"""
        empty_df = pd.DataFrame()
        result = filter.analyze_weekly(empty_df)

        # 에러 발생해도 결과 반환
        assert 'success' in result


class TestMarketSeasonFilterAdvanced:
    """MarketSeasonFilter 고급 테스트"""

    @pytest.fixture
    def filter_with_db(self):
        """DB Manager가 있는 필터"""
        mock_db = Mock()
        mock_db.get_all_latest_analysis_results.return_value = {
            'multi_timeframe': {
                'confidence_score': 0.8,
                'result_data': {'overall_confidence': 0.75}
            },
            'macro_economic': {
                'confidence_score': 0.7,
                'result_data': {
                    'indicators': {'VIX': {'value': 18}, 'DXY': {'value': 98}},
                    'crypto_favorability': 0.6
                }
            }
        }
        mock_db.mark_analysis_as_used.return_value = None

        return MarketSeasonFilter(buffer_band=0.05, db_manager=mock_db)

    def test_integrate_advanced_analysis_no_db(self):
        """DB 없이 고급 분석 통합"""
        filter = MarketSeasonFilter()
        result = filter._integrate_advanced_analysis()

        assert result is None

    def test_integrate_advanced_analysis_with_db(self, filter_with_db):
        """DB로 고급 분석 통합"""
        result = filter_with_db._integrate_advanced_analysis()

        assert result is not None
        assert 'multi_timeframe' in result
        assert 'macro_economic' in result

    def test_adjust_allocation_with_analysis(self, filter_with_db):
        """분석 반영 배분 조정"""
        base_allocation = {'crypto': 0.5, 'krw': 0.5}
        advanced_analysis = {
            'multi_timeframe': {
                'confidence_score': 0.8,
                'result_data': {'overall_confidence': 0.8}
            }
        }

        adjusted = filter_with_db._adjust_allocation_with_analysis(
            base_allocation, advanced_analysis
        )

        # 강세 신호로 암호화폐 비중 증가
        assert adjusted['crypto'] >= base_allocation['crypto']
        assert adjusted['crypto'] + adjusted['krw'] == 1.0

    def test_calculate_adjustment_by_analysis_multi_timeframe(self, filter_with_db):
        """멀티 타임프레임 분석 조정값"""
        result_data = {'overall_confidence': 0.8}
        adjustment = filter_with_db._calculate_adjustment_by_analysis(
            'multi_timeframe', result_data, 0.8
        )

        assert adjustment > 0  # 강세 신호

    def test_calculate_adjustment_by_analysis_low_confidence(self, filter_with_db):
        """낮은 신뢰도 분석 조정값"""
        result_data = {'overall_confidence': 0.2}
        adjustment = filter_with_db._calculate_adjustment_by_analysis(
            'multi_timeframe', result_data, 0.2
        )

        assert adjustment < 0  # 약세 신호

    def test_generate_trading_recommendation_hold(self):
        """HOLD 추천 생성"""
        filter = MarketSeasonFilter()
        analysis_result = {
            'market_season': 'neutral',
            'season_changed': False,
            'advanced_analysis': {}
        }

        recommendation = filter.generate_trading_recommendation(analysis_result)

        assert recommendation['action'] == 'HOLD'

    def test_generate_trading_recommendation_rebalance(self):
        """리밸런싱 추천 생성"""
        filter = MarketSeasonFilter()
        # total_signals > 0 조건을 만족하기 위해 advanced_analysis 필요
        analysis_result = {
            'market_season': 'risk_on',
            'season_changed': True,
            'allocation_weights': {'crypto': 0.7, 'krw': 0.3},
            'advanced_analysis': {
                'multi_timeframe': {
                    'confidence_score': 0.8,
                    'result_data': {'overall_confidence': 0.8}
                }
            }
        }

        recommendation = filter.generate_trading_recommendation(analysis_result)

        assert recommendation['action'] == 'REBALANCE'
        assert recommendation['immediate_action'] is True

    def test_generate_trading_recommendation_with_advanced(self):
        """고급 분석 반영 추천"""
        filter = MarketSeasonFilter()
        analysis_result = {
            'market_season': 'neutral',
            'season_changed': False,
            'advanced_analysis': {
                'multi_timeframe': {
                    'confidence_score': 0.85,
                    'result_data': {}
                },
                'macro_economic': {
                    'result_data': {
                        'indicators': {
                            'VIX': {'value': 15},
                            'DXY': {'value': 95}
                        }
                    }
                }
            }
        }

        recommendation = filter.generate_trading_recommendation(analysis_result)

        # 이유가 포함되어야 함
        assert len(recommendation['reasons']) > 0


class TestDefaultBufferBand:
    """기본 버퍼 밴드 테스트"""

    def test_default_buffer_band_value(self):
        """기본 버퍼 밴드 값 확인"""
        assert DEFAULT_BUFFER_BAND == 0.05
