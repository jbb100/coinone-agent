#!/usr/bin/env python3
"""
전략별 차이 테스트
"""

import sys
import os
sys.path.append('/Users/jongdal100/git/coinone-agent')

from datetime import datetime, timedelta
from src.backtesting.backtesting_engine import BacktestingEngine, BacktestConfig, BacktestMode

def test_strategies():
    """세 가지 전략 비교"""
    print("🔍 전략별 차이 테스트")
    print("=" * 60)
    
    strategies = ['conservative', 'moderate', 'aggressive']
    results = {}
    
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
        performance = engine.run_backtest(calculate_benchmarks=False)
        
        results[strategy] = performance
        
        print(f"  💰 총 수익률: {performance.total_return:.2%}")
        print(f"  📈 연간 수익률: {performance.annualized_return:.2%}")
        print(f"  ⚡ 샤프 비율: {performance.sharpe_ratio:.2f}")
        print(f"  📉 최대 낙폭: {performance.max_drawdown:.2%}")
        print(f"  🔄 거래 수: {performance.total_trades}")
    
    # 비교 결과 출력
    print("\n" + "="*60)
    print("🏆 전략 비교 결과")
    print("="*60)
    print(f"{'전략':<12} {'수익률':<10} {'샤프비율':<10} {'최대낙폭':<10} {'거래수':<8}")
    print("-" * 60)
    
    for strategy, performance in results.items():
        print(f"{strategy:<12} {performance.total_return:>8.1%} "
              f"{performance.sharpe_ratio:>9.2f} "
              f"{performance.max_drawdown:>9.1%} "
              f"{performance.total_trades:>7}")
    
    # 차이 분석
    print("\n📊 전략 간 차이 분석:")
    cons_return = results['conservative'].total_return
    mod_return = results['moderate'].total_return
    agg_return = results['aggressive'].total_return
    
    print(f"Conservative vs Moderate: {(mod_return - cons_return)*100:.1f}%p 차이")
    print(f"Moderate vs Aggressive: {(agg_return - mod_return)*100:.1f}%p 차이")
    print(f"Conservative vs Aggressive: {(agg_return - cons_return)*100:.1f}%p 차이")
    
    # 전략별 특징
    print("\n💡 전략별 특징:")
    if results['conservative'].max_drawdown < results['aggressive'].max_drawdown:
        print("✅ Conservative가 예상대로 낮은 리스크 (낮은 최대 낙폭)")
    if results['aggressive'].total_return > results['conservative'].total_return:
        print("✅ Aggressive가 예상대로 높은 수익률")
    if results['moderate'].sharpe_ratio > results['conservative'].sharpe_ratio and \
       results['moderate'].sharpe_ratio > results['aggressive'].sharpe_ratio:
        print("✅ Moderate가 가장 균형잡힌 위험-수익 비율")

if __name__ == "__main__":
    test_strategies()