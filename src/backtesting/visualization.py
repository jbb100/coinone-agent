"""
Backtesting Visualization

백테스팅 결과를 시각화하는 모듈
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import json
from loguru import logger

try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.patches import Rectangle
    import seaborn as sns
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("matplotlib/seaborn이 설치되지 않음. 시각화 기능이 제한됩니다.")

from .backtesting_engine import PerformanceMetrics, BacktestConfig


class BacktestVisualizer:
    """백테스팅 시각화기"""
    
    def __init__(self, style: str = "default"):
        """
        Args:
            style: 시각화 스타일 (default, dark, minimal)
        """
        self.style = style
        
        if MATPLOTLIB_AVAILABLE:
            self._setup_style()
        else:
            logger.warning("시각화 라이브러리가 없어 텍스트 기반 차트만 지원됩니다")
    
    def _setup_style(self):
        """시각화 스타일 설정"""
        if self.style == "dark":
            plt.style.use('dark_background')
            self.colors = ['#00ff00', '#ff6b6b', '#4ecdc4', '#45b7d1', '#96ceb4']
        elif self.style == "minimal":
            sns.set_style("whitegrid")
            self.colors = ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#6A994E']
        else:
            sns.set_style("whitegrid")
            self.colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
    
    def create_performance_dashboard(
        self,
        portfolio_history: pd.DataFrame,
        trade_history: pd.DataFrame,
        performance: PerformanceMetrics,
        config: BacktestConfig,
        save_path: Optional[str] = None
    ) -> Optional[str]:
        """종합 성과 대시보드 생성"""
        if not MATPLOTLIB_AVAILABLE:
            return self._create_text_dashboard(portfolio_history, performance)
        
        try:
            # 대시보드 레이아웃 (2x3 그리드)
            fig, axes = plt.subplots(2, 3, figsize=(20, 12))
            fig.suptitle(f'KAIROS-1 백테스팅 대시보드 ({config.start_date} ~ {config.end_date})', 
                        fontsize=16, fontweight='bold')
            
            # 1. 포트폴리오 가치 변화
            self._plot_portfolio_value(axes[0, 0], portfolio_history)
            
            # 2. 일일 수익률 분포
            self._plot_returns_distribution(axes[0, 1], portfolio_history)
            
            # 3. 누적 수익률
            self._plot_cumulative_returns(axes[0, 2], portfolio_history)
            
            # 4. 드로우다운 차트
            self._plot_drawdown(axes[1, 0], portfolio_history)
            
            # 5. 거래 빈도 및 볼륨
            self._plot_trade_analysis(axes[1, 1], trade_history)
            
            # 6. 성과 지표 요약
            self._plot_performance_metrics(axes[1, 2], performance)
            
            plt.tight_layout()
            
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                logger.info(f"대시보드 저장: {save_path}")
                return save_path
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                default_path = f"kairos1_dashboard_{timestamp}.png"
                plt.savefig(default_path, dpi=300, bbox_inches='tight')
                logger.info(f"대시보드 저장: {default_path}")
                return default_path
                
        except Exception as e:
            logger.error(f"대시보드 생성 실패: {e}")
            return None
        finally:
            if MATPLOTLIB_AVAILABLE:
                plt.close()
    
    def _plot_portfolio_value(self, ax, portfolio_history: pd.DataFrame):
        """포트폴리오 가치 변화 차트"""
        try:
            if 'date' in portfolio_history.columns and 'total_value' in portfolio_history.columns:
                dates = pd.to_datetime(portfolio_history['date'])
                values = portfolio_history['total_value']
                
                ax.plot(dates, values, color=self.colors[0], linewidth=2)
                ax.set_title('포트폴리오 가치 변화', fontsize=12, fontweight='bold')
                ax.set_ylabel('가치 (원)')
                ax.grid(True, alpha=0.3)
                
                # 포맷팅
                ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x/1e6:.1f}M'))
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
                ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
                plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
            else:
                ax.text(0.5, 0.5, 'Portfolio Value\\nData Not Available', 
                       ha='center', va='center', transform=ax.transAxes)
                ax.set_title('포트폴리오 가치 변화')
        except Exception as e:
            logger.warning(f"포트폴리오 가치 차트 생성 실패: {e}")
    
    def _plot_returns_distribution(self, ax, portfolio_history: pd.DataFrame):
        """수익률 분포 히스토그램"""
        try:
            if 'daily_return' in portfolio_history.columns:
                returns = portfolio_history['daily_return'].dropna()
                
                ax.hist(returns, bins=50, color=self.colors[1], alpha=0.7, edgecolor='black')
                ax.axvline(returns.mean(), color='red', linestyle='--', 
                          label=f'평균: {returns.mean():.3%}')
                ax.set_title('일일 수익률 분포', fontsize=12, fontweight='bold')
                ax.set_xlabel('일일 수익률')
                ax.set_ylabel('빈도')
                ax.legend()
                ax.grid(True, alpha=0.3)
                
                # 백분율 포맷팅
                ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:.1%}'))
            else:
                ax.text(0.5, 0.5, 'Returns Distribution\\nData Not Available',
                       ha='center', va='center', transform=ax.transAxes)
                ax.set_title('일일 수익률 분포')
        except Exception as e:
            logger.warning(f"수익률 분포 차트 생성 실패: {e}")
    
    def _plot_cumulative_returns(self, ax, portfolio_history: pd.DataFrame):
        """누적 수익률 차트"""
        try:
            if 'date' in portfolio_history.columns and 'total_value' in portfolio_history.columns:
                dates = pd.to_datetime(portfolio_history['date'])
                values = portfolio_history['total_value']
                
                # 누적 수익률 계산
                initial_value = values.iloc[0]
                cumulative_returns = (values / initial_value - 1) * 100
                
                ax.plot(dates, cumulative_returns, color=self.colors[2], linewidth=2)
                ax.fill_between(dates, 0, cumulative_returns, alpha=0.3, color=self.colors[2])
                ax.set_title('누적 수익률', fontsize=12, fontweight='bold')
                ax.set_ylabel('누적 수익률 (%)')
                ax.grid(True, alpha=0.3)
                
                # 0% 기준선
                ax.axhline(y=0, color='black', linestyle='-', alpha=0.5)
                
                # 포맷팅
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
                ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
                plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
            else:
                ax.text(0.5, 0.5, 'Cumulative Returns\\nData Not Available',
                       ha='center', va='center', transform=ax.transAxes)
                ax.set_title('누적 수익률')
        except Exception as e:
            logger.warning(f"누적 수익률 차트 생성 실패: {e}")
    
    def _plot_drawdown(self, ax, portfolio_history: pd.DataFrame):
        """드로우다운 차트"""
        try:
            if 'date' in portfolio_history.columns and 'total_value' in portfolio_history.columns:
                dates = pd.to_datetime(portfolio_history['date'])
                values = portfolio_history['total_value']
                
                # 드로우다운 계산
                peak = values.expanding().max()
                drawdown = (values - peak) / peak * 100
                
                ax.fill_between(dates, 0, drawdown, color='red', alpha=0.5)
                ax.plot(dates, drawdown, color='darkred', linewidth=1)
                ax.set_title('드로우다운 (Drawdown)', fontsize=12, fontweight='bold')
                ax.set_ylabel('드로우다운 (%)')
                ax.grid(True, alpha=0.3)
                
                # 최대 드로우다운 표시
                max_dd_idx = drawdown.idxmin()
                max_dd_date = dates.iloc[max_dd_idx]
                max_dd_value = drawdown.iloc[max_dd_idx]
                
                ax.annotate(f'최대 DD: {max_dd_value:.1f}%',
                           xy=(max_dd_date, max_dd_value),
                           xytext=(10, 10), textcoords='offset points',
                           bbox=dict(boxstyle='round,pad=0.3', fc='yellow', alpha=0.7),
                           arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))
                
                # 포맷팅
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
                ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
                plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
            else:
                ax.text(0.5, 0.5, 'Drawdown\\nData Not Available',
                       ha='center', va='center', transform=ax.transAxes)
                ax.set_title('드로우다운')
        except Exception as e:
            logger.warning(f"드로우다운 차트 생성 실패: {e}")
    
    def _plot_trade_analysis(self, ax, trade_history: pd.DataFrame):
        """거래 분석 차트"""
        try:
            if not trade_history.empty and 'asset' in trade_history.columns:
                # 자산별 거래량
                asset_volumes = trade_history.groupby('asset')['amount_krw'].sum()
                
                # 상위 5개 자산만 표시
                top_assets = asset_volumes.nlargest(5)
                
                bars = ax.bar(range(len(top_assets)), top_assets.values, color=self.colors[:len(top_assets)])
                ax.set_title('자산별 거래량 (상위 5개)', fontsize=12, fontweight='bold')
                ax.set_ylabel('거래량 (원)')
                ax.set_xticks(range(len(top_assets)))
                ax.set_xticklabels(top_assets.index, rotation=45)
                
                # 값 표시
                for bar, value in zip(bars, top_assets.values):
                    height = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width()/2., height,
                           f'{value/1e6:.1f}M',
                           ha='center', va='bottom')
                
                ax.grid(True, alpha=0.3)
            else:
                ax.text(0.5, 0.5, 'Trade Analysis\\nData Not Available',
                       ha='center', va='center', transform=ax.transAxes)
                ax.set_title('거래 분석')
        except Exception as e:
            logger.warning(f"거래 분석 차트 생성 실패: {e}")
    
    def _plot_performance_metrics(self, ax, performance: PerformanceMetrics):
        """성과 지표 요약"""
        try:
            # 주요 지표들
            metrics = {
                '총 수익률': f'{performance.total_return:.1%}',
                '연간 수익률': f'{performance.annualized_return:.1%}',
                '샤프 비율': f'{performance.sharpe_ratio:.2f}',
                '최대 낙폭': f'{performance.max_drawdown:.1%}',
                '변동성': f'{performance.volatility:.1%}',
                '승률': f'{performance.win_rate:.1%}'
            }
            
            # 테이블 형태로 표시
            ax.axis('off')  # 축 제거
            
            # 제목
            ax.text(0.5, 0.95, '주요 성과 지표', ha='center', va='top', 
                   transform=ax.transAxes, fontsize=14, fontweight='bold')
            
            # 지표들
            y_pos = 0.8
            for metric, value in metrics.items():
                ax.text(0.1, y_pos, metric + ':', ha='left', va='center',
                       transform=ax.transAxes, fontsize=11, fontweight='bold')
                ax.text(0.9, y_pos, value, ha='right', va='center',
                       transform=ax.transAxes, fontsize=11)
                y_pos -= 0.12
            
            # 성과 등급 표시
            if performance.sharpe_ratio > 1.5:
                grade = 'A+'
                color = 'green'
            elif performance.sharpe_ratio > 1.0:
                grade = 'A'
                color = 'lightgreen'
            elif performance.sharpe_ratio > 0.5:
                grade = 'B'
                color = 'orange'
            else:
                grade = 'C'
                color = 'red'
            
            # 등급 박스
            bbox = Rectangle((0.35, 0.05), 0.3, 0.15, 
                           facecolor=color, alpha=0.3, transform=ax.transAxes)
            ax.add_patch(bbox)
            ax.text(0.5, 0.125, f'등급: {grade}', ha='center', va='center',
                   transform=ax.transAxes, fontsize=16, fontweight='bold')
            
        except Exception as e:
            logger.warning(f"성과 지표 차트 생성 실패: {e}")
    
    def _create_text_dashboard(self, portfolio_history: pd.DataFrame, performance: PerformanceMetrics) -> str:
        """텍스트 기반 간단한 대시보드"""
        try:
            dashboard = f"""
