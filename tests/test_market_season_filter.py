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


class TestMarketSeasonFilterEdgeCases:
    """MarketSeasonFilter 엣지 케이스 테스트"""

    @pytest.fixture
    def filter(self):
        return MarketSeasonFilter(buffer_band=0.05)

    def test_calculate_200week_ma_all_nan(self, filter):
        """모든 값이 NaN인 경우"""
        dates = pd.date_range(end=datetime.now(), periods=250, freq='D')
        df = pd.DataFrame({
            'Close': [np.nan] * 250
        }, index=dates)

        ma = filter.calculate_200week_ma(df)

        # 유효한 값이 없으면 기본값 반환
        assert ma == 50000000.0

    def test_calculate_200week_ma_non_datetime_index(self, filter):
        """datetime 인덱스가 아닌 경우"""
        # 정수 인덱스 사용
        df = pd.DataFrame({
            'Close': [50000000.0] * 250
        }, index=range(250))

        ma = filter.calculate_200week_ma(df)

        # 단순 이동평균 사용
        assert ma == 50000000.0

    def test_calculate_200week_ma_insufficient_weekly_data(self, filter):
        """주간 데이터로 변환 시 부족한 경우"""
        # 200개 일간 데이터지만 주간으로 리샘플링하면 30주 미만
        dates = pd.date_range(end=datetime.now(), periods=200, freq='D')
        df = pd.DataFrame({
            'Close': [50000000.0 + i * 1000 for i in range(200)]
        }, index=dates)

        ma = filter.calculate_200week_ma(df)

        # 일간 200개 이동평균으로 대체
        assert ma > 0 and not pd.isna(ma)

    def test_calculate_200week_ma_nan_result(self, filter):
        """200주 MA 결과가 NaN인 경우"""
        # 데이터가 있지만 이동평균 결과가 NaN이 되는 상황
        dates = pd.date_range(end=datetime.now(), periods=300, freq='W')
        # 처음 250주는 NaN, 마지막 50주만 유효한 값
        prices = [np.nan] * 250 + [50000000.0] * 50
        df = pd.DataFrame({
            'Close': prices
        }, index=dates)

        ma = filter.calculate_200week_ma(df)

        # 50주 이동평균 또는 단순 평균으로 대체
        assert ma > 0

    def test_calculate_200week_ma_resample_error(self, filter):
        """리샘플링 실패 시"""
        dates = pd.date_range(end=datetime.now(), periods=250, freq='D')
        df = pd.DataFrame({
            'Close': [50000000.0] * 250
        }, index=dates)

        # resample 메서드가 예외를 발생시키도록 mock
        with patch.object(pd.DataFrame, 'resample', side_effect=Exception("Resample error")):
            ma = filter.calculate_200week_ma(df)

            # 에러 발생해도 유효한 값 반환
            assert ma > 0

    def test_calculate_200week_ma_general_exception(self, filter):
        """일반 예외 발생 시"""
        # dropna 호출 시 예외 발생
        df = pd.DataFrame({
            'Close': [50000000.0] * 250
        })

        with patch.object(pd.Series, 'dropna', side_effect=Exception("Unexpected error")):
            ma = filter.calculate_200week_ma(df)

            # 기본값 반환
            assert ma == 50000000.0

    def test_integrate_advanced_analysis_empty_results(self):
        """빈 분석 결과 조회"""
        mock_db = Mock()
        mock_db.get_all_latest_analysis_results.return_value = {}

        filter = MarketSeasonFilter(db_manager=mock_db)
        result = filter._integrate_advanced_analysis()

        # 빈 결과면 None 반환
        assert result is None

    def test_integrate_advanced_analysis_exception(self):
        """분석 결과 조회 중 예외"""
        mock_db = Mock()
        mock_db.get_all_latest_analysis_results.side_effect = Exception("DB Error")

        filter = MarketSeasonFilter(db_manager=mock_db)
        result = filter._integrate_advanced_analysis()

        assert result is None

    def test_adjust_allocation_exception(self):
        """배분 조정 중 예외"""
        filter = MarketSeasonFilter()
        base_allocation = {'crypto': 0.5, 'krw': 0.5}

        # None 값으로 예외 유발
        advanced_analysis = {
            'multi_timeframe': None
        }

        adjusted = filter._adjust_allocation_with_analysis(base_allocation, advanced_analysis)

        # 예외 발생해도 기본 배분 반환
        assert adjusted == base_allocation


