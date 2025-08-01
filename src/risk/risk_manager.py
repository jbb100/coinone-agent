"""
Risk Manager

리스크 관리 및 3-라인 체크 시스템을 담당하는 모듈
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from loguru import logger


@dataclass
class RiskLimits:
    """리스크 제한 설정"""
    max_single_trade: float = 10000000  # 단일 거래 최대 금액 (KRW)
    max_daily_volume: float = 50000000  # 일일 최대 거래 금액 (KRW)
    max_position_size: float = 0.50     # 최대 포지션 크기 (전체 포트폴리오 대비)
    max_daily_loss: float = 0.05        # 일일 최대 손실률 (5%)
    max_monthly_loss: float = 0.15      # 월간 최대 손실률 (15%)
    drawdown_threshold: float = 0.20    # 드로우다운 임계값 (20%)


@dataclass
class RiskCheckResult:
    """리스크 체크 결과"""
    approved: bool = False
    risk_score: float = 0.0
    warnings: List[str] = None
    restrictions: List[str] = None
    reason: str = ""
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.restrictions is None:
            self.restrictions = []


class RiskManager:
    """
    리스크 관리자
    
    3-라인 체크 시스템과 리스크 제한을 통해 포트폴리오를 보호합니다.
    """
    
    def __init__(self, config):
        """
        Args:
            config: ConfigLoader 인스턴스
        """
        self.config = config
        self.risk_config = config.get_risk_config()
        
        # 리스크 제한 설정
        trading_limits = self.risk_config.get("trading_limits", {})
        loss_limits = self.risk_config.get("loss_limits", {})
        
        self.risk_limits = RiskLimits(
            max_single_trade=trading_limits.get("max_single_trade", 10000000),
            max_daily_volume=trading_limits.get("max_daily_volume", 50000000),
            max_position_size=trading_limits.get("max_position_size", 0.50),
            max_daily_loss=loss_limits.get("max_daily_loss", 0.05),
            max_monthly_loss=loss_limits.get("max_monthly_loss", 0.15),
            drawdown_threshold=loss_limits.get("drawdown_threshold", 0.20)
        )
        
        # 3-라인 체크 설정
        three_line_config = self.risk_config.get("three_line_check", {})
        self.performance_period = three_line_config.get("performance_period", 30)
        self.tracking_error_threshold = three_line_config.get("tracking_error_threshold", 0.02)
        self.benchmark = three_line_config.get("benchmark", "BTC")
        
        # 일일 거래량 추적
        self.daily_trade_volume = 0
        self.last_reset_date = datetime.now().date()
        
        logger.info("RiskManager 초기화 완료")
    
    def pre_trade_risk_check(self, portfolio_data: Dict, trade_amount: float = 0) -> RiskCheckResult:
        """
        거래 전 리스크 체크
        
        Args:
            portfolio_data: 현재 포트폴리오 데이터
            trade_amount: 거래 금액 (KRW)
            
        Returns:
            리스크 체크 결과
        """
        result = RiskCheckResult()
        
        try:
            total_value = portfolio_data.get("total_krw", 0)
            
            # 1. 기본 포트폴리오 검증
            if total_value <= 0:
                result.reason = "포트폴리오 총 가치가 0 이하"
                return result
            
            # 2. 단일 거래 한도 체크
            if trade_amount > self.risk_limits.max_single_trade:
                result.warnings.append(
                    f"단일 거래 한도 초과: {trade_amount:,.0f} > {self.risk_limits.max_single_trade:,.0f}"
                )
                result.risk_score += 0.3
            
            # 3. 일일 거래량 체크
            self._reset_daily_volume_if_needed()
            projected_daily_volume = self.daily_trade_volume + trade_amount
            
            if projected_daily_volume > self.risk_limits.max_daily_volume:
                result.restrictions.append(
                    f"일일 거래량 한도 초과: {projected_daily_volume:,.0f} > {self.risk_limits.max_daily_volume:,.0f}"
                )
                result.risk_score += 0.5
            
            # 4. 포지션 크기 체크
            position_size_check = self._check_position_sizes(portfolio_data)
            if position_size_check:
                result.warnings.extend(position_size_check)
                result.risk_score += 0.2
            
            # 5. 손실 한도 체크
            loss_check = self._check_loss_limits(portfolio_data)
            if loss_check:
                result.restrictions.extend(loss_check)
                result.risk_score += 0.4
            
            # 6. 최종 승인 결정
            if result.risk_score >= 0.5 or result.restrictions:
                result.approved = False
                result.reason = "리스크 임계값 초과 또는 제한 사항 발생"
            else:
                result.approved = True
                result.reason = "리스크 체크 통과"
            
            logger.info(f"거래 전 리스크 체크 완료: {'승인' if result.approved else '거부'}")
            return result
            
        except Exception as e:
            logger.error(f"리스크 체크 실패: {e}")
            result.approved = False
            result.reason = f"리스크 체크 오류: {str(e)}"
            return result
    
    def _check_position_sizes(self, portfolio_data: Dict) -> List[str]:
        """
        포지션 크기 체크
        
        Args:
            portfolio_data: 포트폴리오 데이터
            
        Returns:
            경고 메시지 리스트
        """
        warnings = []
        total_value = portfolio_data.get("total_krw", 0)
        assets = portfolio_data.get("assets", {})
        
        for asset_name, asset_data in assets.items():
            if asset_name == "KRW":  # 원화는 제외
                continue
                
            if isinstance(asset_data, dict):
                asset_value = asset_data.get("value_krw", 0)
            else:
                asset_value = 0
            
            position_ratio = asset_value / total_value if total_value > 0 else 0
            
            if position_ratio > self.risk_limits.max_position_size:
                warnings.append(
                    f"{asset_name} 포지션 크기 과다: {position_ratio:.1%} > {self.risk_limits.max_position_size:.1%}"
                )
        
        return warnings
    
    def _check_loss_limits(self, portfolio_data: Dict) -> List[str]:
        """
        손실 한도 체크
        
        Args:
            portfolio_data: 포트폴리오 데이터
            
        Returns:
            제한 사항 메시지 리스트
        """
        restrictions = []
        
        # TODO: 실제 구현에서는 데이터베이스에서 과거 데이터를 조회해야 함
        # 여기서는 예시로 간단한 로직만 구현
        
        # 일일 손실 체크 (임시)
        # daily_loss = self._calculate_daily_loss(portfolio_data)
        # if daily_loss < -self.risk_limits.max_daily_loss:
        #     restrictions.append(f"일일 손실 한도 초과: {daily_loss:.2%}")
        
        return restrictions
    
    def _reset_daily_volume_if_needed(self):
        """일일 거래량 리셋 (날짜 변경시)"""
        today = datetime.now().date()
        if today != self.last_reset_date:
            self.daily_trade_volume = 0
            self.last_reset_date = today
            logger.info("일일 거래량 카운터 리셋")
    
    def update_daily_volume(self, trade_amount: float):
        """
        일일 거래량 업데이트
        
        Args:
            trade_amount: 거래 금액
        """
        self._reset_daily_volume_if_needed()
        self.daily_trade_volume += trade_amount
        logger.debug(f"일일 거래량 업데이트: {self.daily_trade_volume:,.0f} KRW")
    
    def three_line_check(self, portfolio_data: Dict, performance_data: Dict) -> Dict:
        """
        3-라인 체크 시스템 실행
        
        Args:
            portfolio_data: 포트폴리오 데이터
            performance_data: 성과 데이터
            
        Returns:
            체크 결과
        """
        check_results = {
            "line1_performance": {"status": "ok", "message": ""},
            "line2_decisions": {"status": "ok", "message": ""},
            "line3_tracking": {"status": "ok", "message": ""},
            "overall_status": "ok",
            "timestamp": datetime.now()
        }
        
        try:
            # Line 1: 성과 기록 체크
            line1_result = self._check_performance_record(performance_data)
            check_results["line1_performance"] = line1_result
            
            # Line 2: 의사결정 로그 체크
            line2_result = self._check_decision_logs()
            check_results["line2_decisions"] = line2_result
            
            # Line 3: 추적오차 알림 체크
            line3_result = self._check_tracking_error(performance_data)
            check_results["line3_tracking"] = line3_result
            
            # 전체 상태 결정
            all_statuses = [
                line1_result["status"],
                line2_result["status"], 
                line3_result["status"]
            ]
            
            if "error" in all_statuses:
                check_results["overall_status"] = "error"
            elif "warning" in all_statuses:
                check_results["overall_status"] = "warning"
            else:
                check_results["overall_status"] = "ok"
            
            logger.info(f"3-라인 체크 완료: {check_results['overall_status']}")
            return check_results
            
        except Exception as e:
            logger.error(f"3-라인 체크 실패: {e}")
            check_results["overall_status"] = "error"
            check_results["error"] = str(e)
            return check_results
    
    def _check_performance_record(self, performance_data: Dict) -> Dict:
        """
        Line 1: 성과 기록 체크
        
        Args:
            performance_data: 성과 데이터
            
        Returns:
            체크 결과
        """
        try:
            total_return = performance_data.get("total_return", 0)
            benchmark_return = performance_data.get("benchmark_return", 0)
            sharpe_ratio = performance_data.get("sharpe_ratio", 0)
            
            if total_return < -0.15:  # -15% 이상 손실
                return {
                    "status": "error",
                    "message": f"심각한 손실 발생: {total_return:.2%}"
                }
            elif total_return < -0.05:  # -5% 이상 손실
                return {
                    "status": "warning",
                    "message": f"손실 주의: {total_return:.2%}"
                }
            elif sharpe_ratio < 0:
                return {
                    "status": "warning",
                    "message": f"샤프 비율 부정: {sharpe_ratio:.2f}"
                }
            else:
                return {
                    "status": "ok",
                    "message": f"성과 양호: 수익률 {total_return:.2%}, 샤프 {sharpe_ratio:.2f}"
                }
                
        except Exception as e:
            return {
                "status": "error",
                "message": f"성과 체크 오류: {str(e)}"
            }
    
    def _check_decision_logs(self) -> Dict:
        """
        Line 2: 의사결정 로그 체크
        
        Returns:
            체크 결과
        """
        try:
            # TODO: 실제 구현에서는 데이터베이스에서 최근 의사결정 로그를 확인
            # 여기서는 간단한 예시만 제공
            
            return {
                "status": "ok",
                "message": "의사결정 로그 정상"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"의사결정 로그 체크 오류: {str(e)}"
            }
    
    def _check_tracking_error(self, performance_data: Dict) -> Dict:
        """
        Line 3: 추적오차 알림 체크
        
        Args:
            performance_data: 성과 데이터
            
        Returns:
            체크 결과
        """
        try:
            tracking_error = performance_data.get("tracking_error", 0)
            
            if tracking_error > self.tracking_error_threshold:
                return {
                    "status": "warning",
                    "message": f"추적오차 임계값 초과: {tracking_error:.2%} > {self.tracking_error_threshold:.2%}"
                }
            else:
                return {
                    "status": "ok",
                    "message": f"추적오차 정상: {tracking_error:.2%}"
                }
                
        except Exception as e:
            return {
                "status": "error",
                "message": f"추적오차 체크 오류: {str(e)}"
            }
    
    def calculate_risk_score(self, portfolio_data: Dict) -> float:
        """
        전체 포트폴리오 리스크 스코어 계산
        
        Args:
            portfolio_data: 포트폴리오 데이터
            
        Returns:
            리스크 스코어 (0.0 ~ 1.0)
        """
        try:
            risk_score = 0.0
            
            # 포지션 집중도 리스크
            concentration_risk = self._calculate_concentration_risk(portfolio_data)
            risk_score += concentration_risk * 0.3
            
            # 변동성 리스크 (임시)
            volatility_risk = 0.2  # TODO: 실제 변동성 계산
            risk_score += volatility_risk * 0.2
            
            # 유동성 리스크
            liquidity_risk = self._calculate_liquidity_risk(portfolio_data)
            risk_score += liquidity_risk * 0.3
            
            # 시장 리스크
            market_risk = 0.3  # TODO: 시장 상황 기반 계산
            risk_score += market_risk * 0.2
            
            return min(risk_score, 1.0)
            
        except Exception as e:
            logger.error(f"리스크 스코어 계산 실패: {e}")
            return 0.5  # 중간값 반환
    
    def _calculate_concentration_risk(self, portfolio_data: Dict) -> float:
        """포지션 집중도 리스크 계산"""
        total_value = portfolio_data.get("total_krw", 0)
        if total_value <= 0:
            return 1.0
        
        assets = portfolio_data.get("assets", {})
        max_position_ratio = 0
        
        for asset_name, asset_data in assets.items():
            if asset_name == "KRW":
                continue
                
            if isinstance(asset_data, dict):
                asset_value = asset_data.get("value_krw", 0)
            else:
                asset_value = 0
            
            position_ratio = asset_value / total_value
            max_position_ratio = max(max_position_ratio, position_ratio)
        
        # 최대 포지션이 50% 이상이면 고위험
        return min(max_position_ratio / 0.5, 1.0)
    
    def _calculate_liquidity_risk(self, portfolio_data: Dict) -> float:
        """유동성 리스크 계산"""
        # 암호화폐는 일반적으로 유동성이 좋으므로 낮은 리스크
        # BTC, ETH는 매우 높은 유동성, 알트코인은 중간 정도
        
        total_value = portfolio_data.get("total_krw", 0)
        if total_value <= 0:
            return 0.0
        
        assets = portfolio_data.get("assets", {})
        weighted_risk = 0
        
        liquidity_scores = {
            "BTC": 0.1,   # 매우 높은 유동성
            "ETH": 0.1,   # 매우 높은 유동성
            "XRP": 0.3,   # 중간 유동성
            "SOL": 0.3,   # 중간 유동성
            "KRW": 0.0    # 현금
        }
        
        for asset_name, asset_data in assets.items():
            if isinstance(asset_data, dict):
                asset_value = asset_data.get("value_krw", 0)
            elif asset_name == "KRW":
                asset_value = asset_data
            else:
                asset_value = 0
            
            weight = asset_value / total_value
            liquidity_score = liquidity_scores.get(asset_name, 0.5)  # 기본값: 중간 리스크
            weighted_risk += weight * liquidity_score
        
        return weighted_risk
    
    def get_risk_limits(self) -> RiskLimits:
        """현재 리스크 제한 설정 반환"""
        return self.risk_limits
    
    def update_risk_limits(self, new_limits: Dict):
        """
        리스크 제한 설정 업데이트
        
        Args:
            new_limits: 새로운 제한 설정
        """
        for key, value in new_limits.items():
            if hasattr(self.risk_limits, key):
                setattr(self.risk_limits, key, value)
                logger.info(f"리스크 제한 업데이트: {key} = {value}")


# 설정 상수
DEFAULT_PERFORMANCE_PERIOD = 30    # 성과 추적 기간 (일)
DEFAULT_TRACKING_ERROR_THRESHOLD = 0.02  # 추적오차 임계값 (2%)
RISK_SCORE_LEVELS = {
    "low": 0.3,
    "medium": 0.6, 
    "high": 1.0
} 