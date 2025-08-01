#!/usr/bin/env python3
"""
KAIROS-1 분기별 리밸런싱 스크립트

분기별로 실행되어 포트폴리오를 목표 비중에 맞게 리밸런싱합니다.
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import json
from loguru import logger

# 프로젝트 루트 디렉토리를 PYTHONPATH에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.market_season_filter import MarketSeasonFilter, MarketSeason
from src.core.portfolio_manager import PortfolioManager, AssetAllocation
from src.core.rebalancer import Rebalancer
from src.trading.coinone_client import CoinoneClient
from src.trading.order_manager import OrderManager
from src.monitoring.alert_system import AlertSystem
from src.risk.risk_manager import RiskManager
from src.utils.config_loader import ConfigLoader
from src.utils.database_manager import DatabaseManager


class QuarterlyRebalancer:
    """분기별 리밸런싱 실행기"""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """
        Args:
            config_path: 설정 파일 경로
        """
        self.config = ConfigLoader(config_path)
        
        # 로깅 설정
        self._setup_logging()
        
        # 컴포넌트 초기화
        self._initialize_components()
        
        logger.info("QuarterlyRebalancer 초기화 완료")
    
    def _setup_logging(self):
        """로깅 설정"""
        log_level = self.config.get("logging.level", "INFO")
        log_file = self.config.get("logging.file_path", "./logs/quarterly_rebalance.log")
        
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
    
    def _initialize_components(self):
        """핵심 컴포넌트 초기화"""
        try:
            # 코인원 클라이언트
            api_config = self.config.get("api.coinone")
            self.coinone_client = CoinoneClient(
                api_key=api_config["api_key"],
                secret_key=api_config["secret_key"],
                sandbox=api_config.get("sandbox", True)
            )
            
            # 시장 계절 필터
            market_config = self.config.get("strategy.market_season")
            self.market_filter = MarketSeasonFilter(
                buffer_band=market_config.get("buffer_band", 0.05)
            )
            
            # 포트폴리오 관리자
            portfolio_config = self.config.get("strategy.portfolio")
            asset_allocation = AssetAllocation(
                btc_weight=portfolio_config["core"]["BTC"],
                eth_weight=portfolio_config["core"]["ETH"],
                xrp_weight=portfolio_config["satellite"]["XRP"],
                sol_weight=portfolio_config["satellite"]["SOL"]
            )
            self.portfolio_manager = PortfolioManager(asset_allocation)
            
            # 주문 관리자
            self.order_manager = OrderManager(self.coinone_client)
            
            # 리밸런서
            self.rebalancer = Rebalancer(
                coinone_client=self.coinone_client,
                portfolio_manager=self.portfolio_manager,
                market_season_filter=self.market_filter,
                order_manager=self.order_manager
            )
            
            # 리스크 관리자
            self.risk_manager = RiskManager(self.config)
            
            # 알림 시스템
            self.alert_system = AlertSystem(self.config)
            
            # 데이터베이스 관리자
            self.db_manager = DatabaseManager(self.config)
            
            logger.info("모든 컴포넌트 초기화 완료")
            
        except Exception as e:
            logger.error(f"컴포넌트 초기화 실패: {e}")
            raise
    
    def get_current_market_season(self) -> MarketSeason:
        """
        현재 시장 계절 조회
        
        Returns:
            현재 시장 계절
        """
        try:
            # 최근 시장 분석 결과 조회
            latest_analysis = self.db_manager.get_latest_market_analysis()
            
            if latest_analysis and latest_analysis.get("success"):
                season_str = latest_analysis.get("market_season", "neutral")
                
                # 문자열을 MarketSeason enum으로 변환
                season_map = {
                    "risk_on": MarketSeason.RISK_ON,
                    "risk_off": MarketSeason.RISK_OFF,
                    "neutral": MarketSeason.NEUTRAL
                }
                
                season = season_map.get(season_str, MarketSeason.NEUTRAL)
                logger.info(f"최근 시장 분석 결과 사용: {season.value}")
                return season
            else:
                logger.warning("최근 시장 분석 결과 없음 - 중립 상태로 설정")
                return MarketSeason.NEUTRAL
                
        except Exception as e:
            logger.error(f"시장 계절 조회 실패: {e} - 중립 상태로 설정")
            return MarketSeason.NEUTRAL
    
    def pre_rebalance_checks(self) -> bool:
        """
        리밸런싱 전 사전 검사
        
        Returns:
            검사 통과 여부
        """
        try:
            logger.info("리밸런싱 사전 검사 시작")
            
            # 1. API 연결 상태 확인
            account_info = self.coinone_client.get_account_info()
            if not account_info:
                logger.error("코인원 API 연결 실패")
                return False
            
            # 2. 포트폴리오 상태 확인
            portfolio = self.coinone_client.get_portfolio_value()
            total_value = portfolio.get("total_krw", 0)
            
            if total_value <= 0:
                logger.error("포트폴리오 총 가치가 0 이하")
                return False
            
            # 3. 리스크 체크
            risk_check = self.risk_manager.pre_trade_risk_check(portfolio)
            if not risk_check.get("approved", False):
                logger.error(f"리스크 체크 실패: {risk_check.get('reason')}")
                return False
            
            # 4. 시장 시간 확인 (필요시)
            # 암호화폐는 24/7 거래이므로 생략
            
            logger.info("리밸런싱 사전 검사 통과")
            return True
            
        except Exception as e:
            logger.error(f"리밸런싱 사전 검사 실패: {e}")
            return False
    
    def execute_rebalancing(self, dry_run: bool = False) -> dict:
        """
        분기별 리밸런싱 실행
        
        Args:
            dry_run: 실제 거래 없이 시뮬레이션만 실행
            
        Returns:
            리밸런싱 결과
        """
        try:
            logger.info("=== KAIROS-1 분기별 리밸런싱 시작 ===")
            
            if dry_run:
                logger.info("🔍 DRY RUN 모드 - 실제 거래 없음")
            
            # 1. 사전 검사
            if not self.pre_rebalance_checks():
                raise RuntimeError("리밸런싱 사전 검사 실패")
            
            # 2. 현재 시장 계절 확인
            current_season = self.get_current_market_season()
            logger.info(f"현재 시장 계절: {current_season.value}")
            
            # 3. 현재 포트폴리오 상태 조회
            current_portfolio = self.coinone_client.get_portfolio_value()
            logger.info(f"현재 포트폴리오 가치: {current_portfolio['total_krw']:,.0f} KRW")
            
            # 4. 목표 자산 배분 계산
            allocation_weights = self.market_filter.get_allocation_weights(current_season)
            target_weights = self.portfolio_manager.calculate_target_weights(
                allocation_weights["crypto"],
                allocation_weights["krw"]
            )
            
            # 5. 리밸런싱 필요 여부 확인
            rebalance_needed = self.rebalancer.check_rebalance_needed(
                current_portfolio, target_weights
            )
            
            if not rebalance_needed:
                logger.info("리밸런싱 불필요 - 모든 자산이 목표 비중 내")
                return {
                    "success": True,
                    "rebalance_needed": False,
                    "message": "리밸런싱 불필요",
                    "timestamp": datetime.now()
                }
            
            # 6. 리밸런싱 실행
            if not dry_run:
                rebalance_result = self.rebalancer.execute_quarterly_rebalance(current_season)
            else:
                # Dry run - 실제 거래 없이 계산만
                rebalance_info = self.portfolio_manager.calculate_rebalance_amounts(
                    current_portfolio, target_weights
                )
                rebalance_result = {
                    "success": True,
                    "dry_run": True,
                    "rebalance_info": rebalance_info,
                    "target_weights": target_weights,
                    "current_season": current_season.value
                }
            
            # 7. 결과 저장
            self.save_rebalance_result(rebalance_result)
            
            # 8. 알림 발송
            self.send_rebalance_notification(rebalance_result)
            
            logger.info("분기별 리밸런싱 완료")
            return rebalance_result
            
        except Exception as e:
            logger.error(f"분기별 리밸런싱 실패: {e}")
            
            # 오류 알림 발송
            self.alert_system.send_error_alert(
                title="분기별 리밸런싱 실패",
                message=f"오류 내용: {str(e)}",
                error_type="quarterly_rebalance_failure"
            )
            
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now()
            }
    
    def save_rebalance_result(self, result: dict):
        """
        리밸런싱 결과 저장
        
        Args:
            result: 리밸런싱 결과
        """
        try:
            self.db_manager.save_rebalance_result(result)
            logger.info("리밸런싱 결과 저장 완료")
            
        except Exception as e:
            logger.error(f"리밸런싱 결과 저장 실패: {e}")
    
    def send_rebalance_notification(self, result: dict):
        """
        리밸런싱 알림 발송
        
        Args:
            result: 리밸런싱 결과
        """
        try:
            if not result.get("success"):
                return
            
            if not result.get("rebalance_needed", True):
                # 리밸런싱이 불필요한 경우
                message = """
