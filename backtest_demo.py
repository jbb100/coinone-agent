#!/usr/bin/env python3
"""
KAIROS-1 백테스팅 데모

백테스팅 시스템의 주요 기능을 시연하는 데모 스크립트
"""

import sys
import os
sys.path.append('/Users/jongdal100/git/coinone-agent')

from datetime import datetime, timedelta
from src.backtesting.backtesting_engine import BacktestingEngine, BacktestConfig, BacktestMode
from src.backtesting.report_generator import BacktestReportGenerator
from src.backtesting.visualization import BacktestVisualizer


def demo_basic_backtest():
    """기본 백테스팅 데모"""
    print("🚀 KAIROS-1 백테스팅 시스템 데모")
    print("=" * 50)
    
    # 백테스팅 설정 (6개월)
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
    
    config = BacktestConfig(
        start_date=start_date,
        end_date=end_date,
        initial_capital=50000000,  # 5천만원
        rebalance_frequency='monthly',
        mode=BacktestMode.SIMPLE,
        risk_level='moderate',
        transaction_cost=0.001,
        use_dynamic_optimization=False
    )
    
    print(f"📅 테스트 기간: {start_date} ~ {end_date}")
    print(f"💰 초기 자본: {config.initial_capital:,.0f}원")
    print(f"🔄 리밸런싱: {config.rebalance_frequency}")
    
    # 백테스팅 실행
    print("\n🔄 백테스팅 실행 중...")
    engine = BacktestingEngine(config)
    engine.load_historical_data('demo')
    performance = engine.run_backtest()
    
    # 결과 출력
    print("\n📊 백테스팅 결과:")
    print(f"  💹 총 수익률: {performance.total_return:.2%}")
    print(f"  📈 연간 수익률: {performance.annualized_return:.2%}")
    print(f"  ⚡ 샤프 비율: {performance.sharpe_ratio:.2f}")
    print(f"  📉 최대 낙폭: {performance.max_drawdown:.2%}")
    print(f"  🔄 총 거래 수: {performance.total_trades}")
    
    # 상세 리포트 생성
    print("\n📋 상세 리포트 생성...")
    report_generator = BacktestReportGenerator()
    
    comprehensive_report = report_generator.generate_comprehensive_report(
        performance=performance,
        config=config,
        portfolio_history=engine.get_portfolio_history(),
        trade_history=engine.get_trade_history()
    )
    
    # JSON 리포트 저장
    report_file = report_generator.save_report_to_file(comprehensive_report)
    print(f"✅ JSON 리포트 저장: {report_file}")
    
    # HTML 리포트 생성
    visualizer = BacktestVisualizer()
    html_report = visualizer.create_interactive_report(comprehensive_report)
    print(f"✅ HTML 리포트 생성: {html_report}")
    
    # 요약 출력
    summary = report_generator.generate_summary_text(comprehensive_report)
    print("\n" + "="*50)
    print(summary)
    
    return performance, comprehensive_report


def demo_strategy_comparison():
    """전략 비교 데모"""
    print("\n🔍 전략 비교 백테스팅 데모")
    print("=" * 50)
    
    strategies = ['conservative', 'moderate', 'aggressive']
    results = {}
    
    # 공통 설정
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
    
    for strategy in strategies:
        print(f"\n📊 {strategy.capitalize()} 전략 실행...")
        
        config = BacktestConfig(
            start_date=start_date,
            end_date=end_date,
            initial_capital=30000000,  # 3천만원
            rebalance_frequency='monthly',
            mode=BacktestMode.SIMPLE,
            risk_level=strategy,
            transaction_cost=0.001
        )
        
        engine = BacktestingEngine(config)
        engine.load_historical_data('demo')
        performance = engine.run_backtest()
        
        results[strategy] = performance
        print(f"  수익률: {performance.total_return:.2%}")
        print(f"  샤프비율: {performance.sharpe_ratio:.2f}")
        print(f"  최대낙폭: {performance.max_drawdown:.2%}")
    
    # 비교 결과 출력
    print("\n🏆 전략 비교 결과:")
    print("=" * 70)
    print(f"{'전략':<12} {'수익률':<10} {'샤프비율':<10} {'최대낙폭':<10} {'거래수':<8}")
    print("-" * 70)
    
    for strategy, performance in results.items():
        print(f"{strategy:<12} "
              f"{performance.total_return:>8.1%} "
              f"{performance.sharpe_ratio:>9.2f} "
              f"{performance.max_drawdown:>9.1%} "
              f"{performance.total_trades:>7}")
    
    # 최고 성과 전략
    best_strategy = max(results.keys(), key=lambda k: results[k].sharpe_ratio)
    print(f"\n🥇 최고 성과 전략: {best_strategy}")
    print(f"   샤프비율: {results[best_strategy].sharpe_ratio:.2f}")
    
    # 시각화 생성
    visualizer = BacktestVisualizer()
    comparison_chart = visualizer.create_comparison_chart(results)
    if comparison_chart:
        print(f"📊 비교 차트 생성: {comparison_chart}")
    
    return results


