"""
Backtesting Report Generator

백테스팅 결과를 분석하고 리포트를 생성하는 시스템
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import asdict
import json
from loguru import logger

from .backtesting_engine import PerformanceMetrics, BacktestConfig


class BacktestReportGenerator:
    """백테스팅 리포트 생성기"""
    
    def __init__(self):
        self.benchmark_data = {}
    
    def generate_comprehensive_report(
        self,
        performance: PerformanceMetrics,
        config: BacktestConfig,
        portfolio_history: pd.DataFrame,
        trade_history: pd.DataFrame,
        benchmark_performance: Optional[PerformanceMetrics] = None
    ) -> Dict[str, Any]:
        """종합 백테스팅 리포트 생성"""
        try:
            logger.info("백테스팅 종합 리포트 생성 시작")
            
            report = {
                "metadata": self._generate_metadata(config),
                "executive_summary": self._generate_executive_summary(performance, config),
                "performance_metrics": self._format_performance_metrics(performance),
                "risk_analysis": self._generate_risk_analysis(performance, portfolio_history),
                "trade_analysis": self._generate_trade_analysis(trade_history),
                "period_analysis": self._generate_period_analysis(portfolio_history, performance),
                "comparison": self._generate_benchmark_comparison(performance, benchmark_performance),
                "recommendations": self._generate_recommendations(performance, config),
                "charts_data": self._prepare_chart_data(portfolio_history, trade_history)
            }
            
            logger.info("백테스팅 리포트 생성 완료")
            return report
            
        except Exception as e:
            logger.error(f"리포트 생성 실패: {e}")
            raise
    
    def _generate_metadata(self, config: BacktestConfig) -> Dict[str, Any]:
        """메타데이터 생성"""
        return {
            "report_generated": datetime.now().isoformat(),
            "backtest_period": {
                "start_date": config.start_date,
                "end_date": config.end_date,
                "duration_days": (pd.to_datetime(config.end_date) - pd.to_datetime(config.start_date)).days
            },
            "settings": {
                "initial_capital": config.initial_capital,
                "rebalance_frequency": config.rebalance_frequency,
                "transaction_cost": config.transaction_cost,
                "slippage": config.slippage,
                "risk_level": config.risk_level,
                "mode": config.mode.value
            }
        }
    
    def _generate_executive_summary(self, performance: PerformanceMetrics, config: BacktestConfig) -> Dict[str, Any]:
        """핵심 요약 생성"""
        duration_years = (pd.to_datetime(config.end_date) - pd.to_datetime(config.start_date)).days / 365.25
        
        # 성과 등급 판정
        if performance.sharpe_ratio > 1.5:
            performance_grade = "A+"
            performance_desc = "매우 우수"
        elif performance.sharpe_ratio > 1.0:
            performance_grade = "A"
            performance_desc = "우수"
        elif performance.sharpe_ratio > 0.5:
            performance_grade = "B"
            performance_desc = "양호"
        else:
            performance_grade = "C"
            performance_desc = "개선 필요"
        
        # 리스크 등급 판정
        if performance.max_drawdown < 0.1:
            risk_grade = "낮음"
        elif performance.max_drawdown < 0.2:
            risk_grade = "보통"
        else:
            risk_grade = "높음"
        
        return {
            "performance_grade": performance_grade,
            "performance_description": performance_desc,
            "key_metrics": {
                "total_return": performance.total_return,
                "annualized_return": performance.annualized_return,
                "sharpe_ratio": performance.sharpe_ratio,
                "max_drawdown": performance.max_drawdown,
                "win_rate": performance.win_rate
            },
            "risk_assessment": {
                "risk_level": risk_grade,
                "volatility": performance.volatility,
                "risk_adjusted_return": performance.annualized_return / performance.volatility if performance.volatility > 0 else 0
            },
            "trading_summary": {
                "total_trades": performance.total_trades,
                "winning_trades": performance.winning_trades,
                "average_trade_size": performance.avg_win if performance.avg_win > 0 else 0
            }
        }
    
    def _format_performance_metrics(self, performance: PerformanceMetrics) -> Dict[str, Any]:
        """성과 지표 포맷팅"""
        return {
            "returns": {
                "total_return": {
                    "value": performance.total_return,
                    "formatted": f"{performance.total_return:.2%}",
                    "description": "전체 기간 총 수익률"
                },
                "annualized_return": {
                    "value": performance.annualized_return,
                    "formatted": f"{performance.annualized_return:.2%}",
                    "description": "연간 수익률"
                }
            },
            "risk": {
                "volatility": {
                    "value": performance.volatility,
                    "formatted": f"{performance.volatility:.2%}",
                    "description": "연간 변동성"
                },
                "max_drawdown": {
                    "value": performance.max_drawdown,
                    "formatted": f"{performance.max_drawdown:.2%}",
                    "description": "최대 낙폭"
                },
                "sharpe_ratio": {
                    "value": performance.sharpe_ratio,
                    "formatted": f"{performance.sharpe_ratio:.2f}",
                    "description": "샤프 비율 (위험 대비 수익)"
                }
            },
            "trading": {
                "win_rate": {
                    "value": performance.win_rate,
                    "formatted": f"{performance.win_rate:.1%}",
                    "description": "승률"
                },
                "profit_factor": {
                    "value": performance.profit_factor,
                    "formatted": f"{performance.profit_factor:.2f}",
                    "description": "수익 팩터"
                },
                "total_trades": {
                    "value": performance.total_trades,
                    "formatted": f"{performance.total_trades}",
                    "description": "총 거래 수"
                }
            }
        }
    
    def _generate_risk_analysis(self, performance: PerformanceMetrics, portfolio_history: pd.DataFrame) -> Dict[str, Any]:
        """리스크 분석"""
        try:
            # VaR 계산 (95% 신뢰구간)
            returns = portfolio_history['daily_return'].dropna()
            var_95 = np.percentile(returns, 5) if len(returns) > 0 else 0
            
            # CVaR (Conditional VaR) 계산
            cvar_95 = returns[returns <= var_95].mean() if len(returns[returns <= var_95]) > 0 else 0
            
            # 연속 손실 기간 계산
            consecutive_losses = self._calculate_consecutive_losses(returns)
            
            # 월별 변동성
            if 'date' in portfolio_history.columns:
                portfolio_history['month'] = pd.to_datetime(portfolio_history['date']).dt.to_period('M')
                monthly_volatility = portfolio_history.groupby('month')['daily_return'].std().mean()
            else:
                monthly_volatility = 0
            
            return {
                "value_at_risk": {
                    "var_95": var_95,
                    "cvar_95": cvar_95,
                    "interpretation": "95% 신뢰구간에서 일일 최대 예상 손실"
                },
                "drawdown_analysis": {
                    "max_drawdown": performance.max_drawdown,
                    "max_consecutive_losses": consecutive_losses,
                    "recovery_analysis": "추가 분석 필요"
                },
                "volatility_analysis": {
                    "annual_volatility": performance.volatility,
                    "monthly_volatility": monthly_volatility,
                    "volatility_stability": "보통"
                }
            }
            
        except Exception as e:
            logger.warning(f"리스크 분석 실패: {e}")
            return {"error": "리스크 분석을 생성할 수 없습니다"}
    
    def _calculate_consecutive_losses(self, returns: pd.Series) -> int:
        """연속 손실 기간 계산"""
        if len(returns) == 0:
            return 0
        
        max_consecutive = 0
        current_consecutive = 0
        
        for ret in returns:
            if ret < 0:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0
        
        return max_consecutive
    
    def _generate_trade_analysis(self, trade_history: pd.DataFrame) -> Dict[str, Any]:
        """거래 분석"""
        try:
            if trade_history.empty:
                return {"message": "거래 내역이 없습니다"}
            
            # 자산별 거래 분석
            asset_analysis = {}
            for asset in trade_history['asset'].unique():
                asset_trades = trade_history[trade_history['asset'] == asset]
                asset_analysis[asset] = {
                    "total_trades": len(asset_trades),
                    "buy_trades": len(asset_trades[asset_trades['side'] == 'buy']),
                    "sell_trades": len(asset_trades[asset_trades['side'] == 'sell']),
                    "total_volume": asset_trades['amount_krw'].sum(),
                    "avg_trade_size": asset_trades['amount_krw'].mean(),
                    "total_fees": asset_trades['fee'].sum()
                }
            
            # 월별 거래 분석
            trade_history['month'] = pd.to_datetime(trade_history['timestamp']).dt.to_period('M')
            monthly_trades = trade_history.groupby('month').agg({
                'amount_krw': ['count', 'sum', 'mean'],
                'fee': 'sum'
            }).round(2)
            
            # 거래 효율성
            total_fees = trade_history['fee'].sum()
            total_volume = trade_history['amount_krw'].sum()
            fee_ratio = total_fees / total_volume if total_volume > 0 else 0
            
            return {
                "summary": {
                    "total_trades": len(trade_history),
                    "total_volume": total_volume,
                    "total_fees": total_fees,
                    "fee_ratio": fee_ratio,
                    "avg_trade_size": trade_history['amount_krw'].mean()
                },
                "by_asset": asset_analysis,
                "efficiency": {
                    "cost_efficiency": f"{fee_ratio:.3%}",
                    "trade_frequency": len(trade_history) / len(trade_history['timestamp'].dt.date.unique()) if len(trade_history) > 0 else 0,
                    "recommendation": "적정" if fee_ratio < 0.01 else "높음"
                }
            }
            
        except Exception as e:
            logger.warning(f"거래 분석 실패: {e}")
            return {"error": "거래 분석을 생성할 수 없습니다"}
    
    def _generate_period_analysis(self, portfolio_history: pd.DataFrame, performance: PerformanceMetrics) -> Dict[str, Any]:
        """기간별 분석"""
        try:
            # 월별 수익률 분석
            monthly_stats = {
                "returns": performance.monthly_returns,
                "avg_monthly_return": np.mean(performance.monthly_returns) if performance.monthly_returns else 0,
                "best_month": max(performance.monthly_returns) if performance.monthly_returns else 0,
                "worst_month": min(performance.monthly_returns) if performance.monthly_returns else 0,
                "positive_months": sum(1 for r in performance.monthly_returns if r > 0),
                "total_months": len(performance.monthly_returns)
            }
            
            # 연별 수익률 분석
            yearly_stats = {
                "returns": performance.yearly_returns,
                "avg_yearly_return": np.mean(performance.yearly_returns) if performance.yearly_returns else 0,
                "best_year": max(performance.yearly_returns) if performance.yearly_returns else 0,
                "worst_year": min(performance.yearly_returns) if performance.yearly_returns else 0,
                "positive_years": sum(1 for r in performance.yearly_returns if r > 0),
                "total_years": len(performance.yearly_returns)
            }
            
            # 계절성 분석 (월별)
            if not portfolio_history.empty and 'date' in portfolio_history.columns:
                portfolio_history['month_num'] = pd.to_datetime(portfolio_history['date']).dt.month
                seasonal_returns = portfolio_history.groupby('month_num')['daily_return'].mean().to_dict()
            else:
                seasonal_returns = {}
            
            return {
                "monthly_analysis": monthly_stats,
                "yearly_analysis": yearly_stats,
                "seasonality": {
                    "monthly_patterns": seasonal_returns,
                    "best_performing_months": sorted(seasonal_returns.items(), key=lambda x: x[1], reverse=True)[:3] if seasonal_returns else [],
                    "analysis": "월별 성과 패턴 분석"
                }
            }
            
        except Exception as e:
            logger.warning(f"기간별 분석 실패: {e}")
            return {"error": "기간별 분석을 생성할 수 없습니다"}
    
    def _generate_benchmark_comparison(
        self, 
        performance: PerformanceMetrics, 
        benchmark: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """벤치마크 비교 분석 (Buy-and-Hold 전략 포함)"""
        if not benchmark:
            return {
                "message": "벤치마크 데이터가 없습니다",
                "recommendation": "백테스팅 시 calculate_benchmarks=True 옵션을 사용하세요"
            }
        
        comparison_results = {}
        
        # 각 자산별 Buy-and-Hold와 비교
        for asset, bench_data in benchmark.items():
            if asset == 'EQUAL_WEIGHT':
                continue
                
            comparison_results[asset] = {
                "buy_and_hold_return": bench_data.get('total_return', 0),
                "buy_and_hold_annual": bench_data.get('annualized_return', 0),
                "buy_and_hold_sharpe": bench_data.get('sharpe_ratio', 0),
                "strategy_outperformance": performance.total_return - bench_data.get('total_return', 0),
                "strategy_wins": performance.total_return > bench_data.get('total_return', 0)
            }
        
        # 균등 가중 포트폴리오와 비교
        if 'EQUAL_WEIGHT' in benchmark:
            eq_weight = benchmark['EQUAL_WEIGHT']
            comparison_results['EQUAL_WEIGHT_PORTFOLIO'] = {
                "portfolio_return": eq_weight.get('total_return', 0),
                "portfolio_annual": eq_weight.get('annualized_return', 0),
                "portfolio_sharpe": eq_weight.get('sharpe_ratio', 0),
                "strategy_outperformance": performance.total_return - eq_weight.get('total_return', 0),
                "strategy_wins": performance.total_return > eq_weight.get('total_return', 0)
            }
        
        # 최고 성과 벤치마크 찾기
        best_benchmark = max(benchmark.items(), 
                           key=lambda x: x[1].get('total_return', 0) if x[0] != 'EQUAL_WEIGHT' else 0)
        
        return {
            "buy_and_hold_comparison": comparison_results,
            "best_benchmark": {
                "asset": best_benchmark[0],
                "return": best_benchmark[1].get('total_return', 0),
                "strategy_beats_best": performance.total_return > best_benchmark[1].get('total_return', 0)
            },
            "summary": {
                "strategy_return": performance.total_return,
                "strategy_annual": performance.annualized_return,
                "strategy_sharpe": performance.sharpe_ratio,
                "beats_all_benchmarks": all(
                    performance.total_return > b.get('total_return', 0) 
                    for b in benchmark.values()
                ),
                "average_outperformance": np.mean([
                    performance.total_return - b.get('total_return', 0)
                    for b in benchmark.values()
                ])
            }
        }
    
    
    def _generate_recommendations(self, performance: PerformanceMetrics, config: BacktestConfig) -> List[Dict[str, str]]:
        """개선 권장사항 생성"""
        recommendations = []
        
        # 수익률 기반 권장사항
        if performance.annualized_return < 0.05:  # 5% 미만
            recommendations.append({
                "category": "수익률 개선",
                "issue": "연간 수익률이 낮습니다",
                "recommendation": "더 공격적인 자산 배분을 고려하거나 리밸런싱 주기를 단축해보세요",
                "priority": "높음"
            })
        
        # 리스크 기반 권장사항
        if performance.max_drawdown > 0.3:  # 30% 초과
            recommendations.append({
                "category": "리스크 관리",
                "issue": "최대 낙폭이 큽니다",
                "recommendation": "포지션 크기를 줄이거나 손절매 규칙을 추가해보세요",
                "priority": "높음"
            })
        
        # 샤프 비율 기반 권장사항
        if performance.sharpe_ratio < 0.5:
            recommendations.append({
                "category": "위험 대비 수익",
                "issue": "샤프 비율이 낮습니다",
                "recommendation": "변동성을 줄이거나 수익률을 개선하는 전략을 검토해보세요",
                "priority": "보통"
            })
        
        # 거래 빈도 기반 권장사항
        if performance.total_trades > 1000:
            recommendations.append({
                "category": "거래 효율성",
                "issue": "거래 횟수가 많습니다",
                "recommendation": "거래 수수료 최적화를 위해 리밸런싱 임계값을 높여보세요",
                "priority": "보통"
            })
        
        # 긍정적인 피드백
        if performance.sharpe_ratio > 1.0 and performance.max_drawdown < 0.2:
            recommendations.append({
                "category": "우수한 성과",
                "issue": "전략이 잘 작동하고 있습니다",
                "recommendation": "현재 설정을 유지하되, 시장 환경 변화에 주의하세요",
                "priority": "정보"
            })
        
        return recommendations
    
    def _prepare_chart_data(self, portfolio_history: pd.DataFrame, trade_history: pd.DataFrame) -> Dict[str, Any]:
        """차트 데이터 준비"""
        try:
            chart_data = {}
            
            # 포트폴리오 가치 차트 데이터
            if not portfolio_history.empty:
                chart_data["portfolio_value"] = {
                    "dates": portfolio_history['date'].dt.strftime('%Y-%m-%d').tolist() if 'date' in portfolio_history.columns else [],
                    "values": portfolio_history['total_value'].tolist() if 'total_value' in portfolio_history.columns else [],
                    "daily_returns": portfolio_history['daily_return'].tolist() if 'daily_return' in portfolio_history.columns else []
                }
            
            # 거래 빈도 차트 데이터
            if not trade_history.empty:
                trade_counts = trade_history.groupby(trade_history['timestamp'].dt.date).size()
                chart_data["trade_frequency"] = {
                    "dates": trade_counts.index.astype(str).tolist(),
                    "counts": trade_counts.tolist()
                }
                
                # 자산별 거래량
                asset_volumes = trade_history.groupby('asset')['amount_krw'].sum()
                chart_data["asset_allocation"] = {
                    "assets": asset_volumes.index.tolist(),
                    "volumes": asset_volumes.tolist()
                }
            
            return chart_data
            
        except Exception as e:
            logger.warning(f"차트 데이터 준비 실패: {e}")
            return {}
    
    def save_report_to_file(self, report: Dict[str, Any], filename: str = None) -> str:
        """리포트를 파일로 저장"""
        try:
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"backtest_report_{timestamp}.json"
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False, default=str)
            
            logger.info(f"리포트 저장 완료: {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"리포트 저장 실패: {e}")
            raise
    
    def generate_summary_text(self, report: Dict[str, Any]) -> str:
        """리포트 요약 텍스트 생성"""
        try:
            summary = report.get("executive_summary", {})
            performance = summary.get("key_metrics", {})
            
            text = f"""
