"""
Dynamic Portfolio Optimizer

동적 포트폴리오 최적화를 통해 자동으로 코인 선택 및 비중을 조정하는 시스템입니다.
시장 상황, 성과, 리스크 지표를 종합하여 최적의 포트폴리오를 구성합니다.
"""

import math
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import yfinance as yf
from loguru import logger


class AssetClass(Enum):
    """자산 클래스"""
    CORE = "core"               # 핵심 자산 (BTC, ETH)
    LARGE_CAP = "large_cap"     # 대형 알트코인
    MID_CAP = "mid_cap"         # 중형 알트코인  
    SMALL_CAP = "small_cap"     # 소형 알트코인
    DEFI = "defi"              # DeFi 토큰
    LAYER1 = "layer1"          # Layer 1 블록체인
    UTILITY = "utility"         # 유틸리티 토큰
    MEME = "meme"              # 밈 코인


class SelectionCriteria(Enum):
    """선택 기준"""
    MARKET_CAP = "market_cap"           # 시가총액
    VOLUME = "volume"                   # 거래량
    VOLATILITY = "volatility"           # 변동성
    MOMENTUM = "momentum"               # 모멘텀
    CORRELATION = "correlation"         # 상관관계
    SHARPE_RATIO = "sharpe_ratio"      # 샤프비율
    MAX_DRAWDOWN = "max_drawdown"      # 최대낙폭
    LIQUIDITY = "liquidity"            # 유동성


@dataclass
class AssetMetrics:
    """자산 성과 지표"""
    symbol: str
    market_cap: float
    volume_24h: float
    price_change_24h: float
    price_change_7d: float
    price_change_30d: float
    volatility_30d: float
    sharpe_ratio_30d: float
    max_drawdown_30d: float
    correlation_btc: float
    liquidity_score: float
    momentum_score: float
    quality_score: float
    risk_score: float
    overall_score: float
    asset_class: AssetClass
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class PortfolioWeights:
    """포트폴리오 비중"""
    weights: Dict[str, float]
    risk_level: str  # conservative, moderate, aggressive
    diversification_score: float
    expected_return: float
    expected_risk: float
    sharpe_ratio: float
    created_at: datetime = field(default_factory=datetime.now)