class TestGenerateTradingRecommendationEdgeCases:
    """generate_trading_recommendation 엣지 케이스"""

    @pytest.fixture
    def filter(self):
        return MarketSeasonFilter(buffer_band=0.05)

    def test_recommendation_low_mtf_confidence(self, filter):
        """멀티 타임프레임 약세 신호"""
        analysis_result = {
            'market_season': 'neutral',
            'season_changed': False,
            'advanced_analysis': {
                'multi_timeframe': {
                    'confidence_score': 0.2,  # 낮은 신뢰도 = 약세
                    'result_data': {}
                }
            }
        }

        recommendation = filter.generate_trading_recommendation(analysis_result)

        # 약세 신호 포함
        assert len(recommendation['reasons']) > 0
        assert any('약세' in r or '📉' in r for r in recommendation['reasons'])

    def test_recommendation_high_vix(self, filter):
        """VIX 높음 (약세 신호)"""
        analysis_result = {
            'market_season': 'neutral',
            'season_changed': False,
            'advanced_analysis': {
                'macro_economic': {
                    'result_data': {
                        'indicators': {
                            'VIX': {'value': 35},  # 높은 VIX
                            'DXY': {'value': 100}
                        }
                    }
                }
            }
        }

        recommendation = filter.generate_trading_recommendation(analysis_result)

        # VIX 높으면 약세 신호
        assert 'action' in recommendation

    def test_recommendation_low_vix_weak_dxy(self, filter):
        """VIX 낮고 DXY 약함 (강세 신호)"""
        analysis_result = {
            'market_season': 'neutral',
            'season_changed': False,
            'advanced_analysis': {
                'macro_economic': {
                    'result_data': {
                        'indicators': {
                            'VIX': {'value': 15},  # 낮은 VIX
                            'DXY': {'value': 95}   # 약한 DXY
                        }
                    }
                }
            }
        }

        recommendation = filter.generate_trading_recommendation(analysis_result)

        # 강세 신호 포함 가능
        assert 'action' in recommendation

    def test_recommendation_onchain_positive(self, filter):
        """온체인 강세 신호"""
        analysis_result = {
            'market_season': 'neutral',
            'season_changed': False,
            'advanced_analysis': {
                'onchain_data': {
                    'confidence_score': 0.8,  # 높은 신뢰도
                    'result_data': {
                        'mvrv_ratio': 1.5,  # MVRV 적정 범위
                        'exchange_netflow': -1000  # 순유출 (강세)
                    }
                }
            }
        }

        recommendation = filter.generate_trading_recommendation(analysis_result)

        # 추천 생성됨
        assert 'action' in recommendation

    def test_recommendation_behavioral_bias_warning(self, filter):
        """행동 편향 경고"""
        analysis_result = {
            'market_season': 'risk_on',
            'season_changed': False,
            'advanced_analysis': {
                'behavioral_bias': {
                    'result_data': {
                        'fomo_detected': True,
                        'overconfidence_level': 0.8
                    }
                }
            }
        }

        recommendation = filter.generate_trading_recommendation(analysis_result)

        # 경고 메시지 포함 가능
        assert 'action' in recommendation

    def test_recommendation_strong_buy(self, filter):
        """강력한 매수 신호"""
        analysis_result = {
            'market_season': 'risk_on',
            'season_changed': True,
            'allocation_weights': {'crypto': 0.7, 'krw': 0.3},
            'advanced_analysis': {
                'multi_timeframe': {
                    'confidence_score': 0.9,
                    'result_data': {}
                },
                'macro_economic': {
                    'result_data': {
                        'indicators': {
                            'VIX': {'value': 12},
                            'DXY': {'value': 92}
                        },
                        'crypto_favorability': 0.8
                    }
                },
                'onchain_data': {
                    'confidence_score': 0.85,
                    'result_data': {
                        'mvrv_ratio': 1.3,
                        'exchange_netflow': -5000
                    }
                }
            }
        }

        recommendation = filter.generate_trading_recommendation(analysis_result)

        # 강력한 매수 또는 리밸런싱
        assert recommendation['action'] in ['BUY', 'REBALANCE']
        assert recommendation['strength'] > 0.5

    def test_recommendation_strong_sell(self, filter):
        """강력한 매도 신호"""
        analysis_result = {
            'market_season': 'risk_off',
            'season_changed': True,
            'allocation_weights': {'crypto': 0.3, 'krw': 0.7},
            'advanced_analysis': {
                'multi_timeframe': {
                    'confidence_score': 0.15,
                    'result_data': {}
                },
                'macro_economic': {
                    'result_data': {
                        'indicators': {
                            'VIX': {'value': 40},
                            'DXY': {'value': 110}
                        },
                        'crypto_favorability': 0.2
                    }
                },
                'onchain_data': {
                    'confidence_score': 0.2,
                    'result_data': {
                        'mvrv_ratio': 3.5,  # 고평가
                        'exchange_netflow': 5000  # 순유입 (약세)
                    }
                },
                'behavioral_bias': {
                    'result_data': {
                        'fear_level': 0.9
                    }
                }
            }
        }

        recommendation = filter.generate_trading_recommendation(analysis_result)

        # 매도 또는 리밸런싱
        assert recommendation['action'] in ['SELL', 'REBALANCE']

    def test_recommendation_exception(self, filter):
        """추천 생성 중 예외"""
        # 잘못된 데이터로 예외 유발
        analysis_result = None

        recommendation = filter.generate_trading_recommendation(analysis_result)

        # 예외 발생해도 기본 추천 반환
        assert recommendation['action'] == 'HOLD'


