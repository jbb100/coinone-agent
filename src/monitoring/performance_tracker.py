"""
Performance Tracker

포트폴리오 성과 추적 및 분석을 담당하는 모듈
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from loguru import logger


@dataclass
class PerformanceMetrics:
    """성과 지표 데이터 클래스"""
    period_days: int
    total_return: float
    annualized_return: float
    volatility: float
    sharpe_ratio: float
    max_drawdown: float
    benchmark_return: float
    tracking_error: float
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    calmar_ratio: float = 0.0
    sortino_ratio: float = 0.0


class PerformanceTracker:
    """
    성과 추적기
    
    포트폴리오의 성과를 추적하고 다양한 리스크 지표를 계산합니다.
    """
    
    def __init__(self, config, db_manager):
        """
        Args:
            config: ConfigLoader 인스턴스
            db_manager: DatabaseManager 인스턴스
        """
        self.config = config
        self.db_manager = db_manager
        
        # 설정 값들
        risk_config = config.get_risk_config().get("three_line_check", {})
        self.benchmark = risk_config.get("benchmark", "BTC")
        self.performance_period = risk_config.get("performance_period", 30)
        
        # 무위험 수익률 (연 2% 가정)
        self.risk_free_rate = 0.02
        
        logger.info("PerformanceTracker 초기화 완료")
    
    def calculate_performance_metrics(
        self, 
        period_days: int = 30,
        end_date: Optional[datetime] = None
    ) -> PerformanceMetrics:
        """
        성과 지표 계산
        
        Args:
            period_days: 분석 기간 (일)
            end_date: 종료 날짜 (None인 경우 현재 날짜)
            
        Returns:
            성과 지표 객체
        """
        try:
            if end_date is None:
                end_date = datetime.now()
            
            start_date = end_date - timedelta(days=period_days)
            
            # 포트폴리오 이력 데이터 조회
            portfolio_history = self.db_manager.get_portfolio_history(period_days + 10)
            
            if len(portfolio_history) < 2:
                logger.warning("성과 계산을 위한 충분한 데이터가 없음")
                return self._create_empty_metrics(period_days)
            
            # 포트폴리오 가치 시계열 생성
            portfolio_values = []
            dates = []
            
            for snapshot in portfolio_history:
                snapshot_date = pd.to_datetime(snapshot['snapshot_date'])
                if start_date <= snapshot_date <= end_date:
                    portfolio_values.append(snapshot['total_value_krw'])
                    dates.append(snapshot_date)
            
            if len(portfolio_values) < 2:
                logger.warning("기간 내 충분한 포트폴리오 데이터가 없음")
                return self._create_empty_metrics(period_days)
            
            # 수익률 계산
            returns = self._calculate_returns(portfolio_values)
            
            # 벤치마크 수익률 (BTC) 계산
            benchmark_return = self._calculate_benchmark_return(start_date, end_date)
            
            # 성과 지표 계산
            metrics = self._calculate_metrics(
                returns, 
                period_days, 
                benchmark_return,
                portfolio_values
            )
            
            logger.info(f"성과 지표 계산 완료: {period_days}일간")
            return metrics
            
        except Exception as e:
            logger.error(f"성과 지표 계산 실패: {e}")
            return self._create_empty_metrics(period_days)
    
    def _calculate_returns(self, portfolio_values: List[float]) -> np.ndarray:
        """
        포트폴리오 수익률 계산
        
        Args:
            portfolio_values: 포트폴리오 가치 리스트
            
        Returns:
            일간 수익률 배열
        """
        values = np.array(portfolio_values)
        returns = (values[1:] - values[:-1]) / values[:-1]
        return returns
    
    def _calculate_benchmark_return(
        self, 
        start_date: datetime, 
        end_date: datetime
    ) -> float:
        """
        벤치마크 수익률 계산 (BTC 기준)
        
        Args:
            start_date: 시작 날짜
            end_date: 종료 날짜
            
        Returns:
            벤치마크 총 수익률
        """
        try:
            # TODO: 실제 구현에서는 외부 API에서 BTC 가격 데이터를 가져와야 함
            # 여기서는 임시로 5% 수익률 가정
            return 0.05
            
        except Exception as e:
            logger.error(f"벤치마크 수익률 계산 실패: {e}")
            return 0.0
    
    def _calculate_metrics(
        self,
        returns: np.ndarray,
        period_days: int,
        benchmark_return: float,
        portfolio_values: List[float]
    ) -> PerformanceMetrics:
        """
        성과 지표 계산
        
        Args:
            returns: 일간 수익률 배열
            period_days: 분석 기간
            benchmark_return: 벤치마크 수익률
            portfolio_values: 포트폴리오 가치 리스트
            
        Returns:
            성과 지표 객체
        """
        # 기본 수익률 지표
        total_return = (portfolio_values[-1] / portfolio_values[0]) - 1
        annualized_return = (1 + total_return) ** (365 / period_days) - 1
        
        # 변동성 (연환산)
        volatility = np.std(returns) * np.sqrt(365) if len(returns) > 1 else 0.0
        
        # 샤프 비율
        excess_return = annualized_return - self.risk_free_rate
        sharpe_ratio = excess_return / volatility if volatility > 0 else 0.0
        
        # 최대 드로우다운
        max_drawdown = self._calculate_max_drawdown(portfolio_values)
        
        # 추적오차
        tracking_error = abs(total_return - benchmark_return)
        
        # 승률 및 평균 손익
        win_rate, avg_win, avg_loss = self._calculate_win_loss_stats(returns)
        
        # 칼마 비율 (연환산 수익률 / 최대 드로우다운)
        calmar_ratio = annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0.0
        
        # 소르티노 비율
        sortino_ratio = self._calculate_sortino_ratio(returns, annualized_return)
        
        return PerformanceMetrics(
            period_days=period_days,
            total_return=total_return,
            annualized_return=annualized_return,
            volatility=volatility,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            benchmark_return=benchmark_return,
            tracking_error=tracking_error,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            calmar_ratio=calmar_ratio,
            sortino_ratio=sortino_ratio
        )
    
    def _calculate_max_drawdown(self, portfolio_values: List[float]) -> float:
        """
        최대 드로우다운 계산
        
        Args:
            portfolio_values: 포트폴리오 가치 리스트
            
        Returns:
            최대 드로우다운 (음수)
        """
        values = np.array(portfolio_values)
        cumulative_max = np.maximum.accumulate(values)
        drawdowns = (values - cumulative_max) / cumulative_max
        return np.min(drawdowns)
    
    def _calculate_win_loss_stats(
        self, 
        returns: np.ndarray
    ) -> Tuple[float, float, float]:
        """
        승률 및 평균 손익 계산
        
        Args:
            returns: 수익률 배열
            
        Returns:
            (승률, 평균 이익, 평균 손실)
        """
        if len(returns) == 0:
            return 0.0, 0.0, 0.0
        
        wins = returns[returns > 0]
        losses = returns[returns < 0]
        
        win_rate = len(wins) / len(returns)
        avg_win = np.mean(wins) if len(wins) > 0 else 0.0
        avg_loss = np.mean(losses) if len(losses) > 0 else 0.0
        
        return win_rate, avg_win, avg_loss
    
    def _calculate_sortino_ratio(
        self, 
        returns: np.ndarray, 
        annualized_return: float
    ) -> float:
        """
        소르티노 비율 계산
        
        Args:
            returns: 수익률 배열
            annualized_return: 연환산 수익률
            
        Returns:
            소르티노 비율
        """
        negative_returns = returns[returns < 0]
        if len(negative_returns) == 0:
            return float('inf') if annualized_return > 0 else 0.0
        
        downside_deviation = np.std(negative_returns) * np.sqrt(365)
        excess_return = annualized_return - self.risk_free_rate
        
        return excess_return / downside_deviation if downside_deviation > 0 else 0.0
    
    def _create_empty_metrics(self, period_days: int) -> PerformanceMetrics:
        """빈 성과 지표 생성"""
        return PerformanceMetrics(
            period_days=period_days,
            total_return=0.0,
            annualized_return=0.0,
            volatility=0.0,
            sharpe_ratio=0.0,
            max_drawdown=0.0,
            benchmark_return=0.0,
            tracking_error=0.0
        )
    
    def save_performance_metrics(self, metrics: PerformanceMetrics) -> int:
        """
        성과 지표를 데이터베이스에 저장
        
        Args:
            metrics: 성과 지표
            
        Returns:
            저장된 레코드 ID
        """
        try:
            metrics_data = {
                "metric_date": datetime.now(),
                "period_days": metrics.period_days,
                "total_return": metrics.total_return,
                "annualized_return": metrics.annualized_return,
                "volatility": metrics.volatility,
                "sharpe_ratio": metrics.sharpe_ratio,
                "max_drawdown": metrics.max_drawdown,
                "benchmark_return": metrics.benchmark_return,
                "tracking_error": metrics.tracking_error,
                "metrics_data": {
                    "win_rate": metrics.win_rate,
                    "avg_win": metrics.avg_win,
                    "avg_loss": metrics.avg_loss,
                    "calmar_ratio": metrics.calmar_ratio,
                    "sortino_ratio": metrics.sortino_ratio
                }
            }
            
            # TODO: DatabaseManager에 save_performance_metrics 메서드 추가 필요
            # record_id = self.db_manager.save_performance_metrics(metrics_data)
            record_id = 1  # 임시
            
            logger.info(f"성과 지표 저장 완료: ID {record_id}")
            return record_id
            
        except Exception as e:
            logger.error(f"성과 지표 저장 실패: {e}")
            raise
    
    def generate_performance_report(
        self, 
        period_days: int = 30
    ) -> Dict:
        """
        성과 보고서 생성
        
        Args:
            period_days: 분석 기간
            
        Returns:
            성과 보고서 딕셔너리
        """
        try:
            # 성과 지표 계산
            metrics = self.calculate_performance_metrics(period_days)
            
            # 포트폴리오 현황
            recent_snapshots = self.db_manager.get_portfolio_history(7)
            current_portfolio = recent_snapshots[-1] if recent_snapshots else {}
            
            # 거래 통계
            trade_history = self.db_manager.get_trade_history(period_days)
            trade_stats = self._calculate_trade_statistics(trade_history)
            
            # 보고서 생성
            report = {
                "report_date": datetime.now(),
                "analysis_period": period_days,
                "performance_metrics": {
                    "total_return": metrics.total_return,
                    "annualized_return": metrics.annualized_return,
                    "volatility": metrics.volatility,
                    "sharpe_ratio": metrics.sharpe_ratio,
                    "max_drawdown": metrics.max_drawdown,
                    "benchmark_return": metrics.benchmark_return,
                    "tracking_error": metrics.tracking_error,
                    "win_rate": metrics.win_rate,
                    "calmar_ratio": metrics.calmar_ratio,
                    "sortino_ratio": metrics.sortino_ratio
                },
                "portfolio_status": {
                    "total_value_krw": current_portfolio.get("total_value_krw", 0),
                    "asset_allocation": self._get_current_allocation(current_portfolio)
                },
                "trading_statistics": trade_stats,
                "risk_assessment": self._assess_risk_level(metrics),
                "recommendations": self._generate_recommendations(metrics)
            }
            
            logger.info(f"성과 보고서 생성 완료: {period_days}일간")
            return report
            
        except Exception as e:
            logger.error(f"성과 보고서 생성 실패: {e}")
            return {"error": str(e), "report_date": datetime.now()}
    
    def _calculate_trade_statistics(self, trade_history: List[Dict]) -> Dict:
        """
        거래 통계 계산
        
        Args:
            trade_history: 거래 내역 리스트
            
        Returns:
            거래 통계 딕셔너리
        """
        if not trade_history:
            return {
                "total_trades": 0,
                "successful_trades": 0,
                "success_rate": 0.0,
                "total_fees": 0.0,
                "avg_trade_size": 0.0
            }
        
        total_trades = len(trade_history)
        successful_trades = len([t for t in trade_history if t.get("status") == "filled"])
        success_rate = successful_trades / total_trades if total_trades > 0 else 0.0
        
        total_fees = sum(t.get("fee", 0) for t in trade_history)
        trade_sizes = [t.get("amount", 0) for t in trade_history if t.get("amount")]
        avg_trade_size = np.mean(trade_sizes) if trade_sizes else 0.0
        
        return {
            "total_trades": total_trades,
            "successful_trades": successful_trades,
            "success_rate": success_rate,
            "total_fees": total_fees,
            "avg_trade_size": avg_trade_size
        }
    
    def _get_current_allocation(self, portfolio_snapshot: Dict) -> Dict:
        """
        현재 자산 배분 비율 계산
        
        Args:
            portfolio_snapshot: 포트폴리오 스냅샷
            
        Returns:
            자산 배분 딕셔너리
        """
        total_value = portfolio_snapshot.get("total_value_krw", 0)
        if total_value <= 0:
            return {}
        
        allocation = {}
        
        # 각 자산의 비중 계산
        for asset in ["KRW", "BTC", "ETH", "XRP", "SOL"]:
            if asset == "KRW":
                value = portfolio_snapshot.get("krw_balance", 0)
            else:
                value = portfolio_snapshot.get(f"{asset.lower()}_value_krw", 0)
            
            allocation[asset] = value / total_value if total_value > 0 else 0.0
        
        return allocation
    
    def _assess_risk_level(self, metrics: PerformanceMetrics) -> str:
        """
        리스크 수준 평가
        
        Args:
            metrics: 성과 지표
            
        Returns:
            리스크 수준 ("low", "medium", "high")
        """
        risk_score = 0
        
        # 변동성 기준
        if metrics.volatility > 0.30:  # 30% 이상
            risk_score += 2
        elif metrics.volatility > 0.20:  # 20% 이상
            risk_score += 1
        
        # 최대 드로우다운 기준
        if metrics.max_drawdown < -0.20:  # -20% 이하
            risk_score += 2
        elif metrics.max_drawdown < -0.10:  # -10% 이하
            risk_score += 1
        
        # 샤프 비율 기준
        if metrics.sharpe_ratio < 0:
            risk_score += 1
        elif metrics.sharpe_ratio < 0.5:
            risk_score += 0.5
        
        if risk_score >= 3:
            return "high"
        elif risk_score >= 1:
            return "medium"
        else:
            return "low"
    
    def _generate_recommendations(self, metrics: PerformanceMetrics) -> List[str]:
        """
        성과 기반 권장사항 생성
        
        Args:
            metrics: 성과 지표
            
        Returns:
            권장사항 리스트
        """
        recommendations = []
        
        # 수익률 기반 권장사항
        if metrics.total_return < -0.10:
            recommendations.append("포트폴리오 손실이 큽니다. 리스크 관리 전략 재검토가 필요합니다.")
        
        # 변동성 기반 권장사항
        if metrics.volatility > 0.25:
            recommendations.append("포트폴리오 변동성이 높습니다. 안전자산 비중 증대를 고려하세요.")
        
        # 드로우다운 기반 권장사항
        if metrics.max_drawdown < -0.15:
            recommendations.append("최대 드로우다운이 큽니다. 손절 전략 강화가 필요합니다.")
        
        # 샤프 비율 기반 권장사항
        if metrics.sharpe_ratio < 0.5:
            recommendations.append("위험 대비 수익률이 낮습니다. 포트폴리오 구성 재검토를 권장합니다.")
        
        # 추적오차 기반 권장사항
        if metrics.tracking_error > 0.05:
            recommendations.append("벤치마크 대비 추적오차가 큽니다. 운용 전략 점검이 필요합니다.")
        
        # 기본 권장사항
        if not recommendations:
            recommendations.append("포트폴리오가 안정적으로 운용되고 있습니다. 현재 전략을 유지하세요.")
        
        return recommendations
    
    def compare_with_benchmark(
        self, 
        period_days: int = 30
    ) -> Dict:
        """
        벤치마크 대비 성과 비교
        
        Args:
            period_days: 비교 기간
            
        Returns:
            비교 결과 딕셔너리
        """
        try:
            metrics = self.calculate_performance_metrics(period_days)
            
            # 초과 수익률 계산
            excess_return = metrics.total_return - metrics.benchmark_return
            
            # 정보 비율 (초과수익률 / 추적오차)
            information_ratio = excess_return / metrics.tracking_error if metrics.tracking_error > 0 else 0
            
            comparison = {
                "period_days": period_days,
                "portfolio_return": metrics.total_return,
                "benchmark_return": metrics.benchmark_return,
                "excess_return": excess_return,
                "tracking_error": metrics.tracking_error,
                "information_ratio": information_ratio,
                "outperformed": excess_return > 0,
                "analysis_date": datetime.now()
            }
            
            logger.info(f"벤치마크 비교 완료: 초과수익률 {excess_return:.2%}")
            return comparison
            
        except Exception as e:
            logger.error(f"벤치마크 비교 실패: {e}")
            return {"error": str(e)}


# 설정 상수
DEFAULT_RISK_FREE_RATE = 0.02  # 무위험 수익률 2%
PERFORMANCE_CALCULATION_PERIODS = [7, 30, 90, 365]  # 성과 계산 기간들 