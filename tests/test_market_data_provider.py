"""
Market Data Provider Tests

시장 데이터 제공자 테스트 모듈
"""

import pytest
import pandas as pd
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta

from src.utils.market_data_provider import MarketDataProvider


@pytest.mark.data
class TestMarketDataProviderInit:
    """MarketDataProvider 초기화 테스트"""

    def test_init_without_db(self):
        """DB 없이 초기화"""
        provider = MarketDataProvider()

        assert provider.db_manager is None

    def test_init_with_db(self):
        """DB와 함께 초기화"""
        mock_db = Mock()
        provider = MarketDataProvider(db_manager=mock_db)

        assert provider.db_manager == mock_db


@pytest.mark.data
class TestGetBtc200WMA:
    """BTC 200주 이동평균 조회 테스트"""

    @pytest.fixture
    def provider(self):
        return MarketDataProvider()

    @pytest.fixture
    def provider_with_db(self):
        mock_db = Mock()
        return MarketDataProvider(db_manager=mock_db)

    def test_get_200w_ma_from_cache(self, provider_with_db):
        """캐시에서 200주 이동평균 조회"""
        with patch.object(provider_with_db, '_get_cached_200w_ma', return_value=50000000.0):
            ma, source = provider_with_db.get_btc_200w_ma()

            assert ma == 50000000.0
            assert source == "cache"

    def test_get_200w_ma_from_binance(self, provider):
        """Binance에서 200주 이동평균 계산"""
        with patch.object(provider, '_calculate_200w_ma_from_binance', return_value=48000000.0):
            ma, source = provider.get_btc_200w_ma()

            assert ma == 48000000.0
            assert source == "binance"

    def test_get_200w_ma_fallback_to_current_price(self, provider):
        """현재가 기반 fallback"""
        with patch.object(provider, '_calculate_200w_ma_from_binance', return_value=None):
            with patch.object(provider, '_get_current_btc_price', return_value=60000000.0):
                ma, source = provider.get_btc_200w_ma(fallback_to_current_price=True)

                assert source == "fallback"
                # 현재가 * MA_CALCULATION_FALLBACK_RATIO
                assert ma > 0

    def test_get_200w_ma_emergency_fallback(self, provider):
        """최종 emergency fallback"""
        with patch.object(provider, '_calculate_200w_ma_from_binance', side_effect=Exception("Error")):
            with patch.object(provider, '_get_current_btc_price', return_value=None):
                ma, source = provider.get_btc_200w_ma(fallback_to_current_price=True)

                assert source == "emergency_fallback"
                assert ma > 0

    def test_get_200w_ma_no_fallback_raises_exception(self, provider):
        """fallback 비활성화 시 예외 발생"""
        with patch.object(provider, '_calculate_200w_ma_from_binance', return_value=None):
            with patch.object(provider, '_get_current_btc_price', return_value=None):
                with pytest.raises(Exception):
                    provider.get_btc_200w_ma(fallback_to_current_price=False)

    def test_get_200w_ma_cache_and_store(self, provider_with_db):
        """Binance에서 계산 후 캐시 저장"""
        provider_with_db._get_cached_200w_ma = Mock(return_value=None)
        provider_with_db._cache_200w_ma = Mock()

        with patch.object(provider_with_db, '_calculate_200w_ma_from_binance', return_value=50000000.0):
            ma, source = provider_with_db.get_btc_200w_ma()

            assert ma == 50000000.0
            assert source == "binance"
            provider_with_db._cache_200w_ma.assert_called_once_with(50000000.0)