📊 KAIROS-1 백테스팅 결과 대시보드
{'='*50}

📈 주요 성과 지표:
  • 총 수익률: {performance.total_return:.2%}
  • 연간 수익률: {performance.annualized_return:.2%}
  • 샤프 비율: {performance.sharpe_ratio:.2f}
  • 최대 낙폭: {performance.max_drawdown:.2%}
  • 변동성: {performance.volatility:.2%}
  • 승률: {performance.win_rate:.1%}

🔄 거래 통계:
  • 총 거래 수: {performance.total_trades}
  • 수익 거래: {performance.winning_trades}
  • 손실 거래: {performance.losing_trades}

📊 포트폴리오 요약:
  • 기간: {len(portfolio_history)}일
  • 초기 가치: {portfolio_history['total_value'].iloc[0]:,.0f}원 (추정)
  • 최종 가치: {portfolio_history['total_value'].iloc[-1]:,.0f}원 (추정)

⭐ 성과 등급: {'A+' if performance.sharpe_ratio > 1.5 else 'A' if performance.sharpe_ratio > 1.0 else 'B' if performance.sharpe_ratio > 0.5 else 'C'}
            """
            
            # 텍스트 파일로 저장
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"text_dashboard_{timestamp}.txt"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(dashboard)
            
            logger.info(f"텍스트 대시보드 저장: {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"텍스트 대시보드 생성 실패: {e}")
            return ""
    
    def create_comparison_chart(
        self, 
        results: Dict[str, PerformanceMetrics], 
        save_path: Optional[str] = None
    ) -> Optional[str]:
        """전략 비교 차트"""
        if not MATPLOTLIB_AVAILABLE:
            return self._create_text_comparison(results)
        
        try:
            fig, axes = plt.subplots(1, 3, figsize=(15, 5))
            fig.suptitle('전략 비교 분석', fontsize=16, fontweight='bold')
            
            strategies = list(results.keys())
            
            # 1. 수익률 비교
            returns = [results[s].annualized_return for s in strategies]
            axes[0].bar(strategies, returns, color=self.colors[:len(strategies)])
            axes[0].set_title('연간 수익률 비교')
            axes[0].set_ylabel('수익률')
            axes[0].yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:.1%}'))
            
            # 2. 샤프 비율 비교
            sharpe_ratios = [results[s].sharpe_ratio for s in strategies]
            axes[1].bar(strategies, sharpe_ratios, color=self.colors[:len(strategies)])
            axes[1].set_title('샤프 비율 비교')
            axes[1].set_ylabel('샤프 비율')
            axes[1].axhline(y=1.0, color='red', linestyle='--', alpha=0.5, label='우수 기준')
            axes[1].legend()
            
            # 3. 리스크-수익률 산점도
            volatilities = [results[s].volatility for s in strategies]
            scatter = axes[2].scatter(volatilities, returns, c=range(len(strategies)), 
                                    s=100, cmap='viridis', alpha=0.7)
            
            for i, strategy in enumerate(strategies):
                axes[2].annotate(strategy, (volatilities[i], returns[i]),
                               xytext=(5, 5), textcoords='offset points')
            
            axes[2].set_title('리스크-수익률 관계')
            axes[2].set_xlabel('변동성')
            axes[2].set_ylabel('수익률')
            axes[2].xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:.1%}'))
            axes[2].yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:.1%}'))
            axes[2].grid(True, alpha=0.3)
            
            plt.tight_layout()
            
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                return save_path
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                default_path = f"strategy_comparison_{timestamp}.png"
                plt.savefig(default_path, dpi=300, bbox_inches='tight')
                return default_path
                
        except Exception as e:
            logger.error(f"비교 차트 생성 실패: {e}")
            return None
        finally:
            if MATPLOTLIB_AVAILABLE:
                plt.close()
    
    def _create_text_comparison(self, results: Dict[str, PerformanceMetrics]) -> str:
        """텍스트 기반 전략 비교"""
        try:
            comparison = f"""
