"""
Binance Data Provider Tests
binance_data_provider.py 모듈의 테스트
"""
import pytest
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from src.utils.binance_data_provider import BinanceDataProvider


class TestBinanceDataProviderInit:
    """BinanceDataProvider 초기화 테스트"""

    def test_init_without_credentials(self):
        """API 키 없이 초기화"""
        with patch('src.utils.binance_data_provider.Client') as MockClient:
            provider = BinanceDataProvider()

            MockClient.assert_called_once_with("", "")
            assert provider.client is not None
            assert 'kline_intervals' in dir(provider)

    def test_init_with_credentials(self):
        """API 키로 초기화"""
        with patch('src.utils.binance_data_provider.Client') as MockClient:
            provider = BinanceDataProvider(api_key="test_key", api_secret="test_secret")

            MockClient.assert_called_once_with("test_key", "test_secret")

    def test_kline_intervals(self):
        """시간 간격 설정 확인"""
        with patch('src.utils.binance_data_provider.Client'):
            provider = BinanceDataProvider()

            assert '1d' in provider.kline_intervals
            assert '1w' in provider.kline_intervals
            assert '1h' in provider.kline_intervals
            assert '4h' in provider.kline_intervals


class TestGetHistoricalKlines:
    """get_historical_klines 테스트"""

    @pytest.fixture
    def mock_klines(self):
        """샘플 캔들 데이터"""
        return [
            [1609459200000, '30000', '31000', '29500', '30500', '1000',
             1609545599999, '30500000', 5000, '500', '15250000', '0'],
            [1609545600000, '30500', '32000', '30000', '31500', '1200',
             1609631999999, '37800000', 6000, '600', '18900000', '0'],
        ]

    @pytest.fixture
    def provider(self):
        with patch('src.utils.binance_data_provider.Client'):
            return BinanceDataProvider()

    def test_get_historical_klines_success(self, provider, mock_klines):
        """성공적인 데이터 조회"""
        provider.client.get_historical_klines.return_value = mock_klines

        df = provider.get_historical_klines(symbol="BTCUSDT", interval="1d")

        assert not df.empty
        assert len(df) == 2
        assert 'Open' in df.columns
        assert 'High' in df.columns
        assert 'Low' in df.columns
        assert 'Close' in df.columns
        assert 'Volume' in df.columns

    def test_get_historical_klines_with_dates(self, provider, mock_klines):
        """날짜 범위 지정 조회"""
        provider.client.get_historical_klines.return_value = mock_klines

        start = datetime.now() - timedelta(days=30)
        end = datetime.now()

        df = provider.get_historical_klines(
            symbol="BTCUSDT",
            interval="1d",
            start_date=start,
            end_date=end
        )

        assert not df.empty
        # 날짜가 밀리초 문자열로 변환되어 호출됨
        call_args = provider.client.get_historical_klines.call_args
        assert call_args is not None

    def test_get_historical_klines_without_start_date(self, provider, mock_klines):
        """시작 날짜 없이 조회 (기본 5년)"""
        provider.client.get_historical_klines.return_value = mock_klines

        df = provider.get_historical_klines(symbol="BTCUSDT", interval="1d")

        assert not df.empty

    def test_get_historical_klines_without_end_date(self, provider, mock_klines):
        """종료 날짜 없이 조회"""
        provider.client.get_historical_klines.return_value = mock_klines

        df = provider.get_historical_klines(
            symbol="BTCUSDT",
            interval="1d",
            start_date=datetime.now() - timedelta(days=30)
        )

        assert not df.empty

    def test_get_historical_klines_empty_response(self, provider):
        """빈 응답 처리"""
        provider.client.get_historical_klines.return_value = []

        df = provider.get_historical_klines(symbol="BTCUSDT")

        assert df.empty

    def test_get_historical_klines_none_response(self, provider):
        """None 응답 처리"""
        provider.client.get_historical_klines.return_value = None

        df = provider.get_historical_klines(symbol="BTCUSDT")

        assert df.empty

    def test_get_historical_klines_api_exception(self, provider):
        """Binance API 예외 처리"""
        from binance.exceptions import BinanceAPIException
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "API Error"
        provider.client.get_historical_klines.side_effect = BinanceAPIException(
            response=mock_response, status_code=400, text="API Error"
        )

        df = provider.get_historical_klines(symbol="BTCUSDT")

        assert df.empty

    def test_get_historical_klines_general_exception(self, provider):
        """일반 예외 처리"""
        provider.client.get_historical_klines.side_effect = Exception("Network error")

        df = provider.get_historical_klines(symbol="BTCUSDT")

        assert df.empty

    def test_get_historical_klines_different_intervals(self, provider, mock_klines):
        """다양한 시간 간격 테스트"""
        provider.client.get_historical_klines.return_value = mock_klines

        for interval in ['1d', '1w', '1h', '4h', 'unknown']:
            df = provider.get_historical_klines(symbol="BTCUSDT", interval=interval)
            assert not df.empty

    @staticmethod
    def make_daily_klines(n, start_close=100.0):
        """n개의 일봉 mock — Close가 start_close부터 1씩 증가"""
        data = []
        base = datetime.now() - timedelta(days=n)
        for i in range(n):
            ts = int((base + timedelta(days=i)).timestamp() * 1000)
            close = start_close + i
            data.append([
                ts, str(close - 1), str(close + 1), str(close - 2),
                str(close), '1000', ts + 86399999, '30500000',
                5000, '500', '15250000', '0'
            ])
        return data

    def test_limit_returns_most_recent_candles(self, provider):
        """limit=N이면 가장 최근 N개만 반환 — limit 무시 시 5년 수익률을
        14일 벤치마크로 보고하는 버그(월간 리포트 BTC +64.8%)의 근본 원인"""
        provider.client.get_historical_klines.return_value = self.make_daily_klines(30)

        df = provider.get_historical_klines(symbol="BTCUSDT", interval="1d", limit=5)

        assert len(df) == 5
        # 앞이 아니라 뒤(최근)에서 잘라야 함: Close 125~129
        assert list(df["Close"]) == [125.0, 126.0, 127.0, 128.0, 129.0]

    def test_limit_narrows_default_start_range(self, provider):
        """start_date 없이 limit만 주면 조회 범위도 limit 기반이어야 함
        (5년치를 받아와 뒤에서 자르는 낭비 금지)"""
        provider.client.get_historical_klines.return_value = self.make_daily_klines(16)

        provider.get_historical_klines(symbol="BTCUSDT", interval="1d", limit=15)

        start_ms = int(provider.client.get_historical_klines.call_args.args[2])
        thirty_days_ago_ms = int(
            (datetime.now() - timedelta(days=30)).timestamp() * 1000
        )
        assert start_ms > thirty_days_ago_ms

    def test_no_limit_returns_full_range(self, provider):
        """limit 미지정이면 기존 동작 유지 — 전체 기간 반환 (백테스트 등)"""
        provider.client.get_historical_klines.return_value = self.make_daily_klines(30)

        df = provider.get_historical_klines(symbol="BTCUSDT", interval="1d")

        assert len(df) == 30
        # 기본 조회 시작은 5년 전
        start_ms = int(provider.client.get_historical_klines.call_args.args[2])
        four_years_ago_ms = int(
            (datetime.now() - timedelta(days=365 * 4)).timestamp() * 1000
        )
        assert start_ms < four_years_ago_ms


