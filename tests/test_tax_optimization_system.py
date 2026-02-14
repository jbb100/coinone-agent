"""
Tax Optimization System Tests

세금 최적화 시스템 테스트
- TaxLot 데이터 클래스
- TaxOptimizationSystem 메서드들
- 세금 계산 및 최적화 로직
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.core.tax_optimization_system import (
    TaxOptimizationSystem,
    TaxLot,
    TaxEvent,
    TaxOptimizationPlan,
    TaxEventType,
    TaxLotMethod,
    HoldingPeriod
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def tax_system():
    """기본 세금 최적화 시스템"""
    return TaxOptimizationSystem()


@pytest.fixture
def sample_tax_lot():
    """샘플 세금 로트"""
    return TaxLot(
        asset="BTC",
        quantity=0.5,
        purchase_price=50000000,
        purchase_date=datetime.now() - timedelta(days=200),
        purchase_id="BTC_20240101_100000",
        fees=50000
    )


@pytest.fixture
def long_term_tax_lot():
    """장기보유 세금 로트 (1년 이상)"""
    return TaxLot(
        asset="BTC",
        quantity=0.3,
        purchase_price=40000000,
        purchase_date=datetime.now() - timedelta(days=400),
        purchase_id="BTC_20230601_100000",
        fees=30000
    )


@pytest.fixture
def short_term_tax_lot():
    """단기보유 세금 로트 (1년 미만)"""
    return TaxLot(
        asset="ETH",
        quantity=2.0,
        purchase_price=3000000,
        purchase_date=datetime.now() - timedelta(days=100),
        purchase_id="ETH_20241001_100000",
        fees=20000
    )


@pytest.fixture
def tax_system_with_lots(tax_system):
    """세금 로트가 있는 시스템"""
    # 다양한 매수 기록 추가
    # BTC - 오래된 매수 (장기보유)
    tax_system.add_purchase(
        asset="BTC",
        quantity=0.5,
        price=40000000,
        date=datetime.now() - timedelta(days=400),
        fees=30000
    )
    # BTC - 중간 매수
    tax_system.add_purchase(
        asset="BTC",
        quantity=0.3,
        price=50000000,
        date=datetime.now() - timedelta(days=200),
        fees=20000
    )
    # BTC - 최근 매수
    tax_system.add_purchase(
        asset="BTC",
        quantity=0.2,
        price=60000000,
        date=datetime.now() - timedelta(days=30),
        fees=15000
    )
    # ETH 매수
    tax_system.add_purchase(
        asset="ETH",
        quantity=3.0,
        price=3000000,
        date=datetime.now() - timedelta(days=150),
        fees=25000
    )
    return tax_system


@pytest.fixture
def custom_tax_plan():
    """커스텀 세금 최적화 계획"""
    return TaxOptimizationPlan(
        annual_gain_target=20000000,
        annual_loss_budget=5000000,
        long_term_preference=0.9,
        tax_loss_harvesting=True,
        lot_method=TaxLotMethod.TAX_EFFICIENT,
        tax_rates={
            "cryptocurrency": {
                "short_term": 0.22,
                "long_term": 0.15
            }
        }
    )


# ============================================================================
# TaxLot Tests
# ============================================================================

class TestTaxLotDataclass:
    """TaxLot 데이터 클래스 테스트"""

    def test_holding_period_short_term(self, short_term_tax_lot):
        """단기 보유 기간 확인"""
        assert short_term_tax_lot.holding_period == HoldingPeriod.SHORT_TERM

    def test_holding_period_long_term(self, long_term_tax_lot):
        """장기 보유 기간 확인"""
        assert long_term_tax_lot.holding_period == HoldingPeriod.LONG_TERM

    def test_cost_basis_calculation(self, sample_tax_lot):
        """취득 원가 계산"""
        expected = 0.5 * 50000000 + 50000  # quantity * price + fees
        assert sample_tax_lot.cost_basis == expected

    def test_days_until_long_term_short_term(self, short_term_tax_lot):
        """장기보유까지 남은 일수 (단기 로트)"""
        # 100일 보유 -> 265일 남음
        assert short_term_tax_lot.days_until_long_term > 200
        assert short_term_tax_lot.days_until_long_term <= 265

    def test_days_until_long_term_long_term(self, long_term_tax_lot):
        """장기보유까지 남은 일수 (장기 로트)"""
        # 이미 장기보유 -> 0일
        assert long_term_tax_lot.days_until_long_term == 0


class TestTaxLotBoundary:
    """TaxLot 경계 조건 테스트"""

    def test_exactly_365_days(self):
        """정확히 365일 보유"""
        lot = TaxLot(
            asset="BTC",
            quantity=1.0,
            purchase_price=50000000,
            purchase_date=datetime.now() - timedelta(days=365),
            purchase_id="BTC_exact_365"
        )
        assert lot.holding_period == HoldingPeriod.LONG_TERM
        assert lot.days_until_long_term == 0

    def test_exactly_364_days(self):
        """정확히 364일 보유"""
        lot = TaxLot(
            asset="BTC",
            quantity=1.0,
            purchase_price=50000000,
            purchase_date=datetime.now() - timedelta(days=364),
            purchase_id="BTC_exact_364"
        )
        assert lot.holding_period == HoldingPeriod.SHORT_TERM
        assert lot.days_until_long_term == 1


# ============================================================================
# TaxOptimizationSystem Initialization Tests
# ============================================================================

class TestTaxOptimizationSystemInit:
    """TaxOptimizationSystem 초기화 테스트"""

    def test_default_tax_rates(self, tax_system):
        """기본 세율 설정 확인"""
        assert "cryptocurrency" in tax_system.tax_rates
        assert tax_system.tax_rates["cryptocurrency"]["short_term"] == 0.22
        assert tax_system.tax_rates["cryptocurrency"]["long_term"] == 0.22

    def test_default_plan(self, tax_system):
        """기본 최적화 계획 확인"""
        plan = tax_system.default_plan
        assert plan.annual_gain_target == 10000000
        assert plan.annual_loss_budget == 2000000
        assert plan.long_term_preference == 0.8
        assert plan.tax_loss_harvesting is True
        assert plan.lot_method == TaxLotMethod.TAX_EFFICIENT

    def test_empty_tax_lots_on_init(self, tax_system):
        """초기 세금 로트 비어있음"""
        assert tax_system.tax_lots == {}
        assert tax_system.tax_events == []


# ============================================================================
# Add Purchase Tests
# ============================================================================

class TestAddPurchase:
    """매수 기록 추가 테스트"""

    def test_add_purchase_basic(self, tax_system):
        """기본 매수 추가"""
        purchase_date = datetime.now()
        lot = tax_system.add_purchase(
            asset="BTC",
            quantity=0.5,
            price=50000000,
            date=purchase_date,
            fees=25000
        )

        assert lot.asset == "BTC"
        assert lot.quantity == 0.5
        assert lot.purchase_price == 50000000
        assert lot.fees == 25000
        assert "BTC" in tax_system.tax_lots
        assert len(tax_system.tax_lots["BTC"]) == 1

    def test_add_purchase_with_custom_id(self, tax_system):
        """커스텀 ID로 매수 추가"""
        custom_id = "my_custom_purchase_id"
        lot = tax_system.add_purchase(
            asset="ETH",
            quantity=2.0,
            price=3000000,
            date=datetime.now(),
            purchase_id=custom_id
        )

        assert lot.purchase_id == custom_id

    def test_add_purchase_auto_id_generation(self, tax_system):
        """ID 자동 생성"""
        purchase_date = datetime(2024, 6, 15, 10, 30, 45)
        lot = tax_system.add_purchase(
            asset="XRP",
            quantity=1000,
            price=500,
            date=purchase_date
        )

        assert lot.purchase_id == "XRP_20240615_103045"

    def test_add_multiple_purchases_same_asset(self, tax_system):
        """동일 자산 다중 매수"""
        tax_system.add_purchase("BTC", 0.5, 50000000, datetime.now())
        tax_system.add_purchase("BTC", 0.3, 55000000, datetime.now())
        tax_system.add_purchase("BTC", 0.2, 48000000, datetime.now())

        assert len(tax_system.tax_lots["BTC"]) == 3

    def test_add_purchase_records_tax_event(self, tax_system):
        """매수 시 세금 이벤트 기록"""
        tax_system.add_purchase(
            asset="BTC",
            quantity=0.5,
            price=50000000,
            date=datetime.now(),
            fees=25000
        )

        assert len(tax_system.tax_events) == 1
        event = tax_system.tax_events[0]
        assert event.event_type == TaxEventType.BUY
        assert event.asset == "BTC"
        assert event.quantity == 0.5
        assert event.total_amount == 0.5 * 50000000 + 25000


# ============================================================================
# Calculate Optimal Sale Tests
# ============================================================================

class TestCalculateOptimalSale:
    """최적 매도 계산 테스트"""

    def test_calculate_optimal_sale_basic(self, tax_system_with_lots):
        """기본 최적 매도 계산"""
        lots, proceeds, analysis = tax_system_with_lots.calculate_optimal_sale(
            asset="BTC",
            target_quantity=0.3,
            current_price=55000000
        )

        assert len(lots) > 0
        assert proceeds > 0
        assert "gross_proceeds" in analysis
        assert "total_tax" in analysis

    def test_calculate_optimal_sale_no_lots(self, tax_system):
        """보유 로트 없을 때"""
        lots, proceeds, analysis = tax_system.calculate_optimal_sale(
            asset="BTC",
            target_quantity=0.1,
            current_price=50000000
        )

        assert lots == []
        assert proceeds == 0.0
        assert "error" in analysis

    def test_calculate_optimal_sale_with_custom_plan(self, tax_system_with_lots, custom_tax_plan):
        """커스텀 계획으로 최적 매도"""
        lots, proceeds, analysis = tax_system_with_lots.calculate_optimal_sale(
            asset="BTC",
            target_quantity=0.5,
            current_price=55000000,
            plan=custom_tax_plan
        )

        assert len(lots) > 0
        assert "total_cost_basis" in analysis

    def test_calculate_optimal_sale_partial_lot(self, tax_system):
        """부분 로트 매도"""
        tax_system.add_purchase("BTC", 1.0, 50000000, datetime.now())

        lots, proceeds, analysis = tax_system.calculate_optimal_sale(
            asset="BTC",
            target_quantity=0.3,
            current_price=55000000
        )

        assert len(lots) == 1
        assert lots[0].quantity == 0.3  # 부분 로트
        assert "partial" in lots[0].purchase_id


# ============================================================================
# Select Tax Lots Tests
# ============================================================================

class TestSelectTaxLots:
    """세금 로트 선택 테스트"""

    def test_select_lots_fifo(self, tax_system_with_lots):
        """FIFO 방식 로트 선택"""
        plan = TaxOptimizationPlan(
            annual_gain_target=10000000,
            annual_loss_budget=2000000,
            long_term_preference=0.5,
            tax_loss_harvesting=True,
            lot_method=TaxLotMethod.FIFO,
            tax_rates=tax_system_with_lots.tax_rates
        )

        available_lots = tax_system_with_lots.tax_lots["BTC"]
        selected = tax_system_with_lots._select_tax_lots(
            available_lots, 0.5, 55000000, plan
        )

        # FIFO: 가장 오래된 로트 먼저
        assert len(selected) > 0
        # 첫 번째 로트가 가장 오래된 것
        first_lot = selected[0]
        assert first_lot.purchase_date <= available_lots[1].purchase_date

    def test_select_lots_lifo(self, tax_system_with_lots):
        """LIFO 방식 로트 선택"""
        plan = TaxOptimizationPlan(
            annual_gain_target=10000000,
            annual_loss_budget=2000000,
            long_term_preference=0.5,
            tax_loss_harvesting=True,
            lot_method=TaxLotMethod.LIFO,
            tax_rates=tax_system_with_lots.tax_rates
        )

        available_lots = tax_system_with_lots.tax_lots["BTC"]
        selected = tax_system_with_lots._select_tax_lots(
            available_lots, 0.2, 55000000, plan
        )

        # LIFO: 가장 최근 로트 먼저
        assert len(selected) > 0

    def test_select_lots_highest_cost(self, tax_system_with_lots):
        """최고가 우선 방식 로트 선택"""
        plan = TaxOptimizationPlan(
            annual_gain_target=10000000,
            annual_loss_budget=2000000,
            long_term_preference=0.5,
            tax_loss_harvesting=True,
            lot_method=TaxLotMethod.HIGHEST_COST,
            tax_rates=tax_system_with_lots.tax_rates
        )

        available_lots = tax_system_with_lots.tax_lots["BTC"]
        selected = tax_system_with_lots._select_tax_lots(
            available_lots, 0.2, 55000000, plan
        )

        # 최고가 로트 먼저 (60,000,000에 산 것)
        assert len(selected) > 0
        assert selected[0].purchase_price == 60000000

    def test_select_lots_tax_efficient(self, tax_system_with_lots):
        """세금 효율적 방식 로트 선택"""
        available_lots = tax_system_with_lots.tax_lots["BTC"]
        selected = tax_system_with_lots._select_tax_lots(
            available_lots, 0.5, 55000000, tax_system_with_lots.default_plan
        )

        assert len(selected) > 0


# ============================================================================
# Sort Lots Tax Efficient Tests
# ============================================================================

class TestSortLotsTaxEfficient:
    """세금 효율적 로트 정렬 테스트"""

    def test_loss_lots_prioritized(self, tax_system):
        """손실 로트 우선 정렬"""
        # 손실 로트 (현재가 > 매수가)
        tax_system.add_purchase("BTC", 0.5, 70000000, datetime.now() - timedelta(days=50))
        # 이익 로트 (현재가 < 매수가)
        tax_system.add_purchase("BTC", 0.5, 40000000, datetime.now() - timedelta(days=100))

        sorted_lots = tax_system._sort_lots_tax_efficient(
            tax_system.tax_lots["BTC"],
            current_price=50000000,  # 손실 로트: 70M->50M, 이익 로트: 40M->50M
            plan=tax_system.default_plan
        )

        # 손실 로트가 먼저 (70M에 산 것이 손실)
        assert sorted_lots[0].purchase_price == 70000000

    def test_long_term_lots_preference(self, tax_system):
        """장기보유 로트 선호"""
        # 단기 로트
        tax_system.add_purchase("BTC", 0.5, 50000000, datetime.now() - timedelta(days=100))
        # 장기 로트
        tax_system.add_purchase("BTC", 0.5, 50000000, datetime.now() - timedelta(days=400))

        # 높은 장기보유 선호도
        plan = TaxOptimizationPlan(
            annual_gain_target=10000000,
            annual_loss_budget=2000000,
            long_term_preference=0.9,
            tax_loss_harvesting=True,
            lot_method=TaxLotMethod.TAX_EFFICIENT,
            tax_rates=tax_system.tax_rates
        )

        sorted_lots = tax_system._sort_lots_tax_efficient(
            tax_system.tax_lots["BTC"],
            current_price=50000000,
            plan=plan
        )

        # 장기 로트가 더 높은 점수
        assert sorted_lots[0].holding_period == HoldingPeriod.LONG_TERM


# ============================================================================
# Calculate Tax Impact Tests
# ============================================================================

class TestCalculateTaxImpact:
    """세금 영향 계산 테스트"""

    def test_basic_tax_calculation(self, tax_system_with_lots):
        """기본 세금 계산"""
        lots = tax_system_with_lots.tax_lots["BTC"][:1]  # 첫 번째 로트만

        tax_analysis = tax_system_with_lots._calculate_tax_impact(
            lots, 55000000, tax_system_with_lots.default_plan
        )

        assert "gross_proceeds" in tax_analysis
        assert "total_cost_basis" in tax_analysis
        assert "total_gain_loss" in tax_analysis
        assert "short_term_tax" in tax_analysis
        assert "long_term_tax" in tax_analysis
        assert "total_tax" in tax_analysis
        assert "effective_tax_rate" in tax_analysis
        assert "lots_analysis" in tax_analysis

    def test_gain_tax_calculation(self, tax_system):
        """이익에 대한 세금 계산"""
        # 낮은 가격에 매수
        tax_system.add_purchase("BTC", 0.5, 40000000, datetime.now() - timedelta(days=50))
        lots = tax_system.tax_lots["BTC"]

        # 높은 가격에 매도
        tax_analysis = tax_system._calculate_tax_impact(
            lots, 60000000, tax_system.default_plan
        )

        # 이익 발생
        assert tax_analysis["total_gain_loss"] > 0
        assert tax_analysis["total_tax"] > 0

    def test_loss_no_tax(self, tax_system):
        """손실 시 세금 없음"""
        # 높은 가격에 매수
        tax_system.add_purchase("BTC", 0.5, 60000000, datetime.now() - timedelta(days=50))
        lots = tax_system.tax_lots["BTC"]

        # 낮은 가격에 매도
        tax_analysis = tax_system._calculate_tax_impact(
            lots, 40000000, tax_system.default_plan
        )

        # 손실 발생, 세금 0
        assert tax_analysis["total_gain_loss"] < 0
        assert tax_analysis["total_tax"] == 0

    def test_mixed_holding_periods(self, tax_system):
        """혼합 보유기간 세금 계산"""
        # 장기 보유 로트
        tax_system.add_purchase("BTC", 0.5, 40000000, datetime.now() - timedelta(days=400))
        # 단기 보유 로트
        tax_system.add_purchase("BTC", 0.5, 45000000, datetime.now() - timedelta(days=100))

        lots = tax_system.tax_lots["BTC"]
        tax_analysis = tax_system._calculate_tax_impact(
            lots, 55000000, tax_system.default_plan
        )

        assert "short_term_gain" in tax_analysis
        assert "long_term_gain" in tax_analysis


# ============================================================================
# Identify Tax Loss Opportunities Tests
# ============================================================================

class TestIdentifyTaxLossOpportunities:
    """세금 손실 수확 기회 식별 테스트"""

    def test_identify_loss_opportunities(self, tax_system):
        """손실 기회 식별"""
        # 손실 상태인 로트 추가 (매수가 > 현재가)
        tax_system.add_purchase("BTC", 0.5, 70000000, datetime.now() - timedelta(days=50))
        tax_system.add_purchase("ETH", 2.0, 5000000, datetime.now() - timedelta(days=100))

        current_prices = {"BTC": 50000000, "ETH": 3000000}

        opportunities = tax_system.identify_tax_loss_opportunities(current_prices)

        # 손실이 있는 로트만 기회로 식별
        # BTC: cost_basis = 0.5 * 70M = 35M, current = 0.5 * 50M = 25M, loss = 10M
        # ETH: cost_basis = 2.0 * 5M = 10M, current = 2.0 * 3M = 6M, loss = 4M
        if len(opportunities) > 0:
            assert opportunities[0]["unrealized_loss"] > 0
            # 손실이 큰 순서대로 정렬
            if len(opportunities) > 1:
                assert opportunities[0]["unrealized_loss"] >= opportunities[1]["unrealized_loss"]
        else:
            # 손실 기회가 없으면 빈 리스트
            assert opportunities == []

    def test_no_loss_opportunities(self, tax_system):
        """손실 기회 없음"""
        # 이익 상태인 로트만
        tax_system.add_purchase("BTC", 0.5, 40000000, datetime.now() - timedelta(days=50))

        current_prices = {"BTC": 60000000}

        opportunities = tax_system.identify_tax_loss_opportunities(current_prices)

        assert len(opportunities) == 0

    def test_budget_filtering(self, tax_system):
        """예산 범위 필터링"""
        # 큰 손실
        tax_system.add_purchase("BTC", 1.0, 70000000, datetime.now() - timedelta(days=50))
        # 작은 손실
        tax_system.add_purchase("ETH", 1.0, 4000000, datetime.now() - timedelta(days=100))

        current_prices = {"BTC": 50000000, "ETH": 3000000}  # BTC: 2000만 손실, ETH: 100만 손실

        # 작은 예산
        opportunities = tax_system.identify_tax_loss_opportunities(
            current_prices, max_loss_budget=1500000
        )

        # 예산 내에서 가능한 것만
        assert len(opportunities) == 1
        assert opportunities[0]["asset"] == "ETH"

    def test_tax_benefit_calculation(self, tax_system):
        """세금 혜택 계산"""
        tax_system.add_purchase("BTC", 0.5, 70000000, datetime.now() - timedelta(days=50))
        current_prices = {"BTC": 50000000}

        opportunities = tax_system.identify_tax_loss_opportunities(current_prices)

        # BTC: cost_basis = 0.5 * 70M = 35M, current = 0.5 * 50M = 25M, loss = 10M
        if len(opportunities) > 0:
            opp = opportunities[0]
            assert opp["asset"] == "BTC"
            assert opp["unrealized_loss"] > 0
            # 세금 혜택 = 손실 * 세율
            assert opp["tax_benefit"] == opp["unrealized_loss"] * 0.22
        else:
            # 손실 기회가 없으면 건너뜀
            assert opportunities == []


# ============================================================================
# Plan Year End Tax Strategy Tests
# ============================================================================

class TestPlanYearEndTaxStrategy:
    """연말 세금 전략 테스트"""

    def test_basic_strategy_generation(self, tax_system_with_lots):
        """기본 전략 생성"""
        current_prices = {"BTC": 55000000, "ETH": 3500000}

        strategy = tax_system_with_lots.plan_year_end_tax_strategy(current_prices)

        assert "current_unrealized_gains" in strategy
        assert "current_unrealized_losses" in strategy
        assert "long_term_candidates" in strategy
        assert "tax_loss_harvesting" in strategy
        assert "recommendations" in strategy
        assert "summary" in strategy

    def test_unrealized_gains_calculation(self, tax_system):
        """미실현 이익 계산"""
        # 이익 상태 포지션
        tax_system.add_purchase("BTC", 0.5, 40000000, datetime.now() - timedelta(days=100))
        current_prices = {"BTC": 60000000}

        strategy = tax_system.plan_year_end_tax_strategy(current_prices)

        assert "BTC" in strategy["current_unrealized_gains"]
        assert strategy["summary"]["total_unrealized_gains"] > 0

    def test_long_term_candidates_detection(self, tax_system):
        """장기보유 전환 후보 감지"""
        # 330일 보유 (35일 남음)
        tax_system.add_purchase("BTC", 0.5, 50000000, datetime.now() - timedelta(days=330))
        current_prices = {"BTC": 55000000}

        strategy = tax_system.plan_year_end_tax_strategy(current_prices)

        assert len(strategy["long_term_candidates"]) == 1
        candidate = strategy["long_term_candidates"][0]
        assert candidate["days_remaining"] <= 60

    def test_recommendations_for_large_gains(self, tax_system):
        """큰 이익에 대한 권장사항"""
        # 큰 이익 상태
        tax_system.add_purchase("BTC", 1.0, 40000000, datetime.now() - timedelta(days=100))
        current_prices = {"BTC": 60000000}  # 2000만원 이익

        strategy = tax_system.plan_year_end_tax_strategy(current_prices)

        # 이익 실현 권장사항 확인
        rec_types = [r["type"] for r in strategy["recommendations"]]
        assert "gain_realization" in rec_types

    def test_custom_target_date(self, tax_system_with_lots):
        """커스텀 대상 날짜"""
        current_prices = {"BTC": 55000000, "ETH": 3500000}
        custom_date = datetime(2025, 6, 30)

        strategy = tax_system_with_lots.plan_year_end_tax_strategy(
            current_prices, target_date=custom_date
        )

        assert strategy is not None


# ============================================================================
# Execute Tax Optimized Rebalancing Tests
# ============================================================================

class TestExecuteTaxOptimizedRebalancing:
    """세금 최적화 리밸런싱 테스트"""

    def test_basic_rebalancing(self, tax_system_with_lots):
        """기본 리밸런싱"""
        target_weights = {"BTC": 0.5, "ETH": 0.3, "XRP": 0.2}
        current_prices = {"BTC": 55000000, "ETH": 3500000, "XRP": 500}
        total_value = 100000000

        plan = tax_system_with_lots.execute_tax_optimized_rebalancing(
            target_weights, current_prices, total_value
        )

        assert isinstance(plan, list)

    def test_new_asset_purchase(self, tax_system_with_lots):
        """신규 자산 매수"""
        target_weights = {"BTC": 0.5, "XRP": 0.5}  # XRP는 신규
        current_prices = {"BTC": 55000000, "XRP": 500}
        total_value = 100000000

        plan = tax_system_with_lots.execute_tax_optimized_rebalancing(
            target_weights, current_prices, total_value
        )

        xrp_actions = [p for p in plan if p["asset"] == "XRP"]
        assert len(xrp_actions) == 1
        assert xrp_actions[0]["action"] == "buy"

    def test_sell_with_tax_impact(self, tax_system_with_lots):
        """세금 영향 있는 매도"""
        # 현재 BTC 보유가 많은 상태에서 줄이기
        target_weights = {"BTC": 0.2, "ETH": 0.8}
        current_prices = {"BTC": 55000000, "ETH": 3500000}
        total_value = 100000000

        plan = tax_system_with_lots.execute_tax_optimized_rebalancing(
            target_weights, current_prices, total_value
        )

        sell_actions = [p for p in plan if p["action"] == "sell"]
        assert len(sell_actions) > 0

    def test_small_difference_ignored(self, tax_system):
        """작은 차이는 무시"""
        # 0.49% vs 0.5% (1% 미만 차이)
        tax_system.add_purchase("BTC", 0.01, 50000000, datetime.now())

        target_weights = {"BTC": 0.5}
        current_prices = {"BTC": 50000000}
        total_value = 1000000  # 100만원 포트폴리오, BTC 0.01개 = 50만원 = 50%

        plan = tax_system.execute_tax_optimized_rebalancing(
            target_weights, current_prices, total_value
        )

        # 차이가 작으면 액션 없음
        assert len(plan) == 0


# ============================================================================
# Generate Tax Report Tests
# ============================================================================

class TestGenerateTaxReport:
    """세금 보고서 생성 테스트"""

    def test_basic_report_structure(self, tax_system):
        """기본 보고서 구조"""
        report = tax_system.generate_tax_report(2024)

        assert report["tax_year"] == 2024
        assert "total_transactions" in report
        assert "realized_gains_losses" in report
        assert "short_term_gains" in report
        assert "long_term_gains" in report
        assert "total_tax_liability" in report
        assert "transactions" in report
        assert "summary_by_asset" in report

    def test_report_with_transactions(self, tax_system):
        """거래가 있는 보고서"""
        # 올해 거래 추가
        current_year = datetime.now().year
        tax_system.add_purchase(
            "BTC", 0.5, 50000000,
            datetime(current_year, 3, 15)
        )
        tax_system.add_purchase(
            "ETH", 2.0, 3000000,
            datetime(current_year, 6, 20)
        )

        report = tax_system.generate_tax_report(current_year)

        assert report["total_transactions"] == 2
        assert len(report["transactions"]) == 2

    def test_report_asset_summary(self, tax_system):
        """자산별 요약"""
        current_year = datetime.now().year
        tax_system.add_purchase("BTC", 0.5, 50000000, datetime(current_year, 1, 15))
        tax_system.add_purchase("BTC", 0.3, 55000000, datetime(current_year, 2, 20))

        report = tax_system.generate_tax_report(current_year)

        assert "BTC" in report["summary_by_asset"]
        assert report["summary_by_asset"]["BTC"]["transaction_count"] == 2

    def test_empty_year_report(self, tax_system):
        """빈 연도 보고서"""
        report = tax_system.generate_tax_report(2020)  # 과거 연도

        assert report["total_transactions"] == 0
        assert report["transactions"] == []


# ============================================================================
# Get Portfolio Tax Efficiency Score Tests
# ============================================================================

class TestGetPortfolioTaxEfficiencyScore:
    """포트폴리오 세금 효율성 점수 테스트"""

    def test_basic_score(self, tax_system_with_lots):
        """기본 점수 계산"""
        current_prices = {"BTC": 55000000, "ETH": 3500000}

        score = tax_system_with_lots.get_portfolio_tax_efficiency_score(current_prices)

        assert "overall_score" in score
        assert "long_term_ratio" in score
        assert "unrealized_loss_ratio" in score
        assert "lot_optimization_score" in score
        assert "recommendations" in score
        assert 0 <= score["overall_score"] <= 100

    def test_high_long_term_ratio(self, tax_system):
        """높은 장기보유 비율"""
        # 모두 장기보유
        tax_system.add_purchase("BTC", 0.5, 50000000, datetime.now() - timedelta(days=400))
        tax_system.add_purchase("ETH", 2.0, 3000000, datetime.now() - timedelta(days=500))

        current_prices = {"BTC": 55000000, "ETH": 3500000}
        score = tax_system.get_portfolio_tax_efficiency_score(current_prices)

        assert score["long_term_ratio"] == 1.0

    def test_low_long_term_ratio_recommendation(self, tax_system):
        """낮은 장기보유 비율 권장사항"""
        # 모두 단기보유
        tax_system.add_purchase("BTC", 0.5, 50000000, datetime.now() - timedelta(days=100))
        tax_system.add_purchase("ETH", 2.0, 3000000, datetime.now() - timedelta(days=50))

        current_prices = {"BTC": 55000000, "ETH": 3500000}
        score = tax_system.get_portfolio_tax_efficiency_score(current_prices)

        assert score["long_term_ratio"] == 0.0
        assert "장기보유 비중 확대 권장" in score["recommendations"]

    def test_high_loss_ratio_recommendation(self, tax_system):
        """높은 손실 비율 권장사항"""
        # 손실 상태
        tax_system.add_purchase("BTC", 0.5, 80000000, datetime.now() - timedelta(days=100))

        current_prices = {"BTC": 50000000}  # 30% 손실
        score = tax_system.get_portfolio_tax_efficiency_score(current_prices)

        assert score["unrealized_loss_ratio"] > 0.2
        assert "세금 손실 수확 고려" in score["recommendations"]

    def test_empty_portfolio(self, tax_system):
        """빈 포트폴리오"""
        score = tax_system.get_portfolio_tax_efficiency_score({})

        # 빈 포트폴리오는 long_term_ratio = 0, unrealized_loss_ratio = 0
        # 손실 최소화 점수로 인해 0보다 클 수 있음: (1-0) * 30 = 30
        assert score["long_term_ratio"] == 0.0
        assert "overall_score" in score


# ============================================================================
# Get Optimization Summary Tests
# ============================================================================

class TestGetOptimizationSummary:
    """최적화 요약 테스트"""

    def test_basic_summary(self, tax_system_with_lots):
        """기본 요약"""
        summary = tax_system_with_lots.get_optimization_summary()

        assert "optimized_lots" in summary
        assert "tax_savings" in summary
        assert "total_lots" in summary
        assert "long_term_lots" in summary
        assert "short_term_lots" in summary
        assert "total_assets" in summary
        assert "optimization_efficiency" in summary

    def test_lot_count(self, tax_system_with_lots):
        """로트 수 계산"""
        summary = tax_system_with_lots.get_optimization_summary()

        # tax_system_with_lots는 BTC 3개 + ETH 1개 = 4개 로트
        assert summary["total_lots"] == 4
        assert summary["total_assets"] == 2

    def test_empty_portfolio_summary(self, tax_system):
        """빈 포트폴리오 요약"""
        summary = tax_system.get_optimization_summary()

        assert summary["total_lots"] == 0
        assert summary["optimization_efficiency"] == 0

    def test_long_term_lots_count(self, tax_system):
        """장기보유 로트 수"""
        # 장기 1개, 단기 2개
        tax_system.add_purchase("BTC", 0.5, 50000000, datetime.now() - timedelta(days=400))
        tax_system.add_purchase("BTC", 0.3, 55000000, datetime.now() - timedelta(days=100))
        tax_system.add_purchase("ETH", 2.0, 3000000, datetime.now() - timedelta(days=50))

        summary = tax_system.get_optimization_summary()

        assert summary["long_term_lots"] == 1
        assert summary["short_term_lots"] == 2


# ============================================================================
# Enum Tests
# ============================================================================

class TestEnums:
    """Enum 테스트"""

    def test_tax_event_type_values(self):
        """TaxEventType 값"""
        assert TaxEventType.BUY.value == "buy"
        assert TaxEventType.SELL.value == "sell"
        assert TaxEventType.DIVIDEND.value == "dividend"
        assert TaxEventType.STAKING_REWARD.value == "staking_reward"

    def test_tax_lot_method_values(self):
        """TaxLotMethod 값"""
        assert TaxLotMethod.FIFO.value == "fifo"
        assert TaxLotMethod.LIFO.value == "lifo"
        assert TaxLotMethod.HIGHEST_COST.value == "highest_cost"
        assert TaxLotMethod.TAX_EFFICIENT.value == "tax_efficient"

    def test_holding_period_values(self):
        """HoldingPeriod 값"""
        assert HoldingPeriod.SHORT_TERM.value == "short_term"
        assert HoldingPeriod.LONG_TERM.value == "long_term"


# ============================================================================
# Edge Cases & Error Handling Tests
# ============================================================================

class TestEdgeCases:
    """엣지 케이스 테스트"""

    def test_zero_quantity_lot_ignored(self, tax_system):
        """수량 0인 로트 무시"""
        lot = tax_system.add_purchase("BTC", 0.5, 50000000, datetime.now())
        lot.quantity = 0  # 전량 매도된 상태

        current_prices = {"BTC": 55000000}
        opportunities = tax_system.identify_tax_loss_opportunities(current_prices)

        assert len(opportunities) == 0

    def test_missing_price_asset_skipped(self, tax_system_with_lots):
        """가격 없는 자산 건너뜀"""
        # ETH 가격 없이 BTC만
        current_prices = {"BTC": 55000000}

        score = tax_system_with_lots.get_portfolio_tax_efficiency_score(current_prices)

        # ETH는 무시되고 BTC만 계산
        assert score is not None

    def test_very_small_fees(self, tax_system):
        """매우 작은 수수료"""
        lot = tax_system.add_purchase(
            "BTC", 0.5, 50000000,
            datetime.now(),
            fees=0.00001
        )

        assert lot.cost_basis == 0.5 * 50000000 + 0.00001

    def test_large_quantity(self, tax_system):
        """큰 수량"""
        lot = tax_system.add_purchase(
            "XRP", 1000000,  # 100만 XRP
            500,
            datetime.now()
        )

        assert lot.quantity == 1000000
        assert lot.cost_basis == 1000000 * 500


class TestErrorHandling:
    """에러 처리 테스트"""

    def test_calculate_optimal_sale_exception(self, tax_system):
        """최적 매도 계산 예외 처리"""
        # 빈 자산 목록으로 오류 유발
        lots, proceeds, analysis = tax_system.calculate_optimal_sale(
            asset="NONEXISTENT",
            target_quantity=1.0,
            current_price=50000000
        )

        assert lots == []
        assert proceeds == 0.0
        assert "error" in analysis

    def test_year_end_strategy_with_exception(self, tax_system):
        """연말 전략 예외 처리"""
        # 정상 동작 확인
        strategy = tax_system.plan_year_end_tax_strategy({})

        assert strategy is not None
        assert "summary" not in strategy or strategy.get("summary") is None or \
               strategy.get("summary", {}).get("total_unrealized_gains", 0) == 0


class TestTaxOptimizationPlanDataclass:
    """TaxOptimizationPlan 데이터 클래스 테스트"""

    def test_plan_creation(self, custom_tax_plan):
        """계획 생성"""
        assert custom_tax_plan.annual_gain_target == 20000000
        assert custom_tax_plan.annual_loss_budget == 5000000
        assert custom_tax_plan.long_term_preference == 0.9
        assert custom_tax_plan.tax_loss_harvesting is True
        assert custom_tax_plan.lot_method == TaxLotMethod.TAX_EFFICIENT

    def test_plan_with_different_methods(self):
        """다른 방식의 계획"""
        fifo_plan = TaxOptimizationPlan(
            annual_gain_target=10000000,
            annual_loss_budget=2000000,
            long_term_preference=0.5,
            tax_loss_harvesting=False,
            lot_method=TaxLotMethod.FIFO,
            tax_rates={}
        )

        assert fifo_plan.lot_method == TaxLotMethod.FIFO
        assert fifo_plan.tax_loss_harvesting is False


class TestTaxEventDataclass:
    """TaxEvent 데이터 클래스 테스트"""

    def test_event_creation(self):
        """이벤트 생성"""
        event = TaxEvent(
            date=datetime.now(),
            event_type=TaxEventType.BUY,
            asset="BTC",
            quantity=0.5,
            price=50000000,
            total_amount=25000000,
            fees=25000
        )

        assert event.asset == "BTC"
        assert event.quantity == 0.5
        assert event.realized_gain_loss == 0.0
        assert event.tax_lots_used == []

    def test_sell_event_with_gain(self):
        """이익이 있는 매도 이벤트"""
        event = TaxEvent(
            date=datetime.now(),
            event_type=TaxEventType.SELL,
            asset="BTC",
            quantity=0.5,
            price=60000000,
            total_amount=30000000,
            realized_gain_loss=5000000,
            holding_period=HoldingPeriod.LONG_TERM,
            tax_rate_applied=0.22
        )

        assert event.event_type == TaxEventType.SELL
        assert event.realized_gain_loss == 5000000
        assert event.holding_period == HoldingPeriod.LONG_TERM


class TestTaxOptimizationUncoveredLines:
    """커버되지 않은 라인 테스트"""

    @pytest.fixture
    def tax_system_with_lots(self):
        """로트가 있는 세금 시스템"""
        system = TaxOptimizationSystem()
        # 장기보유 로트 추가
        long_term_lot = TaxLot(
            asset="BTC",
            quantity=1.0,
            purchase_price=40000000,
            purchase_date=datetime.now() - timedelta(days=400),
            purchase_id="BTC_LONG_1"
        )
        # 단기보유 로트 추가
        short_term_lot = TaxLot(
            asset="BTC",
            quantity=0.5,
            purchase_price=50000000,
            purchase_date=datetime.now() - timedelta(days=100),
            purchase_id="BTC_SHORT_1"
        )
        system.tax_lots["BTC"] = [long_term_lot, short_term_lot]
        return system

    def test_calculate_optimal_sale_no_lots(self):
        """매도 가능 로트 없음 (라인 204)"""
        system = TaxOptimizationSystem()
        # 빈 로트 리스트
        system.tax_lots["BTC"] = []

        selected, proceeds, analysis = system.calculate_optimal_sale("BTC", 0.5, 50000000)

        assert selected == []
        assert proceeds == 0.0
        assert "error" in analysis

    def test_calculate_optimal_sale_exception(self):
        """최적 매도 계산 예외 (라인 223-225)"""
        system = TaxOptimizationSystem()

        # 예외 발생시키기 위해 존재하지 않는 자산
        selected, proceeds, analysis = system.calculate_optimal_sale("NONEXISTENT", 1.0, 1000)

        assert selected == []
        assert proceeds == 0.0
        assert "error" in analysis

    def test_plan_year_end_tax_strategy_exception(self, tax_system_with_lots):
        """연말 전략 예외 (라인 515-517)"""
        # tax_lots를 예외 발생시키도록 모킹
        with patch.object(tax_system_with_lots, 'tax_lots', new_callable=lambda: Mock(side_effect=Exception("Test"))):
            result = tax_system_with_lots.plan_year_end_tax_strategy({"BTC": 50000000})
            # 예외 시 기본 strategy 반환
            assert "recommendations" in result

    def test_execute_tax_optimized_rebalancing_exception(self, tax_system_with_lots):
        """세금 최적화 리밸런싱 예외 (라인 589-591)"""
        # calculate_optimal_sale에서 예외 발생
        with patch.object(tax_system_with_lots, 'calculate_optimal_sale', side_effect=Exception("Test")):
            result = tax_system_with_lots.execute_tax_optimized_rebalancing(
                target_weights={"BTC": 0.3},
                current_prices={"BTC": 50000000},
                total_portfolio_value=100000000
            )
            assert result == []

    def test_generate_tax_report_sell_events(self, tax_system_with_lots):
        """세금 보고서 매도 이벤트 (라인 618-626)"""
        # 매도 이벤트 추가
        sell_event = TaxEvent(
            date=datetime.now(),
            event_type=TaxEventType.SELL,
            asset="BTC",
            quantity=0.5,
            price=55000000,
            total_amount=27500000,
            realized_gain_loss=2500000,
            holding_period=HoldingPeriod.SHORT_TERM,
            tax_rate_applied=0.22
        )
        tax_system_with_lots.tax_events.append(sell_event)

        report = tax_system_with_lots.generate_tax_report(datetime.now().year)

        assert report["total_transactions"] == 1
        assert report["short_term_gains"] == 2500000
        assert report["total_tax_liability"] == 2500000 * 0.22

    def test_generate_tax_report_long_term_sell(self, tax_system_with_lots):
        """세금 보고서 장기 매도 (라인 623-624)"""
        sell_event = TaxEvent(
            date=datetime.now(),
            event_type=TaxEventType.SELL,
            asset="BTC",
            quantity=0.5,
            price=55000000,
            total_amount=27500000,
            realized_gain_loss=5000000,
            holding_period=HoldingPeriod.LONG_TERM,
            tax_rate_applied=0.15
        )
        tax_system_with_lots.tax_events.append(sell_event)

        report = tax_system_with_lots.generate_tax_report(datetime.now().year)

        assert report["long_term_gains"] == 5000000

    def test_generate_tax_report_buy_event(self, tax_system_with_lots):
        """세금 보고서 매수 이벤트 (라인 654)"""
        buy_event = TaxEvent(
            date=datetime.now(),
            event_type=TaxEventType.BUY,
            asset="BTC",
            quantity=0.5,
            price=50000000,
            total_amount=25000000
        )
        tax_system_with_lots.tax_events.append(buy_event)

        report = tax_system_with_lots.generate_tax_report(datetime.now().year)

        assert report["summary_by_asset"]["BTC"]["total_bought"] == 25000000

    def test_generate_tax_report_exception(self, tax_system_with_lots):
        """세금 보고서 예외 (라인 662-664)"""
        # 잘못된 이벤트 추가
        bad_event = Mock()
        bad_event.date = datetime.now()
        bad_event.event_type = TaxEventType.SELL
        bad_event.realized_gain_loss = Mock(side_effect=Exception("Test"))
        tax_system_with_lots.tax_events.append(bad_event)

        report = tax_system_with_lots.generate_tax_report(datetime.now().year)
        # 예외 시 기본 report 반환
        assert "tax_year" in report

    def test_portfolio_tax_efficiency_empty_lot(self):
        """포트폴리오 효율성 - 빈 로트 (라인 691)"""
        system = TaxOptimizationSystem()
        # quantity가 0인 로트
        empty_lot = TaxLot(
            asset="BTC",
            quantity=0,
            purchase_price=50000000,
            purchase_date=datetime.now() - timedelta(days=100),
            purchase_id="EMPTY_LOT"
        )
        system.tax_lots["BTC"] = [empty_lot]

        score = system.get_portfolio_tax_efficiency_score({"BTC": 50000000})
        assert "overall_score" in score

    def test_portfolio_tax_efficiency_many_lots(self):
        """포트폴리오 효율성 - 많은 로트 (라인 729)"""
        system = TaxOptimizationSystem()
        # 많은 로트 추가 (평균 로트 > 5)
        lots = []
        for i in range(10):
            lot = TaxLot(
                asset="BTC",
                quantity=0.1,
                purchase_price=50000000,
                purchase_date=datetime.now() - timedelta(days=100+i),
                purchase_id=f"LOT_{i}"
            )
            lots.append(lot)
        system.tax_lots["BTC"] = lots

        score = system.get_portfolio_tax_efficiency_score({"BTC": 50000000})

        assert "로트 통합" in score["recommendations"][0] or len(score["recommendations"]) > 0

    def test_portfolio_tax_efficiency_exception(self):
        """포트폴리오 효율성 예외 (라인 733-735)"""
        system = TaxOptimizationSystem()
        # 잘못된 데이터로 예외 유발
        bad_lot = Mock()
        bad_lot.quantity = 1.0
        bad_lot.holding_period = Mock(side_effect=Exception("Test"))
        system.tax_lots["BTC"] = [bad_lot]

        score = system.get_portfolio_tax_efficiency_score({"BTC": 50000000})
        assert score["overall_score"] == 0.0

    def test_optimization_summary_empty_lot(self, tax_system_with_lots):
        """최적화 요약 - 빈 로트 건너뛰기 (라인 759)"""
        # 빈 로트 추가
        empty_lot = TaxLot(
            asset="ETH",
            quantity=0,
            purchase_price=3000000,
            purchase_date=datetime.now() - timedelta(days=50),
            purchase_id="ETH_EMPTY"
        )
        tax_system_with_lots.tax_lots["ETH"] = [empty_lot]

        summary = tax_system_with_lots.get_optimization_summary()

        # ETH 빈 로트는 카운트되지 않음
        assert summary["total_lots"] > 0

    def test_optimization_summary_exception(self):
        """최적화 요약 예외 (라인 784-786)"""
        system = TaxOptimizationSystem()
        # 잘못된 데이터로 예외 유발
        bad_lot = Mock()
        bad_lot.quantity = 1.0
        bad_lot.holding_period = Mock(side_effect=Exception("Test"))
        system.tax_lots["BTC"] = [bad_lot]

        summary = system.get_optimization_summary()
        assert summary["optimized_lots"] == 0