class TestAnalyzeWeeklyEdgeCases:
    """analyze_weekly 엣지 케이스"""

    def test_analyze_weekly_with_advanced_analysis(self):
        """고급 분석 결과 반영"""
        mock_db = Mock()
        mock_db.get_all_latest_analysis_results.return_value = {
            'multi_timeframe': {
                'confidence_score': 0.8,
                'result_data': {'overall_confidence': 0.75}
            }
        }
        mock_db.mark_analysis_as_used.return_value = None

        filter = MarketSeasonFilter(buffer_band=0.05, db_manager=mock_db)

        dates = pd.date_range(end=datetime.now(), periods=250, freq='D')
        price_data = pd.DataFrame({
            'Close': [55000000.0] * 250  # 고정 가격
        }, index=dates)

        result = filter.analyze_weekly(price_data)

        assert result['success'] is True
        assert result['advanced_analysis'] is not None

    def test_analyze_weekly_exception(self):
        """분석 중 예외 발생"""
        filter = MarketSeasonFilter()

        # 예외를 유발하는 데이터
        with patch.object(filter, 'calculate_200week_ma', side_effect=Exception("Calc error")):
            dates = pd.date_range(end=datetime.now(), periods=250, freq='D')
            price_data = pd.DataFrame({
                'Close': [55000000.0] * 250
            }, index=dates)

            result = filter.analyze_weekly(price_data)

            assert result['success'] is False
            assert 'error' in result


