"""
Market Data Provider

실제 시장 데이터를 수집하고 200주 이동평균을 계산하는 모듈
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from loguru import logger
from .constants import MA_CALCULATION_FALLBACK_RATIO
from .binance_data_provider import BinanceDataProvider


class MarketDataProvider:
    """
    시장 데이터 제공자
    
    외부 API를 통해 가격 데이터를 수집하고 기술적 분석 지표를 계산합니다.
    """
    
    def __init__(self, db_manager=None):
        """
        Args:
            db_manager: 데이터베이스 매니저 (캐싱용)
        """
        self.db_manager = db_manager
        logger.info("MarketDataProvider 초기화 완료")
    
    def get_btc_200w_ma(self, fallback_to_current_price: bool = True) -> Tuple[float, str]:
        """
        BTC 200주 이동평균 계산
        
        Args:
            fallback_to_current_price: 실패 시 현재가 기반 fallback 사용 여부
            
        Returns:
            Tuple[200주 이동평균, 데이터 소스]
        """
        try:
            # 1. 캐시된 데이터 확인 (데이터베이스)
            if self.db_manager:
                cached_ma = self._get_cached_200w_ma()
                if cached_ma:
                    logger.info(f"캐시된 200주 이동평균 사용: {cached_ma:.2f}")
                    return cached_ma, "cache"
            
            # 2. Binance에서 실시간 계산
            try:
                ma_200w = self._calculate_200w_ma_from_binance()
                if ma_200w and ma_200w > 0:
                    # 계산된 값 캐싱
                    if self.db_manager:
                        self._cache_200w_ma(ma_200w)
                    logger.info(f"Binance에서 200주 이동평균 계산: {ma_200w:.2f}")
                    return ma_200w, "binance"
            except Exception as e:
                logger.warning(f"Binance 200주 이동평균 계산 실패: {e}")
            
            # 3. 다른 외부 API 시도 (향후 확장)
            # 예: CoinGecko, Binance 등
            
            # 4. Fallback: 현재가 기반 추정
            if fallback_to_current_price:
                current_price = self._get_current_btc_price()
                if current_price and current_price > 0:
                    fallback_ma = current_price * MA_CALCULATION_FALLBACK_RATIO
                    logger.warning(f"Fallback 200주 이동평균 사용: {fallback_ma:.2f} (현재가 {current_price:.2f} × {MA_CALCULATION_FALLBACK_RATIO})")
                    return fallback_ma, "fallback"
            
            raise Exception("모든 200주 이동평균 계산 방법 실패")
            
        except Exception as e:
            logger.error(f"BTC 200주 이동평균 조회 실패: {e}")
            if fallback_to_current_price:
                # 최종 fallback
                estimated_ma = 50000.0 * MA_CALCULATION_FALLBACK_RATIO  # 예상 평균 가격
                logger.error(f"최종 fallback 사용: {estimated_ma:.2f}")
                return estimated_ma, "emergency_fallback"
            else:
                raise
    
    def _calculate_200w_ma_from_binance(self) -> Optional[float]:
        """
        Binance를 사용하여 200주 이동평균 계산
        
        Returns:
            200주 이동평균 또는 None
        """
        try:
            logger.info("Binance를 통한 BTC 200주 이동평균 계산 시작")
            
            # Binance 데이터 제공자 인스턴스 생성
            provider = BinanceDataProvider()
            
            # BTC 200주 데이터 가져오기
            hist = provider.get_btc_price_data_for_analysis(weeks_required=210)
            
            if hist.empty:
                logger.error("Binance에서 BTC 데이터를 가져올 수 없습니다")
                return None
            
            logger.info(f"Binance에서 {len(hist)}개의 BTC 데이터 수집")
            
            # KRW 변환
            try:
                import yaml
                with open('config/config.yaml', 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                usd_krw_rate = config.get('market_data', {}).get('usd_krw_rate', 1400.0)
            except Exception:
                usd_krw_rate = 1400.0
            
            hist = provider.convert_usdt_to_krw(hist, usd_krw_rate)
            
            # 200주 이동평균 계산 (일간 데이터인 경우 200*7=1400일 이동평균)
            if len(hist) >= 1400:  # 200주 * 7일
                ma_200w = hist['Close'].rolling(window=1400).mean().iloc[-1]
                logger.info(f"정확한 200주 이동평균 계산 (1400일): {ma_200w:.2f}")
            elif len(hist) >= 200:  # 주간 데이터인 경우
                ma_200w = hist['Close'].rolling(window=200).mean().iloc[-1]
                logger.info(f"200주 이동평균 계산: {ma_200w:.2f}")
            else:
                logger.warning(f"데이터가 부족합니다. 필요: 200주, 보유: {len(hist)}개")
                # 보유한 데이터로 최대한 계산
                ma_period = min(len(hist), 200)
                ma_200w = hist['Close'].rolling(window=ma_period).mean().iloc[-1]
                logger.info(f"{ma_period}개 이동평균으로 계산: {ma_200w:.2f}")
            
            # 유효성 검증
            current_price = hist['Close'].iloc[-1]
            if ma_200w <= 0 or ma_200w > current_price * 2:  # 현재가의 2배를 넘으면 비정상
                logger.error(f"계산된 200주 이동평균이 비정상적입니다: {ma_200w:.2f} (현재가: {current_price:.2f})")
                return None
            
            return float(ma_200w)
            
        except Exception as e:
            logger.error(f"Binance 200주 이동평균 계산 실패: {e}")
            return None
    
    def _get_current_btc_price(self) -> Optional[float]:
        """
        현재 BTC 가격 조회 (Binance 사용)
        
        Returns:
            현재 BTC 가격 (KRW) 또는 None
        """
        try:
            # Binance 데이터 제공자 사용
            provider = BinanceDataProvider()
            
            # 최근 1일 데이터 가져오기
            hist = provider.get_historical_klines(
                symbol="BTCUSDT",
                interval="1h",
                start_date=datetime.now() - timedelta(hours=24),
                limit=1
            )
            
            if not hist.empty:
                # KRW 변환
                try:
                    import yaml
                    with open('config/config.yaml', 'r', encoding='utf-8') as f:
                        config = yaml.safe_load(f)
                    usd_krw_rate = config.get('market_data', {}).get('usd_krw_rate', 1400.0)
                except:
                    usd_krw_rate = 1400.0
                
                hist = provider.convert_usdt_to_krw(hist, usd_krw_rate)
                return float(hist['Close'].iloc[-1])
            
            return None
            
        except Exception as e:
            logger.warning(f"현재 BTC 가격 조회 실패: {e}")
            return None
    
    def _get_cached_200w_ma(self) -> Optional[float]:
        """
        캐시된 200주 이동평균 조회
        
        Returns:
            캐시된 200주 이동평균 또는 None
        """
        try:
            if not self.db_manager:
                return None
            
            # 최근 24시간 이내의 캐시된 데이터 조회
            cutoff_time = datetime.now() - timedelta(hours=24)
            
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT ma_200w, calculated_at 
                    FROM market_indicators 
                    WHERE symbol = 'BTC' 
                      AND calculated_at > ? 
                    ORDER BY calculated_at DESC 
                    LIMIT 1
                """, (cutoff_time.isoformat(),))
                
                row = cursor.fetchone()
                if row:
                    logger.info(f"캐시된 200주 이동평균 발견: {row['ma_200w']:.2f} ({row['calculated_at']})")
                    return float(row['ma_200w'])
            
            return None
            
        except Exception as e:
            logger.warning(f"캐시된 200주 이동평균 조회 실패: {e}")
            return None
    
    def _cache_200w_ma(self, ma_value: float):
        """
        200주 이동평균을 캐시에 저장
        
        Args:
            ma_value: 200주 이동평균 값
        """
        try:
            if not self.db_manager:
                return
            
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # 테이블이 없으면 생성
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS market_indicators (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        ma_200w REAL,
                        calculated_at TEXT NOT NULL,
                        data_source TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 새 값 삽입
                cursor.execute("""
                    INSERT INTO market_indicators (symbol, ma_200w, calculated_at, data_source)
                    VALUES (?, ?, ?, ?)
                """, ("BTC", ma_value, datetime.now().isoformat(), "binance"))
                
                # 오래된 캐시 데이터 정리 (30일 이상)
                old_cutoff = datetime.now() - timedelta(days=30)
                cursor.execute("""
                    DELETE FROM market_indicators 
                    WHERE calculated_at < ?
                """, (old_cutoff.isoformat(),))
                
                conn.commit()
                logger.info(f"200주 이동평균 캐시 저장: {ma_value:.2f}")
            
        except Exception as e:
            logger.warning(f"200주 이동평균 캐시 저장 실패: {e}")
    
    def get_market_volatility(self, days: int = 30) -> Dict[str, float]:
        """
        시장 변동성 계산
        
        Args:
            days: 계산 기간 (일)
            
        Returns:
            변동성 지표 딕셔너리
        """
        try:
            # Binance 데이터 제공자 사용
            provider = BinanceDataProvider()
            
            # 히스토리컬 데이터 가져오기
            start_date = datetime.now() - timedelta(days=days)
            hist = provider.get_historical_klines(
                symbol="BTCUSDT",
                interval="1d",
                start_date=start_date,
                limit=days
            )
            
            if hist.empty or len(hist) < 2:
                return {"volatility": 0.0, "avg_volume": 0.0}
            
            # KRW 변환
            try:
                import yaml
                with open('config/config.yaml', 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                usd_krw_rate = config.get('market_data', {}).get('usd_krw_rate', 1400.0)
            except Exception:
                usd_krw_rate = 1400.0
            
            hist = provider.convert_usdt_to_krw(hist, usd_krw_rate)
            
            # 일일 수익률 계산
            returns = hist['Close'].pct_change().dropna()
            
            # 변동성 계산 (표준편차)
            volatility = returns.std()
            
            # 평균 거래량
            avg_volume = hist['Volume'].mean()
            
            return {
                "volatility": float(volatility),
                "avg_volume": float(avg_volume),
                "period_days": days,
                "data_points": len(hist)
            }
            
        except Exception as e:
            logger.error(f"시장 변동성 계산 실패: {e}")
            return {"volatility": 0.0, "avg_volume": 0.0}