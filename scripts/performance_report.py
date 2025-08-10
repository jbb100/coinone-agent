#!/usr/bin/env python3
"""
KAIROS-1 성과 분석 보고서 생성 스크립트

포트폴리오 성과를 분석하고 상세 보고서를 생성합니다.
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import argparse
from loguru import logger

# 프로젝트 루트 디렉토리를 PYTHONPATH에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.monitoring.performance_tracker import PerformanceTracker
from src.monitoring.alert_system import AlertSystem
from src.utils.config_loader import ConfigLoader
from src.utils.database_manager import DatabaseManager


class PerformanceReportGenerator:
    """성과 보고서 생성기"""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """
        Args:
            config_path: 설정 파일 경로
        """
        self.config = ConfigLoader(config_path)
        self.db_manager = DatabaseManager(self.config)
        self.performance_tracker = PerformanceTracker(self.config, self.db_manager)
        self.alert_system = AlertSystem(self.config)
        
        # 로깅 설정
        self._setup_logging()
        
        logger.info("PerformanceReportGenerator 초기화 완료")
    
    def _setup_logging(self):
        """로깅 설정"""
        log_level = self.config.get("logging.level", "INFO")
        log_file = self.config.get("logging.file_path", "./logs/performance_report.log")
        
        logger.remove()  # 기본 핸들러 제거
        logger.add(
            log_file,
            level=log_level,
            rotation=self.config.get("logging.rotation", "100 MB"),
            retention=self.config.get("logging.retention", "30 days"),
            format=self.config.get("logging.format", 
                "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}")
        )
        logger.add(sys.stdout, level=log_level)
    
    def generate_comprehensive_report(
        self, 
        periods: list = [7, 30, 90]
    ) -> dict:
        """
        종합 성과 보고서 생성
        
        Args:
            periods: 분석 기간 리스트 (일)
            
        Returns:
            종합 보고서 딕셔너리
        """
        try:
            logger.info("=== KAIROS-1 종합 성과 보고서 생성 시작 ===")
            
            comprehensive_report = {
                "report_date": datetime.now(),
                "periods_analyzed": periods,
                "performance_by_period": {},
                "benchmark_comparison": {},
                "overall_summary": {},
                "risk_analysis": {},
                "recommendations": []
            }
            
            # 각 기간별 성과 분석
            for period in periods:
                logger.info(f"{period}일간 성과 분석 시작")
                
                # 성과 지표 계산
                metrics = self.performance_tracker.calculate_performance_metrics(period)
                
                # 성과 보고서 생성
                period_report = self.performance_tracker.generate_performance_report(period)
                
                # 벤치마크 비교
                benchmark_comparison = self.performance_tracker.compare_with_benchmark(period)
                
                comprehensive_report["performance_by_period"][f"{period}d"] = period_report
                comprehensive_report["benchmark_comparison"][f"{period}d"] = benchmark_comparison
                
                logger.info(f"{period}일간 성과 분석 완료")
            
            # 전체 요약 생성
            comprehensive_report["overall_summary"] = self._create_overall_summary(
                comprehensive_report["performance_by_period"]
            )
            
            # 리스크 분석
            comprehensive_report["risk_analysis"] = self._analyze_risk_trends(
                comprehensive_report["performance_by_period"]
            )
            
            # 종합 권장사항
            comprehensive_report["recommendations"] = self._generate_comprehensive_recommendations(
                comprehensive_report
            )
            
            logger.info("종합 성과 보고서 생성 완료")
            return comprehensive_report
            
        except Exception as e:
            logger.error(f"종합 성과 보고서 생성 실패: {e}")
            return {
                "error": str(e),
                "report_date": datetime.now()
            }
    
    def _create_overall_summary(self, performance_by_period: dict) -> dict:
        """전체 요약 생성"""
        try:
            # 30일 기준으로 요약 (가장 대표적인 기간)
            base_period = "30d"
            if base_period not in performance_by_period:
                base_period = list(performance_by_period.keys())[0]
            
            base_report = performance_by_period[base_period]
            metrics = base_report.get("performance_metrics", {})
            portfolio = base_report.get("portfolio_status", {})
            
            summary = {
                "current_value": portfolio.get("total_value_krw", 0),
                "primary_return": metrics.get("total_return", 0),
                "primary_sharpe": metrics.get("sharpe_ratio", 0),
                "primary_drawdown": metrics.get("max_drawdown", 0),
                "risk_level": base_report.get("risk_assessment", "medium"),
                "asset_allocation": portfolio.get("asset_allocation", {}),
                "performance_trend": self._determine_performance_trend(performance_by_period)
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"전체 요약 생성 실패: {e}")
            return {}
    
    def _analyze_risk_trends(self, performance_by_period: dict) -> dict:
        """리스크 트렌드 분석"""
        try:
            risk_analysis = {
                "volatility_trend": [],
                "drawdown_trend": [],
                "sharpe_trend": [],
                "risk_assessment": "stable"
            }
            
            periods = sorted(performance_by_period.keys())
            for period in periods:
                metrics = performance_by_period[period].get("performance_metrics", {})
                
                risk_analysis["volatility_trend"].append({
                    "period": period,
                    "volatility": metrics.get("volatility", 0)
                })
                
                risk_analysis["drawdown_trend"].append({
                    "period": period,
                    "max_drawdown": metrics.get("max_drawdown", 0)
                })
                
                risk_analysis["sharpe_trend"].append({
                    "period": period,
                    "sharpe_ratio": metrics.get("sharpe_ratio", 0)
                })
            
            # 리스크 상태 판단
            latest_metrics = performance_by_period[periods[-1]].get("performance_metrics", {})
            if latest_metrics.get("volatility", 0) > 0.3:
                risk_analysis["risk_assessment"] = "high"
            elif latest_metrics.get("max_drawdown", 0) < -0.15:
                risk_analysis["risk_assessment"] = "high"
            elif latest_metrics.get("sharpe_ratio", 0) < 0:
                risk_analysis["risk_assessment"] = "deteriorating"
            else:
                risk_analysis["risk_assessment"] = "stable"
            
            return risk_analysis
            
        except Exception as e:
            logger.error(f"리스크 트렌드 분석 실패: {e}")
            return {}
    
    def _determine_performance_trend(self, performance_by_period: dict) -> str:
        """성과 트렌드 판단"""
        try:
            periods = sorted(performance_by_period.keys())
            returns = []
            
            for period in periods:
                metrics = performance_by_period[period].get("performance_metrics", {})
                returns.append(metrics.get("total_return", 0))
            
            if len(returns) < 2:
                return "insufficient_data"
            
            # 단기 vs 장기 수익률 비교
            short_term = returns[0] if len(returns) > 0 else 0  # 가장 짧은 기간
            long_term = returns[-1] if len(returns) > 1 else 0  # 가장 긴 기간
            
            if short_term > long_term + 0.02:  # 2%포인트 차이
                return "improving"
            elif long_term > short_term + 0.02:
                return "deteriorating"
            else:
                return "stable"
                
        except Exception:
            return "unknown"
    
    def _generate_comprehensive_recommendations(self, comprehensive_report: dict) -> list:
        """종합 권장사항 생성"""
        recommendations = []
        
        try:
            overall_summary = comprehensive_report.get("overall_summary", {})
            risk_analysis = comprehensive_report.get("risk_analysis", {})
            
            # 성과 기반 권장사항
            primary_return = overall_summary.get("primary_return", 0)
            if primary_return < -0.05:
                recommendations.append({
                    "type": "performance",
                    "priority": "high",
                    "message": "포트폴리오 손실이 지속되고 있습니다. 전략 재검토가 필요합니다."
                })
            
            # 리스크 기반 권장사항
            risk_assessment = risk_analysis.get("risk_assessment", "stable")
            if risk_assessment == "high":
                recommendations.append({
                    "type": "risk",
                    "priority": "high",
                    "message": "리스크 수준이 높습니다. 안전자산 비중 확대를 고려하세요."
                })
            
            # 트렌드 기반 권장사항
            performance_trend = overall_summary.get("performance_trend", "stable")
            if performance_trend == "deteriorating":
                recommendations.append({
                    "type": "trend",
                    "priority": "medium",
                    "message": "성과가 악화되는 추세입니다. 포트폴리오 점검이 필요합니다."
                })
            
            # 기본 권장사항
            if not recommendations:
                recommendations.append({
                    "type": "general",
                    "priority": "low",
                    "message": "포트폴리오가 안정적으로 운용되고 있습니다."
                })
            
            return recommendations
            
        except Exception as e:
            logger.error(f"종합 권장사항 생성 실패: {e}")
            return []
    
    def send_performance_alerts(self, comprehensive_report: dict):
        """성과 보고서 알림 발송"""
        try:
            overall_summary = comprehensive_report.get("overall_summary", {})
            
            # 성과 알림 데이터 준비
            performance_data = {
                "period_days": 30,  # 기본 30일
                "total_return": overall_summary.get("primary_return", 0),
                "benchmark_return": 0.05,  # 임시값
                "sharpe_ratio": overall_summary.get("primary_sharpe", 0),
                "max_drawdown": overall_summary.get("primary_drawdown", 0)
            }
            
            # 성과 알림 발송
            self.alert_system.send_performance_alert(performance_data)
            
            logger.info("성과 보고서 알림 발송 완료")
            
        except Exception as e:
            logger.error(f"성과 보고서 알림 발송 실패: {e}")
    
    def save_report_to_file(self, report: dict, output_path: str = None):
        """보고서를 파일로 저장"""
        try:
            if output_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"./reports/performance_report_{timestamp}.json"
            
            # 디렉토리 생성
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            # JSON 형태로 저장
            import json
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2, default=str)
            
            logger.info(f"성과 보고서 파일 저장 완료: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"보고서 파일 저장 실패: {e}")
            return None


def main():
    """메인 실행 함수"""
    parser = argparse.ArgumentParser(description="KAIROS-1 성과 분석 보고서 생성")
    parser.add_argument("--periods", nargs="+", type=int, default=[7, 30, 90],
                        help="분석 기간 (일) 리스트")
    parser.add_argument("--output", type=str, help="출력 파일 경로")
    parser.add_argument("--send-alert", action="store_true", help="알림 발송 여부")
    
    args = parser.parse_args()
    
    try:
        # 설정 파일 경로 확인
        config_path = os.environ.get("KAIROS_CONFIG", "config/config.yaml")
        
        if not os.path.exists(config_path):
            print(f"❌ 설정 파일을 찾을 수 없습니다: {config_path}")
            sys.exit(1)
        
        # 성과 보고서 생성기 실행
        generator = PerformanceReportGenerator(config_path)
        report = generator.generate_comprehensive_report(args.periods)
        
        # 결과 확인
        if "error" in report:
            print("❌ 성과 보고서 생성 실패")
            print(f"오류: {report['error']}")
            sys.exit(1)
        
        # 보고서 저장
        if args.output:
            generator.save_report_to_file(report, args.output)
        else:
            output_file = generator.save_report_to_file(report)
            print(f"📄 보고서 저장: {output_file}")
        
        # 알림 발송 (기본적으로 항상 발송)
        if args.send_alert or True:  # 항상 알림 발송
            generator.send_performance_alerts(report)
            print("📧 성과 알림 발송 완료")
        
        # 결과 요약 출력
        overall_summary = report.get("overall_summary", {})
        print("✅ 성과 보고서 생성 완료")
        print(f"📊 현재 포트폴리오 가치: {overall_summary.get('current_value', 0):,.0f} KRW")
        print(f"📈 주요 수익률: {overall_summary.get('primary_return', 0):+.2%}")
        print(f"🎯 샤프 비율: {overall_summary.get('primary_sharpe', 0):.2f}")
        print(f"⚠️ 리스크 수준: {overall_summary.get('risk_level', 'unknown')}")
        
    except KeyboardInterrupt:
        print("\n⏹️ 사용자에 의해 중단되었습니다.")
        sys.exit(0)
    except Exception as e:
        print(f"❌ 예기치 못한 오류: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 