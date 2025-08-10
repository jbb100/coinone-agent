#!/usr/bin/env python3
"""
KAIROS-1 향상된 백테스팅 데모

Buy-and-Hold 벤치마크 비교 및 일관된 결과 제공
"""

import sys
import os
sys.path.append('/Users/jongdal100/git/coinone-agent')

from datetime import datetime, timedelta
from src.backtesting.backtesting_engine import BacktestingEngine, BacktestConfig, BacktestMode
from src.backtesting.report_generator import BacktestReportGenerator
from src.backtesting.visualization import BacktestVisualizer
import pandas as pd
import numpy as np


def demo_with_benchmarks():
    """Buy-and-Hold 벤치마크와 비교하는 백테스팅 데모"""
    print("🚀 KAIROS-1 향상된 백테스팅 시스템 데모")
    print("=" * 60)
    print("📌 고정 시드로 일관된 결과 보장")
    print("📊 Buy-and-Hold 전략과 성과 비교")
    print("=" * 60)
    
    # 백테스팅 설정
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    
    config = BacktestConfig(
        start_date=start_date,
        end_date=end_date,
        initial_capital=10000000,  # 1천만원
        rebalance_frequency='monthly',
        mode=BacktestMode.SIMPLE,
        risk_level='moderate',
        transaction_cost=0.001,
        use_dynamic_optimization=False
    )
    
    print(f"\n📅 테스트 기간: {start_date} ~ {end_date}")
    print(f"💰 초기 자본: {config.initial_capital:,.0f}원")
    print(f"🔄 리밸런싱: {config.rebalance_frequency}")
    
    # 백테스팅 실행 (벤치마크 계산 포함)
    print("\n🔄 백테스팅 실행 중...")
    engine = BacktestingEngine(config)
    engine.load_historical_data('demo')  # 고정 시드로 일관된 데이터
    performance = engine.run_backtest(calculate_benchmarks=True)
    
    # 벤치마크 비교 데이터 가져오기
    benchmark_comparison = engine.get_benchmark_comparison()
    
    # 결과 출력
    print("\n" + "="*60)
    print("📊 전략 성과 결과")
    print("="*60)
    print(f"💹 총 수익률: {performance.total_return:.2%}")
    print(f"📈 연간 수익률: {performance.annualized_return:.2%}")
    print(f"⚡ 샤프 비율: {performance.sharpe_ratio:.2f}")
    print(f"📉 최대 낙폭: {performance.max_drawdown:.2%}")
    print(f"🎯 승률: {performance.win_rate:.1%}")
    print(f"🔄 총 거래 수: {performance.total_trades}")
    
    # Buy-and-Hold 벤치마크 비교
    print("\n" + "="*60)
    print("🆚 Buy-and-Hold 전략과 비교")
    print("="*60)
    
    if 'benchmarks' in benchmark_comparison:
        benchmarks = benchmark_comparison['benchmarks']
        strategy_return = benchmark_comparison['strategy']['total_return']
        
        # 테이블 헤더
        print(f"{'자산':<10} {'Buy&Hold 수익률':<15} {'전략 대비':<15} {'결과':<10}")
        print("-" * 60)
        
        # 각 자산별 비교
        for asset, bench_data in benchmarks.items():
            if asset == 'EQUAL_WEIGHT':
                continue
            bh_return = bench_data['total_return']
            diff = strategy_return - bh_return
            result = "✅ 승리" if diff > 0 else "❌ 패배"
            print(f"{asset:<10} {bh_return:>13.2%} {diff:>13.2%} {result:<10}")
        
        # 균등 가중 포트폴리오
        if 'EQUAL_WEIGHT' in benchmarks:
            eq_data = benchmarks['EQUAL_WEIGHT']
            eq_return = eq_data['total_return']
            diff = strategy_return - eq_return
            result = "✅ 승리" if diff > 0 else "❌ 패배"
            print("-" * 60)
            print(f"{'균등가중':<10} {eq_return:>13.2%} {diff:>13.2%} {result:<10}")
        
        # 전략 평가
        outperform_count = sum(1 for asset, data in benchmark_comparison['outperformance'].items() 
                              if data['is_better'])
        total_assets = len(benchmark_comparison['outperformance'])
        
        print("\n" + "="*60)
        print("🎯 전략 평가")
        print("="*60)
        print(f"✅ 전략이 이긴 자산: {outperform_count}/{total_assets}")
        
        # 최고 벤치마크와 비교
        best_asset = max(benchmarks.items(), 
                        key=lambda x: x[1]['total_return'] if x[0] != 'EQUAL_WEIGHT' else 0)
        print(f"🏆 최고 성과 벤치마크: {best_asset[0]} ({best_asset[1]['total_return']:.2%})")
        
        if strategy_return > best_asset[1]['total_return']:
            print(f"🎉 전략이 최고 벤치마크를 이김! (+{strategy_return - best_asset[1]['total_return']:.2%})")
        else:
            print(f"💡 전략이 최고 벤치마크에 못 미침 ({strategy_return - best_asset[1]['total_return']:.2%})")
        
        # 전략의 장점 분석
        print("\n📈 전략의 강점:")
        if performance.sharpe_ratio > np.mean([b['sharpe_ratio'] for b in benchmarks.values()]):
            print("  ✅ 위험 대비 수익률(샤프 비율)이 우수함")
        if performance.max_drawdown < np.mean([b['max_drawdown'] for b in benchmarks.values()]):
            print("  ✅ 최대 낙폭이 개별 자산보다 낮음 (리스크 관리 우수)")
        if performance.volatility < np.mean([b['volatility'] for b in benchmarks.values()]):
            print("  ✅ 변동성이 개별 자산보다 낮음 (안정적)")
        
        # 투자 권장사항
        print("\n💡 투자 권장사항:")
        if strategy_return > eq_data['total_return']:
            print("  → 단순 균등 분산 투자보다 우수한 성과")
            print("  → 리밸런싱 전략이 효과적으로 작동함")
        else:
            print("  → 전략 개선이 필요함")
            print("  → 리밸런싱 주기나 자산 선택 재검토 필요")
    
    # 상세 리포트 생성
    print("\n📋 상세 리포트 생성...")
    report_generator = BacktestReportGenerator()
    
    comprehensive_report = report_generator.generate_comprehensive_report(
        performance=performance,
        config=config,
        portfolio_history=engine.get_portfolio_history(),
        trade_history=engine.get_trade_history(),
        benchmark_performance=benchmark_comparison.get('benchmarks')
    )
    
    # 리포트 저장
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"enhanced_backtest_report_{timestamp}.json"
    report_generator.save_report_to_file(comprehensive_report, report_file)
    print(f"✅ 상세 리포트 저장: {report_file}")
    
    return performance, benchmark_comparison


