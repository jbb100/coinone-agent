"""
Risk Parity Model

변동성 기반 리스크 균등 배분 모델
- 동일한 리스크 기여도를 갖도록 자산 배분
- 변동성 역가중 방식
- 상관관계를 고려한 리스크 조정
- 동적 리밸런싱 신호 생성
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import pandas as pd
import numpy as np
from scipy.optimize import minimize
from loguru import logger


@dataclass
class RiskMetrics:
    """리스크 지표"""
    volatility: float
    var_95: float          # 95% VaR
    expected_shortfall: float  # Expected Shortfall (CVaR)
    max_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float


@dataclass
class RiskContribution:
    """리스크 기여도"""
    asset: str
    weight: float
    volatility: float
    risk_contribution: float  # 포트폴리오 리스크에 대한 기여도 (%)
    marginal_risk: float     # 한계 리스크
    component_risk: float    # 구성 요소 리스크


@dataclass
class RiskParityAllocation:
    """리스크 패리티 배분 결과"""
    weights: Dict[str, float]
    risk_contributions: List[RiskContribution]
    portfolio_volatility: float
    total_risk: float
    optimization_success: bool
    convergence_error: float
    created_at: datetime


class RiskParityModel:
    """
    리스크 패리티 모델
    
    모든 자산이 포트폴리오 리스크에 동일하게 기여하도록
    자산 배분을 최적화합니다.
    """
    
    def __init__(self, lookback_period: int = 252):
        """
        Args:
            lookback_period: 리스크 계산 기간 (일)
        """
        self.lookback_period = lookback_period
        self.min_weight = 0.05   # 최소 비중 5%
        self.max_weight = 0.50   # 최대 비중 50%
        
        # 수렴 조건
        self.max_iterations = 1000
        self.tolerance = 1e-8
        
        logger.info(f"RiskParityModel 초기화: 기간 {lookback_period}일")
    
    def calculate_risk_parity_weights(
        self,
        price_data: Dict[str, pd.DataFrame],
        target_assets: List[str]
    ) -> RiskParityAllocation:
        """
        리스크 패리티 가중치 계산
        
        Args:
            price_data: 자산별 가격 데이터
            target_assets: 대상 자산 리스트
            
        Returns:
            리스크 패리티 배분 결과
        """
        try:
            logger.info(f"리스크 패리티 가중치 계산 시작: {target_assets}")
            
            # 수익률 데이터 준비
            returns_data = self._prepare_returns_data(price_data, target_assets)
            if returns_data.empty:
                return self._get_equal_weight_fallback(target_assets)
            
            # 공분산 행렬 계산
            cov_matrix = returns_data.cov().values * 252  # 연화
            
            # 변동성 계산
            volatilities = np.sqrt(np.diag(cov_matrix))
            
            # 초기 가중치 (변동성 역가중)
            inverse_vol_weights = (1 / volatilities) / np.sum(1 / volatilities)
            
            # 리스크 패리티 최적화
            optimal_weights = self._optimize_risk_parity(
                cov_matrix, initial_weights=inverse_vol_weights
            )
            
            # 결과 검증
            if optimal_weights is None or np.any(optimal_weights < 0):
                logger.warning("최적화 실패, 변동성 역가중 방식 사용")
                optimal_weights = inverse_vol_weights
                optimization_success = False
                convergence_error = float('inf')
            else:
                optimization_success = True
                convergence_error = self._calculate_risk_parity_error(cov_matrix, optimal_weights)
            
            # 가중치 딕셔너리 생성
            weights_dict = dict(zip(target_assets, optimal_weights))
            
            # 리스크 기여도 계산
            risk_contributions = self._calculate_risk_contributions(
                weights_dict, cov_matrix, target_assets
            )
            
            # 포트폴리오 변동성
            portfolio_vol = np.sqrt(optimal_weights.T @ cov_matrix @ optimal_weights)
            
            allocation = RiskParityAllocation(
                weights=weights_dict,
                risk_contributions=risk_contributions,
                portfolio_volatility=portfolio_vol,
                total_risk=np.sum([rc.risk_contribution for rc in risk_contributions]),
                optimization_success=optimization_success,
                convergence_error=convergence_error,
                created_at=datetime.now()
            )
            
            logger.info(f"리스크 패리티 계산 완료: 포트폴리오 변동성 {portfolio_vol:.1%}")
            return allocation
            
        except Exception as e:
            logger.error(f"리스크 패리티 계산 실패: {e}")
            return self._get_equal_weight_fallback(target_assets)
    
    def _prepare_returns_data(
        self, 
        price_data: Dict[str, pd.DataFrame], 
        assets: List[str]
    ) -> pd.DataFrame:
        """수익률 데이터 준비"""
        
        returns_dict = {}
        
        for asset in assets:
            if asset in price_data and len(price_data[asset]) > self.lookback_period:
                # 최근 기간 가격 데이터
                prices = price_data[asset]['Close'].tail(self.lookback_period)
                
                # 일일 수익률 계산
                returns = prices.pct_change().dropna()
                
                if len(returns) > 50:  # 최소 50일 데이터
                    returns_dict[asset] = returns
        
        if not returns_dict:
            logger.error("충분한 수익률 데이터가 없습니다")
            return pd.DataFrame()
        
        # 공통 날짜 인덱스로 정렬
        returns_df = pd.DataFrame(returns_dict)
        returns_df = returns_df.dropna()
        
        logger.debug(f"수익률 데이터 준비 완료: {len(returns_df)}일, {len(returns_df.columns)}개 자산")
        return returns_df
    
    def _optimize_risk_parity(
        self, 
        cov_matrix: np.ndarray, 
        initial_weights: np.ndarray
    ) -> Optional[np.ndarray]:
        """리스크 패리티 최적화"""
        
        n_assets = len(initial_weights)
        
        # 목적 함수: 리스크 기여도 분산 최소화
        def objective(weights):
            return self._risk_parity_objective(weights, cov_matrix)
        
        # 제약 조건
        constraints = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0}  # 가중치 합 = 1
        ]
        
        # 경계 조건 (최소/최대 비중)
        bounds = [(self.min_weight, self.max_weight) for _ in range(n_assets)]
        
        try:
            # 최적화 실행
            result = minimize(
                objective,
                initial_weights,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints,
                options={
                    'maxiter': self.max_iterations,
                    'ftol': self.tolerance
                }
            )
            
            if result.success:
                return result.x
            else:
                logger.warning(f"최적화 수렴 실패: {result.message}")
                return None
                
        except Exception as e:
            logger.error(f"최적화 실행 실패: {e}")
            return None
    
    def _risk_parity_objective(self, weights: np.ndarray, cov_matrix: np.ndarray) -> float:
        """리스크 패리티 목적 함수"""
        
        # 포트폴리오 변동성
        portfolio_var = weights.T @ cov_matrix @ weights
        portfolio_vol = np.sqrt(portfolio_var)
        
        if portfolio_vol == 0:
            return float('inf')
        
        # 각 자산의 한계 리스크 기여도
        marginal_contrib = cov_matrix @ weights / portfolio_vol
        
        # 각 자산의 리스크 기여도
        risk_contrib = weights * marginal_contrib
        
        # 목표: 모든 자산이 동일한 리스크 기여도를 가져야 함
        target_contrib = portfolio_vol / len(weights)  # 동일 분배
        
        # 리스크 기여도 편차의 제곱합 (최소화 목표)
        deviation_squared = np.sum((risk_contrib - target_contrib) ** 2)
        
        return deviation_squared
    
    def _calculate_risk_parity_error(
        self, 
        cov_matrix: np.ndarray, 
        weights: np.ndarray
    ) -> float:
        """리스크 패리티 오차 계산"""
        
        portfolio_var = weights.T @ cov_matrix @ weights
        portfolio_vol = np.sqrt(portfolio_var)
        
        if portfolio_vol == 0:
            return float('inf')
        
        # 리스크 기여도 계산
        marginal_contrib = cov_matrix @ weights / portfolio_vol
        risk_contrib = weights * marginal_contrib
        
        # 리스크 기여도의 표준편차 (낮을수록 좋음)
        return np.std(risk_contrib)
    
    def _calculate_risk_contributions(
        self,
        weights: Dict[str, float],
        cov_matrix: np.ndarray,
        assets: List[str]
    ) -> List[RiskContribution]:
        """리스크 기여도 상세 계산"""
        
        weight_array = np.array([weights[asset] for asset in assets])
        
        # 포트폴리오 변동성
        portfolio_var = weight_array.T @ cov_matrix @ weight_array
        portfolio_vol = np.sqrt(portfolio_var)
        
        risk_contributions = []
        
        for i, asset in enumerate(assets):
            # 개별 자산 변동성
            asset_vol = np.sqrt(cov_matrix[i, i])
            
            # 한계 리스크 기여도
            marginal_risk = (cov_matrix[i, :] @ weight_array) / portfolio_vol if portfolio_vol > 0 else 0
            
            # 구성 요소 리스크
            component_risk = weights[asset] * marginal_risk
            
            # 리스크 기여도 (%)
            risk_contrib_pct = (component_risk / portfolio_vol * 100) if portfolio_vol > 0 else 0
            
            risk_contribution = RiskContribution(
                asset=asset,
                weight=weights[asset],
                volatility=asset_vol,
                risk_contribution=risk_contrib_pct,
                marginal_risk=marginal_risk,
                component_risk=component_risk
            )
            
            risk_contributions.append(risk_contribution)
        
        return risk_contributions
    
    def calculate_portfolio_risk_metrics(
        self, 
        returns_data: pd.DataFrame, 
        weights: Dict[str, float]
    ) -> RiskMetrics:
        """포트폴리오 리스크 지표 계산"""
        
        try:
            # 가중치 배열
            weight_array = np.array([weights.get(col, 0) for col in returns_data.columns])
            
            # 포트폴리오 수익률
            portfolio_returns = returns_data @ weight_array
            
            if len(portfolio_returns) == 0:
                return self._get_default_risk_metrics()
            
            # 기본 통계
            annual_return = portfolio_returns.mean() * 252
            annual_volatility = portfolio_returns.std() * np.sqrt(252)
            
            # VaR 95%
            var_95 = np.percentile(portfolio_returns, 5) * np.sqrt(252)
            
            # Expected Shortfall (CVaR)
            below_var = portfolio_returns[portfolio_returns <= np.percentile(portfolio_returns, 5)]
            expected_shortfall = below_var.mean() * np.sqrt(252) if len(below_var) > 0 else var_95
            
            # 최대 손실폭
            cumulative_returns = (1 + portfolio_returns).cumprod()
            rolling_max = cumulative_returns.expanding().max()
            drawdowns = (cumulative_returns - rolling_max) / rolling_max
            max_drawdown = drawdowns.min()
            
            # 샤프 비율 (무위험 수익률 = 0 가정)
            sharpe_ratio = annual_return / annual_volatility if annual_volatility > 0 else 0
            
            # 소르티노 비율 (하방 편차만 고려)
            downside_returns = portfolio_returns[portfolio_returns < 0]
            downside_volatility = downside_returns.std() * np.sqrt(252) if len(downside_returns) > 0 else annual_volatility
            sortino_ratio = annual_return / downside_volatility if downside_volatility > 0 else 0
            
            # 칼마 비율 (연수익률 / 최대손실폭)
            calmar_ratio = annual_return / abs(max_drawdown) if max_drawdown < 0 else 0
            
            return RiskMetrics(
                volatility=annual_volatility,
                var_95=var_95,
                expected_shortfall=expected_shortfall,
                max_drawdown=max_drawdown,
                sharpe_ratio=sharpe_ratio,
                sortino_ratio=sortino_ratio,
                calmar_ratio=calmar_ratio
            )
            
        except Exception as e:
            logger.error(f"리스크 지표 계산 실패: {e}")
            return self._get_default_risk_metrics()
    
    def _get_default_risk_metrics(self) -> RiskMetrics:
        """기본 리스크 지표 (오류 시)"""
        return RiskMetrics(
            volatility=0.0,
            var_95=0.0,
            expected_shortfall=0.0,
            max_drawdown=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            calmar_ratio=0.0
        )
    
    def _get_equal_weight_fallback(self, assets: List[str]) -> RiskParityAllocation:
        """동일 가중치 폴백"""
        
        equal_weight = 1.0 / len(assets)
        weights = {asset: equal_weight for asset in assets}
        
        # 더미 리스크 기여도
        risk_contributions = [
            RiskContribution(
                asset=asset,
                weight=equal_weight,
                volatility=0.5,  # 기본값
                risk_contribution=100.0 / len(assets),
                marginal_risk=0.0,
                component_risk=0.0
            ) for asset in assets
        ]
        
        return RiskParityAllocation(
            weights=weights,
            risk_contributions=risk_contributions,
            portfolio_volatility=0.5,
            total_risk=100.0,
            optimization_success=False,
            convergence_error=float('inf'),
            created_at=datetime.now()
        )
    
    def compare_with_market_cap_weights(
        self,
        risk_parity_weights: Dict[str, float],
        market_cap_weights: Dict[str, float],
        returns_data: pd.DataFrame
    ) -> Dict[str, Any]:
        """리스크 패리티와 시가총액 가중 비교"""
        
        try:
            # 리스크 패리티 포트폴리오 지표
            rp_metrics = self.calculate_portfolio_risk_metrics(returns_data, risk_parity_weights)
            
            # 시가총액 가중 포트폴리오 지표
            mc_metrics = self.calculate_portfolio_risk_metrics(returns_data, market_cap_weights)
            
            # 비교 결과
            comparison = {
                "risk_parity": {
                    "volatility": rp_metrics.volatility,
                    "sharpe_ratio": rp_metrics.sharpe_ratio,
                    "max_drawdown": rp_metrics.max_drawdown,
                    "weights": risk_parity_weights
                },
                "market_cap": {
                    "volatility": mc_metrics.volatility,
                    "sharpe_ratio": mc_metrics.sharpe_ratio,
                    "max_drawdown": mc_metrics.max_drawdown,
                    "weights": market_cap_weights
                },
                "improvement": {
                    "volatility_reduction": (mc_metrics.volatility - rp_metrics.volatility) / mc_metrics.volatility if mc_metrics.volatility > 0 else 0,
                    "sharpe_improvement": rp_metrics.sharpe_ratio - mc_metrics.sharpe_ratio,
                    "drawdown_reduction": (mc_metrics.max_drawdown - rp_metrics.max_drawdown) / abs(mc_metrics.max_drawdown) if mc_metrics.max_drawdown < 0 else 0
                }
            }
            
            return comparison
            
        except Exception as e:
            logger.error(f"포트폴리오 비교 실패: {e}")
            return {}
    
    def generate_rebalancing_signals(
        self,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
        threshold: float = 0.05
    ) -> Dict[str, Any]:
        """리밸런싱 신호 생성"""
        
        signals = {
            "rebalance_needed": False,
            "urgency": "low",
            "weight_deviations": {},
            "suggested_trades": {},
            "total_turnover": 0.0
        }
        
        try:
            max_deviation = 0.0
            total_abs_deviation = 0.0
            
            for asset in target_weights:
                current = current_weights.get(asset, 0)
                target = target_weights[asset]
                deviation = abs(current - target)
                
                signals["weight_deviations"][asset] = {
                    "current": current,
                    "target": target, 
                    "deviation": deviation,
                    "deviation_pct": deviation / target if target > 0 else 0
                }
                
                max_deviation = max(max_deviation, deviation)
                total_abs_deviation += deviation
                
                # 거래 제안
                if deviation > threshold:
                    trade_amount = target - current
                    signals["suggested_trades"][asset] = {
                        "action": "buy" if trade_amount > 0 else "sell",
                        "amount_change": trade_amount,
                        "priority": deviation / target if target > 0 else 0
                    }
            
            # 총 회전율
            signals["total_turnover"] = total_abs_deviation / 2  # 매수/매도 합산 조정
            
            # 리밸런싱 필요성 및 긴급도
            if max_deviation > threshold:
                signals["rebalance_needed"] = True
                
                if max_deviation > 0.15:  # 15% 이상
                    signals["urgency"] = "high"
                elif max_deviation > 0.10:  # 10% 이상
                    signals["urgency"] = "medium"
                else:
                    signals["urgency"] = "low"
            
            return signals
            
        except Exception as e:
            logger.error(f"리밸런싱 신호 생성 실패: {e}")
            return signals
    
    def calculate_risk_adjusted_returns(
        self, 
        returns_data: pd.DataFrame, 
        weights: Dict[str, float],
        benchmark_returns: Optional[pd.Series] = None
    ) -> Dict[str, float]:
        """리스크 조정 수익률 지표 계산"""
        
        try:
            weight_array = np.array([weights.get(col, 0) for col in returns_data.columns])
            portfolio_returns = returns_data @ weight_array
            
            if len(portfolio_returns) == 0:
                return {}
            
            # 기본 지표
            annual_return = portfolio_returns.mean() * 252
            annual_volatility = portfolio_returns.std() * np.sqrt(252)
            
            metrics = {
                "annual_return": annual_return,
                "annual_volatility": annual_volatility,
                "sharpe_ratio": annual_return / annual_volatility if annual_volatility > 0 else 0
            }
            
            # 벤치마크 비교 (제공된 경우)
            if benchmark_returns is not None and len(benchmark_returns) > 0:
                # 공통 기간 추출
                common_dates = portfolio_returns.index.intersection(benchmark_returns.index)
                if len(common_dates) > 0:
                    port_common = portfolio_returns.loc[common_dates]
                    bench_common = benchmark_returns.loc[common_dates]
                    
                    # 초과 수익률
                    excess_returns = port_common - bench_common
                    annual_excess = excess_returns.mean() * 252
                    tracking_error = excess_returns.std() * np.sqrt(252)
                    
                    metrics.update({
                        "annual_excess_return": annual_excess,
                        "tracking_error": tracking_error,
                        "information_ratio": annual_excess / tracking_error if tracking_error > 0 else 0,
                        "beta": np.cov(port_common, bench_common)[0, 1] / np.var(bench_common) if np.var(bench_common) > 0 else 1,
                        "alpha": annual_return - (np.mean(bench_common) * 252 * metrics.get("beta", 1))
                    })
            
            return metrics
            
        except Exception as e:
            logger.error(f"리스크 조정 수익률 계산 실패: {e}")
            return {}


# 유틸리티 함수들
def calculate_diversification_ratio(weights: np.ndarray, cov_matrix: np.ndarray) -> float:
    """다각화 비율 계산"""
    try:
        # 개별 자산 가중 평균 변동성
        individual_vols = np.sqrt(np.diag(cov_matrix))
        weighted_avg_vol = weights @ individual_vols
        
        # 포트폴리오 변동성
        portfolio_vol = np.sqrt(weights.T @ cov_matrix @ weights)
        
        # 다각화 비율 = 가중평균 변동성 / 포트폴리오 변동성
        return weighted_avg_vol / portfolio_vol if portfolio_vol > 0 else 1.0
        
    except:
        return 1.0


def calculate_maximum_diversification_weights(cov_matrix: np.ndarray) -> np.ndarray:
    """최대 다각화 가중치 계산"""
    try:
        # 변동성 벡터
        vol_vector = np.sqrt(np.diag(cov_matrix))
        
        # 역변동성 가중치
        inv_vol_weights = (1 / vol_vector) / np.sum(1 / vol_vector)
        
        return inv_vol_weights
        
    except:
        n = len(cov_matrix)
        return np.ones(n) / n  # 동일 가중치 폴백