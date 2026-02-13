"""
Backtest Validator Module

백테스트 결과 검증 (Look-ahead bias, 과적합 경고, OOS 테스트)
"""

from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional
from loguru import logger

from src.utils.constants import (
    SHARPE_OVERFITTING_THRESHOLD,
    MAX_STRATEGY_PARAMS,
    OOS_PERFORMANCE_DROP_THRESHOLD
)


class BacktestValidator:
    """
    백테스트 검증기

    Look-ahead bias, 과적합, Out-of-sample 성능 검증을 수행합니다.
    """

    def __init__(
        self,
        sharpe_threshold: float = SHARPE_OVERFITTING_THRESHOLD,
        max_params: int = MAX_STRATEGY_PARAMS,
        oos_drop_threshold: float = OOS_PERFORMANCE_DROP_THRESHOLD,
        win_rate_threshold: float = 0.80  # 80% 초과 승률 경고
    ):
        """
        Args:
            sharpe_threshold: Sharpe ratio 과적합 임계값
            max_params: 최대 전략 파라미터 수
            oos_drop_threshold: OOS 성능 하락 임계값
            win_rate_threshold: 비현실적 승률 임계값
        """
        self.sharpe_threshold = sharpe_threshold
        self.max_params = max_params
        self.oos_drop_threshold = oos_drop_threshold
        self.win_rate_threshold = win_rate_threshold

        logger.info("BacktestValidator 초기화 완료")

    def check_lookahead_bias(self, trades: List[Dict]) -> List[Dict]:
        """
        Look-ahead bias 검사

        거래 신호가 실제 거래일 이전에 생성되었는지 확인합니다.

        Args:
            trades: 거래 목록 (date, signal_date 포함)

        Returns:
            Look-ahead bias 위반 목록
        """
        violations = []

        for trade in trades:
            trade_date = trade.get("date")
            signal_date = trade.get("signal_date")

            if not trade_date or not signal_date:
                continue

            # 날짜 파싱
            if isinstance(trade_date, str):
                trade_date = datetime.strptime(trade_date, "%Y-%m-%d")
            if isinstance(signal_date, str):
                signal_date = datetime.strptime(signal_date, "%Y-%m-%d")

            # 신호가 거래일 이후면 look-ahead bias
            if signal_date > trade_date:
                violations.append({
                    "trade_date": trade.get("date"),
                    "signal_date": trade.get("signal_date"),
                    "message": "미래 데이터 사용 감지"
                })
                logger.warning(f"Look-ahead bias 감지: {trade.get('date')}")

        return violations

    def validate_data_availability(self, config: Dict) -> Tuple[bool, str]:
        """
        데이터 사용 가능 시점 검증

        Args:
            config: 백테스트 설정 (start_date, lookback_period, data_start_date)

        Returns:
            (유효 여부, 메시지) 튜플
        """
        start_date = config.get("start_date")
        lookback_period = config.get("lookback_period", 0)
        data_start_date = config.get("data_start_date")

        if not start_date or not data_start_date:
            return False, "시작일 또는 데이터 시작일 누락"

        # 날짜 파싱
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
        if isinstance(data_start_date, str):
            data_start_date = datetime.strptime(data_start_date, "%Y-%m-%d")

        # lookback 기간만큼의 데이터가 있어야 함
        required_start = start_date
        if lookback_period > 0:
            from datetime import timedelta
            required_start = start_date - timedelta(days=lookback_period)

        if data_start_date > required_start:
            return False, f"lookback 기간({lookback_period}일)을 위한 데이터 부족"

        return True, "데이터 사용 가능"

    def check_overfitting_warnings(self, metrics: Dict) -> List[str]:
        """
        과적합 경고 검사

        Args:
            metrics: 성과 지표 (sharpe_ratio, win_rate 등)

        Returns:
            경고 메시지 목록
        """
        warnings = []

        # Sharpe ratio 검사
        sharpe = metrics.get("sharpe_ratio", 0)
        if sharpe > self.sharpe_threshold:
            warnings.append(
                f"과적합 의심: Sharpe ratio {sharpe:.2f}가 "
                f"임계값 {self.sharpe_threshold}를 초과합니다"
            )
            logger.warning(f"높은 Sharpe ratio 감지: {sharpe:.2f}")

        # 승률 검사
        win_rate = metrics.get("win_rate", 0)
        if win_rate > self.win_rate_threshold:
            warnings.append(
                f"비현실적 승률: {win_rate:.1%}는 "
                f"과적합 가능성이 높습니다"
            )
            logger.warning(f"높은 승률 감지: {win_rate:.1%}")

        # 수익률 대비 최대 낙폭 비율 검사
        total_return = metrics.get("total_return", 0)
        max_drawdown = metrics.get("max_drawdown", 0)
        if total_return > 0 and max_drawdown > 0:
            return_to_dd = total_return / max_drawdown
            if return_to_dd > 10:  # 수익률이 낙폭의 10배 초과
                warnings.append(
                    f"비현실적인 수익/낙폭 비율: {return_to_dd:.1f}"
                )

        return warnings

    def check_parameter_warnings(self, strategy_params: Dict) -> List[str]:
        """
        전략 파라미터 수 검사

        Args:
            strategy_params: 전략 파라미터 딕셔너리

        Returns:
            경고 메시지 목록
        """
        warnings = []

        param_count = len(strategy_params)
        if param_count > self.max_params:
            warnings.append(
                f"과적합 위험: 파라미터 {param_count}개가 "
                f"권장 최대값 {self.max_params}개를 초과합니다"
            )
            logger.warning(f"과다 파라미터 감지: {param_count}개")

        return warnings

    def compare_is_oos(
        self,
        in_sample_metrics: Dict,
        out_of_sample_metrics: Dict
    ) -> Dict:
        """
        In-sample vs Out-of-sample 비교

        Args:
            in_sample_metrics: In-sample 성과 지표
            out_of_sample_metrics: Out-of-sample 성과 지표

        Returns:
            비교 결과 딕셔너리
        """
        is_return = in_sample_metrics.get("total_return", 0)
        oos_return = out_of_sample_metrics.get("total_return", 0)

        # 성능 하락률 계산
        if is_return > 0:
            performance_drop = (is_return - oos_return) / is_return
        else:
            performance_drop = 0

        is_overfitted = performance_drop > self.oos_drop_threshold

        result = {
            "in_sample": in_sample_metrics,
            "out_of_sample": out_of_sample_metrics,
            "performance_drop": performance_drop,
            "is_overfitted": is_overfitted
        }

        if is_overfitted:
            logger.warning(
                f"과적합 감지: OOS 성능 하락 {performance_drop:.1%}"
            )

        return result

    def generate_validation_report(self, backtest_result: Dict) -> Dict:
        """
        전체 검증 리포트 생성

        Args:
            backtest_result: 백테스트 결과

        Returns:
            검증 리포트
        """
        trades = backtest_result.get("trades", [])
        metrics = backtest_result.get("metrics", {})
        strategy_params = backtest_result.get("strategy_params", {})

        # 각 검증 수행
        lookahead_violations = self.check_lookahead_bias(trades)
        overfitting_warnings = self.check_overfitting_warnings(metrics)
        parameter_warnings = self.check_parameter_warnings(strategy_params)

        # 전체 유효성 판단
        is_valid = (
            len(lookahead_violations) == 0 and
            len(overfitting_warnings) == 0 and
            len(parameter_warnings) == 0
        )

        report = {
            "lookahead_violations": lookahead_violations,
            "overfitting_warnings": overfitting_warnings,
            "parameter_warnings": parameter_warnings,
            "is_valid": is_valid,
            "validated_at": datetime.now().isoformat()
        }

        logger.info(f"백테스트 검증 완료: 유효={is_valid}")
        return report