def compare_multiple_strategies():
    """여러 전략과 Buy-and-Hold 비교"""
    print("\n" + "="*60)
    print("🔍 여러 전략 비교 분석")
    print("="*60)
    
    strategies = ['conservative', 'moderate', 'aggressive']
    results = {}
    benchmarks_all = {}
    
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    
    for strategy in strategies:
        print(f"\n📊 {strategy.capitalize()} 전략 실행...")
        
        config = BacktestConfig(
            start_date=start_date,
            end_date=end_date,
            initial_capital=10000000,
            rebalance_frequency='monthly',
            mode=BacktestMode.SIMPLE,
            risk_level=strategy,
            transaction_cost=0.001
        )
        
        engine = BacktestingEngine(config)
        engine.load_historical_data('demo')
        performance = engine.run_backtest(calculate_benchmarks=True)
        
        results[strategy] = {
            'performance': performance,
            'benchmarks': engine.get_benchmark_comparison()
        }
        
        # 첫 번째 전략의 벤치마크 저장 (모든 전략이 같은 데이터 사용)
        if not benchmarks_all:
            benchmarks_all = engine.get_benchmark_comparison()['benchmarks']
    
    # 비교 결과 테이블
    print("\n" + "="*60)
    print("🏆 전략별 성과 비교")
    print("="*60)
    print(f"{'전략':<12} {'수익률':<12} {'연간수익':<12} {'샤프비율':<10} {'최대낙폭':<10}")
    print("-" * 60)
    
    for strategy, data in results.items():
        perf = data['performance']
        print(f"{strategy:<12} {perf.total_return:>10.2%} {perf.annualized_return:>10.2%} "
              f"{perf.sharpe_ratio:>9.2f} {perf.max_drawdown:>9.2%}")
    
    # Buy-and-Hold 벤치마크 추가
    print("-" * 60)
    for asset, bench_data in benchmarks_all.items():
        if asset != 'EQUAL_WEIGHT':
            print(f"{asset+' B&H':<12} {bench_data['total_return']:>10.2%} "
                  f"{bench_data['annualized_return']:>10.2%} "
                  f"{bench_data['sharpe_ratio']:>9.2f} {bench_data['max_drawdown']:>9.2%}")
    
    # 최종 추천
    best_strategy = max(results.keys(), 
                       key=lambda k: results[k]['performance'].sharpe_ratio)
    best_benchmark = max(benchmarks_all.items(),
                        key=lambda x: x[1]['total_return'])
    
    print("\n" + "="*60)
    print("📊 최종 분석")
    print("="*60)
    print(f"🥇 최고 전략: {best_strategy} (샤프 비율: {results[best_strategy]['performance'].sharpe_ratio:.2f})")
    print(f"🏆 최고 Buy&Hold: {best_benchmark[0]} (수익률: {best_benchmark[1]['total_return']:.2%})")
    
    if results[best_strategy]['performance'].total_return > best_benchmark[1]['total_return']:
        print("\n✅ 결론: 액티브 전략이 패시브 Buy&Hold보다 우수합니다!")
    else:
        print("\n💡 결론: Buy&Hold 전략도 고려해볼 만합니다.")


def main():
    """메인 데모 함수"""
    try:
        # 1. 벤치마크 비교 포함 백테스팅
        performance, benchmarks = demo_with_benchmarks()
        
        # 2. 여러 전략 비교
        compare_multiple_strategies()
        
        print("\n" + "="*60)
        print("🎉 향상된 백테스팅 데모 완료!")
        print("="*60)
        print("\n💡 핵심 개선사항:")
        print("  ✅ 고정 시드 사용으로 일관된 결과 보장")
        print("  ✅ Buy-and-Hold 전략과 직접 비교")
        print("  ✅ 개별 코인 및 균등 포트폴리오 벤치마크")
        print("  ✅ 전략의 실제 가치 평가 가능")
        
    except Exception as e:
        print(f"❌ 데모 실행 실패: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()