📊 KAIROS-1 백테스팅 결과 요약
{'=' * 50}

🏆 전체 성과 등급: {summary.get('performance_grade', 'N/A')} ({summary.get('performance_description', 'N/A')})

📈 주요 성과 지표:
  • 총 수익률: {performance.get('total_return', 0):.2%}
  • 연간 수익률: {performance.get('annualized_return', 0):.2%}
  • 샤프 비율: {performance.get('sharpe_ratio', 0):.2f}
  • 최대 낙폭: {performance.get('max_drawdown', 0):.2%}
  • 승률: {performance.get('win_rate', 0):.1%}

⚠️ 리스크 평가:
  • 리스크 수준: {summary.get('risk_assessment', {}).get('risk_level', 'N/A')}
  • 변동성: {summary.get('risk_assessment', {}).get('volatility', 0):.2%}

📋 거래 요약:
  • 총 거래 수: {summary.get('trading_summary', {}).get('total_trades', 0)}
  • 수익 거래: {summary.get('trading_summary', {}).get('winning_trades', 0)}

💡 권장사항: {len(report.get('recommendations', []))}개 항목
            """
            
            return text.strip()
            
        except Exception as e:
            logger.error(f"요약 텍스트 생성 실패: {e}")
            return "리포트 요약을 생성할 수 없습니다."