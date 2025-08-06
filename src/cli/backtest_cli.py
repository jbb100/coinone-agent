"""
Backtesting CLI Commands

백테스팅 시스템을 위한 CLI 명령어 인터페이스
"""

import click
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Optional
from loguru import logger

from ..backtesting.backtesting_engine import BacktestingEngine, BacktestConfig, BacktestMode
from ..backtesting.report_generator import BacktestReportGenerator


@click.group()
def backtest():
    """백테스팅 관련 명령어들"""
    pass


@backtest.command()
@click.option('--start-date', 
              type=str, 
              required=True,
              help='백테스팅 시작일 (YYYY-MM-DD)')
@click.option('--end-date', 
              type=str, 
              required=True,
              help='백테스팅 종료일 (YYYY-MM-DD)')
@click.option('--initial-capital', 
              type=float, 
              default=10000000,
              help='초기 자본 (원, 기본값: 1천만원)')
@click.option('--rebalance-frequency',
              type=click.Choice(['daily', 'weekly', 'monthly', 'quarterly']),
              default='monthly',
              help='리밸런싱 주기')
@click.option('--mode',
              type=click.Choice(['simple', 'advanced', 'comparison']),
              default='simple',
              help='백테스팅 모드')
@click.option('--risk-level',
              type=click.Choice(['conservative', 'moderate', 'aggressive']),
              default='moderate',
              help='리스크 수준')
@click.option('--use-dynamic-optimization',
              is_flag=True,
              help='동적 포트폴리오 최적화 사용')
@click.option('--transaction-cost',
              type=float,
              default=0.001,
              help='거래 수수료 (기본값: 0.1%)')
@click.option('--data-source',
              type=click.Choice(['demo', 'yfinance']),
              default='demo',
              help='데이터 소스')
@click.option('--output-file',
              type=str,
              help='결과 저장 파일명')
@click.option('--verbose',
              is_flag=True,
              help='상세 로그 출력')
def run(start_date: str, end_date: str, initial_capital: float, 
        rebalance_frequency: str, mode: str, risk_level: str,
        use_dynamic_optimization: bool, transaction_cost: float,
        data_source: str, output_file: str, verbose: bool):
    """백테스팅 실행"""
    try:
        # 로그 레벨 설정
        if verbose:
            logger.add("backtest.log", level="DEBUG")
        
        click.echo(f"🚀 KAIROS-1 백테스팅 시작")
        click.echo(f"📅 기간: {start_date} ~ {end_date}")
        click.echo(f"💰 초기 자본: {initial_capital:,.0f}원")
        click.echo(f"🔄 리밸런싱: {rebalance_frequency}")
        click.echo(f"📊 모드: {mode} ({risk_level})")
        
        # 백테스팅 설정
        config = BacktestConfig(
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            rebalance_frequency=rebalance_frequency,
            mode=BacktestMode(mode),
            risk_level=risk_level,
            use_dynamic_optimization=use_dynamic_optimization,
            transaction_cost=transaction_cost
        )
        
        # 백테스팅 엔진 초기화
        click.echo("\n📊 백테스팅 엔진 초기화...")
        engine = BacktestingEngine(config)
        
        # 데이터 로드
        click.echo(f"📈 데이터 로드 중... (소스: {data_source})")
        success = engine.load_historical_data(data_source)
        
        if not success:
            click.echo("❌ 데이터 로드 실패")
            return
        
        click.echo(f"✅ 데이터 로드 완료: {len(engine.historical_data)}개 자산")
        
        # 백테스팅 실행
        click.echo("\\n🔄 백테스팅 실행 중...")
        with click.progressbar(length=100, label='백테스팅 진행') as bar:
            performance = engine.run_backtest()
            bar.update(100)
        
        # 결과 출력
        click.echo("\\n🎉 백테스팅 완료!")
        click.echo("\\n📊 주요 결과:")
        click.echo(f"  💹 총 수익률: {performance.total_return:.2%}")
        click.echo(f"  📈 연간 수익률: {performance.annualized_return:.2%}")
        click.echo(f"  ⚡ 샤프 비율: {performance.sharpe_ratio:.2f}")
        click.echo(f"  📉 최대 낙폭: {performance.max_drawdown:.2%}")
        click.echo(f"  🎯 승률: {performance.win_rate:.1%}")
        click.echo(f"  🔄 총 거래 수: {performance.total_trades}")
        
        # 상세 리포트 생성
        click.echo("\\n📋 상세 리포트 생성 중...")
        report_generator = BacktestReportGenerator()
        
        portfolio_history = engine.get_portfolio_history()
        trade_history = engine.get_trade_history()
        
        comprehensive_report = report_generator.generate_comprehensive_report(
            performance=performance,
            config=config,
            portfolio_history=portfolio_history,
            trade_history=trade_history
        )
        
        # 파일 저장
        if output_file:
            filename = output_file
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"kairos1_backtest_{timestamp}.json"
        
        report_generator.save_report_to_file(comprehensive_report, filename)
        click.echo(f"✅ 상세 리포트 저장: {filename}")
        
        # 요약 출력
        summary_text = report_generator.generate_summary_text(comprehensive_report)
        click.echo("\\n" + summary_text)
        
    except Exception as e:
        click.echo(f"❌ 백테스팅 실패: {e}")
        if verbose:
            import traceback
            traceback.print_exc()


