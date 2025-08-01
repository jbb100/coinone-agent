"""
Rebalancer

포트폴리오 리밸런싱 실행을 담당하는 모듈
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from loguru import logger

from ..trading.coinone_client import CoinoneClient
from ..trading.order_manager import OrderManager
from .portfolio_manager import PortfolioManager
from .market_season_filter import MarketSeasonFilter, MarketSeason


class RebalanceResult:
    """리밸런싱 결과 클래스"""
    
    def __init__(self):
        self.success = False
        self.timestamp = datetime.now()
        self.executed_orders = []
        self.failed_orders = []
        self.total_value_before = 0
        self.total_value_after = 0
        self.rebalance_summary = {}
        self.error_message = None
    
    def to_dict(self) -> Dict:
        """딕셔너리로 변환"""
        return {
            "success": self.success,
            "timestamp": self.timestamp,
            "executed_orders": self.executed_orders,
            "failed_orders": self.failed_orders,
            "total_value_before": self.total_value_before,
            "total_value_after": self.total_value_after,
            "rebalance_summary": self.rebalance_summary,
            "error_message": self.error_message
        }


class Rebalancer:
    """
    포트폴리오 리밸런서
    
    시장 계절 필터의 신호에 따라 포트폴리오를 리밸런싱합니다.
    """
    
    def __init__(
        self,
        coinone_client: CoinoneClient,
        portfolio_manager: PortfolioManager,
        market_season_filter: MarketSeasonFilter,
        order_manager: Optional[OrderManager] = None
    ):
        """
        Args:
            coinone_client: 코인원 클라이언트
            portfolio_manager: 포트폴리오 관리자
            market_season_filter: 시장 계절 필터
            order_manager: 주문 관리자 (선택사항)
        """
        self.coinone_client = coinone_client
        self.portfolio_manager = portfolio_manager
        self.market_season_filter = market_season_filter
        self.order_manager = order_manager or OrderManager(coinone_client)
        
        # 리밸런싱 설정
        self.min_rebalance_threshold = 0.01  # 1%
        self.max_slippage = 0.005  # 0.5%
        self.order_timeout = 300  # 5분
        
        logger.info("Rebalancer 초기화 완료")
    
    def calculate_rebalancing_orders(self, target_market_season: Optional[MarketSeason] = None) -> Dict:
        """
        리밸런싱 주문 계획 수립 (실제 실행은 하지 않음)
        
        Args:
            target_market_season: 목표 시장 계절 (None이면 자동 판단)
            
        Returns:
            리밸런싱 계획 정보
        """
        try:
            logger.info("리밸런싱 주문 계획 수립 시작")
            
            # 1. 현재 포트폴리오 상태 조회
            current_portfolio = self.coinone_client.get_portfolio_value()
            total_value_before = current_portfolio["total_krw"]
            
            # 2. 시장 계절 판단 (필요시)
            if target_market_season is None:
                target_market_season = self._get_current_market_season()
            
            # 3. 목표 자산 배분 계산
            allocation_weights = self.market_season_filter.get_allocation_weights(target_market_season)
            target_weights = self.portfolio_manager.calculate_target_weights(
                allocation_weights["crypto"],
                allocation_weights["krw"]
            )
            
            # 4. 리밸런싱 필요 금액 계산
            rebalance_info = self.portfolio_manager.calculate_rebalance_amounts(
                current_portfolio, 
                target_weights
            )
            
            # 5. 리밸런싱 실행 가능성 검증
            validation_results = self.portfolio_manager.validate_rebalance_feasibility(rebalance_info)
            
            return {
                "success": True,
                "total_value_before": total_value_before,
                "market_season": target_market_season.value,
                "target_weights": target_weights,
                "rebalance_orders": rebalance_info.get("rebalance_orders", {}),
                "validation_results": validation_results,
                "message": f"리밸런싱 계획 수립 완료: {len(rebalance_info.get('rebalance_orders', {}))}개 주문"
            }
            
        except Exception as e:
            logger.error(f"리밸런싱 계획 수립 실패: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def execute_quarterly_rebalance(
        self, 
        target_market_season: Optional[MarketSeason] = None
    ) -> RebalanceResult:
        """
        분기별 리밸런싱 실행
        
        Args:
            target_market_season: 목표 시장 계절 (None인 경우 자동 판단)
            
        Returns:
            리밸런싱 결과
        """
        result = RebalanceResult()
        
        try:
            logger.info("분기별 리밸런싱 시작")
            
            # 1. 현재 포트폴리오 상태 조회
            current_portfolio = self.coinone_client.get_portfolio_value()
            result.total_value_before = current_portfolio["total_krw"]
            
            # 2. 시장 계절 판단 (필요시)
            if target_market_season is None:
                # BTC 가격 데이터를 가져와서 시장 계절 판단
                # 실제 구현에서는 데이터 수집기에서 가져와야 함
                target_market_season = self._get_current_market_season()
            
            # 3. 목표 자산 배분 계산
            allocation_weights = self.market_season_filter.get_allocation_weights(target_market_season)
            target_weights = self.portfolio_manager.calculate_target_weights(
                allocation_weights["crypto"],
                allocation_weights["krw"]
            )
            
            # 4. 리밸런싱 필요 금액 계산
            rebalance_info = self.portfolio_manager.calculate_rebalance_amounts(
                current_portfolio, 
                target_weights
            )
            
            # 디버깅: 계산된 주문 정보 확인
            logger.info("=== 리밸런싱 주문 정보 ===")
            for asset, order_info in rebalance_info.get("rebalance_orders", {}).items():
                amount = order_info["amount_diff_krw"]
                action = order_info["action"]
                logger.info(f"  {asset}: {action} {amount:,.0f} KRW")
            logger.info("=== 주문 정보 끝 ===")
            
            # 5. 리밸런싱 실행 가능성 검증
            validation_results = self.portfolio_manager.validate_rebalance_feasibility(rebalance_info)
            
            # 6. 실제 리밸런싱 실행
            if any(validation_results.values()):
                execution_result = self._execute_rebalancing_orders(rebalance_info, validation_results)
                result.executed_orders = execution_result["executed"]
                result.failed_orders = execution_result["failed"]
            
            # 7. 최종 포트폴리오 상태 확인
            final_portfolio = self.coinone_client.get_portfolio_value()
            result.total_value_after = final_portfolio["total_krw"]
            
            # 8. 결과 정리
            # KRW는 기본 통화이므로 성공 기준에서 제외 (실행 대상 주문만 고려)
            crypto_orders = [order for order in (result.executed_orders + result.failed_orders) 
                           if order.get("asset") != "KRW"]
            crypto_failed = [order for order in result.failed_orders 
                           if order.get("asset") != "KRW"]
            
            result.success = len(crypto_failed) == 0
            result.rebalance_summary = {
                "market_season": target_market_season.value,
                "target_weights": target_weights,
                "orders_executed": len(result.executed_orders),
                "orders_failed": len(result.failed_orders),
                "value_change": result.total_value_after - result.total_value_before
            }
            
            logger.info(f"분기별 리밸런싱 완료: {'성공' if result.success else '부분 실패'}")
            
        except Exception as e:
            logger.error(f"분기별 리밸런싱 실패: {e}")
            result.success = False
            result.error_message = str(e)
        
        return result
    
    def _execute_rebalancing_orders(
        self, 
        rebalance_info: Dict, 
        validation_results: Dict[str, bool]
    ) -> Dict[str, List]:
        """
        리밸런싱 주문 실행
        
        Args:
            rebalance_info: 리밸런싱 정보
            validation_results: 검증 결과
            
        Returns:
            실행 결과 딕셔너리
        """
        executed_orders = []
        failed_orders = []
        
        # 우선순위 순으로 정렬
        rebalance_orders = rebalance_info.get("rebalance_orders", {})
        sorted_orders = sorted(
            rebalance_orders.items(), 
            key=lambda x: x[1]["priority"]
        )
        
        for asset, order_info in sorted_orders:
            # KRW는 기본 통화이므로 직접 거래할 수 없음 (다른 자산 거래로 자동 조정)
            if asset == "KRW":
                logger.info(f"KRW: 기본 통화이므로 주문 건너뜀 (자동 조정됨)")
                continue
                
            if not validation_results.get(asset, False):
                logger.warning(f"{asset}: 검증 실패로 건너뜀")
                continue
            
            try:
                # 매도 주문 먼저 실행 (현금 확보)
                if order_info["action"] == "sell":
                    order_result = self._execute_sell_order(asset, order_info)
                else:
                    # 디버깅: 매수 주문 정보 확인
                    amount_krw = order_info["amount_diff_krw"]
                    logger.info(f"=== {asset} 매수 주문 실행 ===")
                    logger.info(f"  주문 금액: {amount_krw:,.0f} KRW")
                    logger.info(f"  주문 정보: {order_info}")
                    
                    order_result = self._execute_buy_order(asset, order_info)
                
                if order_result["success"]:
                    executed_orders.append(order_result)
                    logger.info(f"{asset} {order_info['action']} 주문 성공")
                else:
                    failed_orders.append(order_result)
                    logger.error(f"{asset} {order_info['action']} 주문 실패")
            
            except Exception as e:
                error_result = {
                    "asset": asset,
                    "action": order_info["action"],
                    "error": str(e),
                    "success": False
                }
                failed_orders.append(error_result)
                logger.error(f"{asset} 주문 실행 중 오류: {e}")
        
        return {"executed": executed_orders, "failed": failed_orders}
    
    def _execute_sell_order(self, asset: str, order_info: Dict) -> Dict:
        """
        매도 주문 실행
        
        Args:
            asset: 자산명
            order_info: 주문 정보
            
        Returns:
            주문 결과
        """
        try:
            # 현재 잔고 확인
            balances = self.coinone_client.get_balances()
            current_balance = balances.get(asset, 0)
            
            if current_balance <= 0:
                return {
                    "asset": asset,
                    "action": "sell", 
                    "error": "잔고 부족",
                    "success": False
                }
            
            # 매도할 수량 계산 (가격 변동 고려)
            ticker = self.coinone_client.get_ticker(asset)
            current_price = float(ticker.get("last", 0))
            
            target_sell_amount_krw = abs(order_info["amount_diff_krw"])
            sell_quantity = min(
                target_sell_amount_krw / current_price,
                current_balance * 0.99  # 수수료 고려하여 99%만 매도
            )
            
            # 시장가 매도 주문 실행
            order_result = self.coinone_client.place_order(
                currency=asset,
                side="sell",
                amount=sell_quantity
            )
            
            return {
                "asset": asset,
                "action": "sell",
                "quantity": sell_quantity,
                "estimated_krw": sell_quantity * current_price,
                "order_id": order_result.get("order_id"),
                "success": order_result.get("result") == "success"
            }
            
        except Exception as e:
            return {
                "asset": asset,
                "action": "sell",
                "error": str(e),
                "success": False
            }
    
    def _execute_buy_order(self, asset: str, order_info: Dict) -> Dict:
        """
        매수 주문 실행
        
        Args:
            asset: 자산명
            order_info: 주문 정보
            
        Returns:
            주문 결과
        """
        try:
            # KRW 잔고 확인
            balances = self.coinone_client.get_balances()
            krw_balance = balances.get("KRW", 0)
            
            target_buy_amount_krw = order_info["amount_diff_krw"]
            
            if krw_balance < target_buy_amount_krw:
                return {
                    "asset": asset,
                    "action": "buy",
                    "error": f"KRW 잔고 부족: {krw_balance:,.0f} < {target_buy_amount_krw:,.0f}",
                    "success": False
                }
            
            # 시장가 매수 주문 실행 (KRW 금액 기준)
            buy_amount_krw = min(target_buy_amount_krw, krw_balance * 0.99)  # 수수료 고려
            
            order_result = self.coinone_client.place_order(
                currency=asset,
                side="buy", 
                amount=buy_amount_krw,  # KRW 금액
                amount_in_krw=True  # KRW 금액으로 처리
            )
            
            return {
                "asset": asset,
                "action": "buy",
                "amount_krw": buy_amount_krw,
                "order_id": order_result.get("order_id"),
                "success": order_result.get("result") == "success"
            }
            
        except Exception as e:
            return {
                "asset": asset,
                "action": "buy",
                "error": str(e),
                "success": False
            }
    
    def _get_current_market_season(self) -> MarketSeason:
        """
        현재 시장 계절 판단 (임시 구현)
        
        실제로는 데이터 수집기에서 BTC 가격 데이터를 가져와야 함
        
        Returns:
            현재 시장 계절
        """
        try:
            # BTC 현재 가격 조회
            ticker = self.coinone_client.get_ticker("BTC")
            current_price = float(ticker.get("last", 0))
            
            # 임시로 간단한 로직 사용 (실제로는 200주 이동평균 필요)
            # 여기서는 예시로 50,000,000원을 기준으로 사용
            reference_price = 50000000  # 5천만원
            
            if current_price > reference_price * 1.05:
                return MarketSeason.RISK_ON
            elif current_price < reference_price * 0.95:
                return MarketSeason.RISK_OFF
            else:
                return MarketSeason.NEUTRAL
                
        except Exception as e:
            logger.error(f"시장 계절 판단 실패: {e}")
            return MarketSeason.NEUTRAL  # 기본값 반환
    
    def check_rebalance_needed(
        self, 
        current_portfolio: Dict, 
        target_weights: Dict[str, float]
    ) -> bool:
        """
        리밸런싱 필요 여부 확인
        
        Args:
            current_portfolio: 현재 포트폴리오
            target_weights: 목표 비중
            
        Returns:
            리밸런싱 필요 여부
        """
        current_weights = self.portfolio_manager.get_current_weights(current_portfolio)
        
        for asset, target_weight in target_weights.items():
            current_weight = current_weights.get(asset, 0)
            weight_diff = abs(target_weight - current_weight)
            
            if weight_diff > self.min_rebalance_threshold:
                logger.info(f"리밸런싱 필요: {asset} 차이 {weight_diff:.2%}")
                return True
        
        logger.info("리밸런싱 불필요: 모든 자산이 목표 비중 내")
        return False
    
    def get_rebalance_schedule(self) -> List[datetime]:
        """
        분기별 리밸런싱 스케줄 생성
        
        Returns:
            리밸런싱 실행일 리스트
        """
        current_year = datetime.now().year
        quarters = [
            datetime(current_year, 1, 1),   # Q1
            datetime(current_year, 4, 1),   # Q2  
            datetime(current_year, 7, 1),   # Q3
            datetime(current_year, 10, 1)   # Q4
        ]
        
        # 각 분기 첫 월요일로 조정
        schedule = []
        for quarter_start in quarters:
            # 첫 번째 월요일 찾기
            days_ahead = 0 - quarter_start.weekday()  # 월요일은 0
            if days_ahead <= 0:
                days_ahead += 7
            first_monday = quarter_start + timedelta(days=days_ahead)
            schedule.append(first_monday.replace(hour=9, minute=0, second=0))
        
        return schedule


# 설정 상수
DEFAULT_REBALANCE_THRESHOLD = 0.01  # 1%
DEFAULT_MAX_SLIPPAGE = 0.005        # 0.5%
DEFAULT_ORDER_TIMEOUT = 300         # 5분
QUARTER_MONTHS = [1, 4, 7, 10]     # 분기별 리밸런싱 월 