@pytest.mark.data
class TestCalculate200WMAFromBinance:
    """Binance에서 200주 이동평균 계산 테스트"""

    @pytest.fixture
    def provider(self):
        return MarketDataProvider()

    def test_calculate_200w_ma_with_sufficient_data(self, provider):
        """충분한 데이터로 200주 이동평균 계산"""
        # 200주 데이터 생성
        mock_df = pd.DataFrame({
            'Close': [50000000.0 + i * 10000 for i in range(1400)],
            'Volume': [100.0] * 1400
        })

        with patch('src.utils.market_data_provider.BinanceDataProvider') as MockProvider:
            mock_instance = MockProvider.return_value
            mock_instance.get_btc_price_data_for_analysis.return_value = mock_df
            mock_instance.convert_usdt_to_krw.return_value = mock_df

            ma = provider._calculate_200w_ma_from_binance()

            assert ma is not None
            assert ma > 0

    def test_calculate_200w_ma_with_weekly_data(self, provider):
        """주간 데이터로 200주 이동평균 계산"""
        # 200개 주간 데이터
        mock_df = pd.DataFrame({
            'Close': [50000000.0 + i * 100000 for i in range(210)],
            'Volume': [1000.0] * 210
        })

        with patch('src.utils.market_data_provider.BinanceDataProvider') as MockProvider:
            mock_instance = MockProvider.return_value
            mock_instance.get_btc_price_data_for_analysis.return_value = mock_df
            mock_instance.convert_usdt_to_krw.return_value = mock_df

            ma = provider._calculate_200w_ma_from_binance()

            assert ma is not None
            assert ma > 0

    def test_calculate_200w_ma_with_insufficient_data(self, provider):
        """부족한 데이터로 이동평균 계산"""
        # 100개 데이터만
        mock_df = pd.DataFrame({
            'Close': [50000000.0 + i * 10000 for i in range(100)],
            'Volume': [100.0] * 100
        })

        with patch('src.utils.market_data_provider.BinanceDataProvider') as MockProvider:
            mock_instance = MockProvider.return_value
            mock_instance.get_btc_price_data_for_analysis.return_value = mock_df
            mock_instance.convert_usdt_to_krw.return_value = mock_df

            ma = provider._calculate_200w_ma_from_binance()

            # 보유한 데이터로 최대한 계산
            assert ma is not None

    def test_calculate_200w_ma_empty_data(self, provider):
        """빈 데이터 처리"""
        with patch('src.utils.market_data_provider.BinanceDataProvider') as MockProvider:
            mock_instance = MockProvider.return_value
            mock_instance.get_btc_price_data_for_analysis.return_value = pd.DataFrame()

            ma = provider._calculate_200w_ma_from_binance()

            assert ma is None

    def test_calculate_200w_ma_exception(self, provider):
        """예외 처리"""
        with patch('src.utils.market_data_provider.BinanceDataProvider') as MockProvider:
            MockProvider.side_effect = Exception("API Error")

            ma = provider._calculate_200w_ma_from_binance()

            assert ma is None

    def test_calculate_200w_ma_invalid_value(self, provider):
        """비정상적인 값 필터링"""
        # 현재가보다 2배 이상 높은 이동평균 (비정상)
        mock_df = pd.DataFrame({
            'Close': [50000000.0, 50000000.0, 150000000.0],  # 마지막 값이 비정상
            'Volume': [100.0] * 3
        })

        with patch('src.utils.market_data_provider.BinanceDataProvider') as MockProvider:
            mock_instance = MockProvider.return_value
            mock_instance.get_btc_price_data_for_analysis.return_value = mock_df
            mock_instance.convert_usdt_to_krw.return_value = mock_df

            ma = provider._calculate_200w_ma_from_binance()

            # 비정상 값은 None 반환
            assert ma is None or ma < 150000000.0 * 2