📊 **KAIROS-1 분기별 리밸런싱 결과**

✅ **결과**: 리밸런싱 불필요
📅 **실행 시간**: {timestamp}

💡 **사유**: 모든 자산이 목표 비중 범위 내에 있어 조정이 불필요합니다.
                """.format(timestamp=datetime.now().strftime('%Y-%m-%d %H:%M'))
            else:
                # 실제 리밸런싱 실행된 경우
                summary = result.get("rebalance_summary", {})
                executed_orders = len(result.get("executed_orders", []))
                failed_orders = len(result.get("failed_orders", []))
                
                message = f"""
📊 **KAIROS-1 분기별 리밸런싱 결과**

✅ **결과**: {'성공' if result.get('success') else '부분 실패'}
📅 **실행 시간**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
🎯 **시장 계절**: {summary.get('market_season', 'N/A').upper()}

📈 **거래 실행**:
• 성공한 주문: {executed_orders}개
• 실패한 주문: {failed_orders}개

💰 **포트폴리오 가치**:
• 리밸런싱 전: {result.get('total_value_before', 0):,.0f} KRW
• 리밸런싱 후: {result.get('total_value_after', 0):,.0f} KRW
• 변화: {summary.get('value_change', 0):+,.0f} KRW
                """
            
            self.alert_system.send_info_alert(
                title="분기별 리밸런싱 완료",
                message=message.strip(),
                alert_type="quarterly_rebalance"
            )
            
            logger.info("리밸런싱 알림 발송 완료")
            
        except Exception as e:
            logger.error(f"리밸런싱 알림 발송 실패: {e}")


def main():
    """메인 실행 함수"""
    try:
        # 명령행 인수 처리
        dry_run = "--dry-run" in sys.argv or "-d" in sys.argv
        
        # 설정 파일 경로 확인
        config_path = os.environ.get("KAIROS_CONFIG", "config/config.yaml")
        
        if not os.path.exists(config_path):
            print(f"❌ 설정 파일을 찾을 수 없습니다: {config_path}")
            print("config/config.example.yaml을 복사하여 config/config.yaml을 생성하고 설정을 입력하세요.")
            sys.exit(1)
        
        # 분기별 리밸런서 실행
        rebalancer = QuarterlyRebalancer(config_path)
        result = rebalancer.execute_rebalancing(dry_run=dry_run)
        
        # 결과 출력
        if result.get("success"):
            if result.get("rebalance_needed", True):
                print("✅ 분기별 리밸런싱 완료")
                if dry_run:
                    print("🔍 DRY RUN 모드로 실행됨")
                
                executed = len(result.get("executed_orders", []))
                failed = len(result.get("failed_orders", []))
                print(f"📊 거래 결과: 성공 {executed}개, 실패 {failed}개")
            else:
                print("✅ 리밸런싱 불필요 - 모든 자산이 목표 비중 내")
        else:
            print("❌ 분기별 리밸런싱 실패")
            print(f"오류: {result.get('error', 'Unknown error')}")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⏹️ 사용자에 의해 중단되었습니다.")
        sys.exit(0)
    except Exception as e:
        print(f"❌ 예기치 못한 오류: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 