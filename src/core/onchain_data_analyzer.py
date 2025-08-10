"""
On-Chain Data Analyzer

온체인 데이터 분석을 통한 암호화폐 시장 인사이트
- 고래 축적 패턴 분석
- 거래소 유입/유출 모니터링  
- 장기보유자 공급량 추적
- 네트워크 성장률 분석
- 스테이블코인 도미넌스 분석
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import numpy as np
import requests
from loguru import logger


class OnchainTrend(Enum):
    """온체인 트렌드"""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class WhaleActivity(Enum):
    """고래 활동 패턴"""
    ACCUMULATING = "accumulating"    # 축적
    DISTRIBUTING = "distributing"    # 분산
    HODLING = "hodling"             # 보유
    MIXED = "mixed"                 # 혼재


class ExchangeFlow(Enum):
    """거래소 자금 흐름"""
    INFLOW = "inflow"               # 유입 (매도 압력)
    OUTFLOW = "outflow"             # 유출 (장기 보유)
    BALANCED = "balanced"           # 균형


@dataclass
class OnchainMetrics:
    """온체인 메트릭스"""
    # 고래 메트릭스
    whale_addresses_count: int      # 고래 주소 수 (>1000 BTC)
    whale_balance_total: float      # 고래 총 보유량
    whale_net_flow_24h: float      # 고래 24시간 순 흐름
    
    # 거래소 메트릭스
    exchange_inflow_24h: float      # 거래소 24시간 유입량
    exchange_outflow_24h: float     # 거래소 24시간 유출량
    exchange_netflow_24h: float     # 거래소 24시간 순 흐름
    exchange_reserves: float        # 거래소 보유량
    
    # 장기보유자 메트릭스
    long_term_holder_supply: float  # 장기보유자 공급량 (%)
    short_term_holder_supply: float # 단기보유자 공급량 (%)
    lth_net_position_change: float  # 장기보유자 포지션 변화
    
    # 네트워크 메트릭스
    active_addresses: int           # 활성 주소 수
    network_hash_rate: float        # 해시레이트
    transaction_count: int          # 트랜잭션 수
    network_value_locked: float     # 네트워크 잠금 가치
    
    # 스테이블코인 메트릭스
    stablecoin_supply: float        # 스테이블코인 총 공급량
    stablecoin_dominance: float     # 스테이블코인 도미넌스 (%)
    stablecoin_flow_24h: float      # 스테이블코인 24시간 흐름
    
    # 기타
    fear_greed_index: float         # 공포탐욕지수
    funding_rates: Dict[str, float] # 펀딩비율 (거래소별)
    
    last_updated: datetime


@dataclass
class OnchainAnalysis:
    """온체인 분석 결과"""
    overall_trend: OnchainTrend
    whale_activity: WhaleActivity
    exchange_flow: ExchangeFlow
    accumulation_score: float       # 축적 점수 (0-100)
    distribution_score: float       # 분산 점수 (0-100)
    network_health_score: float     # 네트워크 건강도 (0-100)
    market_sentiment: str           # 시장 심리
    key_insights: List[str]
    price_prediction_signals: Dict[str, float]
    confidence_level: float
    created_at: datetime


class OnchainDataAnalyzer:
    """
    온체인 데이터 분석기
    
    블록체인 온체인 데이터를 분석하여 시장 인사이트를 제공합니다.
    """
    
    def __init__(self, api_keys: Optional[Dict[str, str]] = None):
        """
        Args:
            api_keys: 외부 API 키 딕셔너리 (Glassnode, CryptoQuant 등)
        """
        self.api_keys = api_keys or {}
        
        # 온체인 데이터 제공자 설정
        self.data_providers = {
            "glassnode": "https://api.glassnode.com/v1/metrics",
            "cryptoquant": "https://api.cryptoquant.com/v1",
            "santiment": "https://api.santiment.net/graphql",
            "messari": "https://data.messari.io/api/v1"
        }
        
        # 고래 임계값 설정
        self.whale_thresholds = {
            "BTC": 1000,    # 1000 BTC 이상
            "ETH": 10000,   # 10000 ETH 이상
        }
        
        # 분석 가중치
        self.analysis_weights = {
            "whale_activity": 0.25,
            "exchange_flow": 0.20,
            "lth_behavior": 0.20,
            "network_health": 0.15,
            "stablecoin_flow": 0.10,
            "sentiment": 0.10
        }
        
        logger.info("OnchainDataAnalyzer 초기화 완료")
    
    def collect_onchain_metrics(self, asset: str = "BTC") -> OnchainMetrics:
        """온체인 메트릭스 수집"""
        try:
            logger.info(f"{asset} 온체인 데이터 수집 시작")
            
            # 실제 환경에서는 각 데이터 제공자 API 호출
            # 여기서는 예시 데이터 사용
            metrics = OnchainMetrics(
                # 고래 메트릭스
                whale_addresses_count=self._get_whale_count(asset),
                whale_balance_total=self._get_whale_balance(asset),
                whale_net_flow_24h=self._get_whale_flow(asset),
                
                # 거래소 메트릭스
                exchange_inflow_24h=self._get_exchange_inflow(asset),
                exchange_outflow_24h=self._get_exchange_outflow(asset),
                exchange_netflow_24h=self._get_exchange_netflow(asset),
                exchange_reserves=self._get_exchange_reserves(asset),
                
                # 장기보유자 메트릭스
                long_term_holder_supply=self._get_lth_supply(asset),
                short_term_holder_supply=self._get_sth_supply(asset),
                lth_net_position_change=self._get_lth_position_change(asset),
                
                # 네트워크 메트릭스
                active_addresses=self._get_active_addresses(asset),
                network_hash_rate=self._get_hash_rate(asset),
                transaction_count=self._get_transaction_count(asset),
                network_value_locked=self._get_nvl(asset),
                
                # 스테이블코인 메트릭스
                stablecoin_supply=self._get_stablecoin_supply(),
                stablecoin_dominance=self._get_stablecoin_dominance(),
                stablecoin_flow_24h=self._get_stablecoin_flow(),
                
                # 기타
                fear_greed_index=self._get_fear_greed_index(),
                funding_rates=self._get_funding_rates(asset),
                
                last_updated=datetime.now()
            )
            
            logger.info(f"{asset} 온체인 데이터 수집 완료")
            return metrics
            
        except Exception as e:
            logger.error(f"온체인 메트릭스 수집 실패: {e}")
            return self._get_fallback_metrics()
    
    def analyze_onchain_data(self, metrics: OnchainMetrics, asset: str = "BTC") -> OnchainAnalysis:
        """온체인 데이터 종합 분석"""
        try:
            logger.info(f"{asset} 온체인 분석 시작")
            
            # 고래 활동 분석
            whale_activity = self._analyze_whale_activity(metrics)
            
            # 거래소 흐름 분석
            exchange_flow = self._analyze_exchange_flow(metrics)
            
            # 축적/분산 점수 계산
            accumulation_score = self._calculate_accumulation_score(metrics)
            distribution_score = self._calculate_distribution_score(metrics)
            
            # 네트워크 건강도 계산
            network_health = self._calculate_network_health(metrics)
            
            # 전체 트렌드 결정
            overall_trend = self._determine_overall_trend(
                whale_activity, exchange_flow, accumulation_score, distribution_score
            )
            
            # 시장 심리 분석
            market_sentiment = self._analyze_market_sentiment(metrics)
            
            # 핵심 인사이트 추출
            key_insights = self._extract_key_insights(metrics, whale_activity, exchange_flow)
            
            # 가격 예측 신호
            price_signals = self._generate_price_signals(metrics, overall_trend)
            
            # 신뢰도 계산
            confidence = self._calculate_confidence(metrics)
            
            analysis = OnchainAnalysis(
                overall_trend=overall_trend,
                whale_activity=whale_activity,
                exchange_flow=exchange_flow,
                accumulation_score=accumulation_score,
                distribution_score=distribution_score,
                network_health_score=network_health,
                market_sentiment=market_sentiment,
                key_insights=key_insights,
                price_prediction_signals=price_signals,
                confidence_level=confidence,
                created_at=datetime.now()
            )
            
            logger.info(f"{asset} 온체인 분석 완료: {overall_trend.value}, 축적점수 {accumulation_score:.1f}")
            return analysis
            
        except Exception as e:
            logger.error(f"온체인 분석 실패: {e}")
            return self._get_fallback_analysis()
    
    def _analyze_whale_activity(self, metrics: OnchainMetrics) -> WhaleActivity:
        """고래 활동 패턴 분석"""
        
        whale_flow = metrics.whale_net_flow_24h
        whale_count_change = 0  # 실제로는 전일 대비 변화량 계산 필요
        
        # 고래 활동 점수 계산
        activity_score = 0
        
        if whale_flow > 5000:  # 대량 축적
            activity_score += 2
        elif whale_flow > 1000:  # 중간 축적
            activity_score += 1
        elif whale_flow < -5000:  # 대량 분산
            activity_score -= 2
        elif whale_flow < -1000:  # 중간 분산
            activity_score -= 1
        
        if whale_count_change > 10:  # 고래 수 증가
            activity_score += 1
        elif whale_count_change < -10:  # 고래 수 감소
            activity_score -= 1
        
        # 활동 패턴 결정
        if activity_score >= 2:
            return WhaleActivity.ACCUMULATING
        elif activity_score <= -2:
            return WhaleActivity.DISTRIBUTING
        elif abs(whale_flow) < 500:  # 적은 움직임
            return WhaleActivity.HODLING
        else:
            return WhaleActivity.MIXED
    
    def _analyze_exchange_flow(self, metrics: OnchainMetrics) -> ExchangeFlow:
        """거래소 자금 흐름 분석"""
        
        net_flow = metrics.exchange_netflow_24h
        flow_ratio = abs(net_flow) / (metrics.exchange_inflow_24h + metrics.exchange_outflow_24h + 1)
        
        # 임계값 기반 분류
        if net_flow > 1000 and flow_ratio > 0.1:  # 유의미한 유입
            return ExchangeFlow.INFLOW
        elif net_flow < -1000 and flow_ratio > 0.1:  # 유의미한 유출
            return ExchangeFlow.OUTFLOW
        else:
            return ExchangeFlow.BALANCED
    
    def _calculate_accumulation_score(self, metrics: OnchainMetrics) -> float:
        """축적 점수 계산 (0-100)"""
        
        score_components = []
        
        # 1. 고래 축적 (30%)
        whale_score = 50  # 기본점수
        if metrics.whale_net_flow_24h > 0:
            whale_score += min(metrics.whale_net_flow_24h / 100, 30)
        else:
            whale_score += max(metrics.whale_net_flow_24h / 100, -30)
        score_components.append(("whale", whale_score, 0.30))
        
        # 2. 거래소 유출 (25%)
        exchange_score = 50
        if metrics.exchange_netflow_24h < 0:  # 유출 = 긍정적
            exchange_score += min(abs(metrics.exchange_netflow_24h) / 200, 30)
        else:  # 유입 = 부정적
            exchange_score -= min(metrics.exchange_netflow_24h / 200, 30)
        score_components.append(("exchange", exchange_score, 0.25))
        
        # 3. 장기보유자 증가 (25%)
        lth_score = 50
        if metrics.lth_net_position_change > 0:
            lth_score += min(metrics.lth_net_position_change / 50, 30)
        else:
            lth_score += max(metrics.lth_net_position_change / 50, -30)
        score_components.append(("lth", lth_score, 0.25))
        
        # 4. 네트워크 성장 (20%)
        network_score = 50
        # 활성 주소 수 기반 (간단한 점수)
        if metrics.active_addresses > 800000:  # 높은 활성도
            network_score += 20
        elif metrics.active_addresses < 500000:  # 낮은 활성도
            network_score -= 20
        score_components.append(("network", network_score, 0.20))
        
        # 가중 평균 계산
        total_score = sum(score * weight for _, score, weight in score_components)
        return max(0, min(100, total_score))
    
    def _calculate_distribution_score(self, metrics: OnchainMetrics) -> float:
        """분산 점수 계산 (축적과 반대)"""
        return 100 - self._calculate_accumulation_score(metrics)
    
    def _calculate_network_health(self, metrics: OnchainMetrics) -> float:
        """네트워크 건강도 계산"""
        
        health_components = []
        
        # 1. 해시레이트 (30%)
        hash_score = 70  # 기본 점수
        # 실제로는 평균 대비 비교 필요
        if metrics.network_hash_rate > 500:  # EH/s 기준 (예시)
            hash_score = 90
        elif metrics.network_hash_rate < 300:
            hash_score = 50
        health_components.append(hash_score * 0.30)
        
        # 2. 활성 주소 (25%)
        address_score = 70
        if metrics.active_addresses > 800000:
            address_score = 90
        elif metrics.active_addresses < 500000:
            address_score = 50
        health_components.append(address_score * 0.25)
        
        # 3. 트랜잭션 수 (25%)
        tx_score = 70
        if metrics.transaction_count > 300000:
            tx_score = 90
        elif metrics.transaction_count < 150000:
            tx_score = 50
        health_components.append(tx_score * 0.25)
        
        # 4. 분산도 (20%) - 장기보유자 비율
        decentralization_score = metrics.long_term_holder_supply
        health_components.append(decentralization_score * 0.20)
        
        return sum(health_components)
    
    def _determine_overall_trend(
        self,
        whale_activity: WhaleActivity,
        exchange_flow: ExchangeFlow,
        accumulation_score: float,
        distribution_score: float
    ) -> OnchainTrend:
        """전체 트렌드 결정"""
        
        bullish_factors = 0
        bearish_factors = 0
        
        # 고래 활동
        if whale_activity == WhaleActivity.ACCUMULATING:
            bullish_factors += 2
        elif whale_activity == WhaleActivity.DISTRIBUTING:
            bearish_factors += 2
        
        # 거래소 흐름
        if exchange_flow == ExchangeFlow.OUTFLOW:
            bullish_factors += 2
        elif exchange_flow == ExchangeFlow.INFLOW:
            bearish_factors += 2
        
        # 축적/분산 점수
        if accumulation_score > 70:
            bullish_factors += 1
        elif accumulation_score < 30:
            bearish_factors += 1
        
        # 결정
        if bullish_factors >= bearish_factors + 2:
            return OnchainTrend.BULLISH
        elif bearish_factors >= bullish_factors + 2:
            return OnchainTrend.BEARISH
        else:
            return OnchainTrend.NEUTRAL
    
    def _analyze_market_sentiment(self, metrics: OnchainMetrics) -> str:
        """시장 심리 분석"""
        
        fear_greed = metrics.fear_greed_index
        
        if fear_greed <= 25:
            return "Extreme Fear"
        elif fear_greed <= 45:
            return "Fear"
        elif fear_greed <= 55:
            return "Neutral"
        elif fear_greed <= 75:
            return "Greed"
        else:
            return "Extreme Greed"
    
    def _extract_key_insights(
        self, 
        metrics: OnchainMetrics, 
        whale_activity: WhaleActivity, 
        exchange_flow: ExchangeFlow
    ) -> List[str]:
        """핵심 인사이트 추출"""
        
        insights = []
        
        # 고래 활동 인사이트
        if whale_activity == WhaleActivity.ACCUMULATING:
            if metrics.whale_net_flow_24h > 10000:
                insights.append("대형 고래들의 대규모 축적 패턴 감지")
            else:
                insights.append("고래들의 점진적 축적 진행 중")
        elif whale_activity == WhaleActivity.DISTRIBUTING:
            insights.append("고래들의 수익 실현 움직임 포착")
        
        # 거래소 흐름 인사이트
        if exchange_flow == ExchangeFlow.OUTFLOW:
            if abs(metrics.exchange_netflow_24h) > 15000:
                insights.append("거래소에서 대량 자금 유출 - 장기 보유 심리 강화")
            else:
                insights.append("꾸준한 거래소 자금 유출 지속")
        elif exchange_flow == ExchangeFlow.INFLOW:
            insights.append("거래소 자금 유입 증가 - 매도 압력 우려")
        
        # 장기보유자 인사이트
        if metrics.long_term_holder_supply > 75:
            insights.append(f"장기보유자 비율 {metrics.long_term_holder_supply:.1f}% - 강한 홀딩 심리")
        elif metrics.long_term_holder_supply < 60:
            insights.append("장기보유자 비율 감소 - 단기 변동성 증가 가능")
        
        # 스테이블코인 인사이트
        if metrics.stablecoin_dominance > 15:
            insights.append("스테이블코인 도미넌스 높음 - 관망세 강화")
        elif metrics.stablecoin_flow_24h > 1000000000:  # 10억 달러
            insights.append("대규모 스테이블코인 이동 감지 - 큰 시장 변화 예상")
        
        return insights[:4]  # 상위 4개만
    
    def _generate_price_signals(self, metrics: OnchainMetrics, trend: OnchainTrend) -> Dict[str, float]:
        """가격 예측 신호 생성"""
        
        signals = {}
        
        # 단기 신호 (1-7일)
        short_term_signal = 0.0
        if trend == OnchainTrend.BULLISH:
            short_term_signal += 0.3
        elif trend == OnchainTrend.BEARISH:
            short_term_signal -= 0.3
        
        # 거래소 흐름 영향
        if metrics.exchange_netflow_24h < -10000:  # 대량 유출
            short_term_signal += 0.2
        elif metrics.exchange_netflow_24h > 10000:  # 대량 유입
            short_term_signal -= 0.2
        
        signals["short_term"] = max(-1.0, min(1.0, short_term_signal))
        
        # 중기 신호 (1-4주)
        medium_term_signal = 0.0
        if metrics.whale_net_flow_24h > 5000:  # 고래 축적
            medium_term_signal += 0.4
        elif metrics.whale_net_flow_24h < -5000:  # 고래 분산
            medium_term_signal -= 0.4
        
        if metrics.lth_net_position_change > 50:  # 장기보유자 증가
            medium_term_signal += 0.3
        
        signals["medium_term"] = max(-1.0, min(1.0, medium_term_signal))
        
        # 장기 신호 (1-6개월)
        long_term_signal = 0.0
        if metrics.long_term_holder_supply > 75:
            long_term_signal += 0.3
        elif metrics.long_term_holder_supply < 60:
            long_term_signal -= 0.2
        
        # 네트워크 건강도 반영
        network_health = self._calculate_network_health(metrics)
        if network_health > 80:
            long_term_signal += 0.2
        elif network_health < 50:
            long_term_signal -= 0.2
        
        signals["long_term"] = max(-1.0, min(1.0, long_term_signal))
        
        return signals
    
    def _calculate_confidence(self, metrics: OnchainMetrics) -> float:
        """분석 신뢰도 계산"""
        
        confidence = 0.7  # 기본값
        
        # 데이터 최신성
        data_age = (datetime.now() - metrics.last_updated).total_seconds() / 3600
        if data_age > 6:  # 6시간 이상
            confidence -= 0.2
        
        # 데이터 일관성 (예: 고래 흐름과 거래소 흐름의 일관성)
        whale_exchange_consistency = abs(
            np.sign(metrics.whale_net_flow_24h) + np.sign(-metrics.exchange_netflow_24h)
        )
        if whale_exchange_consistency == 2:  # 일관성 있음
            confidence += 0.15
        elif whale_exchange_consistency == 0:  # 상반됨
            confidence -= 0.1
        
        return max(0.3, min(1.0, confidence))
    
    def get_latest_signal(self) -> Dict[str, Any]:
        """
        최신 시장 신호 조회
        
        Returns:
            최신 온체인 분석 결과와 시장 신호
        """
        try:
            # 최신 온체인 분석 실행
            analysis = self.analyze_comprehensive_onchain(asset="BTC")
            
            if not analysis.get("success"):
                return {
                    "market_signal": 0.0,
                    "confidence": 0.3,
                    "timestamp": datetime.now(),
                    "error": analysis.get("error", "분석 실패")
                }
            
            # 주요 신호들을 종합하여 단일 시장 신호로 변환
            signals = analysis.get("signals", {})
            market_signal = (
                signals.get("short_term", 0) * 0.4 +
                signals.get("medium_term", 0) * 0.4 +
                signals.get("long_term", 0) * 0.2
            )
            
            return {
                "market_signal": market_signal,
                "confidence": analysis.get("confidence", 0.5),
                "timestamp": datetime.now(),
                "signals": signals,
                "metrics": analysis.get("metrics")
            }
            
        except Exception as e:
            logger.error(f"온체인 최신 신호 조회 실패: {e}")
            return {
                "market_signal": 0.0,
                "confidence": 0.3,
                "timestamp": datetime.now(),
                "error": str(e)
            }
    
    # 데이터 수집 메서드들 (예시 - 실제로는 API 호출)
    def _get_whale_count(self, asset: str) -> int:
        """고래 주소 수 조회"""
        try:
            # 실제로는 Glassnode API 호출
            return 2150  # 예시 데이터
        except:
            return 2000
    
    def _get_whale_balance(self, asset: str) -> float:
        """고래 총 보유량 조회"""
        try:
            return 8500000  # BTC 기준 예시
        except:
            return 8000000
    
    def _get_whale_flow(self, asset: str) -> float:
        """고래 24시간 순 흐름"""
        try:
            return 2500  # BTC 기준 예시 (양수 = 축적)
        except:
            return 0
    
    def _get_exchange_inflow(self, asset: str) -> float:
        """거래소 유입량"""
        try:
            return 25000  # 예시
        except:
            return 20000
    
    def _get_exchange_outflow(self, asset: str) -> float:
        """거래소 유출량"""
        try:
            return 28000  # 예시
        except:
            return 25000
    
    def _get_exchange_netflow(self, asset: str) -> float:
        """거래소 순 흐름 (유입 - 유출)"""
        return self._get_exchange_inflow(asset) - self._get_exchange_outflow(asset)
    
    def _get_exchange_reserves(self, asset: str) -> float:
        """거래소 보유량"""
        try:
            return 2800000  # 예시
        except:
            return 3000000
    
    def _get_lth_supply(self, asset: str) -> float:
        """장기보유자 공급량 (%)"""
        try:
            return 68.5  # 예시
        except:
            return 65.0
    
    def _get_sth_supply(self, asset: str) -> float:
        """단기보유자 공급량 (%)"""
        return 100 - self._get_lth_supply(asset)
    
    def _get_lth_position_change(self, asset: str) -> float:
        """장기보유자 포지션 변화"""
        try:
            return 150  # 예시 (BTC)
        except:
            return 0
    
    def _get_active_addresses(self, asset: str) -> int:
        """활성 주소 수"""
        try:
            return 750000  # 예시
        except:
            return 700000
    
    def _get_hash_rate(self, asset: str) -> float:
        """해시레이트"""
        try:
            return 450.5  # EH/s 기준 예시
        except:
            return 400.0
    
    def _get_transaction_count(self, asset: str) -> int:
        """트랜잭션 수"""
        try:
            return 280000  # 예시
        except:
            return 250000
    
    def _get_nvl(self, asset: str) -> float:
        """네트워크 잠금 가치"""
        try:
            return 450000000000  # USD 기준 예시
        except:
            return 400000000000
    
    def _get_stablecoin_supply(self) -> float:
        """스테이블코인 총 공급량"""
        try:
            return 130000000000  # USD 기준 예시
        except:
            return 120000000000
    
    def _get_stablecoin_dominance(self) -> float:
        """스테이블코인 도미넌스"""
        try:
            return 8.5  # % 기준 예시
        except:
            return 10.0
    
    def _get_stablecoin_flow(self) -> float:
        """스테이블코인 24시간 흐름"""
        try:
            return 2500000000  # USD 기준 예시
        except:
            return 2000000000
    
    def _get_fear_greed_index(self) -> float:
        """공포탐욕지수"""
        try:
            return 55  # 0-100 기준
        except:
            return 50
    
    def _get_funding_rates(self, asset: str) -> Dict[str, float]:
        """펀딩비율"""
        try:
            return {
                "binance": 0.0025,
                "bybit": 0.0030,
                "okx": 0.0020
            }
        except:
            return {"average": 0.0025}
    
    def _get_fallback_metrics(self) -> OnchainMetrics:
        """폴백 메트릭스"""
        return OnchainMetrics(
            whale_addresses_count=2000,
            whale_balance_total=8000000,
            whale_net_flow_24h=0,
            exchange_inflow_24h=20000,
            exchange_outflow_24h=25000,
            exchange_netflow_24h=-5000,
            exchange_reserves=3000000,
            long_term_holder_supply=65.0,
            short_term_holder_supply=35.0,
            lth_net_position_change=0,
            active_addresses=700000,
            network_hash_rate=400.0,
            transaction_count=250000,
            network_value_locked=400000000000,
            stablecoin_supply=120000000000,
            stablecoin_dominance=10.0,
            stablecoin_flow_24h=2000000000,
            fear_greed_index=50,
            funding_rates={"average": 0.0025},
            last_updated=datetime.now()
        )
    
    def _get_fallback_analysis(self) -> OnchainAnalysis:
        """폴백 분석"""
        return OnchainAnalysis(
            overall_trend=OnchainTrend.NEUTRAL,
            whale_activity=WhaleActivity.HODLING,
            exchange_flow=ExchangeFlow.BALANCED,
            accumulation_score=50.0,
            distribution_score=50.0,
            network_health_score=70.0,
            market_sentiment="Neutral",
            key_insights=["데이터 수집 중 오류 발생"],
            price_prediction_signals={
                "short_term": 0.0,
                "medium_term": 0.0,
                "long_term": 0.0
            },
            confidence_level=0.3,
            created_at=datetime.now()
        )