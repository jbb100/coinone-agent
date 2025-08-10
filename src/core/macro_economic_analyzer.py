"""
Macro Economic Analyzer

매크로 경제 지표를 분석하여 암호화폐 투자 전략에 반영
- 연준 기준금리, 인플레이션율, 달러 지수 등
- 통화 공급량 (M2) 변화 추적
- 매크로 기반 리스크 조정
- 경제 사이클 분석
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import numpy as np
import requests
from loguru import logger


class EconomicRegime(Enum):
    """경제 체제"""
    EXPANSION = "expansion"        # 확장
    CONTRACTION = "contraction"    # 수축
    RECOVERY = "recovery"          # 회복
    PEAK = "peak"                 # 정점


class InflationRegime(Enum):
    """인플레이션 체제"""
    DEFLATIONARY = "deflationary"  # 디플레이션 (<0%)
    LOW = "low"                    # 저인플레이션 (0-2%)
    MODERATE = "moderate"          # 적정 인플레이션 (2-4%)
    HIGH = "high"                  # 고인플레이션 (4-6%)
    HYPERINFLATION = "hyperinflation"  # 초인플레이션 (>6%)


class RateEnvironment(Enum):
    """금리 환경"""
    ULTRA_LOW = "ultra_low"        # 초저금리 (0-1%)
    LOW = "low"                    # 저금리 (1-3%)
    MODERATE = "moderate"          # 중금리 (3-5%)
    HIGH = "high"                  # 고금리 (5-7%)
    VERY_HIGH = "very_high"        # 초고금리 (>7%)


@dataclass
class MacroIndicators:
    """매크로 경제 지표"""
    fed_funds_rate: float          # 연준 기준금리 (%)
    inflation_rate: float          # 인플레이션율 (%)
    dxy_index: float              # 달러 지수
    m2_money_supply: float        # M2 통화공급량 (전년대비 증가율)
    unemployment_rate: float       # 실업률 (%)
    gdp_growth: float             # GDP 성장률 (%)
    vix_index: float              # 공포지수
    gold_price: float             # 금 가격 (USD/oz)
    oil_price: float              # 원유 가격 (USD/barrel)
    bond_yield_10y: float         # 10년 국채 수익률 (%)
    last_updated: datetime


@dataclass
class MacroAnalysis:
    """매크로 분석 결과"""
    economic_regime: EconomicRegime
    inflation_regime: InflationRegime
    rate_environment: RateEnvironment
    crypto_favorability: float    # 암호화폐 우호도 (-1 to 1)
    risk_adjustment: float        # 리스크 조정 (-0.3 to 0.3)
    recommended_allocation: Dict[str, float]
    key_drivers: List[str]
    analysis_confidence: float
    created_at: datetime


class MacroEconomicAnalyzer:
    """
    매크로 경제 분석기
    
    거시경제 지표를 종합 분석하여 암호화폐 투자 전략을 조정합니다.
    """
    
    def __init__(self, api_keys: Optional[Dict[str, str]] = None):
        """
        Args:
            api_keys: 외부 API 키 딕셔너리
        """
        self.api_keys = api_keys or {}
        
        # 기본 데이터 소스 설정
        self.data_sources = {
            "fred": "https://api.stlouisfed.org/fred/series/observations",  # FRED API
            "yahoo": "https://query1.finance.yahoo.com/v8/finance/chart",  # Yahoo Finance
            "alpha_vantage": "https://www.alphavantage.co/query"           # Alpha Vantage
        }
        
        # 매크로 지표별 암호화폐 영향도 가중치
        self.impact_weights = {
            "fed_rate": -0.3,           # 금리 상승 = 암호화폐 부정적
            "inflation": 0.2,           # 인플레이션 상승 = 헤지 수요 증가
            "dxy": -0.25,              # 달러 강세 = 암호화폐 부정적
            "m2_supply": 0.35,         # 통화 공급량 증가 = 암호화폐 긍정적
            "vix": -0.15,              # 공포 지수 상승 = 리스크 자산 회피
            "gold": 0.1,               # 금 가격과 약한 상관관계
            "bond_yield": -0.2         # 채권 수익률 상승 = 경쟁 자산 매력도 증가
        }
        
        logger.info("Macro Economic Analyzer 초기화 완료")
    
    def get_current_indicators(self) -> MacroIndicators:
        """현재 매크로 경제 지표 수집"""
        try:
            logger.info("매크로 경제 지표 수집 시작")
            
            # 실제 환경에서는 각 API에서 데이터 수집
            # 여기서는 예시 데이터 사용 (실제 구현 시 API 연동 필요)
            indicators = MacroIndicators(
                fed_funds_rate=self._get_fed_funds_rate(),
                inflation_rate=self._get_inflation_rate(),
                dxy_index=self._get_dxy_index(),
                m2_money_supply=self._get_m2_growth(),
                unemployment_rate=self._get_unemployment_rate(),
                gdp_growth=self._get_gdp_growth(),
                vix_index=self._get_vix_index(),
                gold_price=self._get_gold_price(),
                oil_price=self._get_oil_price(),
                bond_yield_10y=self._get_bond_yield(),
                last_updated=datetime.now()
            )
            
            logger.info(f"매크로 지표 수집 완료: 기준금리 {indicators.fed_funds_rate:.2f}%, "
                       f"인플레이션 {indicators.inflation_rate:.2f}%")
            
            return indicators
            
        except Exception as e:
            logger.error(f"매크로 지표 수집 실패: {e}")
            return self._get_fallback_indicators()
    
    def analyze_macro_environment(self, indicators: MacroIndicators) -> MacroAnalysis:
        """매크로 환경 종합 분석"""
        try:
            logger.info("매크로 환경 분석 시작")
            
            # 경제 체제 판단
            economic_regime = self._determine_economic_regime(indicators)
            
            # 인플레이션 체제 판단
            inflation_regime = self._determine_inflation_regime(indicators.inflation_rate)
            
            # 금리 환경 판단
            rate_environment = self._determine_rate_environment(indicators.fed_funds_rate)
            
            # 암호화폐 우호도 계산
            crypto_favorability = self._calculate_crypto_favorability(indicators)
            
            # 리스크 조정 계산
            risk_adjustment = self._calculate_risk_adjustment(indicators, economic_regime)
            
            # 권장 자산 배분 계산
            recommended_allocation = self._calculate_macro_allocation(
                indicators, crypto_favorability, risk_adjustment
            )
            
            # 주요 동인 식별
            key_drivers = self._identify_key_drivers(indicators)
            
            # 분석 신뢰도 계산
            confidence = self._calculate_analysis_confidence(indicators)
            
            analysis = MacroAnalysis(
                economic_regime=economic_regime,
                inflation_regime=inflation_regime,
                rate_environment=rate_environment,
                crypto_favorability=crypto_favorability,
                risk_adjustment=risk_adjustment,
                recommended_allocation=recommended_allocation,
                key_drivers=key_drivers,
                analysis_confidence=confidence,
                created_at=datetime.now()
            )
            
            logger.info(f"매크로 분석 완료: {economic_regime.value} 체제, "
                       f"암호화폐 우호도 {crypto_favorability:.2f}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"매크로 환경 분석 실패: {e}")
            return self._get_fallback_analysis()
    
    def _determine_economic_regime(self, indicators: MacroIndicators) -> EconomicRegime:
        """경제 체제 판단"""
        
        # GDP 성장률과 실업률을 주요 지표로 사용
        gdp = indicators.gdp_growth
        unemployment = indicators.unemployment_rate
        
        # 경제 상황 점수 계산
        expansion_score = 0
        if gdp > 2.0:  # 강한 성장
            expansion_score += 2
        elif gdp > 0:   # 약한 성장
            expansion_score += 1
        else:          # 마이너스 성장
            expansion_score -= 2
        
        if unemployment < 4.0:  # 낮은 실업률
            expansion_score += 1
        elif unemployment > 6.0:  # 높은 실업률
            expansion_score -= 1
        
        # VIX 지수 고려 (불확실성)
        if indicators.vix_index > 30:  # 높은 불확실성
            expansion_score -= 1
        
        # 체제 결정
        if expansion_score >= 2:
            return EconomicRegime.EXPANSION
        elif expansion_score <= -2:
            return EconomicRegime.CONTRACTION
        elif gdp < 0 and indicators.vix_index > 25:
            return EconomicRegime.PEAK
        else:
            return EconomicRegime.RECOVERY
    
    def _determine_inflation_regime(self, inflation_rate: float) -> InflationRegime:
        """인플레이션 체제 판단"""
        
        if inflation_rate < 0:
            return InflationRegime.DEFLATIONARY
        elif inflation_rate < 2.0:
            return InflationRegime.LOW
        elif inflation_rate < 4.0:
            return InflationRegime.MODERATE
        elif inflation_rate < 6.0:
            return InflationRegime.HIGH
        else:
            return InflationRegime.HYPERINFLATION
    
    def _determine_rate_environment(self, fed_rate: float) -> RateEnvironment:
        """금리 환경 판단"""
        
        if fed_rate < 1.0:
            return RateEnvironment.ULTRA_LOW
        elif fed_rate < 3.0:
            return RateEnvironment.LOW
        elif fed_rate < 5.0:
            return RateEnvironment.MODERATE
        elif fed_rate < 7.0:
            return RateEnvironment.HIGH
        else:
            return RateEnvironment.VERY_HIGH
    
    def _calculate_crypto_favorability(self, indicators: MacroIndicators) -> float:
        """암호화폐 우호도 계산"""
        
        favorability = 0.0
        
        # 각 지표의 기여도 계산
        contributions = {
            "fed_rate": self._normalize_indicator(indicators.fed_funds_rate, 0, 10) * self.impact_weights["fed_rate"],
            "inflation": self._normalize_indicator(indicators.inflation_rate, 0, 8) * self.impact_weights["inflation"],
            "dxy": self._normalize_indicator(indicators.dxy_index, 80, 120) * self.impact_weights["dxy"],
            "m2_supply": self._normalize_indicator(indicators.m2_money_supply, -5, 20) * self.impact_weights["m2_supply"],
            "vix": self._normalize_indicator(indicators.vix_index, 10, 50) * self.impact_weights["vix"],
            "bond_yield": self._normalize_indicator(indicators.bond_yield_10y, 0, 8) * self.impact_weights["bond_yield"]
        }
        
        # 가중 합계
        favorability = sum(contributions.values())
        
        # -1 ~ 1 범위로 제한
        favorability = max(-1.0, min(1.0, favorability))
        
        logger.debug(f"암호화폐 우호도 계산: {favorability:.3f}")
        logger.debug(f"기여도: {contributions}")
        
        return favorability
    
    def _normalize_indicator(self, value: float, min_val: float, max_val: float) -> float:
        """지표 정규화 (0-1 범위)"""
        return (value - min_val) / (max_val - min_val) if max_val != min_val else 0.5
    
    def _calculate_risk_adjustment(
        self, 
        indicators: MacroIndicators, 
        regime: EconomicRegime
    ) -> float:
        """리스크 조정 계산"""
        
        base_adjustment = 0.0
        
        # 경제 체제별 기본 조정
        regime_adjustments = {
            EconomicRegime.EXPANSION: 0.1,    # 리스크 온
            EconomicRegime.RECOVERY: 0.05,   # 약간 리스크 온
            EconomicRegime.PEAK: -0.1,       # 리스크 오프
            EconomicRegime.CONTRACTION: -0.2  # 강한 리스크 오프
        }
        
        base_adjustment += regime_adjustments[regime]
        
        # VIX 기반 조정
        if indicators.vix_index > 30:
            base_adjustment -= 0.15  # 높은 불확실성
        elif indicators.vix_index < 15:
            base_adjustment += 0.05  # 낮은 불확실성
        
        # 금리 급변동 고려
        if indicators.fed_funds_rate > 5.0:
            base_adjustment -= 0.1  # 고금리 환경
        
        # 달러 지수 고려
        if indicators.dxy_index > 110:
            base_adjustment -= 0.05  # 강달러
        
        return max(-0.3, min(0.3, base_adjustment))
    
    def _calculate_macro_allocation(
        self,
        indicators: MacroIndicators,
        crypto_favorability: float,
        risk_adjustment: float
    ) -> Dict[str, float]:
        """매크로 기반 자산 배분 계산"""
        
        # 기본 배분 (중립 상태)
        base_crypto = 0.50
        base_krw = 0.50
        
        # 암호화폐 우호도에 따른 조정
        crypto_adjustment = crypto_favorability * 0.2  # 최대 ±20%
        
        # 리스크 조정에 따른 추가 조정  
        risk_crypto_adjustment = risk_adjustment * 0.15  # 최대 ±15%
        
        # 최종 배분 계산
        final_crypto = base_crypto + crypto_adjustment + risk_crypto_adjustment
        final_crypto = max(0.2, min(0.8, final_crypto))  # 20-80% 범위 제한
        final_krw = 1.0 - final_crypto
        
        return {
            "crypto": final_crypto,
            "krw": final_krw,
            "adjustments": {
                "base_crypto": base_crypto,
                "favorability_adj": crypto_adjustment,
                "risk_adj": risk_crypto_adjustment,
                "final_crypto": final_crypto
            }
        }
    
    def _identify_key_drivers(self, indicators: MacroIndicators) -> List[str]:
        """주요 동인 식별"""
        
        drivers = []
        
        # 금리
        if indicators.fed_funds_rate > 5.0:
            drivers.append("고금리 환경 (리스크 자산 압박)")
        elif indicators.fed_funds_rate < 1.0:
            drivers.append("초저금리 환경 (유동성 풍부)")
        
        # 인플레이션
        if indicators.inflation_rate > 4.0:
            drivers.append("고인플레이션 (인플레이션 헤지 수요)")
        elif indicators.inflation_rate < 1.0:
            drivers.append("저인플레이션 (디플레이션 위험)")
        
        # 달러 지수
        if indicators.dxy_index > 110:
            drivers.append("강달러 (대안 자산 약세)")
        elif indicators.dxy_index < 90:
            drivers.append("약달러 (대안 자산 강세)")
        
        # 통화 공급량
        if indicators.m2_money_supply > 10:
            drivers.append("통화 공급량 급증 (유동성 확대)")
        elif indicators.m2_money_supply < 0:
            drivers.append("통화 공급량 축소 (유동성 긴축)")
        
        # VIX
        if indicators.vix_index > 30:
            drivers.append("높은 시장 불확실성")
        
        return drivers[:3]  # 상위 3개만
    
    def _calculate_analysis_confidence(self, indicators: MacroIndicators) -> float:
        """분석 신뢰도 계산"""
        
        confidence = 0.8  # 기본 신뢰도
        
        # 데이터 최신성 고려
        data_age = (datetime.now() - indicators.last_updated).total_seconds() / 3600  # 시간
        if data_age > 24:  # 24시간 이상
            confidence -= 0.2
        elif data_age > 168:  # 1주 이상
            confidence -= 0.4
        
        # 극단적 값들이 많을수록 불확실성 증가
        extreme_count = 0
        if indicators.vix_index > 40:
            extreme_count += 1
        if indicators.fed_funds_rate > 7 or indicators.fed_funds_rate < 0.5:
            extreme_count += 1
        if indicators.inflation_rate > 6 or indicators.inflation_rate < -1:
            extreme_count += 1
        
        confidence -= extreme_count * 0.1
        
        return max(0.3, min(1.0, confidence))
    
    # 실제 데이터 수집 메서드들 (예시)
    def _get_fed_funds_rate(self) -> float:
        """연준 기준금리 조회"""
        try:
            # 실제로는 FRED API 호출
            # return self._call_fred_api("FEDFUNDS")
            return 5.25  # 예시 데이터
        except:
            return 5.0
    
    def _get_inflation_rate(self) -> float:
        """인플레이션율 조회"""
        try:
            # 실제로는 FRED API 호출 (CPI)
            # return self._call_fred_api("CPIAUCSL")
            return 3.2  # 예시 데이터
        except:
            return 3.0
    
    def _get_dxy_index(self) -> float:
        """달러 지수 조회"""
        try:
            # 실제로는 Yahoo Finance API 호출
            return 104.5  # 예시 데이터
        except:
            return 100.0
    
    def _get_m2_growth(self) -> float:
        """M2 통화공급량 증가율 조회"""
        try:
            # 실제로는 FRED API 호출
            return 8.5  # 예시 데이터
        except:
            return 5.0
    
    def _get_unemployment_rate(self) -> float:
        """실업률 조회"""
        try:
            return 3.8  # 예시 데이터
        except:
            return 4.0
    
    def _get_gdp_growth(self) -> float:
        """GDP 성장률 조회"""
        try:
            return 2.1  # 예시 데이터
        except:
            return 2.0
    
    def _get_vix_index(self) -> float:
        """VIX 지수 조회"""
        try:
            return 18.5  # 예시 데이터
        except:
            return 20.0
    
    def _get_gold_price(self) -> float:
        """금 가격 조회"""
        try:
            return 2050.0  # 예시 데이터
        except:
            return 2000.0
    
    def _get_oil_price(self) -> float:
        """원유 가격 조회"""
        try:
            return 75.0  # 예시 데이터
        except:
            return 80.0
    
    def _get_bond_yield(self) -> float:
        """10년 국채 수익률 조회"""
        try:
            return 4.2  # 예시 데이터
        except:
            return 4.0
    
    def _get_fallback_indicators(self) -> MacroIndicators:
        """폴백 지표 (API 실패 시)"""
        return MacroIndicators(
            fed_funds_rate=5.0,
            inflation_rate=3.0,
            dxy_index=100.0,
            m2_money_supply=5.0,
            unemployment_rate=4.0,
            gdp_growth=2.0,
            vix_index=20.0,
            gold_price=2000.0,
            oil_price=80.0,
            bond_yield_10y=4.0,
            last_updated=datetime.now()
        )
    
    def _get_fallback_analysis(self) -> MacroAnalysis:
        """폴백 분석 (분석 실패 시)"""
        return MacroAnalysis(
            economic_regime=EconomicRegime.RECOVERY,
            inflation_regime=InflationRegime.MODERATE,
            rate_environment=RateEnvironment.MODERATE,
            crypto_favorability=0.0,
            risk_adjustment=0.0,
            recommended_allocation={"crypto": 0.5, "krw": 0.5},
            key_drivers=["분석 데이터 부족"],
            analysis_confidence=0.3,
            created_at=datetime.now()
        )
    
    def get_macro_trend_analysis(self, historical_data: Dict[str, List[float]]) -> Dict[str, Any]:
        """매크로 트렌드 분석"""
        
        try:
            trends = {}
            
            for indicator, values in historical_data.items():
                if len(values) < 2:
                    continue
                    
                # 트렌드 계산 (선형 회귀 기울기)
                x = np.arange(len(values))
                y = np.array(values)
                
                # 최소제곱법으로 기울기 계산
                slope = np.polyfit(x, y, 1)[0]
                
                # 최근 변화율
                recent_change = (values[-1] - values[-2]) / values[-2] if values[-2] != 0 else 0
                
                # 변동성 (표준편차)
                volatility = np.std(values) / np.mean(values) if np.mean(values) != 0 else 0
                
                trends[indicator] = {
                    "slope": slope,
                    "direction": "increasing" if slope > 0.01 else "decreasing" if slope < -0.01 else "stable",
                    "recent_change": recent_change,
                    "volatility": volatility,
                    "current_value": values[-1],
                    "trend_strength": abs(slope) / np.std(y) if np.std(y) != 0 else 0
                }
            
            return {
                "trends": trends,
                "overall_direction": self._determine_overall_trend(trends),
                "trend_confidence": np.mean([trend["trend_strength"] for trend in trends.values()])
            }
            
        except Exception as e:
            logger.error(f"매크로 트렌드 분석 실패: {e}")
            return {"error": str(e)}
    
    def _determine_overall_trend(self, trends: Dict[str, Any]) -> str:
        """전체 트렌드 방향 결정"""
        
        # 암호화폐에 긍정적인 트렌드 점수 계산
        positive_score = 0
        total_weight = 0
        
        for indicator, trend in trends.items():
            weight = abs(self.impact_weights.get(indicator.replace("_", ""), 0.1))
            impact = self.impact_weights.get(indicator.replace("_", ""), 0)
            
            if trend["direction"] == "increasing":
                if impact > 0:  # 긍정적 영향
                    positive_score += weight
                elif impact < 0:  # 부정적 영향
                    positive_score -= weight
            elif trend["direction"] == "decreasing":
                if impact > 0:  # 긍정적 영향
                    positive_score -= weight
                elif impact < 0:  # 부정적 영향
                    positive_score += weight
            
            total_weight += weight
        
        if total_weight == 0:
            return "neutral"
        
        score_ratio = positive_score / total_weight
        
        if score_ratio > 0.2:
            return "crypto_favorable"
        elif score_ratio < -0.2:
            return "crypto_unfavorable"
        else:
            return "neutral"
    
    def get_latest_signal(self) -> Dict[str, Any]:
        """
        최신 시장 신호 조회
        
        Returns:
            최신 매크로 경제 분석 결과와 시장 신호
        """
        try:
            # 최신 매크로 경제 분석 실행
            analysis = self.analyze_comprehensive_macro()
            
            if "error" in analysis:
                return {
                    "market_signal": 0.0,
                    "confidence": 0.3,
                    "timestamp": datetime.now(),
                    "error": analysis.get("error", "분석 실패")
                }
            
            # 전체 트렌드 방향을 시장 신호로 변환
            overall_direction = analysis.get("overall_direction", "neutral")
            trend_confidence = analysis.get("trend_confidence", 0.5)
            
            if overall_direction == "crypto_favorable":
                market_signal = 0.5 * trend_confidence
            elif overall_direction == "crypto_unfavorable":
                market_signal = -0.5 * trend_confidence
            else:  # neutral
                market_signal = 0.0
            
            return {
                "market_signal": market_signal,
                "confidence": trend_confidence,
                "timestamp": datetime.now(),
                "overall_direction": overall_direction,
                "trends": analysis.get("trends", {})
            }
            
        except Exception as e:
            logger.error(f"매크로 최신 신호 조회 실패: {e}")
            return {
                "market_signal": 0.0,
                "confidence": 0.3,
                "timestamp": datetime.now(),
                "error": str(e)
            }