@backtest.command()
@click.option('--start-date', 
              type=str, 
              required=True,
              help='비교 시작일 (YYYY-MM-DD)')
@click.option('--end-date', 
              type=str, 
              required=True,
              help='비교 종료일 (YYYY-MM-DD)')
@click.option('--initial-capital', 
              type=float, 
              default=10000000,
              help='초기 자본')
@click.option('--strategies',
              type=str,
              default='conservative,moderate,aggressive',
              help='비교할 전략들 (쉼표로 구분)')
def compare(start_date: str, end_date: str, initial_capital: float, strategies: str):
    """여러 전략 비교 백테스팅"""
    try:
        click.echo("🔍 전략 비교 백테스팅 시작")
        
        strategy_list = [s.strip() for s in strategies.split(',')]
        results = {}
        
        for strategy in strategy_list:
            click.echo(f"\\n📊 {strategy} 전략 실행...")
            
            config = BacktestConfig(
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                rebalance_frequency='monthly',
                mode=BacktestMode.SIMPLE,
                risk_level=strategy
            )
            
            engine = BacktestingEngine(config)
            engine.load_historical_data('demo')
            performance = engine.run_backtest()
            
            results[strategy] = {
                'total_return': performance.total_return,
                'annualized_return': performance.annualized_return,
                'sharpe_ratio': performance.sharpe_ratio,
                'max_drawdown': performance.max_drawdown,
                'volatility': performance.volatility
            }
            
            click.echo(f"  수익률: {performance.total_return:.2%}")
            click.echo(f"  샤프비율: {performance.sharpe_ratio:.2f}")
        
        # 비교 결과 출력
        click.echo("\\n🏆 전략 비교 결과:")
        click.echo("=" * 60)
        click.echo(f"{'전략':<12} {'수익률':<10} {'샤프비율':<10} {'최대낙폭':<10}")
        click.echo("-" * 60)
        
        for strategy, metrics in results.items():
            click.echo(f"{strategy:<12} "
                      f"{metrics['total_return']:>8.1%} "
                      f"{metrics['sharpe_ratio']:>9.2f} "
                      f"{metrics['max_drawdown']:>9.1%}")
        
        # 최고 성과 전략 추천
        best_strategy = max(results.keys(), key=lambda k: results[k]['sharpe_ratio'])
        click.echo(f"\\n🥇 추천 전략: {best_strategy}")
        click.echo(f"   샤프비율이 {results[best_strategy]['sharpe_ratio']:.2f}로 가장 우수합니다")
        
    except Exception as e:
        click.echo(f"❌ 전략 비교 실패: {e}")


@backtest.command()
@click.option('--config-file',
              type=click.Path(exists=True),
              help='설정 파일 경로 (.json)')
@click.option('--template',
              type=click.Choice(['basic', 'advanced', 'custom']),
              default='basic',
              help='템플릿 유형')
