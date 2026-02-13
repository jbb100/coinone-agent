"""
Composite Signal Analyzer

RSI, MACD, 볼린저밴드 복합 신호 분석기
CLAUDE.md 기준 3개 지표 정렬 전략 구현
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd
import numpy as np
from loguru import logger


class SignalStrength(Enum):
    """신호 강도"""
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    NEUTRAL = "NEUTRAL"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"


@dataclass
class CompositeSignalResult:
    """복합 신호 분석 결과"""
    signal: SignalStrength
    confidence: float
    aligned_indicators: int

    # 개별 지표 신호
    rsi_signal: str = "neutral"
    macd_signal: str = "neutral"
    bollinger_signal: str = "neutral"

    # 지표 값
    rsi_value: float = 50.0
    macd_histogram: float = 0.0
    bollinger_position: str = "middle"

    # 메타데이터
    timestamp: datetime = field(default_factory=datetime.now)
    reason: str = ""


class CompositeSignalAnalyzer:
    """
    복합 신호 분석기

    RSI, MACD, 볼린저밴드 3개 지표를 분석하여 복합 신호를 생성합니다.
    3개 지표가 모두 정렬되면 STRONG 신호, 2개 정렬 시 일반 신호입니다.
    """

    def __init__(self, max_history: int = 100):
        """
        Args:
            max_history: 신호 이력 최대 저장 개수
        """
        # RSI 설정 (14일, 30/70 임계값)
        self.rsi_period = 14
        self.rsi_oversold = 30
        self.rsi_overbought = 70

        # MACD 설정 (12-26-9)
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9

        # 볼린저밴드 설정 (20 SMA ± 2 std)
        self.bollinger_period = 20
        self.bollinger_std = 2

        # 신호 이력
        self.signal_history: List[CompositeSignalResult] = []
        self.max_history = max_history

        logger.info("CompositeSignalAnalyzer 초기화 완료")

    def analyze(self, data: pd.DataFrame) -> CompositeSignalResult:
        """
        복합 신호 분석

        Args:
            data: OHLCV 데이터프레임 (Close, High, Low, Volume 컬럼 필요)

        Returns:
            CompositeSignalResult
        """
        try:
            # 데이터 유효성 검사
            if data is None or len(data) < self.macd_slow + self.macd_signal:
                return self._create_neutral_result("데이터 부족")

            # Close 컬럼 추출
            if isinstance(data, pd.DataFrame):
                prices = data['Close'].dropna()
            else:
                prices = data.dropna()

            if len(prices) < self.macd_slow + self.macd_signal:
                return self._create_neutral_result("유효 데이터 부족")

            # 개별 지표 분석
            rsi_signal, rsi_value = self._analyze_rsi(prices)
            macd_signal, macd_data = self._analyze_macd(prices)
            bollinger_signal, bollinger_data = self._analyze_bollinger(prices)

            # 복합 신호 결정
            buy_count = sum(1 for s in [rsi_signal, macd_signal, bollinger_signal] if s == "buy")
            sell_count = sum(1 for s in [rsi_signal, macd_signal, bollinger_signal] if s == "sell")

            # 신호 강도 및 신뢰도 결정
            if buy_count == 3:
                signal = SignalStrength.STRONG_BUY
                confidence = 0.85
                aligned = 3
            elif sell_count == 3:
                signal = SignalStrength.STRONG_SELL
                confidence = 0.85
                aligned = 3
            elif buy_count == 2 and sell_count == 0:
                signal = SignalStrength.BUY
                confidence = 0.65
                aligned = 2
            elif sell_count == 2 and buy_count == 0:
                signal = SignalStrength.SELL
                confidence = 0.65
                aligned = 2
            elif buy_count > sell_count:
                signal = SignalStrength.BUY
                confidence = 0.55
                aligned = buy_count
            elif sell_count > buy_count:
                signal = SignalStrength.SELL
                confidence = 0.55
                aligned = sell_count
            else:
                signal = SignalStrength.NEUTRAL
                confidence = 0.40
                aligned = 0

            result = CompositeSignalResult(
                signal=signal,
                confidence=confidence,
                aligned_indicators=aligned,
                rsi_signal=rsi_signal,
                macd_signal=macd_signal,
                bollinger_signal=bollinger_signal,
                rsi_value=rsi_value,
                macd_histogram=macd_data.get("histogram", 0),
                bollinger_position=bollinger_data.get("position", "middle"),
                reason=f"RSI:{rsi_signal}, MACD:{macd_signal}, BB:{bollinger_signal}"
            )

            # 이력 저장
            self._add_to_history(result)

            logger.debug(f"복합 신호 분석 완료: {signal.value}, 신뢰도: {confidence:.2%}")
            return result

        except Exception as e:
            logger.error(f"복합 신호 분석 실패: {e}")
            return self._create_neutral_result(f"분석 오류: {str(e)}")

    def _analyze_rsi(self, prices: pd.Series) -> Tuple[str, float]:
        """
        RSI 분석

        Args:
            prices: 가격 시리즈

        Returns:
            (신호, RSI 값) 튜플
        """
        try:
            if len(prices) < self.rsi_period + 1:
                return "neutral", 50.0

            # RSI 계산
            delta = prices.diff()
            gain = delta.where(delta > 0, 0.0)
            loss = (-delta).where(delta < 0, 0.0)

            avg_gain = gain.rolling(window=self.rsi_period, min_periods=1).mean()
            avg_loss = loss.rolling(window=self.rsi_period, min_periods=1).mean()

            rs = avg_gain / avg_loss.replace(0, np.inf)
            rsi = 100 - (100 / (1 + rs))

            current_rsi = rsi.iloc[-1]

            # 신호 결정
            if np.isnan(current_rsi):
                return "neutral", 50.0
            elif current_rsi < self.rsi_oversold:
                return "buy", current_rsi
            elif current_rsi > self.rsi_overbought:
                return "sell", current_rsi
            else:
                return "neutral", current_rsi

        except Exception as e:
            logger.warning(f"RSI 분석 오류: {e}")
            return "neutral", 50.0

    def _analyze_macd(self, prices: pd.Series) -> Tuple[str, Dict]:
        """
        MACD 분석

        Args:
            prices: 가격 시리즈

        Returns:
            (신호, MACD 데이터) 튜플
        """
        try:
            if len(prices) < self.macd_slow + self.macd_signal:
                return "neutral", {"macd_line": 0, "signal_line": 0, "histogram": 0}

            # MACD 계산
            ema_fast = prices.ewm(span=self.macd_fast, adjust=False).mean()
            ema_slow = prices.ewm(span=self.macd_slow, adjust=False).mean()
            macd_line = ema_fast - ema_slow
            signal_line = macd_line.ewm(span=self.macd_signal, adjust=False).mean()
            histogram = macd_line - signal_line

            current_macd = macd_line.iloc[-1]
            current_signal = signal_line.iloc[-1]
            current_histogram = histogram.iloc[-1]
            prev_histogram = histogram.iloc[-2] if len(histogram) > 1 else 0

            data = {
                "macd_line": current_macd,
                "signal_line": current_signal,
                "histogram": current_histogram
            }

            # 신호 결정 (골든크로스/데드크로스)
            if np.isnan(current_macd) or np.isnan(current_signal):
                return "neutral", data

            # 히스토그램 부호 전환 확인
            if prev_histogram <= 0 < current_histogram:
                # 골든크로스 (MACD가 시그널을 상향 돌파)
                return "buy", data
            elif prev_histogram >= 0 > current_histogram:
                # 데드크로스 (MACD가 시그널을 하향 돌파)
                return "sell", data
            elif current_histogram > 0:
                return "buy", data
            elif current_histogram < 0:
                return "sell", data
            else:
                return "neutral", data

        except Exception as e:
            logger.warning(f"MACD 분석 오류: {e}")
            return "neutral", {"macd_line": 0, "signal_line": 0, "histogram": 0}

    def _analyze_bollinger(self, prices: pd.Series) -> Tuple[str, Dict]:
        """
        볼린저밴드 분석

        Args:
            prices: 가격 시리즈

        Returns:
            (신호, 볼린저 데이터) 튜플
        """
        try:
            if len(prices) < self.bollinger_period:
                return "neutral", {"position": "middle", "upper": 0, "middle": 0, "lower": 0}

            # 볼린저밴드 계산
            sma = prices.rolling(window=self.bollinger_period).mean()
            std = prices.rolling(window=self.bollinger_period).std()

            upper_band = sma + (self.bollinger_std * std)
            lower_band = sma - (self.bollinger_std * std)

            current_price = prices.iloc[-1]
            current_upper = upper_band.iloc[-1]
            current_lower = lower_band.iloc[-1]
            current_middle = sma.iloc[-1]

            data = {
                "upper": current_upper,
                "middle": current_middle,
                "lower": current_lower
            }

            # 신호 결정
            if np.isnan(current_upper) or np.isnan(current_lower):
                data["position"] = "middle"
                return "neutral", data

            # 밴드 범위
            band_range = current_upper - current_lower

            if band_range == 0:
                data["position"] = "middle"
                return "neutral", data

            # 밴드 내 위치 계산 (0~1)
            position_ratio = (current_price - current_lower) / band_range

            if current_price <= current_lower or position_ratio < 0.1:
                data["position"] = "lower"
                return "buy", data
            elif current_price >= current_upper or position_ratio > 0.9:
                data["position"] = "upper"
                return "sell", data
            else:
                data["position"] = "middle"
                return "neutral", data

        except Exception as e:
            logger.warning(f"볼린저밴드 분석 오류: {e}")
            return "neutral", {"position": "middle", "upper": 0, "middle": 0, "lower": 0}

    def _create_neutral_result(self, reason: str) -> CompositeSignalResult:
        """중립 결과 생성"""
        result = CompositeSignalResult(
            signal=SignalStrength.NEUTRAL,
            confidence=0.30,
            aligned_indicators=0,
            reason=reason
        )
        self._add_to_history(result)
        return result

    def _add_to_history(self, result: CompositeSignalResult):
        """신호 이력에 추가"""
        self.signal_history.append(result)
        if len(self.signal_history) > self.max_history:
            self.signal_history = self.signal_history[-self.max_history:]

    def get_last_signal(self) -> Optional[CompositeSignalResult]:
        """마지막 신호 반환"""
        if self.signal_history:
            return self.signal_history[-1]
        return None

    def get_signal_summary(self) -> Dict:
        """신호 이력 요약"""
        if not self.signal_history:
            return {"total": 0, "buy": 0, "sell": 0, "neutral": 0}

        buy_count = sum(1 for s in self.signal_history
                       if s.signal in [SignalStrength.BUY, SignalStrength.STRONG_BUY])
        sell_count = sum(1 for s in self.signal_history
                        if s.signal in [SignalStrength.SELL, SignalStrength.STRONG_SELL])
        neutral_count = sum(1 for s in self.signal_history
                          if s.signal == SignalStrength.NEUTRAL)

        return {
            "total": len(self.signal_history),
            "buy": buy_count,
            "sell": sell_count,
            "neutral": neutral_count
        }