class TestGetBTCPriceDataForAnalysis:
    """get_btc_price_data_for_analysis 테스트"""

    @pytest.fixture
    def mock_weekly_data(self):
        """210주 이상의 주간 데이터"""
        data = []
        for i in range(220):
            timestamp = int((datetime.now() - timedelta(weeks=220-i)).timestamp() * 1000)
            data.append([
                timestamp, str(30000+i*10), str(31000+i*10), str(29500+i*10),
                str(30500+i*10), '1000', timestamp+604799999, '30500000',
                5000, '500', '15250000', '0'
            ])
        return data

    @pytest.fixture
    def mock_insufficient_weekly_data(self):
        """200주 미만의 주간 데이터"""
        data = []
        for i in range(100):
            timestamp = int((datetime.now() - timedelta(weeks=100-i)).timestamp() * 1000)
            data.append([
                timestamp, str(30000+i*10), str(31000+i*10), str(29500+i*10),
                str(30500+i*10), '1000', timestamp+604799999, '30500000',
                5000, '500', '15250000', '0'
            ])
        return data

    @pytest.fixture
    def mock_daily_data(self):
        """일간 데이터"""
        data = []
        for i in range(365):
            timestamp = int((datetime.now() - timedelta(days=365-i)).timestamp() * 1000)
            data.append([
                timestamp, str(30000+i), str(31000+i), str(29500+i),
                str(30500+i), '1000', timestamp+86399999, '30500000',
                5000, '500', '15250000', '0'
            ])
        return data

    @pytest.fixture
    def provider(self):
        with patch('src.utils.binance_data_provider.Client'):
            return BinanceDataProvider()

    def test_sufficient_weekly_data(self, provider, mock_weekly_data):
        """충분한 주간 데이터가 있을 때"""
        provider.client.get_historical_klines.return_value = mock_weekly_data

        df = provider.get_btc_price_data_for_analysis(weeks_required=210)

        assert not df.empty
        assert len(df) >= 200

    def test_fallback_to_daily_data(self, provider, mock_insufficient_weekly_data, mock_daily_data):
        """주간 데이터 부족 시 일간 데이터로 대체"""
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_insufficient_weekly_data  # 주간 데이터 (부족)
            else:
                return mock_daily_data  # 일간 데이터

        provider.client.get_historical_klines.side_effect = side_effect

        df = provider.get_btc_price_data_for_analysis(weeks_required=210, fallback_to_daily=True)

        assert not df.empty

    def test_no_fallback_option(self, provider, mock_insufficient_weekly_data):
        """폴백 비활성화 시"""
        provider.client.get_historical_klines.return_value = mock_insufficient_weekly_data

        df = provider.get_btc_price_data_for_analysis(weeks_required=210, fallback_to_daily=False)

        # 주간 데이터만 반환 (200주 미만이면 그대로 반환)
        assert len(df) < 200

    def test_empty_fallback_data(self, provider, mock_insufficient_weekly_data):
        """일간 데이터도 없을 때"""
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_insufficient_weekly_data
            else:
                return []  # 빈 일간 데이터

        provider.client.get_historical_klines.side_effect = side_effect

        df = provider.get_btc_price_data_for_analysis(weeks_required=210, fallback_to_daily=True)

        # 빈 데이터프레임 반환
        assert df.empty

    def test_exception_handling(self, provider):
        """예외 처리"""
        provider.client.get_historical_klines.side_effect = Exception("Data fetch error")

        df = provider.get_btc_price_data_for_analysis()

        assert df.empty

    def test_daily_fallback_not_truncated_below_200w_requirement(
        self, provider, mock_insufficient_weekly_data
    ):
        """일간 폴백(4년치 ≈ 1461개)이 limit에 잘려 200주MA에 필요한
        1400일 밑으로 내려가면 안 됨"""
        daily_4y = TestGetHistoricalKlines.make_daily_klines(1461)
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_insufficient_weekly_data
            return daily_4y

        provider.client.get_historical_klines.side_effect = side_effect

        df = provider.get_btc_price_data_for_analysis(
            weeks_required=210, fallback_to_daily=True
        )

        assert len(df) >= 1400


