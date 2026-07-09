"""
테스트 전용 Rebalancer 서브클래스

과거 프로덕션 Rebalancer 클래스에 섞여 있던 목업 메서드들
(아무것도 실행하지 않고 success를 반환)을 테스트 더블로 분리한 것.

프로덕션 코드는 이 클래스를 절대 사용하면 안 된다 —
실제 리밸런싱은 Rebalancer.execute_quarterly_rebalance()가 담당한다.
"""

from datetime import datetime, timedelta
from typing import Dict, List

from src.core.rebalancer import Rebalancer


class SimulatedRebalancer(Rebalancer):
    """실주문 없이 리밸런싱 흐름만 흉내내는 테스트 더블"""

    async def generate_rebalancing_plan(self, target_weights: Dict[str, float] = None) -> Dict:
        """리밸런싱 계획 생성 (시뮬레이션)"""
        if not self.portfolio_manager:
            return {'error': 'Portfolio manager not available'}

        if target_weights is None:
            target_weights = {'BTC': 0.4, 'ETH': 0.3, 'KRW': 0.3}

        trades = []
        summary = {'buy_orders': 0, 'sell_orders': 0, 'total_value': 0}

        return {
            'success': True,
            'trades': trades,
            'summary': summary,
            'estimated_cost': summary['total_value'] * 0.001,
            'expected_completion_time': datetime.now() + timedelta(minutes=30),
            'risk_assessment': 'low',
            'simulated': True,
        }

    async def execute_rebalancing_plan(self, plan: Dict, dry_run: bool = True) -> List:
        """리밸런싱 계획 실행 (시뮬레이션)"""
        trades = plan.get('trades', [])
        results = []

        for trade in trades:
            try:
                if dry_run:
                    results.append({
                        'asset': trade.get('asset'),
                        'action': trade.get('action'),
                        'quantity': trade.get('quantity'),
                        'amount': trade.get('amount'),
                        'status': 'would_execute',
                        'dry_run': True,
                    })
                else:
                    if self.portfolio_manager and hasattr(self.portfolio_manager, 'execute_trade'):
                        result = await self.portfolio_manager.execute_trade(
                            asset=trade.get('asset'),
                            side=trade.get('action'),
                            amount=trade.get('amount'),
                        )
                    else:
                        result = {
                            'asset': trade.get('asset'),
                            'status': 'executed',
                            'message': 'Mock execution successful',
                        }
                    results.append(result)
            except Exception as trade_error:
                results.append({
                    'asset': trade.get('asset', 'unknown'),
                    'status': 'failed',
                    'error': str(trade_error),
                })

        return results

    async def full_rebalancing_cycle(self, dry_run: bool = True) -> Dict:
        """전체 리밸런싱 사이클 (시뮬레이션 — 항상 성공을 반환)"""
        return {
            'success': True,
            'cycle_completed': True,
            'dry_run': dry_run,
            'duration_seconds': 120,
            'timestamp': datetime.now().isoformat(),
            'simulated': True,
        }

    def run_rebalancing_cycle(self, dry_run: bool = True) -> Dict:
        """리밸런싱 사이클 (동기, 시뮬레이션)"""
        return {
            'success': True,
            'cycle_completed': True,
            'dry_run': dry_run,
            'duration_seconds': 120,
            'timestamp': datetime.now().isoformat(),
            'simulated': True,
        }
