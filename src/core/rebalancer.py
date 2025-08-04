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
            logger.debug(f"current_portfolio 타입: {type(current_portfolio)}, 내용: {current_portfolio}")
            
            # 포트폴리오 데이터 타입 검증
            if not isinstance(current_portfolio, dict):
                logger.error(f"current_portfolio가 딕셔너리가 아님: {type(current_portfolio)}")
                return {"success": False, "error": f"포트폴리오 데이터 형식 오류: {type(current_portfolio)}"}
            
            total_value_before = current_portfolio.get("total_krw", 0)
            
            logger.info(f"=== 현재 포트폴리오 상태 ===")
            logger.info(f"총 자산 가치: {total_value_before:,.0f} KRW")
            
            assets = current_portfolio.get("assets", {})
            if isinstance(assets, dict):
                for asset, info in assets.items():
                    if isinstance(info, dict):
                        value = info.get("value_krw", 0)
                        amount = info.get("amount", 0)
                        logger.info(f"  {asset}: {amount:.6f} 개 = {value:,.0f} KRW")
                    else:
                        logger.warning(f"  {asset}: 정보 형식 오류 - {type(info)}")
            else:
                logger.warning(f"assets가 딕셔너리가 아님: {type(assets)}")
            
            # 2. 시장 계절 판단 (필요시)
            if target_market_season is None:
                target_market_season = self._get_current_market_season()
            
            logger.info(f"목표 시장 계절: {target_market_season}")
            
            # 3. 목표 자산 배분 계산
            allocation_weights = self.market_season_filter.get_allocation_weights(target_market_season)
            logger.info(f"시장 계절별 배분: 암호화폐 {allocation_weights['crypto']:.1%}, KRW {allocation_weights['krw']:.1%}")
            
            target_weights = self.portfolio_manager.calculate_target_weights(
                allocation_weights["crypto"],
                allocation_weights["krw"]
            )
            
            logger.info(f"=== 목표 자산 비중 ===")
            for asset, weight in target_weights.items():
                logger.info(f"  {asset}: {weight:.2%}")
            
            # 4. 현재 자산 비중 계산
            current_weights = self.portfolio_manager.get_current_weights(current_portfolio)
            logger.info(f"=== 현재 자산 비중 ===")
            for asset, weight in current_weights.items():
                logger.info(f"  {asset}: {weight:.2%}")
            
            # 5. 비중 차이 분석
            logger.info(f"=== 비중 차이 분석 ===")
            for asset in set(list(target_weights.keys()) + list(current_weights.keys())):
                current_weight = current_weights.get(asset, 0)
                target_weight = target_weights.get(asset, 0)
                weight_diff = target_weight - current_weight
                amount_diff = weight_diff * total_value_before
                
                if abs(amount_diff) > total_value_before * 0.01:  # 1% 임계값
                    action = "매수" if amount_diff > 0 else "매도"
                    logger.info(f"  {asset}: 현재 {current_weight:.2%} → 목표 {target_weight:.2%} "
                              f"(차이: {weight_diff:+.2%}) → {action} {abs(amount_diff):,.0f} KRW")
                else:
                    logger.info(f"  {asset}: 현재 {current_weight:.2%} → 목표 {target_weight:.2%} "
                              f"(차이: {weight_diff:+.2%}) → 임계값 미만, 조정 안함")
            
            # 6. 리밸런싱 필요 금액 계산
            rebalance_info = self.portfolio_manager.calculate_rebalance_amounts(
                current_portfolio, 
                target_weights
            )
            
            logger.debug(f"rebalance_info 타입: {type(rebalance_info)}, 키: {rebalance_info.keys() if isinstance(rebalance_info, dict) else 'N/A'}")
            
            # rebalance_info 타입 검증
            if not isinstance(rebalance_info, dict):
                logger.error(f"rebalance_info가 딕셔너리가 아님: {type(rebalance_info)}")
                return {"success": False, "error": f"리밸런싱 계산 결과 형식 오류: {type(rebalance_info)}"}
            
            # 7. 리밸런싱 실행 가능성 검증
            validation_results = self.portfolio_manager.validate_rebalance_feasibility(rebalance_info)
            
            logger.info(f"=== 최종 리밸런싱 주문 ===")
            rebalance_orders = rebalance_info.get("rebalance_orders", {})
            if isinstance(rebalance_orders, dict):
                for asset, order_info in rebalance_orders.items():
                    if isinstance(order_info, dict):
                        amount = order_info.get("amount_diff_krw", 0)
                        action = order_info.get("action", "unknown")
                        logger.info(f"  {asset}: {action} {amount:,.0f} KRW")
                    else:
                        logger.warning(f"  {asset}: 주문 정보 형식 오류 - {type(order_info)}")
            else:
                logger.warning(f"rebalance_orders가 딕셔너리가 아님: {type(rebalance_orders)}")
            
            return {
                "success": True,
                "market_season": target_market_season,
                "total_value_before": total_value_before,
                "allocation_weights": allocation_weights,
                "target_weights": target_weights,
                "current_weights": current_weights,
                "rebalance_orders": rebalance_info.get("rebalance_orders", {}),
                "validation_results": validation_results,
                "rebalance_summary": rebalance_info.get("summary", {})
            }
            
        except Exception as e:
            logger.error(f"리밸런싱 주문 계획 수립 실패: {e}")
            return {"success": False, "error": str(e)}
    
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
            
            # 매도할 수량 계산 - 안전한 현재가 조회 사용
            try:
                current_price = self.coinone_client.get_latest_price(asset)
                logger.info(f"{asset} 매도 현재가: {current_price:,.0f} KRW")
                
                if current_price <= 0:
                    raise ValueError(f"현재가 조회 실패: {current_price}")
                    
            except Exception as price_error:
                logger.error(f"{asset} 현재가 조회 실패: {price_error}")
                # 폴백: ticker API 사용하되 더 안전하게
                try:
                    ticker = self.coinone_client.get_ticker(asset)
                    logger.debug(f"{asset} ticker 응답 타입: {type(ticker)}, 내용: {ticker}")
                    
                    # ticker가 딕셔너리가 아닌 경우 처리
                    if not isinstance(ticker, dict):
                        logger.error(f"{asset} ticker 응답이 딕셔너리가 아님: {type(ticker)}")
                        return {
                            "asset": asset,
                            "action": "sell",
                            "error": f"ticker 응답 형식 오류: {type(ticker)}",
                            "success": False
                        }
                    
                    ticker_data = ticker.get("data", {})
                    if not isinstance(ticker_data, dict):
                        logger.error(f"{asset} ticker data가 딕셔너리가 아님: {type(ticker_data)}")
                        return {
                            "asset": asset,
                            "action": "sell",
                            "error": f"ticker data 형식 오류: {type(ticker_data)}",
                            "success": False
                        }
                    
                    current_price = (
                        float(ticker_data.get("last", 0)) or
                        float(ticker_data.get("close_24h", 0)) or
                        float(ticker_data.get("close", 0))
                    )
                    
                    if current_price <= 0:
                        return {
                            "asset": asset,
                            "action": "sell",
                            "error": f"현재가 조회 실패: ticker_data={ticker_data}",
                            "success": False
                        }
                        
                    logger.warning(f"{asset} 폴백 가격 사용: {current_price:,.0f} KRW")
                    
                except Exception as ticker_error:
                    logger.error(f"{asset} ticker 조회도 실패: {ticker_error}")
                    return {
                        "asset": asset,
                        "action": "sell",
                        "error": f"모든 가격 조회 방법 실패: {ticker_error}",
                        "success": False
                    }
            
            target_sell_amount_krw = abs(order_info["amount_diff_krw"])
            
            # 안전한 매도 수량 계산 (추가 검증)
            calculated_quantity = target_sell_amount_krw / current_price
            safe_balance = current_balance * 0.99  # 수수료 고려하여 99%만 매도
            
            sell_quantity = min(calculated_quantity, safe_balance)
            
            # 최종 검증: 매도 수량이 잔고보다 크면 오류
            if sell_quantity > current_balance:
                logger.error(f"{asset} 매도 수량 오류: 계산된 수량({sell_quantity:.6f}) > 잔고({current_balance:.6f})")
                return {
                    "asset": asset,
                    "action": "sell",
                    "error": f"매도 수량 계산 오류: {sell_quantity:.6f} > {current_balance:.6f}",
                    "success": False
                }
            
            # 최소 거래 단위 확인 (너무 작은 수량 방지)
            estimated_krw = sell_quantity * current_price
            if estimated_krw < 1000:  # 1천원 미만 거래 방지
                logger.warning(f"{asset} 매도 금액이 너무 작음: {estimated_krw:,.0f} KRW")
                return {
                    "asset": asset,
                    "action": "sell",
                    "error": f"매도 금액이 너무 작음: {estimated_krw:,.0f} KRW",
                    "success": False
                }
            
            logger.info(f"{asset} 매도 계산: {target_sell_amount_krw:,.0f} KRW ÷ {current_price:,.0f} = {calculated_quantity:.6f} 개")
            logger.info(f"{asset} 실제 매도량: {sell_quantity:.6f} 개 (잔고: {current_balance:.6f} 개)")
            
            # 시장가 매도 주문 실행 (안전한 방법 사용)
            order_result = self.coinone_client.place_safe_order(
                currency=asset,
                side="sell",
                amount=sell_quantity,
                max_retries=2
            )
            
            return {
                "asset": asset,
                "action": "sell",
                "quantity": sell_quantity,
                "estimated_krw": sell_quantity * current_price,
                "order_id": order_result.get("order_id"),
                "success": order_result.get("success", False)
            }
            
        except Exception as e:
            logger.error(f"{asset} 매도 주문 실행 중 예외: {e}")
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
            
            # 시장가 매수 주문 실행 (KRW 금액 기준, 안전한 방법 사용)
            buy_amount_krw = min(target_buy_amount_krw, krw_balance * 0.99)  # 수수료 고려
            
            order_result = self.coinone_client.place_safe_order(
                currency=asset,
                side="buy", 
                amount=buy_amount_krw,  # KRW 금액
                amount_in_krw=True,  # KRW 금액으로 처리
                max_retries=2
            )
            
            return {
                "asset": asset,
                "action": "buy",
                "amount_krw": buy_amount_krw,
                "order_id": order_result.get("order_id"),
                "success": order_result.get("success", False)
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
        현재 시장 계절 판단
        
        1순위: 데이터베이스의 최신 주간 분석 결과 사용
        2순위: 실시간 계산 (200주 이동평균 기반)
        
        Returns:
            현재 시장 계절
        """
        try:
            # 1. 데이터베이스에서 최신 시장 분석 결과 조회 시도
            try:
                latest_analysis = self.db_manager.get_latest_market_analysis()
                
                if latest_analysis and latest_analysis.get("success"):
                    # 분석 결과가 너무 오래되지 않았는지 확인 (7일 이내)
                    analysis_date = latest_analysis.get("analysis_date")
                    if analysis_date:
                        if isinstance(analysis_date, str):
                            analysis_date = datetime.fromisoformat(analysis_date.replace('Z', '+00:00'))
                        
                        days_old = (datetime.now() - analysis_date.replace(tzinfo=None)).days
                        
                        if days_old <= 7:  # 7일 이내 데이터
                            season_str = latest_analysis.get("market_season", "neutral")
                            season_map = {
                                "risk_on": MarketSeason.RISK_ON,
                                "risk_off": MarketSeason.RISK_OFF, 
                                "neutral": MarketSeason.NEUTRAL
                            }
                            
                            season = season_map.get(season_str, MarketSeason.NEUTRAL)
                            logger.info(f"✅ 데이터베이스 시장 분석 결과 사용: {season.value} (분석일: {analysis_date.strftime('%Y-%m-%d')})")
                            return season
                        else:
                            logger.warning(f"데이터베이스 분석 결과가 오래됨: {days_old}일 전 → 실시간 계산 수행")
                    else:
                        logger.warning("분석 날짜 정보 없음 → 실시간 계산 수행")
                else:
                    logger.warning("유효한 시장 분석 결과 없음 → 실시간 계산 수행")
                    
            except Exception as db_error:
                logger.warning(f"데이터베이스 조회 실패: {db_error} → 실시간 계산 수행")
            
            # 2. 실시간 계산 (Fallback)
            logger.info("⚡ 실시간 시장 계절 판단 수행")
            
            # BTC 현재가 조회
            ticker = self.coinone_client.get_ticker("BTC")
            if not isinstance(ticker, dict) or "data" not in ticker:
                logger.error("BTC 티커 데이터 조회 실패")
                return MarketSeason.NEUTRAL
            
            ticker_data = ticker["data"]
            current_price = (
                float(ticker_data.get("last", 0)) or
                float(ticker_data.get("close_24h", 0)) or
                float(ticker_data.get("close", 0))
            )
            
            if current_price <= 0:
                logger.error(f"잘못된 BTC 현재가: {current_price}")
                return MarketSeason.NEUTRAL
            
            logger.info(f"BTC 현재가: {current_price:,.0f} KRW")
            
            # 실제 구현에서는 데이터베이스나 외부 API에서 200주 데이터를 가져와야 함
            # 현재는 임시로 200주 이동평균을 현재가의 90%로 가정
            # TODO: 실제 200주 가격 데이터 수집 및 계산 로직 구현 필요
            ma_200w = current_price * 0.9  # 임시값 (실제로는 DB에서 계산된 값 사용)
            
            logger.warning(f"⚠️  임시 200주 이동평균 사용: {ma_200w:,.0f} KRW")
            logger.warning("💡 정확한 분석을 위해 주간 분석 스크립트를 먼저 실행하세요: python scripts/weekly_check.py")
            
            # market_season_filter의 올바른 로직 사용
            market_season, analysis_info = self.market_season_filter.determine_market_season(
                current_price=current_price,
                ma_200w=ma_200w,
                previous_season=None
            )
            
            logger.info(f"🎯 실시간 시장 계절 판단: {market_season.value}")
            logger.info(f"📊 가격 비율: {analysis_info.get('price_ratio', 0):.3f}")
            logger.info(f"📏 판단 기준: Risk On >= {analysis_info.get('risk_on_threshold', 0):.2f}, "
                       f"Risk Off <= {analysis_info.get('risk_off_threshold', 0):.2f}")
            
            return market_season
                
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