🔍 전략 비교 분석
{'='*60}

{'전략':<12} {'수익률':<10} {'샤프비율':<10} {'최대낙폭':<10} {'등급':<6}
{'-'*60}
"""
            
            for strategy, performance in results.items():
                grade = 'A+' if performance.sharpe_ratio > 1.5 else 'A' if performance.sharpe_ratio > 1.0 else 'B' if performance.sharpe_ratio > 0.5 else 'C'
                
                comparison += f"{strategy:<12} {performance.annualized_return:>8.1%} {performance.sharpe_ratio:>9.2f} {performance.max_drawdown:>9.1%} {grade:<6}\\n"
            
            # 최고 성과 전략
            best_strategy = max(results.keys(), key=lambda k: results[k].sharpe_ratio)
            comparison += f"""
🏆 최고 성과 전략: {best_strategy}
  • 샤프 비율: {results[best_strategy].sharpe_ratio:.2f}
  • 연간 수익률: {results[best_strategy].annualized_return:.1%}
  • 최대 낙폭: {results[best_strategy].max_drawdown:.1%}
            """
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"strategy_comparison_{timestamp}.txt"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(comparison)
            
            return filename
            
        except Exception as e:
            logger.error(f"텍스트 비교 생성 실패: {e}")
            return ""
    
    def create_interactive_report(self, report_data: Dict[str, Any]) -> str:
        """인터랙티브 HTML 리포트 생성"""
        try:
            # 간단한 HTML 리포트 템플릿
            html_content = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KAIROS-1 백테스팅 리포트</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .header h1 {{ color: #2c3e50; margin-bottom: 10px; }}
        .header p {{ color: #7f8c8d; }}
        .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .metric-card {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; text-align: center; }}
        .metric-value {{ font-size: 2em; font-weight: bold; margin: 10px 0; }}
        .metric-label {{ font-size: 0.9em; opacity: 0.9; }}
        .section {{ margin-bottom: 30px; }}
        .section h2 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
        .recommendations {{ background-color: #ecf0f1; padding: 20px; border-radius: 10px; }}
        .recommendation {{ margin-bottom: 15px; padding: 15px; background-color: white; border-radius: 5px; border-left: 4px solid #3498db; }}
        .priority-high {{ border-left-color: #e74c3c; }}
        .priority-medium {{ border-left-color: #f39c12; }}
        .priority-low {{ border-left-color: #27ae60; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 KAIROS-1 백테스팅 리포트</h1>
            <p>생성일: {datetime.now().strftime('%Y년 %m월 %d일 %H시 %M분')}</p>
        </div>
        
        <div class="metrics">
"""
            
            # 주요 지표 카드들
            summary = report_data.get('executive_summary', {})
            key_metrics = summary.get('key_metrics', {})
            
            metrics_cards = [
                ('총 수익률', f"{key_metrics.get('total_return', 0):.1%}", '전체 기간 수익률'),
                ('샤프 비율', f"{key_metrics.get('sharpe_ratio', 0):.2f}", '위험 대비 수익'),
                ('최대 낙폭', f"{key_metrics.get('max_drawdown', 0):.1%}", '최대 손실폭'),
                ('승률', f"{key_metrics.get('win_rate', 0):.1%}", '수익 거래 비율')
            ]
            
            for title, value, description in metrics_cards:
                html_content += f"""
            <div class="metric-card">
                <div class="metric-label">{title}</div>
                <div class="metric-value">{value}</div>
                <div class="metric-label">{description}</div>
            </div>
"""
            
            html_content += """
        </div>
        
        <div class="section">
            <h2>📊 성과 분석</h2>
            <p>백테스팅 기간 동안의 전략 성과를 종합 평가했습니다.</p>
"""
            
            # 성과 등급
            grade = summary.get('performance_grade', 'N/A')
            description = summary.get('performance_description', 'N/A')
            
            html_content += f"""
            <div style="text-align: center; margin: 20px 0;">
                <div style="display: inline-block; padding: 20px 40px; background-color: #2ecc71; color: white; border-radius: 50px; font-size: 1.5em; font-weight: bold;">
                    전체 등급: {grade} ({description})
                </div>
            </div>
        </div>
"""
            
            # 권장사항
            recommendations = report_data.get('recommendations', [])
            if recommendations:
                html_content += """
        <div class="section">
            <h2>💡 개선 권장사항</h2>
            <div class="recommendations">
"""
                
                for rec in recommendations:
                    priority_class = f"priority-{rec.get('priority', 'low').lower()}"
                    html_content += f"""
                <div class="recommendation {priority_class}">
                    <strong>[{rec.get('category', 'N/A')}]</strong> {rec.get('issue', 'N/A')}
                    <br><br>
                    💡 <strong>권장사항:</strong> {rec.get('recommendation', 'N/A')}
                </div>
"""
                
                html_content += """
            </div>
        </div>
"""
            
            html_content += """
        <div class="section">
            <h2>📈 상세 데이터</h2>
            <p>자세한 분석 결과는 JSON 파일을 참고하세요.</p>
        </div>
        
        <div style="text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid #bdc3c7; color: #7f8c8d;">
            <p>KAIROS-1 Cryptocurrency Investment System</p>
            <p>Powered by Advanced Portfolio Optimization</p>
        </div>
    </div>
</body>
</html>
"""
            
            # HTML 파일 저장
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"kairos1_report_{timestamp}.html"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"인터랙티브 리포트 생성: {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"HTML 리포트 생성 실패: {e}")
            return ""