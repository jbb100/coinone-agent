#!/usr/bin/env python3
"""
OpportunisticBuyer 테스트 스크립트

기회적 매수 시스템의 정상 동작을 테스트합니다.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch
from loguru import logger

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.core.opportunistic_buyer import OpportunisticBuyer, OpportunityLevel, BuyOpportunity
from src.trading.coinone_client import CoinoneClient
from src.utils.database_manager import DatabaseManager


class TestOpportunisticBuyer:
    """OpportunisticBuyer 테스트 클래스"""
    
    def __init__(self):
        # Mock 객체들 생성
        self.mock_coinone_client = MagicMock(spec=CoinoneClient)
        self.mock_db_manager = MagicMock(spec=DatabaseManager)
        
        # OpportunisticBuyer 인스턴스 생성
        self.buyer = OpportunisticBuyer(
            coinone_client=self.mock_coinone_client,
            db_manager=self.mock_db_manager,
            cash_reserve_ratio=0.15
        )
        
        logger.info("테스트 환경 초기화 완료")
    
    def test_rsi_calculation(self):
        """RSI 계산 테스트"""
        logger.info("\n[TEST] RSI 계산 테스트")
        
        # 테스트용 가격 데이터 생성
        prices = pd.Series([
            100, 102, 101, 103, 105, 104, 103, 102, 100, 98,
            97, 95, 94, 92, 91, 93, 94, 95, 96, 97
        ])
        
        rsi = self.buyer.calculate_rsi(prices, period=14)
        
        logger.info(f"계산된 RSI: {rsi:.2f}")
        assert 0 <= rsi <= 100, f"RSI는 0-100 범위여야 함. 실제: {rsi}"
        
        # 하락 추세에서 RSI가 낮아야 함
        falling_prices = pd.Series(range(100, 80, -1))
        rsi_falling = self.buyer.calculate_rsi(falling_prices)
        logger.info(f"하락 추세 RSI: {rsi_falling:.2f}")
        assert rsi_falling < 50, f"하락 추세에서 RSI < 50이어야 함. 실제: {rsi_falling}"
        
        logger.success("✅ RSI 계산 테스트 통과")
    
    def test_opportunity_level_determination(self):
        """매수 기회 수준 판단 테스트"""
        logger.info("\n[TEST] 매수 기회 수준 판단 테스트")
        
        test_cases = [
            # (7일 하락률, 30일 하락률, RSI, 공포지수, 예상 레벨)
            (-0.03, -0.02, 45, 50, OpportunityLevel.NONE),      # 작은 하락
            (-0.06, -0.07, 40, 45, OpportunityLevel.MINOR),     # 소폭 하락
            (-0.12, -0.15, 35, 40, OpportunityLevel.MODERATE),  # 중간 하락
            (-0.25, -0.22, 28, 30, OpportunityLevel.MAJOR),     # 대폭 하락
            (-0.35, -0.40, 20, 15, OpportunityLevel.EXTREME),   # 극단적 하락
        ]
        
        for drop_7d, drop_30d, rsi, fear_greed, expected_level in test_cases:
            level = self.buyer._determine_opportunity_level(
                drop_7d, drop_30d, rsi, fear_greed
            )
            logger.info(f"하락률 7d:{drop_7d:.1%}, 30d:{drop_30d:.1%}, "
                       f"RSI:{rsi}, 공포지수:{fear_greed} → {level.value}")
            assert level == expected_level, f"예상: {expected_level.value}, 실제: {level.value}"
        
        logger.success("✅ 기회 수준 판단 테스트 통과")
    
    def test_buy_ratio_calculation(self):
        """매수 비율 계산 테스트"""
        logger.info("\n[TEST] 매수 비율 계산 테스트")
        
        test_cases = [
            # (기회 수준, RSI, 공포지수)
            (OpportunityLevel.MINOR, 40, 40),
            (OpportunityLevel.MODERATE, 30, 35),
            (OpportunityLevel.MAJOR, 25, 20),
            (OpportunityLevel.EXTREME, 15, 10),
        ]
        
        for level, rsi, fear_greed in test_cases:
            ratio = self.buyer._calculate_buy_ratio(level, rsi, fear_greed)
            base_ratio = self.buyer.opportunity_thresholds[level]["buy_ratio"]
            
            logger.info(f"{level.value}: RSI={rsi}, Fear={fear_greed} → "
                       f"매수 비율={ratio:.1%} (기본={base_ratio:.1%})")
            
            assert ratio >= base_ratio, f"조정된 비율이 기본 비율보다 작음"
            # EXTREME 레벨은 더 높은 비율 허용
            if level == OpportunityLevel.EXTREME:
                assert ratio <= 0.5, f"EXTREME 레벨 최대 비율(50%) 초과"
            else:
                assert ratio <= self.buyer.max_buy_per_opportunity, f"최대 비율 초과"
        
        logger.success("✅ 매수 비율 계산 테스트 통과")
    
    def test_identify_opportunities(self):
        """매수 기회 식별 테스트"""
        logger.info("\n[TEST] 매수 기회 식별 테스트")
        
        # Mock 데이터 설정
        btc_prices_7d = pd.DataFrame({
            'Close': [45000, 44000, 43000, 42000, 41000, 40000, 39000],
            'High': [46000, 45000, 44000, 43000, 42000, 41000, 40000],
            'Low': [44000, 43000, 42000, 41000, 40000, 39000, 38000]
        })
        
        btc_prices_30d = pd.DataFrame({
            'Close': np.linspace(50000, 39000, 30),
            'High': np.linspace(51000, 40000, 30),
            'Low': np.linspace(49000, 38000, 30)
        })
        
        # Mock 설정 - get_market_data 메서드 추가
        self.mock_db_manager.get_market_data = MagicMock()
        self.mock_db_manager.get_market_data.side_effect = lambda asset, days: (
            btc_prices_7d if days == 7 else btc_prices_30d
        )
        
        # 기회 식별
        opportunities = self.buyer.identify_opportunities(["BTC", "ETH", "KRW"])
        
        logger.info(f"발견된 기회: {len(opportunities)}개")
        for opp in opportunities:
            logger.info(f"  - {opp.asset}: {opp.opportunity_level.value}, "
                       f"신뢰도={opp.confidence_score:.1%}")
        
        # KRW는 제외되어야 함
        assert all(opp.asset != "KRW" for opp in opportunities), "KRW는 기회 목록에 없어야 함"
        
        logger.success("✅ 매수 기회 식별 테스트 통과")
    
    def test_cash_utilization_strategy(self):
        """현금 활용 전략 테스트"""
        logger.info("\n[TEST] 현금 활용 전략 테스트")
        
        # Mock 데이터 설정
        btc_data = pd.DataFrame({
            'Close': np.linspace(45000, 40000, 30)
        })
        self.mock_db_manager.get_market_data.return_value = btc_data
        
        # 다양한 공포지수에서 전략 테스트
        fear_greed_values = [10, 25, 50, 75, 90]
        
        with patch.object(self.buyer, 'get_fear_greed_index') as mock_fear:
            for fear_value in fear_greed_values:
                mock_fear.return_value = fear_value
                strategy = self.buyer.get_cash_utilization_strategy()
                
                logger.info(f"공포지수 {fear_value}: {strategy['mode']} - "
                           f"현금 활용 {strategy['cash_deploy_ratio']:.1%}")
                
                # 공포가 클수록 더 많은 현금 활용
                if fear_value < 25:
                    assert strategy['mode'] == 'aggressive_buying'
                elif fear_value > 75:
                    assert strategy['mode'] == 'defensive'
        
        logger.success("✅ 현금 활용 전략 테스트 통과")
    
    def test_execute_opportunistic_buys(self):
        """기회적 매수 실행 테스트"""
        logger.info("\n[TEST] 기회적 매수 실행 테스트")
        
        # Mock 매수 기회 생성
        opportunities = [
            BuyOpportunity(
                asset="BTC",
                current_price=40000,
                avg_price_7d=42000,
                avg_price_30d=45000,
                price_drop_7d=-0.05,
                price_drop_30d=-0.11,
                rsi=35,
                fear_greed_index=30,
                opportunity_level=OpportunityLevel.MODERATE,
                recommended_buy_ratio=0.2,
                confidence_score=0.7
            ),
            BuyOpportunity(
                asset="ETH",
                current_price=2500,
                avg_price_7d=2700,
                avg_price_30d=2900,
                price_drop_7d=-0.07,
                price_drop_30d=-0.14,
                rsi=32,
                fear_greed_index=30,
                opportunity_level=OpportunityLevel.MODERATE,
                recommended_buy_ratio=0.15,
                confidence_score=0.65
            )
        ]
        
        # Mock 주문 결과
        self.mock_coinone_client.place_limit_order = MagicMock()
        self.mock_coinone_client.place_limit_order.return_value = {
            "success": True,
            "order_id": "test_order_123"
        }
        
        # Mock DB 저장
        self.mock_db_manager.save_opportunistic_buy_record = MagicMock()
        self.mock_db_manager.save_opportunistic_buy_record.return_value = None
        
        # 실행
        available_cash = 1000000  # 100만원
        results = self.buyer.execute_opportunistic_buys(
            opportunities=opportunities,
            available_cash=available_cash,
            max_total_buy=500000  # 최대 50만원
        )
        
        logger.info(f"실행 결과:")
        logger.info(f"  - 실행된 주문: {len(results['executed_orders'])}개")
        logger.info(f"  - 실패한 주문: {len(results['failed_orders'])}개")
        logger.info(f"  - 총 투자 금액: {results['total_invested']:,.0f} KRW")
        logger.info(f"  - 남은 현금: {results['remaining_cash']:,.0f} KRW")
        
        # 검증
        assert results['total_invested'] <= 500000, "최대 매수 금액 초과"
        assert results['remaining_cash'] == available_cash - results['total_invested']
        
        logger.success("✅ 기회적 매수 실행 테스트 통과")
    
    def test_recent_buy_check(self):
        """최근 매수 이력 확인 테스트"""
        logger.info("\n[TEST] 최근 매수 이력 확인 테스트")
        
        # 이전 테스트에서 기록된 내역 초기화
        self.buyer.recent_buys.clear()
        
        # 현재 시간에 매수 기록
        self.buyer.recent_buys["BTC"] = datetime.now()
        
        # 바로 확인 → 최근 매수
        assert self.buyer._is_recently_bought("BTC") == True
        logger.info("✅ 방금 매수한 자산은 최근 매수로 판단")
        
        # 5시간 전 매수로 설정
        self.buyer.recent_buys["BTC"] = datetime.now() - timedelta(hours=5)
        assert self.buyer._is_recently_bought("BTC") == False
        logger.info("✅ 5시간 전 매수는 최근 매수가 아님")
        
        # 매수 이력 없음 (SOL 사용)
        is_recent = self.buyer._is_recently_bought("SOL")
        assert is_recent == False, f"매수 이력이 없는 SOL이 최근 매수로 판단됨: {is_recent}"
        logger.info("✅ 매수 이력 없는 자산은 최근 매수가 아님")
        
        logger.success("✅ 최근 매수 이력 확인 테스트 통과")
    
    def run_all_tests(self):
        """모든 테스트 실행"""
        logger.info("=" * 60)
        logger.info("OpportunisticBuyer 테스트 시작")
        logger.info("=" * 60)
        
        try:
            self.test_rsi_calculation()
            self.test_opportunity_level_determination()
            self.test_buy_ratio_calculation()
            self.test_identify_opportunities()
            self.test_cash_utilization_strategy()
            self.test_execute_opportunistic_buys()
            self.test_recent_buy_check()
            
            logger.info("\n" + "=" * 60)
            logger.success("🎉 모든 테스트 통과!")
            logger.info("=" * 60)
            return True
            
        except AssertionError as e:
            logger.error(f"❌ 테스트 실패: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ 테스트 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    """메인 함수"""
    tester = TestOpportunisticBuyer()
    success = tester.run_all_tests()
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()