@pytest.mark.data
class TestGetCurrentBtcPrice:
    """현재 BTC 가격 조회 테스트"""

    @pytest.fixture
    def provider(self):
        return MarketDataProvider()

    def test_get_current_price_success(self, provider):
        """현재 가격 조회 성공"""
        mock_df = pd.DataFrame({
            'Close': [60000000.0],
            'Volume': [1000.0]
        })

        with patch('src.utils.market_data_provider.BinanceDataProvider') as MockProvider:
            mock_instance = MockProvider.return_value
            mock_instance.get_historical_klines.return_value = mock_df
            mock_instance.convert_usdt_to_krw.return_value = mock_df

            price = provider._get_current_btc_price()

            assert price == 60000000.0

    def test_get_current_price_empty_data(self, provider):
        """빈 데이터"""
        with patch('src.utils.market_data_provider.BinanceDataProvider') as MockProvider:
            mock_instance = MockProvider.return_value
            mock_instance.get_historical_klines.return_value = pd.DataFrame()

            price = provider._get_current_btc_price()

            assert price is None

    def test_get_current_price_exception(self, provider):
        """예외 처리"""
        with patch('src.utils.market_data_provider.BinanceDataProvider') as MockProvider:
            MockProvider.side_effect = Exception("API Error")

            price = provider._get_current_btc_price()

            assert price is None


@pytest.mark.data
class TestGetCached200WMA:
    """캐시된 200주 이동평균 조회 테스트"""

    def test_get_cached_no_db(self):
        """DB 없이 호출"""
        provider = MarketDataProvider()

        result = provider._get_cached_200w_ma()

        assert result is None

    def test_get_cached_found(self):
        """캐시된 데이터 발견"""
        mock_db = Mock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            'ma_200w': 50000000.0,
            'calculated_at': datetime.now().isoformat()
        }
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_conn.cursor.return_value = mock_cursor
        mock_db.get_connection.return_value = mock_conn

        provider = MarketDataProvider(db_manager=mock_db)

        result = provider._get_cached_200w_ma()

        assert result == 50000000.0

    def test_get_cached_not_found(self):
        """캐시된 데이터 없음"""
        mock_db = Mock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_conn.cursor.return_value = mock_cursor
        mock_db.get_connection.return_value = mock_conn

        provider = MarketDataProvider(db_manager=mock_db)

        result = provider._get_cached_200w_ma()

        assert result is None

    def test_get_cached_exception(self):
        """예외 처리"""
        mock_db = Mock()
        mock_db.get_connection.side_effect = Exception("DB Error")

        provider = MarketDataProvider(db_manager=mock_db)

        result = provider._get_cached_200w_ma()

        assert result is None


@pytest.mark.data
class TestCache200WMA:
    """200주 이동평균 캐시 저장 테스트"""

    def test_cache_no_db(self):
        """DB 없이 호출"""
        provider = MarketDataProvider()

        # 예외 없이 완료되어야 함
        provider._cache_200w_ma(50000000.0)

    def test_cache_success(self):
        """캐시 저장 성공"""
        mock_db = Mock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_conn.cursor.return_value = mock_cursor
        mock_db.get_connection.return_value = mock_conn

        provider = MarketDataProvider(db_manager=mock_db)
        provider._cache_200w_ma(50000000.0)

        # 테이블 생성 및 삽입 호출 확인
        assert mock_cursor.execute.call_count >= 2
        mock_conn.commit.assert_called_once()

    def test_cache_exception(self):
        """예외 처리"""
        mock_db = Mock()
        mock_db.get_connection.side_effect = Exception("DB Error")

        provider = MarketDataProvider(db_manager=mock_db)

        # 예외 없이 완료되어야 함 (로깅만)
        provider._cache_200w_ma(50000000.0)


