"""
Tax Optimization System

세금 효율적인 투자 전략 시스템
- 장기보유 우대세율 활용 (1년 이상)
- 세금 손실 수확 (Tax Loss Harvesting)
- FIFO/LIFO 매도 전략 선택
- 세금 영향도를 고려한 리밸런싱
- 연간 세금 최적화 계획
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd
import numpy as np
from loguru import logger


class TaxEventType(Enum):
    """세금 이벤트 유형"""
    BUY = "buy"
    SELL = "sell"
    DIVIDEND = "dividend"
    STAKING_REWARD = "staking_reward"


class TaxLotMethod(Enum):
    """세금 로트 매도 방식"""
    FIFO = "fifo"           # 선입선출
    LIFO = "lifo"           # 후입선출  
    HIGHEST_COST = "highest_cost"  # 최고가 우선
    TAX_EFFICIENT = "tax_efficient"  # 세금 효율적


class HoldingPeriod(Enum):
    """보유 기간 구분"""
    SHORT_TERM = "short_term"    # 1년 미만
    LONG_TERM = "long_term"      # 1년 이상


@dataclass
class TaxLot:
    """세금 로트 (개별 매수 기록)"""
    asset: str
    quantity: float
    purchase_price: float
    purchase_date: datetime
    purchase_id: str
    fees: float = 0.0
    
    @property
    def holding_period(self) -> HoldingPeriod:
        """현재 기준 보유 기간"""
        days_held = (datetime.now() - self.purchase_date).days
        return HoldingPeriod.LONG_TERM if days_held >= 365 else HoldingPeriod.SHORT_TERM
    
    @property
    def cost_basis(self) -> float:
        """취득 원가"""
        return self.quantity * self.purchase_price + self.fees
    
    @property
    def days_until_long_term(self) -> int:
        """장기보유까지 남은 일수"""
        days_held = (datetime.now() - self.purchase_date).days
        return max(0, 365 - days_held)


@dataclass 
class TaxEvent:
    """세금 이벤트"""
    date: datetime
    event_type: TaxEventType
    asset: str
    quantity: float
    price: float
    total_amount: float
    fees: float = 0.0
    tax_lots_used: List[TaxLot] = field(default_factory=list)
    realized_gain_loss: float = 0.0
    holding_period: Optional[HoldingPeriod] = None
    tax_rate_applied: float = 0.0


@dataclass
class TaxOptimizationPlan:
    """세금 최적화 계획"""
    annual_gain_target: float  # 연간 목표 실현 이익
    annual_loss_budget: float  # 연간 손실 상계 예산
    long_term_preference: float  # 장기보유 선호도 (0-1)
    tax_loss_harvesting: bool  # 세금 손실 수확 활성화
    lot_method: TaxLotMethod  # 매도 방식
    tax_rates: Dict[str, float]  # 세율 정보


class TaxOptimizationSystem:
    """
    세금 최적화 시스템
    
    세금 효율적인 매매와 포트폴리오 관리를 지원합니다.
    """
    
    def __init__(self):
        """세금 최적화 시스템 초기화"""
        
        # 한국 세율 (2024년 기준)
        self.tax_rates = {
            "cryptocurrency": {
                "short_term": 0.22,  # 22% (기타소득세)
                "long_term": 0.22    # 현재는 보유기간 우대 없음 (향후 변경 가능)
            },
            "capital_gains": {
                "basic": 0.22,       # 기본세율
                "local": 0.022       # 지방소득세 10%
            }
        }
        
        # 세금 최적화 설정
        self.default_plan = TaxOptimizationPlan(
            annual_gain_target=10000000,    # 연 1천만원
            annual_loss_budget=2000000,     # 연 200만원 손실 상계
            long_term_preference=0.8,       # 80% 장기보유 선호
            tax_loss_harvesting=True,
            lot_method=TaxLotMethod.TAX_EFFICIENT,
            tax_rates=self.tax_rates
        )
        
        # 세금 로트 추적
        self.tax_lots: Dict[str, List[TaxLot]] = {}  # 자산별 세금 로트
        self.tax_events: List[TaxEvent] = []  # 세금 이벤트 기록
        
        logger.info("Tax Optimization System 초기화 완료")
    
    def add_purchase(
        self, 
        asset: str, 
        quantity: float, 
        price: float, 
        date: datetime,
        fees: float = 0.0,
        purchase_id: Optional[str] = None
    ) -> TaxLot:
        """매수 기록 추가"""
        
        if purchase_id is None:
            purchase_id = f"{asset}_{date.strftime('%Y%m%d_%H%M%S')}"
        
        tax_lot = TaxLot(
            asset=asset,
            quantity=quantity,
            purchase_price=price,
            purchase_date=date,
            purchase_id=purchase_id,
            fees=fees
        )
        
        # 자산별 세금 로트에 추가
        if asset not in self.tax_lots:
            self.tax_lots[asset] = []
        self.tax_lots[asset].append(tax_lot)
        
        # 세금 이벤트 기록
        tax_event = TaxEvent(
            date=date,
            event_type=TaxEventType.BUY,
            asset=asset,
            quantity=quantity,
            price=price,
            total_amount=quantity * price + fees,
            fees=fees
        )
        self.tax_events.append(tax_event)
        
        logger.debug(f"매수 기록 추가: {asset} {quantity:.6f} @ {price:,.0f}")
        return tax_lot
    
    def calculate_optimal_sale(
        self,
        asset: str,
        target_quantity: float,
        current_price: float,
        plan: Optional[TaxOptimizationPlan] = None
    ) -> Tuple[List[TaxLot], float, Dict[str, Any]]:
        """
        세금 최적화된 매도 계획 계산
        
        Returns:
            (사용할 세금 로트들, 예상 세후 수익, 세금 분석)
        """
        
        if plan is None:
            plan = self.default_plan
        
        if asset not in self.tax_lots or not self.tax_lots[asset]:
            return [], 0.0, {"error": "보유 세금 로트 없음"}
        
        try:
            # 사용 가능한 세금 로트들
            available_lots = [lot for lot in self.tax_lots[asset] if lot.quantity > 0]
            
            if not available_lots:
                return [], 0.0, {"error": "매도 가능한 로트 없음"}
            
            # 매도 방식에 따른 로트 선택
            selected_lots = self._select_tax_lots(
                available_lots, target_quantity, current_price, plan
            )
            
            # 세금 영향 계산
            tax_analysis = self._calculate_tax_impact(
                selected_lots, current_price, plan
            )
            
            # 세후 수익 계산
            after_tax_proceeds = tax_analysis["gross_proceeds"] - tax_analysis["total_tax"]
            
            logger.info(f"{asset} 최적 매도: {len(selected_lots)}개 로트, 세후수익 {after_tax_proceeds:,.0f}")
            
            return selected_lots, after_tax_proceeds, tax_analysis
            
        except Exception as e:
            logger.error(f"최적 매도 계산 실패: {e}")
            return [], 0.0, {"error": str(e)}
    
    def _select_tax_lots(
        self,
        available_lots: List[TaxLot],
        target_quantity: float,
        current_price: float,
        plan: TaxOptimizationPlan
    ) -> List[TaxLot]:
        """매도 방식에 따른 세금 로트 선택"""
        
        if plan.lot_method == TaxLotMethod.FIFO:
            # 선입선출: 오래된 것부터
            sorted_lots = sorted(available_lots, key=lambda x: x.purchase_date)
            
        elif plan.lot_method == TaxLotMethod.LIFO:
            # 후입선출: 최근 것부터  
            sorted_lots = sorted(available_lots, key=lambda x: x.purchase_date, reverse=True)
            
        elif plan.lot_method == TaxLotMethod.HIGHEST_COST:
            # 최고가 우선: 손실 최소화
            sorted_lots = sorted(available_lots, key=lambda x: x.purchase_price, reverse=True)
            
        else:  # TAX_EFFICIENT
            # 세금 효율적: 복합 고려
            sorted_lots = self._sort_lots_tax_efficient(
                available_lots, current_price, plan
            )
        
        # 목표 수량까지 로트 선택
        selected_lots = []
        remaining_quantity = target_quantity
        
        for lot in sorted_lots:
            if remaining_quantity <= 0:
                break
                
            if lot.quantity <= remaining_quantity:
                # 로트 전체 사용
                selected_lots.append(lot)
                remaining_quantity -= lot.quantity
            else:
                # 로트 부분 사용 (새 로트 생성)
                partial_lot = TaxLot(
                    asset=lot.asset,
                    quantity=remaining_quantity,
                    purchase_price=lot.purchase_price,
                    purchase_date=lot.purchase_date,
                    purchase_id=f"{lot.purchase_id}_partial",
                    fees=lot.fees * (remaining_quantity / lot.quantity)
                )
                selected_lots.append(partial_lot)
                remaining_quantity = 0
        
        return selected_lots
    
    def _sort_lots_tax_efficient(
        self,
        lots: List[TaxLot],
        current_price: float,
        plan: TaxOptimizationPlan
    ) -> List[TaxLot]:
        """세금 효율적 로트 정렬"""
        
        def tax_efficiency_score(lot: TaxLot) -> float:
            score = 0.0
            
            # 1. 손실 로트 우선 (손실 실현으로 세금 절약)
            gain_loss = (current_price - lot.purchase_price) * lot.quantity
            if gain_loss < 0:
                score += 100  # 손실 로트 우선순위 높음
            
            # 2. 장기보유 로트 선호
            if lot.holding_period == HoldingPeriod.LONG_TERM:
                score += plan.long_term_preference * 50
            
            # 3. 높은 취득원가 로트 선호 (손실 최소화)
            score += lot.purchase_price / current_price * 20
            
            # 4. 작은 로트 우선 (거래비용 효율성)
            score += (1 / lot.quantity) * 10 if lot.quantity > 0 else 0
            
            return score
        
        return sorted(lots, key=tax_efficiency_score, reverse=True)
    
    def _calculate_tax_impact(
        self,
        selected_lots: List[TaxLot],
        current_price: float,
        plan: TaxOptimizationPlan
    ) -> Dict[str, Any]:
        """세금 영향 계산"""
        
        total_quantity = sum(lot.quantity for lot in selected_lots)
        gross_proceeds = total_quantity * current_price
        total_cost_basis = sum(lot.cost_basis for lot in selected_lots)
        total_gain_loss = gross_proceeds - total_cost_basis
        
        # 보유기간별 분리
        short_term_gain = 0.0
        long_term_gain = 0.0
        
        for lot in selected_lots:
            lot_proceeds = lot.quantity * current_price
            lot_gain_loss = lot_proceeds - lot.cost_basis
            
            if lot.holding_period == HoldingPeriod.SHORT_TERM:
                short_term_gain += lot_gain_loss
            else:
                long_term_gain += lot_gain_loss
        
        # 세금 계산
        short_term_tax = max(0, short_term_gain * plan.tax_rates["cryptocurrency"]["short_term"])
        long_term_tax = max(0, long_term_gain * plan.tax_rates["cryptocurrency"]["long_term"])
        total_tax = short_term_tax + long_term_tax
        
        return {
            "gross_proceeds": gross_proceeds,
            "total_cost_basis": total_cost_basis,
            "total_gain_loss": total_gain_loss,
            "short_term_gain": short_term_gain,
            "long_term_gain": long_term_gain,
            "short_term_tax": short_term_tax,
            "long_term_tax": long_term_tax,
            "total_tax": total_tax,
            "effective_tax_rate": total_tax / gross_proceeds if gross_proceeds > 0 else 0,
            "lots_analysis": [
                {
                    "purchase_date": lot.purchase_date,
                    "quantity": lot.quantity,
                    "purchase_price": lot.purchase_price,
                    "holding_period": lot.holding_period.value,
                    "gain_loss": lot.quantity * current_price - lot.cost_basis
                } for lot in selected_lots
            ]
        }
    
    def identify_tax_loss_opportunities(
        self,
        current_prices: Dict[str, float],
        max_loss_budget: float = None
    ) -> List[Dict[str, Any]]:
        """세금 손실 수확 기회 식별"""
        
        if max_loss_budget is None:
            max_loss_budget = self.default_plan.annual_loss_budget
        
        opportunities = []
        
        for asset, lots in self.tax_lots.items():
            if asset not in current_prices:
                continue
                
            current_price = current_prices[asset]
            
            for lot in lots:
                if lot.quantity <= 0:
                    continue
                    
                # 손실 계산
                unrealized_loss = lot.cost_basis - (lot.quantity * current_price)
                
                if unrealized_loss > 0:  # 손실이 있는 경우
                    opportunity = {
                        "asset": asset,
                        "lot": lot,
                        "unrealized_loss": unrealized_loss,
                        "holding_period": lot.holding_period.value,
                        "tax_benefit": unrealized_loss * self.tax_rates["cryptocurrency"]["short_term"],
                        "current_value": lot.quantity * current_price,
                        "loss_percentage": unrealized_loss / lot.cost_basis
                    }
                    opportunities.append(opportunity)
        
        # 손실 크기순 정렬
        opportunities.sort(key=lambda x: x["unrealized_loss"], reverse=True)
        
        # 예산 범위 내 필터링
        filtered_opportunities = []
        cumulative_loss = 0
        
        for opp in opportunities:
            if cumulative_loss + opp["unrealized_loss"] <= max_loss_budget:
                filtered_opportunities.append(opp)
                cumulative_loss += opp["unrealized_loss"]
        
        logger.info(f"세금 손실 수확 기회: {len(filtered_opportunities)}개, 총 손실 {cumulative_loss:,.0f}")
        return filtered_opportunities
    
    def plan_year_end_tax_strategy(
        self, 
        current_prices: Dict[str, float],
        target_date: datetime = None
    ) -> Dict[str, Any]:
        """연말 세금 전략 수립"""
        
        if target_date is None:
            target_date = datetime(datetime.now().year, 12, 31)
        
        strategy = {
            "current_unrealized_gains": {},
            "current_unrealized_losses": {},
            "long_term_candidates": [],
            "tax_loss_harvesting": [],
            "recommendations": []
        }
        
        try:
            total_unrealized_gains = 0
            total_unrealized_losses = 0
            
            # 자산별 미실현 손익 계산
            for asset, lots in self.tax_lots.items():
                if asset not in current_prices:
                    continue
                    
                current_price = current_prices[asset]
                asset_gains = 0
                asset_losses = 0
                
                for lot in lots:
                    if lot.quantity <= 0:
                        continue
                        
                    current_value = lot.quantity * current_price
                    unrealized_pnl = current_value - lot.cost_basis
                    
                    if unrealized_pnl > 0:
                        asset_gains += unrealized_pnl
                    else:
                        asset_losses += abs(unrealized_pnl)
                    
                    # 장기보유 후보 (1년 근처)
                    days_to_long_term = lot.days_until_long_term
                    if 0 < days_to_long_term <= 60:  # 60일 이내
                        strategy["long_term_candidates"].append({
                            "asset": asset,
                            "lot": lot,
                            "days_remaining": days_to_long_term,
                            "target_date": lot.purchase_date + timedelta(days=365),
                            "potential_tax_savings": abs(unrealized_pnl) * 0.1 if unrealized_pnl > 0 else 0  # 가정: 10% 세율 차이
                        })
                
                if asset_gains > 0:
                    strategy["current_unrealized_gains"][asset] = asset_gains
                    total_unrealized_gains += asset_gains
                
                if asset_losses > 0:
                    strategy["current_unrealized_losses"][asset] = asset_losses  
                    total_unrealized_losses += asset_losses
            
            # 세금 손실 수확 기회
            strategy["tax_loss_harvesting"] = self.identify_tax_loss_opportunities(current_prices)
            
            # 권장사항 생성
            recommendations = []
            
            if total_unrealized_gains > 5000000:  # 500만원 이상 이익
                recommendations.append({
                    "type": "gain_realization",
                    "description": f"미실현 이익 {total_unrealized_gains:,.0f}원 중 일부 실현 고려",
                    "priority": "medium"
                })
            
            if strategy["tax_loss_harvesting"]:
                total_harvestable = sum(opp["unrealized_loss"] for opp in strategy["tax_loss_harvesting"])
                recommendations.append({
                    "type": "loss_harvesting", 
                    "description": f"세금 손실 수확으로 {total_harvestable:,.0f}원 손실 실현 고려",
                    "priority": "high"
                })
            
            if strategy["long_term_candidates"]:
                recommendations.append({
                    "type": "long_term_waiting",
                    "description": f"{len(strategy['long_term_candidates'])}개 포지션이 곧 장기보유 전환 예정",
                    "priority": "low"
                })
            
            strategy["recommendations"] = recommendations
            strategy["summary"] = {
                "total_unrealized_gains": total_unrealized_gains,
                "total_unrealized_losses": total_unrealized_losses,
                "net_position": total_unrealized_gains - total_unrealized_losses,
                "estimated_tax_liability": total_unrealized_gains * self.tax_rates["cryptocurrency"]["short_term"]
            }
            
            return strategy
            
        except Exception as e:
            logger.error(f"연말 세금 전략 수립 실패: {e}")
            return strategy
    
    def execute_tax_optimized_rebalancing(
        self,
        target_weights: Dict[str, float],
        current_prices: Dict[str, float],
        total_portfolio_value: float
    ) -> List[Dict[str, Any]]:
        """세금 최적화된 리밸런싱 실행"""
        
        rebalancing_plan = []
        
        try:
            for asset in target_weights:
                target_value = total_portfolio_value * target_weights[asset]
                
                if asset not in self.tax_lots:
                    # 신규 매수
                    if target_value > 10000:  # 최소 매수 금액
                        rebalancing_plan.append({
                            "action": "buy",
                            "asset": asset,
                            "target_value": target_value,
                            "tax_impact": 0,
                            "reasoning": "신규 포지션 구축"
                        })
                    continue
                
                # 현재 보유 가치 계산
                current_value = sum(
                    lot.quantity * current_prices[asset] 
                    for lot in self.tax_lots[asset] 
                    if lot.quantity > 0
                )
                
                value_diff = target_value - current_value
                
                if abs(value_diff) < total_portfolio_value * 0.01:  # 1% 미만 차이
                    continue  # 리밸런싱 불필요
                
                if value_diff > 0:
                    # 매수 필요
                    rebalancing_plan.append({
                        "action": "buy",
                        "asset": asset,
                        "target_value": value_diff,
                        "tax_impact": 0,
                        "reasoning": f"목표 비중까지 {value_diff:,.0f}원 매수"
                    })
                else:
                    # 매도 필요
                    target_quantity = abs(value_diff) / current_prices[asset]
                    selected_lots, after_tax_proceeds, tax_analysis = self.calculate_optimal_sale(
                        asset, target_quantity, current_prices[asset]
                    )
                    
                    rebalancing_plan.append({
                        "action": "sell",
                        "asset": asset,
                        "target_quantity": target_quantity,
                        "selected_lots": selected_lots,
                        "tax_impact": tax_analysis.get("total_tax", 0),
                        "after_tax_proceeds": after_tax_proceeds,
                        "reasoning": f"목표 비중까지 {abs(value_diff):,.0f}원 매도"
                    })
            
            # 세금 영향도로 우선순위 조정
            rebalancing_plan.sort(key=lambda x: x.get("tax_impact", 0))
            
            logger.info(f"세금 최적화 리밸런싱 계획: {len(rebalancing_plan)}개 거래")
            return rebalancing_plan
            
        except Exception as e:
            logger.error(f"세금 최적화 리밸런싱 실패: {e}")
            return []
    
    def generate_tax_report(self, year: int) -> Dict[str, Any]:
        """세금 보고서 생성"""
        
        start_date = datetime(year, 1, 1)
        end_date = datetime(year, 12, 31, 23, 59, 59)
        
        # 해당 연도 거래 필터링
        year_events = [
            event for event in self.tax_events 
            if start_date <= event.date <= end_date
        ]
        
        report = {
            "tax_year": year,
            "total_transactions": len(year_events),
            "realized_gains_losses": 0,
            "short_term_gains": 0,
            "long_term_gains": 0,
            "total_tax_liability": 0,
            "transactions": [],
            "summary_by_asset": {}
        }
        
        try:
            for event in year_events:
                if event.event_type == TaxEventType.SELL:
                    report["realized_gains_losses"] += event.realized_gain_loss
                    
                    if event.holding_period == HoldingPeriod.SHORT_TERM:
                        report["short_term_gains"] += event.realized_gain_loss
                    else:
                        report["long_term_gains"] += event.realized_gain_loss
                    
                    report["total_tax_liability"] += event.realized_gain_loss * event.tax_rate_applied
                
                # 거래 상세
                transaction = {
                    "date": event.date.strftime("%Y-%m-%d"),
                    "type": event.event_type.value,
                    "asset": event.asset,
                    "quantity": event.quantity,
                    "price": event.price,
                    "amount": event.total_amount,
                    "realized_pnl": event.realized_gain_loss,
                    "holding_period": event.holding_period.value if event.holding_period else None
                }
                report["transactions"].append(transaction)
                
                # 자산별 요약
                if event.asset not in report["summary_by_asset"]:
                    report["summary_by_asset"][event.asset] = {
                        "total_bought": 0,
                        "total_sold": 0,
                        "realized_pnl": 0,
                        "transaction_count": 0
                    }
                
                asset_summary = report["summary_by_asset"][event.asset]
                asset_summary["transaction_count"] += 1
                
                if event.event_type == TaxEventType.BUY:
                    asset_summary["total_bought"] += event.total_amount
                elif event.event_type == TaxEventType.SELL:
                    asset_summary["total_sold"] += event.total_amount
                    asset_summary["realized_pnl"] += event.realized_gain_loss
            
            logger.info(f"{year}년 세금 보고서 생성 완료: 총 손익 {report['realized_gains_losses']:,.0f}원")
            return report
            
        except Exception as e:
            logger.error(f"세금 보고서 생성 실패: {e}")
            return report
    
    def get_portfolio_tax_efficiency_score(self, current_prices: Dict[str, float]) -> Dict[str, Any]:
        """포트폴리오 세금 효율성 점수"""
        
        score = {
            "overall_score": 0.0,  # 0-100
            "long_term_ratio": 0.0,
            "unrealized_loss_ratio": 0.0,
            "lot_optimization_score": 0.0,
            "recommendations": []
        }
        
        try:
            total_positions = 0
            long_term_positions = 0
            total_value = 0
            unrealized_losses_value = 0
            
            for asset, lots in self.tax_lots.items():
                if asset not in current_prices:
                    continue
                    
                current_price = current_prices[asset]
                
                for lot in lots:
                    if lot.quantity <= 0:
                        continue
                        
                    total_positions += 1
                    position_value = lot.quantity * current_price
                    total_value += position_value
                    
                    if lot.holding_period == HoldingPeriod.LONG_TERM:
                        long_term_positions += 1
                    
                    unrealized_pnl = position_value - lot.cost_basis
                    if unrealized_pnl < 0:
                        unrealized_losses_value += abs(unrealized_pnl)
            
            if total_positions > 0:
                score["long_term_ratio"] = long_term_positions / total_positions
                
            if total_value > 0:
                score["unrealized_loss_ratio"] = unrealized_losses_value / total_value
            
            # 로트 최적화 점수 (더 적은 로트 = 더 효율적)
            avg_lots_per_asset = np.mean([len(lots) for lots in self.tax_lots.values()])
            score["lot_optimization_score"] = max(0, 1 - (avg_lots_per_asset - 1) / 10)
            
            # 전체 점수 계산
            score["overall_score"] = (
                score["long_term_ratio"] * 40 +        # 장기보유 40%
                score["lot_optimization_score"] * 30 +  # 로트 효율성 30%
                (1 - score["unrealized_loss_ratio"]) * 30  # 손실 최소화 30%
            )
            
            # 권장사항
            if score["long_term_ratio"] < 0.5:
                score["recommendations"].append("장기보유 비중 확대 권장")
            
            if score["unrealized_loss_ratio"] > 0.2:
                score["recommendations"].append("세금 손실 수확 고려")
            
            if avg_lots_per_asset > 5:
                score["recommendations"].append("로트 통합으로 관리 효율성 개선")
            
            return score
            
        except Exception as e:
            logger.error(f"세금 효율성 점수 계산 실패: {e}")
            return score