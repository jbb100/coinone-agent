"""
Binance API를 통한 히스토리컬 데이터 제공자

더 긴 기간의 BTC 가격 데이터를 제공하기 위한 Binance API 통합
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from binance.client import Client
import nest_asyncio
nest_asyncio.apply()  # 중첩된 이벤트 루프 허용
from binance.exceptions import BinanceAPIException
from loguru import logger
import time


class BinanceDataProvider:
    """
    Binance API를 통한 가격 데이터 제공자
    
    200주 이상의 장기 데이터를 효율적으로 수집
    """
    
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        """
        Args:
            api_key: Binance API 키 (선택적 - 공개 데이터만 필요)
            api_secret: Binance API 시크릿 (선택적)
        """
        # API 키 없이도 공개 데이터 접근 가능
        self.client = Client(api_key or "", api_secret or "")
        self.kline_intervals = {
            '1d': Client.KLINE_INTERVAL_1DAY,
            '1w': Client.KLINE_INTERVAL_1WEEK,
            '1h': Client.KLINE_INTERVAL_1HOUR,
            '4h': Client.KLINE_INTERVAL_4HOUR
        }
    
    def get_historical_klines(
        self, 
        symbol: str = "BTCUSDT",
        interval: str = "1d",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 1000
    ) -> pd.DataFrame:
        """
        Binance에서 히스토리컬 캔들 데이터 가져오기
        
        Args:
            symbol: 거래 심볼 (기본: BTCUSDT)
            interval: 시간 간격 ('1d', '1w', '1h', '4h')
            start_date: 시작 날짜
            end_date: 종료 날짜
            limit: 최대 데이터 개수
            
        Returns:
            OHLCV 데이터프레임
        """
        try:
            # 시간 간격 변환
            kline_interval = self.kline_intervals.get(interval, Client.KLINE_INTERVAL_1DAY)
            
            # 날짜 처리
            if start_date:
                start_str = str(int(start_date.timestamp() * 1000))
            else:
                # 기본값: 5년 전
                start_str = str(int((datetime.now() - timedelta(days=365*5)).timestamp() * 1000))
            
            if end_date:
                end_str = str(int(end_date.timestamp() * 1000))
            else:
                end_str = None
            
            logger.info(f"Binance에서 {symbol} 데이터 수집 중... (간격: {interval})")
            
            # 데이터 가져오기
            klines = self.client.get_historical_klines(
                symbol,
                kline_interval,
                start_str,
                end_str,
                limit=limit
            )
            
            if not klines:
                logger.warning("Binance에서 데이터를 가져오지 못했습니다")
                return pd.DataFrame()
            
            # 데이터프레임 변환
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            
            # 타입 변환
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')
            
            # 가격 데이터 float 변환
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
            
            # 인덱스 설정
            df.set_index('timestamp', inplace=True)
            
            # yfinance 형식에 맞춰 컬럼명 변경
            df.rename(columns={
                'open': 'Open',
                'high': 'High', 
                'low': 'Low',
                'close': 'Close',
                'volume': 'Volume'
            }, inplace=True)
            
            # 필요한 컬럼만 선택
            df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
            
            logger.info(f"Binance 데이터 수집 완료: {len(df)}개 캔들")
            
            return df
            
        except BinanceAPIException as e:
            logger.error(f"Binance API 오류: {e}")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"데이터 수집 중 오류: {e}")
            return pd.DataFrame()
    
    def get_btc_price_data_for_analysis(
        self, 
        weeks_required: int = 210,  # 200주 + 여유
        fallback_to_daily: bool = True
    ) -> pd.DataFrame:
        """
        200주 이동평균 계산을 위한 BTC 가격 데이터 가져오기
        
        Args:
            weeks_required: 필요한 주 수 (기본: 210주)
            fallback_to_daily: 주간 데이터 부족 시 일간 데이터 사용
            
        Returns:
            BTC 가격 데이터프레임
        """
        try:
            # 먼저 주간 데이터 시도
            logger.info(f"{weeks_required}주 데이터 수집 시도...")
            
            # 주간 데이터 가져오기 (Binance는 최대 1000개 제한)
            weekly_data = self.get_historical_klines(
                symbol="BTCUSDT",
                interval="1w",
                start_date=datetime.now() - timedelta(weeks=weeks_required),
                limit=1000
            )
            
            if len(weekly_data) >= 200:
                logger.info(f"✅ 충분한 주간 데이터 확보: {len(weekly_data)}주")
                return weekly_data
            
            # 주간 데이터가 부족하면 일간 데이터 사용
            if fallback_to_daily:
                logger.info("주간 데이터 부족, 일간 데이터로 대체...")
                
                # 4년치 일간 데이터 가져오기
                daily_data = self.get_historical_klines(
                    symbol="BTCUSDT",
                    interval="1d",
                    start_date=datetime.now() - timedelta(days=365*4),
                    limit=1000
                )
                
                if not daily_data.empty:
                    logger.info(f"✅ 일간 데이터 확보: {len(daily_data)}일")
                    return daily_data
            
            logger.warning("충분한 데이터를 가져오지 못했습니다")
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"BTC 데이터 수집 실패: {e}")
            return pd.DataFrame()
    
    def get_multi_timeframe_data(self, symbol: str = "BTCUSDT") -> Dict[str, pd.DataFrame]:
        """
        멀티 타임프레임 분석을 위한 데이터 수집
        
        Args:
            symbol: 거래 심볼
            
        Returns:
            타임프레임별 데이터 딕셔너리
        """
        try:
            data = {}
            
            # 단기: 30일 일간 데이터
            data['short'] = self.get_historical_klines(
                symbol=symbol,
                interval="1d",
                start_date=datetime.now() - timedelta(days=30),
                limit=30
            )
            
            # 중기: 1년 일간 데이터
            data['medium'] = self.get_historical_klines(
                symbol=symbol,
                interval="1d", 
                start_date=datetime.now() - timedelta(days=365),
                limit=365
            )
            
            # 장기: 4년 주간 데이터
            data['long'] = self.get_historical_klines(
                symbol=symbol,
                interval="1w",
                start_date=datetime.now() - timedelta(weeks=208),
                limit=208
            )
            
            logger.info(f"멀티 타임프레임 데이터 수집 완료: {len(data)}개 타임프레임")
            return data
            
        except Exception as e:
            logger.error(f"멀티 타임프레임 데이터 수집 실패: {e}")
            return {}
    
    def convert_usdt_to_krw(
        self, 
        df: pd.DataFrame, 
        usd_krw_rate: float = 1400.0
    ) -> pd.DataFrame:
        """
        USDT 가격을 KRW로 변환
        
        Args:
            df: USDT 가격 데이터프레임
            usd_krw_rate: USD/KRW 환율
            
        Returns:
            KRW로 변환된 데이터프레임
        """
        try:
            # 가격 컬럼들을 KRW로 변환
            price_columns = ['Open', 'High', 'Low', 'Close']
            
            for col in price_columns:
                if col in df.columns:
                    df[col] = df[col] * usd_krw_rate
            
            logger.debug(f"가격 데이터를 KRW로 변환 (환율: {usd_krw_rate})")
            return df
            
        except Exception as e:
            logger.error(f"KRW 변환 실패: {e}")
            return df


def test_binance_provider():
    """Binance 데이터 제공자 테스트"""
    provider = BinanceDataProvider()
    
    # BTC 데이터 가져오기
    data = provider.get_btc_price_data_for_analysis()
    
    if not data.empty:
        print(f"✅ 데이터 수집 성공")
        print(f"  - 기간: {data.index[0]} ~ {data.index[-1]}")
        print(f"  - 데이터 개수: {len(data)}")
        print(f"  - 현재 가격: ${data['Close'].iloc[-1]:,.2f}")
        
        # KRW 변환 테스트
        krw_data = provider.convert_usdt_to_krw(data, 1400)
        print(f"  - KRW 변환 가격: ₩{krw_data['Close'].iloc[-1]:,.0f}")
    else:
        print("❌ 데이터 수집 실패")


if __name__ == "__main__":
    test_binance_provider()