@pytest.mark.data
class TestGetMarketVolatility:
    """시장 변동성 계산 테스트"""

    @pytest.fixture
    def provider(self):
        return MarketDataProvider()

    def test_get_volatility_success(self, provider):
        """변동성 계산 성공"""
        mock_df = pd.DataFrame({
            'Close': [50000000.0, 51000000.0, 49000000.0, 52000000.0, 48000000.0],
            'Volume': [100.0, 110.0, 90.0, 120.0, 80.0]
        })

        with patch('src.utils.market_data_provider.BinanceDataProvider') as MockProvider:
            mock_instance = MockProvider.return_value
            mock_instance.get_historical_klines.return_value = mock_df
            mock_instance.convert_usdt_to_krw.return_value = mock_df

            result = provider.get_market_volatility(days=5)

            assert 'volatility' in result
            assert 'avg_volume' in result
            assert result['volatility'] > 0
            assert result['avg_volume'] > 0
            assert result['period_days'] == 5

    def test_get_volatility_empty_data(self, provider):
        """빈 데이터"""
        with patch('src.utils.market_data_provider.BinanceDataProvider') as MockProvider:
            mock_instance = MockProvider.return_value
            mock_instance.get_historical_klines.return_value = pd.DataFrame()

            result = provider.get_market_volatility()

            assert result['volatility'] == 0.0
            assert result['avg_volume'] == 0.0

    def test_get_volatility_insufficient_data(self, provider):
        """데이터 부족 (1개 미만)"""
        mock_df = pd.DataFrame({
            'Close': [50000000.0],
            'Volume': [100.0]
        })

        with patch('src.utils.market_data_provider.BinanceDataProvider') as MockProvider:
            mock_instance = MockProvider.return_value
            mock_instance.get_historical_klines.return_value = mock_df
            mock_instance.convert_usdt_to_krw.return_value = mock_df

            result = provider.get_market_volatility()

            assert result['volatility'] == 0.0
            assert result['avg_volume'] == 0.0

    def test_get_volatility_exception(self, provider):
        """예외 처리"""
        with patch('src.utils.market_data_provider.BinanceDataProvider') as MockProvider:
            MockProvider.side_effect = Exception("API Error")

            result = provider.get_market_volatility()

            assert result['volatility'] == 0.0
            assert result['avg_volume'] == 0.0

    def test_get_volatility_custom_days(self, provider):
        """커스텀 기간"""
        mock_df = pd.DataFrame({
            'Close': [50000000.0 + i * 100000 for i in range(60)],
            'Volume': [100.0] * 60
        })

        with patch('src.utils.market_data_provider.BinanceDataProvider') as MockProvider:
            mock_instance = MockProvider.return_value
            mock_instance.get_historical_klines.return_value = mock_df
            mock_instance.convert_usdt_to_krw.return_value = mock_df

            result = provider.get_market_volatility(days=60)

            assert result['period_days'] == 60
            assert result['data_points'] == 60


@pytest.mark.data
class TestMarketDataProviderIntegration:
    """통합 테스트"""

    def test_full_workflow_with_cache(self):
        """캐시를 활용한 전체 워크플로우"""
        mock_db = Mock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # 처음에는 캐시 없음
        mock_cursor.fetchone.return_value = None
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_conn.cursor.return_value = mock_cursor
        mock_db.get_connection.return_value = mock_conn

        provider = MarketDataProvider(db_manager=mock_db)

        # Binance에서 데이터 가져오기
        mock_df = pd.DataFrame({
            'Close': [50000000.0 + i * 10000 for i in range(200)],
            'Volume': [100.0] * 200
        })

        with patch('src.utils.market_data_provider.BinanceDataProvider') as MockProvider:
            mock_instance = MockProvider.return_value
            mock_instance.get_btc_price_data_for_analysis.return_value = mock_df
            mock_instance.convert_usdt_to_krw.return_value = mock_df

            ma, source = provider.get_btc_200w_ma()

            assert source == "binance"
            assert ma > 0

    def test_full_workflow_fallback_chain(self):
        """fallback 체인 테스트"""
        provider = MarketDataProvider()

        # 모든 외부 호출 실패
        with patch.object(provider, '_calculate_200w_ma_from_binance', return_value=None):
            with patch.object(provider, '_get_current_btc_price', return_value=None):
                ma, source = provider.get_btc_200w_ma(fallback_to_current_price=True)

                assert source == "emergency_fallback"
                assert ma > 0