def quick(config_file: str, template: str):
    """빠른 백테스팅 (미리 설정된 템플릿 사용)"""
    try:
        click.echo(f"⚡ 빠른 백테스팅 ({template} 템플릿)")
        
        if config_file:
            # 설정 파일에서 로드
            with open(config_file, 'r') as f:
                config_dict = json.load(f)
            config = BacktestConfig(**config_dict)
        else:
            # 템플릿 기본 설정
            end_date = datetime.now().strftime('%Y-%m-%d')
            
            if template == 'basic':
                start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
                config = BacktestConfig(
                    start_date=start_date,
                    end_date=end_date,
                    initial_capital=10000000,
                    rebalance_frequency='monthly',
                    mode=BacktestMode.SIMPLE,
                    risk_level='moderate'
                )
            elif template == 'advanced':
                start_date = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')  # 2년
                config = BacktestConfig(
                    start_date=start_date,
                    end_date=end_date,
                    initial_capital=50000000,  # 5천만원
                    rebalance_frequency='weekly',
                    mode=BacktestMode.ADVANCED,
                    risk_level='moderate',
                    use_dynamic_optimization=True
                )
            else:  # custom
                click.echo("사용자 정의 설정을 입력하세요:")
                start_date = click.prompt("시작일 (YYYY-MM-DD)", 
                                        default=(datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'))
                initial_capital = click.prompt("초기 자본 (원)", default=10000000)
                
                config = BacktestConfig(
                    start_date=start_date,
                    end_date=end_date,
                    initial_capital=initial_capital,
                    rebalance_frequency='monthly',
                    mode=BacktestMode.SIMPLE,
                    risk_level='moderate'
                )
        
        # 백테스팅 실행
        click.echo("🔄 백테스팅 실행...")
        engine = BacktestingEngine(config)
        engine.load_historical_data('demo')
        performance = engine.run_backtest()
        
        # 간단한 결과 출력
        click.echo("\\n✅ 결과 요약:")
        click.echo(f"📈 총 수익률: {performance.total_return:.2%}")
        click.echo(f"⚡ 샤프 비율: {performance.sharpe_ratio:.2f}")
        click.echo(f"📉 최대 낙폭: {performance.max_drawdown:.2%}")
        
        # 성과 평가
        if performance.sharpe_ratio > 1.0:
            click.echo("🎉 우수한 성과입니다!")
        elif performance.sharpe_ratio > 0.5:
            click.echo("👍 괜찮은 성과입니다.")
        else:
            click.echo("⚠️ 전략 개선이 필요합니다.")
            
    except Exception as e:
        click.echo(f"❌ 빠른 백테스팅 실패: {e}")


@backtest.command()
@click.argument('report_file', type=click.Path(exists=True))
@click.option('--format',
              type=click.Choice(['summary', 'detailed', 'charts']),
              default='summary',
              help='출력 형식')
def analyze(report_file: str, format: str):
    """백테스팅 결과 분석"""
    try:
        click.echo(f"📋 백테스팅 결과 분석: {report_file}")
        
        # 리포트 파일 로드
        with open(report_file, 'r', encoding='utf-8') as f:
            report = json.load(f)
        
        if format == 'summary':
            # 요약 출력
            summary = report.get('executive_summary', {})
            click.echo("\\n📊 요약:")
            click.echo(f"  등급: {summary.get('performance_grade', 'N/A')}")
            
            key_metrics = summary.get('key_metrics', {})
            click.echo(f"  수익률: {key_metrics.get('total_return', 0):.2%}")
            click.echo(f"  샤프비율: {key_metrics.get('sharpe_ratio', 0):.2f}")
            
        elif format == 'detailed':
            # 상세 분석
            performance = report.get('performance_metrics', {})
            
            click.echo("\\n📈 수익률 분석:")
            returns = performance.get('returns', {})
            for metric, data in returns.items():
                click.echo(f"  {data.get('description', metric)}: {data.get('formatted', 'N/A')}")
            
            click.echo("\\n⚠️ 리스크 분석:")
            risk = performance.get('risk', {})
            for metric, data in risk.items():
                click.echo(f"  {data.get('description', metric)}: {data.get('formatted', 'N/A')}")
                
            click.echo("\\n🔄 거래 분석:")
            trading = performance.get('trading', {})
            for metric, data in trading.items():
                click.echo(f"  {data.get('description', metric)}: {data.get('formatted', 'N/A')}")
        
        elif format == 'charts':
            # 차트 데이터 정보
            charts_data = report.get('charts_data', {})
            click.echo("\\n📊 차트 데이터:")
            
            if 'portfolio_value' in charts_data:
                pv_data = charts_data['portfolio_value']
                click.echo(f"  포트폴리오 가치: {len(pv_data.get('dates', []))}일 데이터")
            
            if 'trade_frequency' in charts_data:
                tf_data = charts_data['trade_frequency']
                click.echo(f"  거래 빈도: {len(tf_data.get('dates', []))}일 데이터")
        
        # 권장사항 출력
        recommendations = report.get('recommendations', [])
        if recommendations:
            click.echo(f"\\n💡 권장사항 ({len(recommendations)}개):")
            for i, rec in enumerate(recommendations, 1):
                click.echo(f"  {i}. [{rec.get('priority', 'N/A')}] {rec.get('issue', 'N/A')}")
                click.echo(f"     → {rec.get('recommendation', 'N/A')}")
        
    except Exception as e:
        click.echo(f"❌ 결과 분석 실패: {e}")


@backtest.command()
@click.option('--output-file',
              type=str,
              default='backtest_config_template.json',
              help='출력할 설정 파일명')
def config_template(output_file: str):
    """백테스팅 설정 템플릿 생성"""
    try:
        template_config = {
            "start_date": "2023-01-01",
            "end_date": "2024-01-01", 
            "initial_capital": 10000000,
            "rebalance_frequency": "monthly",
            "mode": "simple",
            "risk_level": "moderate",
            "use_dynamic_optimization": False,
            "transaction_cost": 0.001,
            "slippage": 0.0005,
            "max_drawdown_threshold": 0.20,
            "_comments": {
                "start_date": "백테스팅 시작일 (YYYY-MM-DD)",
                "end_date": "백테스팅 종료일 (YYYY-MM-DD)",
                "initial_capital": "초기 자본 (원)",
                "rebalance_frequency": "리밸런싱 주기 (daily/weekly/monthly/quarterly)",
                "mode": "백테스팅 모드 (simple/advanced/comparison)",
                "risk_level": "리스크 수준 (conservative/moderate/aggressive)",
                "transaction_cost": "거래 수수료 비율",
                "slippage": "슬리피지 비율"
            }
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(template_config, f, indent=2, ensure_ascii=False)
        
        click.echo(f"✅ 설정 템플릿 생성: {output_file}")
        click.echo("파일을 수정한 후 --config-file 옵션으로 사용하세요")
        
    except Exception as e:
        click.echo(f"❌ 템플릿 생성 실패: {e}")


if __name__ == '__main__':
    backtest()