"""
Market Season Filter

BTC 200주 이동평균선과 ±5% 완충 밴드를 활용한 시장 계절 판단 모듈
"""

from datetime import datetime, timedelta
from typing import Dict, Literal, Optional, Tuple
from enum import Enum
import pandas as pd
import numpy as np
from loguru import logger


class MarketSeason(Enum):
    """시장 계절 정의"""
    RISK_ON = "risk_on"     # 강세장 (암호화폐 70% / KRW 30%)
    RISK_OFF = "risk_off"   # 약세장 (암호화폐 30% / KRW 70%)
    NEUTRAL = "neutral"     # 횡보장 (기존 비중 유지)


class MarketSeasonFilter:
    """
    시장 계절 필터
    
    BTC 가격과 200주 이동평균선의 관계를 분석하여
    시장 상황(강세장/약세장/횡보장)을 판단합니다.
    """
    
    def __init__(self, buffer_band: float = 0.05, db_manager=None):
        """
        Args:
            buffer_band: 완충 밴드 비율 (기본값: 5%)
            db_manager: DatabaseManager 인스턴스 (선택사항)
        """
        self.buffer_band = buffer_band
        self.risk_on_threshold = 1 + buffer_band   # 1.05
        self.risk_off_threshold = 1 - buffer_band  # 0.95
        self.db_manager = db_manager
        
        logger.info(f"MarketSeasonFilter 초기화: buffer_band={buffer_band}")
    
    def calculate_200week_ma(self, price_data: pd.DataFrame) -> float:
        """
        200주 이동평균 계산
        
        Args:
            price_data: BTC 가격 데이터 (DataFrame with 'Close' column)
            
        Returns:
            200주 이동평균값
        """
        try:
            # 데이터 유효성 검증
            if price_data.empty or 'Close' not in price_data.columns:
                logger.warning("가격 데이터가 비어있거나 'Close' 컬럼이 없습니다")
                return 50000000.0  # 5천만원 기본값
            
            # Close 컬럼에서 유효한 데이터만 필터링
            valid_prices = price_data['Close'].dropna()
            if len(valid_prices) == 0:
                logger.warning("유효한 가격 데이터가 없습니다")
                return 50000000.0
            
            # 데이터 길이 체크
            if len(valid_prices) < 200:
                logger.warning(f"데이터 부족: {len(valid_prices)}개 < 200개 필요")
                fallback_ma = valid_prices.mean()
                return fallback_ma if not pd.isna(fallback_ma) else 50000000.0
            
            # 인덱스가 datetime인지 확인
            if not isinstance(price_data.index, pd.DatetimeIndex):
                logger.warning("데이터 인덱스가 datetime이 아닙니다. 단순 이동평균 사용")
                # 단순 200개 이동평균으로 대체
                ma_200 = valid_prices.rolling(window=200).mean().iloc[-1]
                return ma_200 if not pd.isna(ma_200) else valid_prices.mean()
            
            # 주간 데이터로 리샘플링
            try:
                weekly_prices = price_data.resample('W')['Close'].last().dropna()
                if len(weekly_prices) < 200:
                    logger.warning(f"주간 데이터 부족: {len(weekly_prices)}주 < 200주")
                    # 일간 데이터로 200개 이동평균 계산 (대략 200일)
                    ma_200d = valid_prices.rolling(window=200).mean().iloc[-1]
                    return ma_200d if not pd.isna(ma_200d) else valid_prices.mean()
                
                # 200주 이동평균 계산
                ma_200w = weekly_prices.rolling(window=200).mean().iloc[-1]
                
                # 결과 검증
                if pd.isna(ma_200w):
                    logger.warning("200주 이동평균 계산 결과가 NaN입니다. 대체값 사용")
                    # 더 짧은 기간의 이동평균으로 대체
                    ma_50w = weekly_prices.rolling(window=50).mean().iloc[-1]
                    if not pd.isna(ma_50w):
                        return ma_50w
                    else:
                        return valid_prices.mean()
                
                logger.debug(f"200주 이동평균: {ma_200w:.2f}")
                return ma_200w
                
            except Exception as resample_error:
                logger.warning(f"리샘플링 실패: {resample_error}. 단순 이동평균 사용")
                ma_200 = valid_prices.rolling(window=200).mean().iloc[-1]
                return ma_200 if not pd.isna(ma_200) else valid_prices.mean()
                
        except Exception as e:
            logger.error(f"200주 이동평균 계산 중 오류: {e}")
            # 최종 fallback - BTC 대략적 평균가
            return 50000000.0  # 5천만원
    
    def determine_market_season(
        self, 
        current_price: float, 
        ma_200w: float,
        previous_season: Optional[MarketSeason] = None
    ) -> Tuple[MarketSeason, Dict]:
        """
        시장 계절 판단
        
        Args:
            current_price: 현재 BTC 가격
            ma_200w: 200주 이동평균
            previous_season: 이전 시장 계절 (횡보장 판단용)
            
        Returns:
            Tuple[MarketSeason, Dict]: (시장계절, 분석정보)
        """
        # NaN 값 처리
        if pd.isna(current_price) or pd.isna(ma_200w) or ma_200w == 0:
            logger.warning(f"잘못된 데이터: price={current_price}, ma_200w={ma_200w}")
            # 기본값으로 NEUTRAL 반환
            analysis_info = {
                "current_price": current_price,
                "ma_200w": ma_200w,
                "price_ratio": None,
                "risk_on_threshold": self.risk_on_threshold,
                "risk_off_threshold": self.risk_off_threshold,
                "timestamp": datetime.now(),
                "market_season": MarketSeason.NEUTRAL.value,
                "season_changed": False,
                "error": "Invalid price data"
            }
            return MarketSeason.NEUTRAL, analysis_info
        
        price_ratio = current_price / ma_200w
        
        analysis_info = {
            "current_price": current_price,
            "ma_200w": ma_200w,
            "price_ratio": price_ratio,
            "risk_on_threshold": self.risk_on_threshold,
            "risk_off_threshold": self.risk_off_threshold,
            "timestamp": datetime.now()
        }
        
        # 시장 계절 판단 로직
        if price_ratio >= self.risk_on_threshold:
            season = MarketSeason.RISK_ON
            logger.info(f"강세장 신호: {price_ratio:.3f} >= {self.risk_on_threshold}")
            
        elif price_ratio <= self.risk_off_threshold:
            season = MarketSeason.RISK_OFF
            logger.info(f"약세장 신호: {price_ratio:.3f} <= {self.risk_off_threshold}")
            
        else:
            # 완충 밴드 내 - 기존 상태 유지
            season = previous_season if previous_season else MarketSeason.NEUTRAL
            logger.info(f"횡보장 (밴드 내): {price_ratio:.3f}, 기존 상태 유지")
        
        analysis_info["market_season"] = season.value
        analysis_info["season_changed"] = (previous_season != season) if previous_season else True
        
        return season, analysis_info
    
    def get_allocation_weights(self, market_season: MarketSeason) -> Dict[str, float]:
        """
        시장 계절에 따른 자산 배분 비중 반환
        
        Args:
            market_season: 시장 계절
            
        Returns:
            자산 배분 비중 딕셔너리
        """
        allocation_map = {
            MarketSeason.RISK_ON: {
                "crypto": 0.70,  # 암호화폐 70%
                "krw": 0.30      # 원화 30%
            },
            MarketSeason.RISK_OFF: {
                "crypto": 0.30,  # 암호화폐 30%
                "krw": 0.70      # 원화 70%
            },
            MarketSeason.NEUTRAL: {
                "crypto": 0.50,  # 중립 상태: 50:50
                "krw": 0.50
            }
        }
        
        weights = allocation_map[market_season]
        logger.info(f"자산 배분 비중: {weights}")
        
        return weights
    
    def analyze_weekly(self, price_data: pd.DataFrame) -> Dict:
        """
        주간 시장 분석 실행 (고급 분석 결과 통합)
        
        Args:
            price_data: BTC 가격 데이터
            
        Returns:
            분석 결과 딕셔너리
        """
        try:
            # 200주 이동평균 계산
            ma_200w = self.calculate_200week_ma(price_data)
            
            # 현재 가격
            current_price = price_data['Close'].iloc[-1]
            
            # 시장 계절 판단
            season, analysis_info = self.determine_market_season(current_price, ma_200w)
            
            # 자산 배분 비중
            allocation_weights = self.get_allocation_weights(season)
            
            # 고급 분석 결과 통합 (DB에서 조회)
            advanced_analysis = self._integrate_advanced_analysis()
            
            # 고급 분석 결과를 반영한 배분 조정
            if advanced_analysis:
                allocation_weights = self._adjust_allocation_with_analysis(
                    allocation_weights, advanced_analysis
                )
            
            result = {
                "analysis_date": datetime.now(),
                "market_season": season.value,
                "allocation_weights": allocation_weights,
                "analysis_info": analysis_info,
                "advanced_analysis": advanced_analysis,
                "success": True
            }
            
            logger.info(f"주간 분석 완료: {season.value} (고급 분석 통합)")
            return result
            
        except Exception as e:
            logger.error(f"주간 분석 실패: {e}")
            return {
                "analysis_date": datetime.now(),
                "error": str(e),
                "success": False
            }
    
    def _integrate_advanced_analysis(self) -> Optional[Dict]:
        """고급 분석 결과를 DB에서 조회하여 통합"""
        if not self.db_manager:
            return None
        
        try:
            # 모든 고급 분석 결과 조회
            analysis_results = self.db_manager.get_all_latest_analysis_results()
            
            if not analysis_results:
                logger.info("저장된 고급 분석 결과가 없습니다")
                return None
            
            # 분석 결과 요약
            summary = {
                "multi_timeframe": analysis_results.get("multi_timeframe"),
                "macro_economic": analysis_results.get("macro_economic"),
                "onchain_data": analysis_results.get("onchain_data"),
                "scenario_response": analysis_results.get("scenario_response"),
                "behavioral_bias": analysis_results.get("behavioral_bias"),
                "performance_analytics": analysis_results.get("performance_analytics")
            }
            
            # 각 분석 결과를 의사결정에 사용했음을 표시
            for analysis_type, result in summary.items():
                if result:
                    self.db_manager.mark_analysis_as_used(
                        analysis_type, 
                        result.get("analysis_date", datetime.now().isoformat())
                    )
            
            logger.info(f"고급 분석 결과 통합 완료: {len([r for r in summary.values() if r])}개 모듈")
            return summary
            
        except Exception as e:
            logger.error(f"고급 분석 결과 통합 실패: {e}")
            return None
    
    def _adjust_allocation_with_analysis(self, base_allocation: Dict[str, float], 
                                       advanced_analysis: Dict) -> Dict[str, float]:
        """고급 분석 결과를 반영한 자산 배분 조정"""
        try:
            adjusted_allocation = base_allocation.copy()
            
            # 각 분석 모듈의 영향 가중치
            analysis_weights = {
                "multi_timeframe": 0.3,
                "macro_economic": 0.25,
                "onchain_data": 0.15,
                "scenario_response": 0.15,
                "behavioral_bias": 0.1,
                "performance_analytics": 0.05
            }
            
            total_adjustment = 0.0
            
            # 각 분석 결과에서 배분 조정 요소 추출
            for analysis_type, weight in analysis_weights.items():
                analysis_data = advanced_analysis.get(analysis_type)
                if not analysis_data:
                    continue
                
                result_data = analysis_data.get("result_data", {})
                confidence = analysis_data.get("confidence_score", 0.5)
                
                # 분석별 조정 계산
                adjustment = self._calculate_adjustment_by_analysis(
                    analysis_type, result_data, confidence
                )
                
                total_adjustment += adjustment * weight
            
            # 조정값 적용 (최대 ±20% 범위)
            total_adjustment = max(-0.2, min(0.2, total_adjustment))
            
            if abs(total_adjustment) > 0.01:  # 1% 이상 조정시에만 적용
                crypto_ratio = adjusted_allocation["crypto"]
                krw_ratio = adjusted_allocation["krw"]
                
                # 암호화폐 비중 조정
                new_crypto_ratio = crypto_ratio + total_adjustment
                new_crypto_ratio = max(0.2, min(0.8, new_crypto_ratio))  # 20-80% 범위
                
                adjusted_allocation["crypto"] = new_crypto_ratio
                adjusted_allocation["krw"] = 1.0 - new_crypto_ratio
                
                logger.info(f"고급 분석 반영 배분 조정: {crypto_ratio:.1%} → {new_crypto_ratio:.1%} "
                           f"(조정값: {total_adjustment:+.1%})")
            
            return adjusted_allocation
            
        except Exception as e:
            logger.error(f"배분 조정 실패: {e}")
            return base_allocation
    
    def generate_trading_recommendation(self, analysis_result: Dict) -> Dict:
        """고급 분석 결과를 기반으로 매수/매도 권장사항 생성"""
        try:
            recommendation = {
                "action": "HOLD",  # BUY, SELL, HOLD, REBALANCE
                "strength": 0.5,  # 0-1 강도
                "reasons": [],
                "target_allocation": {},
                "immediate_action": False
            }
            
            # 기본 시장 계절 판단
            market_season = analysis_result.get("market_season")
            season_changed = analysis_result.get("season_changed", False)
            
            # 고급 분석 결과
            advanced_analysis = analysis_result.get("advanced_analysis", {})
            
            # 매수/매도 신호 카운터
            buy_signals = 0
            sell_signals = 0
            total_signals = 0
            
            # 1. 멀티 타임프레임 분석
            if advanced_analysis.get("multi_timeframe"):
                mtf = advanced_analysis["multi_timeframe"]
                confidence = mtf.get("confidence_score", 0.5)
                result_data = mtf.get("result_data", {})
                
                if confidence > 0.7:
                    buy_signals += 1
                    recommendation["reasons"].append(f"📈 멀티 타임프레임 분석 강세 신호 (신뢰도: {confidence:.1%})")
                elif confidence < 0.3:
                    sell_signals += 1
                    recommendation["reasons"].append(f"📉 멀티 타임프레임 분석 약세 신호 (신뢰도: {confidence:.1%})")
                total_signals += 1
            
            # 2. 매크로 경제 분석
            if advanced_analysis.get("macro_economic"):
                macro = advanced_analysis["macro_economic"]
                result_data = macro.get("result_data", {})
                indicators = result_data.get("indicators", {})
                
                # VIX가 낮고 DXY가 약하면 매수 신호
                vix = indicators.get("VIX", {}).get("value", 20)
                dxy = indicators.get("DXY", {}).get("value", 100)
                
                if isinstance(vix, (int, float)) and isinstance(dxy, (int, float)):
                    if vix < 20 and dxy < 100:
                        buy_signals += 1
                        recommendation["reasons"].append(f"🌍 위험자산 선호 환경 (VIX: {vix:.1f}, DXY: {dxy:.1f})")
                    elif vix > 30 and dxy > 105:
                        sell_signals += 1
                        recommendation["reasons"].append(f"⚠️ 위험회피 환경 (VIX: {vix:.1f}, DXY: {dxy:.1f})")
                    total_signals += 1
            
            # 3. 온체인 데이터 분석
            if advanced_analysis.get("onchain_data"):
                onchain = advanced_analysis["onchain_data"]
                result_data = onchain.get("result_data", {})
                metrics = result_data.get("metrics", {})
                
                nupl = metrics.get("nupl")
                if nupl:
                    if isinstance(nupl, (int, float)):
                        if nupl < 0.25:  # 매수 기회
                            buy_signals += 1
                            recommendation["reasons"].append(f"🔗 온체인 매수 기회 (NUPL: {nupl:.2f})")
                        elif nupl > 0.75:  # 과열 구간
                            sell_signals += 1
                            recommendation["reasons"].append(f"🔥 온체인 과열 경고 (NUPL: {nupl:.2f})")
                        total_signals += 1
            
            # 4. 행동 편향 분석
            if advanced_analysis.get("behavioral_bias"):
                bias = advanced_analysis["behavioral_bias"]
                result_data = bias.get("result_data", {})
                biases = result_data.get("detected_biases", [])
                
                if len(biases) > 2:  # 여러 편향이 감지되면 경고
                    recommendation["reasons"].append(f"🧠 심리적 편향 경고 ({len(biases)}개 감지) - 신중한 판단 필요")
            
            # 5. 시나리오 대응
            if advanced_analysis.get("scenario_response"):
                scenario = advanced_analysis["scenario_response"]
                result_data = scenario.get("result_data", {})
                active_scenarios = result_data.get("active_scenarios", [])
                
                for s in active_scenarios:
                    if s.get("severity") == "high":
                        sell_signals += 0.5  # 고위험 시나리오는 부분 매도 신호
                        recommendation["reasons"].append(f"🚨 고위험 시나리오 감지: {s.get('name', 'Unknown')}")
            
            # 최종 판단
            if total_signals > 0:
                buy_ratio = buy_signals / max(total_signals, 1)
                sell_ratio = sell_signals / max(total_signals, 1)
                
                if season_changed:
                    recommendation["action"] = "REBALANCE"
                    recommendation["strength"] = 1.0
                    recommendation["immediate_action"] = True
                    recommendation["reasons"].insert(0, "🔄 시장 계절 변화 - 즉시 리밸런싱 필요")
                elif buy_ratio > 0.6:
                    recommendation["action"] = "BUY"
                    recommendation["strength"] = min(buy_ratio, 1.0)
                    if buy_ratio > 0.8:
                        recommendation["immediate_action"] = True
                elif sell_ratio > 0.6:
                    recommendation["action"] = "SELL"
                    recommendation["strength"] = min(sell_ratio, 1.0)
                    if sell_ratio > 0.8:
                        recommendation["immediate_action"] = True
                else:
                    recommendation["action"] = "HOLD"
                    recommendation["strength"] = 0.5
            
            # 목표 배분 설정
            if analysis_result.get("allocation_weights"):
                recommendation["target_allocation"] = analysis_result["allocation_weights"]
            
            # 추가 상세 정보
            recommendation["market_season"] = market_season
            recommendation["signal_summary"] = {
                "buy_signals": buy_signals,
                "sell_signals": sell_signals,
                "total_signals": total_signals
            }
            
            return recommendation
            
        except Exception as e:
            logger.error(f"투자 권장사항 생성 실패: {e}")
            return {
                "action": "HOLD",
                "strength": 0.5,
                "reasons": ["분석 오류 - 현상 유지"],
                "immediate_action": False
            }
    
    def _calculate_adjustment_by_analysis(self, analysis_type: str, 
                                        result_data: Dict, confidence: float) -> float:
        """분석별 배분 조정값 계산"""
        try:
            if analysis_type == "multi_timeframe":
                # 멀티 타임프레임 분석의 전체 신호 활용
                overall_confidence = result_data.get("overall_confidence", 0.5)
                if overall_confidence > 0.7:
                    return 0.1  # 암호화폐 비중 증가
                elif overall_confidence < 0.3:
                    return -0.1  # 암호화폐 비중 감소
                    
            elif analysis_type == "macro_economic":
                # 매크로 경제 분석의 암호화폐 우호도 활용
                crypto_favorability = result_data.get("crypto_favorability", 0.0)
                return crypto_favorability * 0.15 * confidence
                
            elif analysis_type == "scenario_response":
                # 시나리오 대응 시스템의 리스크 평가 활용
                risk_level = result_data.get("risk_level", "medium")
                if risk_level == "high":
                    return -0.1
                elif risk_level == "low":
                    return 0.05
            
            return 0.0
            
        except Exception as e:
            logger.debug(f"{analysis_type} 조정값 계산 실패: {e}")
            return 0.0


# 설정 상수
DEFAULT_BUFFER_BAND = 0.05  # 5% 완충 밴드
ANALYSIS_FREQUENCY = "weekly"  # 주간 분석 