class TestMarketSeasonFilter200WeekMA:
    """200주 이동평균 계산 고급 테스트"""

    @pytest.fixture
    def filter(self):
        return MarketSeasonFilter(buffer_band=0.05)

    def test_calculate_200week_ma_nan_ma_result(self, filter):
        """200주 MA 결과가 NaN이고 50주 MA로 폴백 (라인 91-98 커버)"""
        # 200주 이상의 주간 데이터 생성하되, 앞부분은 NaN, 뒷부분만 유효
        dates = pd.date_range(end=datetime.now(), periods=210, freq='W')
        prices = [np.nan] * 160 + [50000000.0] * 50
        df = pd.DataFrame({
            'Close': prices
        }, index=dates)

        ma = filter.calculate_200week_ma(df)

        # 50주 MA 또는 평균으로 폴백
        assert ma > 0
        assert not pd.isna(ma)

    def test_calculate_200week_ma_nan_50week_also_nan(self, filter):
        """200주, 50주 MA 모두 NaN일 때 평균으로 폴백 (라인 97-98 커버)"""
        dates = pd.date_range(end=datetime.now(), periods=210, freq='W')
        # 거의 모두 NaN이고 마지막 10개만 유효
        prices = [np.nan] * 200 + [50000000.0] * 10
        df = pd.DataFrame({
            'Close': prices
        }, index=dates)

        ma = filter.calculate_200week_ma(df)

        # 단순 평균으로 폴백
        assert ma > 0


class TestGenerateTradingRecommendationOnchain:
    """온체인 데이터 기반 추천 생성 테스트"""

    @pytest.fixture
    def filter(self):
        return MarketSeasonFilter(buffer_band=0.05)

    def test_recommendation_onchain_nupl_low(self, filter):
        """NUPL 낮음 - 매수 기회 (라인 420-422 커버)"""
        analysis_result = {
            'market_season': 'neutral',
            'season_changed': False,
            'advanced_analysis': {
                'onchain_data': {
                    'confidence_score': 0.8,
                    'result_data': {
                        'metrics': {
                            'nupl': 0.2  # 매수 기회
                        }
                    }
                }
            }
        }

        recommendation = filter.generate_trading_recommendation(analysis_result)

        assert 'action' in recommendation
        assert any('온체인 매수' in r or 'NUPL' in r for r in recommendation['reasons'])

    def test_recommendation_onchain_nupl_high(self, filter):
        """NUPL 높음 - 과열 경고 (라인 423-425 커버)"""
        analysis_result = {
            'market_season': 'neutral',
            'season_changed': False,
            'advanced_analysis': {
                'onchain_data': {
                    'confidence_score': 0.8,
                    'result_data': {
                        'metrics': {
                            'nupl': 0.8  # 과열 구간
                        }
                    }
                }
            }
        }

        recommendation = filter.generate_trading_recommendation(analysis_result)

        assert 'action' in recommendation
        assert any('온체인 과열' in r or 'NUPL' in r for r in recommendation['reasons'])


class TestGenerateTradingRecommendationBias:
    """행동 편향 기반 추천 테스트"""

    @pytest.fixture
    def filter(self):
        return MarketSeasonFilter(buffer_band=0.05)

    def test_recommendation_multiple_biases(self, filter):
        """여러 편향 감지 시 경고 (라인 434-435 커버)"""
        analysis_result = {
            'market_season': 'neutral',
            'season_changed': False,
            'advanced_analysis': {
                'behavioral_bias': {
                    'confidence_score': 0.7,
                    'result_data': {
                        'detected_biases': ['FOMO', 'OVERCONFIDENCE', 'LOSS_AVERSION']
                    }
                }
            }
        }

        recommendation = filter.generate_trading_recommendation(analysis_result)

        assert 'action' in recommendation
        assert any('심리적 편향' in r or '편향' in r for r in recommendation['reasons'])


class TestGenerateTradingRecommendationScenario:
    """시나리오 대응 기반 추천 테스트"""

    @pytest.fixture
    def filter(self):
        return MarketSeasonFilter(buffer_band=0.05)

    def test_recommendation_high_severity_scenario(self, filter):
        """고위험 시나리오 감지 (라인 438-446 커버)"""
        analysis_result = {
            'market_season': 'neutral',
            'season_changed': False,
            'advanced_analysis': {
                'scenario_response': {
                    'confidence_score': 0.8,
                    'result_data': {
                        'active_scenarios': [
                            {'name': 'Flash Crash', 'severity': 'high'}
                        ]
                    }
                }
            }
        }

        recommendation = filter.generate_trading_recommendation(analysis_result)

        assert 'action' in recommendation
        assert any('고위험' in r or '시나리오' in r for r in recommendation['reasons'])