class TestConvertUSDTToKRW:
    """convert_usdt_to_krw 테스트"""

    @pytest.fixture
    def provider(self):
        with patch('src.utils.binance_data_provider.Client'):
            return BinanceDataProvider()

    @pytest.fixture
    def sample_df(self):
        """샘플 USDT 가격 데이터"""
        return pd.DataFrame({
            'Open': [30000.0, 31000.0],
            'High': [31500.0, 32500.0],
            'Low': [29500.0, 30500.0],
            'Close': [31000.0, 32000.0],
            'Volume': [1000.0, 1200.0]
        })

    def test_convert_usdt_to_krw_success(self, provider, sample_df):
        """KRW 변환 성공"""
        rate = 1400

        result = provider.convert_usdt_to_krw(sample_df, usd_krw_rate=rate)

        assert result['Close'].iloc[0] == 31000.0 * rate
        assert result['Open'].iloc[0] == 30000.0 * rate

    def test_convert_usdt_to_krw_default_rate(self, provider, sample_df):
        """기본 환율 사용"""
        from src.utils.constants import DEFAULT_USD_KRW_RATE

        result = provider.convert_usdt_to_krw(sample_df)

        assert result['Close'].iloc[0] == 31000.0 * DEFAULT_USD_KRW_RATE

    def test_convert_usdt_to_krw_exception(self, provider):
        """예외 발생 시 원본 반환"""
        # 잘못된 데이터프레임
        df = pd.DataFrame({'Invalid': [1, 2, 3]})

        result = provider.convert_usdt_to_krw(df)

        # 변환 시도 후 원본 반환 (예외 없음)
        assert 'Invalid' in result.columns


class TestTestFunction:
    """test_binance_provider 함수 테스트"""

    def test_test_binance_provider_success(self):
        """테스트 함수 성공 케이스"""
        mock_data = pd.DataFrame({
            'Open': [30000.0],
            'High': [31000.0],
            'Low': [29500.0],
            'Close': [30500.0],
            'Volume': [1000.0]
        }, index=[datetime.now()])

        with patch('src.utils.binance_data_provider.BinanceDataProvider') as MockProvider:
            instance = MockProvider.return_value
            instance.get_btc_price_data_for_analysis.return_value = mock_data
            instance.convert_usdt_to_krw.return_value = mock_data.copy()
            instance.convert_usdt_to_krw.return_value['Close'] = [30500.0 * 1400]

            # 함수 import 및 실행
            from src.utils.binance_data_provider import test_binance_provider
            test_binance_provider()  # 예외 없이 실행되어야 함

    def test_test_binance_provider_empty_data(self):
        """테스트 함수 빈 데이터 케이스"""
        with patch('src.utils.binance_data_provider.BinanceDataProvider') as MockProvider:
            instance = MockProvider.return_value
            instance.get_btc_price_data_for_analysis.return_value = pd.DataFrame()

            from src.utils.binance_data_provider import test_binance_provider
            test_binance_provider()  # 예외 없이 실행되어야 함
