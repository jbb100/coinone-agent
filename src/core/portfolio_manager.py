"""
Portfolio Manager

포트폴리오 구성 및 자산 배분 관리를 담당하는 모듈
동적 포트폴리오 최적화 기능 포함
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from loguru import logger

from .dynamic_portfolio_optimizer import DynamicPortfolioOptimizer, PortfolioWeights, AssetMetrics


@dataclass
class AssetAllocation:
    """자산 배분 설정"""
    btc_weight: float = 0.40  # BTC 40%
    eth_weight: float = 0.30  # ETH 30%
    xrp_weight: float = 0.15  # XRP 15%
    sol_weight: float = 0.15  # SOL 15%
    
    def get_crypto_weights(self) -> Dict[str, float]:
        """암호화폐 내 비중 반환"""
        return {
            "BTC": self.btc_weight,
            "ETH": self.eth_weight,
            "XRP": self.xrp_weight,
            "SOL": self.sol_weight
        }
    
    def validate_weights(self) -> bool:
        """비중 합계 검증 (100% = 1.0)"""
        total = self.btc_weight + self.eth_weight + self.xrp_weight + self.sol_weight
        return abs(total - 1.0) < 0.001  # 오차 허용


class PortfolioManager:
    """
    포트폴리오 관리자
    
    Core/Satellite 구조의 포트폴리오 구성 및 목표 비중 계산을 담당합니다.
    """
    
    def __init__(
        self, 
        asset_allocation: Optional[AssetAllocation] = None,
        coinone_client=None,
        use_dynamic_optimization: bool = False,
        risk_level: str = "moderate"
    ):
        """
        Args:
            asset_allocation: 자산 배분 설정 (기본값: 표준 배분)
            coinone_client: 코인원 클라이언트 (동적 최적화에 필요)
            use_dynamic_optimization: 동적 포트폴리오 최적화 사용 여부
            risk_level: 리스크 수준 (conservative/moderate/aggressive)
        """
        self.asset_allocation = asset_allocation or AssetAllocation()
        self.coinone_client = coinone_client
        self.use_dynamic_optimization = use_dynamic_optimization
        
        if not self.asset_allocation.validate_weights():
            raise ValueError("자산 배분 비중의 합이 100%가 아닙니다.")
        
        # Core/Satellite 구성
        self.core_assets = ["BTC", "ETH"]  # 70%
        self.satellite_assets = ["XRP", "SOL"]  # 30%
        self.core_weight = 0.70
        self.satellite_weight = 0.30
        
        # 동적 포트폴리오 최적화기 초기화
        self.dynamic_optimizer = None
        if use_dynamic_optimization and coinone_client:
            try:
                self.dynamic_optimizer = DynamicPortfolioOptimizer(
                    coinone_client=coinone_client,
                    risk_level=risk_level,
                    max_assets=6,
                    min_market_cap_usd=1e9
                )
                logger.info(f"동적 포트폴리오 최적화기 활성화 (리스크: {risk_level})")
            except Exception as e:
                logger.warning(f"동적 포트폴리오 최적화기 초기화 실패: {e}")
                self.use_dynamic_optimization = False
        
        # 마지막 최적화 시간 추적
        self.last_optimization_time = None
        self.optimization_cache = None
        
        logger.info("PortfolioManager 초기화 완료")
        logger.info(f"Core Assets: {self.core_assets} ({self.core_weight*100}%)")
        logger.info(f"Satellite Assets: {self.satellite_assets} ({self.satellite_weight*100}%)")
        if use_dynamic_optimization:
            logger.info("동적 포트폴리오 최적화 모드 활성화")
    
    def calculate_target_weights(
        self, 
        crypto_allocation: float, 
        krw_allocation: float
    ) -> Dict[str, float]:
        """
        목표 포트폴리오 비중 계산
        
        Args:
            crypto_allocation: 암호화폐 전체 비중 (0.3 or 0.7)
            krw_allocation: 원화 비중 (0.7 or 0.3)
            
        Returns:
            자산별 목표 비중 딕셔너리
        """
        if abs(crypto_allocation + krw_allocation - 1.0) > 0.001:
            raise ValueError("암호화폐와 원화 비중의 합이 100%가 아닙니다.")
        
        target_weights = {"KRW": krw_allocation}
        crypto_weights = self.asset_allocation.get_crypto_weights()
        
        # 암호화폐 내 개별 자산 비중 계산
        for asset, weight in crypto_weights.items():
            target_weights[asset] = crypto_allocation * weight
        
        logger.info(f"목표 비중 계산 완료: crypto {crypto_allocation*100}% / KRW {krw_allocation*100}%")
        logger.debug(f"목표 비중: {target_weights}")
        
        return target_weights
    
    def get_current_weights(self, portfolio_value: Dict) -> Dict[str, float]:
        """
        현재 포트폴리오 비중 계산
        
        Args:
            portfolio_value: 현재 포트폴리오 가치 정보
            
        Returns:
            현재 자산별 비중 딕셔너리
        """
        total_value = portfolio_value.get("total_krw", 0)
        if total_value <= 0:
            logger.warning("포트폴리오 총 가치가 0 이하입니다.")
            return {}
        
        current_weights = {}
        assets = portfolio_value.get("assets", {})
        
        # KRW 비중
        krw_asset = assets.get("KRW", {})
        krw_value = krw_asset.get("value_krw", 0) if isinstance(krw_asset, dict) else krw_asset
        current_weights["KRW"] = krw_value / total_value
        
        # 암호화폐 비중
        for asset in ["BTC", "ETH", "XRP", "SOL"]:
            asset_value = assets.get(asset, 0)
            # API 응답에서는 단순 숫자 값 또는 dict 형태 모두 지원
            if isinstance(asset_value, dict):
                asset_value = asset_value.get("value_krw", 0)
            elif not isinstance(asset_value, (int, float)):
                asset_value = 0
            
            current_weights[asset] = asset_value / total_value
        
        logger.debug(f"현재 비중: {current_weights}")
        return current_weights
    
    def calculate_rebalance_amounts(
        self, 
        current_portfolio: Dict, 
        target_weights: Dict[str, float]
    ) -> Dict[str, Dict]:
        """
        리밸런싱 필요 금액 계산
        
        Args:
            current_portfolio: 현재 포트폴리오 정보
            target_weights: 목표 비중
            
        Returns:
            리밸런싱 정보 딕셔너리
        """
        total_value = current_portfolio.get("total_krw", 0)
        current_weights = self.get_current_weights(current_portfolio)
        
        rebalance_info = {
            "total_value_krw": total_value,
            "rebalance_orders": {},
            "summary": {
                "buy_orders": [],
                "sell_orders": [],
                "total_buy_amount": 0,
                "total_sell_amount": 0
            }
        }
        
        for asset, target_weight in target_weights.items():
            current_weight = current_weights.get(asset, 0)
            weight_diff = target_weight - current_weight
            amount_diff = weight_diff * total_value
            
            # 임계값 설정 (총 자산의 1% 미만은 무시)
            threshold = total_value * 0.01
            
            if abs(amount_diff) > threshold:
                order_info = {
                    "asset": asset,
                    "current_weight": current_weight,
                    "target_weight": target_weight,
                    "weight_diff": weight_diff,
                    "amount_diff_krw": amount_diff,
                    "action": "buy" if amount_diff > 0 else "sell",
                    "priority": self._get_rebalance_priority(asset)
                }
                
                rebalance_info["rebalance_orders"][asset] = order_info
                
                # 요약 정보 업데이트
                if amount_diff > 0:
                    rebalance_info["summary"]["buy_orders"].append(asset)
                    rebalance_info["summary"]["total_buy_amount"] += amount_diff
                else:
                    rebalance_info["summary"]["sell_orders"].append(asset)
                    rebalance_info["summary"]["total_sell_amount"] += abs(amount_diff)
        
        # crypto 주문을 개별 암호화폐 주문으로 분해
        rebalance_info = self._expand_crypto_orders(rebalance_info)
        
        logger.info(f"리밸런싱 계산 완료: {len(rebalance_info['rebalance_orders'])}개 주문")
        return rebalance_info
    
    def _expand_crypto_orders(self, rebalance_info: Dict) -> Dict:
        """
        crypto 주문을 개별 암호화폐 주문으로 분해
        
        Args:
            rebalance_info: 리밸런싱 정보
            
        Returns:
            분해된 리밸런싱 정보
        """
        orders = rebalance_info["rebalance_orders"]
        
        # crypto 주문이 있는지 확인
        if "crypto" in orders:
            crypto_order = orders.pop("crypto")  # crypto 주문 제거
            crypto_amount = crypto_order["amount_diff_krw"]
            crypto_action = crypto_order["action"]
            
            logger.info(f"crypto 주문 분해: {crypto_action} {crypto_amount:,.0f} KRW")
            
            # 개별 암호화폐로 분배
            # Core assets (70%): BTC, ETH
            # Satellite assets (30%): XRP, SOL
            core_amount = crypto_amount * 0.7  # 70%
            satellite_amount = crypto_amount * 0.3  # 30%
            
            # Core assets 분배
            btc_amount = core_amount * (self.asset_allocation.btc_weight / (self.asset_allocation.btc_weight + self.asset_allocation.eth_weight))
            eth_amount = core_amount * (self.asset_allocation.eth_weight / (self.asset_allocation.btc_weight + self.asset_allocation.eth_weight))
            
            # Satellite assets 분배
            xrp_amount = satellite_amount * (self.asset_allocation.xrp_weight / (self.asset_allocation.xrp_weight + self.asset_allocation.sol_weight))
            sol_amount = satellite_amount * (self.asset_allocation.sol_weight / (self.asset_allocation.xrp_weight + self.asset_allocation.sol_weight))
            
            # 개별 암호화폐 주문 생성
            for asset, amount in [("BTC", btc_amount), ("ETH", eth_amount), ("XRP", xrp_amount), ("SOL", sol_amount)]:
                if abs(amount) > rebalance_info["total_value_krw"] * 0.01:  # 1% 임계값
                    orders[asset] = {
                        "asset": asset,
                        "current_weight": 0,  # 추후 정확한 값으로 업데이트 필요
                        "target_weight": amount / rebalance_info["total_value_krw"],
                        "weight_diff": amount / rebalance_info["total_value_krw"],
                        "amount_diff_krw": amount,
                        "action": crypto_action,
                        "priority": self._get_rebalance_priority(asset)
                    }
                    logger.info(f"  -> {asset}: {crypto_action} {amount:,.0f} KRW")
            
            # 요약 정보 업데이트
            summary = rebalance_info["summary"]
            if crypto_action == "buy":
                summary["buy_orders"].remove("crypto")
                summary["buy_orders"].extend([asset for asset in ["BTC", "ETH", "XRP", "SOL"] if asset in orders])
            else:
                summary["sell_orders"].remove("crypto")
                summary["sell_orders"].extend([asset for asset in ["BTC", "ETH", "XRP", "SOL"] if asset in orders])
        
        return rebalance_info
    
    def _get_rebalance_priority(self, asset: str) -> int:
        """
        리밸런싱 우선순위 반환
        
        Args:
            asset: 자산명
            
        Returns:
            우선순위 (낮을수록 높은 우선순위)
        """
        priority_map = {
            "KRW": 1,   # 원화 우선
            "BTC": 2,   # Core 자산
            "ETH": 3,   # Core 자산
            "XRP": 4,   # Satellite 자산
            "SOL": 5    # Satellite 자산
        }
        return priority_map.get(asset, 999)
    
    def validate_rebalance_feasibility(
        self, 
        rebalance_info: Dict,
        min_trade_amount: float = 10000  # 최소 거래 금액 (KRW)
    ) -> Dict[str, bool]:
        """
        리밸런싱 실행 가능성 검증
        
        Args:
            rebalance_info: 리밸런싱 정보
            min_trade_amount: 최소 거래 금액
            
        Returns:
            검증 결과 딕셔너리
        """
        validation_results = {}
        
        for asset, order_info in rebalance_info.get("rebalance_orders", {}).items():
            amount = abs(order_info["amount_diff_krw"])
            
            # 최소 거래 금액 검증
            if amount < min_trade_amount:
                validation_results[asset] = False
                logger.warning(f"{asset}: 거래 금액 부족 ({amount:,.0f} < {min_trade_amount:,.0f})")
            else:
                validation_results[asset] = True
                logger.debug(f"{asset}: 리밸런싱 가능 ({amount:,.0f} KRW)")
        
        return validation_results
    
    def get_optimal_portfolio_weights(self, force_optimization: bool = False) -> Dict[str, float]:
        """
        최적 포트폴리오 비중 조회
        
        동적 최적화가 활성화된 경우 최적화된 비중 반환,
        그렇지 않으면 기본 자산 배분 비중 반환
        
        Args:
            force_optimization: 강제 최적화 실행 여부
            
        Returns:
            자산별 최적 비중 딕셔너리
        """
        try:
            if not self.use_dynamic_optimization or not self.dynamic_optimizer:
                # 동적 최적화 비활성화 시 기본 비중 사용
                return self.asset_allocation.get_crypto_weights()
            
            # 캐시 확인 (30분 이내면 재사용)
            if (not force_optimization and 
                self.optimization_cache and 
                self.last_optimization_time and
                datetime.now() - self.last_optimization_time < timedelta(minutes=30)):
                
                logger.info("최적화 캐시 사용 (30분 이내)")
                return self.optimization_cache.weights
            
            # 새로운 최적화 실행
            logger.info("포트폴리오 최적화 실행")
            optimal_portfolio = self.dynamic_optimizer.generate_optimal_portfolio()
            
            if optimal_portfolio and optimal_portfolio.weights:
                self.optimization_cache = optimal_portfolio
                self.last_optimization_time = datetime.now()
                
                logger.info("최적화 완료:")
                for asset, weight in optimal_portfolio.weights.items():
                    logger.info(f"  {asset}: {weight:.1%}")
                logger.info(f"예상 수익률: {optimal_portfolio.expected_return:.1%}, "
                          f"리스크: {optimal_portfolio.expected_risk:.1%}")
                
                return optimal_portfolio.weights
            else:
                logger.warning("최적화 실패 - 기본 비중 사용")
                return self.asset_allocation.get_crypto_weights()
                
        except Exception as e:
            logger.error(f"포트폴리오 최적화 실패: {e}")
            return self.asset_allocation.get_crypto_weights()
    
    def should_rebalance_portfolio(
        self, 
        current_portfolio: Dict,
        rebalance_threshold: float = 0.05
    ) -> Tuple[bool, Dict]:
        """
        포트폴리오 리밸런싱 필요 여부 판단
        
        Args:
            current_portfolio: 현재 포트폴리오 정보
            rebalance_threshold: 리밸런싱 임계값 (5% 기본)
            
        Returns:
            (리밸런싱 필요 여부, 편차 정보)
        """
        try:
            current_weights = self.get_current_weights(current_portfolio)
            optimal_weights = self.get_optimal_portfolio_weights()
            
            # 현재 비중과 최적 비중 비교
            deviations = {}
            max_deviation = 0
            total_deviation = 0
            
            # 모든 자산에 대해 편차 계산
            all_assets = set(list(current_weights.keys()) + list(optimal_weights.keys()))
            
            for asset in all_assets:
                if asset == "KRW":  # KRW는 별도 처리
                    continue
                    
                current_weight = current_weights.get(asset, 0)
                optimal_weight = optimal_weights.get(asset, 0)
                deviation = abs(current_weight - optimal_weight)
                
                deviations[asset] = {
                    "current_weight": current_weight,
                    "optimal_weight": optimal_weight,
                    "deviation": deviation
                }
                
                max_deviation = max(max_deviation, deviation)
                total_deviation += deviation
            
            # 리밸런싱 필요 여부 판단
            needs_rebalancing = max_deviation > rebalance_threshold
            
            rebalance_info = {
                "needs_rebalancing": needs_rebalancing,
                "max_deviation": max_deviation,
                "total_deviation": total_deviation,
                "threshold": rebalance_threshold,
                "deviations": deviations,
                "recommendation": "리밸런싱 필요" if needs_rebalancing else "리밸런싱 불필요"
            }
            
            logger.info(f"리밸런싱 검토: 최대 편차 {max_deviation:.1%} "
                       f"(임계값: {rebalance_threshold:.1%}) "
                       f"-> {rebalance_info['recommendation']}")
            
            return needs_rebalancing, rebalance_info
            
        except Exception as e:
            logger.error(f"리밸런싱 판단 실패: {e}")
            return False, {"error": str(e)}
    
    def calculate_dynamic_target_weights(
        self, 
        crypto_allocation: float, 
        krw_allocation: float,
        use_optimization: bool = True
    ) -> Dict[str, float]:
        """
        동적 최적화를 고려한 목표 비중 계산
        
        Args:
            crypto_allocation: 암호화폐 전체 비중
            krw_allocation: 원화 비중
            use_optimization: 동적 최적화 사용 여부
            
        Returns:
            자산별 목표 비중 딕셔너리
        """
        try:
            if abs(crypto_allocation + krw_allocation - 1.0) > 0.001:
                raise ValueError("암호화폐와 원화 비중의 합이 100%가 아닙니다.")
            
            target_weights = {"KRW": krw_allocation}
            
            # 동적 최적화 사용 시 최적화된 비중 적용
            if use_optimization and self.use_dynamic_optimization:
                optimal_weights = self.get_optimal_portfolio_weights()
                
                # 암호화폐 전체 비중을 최적화된 비중에 따라 분배
                for asset, weight in optimal_weights.items():
                    target_weights[asset] = crypto_allocation * weight
                    
                logger.info(f"동적 최적화 목표 비중 적용: crypto {crypto_allocation*100}%")
            else:
                # 기본 자산 배분 사용
                crypto_weights = self.asset_allocation.get_crypto_weights()
                for asset, weight in crypto_weights.items():
                    target_weights[asset] = crypto_allocation * weight
                    
                logger.info(f"기본 목표 비중 적용: crypto {crypto_allocation*100}%")
            
            logger.debug(f"최종 목표 비중: {target_weights}")
            return target_weights
            
        except Exception as e:
            logger.error(f"동적 목표 비중 계산 실패: {e}")
            # 오류 시 기본 방식으로 폴백
            return self.calculate_target_weights(crypto_allocation, krw_allocation)
    
    def get_portfolio_optimization_status(self) -> Dict:
        """
        포트폴리오 최적화 상태 정보 조회
        
        Returns:
            최적화 상태 정보 딕셔너리
        """
        try:
            status = {
                "dynamic_optimization_enabled": self.use_dynamic_optimization,
                "optimizer_available": self.dynamic_optimizer is not None,
                "last_optimization_time": self.last_optimization_time,
                "cache_available": self.optimization_cache is not None,
                "time_since_last_optimization": None
            }
            
            if self.last_optimization_time:
                time_diff = datetime.now() - self.last_optimization_time
                status["time_since_last_optimization"] = {
                    "minutes": int(time_diff.total_seconds() / 60),
                    "is_fresh": time_diff < timedelta(minutes=30)
                }
            
            if self.optimization_cache:
                status["cached_portfolio"] = {
                    "weights": self.optimization_cache.weights,
                    "risk_level": self.optimization_cache.risk_level,
                    "expected_return": self.optimization_cache.expected_return,
                    "expected_risk": self.optimization_cache.expected_risk,
                    "sharpe_ratio": self.optimization_cache.sharpe_ratio
                }
            
            return status
            
        except Exception as e:
            logger.error(f"최적화 상태 조회 실패: {e}")
            return {"error": str(e)}
    
    def force_portfolio_optimization(self) -> PortfolioWeights:
        """
        포트폴리오 강제 최적화 실행
        
        Returns:
            최적화된 포트폴리오 비중
        """
        try:
            if not self.use_dynamic_optimization or not self.dynamic_optimizer:
                raise ValueError("동적 포트폴리오 최적화가 활성화되지 않았습니다.")
            
            logger.info("포트폴리오 강제 최적화 실행")
            optimal_portfolio = self.dynamic_optimizer.generate_optimal_portfolio()
            
            if optimal_portfolio:
                self.optimization_cache = optimal_portfolio
                self.last_optimization_time = datetime.now()
                
                logger.info("강제 최적화 완료")
                return optimal_portfolio
            else:
                raise ValueError("최적화 실행 실패")
                
        except Exception as e:
            logger.error(f"강제 최적화 실패: {e}")
            raise
    
    def get_portfolio_metrics(self, current_portfolio: Dict) -> Dict:
        """
        포트폴리오 메트릭 계산
        
        Args:
            current_portfolio: 현재 포트폴리오 정보
            
        Returns:
            포트폴리오 메트릭 딕셔너리
        """
        current_weights = self.get_current_weights(current_portfolio)
        total_value = current_portfolio.get("total_krw", 0)
        
        # Core/Satellite 비중 계산
        core_weight = sum(current_weights.get(asset, 0) for asset in self.core_assets)
        satellite_weight = sum(current_weights.get(asset, 0) for asset in self.satellite_assets)
        krw_weight = current_weights.get("KRW", 0)
        crypto_weight = core_weight + satellite_weight
        
        metrics = {
            "total_value_krw": total_value,
            "weights": {
                "crypto_total": crypto_weight,
                "krw": krw_weight,
                "core": core_weight,
                "satellite": satellite_weight
            },
            "asset_weights": current_weights,
            "portfolio_health": {
                "is_balanced": abs(crypto_weight + krw_weight - 1.0) < 0.05,
                "core_satellite_ratio": core_weight / satellite_weight if satellite_weight > 0 else float('inf'),
                "target_core_satellite_ratio": self.core_weight / self.satellite_weight
            },
            "last_updated": datetime.now()
        }
        
        logger.info(f"포트폴리오 메트릭: 총 가치 {total_value:,.0f} KRW, 암호화폐 {crypto_weight:.1%}")
        return metrics


# 설정 상수
DEFAULT_CRYPTO_ALLOCATION = {
    "RISK_ON": 0.70,    # 강세장
    "RISK_OFF": 0.30,   # 약세장
    "NEUTRAL": 0.50     # 중립
}

MIN_REBALANCE_THRESHOLD = 0.01  # 1% 이상 차이날 때 리밸런싱
MIN_TRADE_AMOUNT_KRW = 10000   # 최소 거래 금액 10,000원 