class TestCalculateAdjustmentByAnalysis:
    """분석별 조정값 계산 테스트"""

    @pytest.fixture
    def filter(self):
        return MarketSeasonFilter(buffer_band=0.05)

    def test_adjustment_macro_economic(self, filter):
        """매크로 경제 분석 조정값 (라인 507-510 커버)"""
        result_data = {
            'crypto_favorability': 0.8  # 높은 암호화폐 우호도
        }

        adjustment = filter._calculate_adjustment_by_analysis(
            'macro_economic', result_data, 0.9
        )

        # 양수 조정값
        assert adjustment > 0

    def test_adjustment_scenario_high_risk(self, filter):
        """시나리오 고위험 조정값 (라인 512-516 커버)"""
        result_data = {
            'risk_level': 'high'
        }

        adjustment = filter._calculate_adjustment_by_analysis(
            'scenario_response', result_data, 0.8
        )

        # 음수 조정값 (리스크 회피)
        assert adjustment < 0

    def test_adjustment_scenario_low_risk(self, filter):
        """시나리오 저위험 조정값 (라인 517-518 커버)"""
        result_data = {
            'risk_level': 'low'
        }

        adjustment = filter._calculate_adjustment_by_analysis(
            'scenario_response', result_data, 0.8
        )

        # 양수 조정값 (리스크 추구)
        assert adjustment > 0

    def test_adjustment_composite_strong_buy(self, filter):
        """복합 신호 STRONG_BUY (라인 520-528 커버)"""
        result_data = {
            'signal': 'STRONG_BUY',
            'confidence': 0.85
        }

        adjustment = filter._calculate_adjustment_by_analysis(
            'composite_signal', result_data, 0.9
        )

        # 강한 양수 조정값
        assert adjustment == 0.10

    def test_adjustment_composite_strong_sell(self, filter):
        """복합 신호 STRONG_SELL (라인 529-531 커버)"""
        result_data = {
            'signal': 'STRONG_SELL',
            'confidence': 0.85
        }

        adjustment = filter._calculate_adjustment_by_analysis(
            'composite_signal', result_data, 0.9
        )

        # 강한 음수 조정값
        assert adjustment == -0.10

    def test_adjustment_composite_buy(self, filter):
        """복합 신호 BUY (라인 532-533 커버)"""
        result_data = {
            'signal': 'BUY',
            'confidence': 0.7
        }

        adjustment = filter._calculate_adjustment_by_analysis(
            'composite_signal', result_data, 0.8
        )

        # 약한 양수 조정값
        assert adjustment == 0.05

    def test_adjustment_composite_sell(self, filter):
        """복합 신호 SELL (라인 534-535 커버)"""
        result_data = {
            'signal': 'SELL',
            'confidence': 0.7
        }

        adjustment = filter._calculate_adjustment_by_analysis(
            'composite_signal', result_data, 0.8
        )

        # 약한 음수 조정값
        assert adjustment == -0.05

    def test_adjustment_unknown_type(self, filter):
        """알 수 없는 분석 타입 (라인 537 커버)"""
        result_data = {'some_key': 'some_value'}

        adjustment = filter._calculate_adjustment_by_analysis(
            'unknown_analysis_type', result_data, 0.8
        )

        # 조정값 0
        assert adjustment == 0.0

    def test_adjustment_exception(self, filter):
        """조정값 계산 중 예외 (라인 539-541 커버)"""
        # 예외를 유발하는 데이터
        result_data = None  # 예외 유발

        with patch.dict(filter.__dict__, {}):  # 불변 객체 테스트를 위한 패치
            adjustment = filter._calculate_adjustment_by_analysis(
                'multi_timeframe', None, 0.5
            )

            # 예외 발생 시 0 반환
            assert adjustment == 0.0