def demo_advanced_backtest():
    """고급 백테스팅 데모 (동적 최적화 포함)"""
    print("\n🚀 고급 백테스팅 데모 (동적 최적화)")
    print("=" * 50)
    
    # 1년 기간
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    
    config = BacktestConfig(
        start_date=start_date,
        end_date=end_date,
        initial_capital=100000000,  # 1억원
        rebalance_frequency='weekly',  # 주간 리밸런싱
        mode=BacktestMode.ADVANCED,
        risk_level='moderate',
        use_dynamic_optimization=True,  # 동적 최적화 활성화
        transaction_cost=0.0005,  # 더 낮은 수수료
        max_drawdown_threshold=0.15  # 15% 최대 낙폭 한도
    )
    
    print(f"📅 테스트 기간: {start_date} ~ {end_date} (1년)")
    print(f"💰 초기 자본: {config.initial_capital:,.0f}원")
    print(f"🔄 리밸런싱: {config.rebalance_frequency}")
    print(f"🤖 동적 최적화: {config.use_dynamic_optimization}")
    
    # 백테스팅 실행
    print("\n🔄 고급 백테스팅 실행 중...")
    engine = BacktestingEngine(config)
    engine.load_historical_data('demo')
    performance = engine.run_backtest()
    
    # 결과 출력
    print("\n📊 고급 백테스팅 결과:")
    print(f"  💹 총 수익률: {performance.total_return:.2%}")
    print(f"  📈 연간 수익률: {performance.annualized_return:.2%}")
    print(f"  ⚡ 샤프 비율: {performance.sharpe_ratio:.2f}")
    print(f"  📉 최대 낙폭: {performance.max_drawdown:.2%}")
    print(f"  🎯 승률: {performance.win_rate:.1%}")
    print(f"  🔄 총 거래 수: {performance.total_trades}")
    print(f"  💰 수익 거래: {performance.winning_trades}")
    print(f"  📉 손실 거래: {performance.losing_trades}")
    
    # 성과 등급 평가
    if performance.sharpe_ratio > 1.5:
        grade = "A+ (매우 우수)"
        emoji = "🏆"
    elif performance.sharpe_ratio > 1.0:
        grade = "A (우수)"
        emoji = "🥇"
    elif performance.sharpe_ratio > 0.5:
        grade = "B (양호)"
        emoji = "👍"
    else:
        grade = "C (개선 필요)"
        emoji = "📈"
    
    print(f"\n{emoji} 성과 등급: {grade}")
    
    return performance


def main():
    """메인 데모 함수"""
    try:
        # 1. 기본 백테스팅
        basic_performance, basic_report = demo_basic_backtest()
        
        # 2. 전략 비교
        comparison_results = demo_strategy_comparison()
        
        # 3. 고급 백테스팅
        advanced_performance = demo_advanced_backtest()
        
        # 전체 요약
        print("\n" + "="*60)
        print("🎉 KAIROS-1 백테스팅 시스템 데모 완료!")
        print("="*60)
        
        print("\n📊 데모 결과 요약:")
        print(f"✅ 기본 백테스팅 - 샤프비율: {basic_performance.sharpe_ratio:.2f}")
        print(f"✅ 전략 비교 - {len(comparison_results)}개 전략 비교")
        print(f"✅ 고급 백테스팅 - 샤프비율: {advanced_performance.sharpe_ratio:.2f}")
        
        print("\n🎯 백테스팅 시스템 특징:")
        print("  🔹 완전 자동화된 백테스팅 엔진")
        print("  🔹 다양한 리밸런싱 전략 지원")
        print("  🔹 상세한 성과 분석 및 리포트")
        print("  🔹 시각화 및 HTML 리포트")
        print("  🔹 CLI를 통한 편리한 사용")
        
        print("\n🚀 이제 실제 투자 전략을 백테스팅해보세요!")
        
    except Exception as e:
        print(f"❌ 데모 실행 실패: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()