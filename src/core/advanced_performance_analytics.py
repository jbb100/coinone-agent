"""
Advanced Performance Analytics

고도화된 성과 측정 시스템
- 다양한 리스크 조정 수익률 지표
- 벤치마크 대비 성과 분석
- 드로우다운 및 회복 분석
- 포트폴리오 기여도 분석
- 스타일 분석 및 팩터 익스포저
- 성과 귀인 분석
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import pandas as pd
import numpy as np
from scipy import stats
from loguru import logger


@dataclass
class PerformanceMetrics:
    """성과 지표"""
    # 기본 수익률 지표
    total_return: float
    annual_return: float
    daily_returns_mean: float
    daily_returns_std: float
    
    # 리스크 조정 수익률
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    omega_ratio: float
    
    # 리스크 지표  
    volatility: float
    max_drawdown: float
    var_95: float
    cvar_95: float
    skewness: float
    kurtosis: float
    
    # 일관성 지표 (기본값이 없는 필드들)
    hit_rate: float              # 양의 수익률 비율
    profit_factor: float         # 총 이익 / 총 손실
    expectancy: float            # 기대값
    consistency_score: float     # 일관성 점수
    
    # 시간 기반 지표
    recovery_factor: float       # 총수익 / 최대낙폭
    sterling_ratio: float        # 연수익 / 평균낙폭
    burke_ratio: float          # 연수익 / sqrt(낙폭제곱합)
    
    period_start: datetime
    period_end: datetime
    
    # 벤치마크 대비 (기본값이 있는 필드들은 마지막에)
    information_ratio: Optional[float] = None
    alpha: Optional[float] = None
    beta: Optional[float] = None
    tracking_error: Optional[float] = None
    excess_return: Optional[float] = None


@dataclass
class DrawdownAnalysis:
    """드로우다운 분석"""
    max_drawdown: float
    max_drawdown_duration: int   # 일수
    current_drawdown: float
    drawdown_periods: List[Dict[str, Any]]  # 개별 드로우다운 기간들
    recovery_times: List[int]    # 회복 시간들 (일)
    avg_recovery_time: float
    max_recovery_time: int
    
    # 드로우다운 통계
    drawdown_frequency: float    # 연간 드로우다운 발생 빈도
    avg_drawdown_depth: float    # 평균 드로우다운 깊이
    pain_index: float           # 드로우다운 고통 지수


@dataclass
class AttributionAnalysis:
    """성과 귀인 분석"""
    asset_contributions: Dict[str, float]    # 자산별 기여도
    allocation_effect: float                 # 자산 배분 효과
    selection_effect: float                  # 종목 선택 효과
    interaction_effect: float                # 상호작용 효과
    timing_effect: float                     # 타이밍 효과
    rebalancing_alpha: float                 # 리밸런싱 알파


@dataclass
class FactorExposure:
    """팩터 익스포저"""
    market_beta: float           # 시장 베타
    momentum_exposure: float     # 모멘텀 익스포저
    mean_reversion_exposure: float  # 평균회귀 익스포저
    volatility_exposure: float   # 변동성 익스포저
    carry_exposure: float        # 캐리 익스포저
    r_squared: float            # 설명력


class AdvancedPerformanceAnalytics:
    """
    고도화된 성과 분석기
    
    포트폴리오의 성과를 다각도로 분석하고 
    심층적인 인사이트를 제공합니다.
    """
    
    def __init__(self):
        """성과 분석기 초기화"""
        
        # 분석 설정
        self.risk_free_rate = 0.02  # 연 2% 무위험 수익률
        self.trading_days_per_year = 252
        
        # 벤치마크 설정
        self.benchmarks = {
            "btc": "Bitcoin",
            "eth": "Ethereum", 
            "crypto_index": "Crypto Index",
            "traditional_60_40": "60/40 Portfolio"
        }
        
        logger.info("Advanced Performance Analytics 초기화 완료")
    
    def calculate_comprehensive_metrics(
        self,
        portfolio_returns: pd.Series,
        benchmark_returns: Optional[pd.Series] = None,
        portfolio_values: Optional[pd.Series] = None
    ) -> PerformanceMetrics:
        """종합 성과 지표 계산"""
        
        try:
            # 기본 수익률 통계
            total_return = (1 + portfolio_returns).prod() - 1
            periods_per_year = self._get_periods_per_year(portfolio_returns)
            annual_return = (1 + portfolio_returns.mean()) ** periods_per_year - 1
            annual_volatility = portfolio_returns.std() * np.sqrt(periods_per_year)
            
            # 리스크 조정 수익률
            sharpe = self._calculate_sharpe_ratio(portfolio_returns, periods_per_year)
            sortino = self._calculate_sortino_ratio(portfolio_returns, periods_per_year)
            calmar = self._calculate_calmar_ratio(portfolio_returns, portfolio_values)
            omega = self._calculate_omega_ratio(portfolio_returns)
            
            # VaR 및 CVaR
            var_95 = np.percentile(portfolio_returns, 5)
            cvar_95 = portfolio_returns[portfolio_returns <= var_95].mean()
            
            # 최대 손실폭
            if portfolio_values is not None:
                max_dd = self._calculate_max_drawdown(portfolio_values)
            else:
                max_dd = self._calculate_max_drawdown_from_returns(portfolio_returns)
            
            # 분포 특성
            skew = stats.skew(portfolio_returns)
            kurt = stats.kurtosis(portfolio_returns)
            
            # 거래 통계
            hit_rate = (portfolio_returns > 0).mean()
            positive_returns = portfolio_returns[portfolio_returns > 0]
            negative_returns = portfolio_returns[portfolio_returns < 0]
            
            if len(negative_returns) > 0:
                profit_factor = positive_returns.sum() / abs(negative_returns.sum())
            else:
                profit_factor = float('inf')
            
            expectancy = portfolio_returns.mean()
            consistency_score = self._calculate_consistency_score(portfolio_returns)
            
            # 시간 기반 지표
            recovery_factor = total_return / abs(max_dd) if max_dd != 0 else float('inf')
            sterling_ratio = annual_return / abs(max_dd) if max_dd != 0 else float('inf')
            burke_ratio = self._calculate_burke_ratio(portfolio_returns, portfolio_values)
            
            # 벤치마크 대비 지표
            alpha, beta, tracking_error, excess_return, info_ratio = None, None, None, None, None
            if benchmark_returns is not None:
                alpha, beta = self._calculate_alpha_beta(portfolio_returns, benchmark_returns)
                tracking_error = (portfolio_returns - benchmark_returns).std() * np.sqrt(periods_per_year)
                excess_return = annual_return - ((1 + benchmark_returns.mean()) ** periods_per_year - 1)
                if tracking_error > 0:
                    info_ratio = excess_return / tracking_error
            
            metrics = PerformanceMetrics(
                total_return=total_return,
                annual_return=annual_return,
                daily_returns_mean=portfolio_returns.mean(),
                daily_returns_std=portfolio_returns.std(),
                sharpe_ratio=sharpe,
                sortino_ratio=sortino,
                calmar_ratio=calmar,
                omega_ratio=omega,
                information_ratio=info_ratio,
                volatility=annual_volatility,
                max_drawdown=max_dd,
                var_95=var_95,
                cvar_95=cvar_95,
                skewness=skew,
                kurtosis=kurt,
                alpha=alpha,
                beta=beta,
                tracking_error=tracking_error,
                excess_return=excess_return,
                hit_rate=hit_rate,
                profit_factor=profit_factor,
                expectancy=expectancy,
                consistency_score=consistency_score,
                recovery_factor=recovery_factor,
                sterling_ratio=sterling_ratio,
                burke_ratio=burke_ratio,
                period_start=portfolio_returns.index[0],
                period_end=portfolio_returns.index[-1]
            )
            
            logger.info(f"성과 지표 계산 완료: 샤프 {sharpe:.2f}, 최대낙폭 {max_dd:.1%}")
            return metrics
            
        except Exception as e:
            logger.error(f"성과 지표 계산 실패: {e}")
            raise
    
    def analyze_drawdowns(
        self,
        portfolio_values: pd.Series,
        threshold: float = 0.05
    ) -> DrawdownAnalysis:
        """드로우다운 심층 분석"""
        
        try:
            # 누적 최고점 계산
            cumulative_max = portfolio_values.expanding().max()
            drawdowns = (portfolio_values - cumulative_max) / cumulative_max
            
            # 현재 드로우다운
            current_drawdown = drawdowns.iloc[-1]
            
            # 최대 드로우다운
            max_drawdown = drawdowns.min()
            max_dd_idx = drawdowns.idxmin()
            
            # 드로우다운 기간들 식별
            drawdown_periods = []
            recovery_times = []
            in_drawdown = False
            dd_start = None
            dd_peak = None
            
            for date, dd in drawdowns.items():
                if dd < -threshold and not in_drawdown:  # 드로우다운 시작
                    in_drawdown = True
                    dd_start = date
                    dd_peak = dd
                    dd_peak_date = date
                elif dd < dd_peak and in_drawdown:  # 드로우다운 심화
                    dd_peak = dd
                    dd_peak_date = date
                elif dd >= -0.001 and in_drawdown:  # 드로우다운 회복
                    in_drawdown = False
                    dd_end = date
                    recovery_time = (dd_end - dd_peak_date).days
                    
                    drawdown_periods.append({
                        "start_date": dd_start,
                        "peak_date": dd_peak_date,
                        "end_date": dd_end,
                        "max_drawdown": dd_peak,
                        "duration_days": (dd_end - dd_start).days,
                        "recovery_days": recovery_time
                    })
                    
                    recovery_times.append(recovery_time)
            
            # 최대 드로우다운 지속 기간
            max_dd_period = None
            for period in drawdown_periods:
                if abs(period["max_drawdown"] - max_drawdown) < 0.001:
                    max_dd_period = period
                    break
            
            max_dd_duration = max_dd_period["duration_days"] if max_dd_period else 0
            
            # 통계 계산
            avg_recovery_time = np.mean(recovery_times) if recovery_times else 0
            max_recovery_time = max(recovery_times) if recovery_times else 0
            
            # 드로우다운 빈도 (연간)
            total_days = (drawdowns.index[-1] - drawdowns.index[0]).days
            dd_frequency = len(drawdown_periods) / (total_days / 365.25) if total_days > 0 else 0
            
            # 평균 드로우다운 깊이
            avg_dd_depth = np.mean([p["max_drawdown"] for p in drawdown_periods]) if drawdown_periods else 0
            
            # 고통 지수 (Pain Index) - 드로우다운의 시간 가중 평균
            pain_index = (drawdowns[drawdowns < 0].abs().sum() / len(drawdowns)) if len(drawdowns) > 0 else 0
            
            return DrawdownAnalysis(
                max_drawdown=max_drawdown,
                max_drawdown_duration=max_dd_duration,
                current_drawdown=current_drawdown,
                drawdown_periods=drawdown_periods,
                recovery_times=recovery_times,
                avg_recovery_time=avg_recovery_time,
                max_recovery_time=max_recovery_time,
                drawdown_frequency=dd_frequency,
                avg_drawdown_depth=avg_dd_depth,
                pain_index=pain_index
            )
            
        except Exception as e:
            logger.error(f"드로우다운 분석 실패: {e}")
            raise
    
    def perform_attribution_analysis(
        self,
        portfolio_returns: pd.Series,
        asset_returns: Dict[str, pd.Series],
        portfolio_weights: Dict[str, pd.Series],
        benchmark_returns: Optional[pd.Series] = None
    ) -> AttributionAnalysis:
        """성과 귀인 분석"""
        
        try:
            asset_contributions = {}
            
            # 자산별 기여도 계산
            for asset, returns in asset_returns.items():
                if asset in portfolio_weights:
                    weights = portfolio_weights[asset]
                    # 시간에 따른 가중 수익률 기여도
                    contribution = (weights * returns).sum()
                    asset_contributions[asset] = contribution
            
            # 전체 성과 분해
            allocation_effect = 0.0
            selection_effect = 0.0
            interaction_effect = 0.0
            timing_effect = 0.0
            rebalancing_alpha = 0.0
            
            if benchmark_returns is not None:
                # 벤치마크와 비교하여 각 효과 계산
                # 자산 배분 효과: (포트폴리오 가중치 - 벤치마크 가중치) × 벤치마크 수익률
                # 종목 선택 효과: 벤치마크 가중치 × (자산 수익률 - 벤치마크 수익률)
                # 상호작용 효과: (포트폴리오 가중치 - 벤치마크 가중치) × (자산 수익률 - 벤치마크 수익률)
                
                # 간단한 계산 (실제로는 더 복잡한 로직 필요)
                total_portfolio_return = portfolio_returns.sum()
                total_benchmark_return = benchmark_returns.sum()
                
                # 리밸런싱 알파 계산 (매월 리밸런싱 효과)
                rebalancing_alpha = self._calculate_rebalancing_alpha(
                    portfolio_returns, asset_returns, portfolio_weights
                )
            
            return AttributionAnalysis(
                asset_contributions=asset_contributions,
                allocation_effect=allocation_effect,
                selection_effect=selection_effect,
                interaction_effect=interaction_effect,
                timing_effect=timing_effect,
                rebalancing_alpha=rebalancing_alpha
            )
            
        except Exception as e:
            logger.error(f"성과 귀인 분석 실패: {e}")
            raise
    
    def analyze_factor_exposure(
        self,
        portfolio_returns: pd.Series,
        market_returns: pd.Series,
        momentum_factor: Optional[pd.Series] = None,
        volatility_factor: Optional[pd.Series] = None
    ) -> FactorExposure:
        """팩터 익스포저 분석"""
        
        try:
            # 시장 베타 계산
            market_beta = np.cov(portfolio_returns, market_returns)[0, 1] / np.var(market_returns)
            
            # 다중 회귀 분석을 위한 팩터들
            factors = {"market": market_returns}
            
            if momentum_factor is not None:
                factors["momentum"] = momentum_factor
            if volatility_factor is not None:
                factors["volatility"] = volatility_factor
            
            # 간단한 팩터 익스포저 계산 (실제로는 더 정교한 모델 필요)
            momentum_exposure = 0.0
            mean_reversion_exposure = 0.0
            volatility_exposure = 0.0
            carry_exposure = 0.0
            
            if momentum_factor is not None:
                momentum_exposure = np.corrcoef(portfolio_returns, momentum_factor)[0, 1]
            
            # 평균회귀 익스포저 (수익률의 자기상관)
            if len(portfolio_returns) > 1:
                mean_reversion_exposure = -np.corrcoef(
                    portfolio_returns[:-1], portfolio_returns[1:]
                )[0, 1]
            
            # 변동성 익스포저 (롤링 변동성과의 상관관계)
            rolling_vol = portfolio_returns.rolling(window=20).std()
            if not rolling_vol.isna().all():
                volatility_exposure = np.corrcoef(
                    portfolio_returns[19:], rolling_vol[19:]
                )[0, 1]
            
            # R-squared 계산
            correlation_with_market = np.corrcoef(portfolio_returns, market_returns)[0, 1]
            r_squared = correlation_with_market ** 2
            
            return FactorExposure(
                market_beta=market_beta,
                momentum_exposure=momentum_exposure,
                mean_reversion_exposure=mean_reversion_exposure,
                volatility_exposure=volatility_exposure,
                carry_exposure=carry_exposure,
                r_squared=r_squared
            )
            
        except Exception as e:
            logger.error(f"팩터 익스포저 분석 실패: {e}")
            raise
    
    def calculate_rolling_metrics(
        self,
        portfolio_returns: pd.Series,
        window_days: int = 252,
        metrics: List[str] = ["sharpe", "volatility", "max_drawdown"]
    ) -> pd.DataFrame:
        """롤링 성과 지표 계산"""
        
        try:
            rolling_metrics = pd.DataFrame(index=portfolio_returns.index)
            
            for metric in metrics:
                if metric == "sharpe":
                    rolling_metrics[metric] = portfolio_returns.rolling(
                        window=window_days
                    ).apply(
                        lambda x: self._calculate_sharpe_ratio(x, 252) if len(x) == window_days else np.nan
                    )
                elif metric == "volatility":
                    rolling_metrics[metric] = portfolio_returns.rolling(
                        window=window_days
                    ).std() * np.sqrt(252)
                elif metric == "max_drawdown":
                    rolling_metrics[metric] = portfolio_returns.rolling(
                        window=window_days
                    ).apply(
                        lambda x: self._calculate_max_drawdown_from_returns(x) if len(x) == window_days else np.nan
                    )
            
            return rolling_metrics.dropna()
            
        except Exception as e:
            logger.error(f"롤링 지표 계산 실패: {e}")
            return pd.DataFrame()
    
    def generate_performance_report(
        self,
        portfolio_returns: pd.Series,
        portfolio_values: Optional[pd.Series] = None,
        benchmark_returns: Optional[pd.Series] = None,
        asset_returns: Optional[Dict[str, pd.Series]] = None,
        portfolio_weights: Optional[Dict[str, pd.Series]] = None
    ) -> Dict[str, Any]:
        """종합 성과 보고서 생성"""
        
        try:
            report = {
                "analysis_date": datetime.now(),
                "period": {
                    "start": portfolio_returns.index[0],
                    "end": portfolio_returns.index[-1],
                    "days": len(portfolio_returns)
                }
            }
            
            # 기본 성과 지표
            report["performance_metrics"] = self.calculate_comprehensive_metrics(
                portfolio_returns, benchmark_returns, portfolio_values
            )
            
            # 드로우다운 분석
            if portfolio_values is not None:
                report["drawdown_analysis"] = self.analyze_drawdowns(portfolio_values)
            
            # 성과 귀인 분석
            if asset_returns and portfolio_weights:
                report["attribution_analysis"] = self.perform_attribution_analysis(
                    portfolio_returns, asset_returns, portfolio_weights, benchmark_returns
                )
            
            # 팩터 익스포저
            if benchmark_returns is not None:
                report["factor_exposure"] = self.analyze_factor_exposure(
                    portfolio_returns, benchmark_returns
                )
            
            # 롤링 지표
            if len(portfolio_returns) > 252:
                report["rolling_metrics"] = self.calculate_rolling_metrics(portfolio_returns)
            
            # 성과 요약 및 인사이트
            report["summary"] = self._generate_performance_summary(report)
            
            logger.info("종합 성과 보고서 생성 완료")
            return report
            
        except Exception as e:
            logger.error(f"성과 보고서 생성 실패: {e}")
            return {"error": str(e)}
    
    # 헬퍼 메서드들
    def _get_periods_per_year(self, returns: pd.Series) -> float:
        """연간 기간 수 계산"""
        if len(returns) < 2:
            return 252
        
        freq = pd.infer_freq(returns.index)
        if freq is None:
            # 평균 간격 계산
            avg_diff = (returns.index[-1] - returns.index[0]) / (len(returns) - 1)
            return 365.25 / avg_diff.days if avg_diff.days > 0 else 252
        
        freq_map = {
            'D': 252, 'B': 252,  # 일간
            'W': 52,             # 주간
            'M': 12,             # 월간
            'Q': 4,              # 분기
            'Y': 1               # 연간
        }
        
        return freq_map.get(freq[0], 252)
    
    def _calculate_sharpe_ratio(self, returns: pd.Series, periods_per_year: float) -> float:
        """샤프 비율 계산"""
        if returns.std() == 0:
            return 0.0
        
        excess_returns = returns.mean() - (self.risk_free_rate / periods_per_year)
        return (excess_returns * periods_per_year) / (returns.std() * np.sqrt(periods_per_year))
    
    def _calculate_sortino_ratio(self, returns: pd.Series, periods_per_year: float) -> float:
        """소르티노 비율 계산"""
        downside_returns = returns[returns < 0]
        if len(downside_returns) == 0:
            return float('inf')
        
        downside_std = downside_returns.std()
        if downside_std == 0:
            return float('inf')
        
        excess_returns = returns.mean() - (self.risk_free_rate / periods_per_year)
        return (excess_returns * periods_per_year) / (downside_std * np.sqrt(periods_per_year))
    
    def _calculate_calmar_ratio(
        self, 
        returns: pd.Series, 
        values: Optional[pd.Series] = None
    ) -> float:
        """칼마 비율 계산"""
        annual_return = (1 + returns.mean()) ** self._get_periods_per_year(returns) - 1
        
        if values is not None:
            max_dd = abs(self._calculate_max_drawdown(values))
        else:
            max_dd = abs(self._calculate_max_drawdown_from_returns(returns))
        
        if max_dd == 0:
            return float('inf')
        
        return annual_return / max_dd
    
    def _calculate_omega_ratio(self, returns: pd.Series, threshold: float = 0.0) -> float:
        """오메가 비율 계산"""
        gains = returns[returns > threshold] - threshold
        losses = threshold - returns[returns <= threshold]
        
        if losses.sum() == 0:
            return float('inf')
        
        return gains.sum() / losses.sum()
    
    def _calculate_max_drawdown(self, values: pd.Series) -> float:
        """최대 드로우다운 계산 (가치 시리즈)"""
        cumulative_max = values.expanding().max()
        drawdowns = (values - cumulative_max) / cumulative_max
        return drawdowns.min()
    
    def _calculate_max_drawdown_from_returns(self, returns: pd.Series) -> float:
        """최대 드로우다운 계산 (수익률 시리즈)"""
        cumulative = (1 + returns).cumprod()
        cumulative_max = cumulative.expanding().max()
        drawdowns = (cumulative - cumulative_max) / cumulative_max
        return drawdowns.min()
    
    def _calculate_alpha_beta(
        self, 
        portfolio_returns: pd.Series, 
        benchmark_returns: pd.Series
    ) -> Tuple[float, float]:
        """알파와 베타 계산"""
        if len(portfolio_returns) != len(benchmark_returns):
            # 공통 인덱스로 맞춤
            common_idx = portfolio_returns.index.intersection(benchmark_returns.index)
            portfolio_returns = portfolio_returns.loc[common_idx]
            benchmark_returns = benchmark_returns.loc[common_idx]
        
        # 베타 계산
        covariance = np.cov(portfolio_returns, benchmark_returns)[0, 1]
        benchmark_variance = np.var(benchmark_returns)
        beta = covariance / benchmark_variance if benchmark_variance != 0 else 0
        
        # 알파 계산 (CAPM)
        periods_per_year = self._get_periods_per_year(portfolio_returns)
        portfolio_annual = (1 + portfolio_returns.mean()) ** periods_per_year - 1
        benchmark_annual = (1 + benchmark_returns.mean()) ** periods_per_year - 1
        alpha = portfolio_annual - (self.risk_free_rate + beta * (benchmark_annual - self.risk_free_rate))
        
        return alpha, beta
    
    def _calculate_consistency_score(self, returns: pd.Series) -> float:
        """일관성 점수 계산"""
        if len(returns) < 12:
            return 0.5
        
        # 월간 수익률의 일관성 측정
        monthly_returns = returns.resample('M').apply(lambda x: (1 + x).prod() - 1)
        positive_months = (monthly_returns > 0).sum()
        total_months = len(monthly_returns)
        
        return positive_months / total_months if total_months > 0 else 0.0
    
    def _calculate_burke_ratio(
        self, 
        returns: pd.Series, 
        values: Optional[pd.Series] = None
    ) -> float:
        """버크 비율 계산"""
        annual_return = (1 + returns.mean()) ** self._get_periods_per_year(returns) - 1
        
        if values is not None:
            cumulative_max = values.expanding().max()
            drawdowns = (values - cumulative_max) / cumulative_max
        else:
            cumulative = (1 + returns).cumprod()
            cumulative_max = cumulative.expanding().max()
            drawdowns = (cumulative - cumulative_max) / cumulative_max
        
        # 드로우다운 제곱의 합의 제곱근
        drawdown_squared_sum = (drawdowns[drawdowns < 0] ** 2).sum()
        burke_denominator = np.sqrt(drawdown_squared_sum)
        
        if burke_denominator == 0:
            return float('inf')
        
        return annual_return / burke_denominator
    
    def _calculate_rebalancing_alpha(
        self,
        portfolio_returns: pd.Series,
        asset_returns: Dict[str, pd.Series],
        portfolio_weights: Dict[str, pd.Series]
    ) -> float:
        """리밸런싱 알파 계산"""
        # 매월 리밸런싱 vs 바이앤홀드 수익률 차이
        # 간단한 근사치 계산
        
        try:
            monthly_portfolio_returns = portfolio_returns.resample('M').apply(
                lambda x: (1 + x).prod() - 1
            )
            
            # 바이앤홀드 수익률 계산 (초기 가중치 유지)
            initial_weights = {}
            for asset in asset_returns.keys():
                if asset in portfolio_weights:
                    initial_weights[asset] = portfolio_weights[asset].iloc[0]
            
            buy_hold_returns = []
            for month_end in monthly_portfolio_returns.index:
                month_return = 0
                for asset, returns in asset_returns.items():
                    if asset in initial_weights:
                        asset_month_return = returns.resample('M').apply(
                            lambda x: (1 + x).prod() - 1
                        ).loc[month_end] if month_end in returns.resample('M').apply(
                            lambda x: (1 + x).prod() - 1
                        ).index else 0
                        month_return += initial_weights[asset] * asset_month_return
                buy_hold_returns.append(month_return)
            
            buy_hold_series = pd.Series(buy_hold_returns, index=monthly_portfolio_returns.index)
            
            # 리밸런싱 알파 = 리밸런싱 수익률 - 바이앤홀드 수익률
            rebalancing_alpha = (monthly_portfolio_returns - buy_hold_series).mean() * 12
            return rebalancing_alpha
            
        except Exception as e:
            logger.warning(f"리밸런싱 알파 계산 실패: {e}")
            return 0.0
    
    def _generate_performance_summary(self, report: Dict[str, Any]) -> Dict[str, Any]:
        """성과 요약 생성"""
        
        metrics = report.get("performance_metrics")
        if not metrics:
            return {"summary": "성과 데이터 부족"}
        
        summary = {
            "overall_grade": "B",  # 기본 등급
            "key_strengths": [],
            "key_weaknesses": [],
            "recommendations": []
        }
        
        # 등급 결정
        score = 0
        if metrics.sharpe_ratio > 1.5:
            score += 25
            summary["key_strengths"].append("우수한 샤프 비율")
        elif metrics.sharpe_ratio < 0.5:
            summary["key_weaknesses"].append("낮은 샤프 비율")
        else:
            score += 15
        
        if abs(metrics.max_drawdown) < 0.15:  # 15% 미만
            score += 25
            summary["key_strengths"].append("양호한 드로우다운 관리")
        elif abs(metrics.max_drawdown) > 0.30:  # 30% 이상
            summary["key_weaknesses"].append("큰 최대 드로우다운")
        else:
            score += 15
        
        if metrics.hit_rate > 0.6:  # 60% 이상
            score += 20
            summary["key_strengths"].append("높은 승률")
        elif metrics.hit_rate < 0.4:  # 40% 미만
            summary["key_weaknesses"].append("낮은 승률")
        else:
            score += 10
        
        if metrics.consistency_score > 0.7:
            score += 15
            summary["key_strengths"].append("일관된 성과")
        elif metrics.consistency_score < 0.4:
            summary["key_weaknesses"].append("불안정한 성과")
        
        # 등급 매핑
        if score >= 80:
            summary["overall_grade"] = "A"
        elif score >= 65:
            summary["overall_grade"] = "B"
        elif score >= 50:
            summary["overall_grade"] = "C"
        else:
            summary["overall_grade"] = "D"
        
        # 권장사항
        if abs(metrics.max_drawdown) > 0.25:
            summary["recommendations"].append("리스크 관리 강화 필요")
        if metrics.sharpe_ratio < 1.0:
            summary["recommendations"].append("리스크 조정 수익률 개선 필요")
        if metrics.consistency_score < 0.5:
            summary["recommendations"].append("포트폴리오 안정성 제고 필요")
        
        return summary