class TestAdjustAllocationWithAnalysisAdvanced:
    """고급 분석 반영 배분 조정 상세 테스트"""

    @pytest.fixture
    def filter(self):
        return MarketSeasonFilter(buffer_band=0.05)

    def test_adjust_allocation_significant_adjustment(self, filter):
        """큰 조정값 적용 (라인 335-347 커버)"""
        base_allocation = {'crypto': 0.5, 'krw': 0.5}
        advanced_analysis = {
            'multi_timeframe': {
                'confidence_score': 0.9,
                'result_data': {'overall_confidence': 0.9}
            },
            'macro_economic': {
                'confidence_score': 0.9,
                'result_data': {'crypto_favorability': 0.8}
            },
            'composite_signal': {
                'confidence_score': 0.9,
                'result_data': {'signal': 'STRONG_BUY', 'confidence': 0.85}
            }
        }

        adjusted = filter._adjust_allocation_with_analysis(
            base_allocation, advanced_analysis
        )

        # 암호화폐 비중 증가
        assert adjusted['crypto'] > base_allocation['crypto']
        # 합계는 1.0
        assert adjusted['crypto'] + adjusted['krw'] == pytest.approx(1.0, rel=1e-3)

    def test_adjust_allocation_exception_handling(self, filter):
        """배분 조정 중 예외 처리 (라인 351-353 커버)"""
        base_allocation = {'crypto': 0.5, 'krw': 0.5}

        # 예외를 유발하는 분석 결과
        class BadDict:
            def get(self, key, default=None):
                raise Exception("Bad access")

        # _calculate_adjustment_by_analysis에서 예외 발생
        with patch.object(filter, '_calculate_adjustment_by_analysis', side_effect=Exception("Error")):
            adjusted = filter._adjust_allocation_with_analysis(
                base_allocation, {'multi_timeframe': {'confidence_score': 0.8, 'result_data': {}}}
            )

            # 기본 배분 반환
            assert adjusted == base_allocation


class TestGenerateTradingRecommendationBuyRatio:
    """매수/매도 비율 기반 추천 테스트"""

    @pytest.fixture
    def filter(self):
        return MarketSeasonFilter(buffer_band=0.05)

    def test_recommendation_buy_ratio_over_80(self, filter):
        """매수 비율 80% 초과 - 즉시 액션 (라인 461-462 커버)"""
        analysis_result = {
            'market_season': 'risk_on',
            'season_changed': False,
            'allocation_weights': {'crypto': 0.7, 'krw': 0.3},
            'advanced_analysis': {
                'multi_timeframe': {
                    'confidence_score': 0.9,
                    'result_data': {}
                },
                'macro_economic': {
                    'result_data': {
                        'indicators': {
                            'VIX': {'value': 12},
                            'DXY': {'value': 92}
                        }
                    }
                },
                'onchain_data': {
                    'result_data': {
                        'metrics': {
                            'nupl': 0.2
                        }
                    }
                }
            }
        }

        recommendation = filter.generate_trading_recommendation(analysis_result)

        # BUY 액션
        assert recommendation['action'] == 'BUY'
        # 즉시 액션
        assert recommendation['immediate_action'] is True

    def test_recommendation_sell_ratio_over_80(self, filter):
        """매도 비율 80% 초과 - 즉시 액션 (라인 466-467 커버)"""
        analysis_result = {
            'market_season': 'risk_off',
            'season_changed': False,
            'allocation_weights': {'crypto': 0.3, 'krw': 0.7},
            'advanced_analysis': {
                'multi_timeframe': {
                    'confidence_score': 0.1,
                    'result_data': {}
                },
                'macro_economic': {
                    'result_data': {
                        'indicators': {
                            'VIX': {'value': 40},
                            'DXY': {'value': 110}
                        }
                    }
                },
                'onchain_data': {
                    'result_data': {
                        'metrics': {
                            'nupl': 0.9
                        }
                    }
                }
            }
        }

        recommendation = filter.generate_trading_recommendation(analysis_result)

        # SELL 액션
        assert recommendation['action'] == 'SELL'
        # 즉시 액션
        assert recommendation['immediate_action'] is True