class DynamicPortfolioOptimizer:
    """
    동적 포트폴리오 최적화기
    
    시장 분석, 자산 평가, 리스크 관리를 통해
    최적의 포트폴리오 구성을 자동으로 결정합니다.
    """
    
    def __init__(
        self,
        coinone_client=None,
        risk_level: str = "moderate",  # conservative, moderate, aggressive
        rebalance_frequency_days: int = 30,
        max_assets: int = 6,
        min_market_cap_usd: float = 1e9,  # 10억 달러
        max_single_weight: float = 0.5,   # 50% 최대
        min_single_weight: float = 0.05   # 5% 최소
    ):
        """
        Args:
            coinone_client: 코인원 클라이언트
            risk_level: 리스크 수준 (conservative/moderate/aggressive)
            rebalance_frequency_days: 리밸런싱 주기 (일)
            max_assets: 최대 보유 자산 수
            min_market_cap_usd: 최소 시가총액 (USD)
            max_single_weight: 단일 자산 최대 비중
            min_single_weight: 단일 자산 최소 비중
        """
        self.coinone_client = coinone_client
        self.risk_level = risk_level
        self.rebalance_frequency_days = rebalance_frequency_days
        self.max_assets = max_assets
        self.min_market_cap_usd = min_market_cap_usd
        self.max_single_weight = max_single_weight
        self.min_single_weight = min_single_weight
        
        # 코인원 지원 암호화폐 리스트 (실제로는 API에서 가져와야 함)
        self.available_assets = [
            "BTC", "ETH", "XRP", "SOL", "ADA", "DOT", "MATIC", "LINK",
            "DOGE", "ATOM", "TRX", "ALGO", "VET", "XLM", "AVAX", "UNI"
        ]
        
        # 자산 분류
        self.asset_classes = {
            "BTC": AssetClass.CORE,
            "ETH": AssetClass.CORE,
            "XRP": AssetClass.LARGE_CAP,
            "SOL": AssetClass.LAYER1,
            "ADA": AssetClass.LAYER1,
            "DOT": AssetClass.LAYER1,
            "MATIC": AssetClass.LAYER1,
            "LINK": AssetClass.UTILITY,
            "DOGE": AssetClass.MEME,
            "ATOM": AssetClass.LAYER1,
            "TRX": AssetClass.LAYER1,
            "ALGO": AssetClass.LAYER1,
            "VET": AssetClass.UTILITY,
            "XLM": AssetClass.UTILITY,
            "AVAX": AssetClass.LAYER1,
            "UNI": AssetClass.DEFI
        }
        
        # 리스크 수준별 설정
        self.risk_settings = {
            "conservative": {
                "core_min_weight": 0.60,      # BTC+ETH 최소 60%
                "max_volatility": 0.15,       # 최대 변동성 15%
                "max_correlation": 0.8,       # 최대 상관관계 80%
                "min_sharpe_ratio": 0.3,      # 최소 샤프비율 0.3
                "diversification_target": 4   # 목표 자산 수 4개
            },
            "moderate": {
                "core_min_weight": 0.50,      # BTC+ETH 최소 50%
                "max_volatility": 0.25,       # 최대 변동성 25%
                "max_correlation": 0.85,      # 최대 상관관계 85%
                "min_sharpe_ratio": 0.2,      # 최소 샤프비율 0.2
                "diversification_target": 6   # 목표 자산 수 6개
            },
            "aggressive": {
                "core_min_weight": 0.40,      # BTC+ETH 최소 40%
                "max_volatility": 0.40,       # 최대 변동성 40%
                "max_correlation": 0.90,      # 최대 상관관계 90%
                "min_sharpe_ratio": 0.1,      # 최소 샤프비율 0.1
                "diversification_target": 8   # 목표 자산 수 8개
            }
        }
        
        logger.info(f"DynamicPortfolioOptimizer 초기화: {risk_level} 리스크")
        logger.info(f"최대 자산 수: {max_assets}, 최소 시총: ${min_market_cap_usd/1e9:.1f}B")
    
    def analyze_all_assets(self) -> Dict[str, AssetMetrics]:
        """모든 가능한 자산 분석"""
        try:
            logger.info("전체 자산 분석 시작")
            asset_metrics = {}
            
            for symbol in self.available_assets:
                try:
                    metrics = self._analyze_single_asset(symbol)
                    if metrics:
                        asset_metrics[symbol] = metrics
                        logger.info(f"✅ {symbol} 분석 완료: 점수 {metrics.overall_score:.2f}")
                except Exception as e:
                    logger.warning(f"⚠️ {symbol} 분석 실패: {e}")
                    continue
            
            logger.info(f"자산 분석 완료: {len(asset_metrics)}개 자산")
            return asset_metrics
            
        except Exception as e:
            logger.error(f"자산 분석 실패: {e}")
            return None
    
    def _analyze_single_asset(self, symbol: str) -> Optional[AssetMetrics]:
        """단일 자산 분석"""
        try:
            # Yahoo Finance에서 데이터 수집 (USD 기준)
            ticker_symbol = f"{symbol}-USD"
            ticker = yf.Ticker(ticker_symbol)
            
            # 30일 가격 데이터
            hist = ticker.history(period="30d")
            if hist.empty:
                logger.warning(f"{symbol}: 가격 데이터 없음")
                return None
            
            # 기본 정보
            info = ticker.info
            market_cap = info.get("marketCap", 0)
            volume_24h = info.get("averageVolume", 0)
            
            # 시가총액 필터링
            if market_cap < self.min_market_cap_usd:
                logger.info(f"{symbol}: 시총 부족 ${market_cap/1e9:.2f}B < ${self.min_market_cap_usd/1e9:.1f}B")
                return None
            
            # 가격 변화율 계산
            current_price = hist['Close'].iloc[-1]
            price_1d_ago = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
            price_7d_ago = hist['Close'].iloc[-7] if len(hist) > 7 else current_price
            price_30d_ago = hist['Close'].iloc[0]
            
            price_change_24h = (current_price - price_1d_ago) / price_1d_ago
            price_change_7d = (current_price - price_7d_ago) / price_7d_ago
            price_change_30d = (current_price - price_30d_ago) / price_30d_ago
            
            # 변동성 계산 (30일 일별 수익률 표준편차 * sqrt(252))
            returns = hist['Close'].pct_change().dropna()
            volatility_30d = returns.std() * np.sqrt(252)
            
            # 샤프 비율 (무위험 수익률 2% 가정)
            risk_free_rate = 0.02
            avg_return = returns.mean() * 252  # 연간화
            sharpe_ratio_30d = (avg_return - risk_free_rate) / volatility_30d if volatility_30d > 0 else 0
            
            # 최대 낙폭 계산
            cumulative_returns = (1 + returns).cumprod()
            running_max = cumulative_returns.expanding().max()
            drawdown = (cumulative_returns - running_max) / running_max
            max_drawdown_30d = drawdown.min()
            
            # BTC와의 상관관계
            btc_correlation = self._calculate_btc_correlation(symbol)
            
            # 유동성 점수 (거래량 기반)
            liquidity_score = min(1.0, volume_24h / 100000000)  # 1억 달러 기준 정규화
            
            # 모멘텀 점수 (7일 + 30일 수익률)
            momentum_score = (price_change_7d * 0.3 + price_change_30d * 0.7)
            
            # 품질 점수 (샤프 비율 + 변동성 역수)
            quality_score = sharpe_ratio_30d * 0.6 + (1 - min(volatility_30d, 1.0)) * 0.4
            
            # 리스크 점수 (변동성 + 최대낙폭)
            risk_score = volatility_30d * 0.6 + abs(max_drawdown_30d) * 0.4
            
            # 종합 점수 계산
            overall_score = self._calculate_overall_score(
                momentum_score, quality_score, risk_score, 
                liquidity_score, btc_correlation
            )
            
            return AssetMetrics(
                symbol=symbol,
                market_cap=market_cap,
                volume_24h=volume_24h,
                price_change_24h=price_change_24h,
                price_change_7d=price_change_7d,
                price_change_30d=price_change_30d,
                volatility_30d=volatility_30d,
                sharpe_ratio_30d=sharpe_ratio_30d,
                max_drawdown_30d=max_drawdown_30d,
                correlation_btc=btc_correlation,
                liquidity_score=liquidity_score,
                momentum_score=momentum_score,
                quality_score=quality_score,
                risk_score=risk_score,
                overall_score=overall_score,
                asset_class=self.asset_classes.get(symbol, AssetClass.UTILITY)
            )
            
        except Exception as e:
            logger.error(f"{symbol} 분석 중 오류: {e}")
            return None
    
    def _calculate_btc_correlation(self, symbol: str) -> float:
        """BTC와의 상관관계 계산"""
        try:
            if symbol == "BTC":
                return 1.0
            
            # 30일 데이터로 상관관계 계산
            btc_data = yf.Ticker("BTC-USD").history(period="30d")['Close'].pct_change().dropna()
            asset_data = yf.Ticker(f"{symbol}-USD").history(period="30d")['Close'].pct_change().dropna()
            
            if len(btc_data) < 10 or len(asset_data) < 10:
                return 0.5  # 기본값
            
            # 길이 맞춤
            min_len = min(len(btc_data), len(asset_data))
            btc_returns = btc_data[-min_len:]
            asset_returns = asset_data[-min_len:]
            
            correlation = btc_returns.corr(asset_returns)
            return float(correlation) if not np.isnan(correlation) else 0.5
            
        except Exception as e:
            logger.warning(f"{symbol} BTC 상관관계 계산 실패: {e}")
            return 0.5
    
    def _calculate_overall_score(
        self, 
        momentum: float, 
        quality: float, 
        risk: float, 
        liquidity: float, 
        correlation: float
    ) -> float:
        """종합 점수 계산"""
        # 리스크 수준별 가중치 조정
        risk_settings = self.risk_settings[self.risk_level]
        
        if self.risk_level == "conservative":
            # 보수적: 품질과 안정성 중시
            score = (
                quality * 0.4 +
                (1 - risk) * 0.3 +
                liquidity * 0.2 +
                momentum * 0.1
            )
        elif self.risk_level == "aggressive":
            # 공격적: 모멘텀과 성장성 중시
            score = (
                momentum * 0.4 +
                quality * 0.3 +
                liquidity * 0.2 +
                (1 - risk) * 0.1
            )
        else:  # moderate
            # 균형형: 모든 요소 균형
            score = (
                quality * 0.3 +
                momentum * 0.25 +
                (1 - risk) * 0.25 +
                liquidity * 0.2
            )
        
        # 상관관계 패널티 (너무 높으면 감점)
        if correlation > risk_settings["max_correlation"]:
            score *= 0.8
        
        return max(0, min(1, score))
    
    def select_optimal_portfolio(self, asset_metrics: Dict[str, AssetMetrics]) -> List[str]:
        """최적 포트폴리오 자산 선택"""
        try:
            logger.info("최적 포트폴리오 자산 선택 시작")
            
            # 1. BTC, ETH는 필수 포함 (Core 자산)
            selected_assets = []
            core_assets = ["BTC", "ETH"]
            
            for core in core_assets:
                if core in asset_metrics:
                    selected_assets.append(core)
                    logger.info(f"🔵 Core 자산 선택: {core}")
            
            # 2. 나머지 자산 중에서 점수 기준으로 선택
            non_core_assets = [
                (symbol, metrics) for symbol, metrics in asset_metrics.items()
                if symbol not in core_assets
            ]
            
            # 점수 순으로 정렬
            non_core_assets.sort(key=lambda x: x[1].overall_score, reverse=True)
            
            # 3. 다양성 고려하여 선택
            risk_settings = self.risk_settings[self.risk_level]
            target_count = min(
                risk_settings["diversification_target"],
                self.max_assets
            ) - len(selected_assets)
            
            added_classes = set()
            for symbol, metrics in non_core_assets:
                if len(selected_assets) >= self.max_assets:
                    break
                
                # 자산 클래스 다양성 체크
                asset_class = metrics.asset_class
                if asset_class in added_classes and len(selected_assets) < target_count:
                    continue  # 같은 클래스는 1개만
                
                # 품질 기준 필터
                if metrics.overall_score < 0.3:  # 최소 점수
                    continue
                
                # 변동성 필터
                if metrics.volatility_30d > risk_settings["max_volatility"]:
                    continue
                
                selected_assets.append(symbol)
                added_classes.add(asset_class)
                logger.info(f"🟢 추가 자산 선택: {symbol} (점수: {metrics.overall_score:.2f}, "
                          f"클래스: {asset_class.value})")
            
            logger.info(f"최종 선택된 자산: {selected_assets}")
            return selected_assets
            
        except Exception as e:
            logger.error(f"포트폴리오 선택 실패: {e}")
            return ["BTC", "ETH", "XRP", "SOL"]  # 기본값
    
    def optimize_weights(
        self, 
        selected_assets: List[str], 
        asset_metrics: Dict[str, AssetMetrics]
    ) -> PortfolioWeights:
        """포트폴리오 비중 최적화"""
        try:
            logger.info(f"포트폴리오 비중 최적화: {selected_assets}")
            
            risk_settings = self.risk_settings[self.risk_level]
            
            # 1. 기본 비중 할당
            weights = {}
            
            # Core 자산 (BTC, ETH) 최소 비중 보장
            core_assets = [asset for asset in selected_assets if asset in ["BTC", "ETH"]]
            non_core_assets = [asset for asset in selected_assets if asset not in ["BTC", "ETH"]]
            
            core_total_weight = max(risk_settings["core_min_weight"], 0.4)
            non_core_total_weight = 1.0 - core_total_weight
            
            # 2. Core 자산 비중 할당
            if core_assets:
                # BTC > ETH 비중으로 할당
                if "BTC" in core_assets and "ETH" in core_assets:
                    weights["BTC"] = core_total_weight * 0.6  # 60%
                    weights["ETH"] = core_total_weight * 0.4  # 40%
                elif "BTC" in core_assets:
                    weights["BTC"] = core_total_weight
                elif "ETH" in core_assets:
                    weights["ETH"] = core_total_weight
            
            # 3. Non-core 자산 비중 할당 (점수 기반)
            if non_core_assets:
                total_score = sum(asset_metrics[asset].overall_score for asset in non_core_assets)
                
                for asset in non_core_assets:
                    if total_score > 0:
                        score_weight = asset_metrics[asset].overall_score / total_score
                        weights[asset] = non_core_total_weight * score_weight
                    else:
                        weights[asset] = non_core_total_weight / len(non_core_assets)
            
            # 4. 비중 제약 조건 적용
            weights = self._apply_weight_constraints(weights)
            
            # 5. 포트폴리오 통계 계산
            portfolio_stats = self._calculate_portfolio_stats(weights, asset_metrics)
            
            portfolio_weights = PortfolioWeights(
                weights=weights,
                risk_level=self.risk_level,
                diversification_score=len(selected_assets) / self.max_assets,
                expected_return=portfolio_stats["expected_return"],
                expected_risk=portfolio_stats["expected_risk"],
                sharpe_ratio=portfolio_stats["sharpe_ratio"]
            )
            
            logger.info("포트폴리오 비중 최적화 완료")
            for asset, weight in weights.items():
                logger.info(f"  {asset}: {weight:.1%}")
            logger.info(f"예상 수익률: {portfolio_stats['expected_return']:.1%}, "
                       f"리스크: {portfolio_stats['expected_risk']:.1%}, "
                       f"샤프비율: {portfolio_stats['sharpe_ratio']:.2f}")
            
            return portfolio_weights
            
        except Exception as e:
            logger.error(f"비중 최적화 실패: {e}")
            # 기본 비중 반환
            equal_weight = 1.0 / len(selected_assets)
            weights = {asset: equal_weight for asset in selected_assets}
            
            return PortfolioWeights(
                weights=weights,
                risk_level=self.risk_level,
                diversification_score=0.5,
                expected_return=0.1,
                expected_risk=0.2,
                sharpe_ratio=0.5
            )
    
    def _apply_weight_constraints(self, weights: Dict[str, float]) -> Dict[str, float]:
        """비중 제약 조건 적용"""
        try:
            # 최대/최소 비중 제약
            for asset in weights:
                weights[asset] = max(self.min_single_weight, 
                                   min(self.max_single_weight, weights[asset]))
            
            # 총합 100% 조정
            total_weight = sum(weights.values())
            if total_weight > 0:
                for asset in weights:
                    weights[asset] /= total_weight
            
            return weights
            
        except Exception as e:
            logger.error(f"비중 제약 조건 적용 실패: {e}")
            return weights
    
    def _calculate_portfolio_stats(
        self, 
        weights: Dict[str, float], 
        asset_metrics: Dict[str, AssetMetrics]
    ) -> Dict[str, float]:
        """포트폴리오 통계 계산"""
        try:
            # 가중 평균 수익률
            expected_return = sum(
                weights.get(asset, 0) * metrics.price_change_30d * 12  # 연간화
                for asset, metrics in asset_metrics.items()
                if asset in weights
            )
            
            # 단순 리스크 추정 (가중 평균 변동성)
            expected_risk = sum(
                weights.get(asset, 0) * metrics.volatility_30d
                for asset, metrics in asset_metrics.items()
                if asset in weights
            )
            
            # 샤프 비율
            sharpe_ratio = expected_return / expected_risk if expected_risk > 0 else 0
            
            return {
                "expected_return": expected_return,
                "expected_risk": expected_risk,
                "sharpe_ratio": sharpe_ratio
            }
            
        except Exception as e:
            logger.error(f"포트폴리오 통계 계산 실패: {e}")
            return {
                "expected_return": 0.1,
                "expected_risk": 0.2,
                "sharpe_ratio": 0.5
            }
    
    def generate_optimal_portfolio(self) -> PortfolioWeights:
        """최적 포트폴리오 생성 (전체 프로세스)"""
        try:
            logger.info("🚀 동적 포트폴리오 최적화 시작")
            
            # 1. 전체 자산 분석
            asset_metrics = self.analyze_all_assets()
            if not asset_metrics:
                logger.error("자산 분석 실패 - 기본 포트폴리오 사용")
                return self._get_default_portfolio()
            
            # 2. 최적 자산 선택
            selected_assets = self.select_optimal_portfolio(asset_metrics)
            if len(selected_assets) < 2:
                logger.error("선택된 자산 부족 - 기본 포트폴리오 사용")
                return self._get_default_portfolio()
            
            # 3. 비중 최적화
            optimal_portfolio = self.optimize_weights(selected_assets, asset_metrics)
            
            logger.info("🎉 동적 포트폴리오 최적화 완료")
            return optimal_portfolio
            
        except Exception as e:
            logger.error(f"포트폴리오 생성 실패: {e}")
            return self._get_default_portfolio()
    
    def _get_default_portfolio(self) -> PortfolioWeights:
        """기본 포트폴리오 반환"""
        default_weights = {
            "BTC": 0.40,
            "ETH": 0.30,
            "XRP": 0.15,
            "SOL": 0.15
        }
        
        return PortfolioWeights(
            weights=default_weights,
            risk_level=self.risk_level,
            diversification_score=0.5,
            expected_return=0.15,
            expected_risk=0.25,
            sharpe_ratio=0.6
        )
    
    def should_rebalance_portfolio(self, current_weights: Dict[str, float]) -> bool:
        """포트폴리오 리밸런싱 필요 여부 판단"""
        try:
            # 새로운 최적 포트폴리오 생성
            optimal_portfolio = self.generate_optimal_portfolio()
            optimal_weights = optimal_portfolio.weights
            
            # 현재 비중과 최적 비중 비교
            total_deviation = 0
            for asset in set(list(current_weights.keys()) + list(optimal_weights.keys())):
                current_weight = current_weights.get(asset, 0)
                optimal_weight = optimal_weights.get(asset, 0)
                total_deviation += abs(current_weight - optimal_weight)
            
            # 10% 이상 차이나면 리밸런싱 필요
            should_rebalance = total_deviation > 0.10
            
            logger.info(f"리밸런싱 검토: 총 편차 {total_deviation:.1%} "
                       f"-> {'필요' if should_rebalance else '불필요'}")
            
            return should_rebalance
            
        except Exception as e:
            logger.error(f"리밸런싱 판단 실패: {e}")
            return False