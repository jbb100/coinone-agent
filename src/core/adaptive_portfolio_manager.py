"""
Adaptive Portfolio Management System

시장 상황과 성숙도에 따라 동적으로 조정되는 적응형 포트폴리오 관리 시스템
- 시장 성숙도별 자산 비중 조정
- 상관관계 분석 기반 리밸런싱
- 변동성 기반 동적 배분
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import numpy as np
from loguru import logger

from .portfolio_manager import PortfolioManager, AssetAllocation
from .multi_timeframe_analyzer import MultiTimeframeResult, CyclePhase, TrendDirection


class MarketMaturity(Enum):
    """시장 성숙도"""
    NASCENT = "nascent"         # 초기 시장 (BTC 중심)
    EMERGING = "emerging"       # 신흥 시장 (ETH 확장)  
    MATURE = "mature"           # 성숙 시장 (다변화)
    INSTITUTIONAL = "institutional"  # 기관 주도 시장


class CorrelationRegime(Enum):
    """상관관계 체제"""
    LOW_CORRELATION = "low_correlation"      # 낮은 상관관계 (< 0.5)
    MEDIUM_CORRELATION = "medium_correlation" # 중간 상관관계 (0.5-0.8)
    HIGH_CORRELATION = "high_correlation"     # 높은 상관관계 (> 0.8)


@dataclass
class MarketCharacteristics:
    """시장 특성"""
    maturity: MarketMaturity
    correlation_regime: CorrelationRegime
    overall_volatility: float
    btc_dominance: float
    altcoin_season_score: float  # 알트시즌 점수 (0-1)
    institutional_flow: float    # 기관 유입 정도 (-1 to 1)
    last_updated: datetime


@dataclass 
class AdaptiveAllocation:
    """적응형 자산 배분"""
    btc_weight: float
    eth_weight: float
    xrp_weight: float
    sol_weight: float
    krw_weight: float
    reasoning: Dict[str, str]  # 배분 근거
    confidence: float
    created_at: datetime
    
    def to_dict(self) -> Dict[str, float]:
        return {
            "BTC": self.btc_weight,
            "ETH": self.eth_weight, 
            "XRP": self.xrp_weight,
            "SOL": self.sol_weight,
            "KRW": self.krw_weight
        }


class AdaptivePortfolioManager:
    """
    적응형 포트폴리오 관리자
    
    시장 상황에 따라 동적으로 포트폴리오 구성을 조정합니다.
    """
    
    def __init__(self, base_portfolio_manager: PortfolioManager):
        """
        Args:
            base_portfolio_manager: 기본 포트폴리오 관리자
        """
        self.base_manager = base_portfolio_manager
        
        # 기본 설정
        self.min_btc_weight = 0.25  # BTC 최소 비중 25%
        self.max_btc_weight = 0.70  # BTC 최대 비중 70%
        self.min_krw_weight = 0.15  # KRW 최소 비중 15%
        self.max_krw_weight = 0.80  # KRW 최대 비중 80%
        
        # 상관관계 임계값
        self.correlation_thresholds = {
            "low": 0.5,
            "high": 0.8
        }
        
        logger.info("AdaptivePortfolioManager 초기화 완료")
    
    def calculate_adaptive_allocation(
        self,
        market_data: Dict[str, pd.DataFrame],
        multiframe_result: MultiTimeframeResult,
        current_portfolio: Dict
    ) -> AdaptiveAllocation:
        """
        적응형 자산 배분 계산
        
        Args:
            market_data: 각 자산의 가격 데이터
            multiframe_result: 멀티 타임프레임 분석 결과
            current_portfolio: 현재 포트폴리오 정보
            
        Returns:
            적응형 자산 배분
        """
        try:
            logger.info("적응형 자산 배분 계산 시작")
            
            # 시장 특성 분석
            market_chars = self._analyze_market_characteristics(market_data)
            
            # 기본 배분 계산 (기존 시스템)
            base_crypto_weight = multiframe_result.recommended_allocation["crypto"]
            base_krw_weight = multiframe_result.recommended_allocation["krw"]
            
            # 적응형 조정 적용
            adaptive_weights = self._apply_adaptive_adjustments(
                base_crypto_weight, base_krw_weight, market_chars, multiframe_result
            )
            
            # 제약 조건 적용
            final_weights = self._apply_constraints(adaptive_weights)
            
            # 배분 근거 생성
            reasoning = self._generate_reasoning(market_chars, multiframe_result, final_weights)
            
            # 신뢰도 계산
            confidence = self._calculate_allocation_confidence(market_chars, multiframe_result)
            
            allocation = AdaptiveAllocation(
                btc_weight=final_weights["BTC"],
                eth_weight=final_weights["ETH"],
                xrp_weight=final_weights["XRP"], 
                sol_weight=final_weights["SOL"],
                krw_weight=final_weights["KRW"],
                reasoning=reasoning,
                confidence=confidence,
                created_at=datetime.now()
            )
            
            logger.info(f"적응형 배분 완료: BTC {allocation.btc_weight:.1%}, 신뢰도 {confidence:.1%}")
            return allocation
            
        except Exception as e:
            logger.error(f"적응형 자산 배분 계산 실패: {e}")
            return self._get_fallback_allocation()
    
    def _analyze_market_characteristics(self, market_data: Dict[str, pd.DataFrame]) -> MarketCharacteristics:
        """시장 특성 분석"""
        try:
            # BTC 도미넌스 계산 (전체 시총 대비 BTC 비중)
            # 실제로는 외부 API에서 가져와야 하지만, 여기서는 근사치 계산
            btc_data = market_data.get("BTC")
            eth_data = market_data.get("ETH")
            
            if btc_data is None or eth_data is None:
                btc_dominance = 0.5  # 기본값
            else:
                # 간단한 근사: BTC/(BTC+ETH) 비율로 계산
                btc_price = btc_data['Close'].iloc[-1]
                eth_price = eth_data['Close'].iloc[-1] 
                btc_dominance = btc_price / (btc_price + eth_price * 0.8)  # ETH 가중치 조정
            
            # 시장 성숙도 판단
            if btc_dominance > 0.7:
                maturity = MarketMaturity.NASCENT
            elif btc_dominance > 0.6:
                maturity = MarketMaturity.EMERGING  
            elif btc_dominance > 0.45:
                maturity = MarketMaturity.MATURE
            else:
                maturity = MarketMaturity.INSTITUTIONAL
            
            # 상관관계 체제 분석
            correlation_regime = self._analyze_correlation_regime(market_data)
            
            # 전체 변동성 계산
            overall_volatility = self._calculate_market_volatility(market_data)
            
            # 알트시즌 점수 (BTC 도미넌스 역수 기반)
            altcoin_season_score = max(0, (0.6 - btc_dominance) / 0.2)
            
            # 기관 유입 점수 (변동성 기반 추정)
            # 낮은 변동성 = 기관 유입 증가
            institutional_flow = max(-1, min(1, (0.8 - overall_volatility) / 0.4))
            
            return MarketCharacteristics(
                maturity=maturity,
                correlation_regime=correlation_regime,
                overall_volatility=overall_volatility,
                btc_dominance=btc_dominance,
                altcoin_season_score=altcoin_season_score,
                institutional_flow=institutional_flow,
                last_updated=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"시장 특성 분석 실패: {e}")
            return MarketCharacteristics(
                maturity=MarketMaturity.MATURE,
                correlation_regime=CorrelationRegime.MEDIUM_CORRELATION,
                overall_volatility=0.6,
                btc_dominance=0.5,
                altcoin_season_score=0.3,
                institutional_flow=0.0,
                last_updated=datetime.now()
            )
    
    def _analyze_correlation_regime(self, market_data: Dict[str, pd.DataFrame]) -> CorrelationRegime:
        """자산 간 상관관계 체제 분석"""
        try:
            # 최근 30일간의 수익률 계산
            assets = ["BTC", "ETH", "XRP", "SOL"]
            returns_data = {}
            
            for asset in assets:
                if asset in market_data and len(market_data[asset]) > 30:
                    prices = market_data[asset]['Close'].tail(30)
                    returns = prices.pct_change().dropna()
                    returns_data[asset] = returns
            
            if len(returns_data) < 2:
                return CorrelationRegime.MEDIUM_CORRELATION
            
            # 상관관계 행렬 계산
            returns_df = pd.DataFrame(returns_data)
            correlation_matrix = returns_df.corr()
            
            # 평균 상관관계 계산 (자기 자신 제외)
            correlations = []
            for i in range(len(correlation_matrix)):
                for j in range(i+1, len(correlation_matrix)):
                    correlations.append(abs(correlation_matrix.iloc[i, j]))
            
            avg_correlation = np.mean(correlations) if correlations else 0.6
            
            if avg_correlation < self.correlation_thresholds["low"]:
                return CorrelationRegime.LOW_CORRELATION
            elif avg_correlation > self.correlation_thresholds["high"]:
                return CorrelationRegime.HIGH_CORRELATION
            else:
                return CorrelationRegime.MEDIUM_CORRELATION
                
        except Exception as e:
            logger.error(f"상관관계 분석 실패: {e}")
            return CorrelationRegime.MEDIUM_CORRELATION
    
    def _calculate_market_volatility(self, market_data: Dict[str, pd.DataFrame]) -> float:
        """시장 전체 변동성 계산"""
        try:
            volatilities = []
            
            for asset in ["BTC", "ETH", "XRP", "SOL"]:
                if asset in market_data:
                    prices = market_data[asset]['Close'].tail(30)
                    returns = prices.pct_change().dropna()
                    vol = returns.std() * np.sqrt(365)  # 연화 변동성
                    volatilities.append(vol)
            
            return np.mean(volatilities) if volatilities else 0.6
            
        except Exception as e:
            logger.error(f"변동성 계산 실패: {e}")
            return 0.6
    
    def _apply_adaptive_adjustments(
        self,
        base_crypto_weight: float,
        base_krw_weight: float, 
        market_chars: MarketCharacteristics,
        multiframe_result: MultiTimeframeResult
    ) -> Dict[str, float]:
        """적응형 조정 적용"""
        
        # 1. 시장 성숙도에 따른 BTC 비중 조정
        maturity_btc_adjustments = {
            MarketMaturity.NASCENT: 0.15,        # BTC 비중 +15%
            MarketMaturity.EMERGING: 0.05,       # BTC 비중 +5%
            MarketMaturity.MATURE: 0.0,          # 기본값 유지
            MarketMaturity.INSTITUTIONAL: -0.1   # BTC 비중 -10%
        }
        
        btc_adjustment = maturity_btc_adjustments[market_chars.maturity]
        
        # 2. 사이클 단계에 따른 조정
        cycle_adjustments = {
            CyclePhase.ACCUMULATION: {"btc": 0.1, "krw": 0.1},    # 축적 단계: 보수적
            CyclePhase.MARKUP: {"btc": -0.05, "krw": -0.1},       # 상승 단계: 공격적
            CyclePhase.DISTRIBUTION: {"btc": 0.05, "krw": 0.15},  # 분배 단계: 방어적
            CyclePhase.DECLINE: {"btc": 0.0, "krw": 0.2}          # 하락 단계: 매우 방어적
        }
        
        cycle_adj = cycle_adjustments[multiframe_result.cycle_phase]
        
        # 3. 상관관계 체제에 따른 다각화 조정
        correlation_adjustments = {
            CorrelationRegime.LOW_CORRELATION: {"diversify": 0.05},   # 다각화 유리
            CorrelationRegime.MEDIUM_CORRELATION: {"diversify": 0.0}, # 기본값
            CorrelationRegime.HIGH_CORRELATION: {"diversify": -0.05}  # 집중 투자 유리
        }
        
        div_adj = correlation_adjustments[market_chars.correlation_regime]
        
        # 4. 알트시즌 조정
        altseason_adj = market_chars.altcoin_season_score * 0.1  # 최대 10% 알트 비중 증가
        
        # 기본 암호화폐 내 비중 (기존 시스템)
        base_asset_allocation = self.base_manager.asset_allocation
        crypto_total = base_crypto_weight
        
        # BTC 비중 계산
        btc_base_ratio = base_asset_allocation.btc_weight
        btc_weight = crypto_total * btc_base_ratio * (1 + btc_adjustment) + cycle_adj["btc"]
        
        # ETH 비중 (기관 유입이 많을 때 증가)
        eth_base_ratio = base_asset_allocation.eth_weight  
        institutional_bonus = market_chars.institutional_flow * 0.05
        eth_weight = crypto_total * eth_base_ratio * (1 + institutional_bonus + div_adj.get("diversify", 0))
        
        # 알트코인 비중 (알트시즌일 때 증가)
        xrp_base_ratio = base_asset_allocation.xrp_weight
        sol_base_ratio = base_asset_allocation.sol_weight
        
        xrp_weight = crypto_total * xrp_base_ratio * (1 + altseason_adj + div_adj.get("diversify", 0))
        sol_weight = crypto_total * sol_base_ratio * (1 + altseason_adj + div_adj.get("diversify", 0))
        
        # KRW 비중
        krw_weight = base_krw_weight + cycle_adj["krw"]
        
        return {
            "BTC": btc_weight,
            "ETH": eth_weight,
            "XRP": xrp_weight, 
            "SOL": sol_weight,
            "KRW": krw_weight
        }
    
    def _apply_constraints(self, weights: Dict[str, float]) -> Dict[str, float]:
        """제약 조건 적용"""
        # BTC 비중 제한
        weights["BTC"] = max(self.min_btc_weight, min(self.max_btc_weight, weights["BTC"]))
        
        # KRW 비중 제한
        weights["KRW"] = max(self.min_krw_weight, min(self.max_krw_weight, weights["KRW"]))
        
        # 전체 비중이 1이 되도록 정규화
        total_weight = sum(weights.values())
        if total_weight != 1.0:
            for asset in weights:
                weights[asset] = weights[asset] / total_weight
        
        # 최소 비중 보장 (각 자산 최소 1%)
        min_weight = 0.01
        for asset in ["BTC", "ETH", "XRP", "SOL"]:
            if weights[asset] < min_weight:
                weights[asset] = min_weight
        
        # 재정규화
        total_weight = sum(weights.values())
        for asset in weights:
            weights[asset] = weights[asset] / total_weight
        
        return weights
    
    def _generate_reasoning(
        self, 
        market_chars: MarketCharacteristics, 
        multiframe_result: MultiTimeframeResult,
        final_weights: Dict[str, float]
    ) -> Dict[str, str]:
        """배분 근거 생성"""
        reasoning = {}
        
        # BTC 비중 근거
        if final_weights["BTC"] > 0.5:
            reasoning["BTC"] = f"시장 성숙도({market_chars.maturity.value})와 BTC 도미넌스({market_chars.btc_dominance:.1%})를 고려하여 BTC 중심 배분"
        else:
            reasoning["BTC"] = f"성숙한 시장 환경에서 BTC 비중을 {final_weights['BTC']:.1%}로 제한"
        
        # 알트코인 근거
        if market_chars.altcoin_season_score > 0.5:
            reasoning["ALTCOINS"] = f"알트시즌 점수 {market_chars.altcoin_season_score:.1f}에 따라 알트코인 비중 증가"
        
        # KRW 비중 근거
        if final_weights["KRW"] > 0.5:
            reasoning["KRW"] = f"사이클 단계({multiframe_result.cycle_phase.value})를 고려한 방어적 포지션"
        
        # 전체 전략
        reasoning["STRATEGY"] = f"상관관계 체제: {market_chars.correlation_regime.value}, 변동성: {market_chars.overall_volatility:.1%}"
        
        return reasoning
    
    def _calculate_allocation_confidence(
        self, 
        market_chars: MarketCharacteristics,
        multiframe_result: MultiTimeframeResult
    ) -> float:
        """배분 신뢰도 계산"""
        confidence_factors = []
        
        # 멀티 타임프레임 신뢰도
        confidence_factors.append(multiframe_result.overall_confidence)
        
        # 시장 특성 확실성 (변동성이 낮을수록 높음)
        volatility_confidence = max(0, 1 - market_chars.overall_volatility)
        confidence_factors.append(volatility_confidence)
        
        # 상관관계 체제 안정성
        if market_chars.correlation_regime == CorrelationRegime.MEDIUM_CORRELATION:
            correlation_confidence = 0.8
        else:
            correlation_confidence = 0.6
        confidence_factors.append(correlation_confidence)
        
        # BTC 도미넌스 안정성 (극값이 아닐 때 높음)
        if 0.4 < market_chars.btc_dominance < 0.7:
            dominance_confidence = 0.8
        else:
            dominance_confidence = 0.5
        confidence_factors.append(dominance_confidence)
        
        return np.mean(confidence_factors)
    
    def _get_fallback_allocation(self) -> AdaptiveAllocation:
        """폴백 배분 (오류 시 기본값)"""
        return AdaptiveAllocation(
            btc_weight=0.4,
            eth_weight=0.3,
            xrp_weight=0.15,
            sol_weight=0.15,
            krw_weight=0.0,
            reasoning={"ERROR": "시스템 오류로 인한 기본 배분"},
            confidence=0.3,
            created_at=datetime.now()
        )
    
    def get_rebalance_urgency(
        self, 
        current_allocation: Dict[str, float],
        target_allocation: AdaptiveAllocation
    ) -> Tuple[float, str]:
        """리밸런싱 긴급도 계산"""
        
        target_dict = target_allocation.to_dict()
        
        # 각 자산별 차이 계산
        differences = []
        for asset in ["BTC", "ETH", "XRP", "SOL", "KRW"]:
            current = current_allocation.get(asset, 0)
            target = target_dict.get(asset, 0)
            diff = abs(current - target)
            differences.append(diff)
        
        # 최대 차이와 평균 차이
        max_diff = max(differences)
        avg_diff = np.mean(differences)
        
        # 긴급도 점수 (0-1)
        urgency_score = min(1.0, (max_diff * 2 + avg_diff) / 2)
        
        # 긴급도 레벨
        if urgency_score > 0.15:
            urgency_level = "HIGH"
        elif urgency_score > 0.08:
            urgency_level = "MEDIUM"
        elif urgency_score > 0.03:
            urgency_level = "LOW"
        else:
            urgency_level = "NONE"
        
        return urgency_score, urgency_level
    
    def analyze_correlation_impact(self, market_data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """상관관계가 포트폴리오에 미치는 영향 분석"""
        try:
            assets = ["BTC", "ETH", "XRP", "SOL"]
            
            # 최근 데이터로 상관관계 계산
            returns_data = {}
            for asset in assets:
                if asset in market_data:
                    prices = market_data[asset]['Close'].tail(60)  # 최근 60일
                    returns = prices.pct_change().dropna()
                    returns_data[asset] = returns
            
            if len(returns_data) < 2:
                return {"error": "insufficient_data"}
            
            returns_df = pd.DataFrame(returns_data)
            correlation_matrix = returns_df.corr()
            
            # 다각화 효과 계산
            equal_weight_portfolio = returns_df.mean(axis=1)
            portfolio_vol = equal_weight_portfolio.std()
            avg_individual_vol = returns_df.std().mean()
            
            diversification_ratio = avg_individual_vol / portfolio_vol
            
            return {
                "correlation_matrix": correlation_matrix.to_dict(),
                "diversification_ratio": diversification_ratio,
                "portfolio_volatility": portfolio_vol,
                "avg_asset_volatility": avg_individual_vol,
                "diversification_benefit": (diversification_ratio - 1) * 100  # 백분율
            }
            
        except Exception as e:
            logger.error(f"상관관계 영향 분석 실패: {e}")
            return {"error": str(e)}