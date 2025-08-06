#!/usr/bin/env python3
"""
KAIROS-1: 장기 투자 시스템 메인 실행 파일

코인원 거래소 맞춤형 자동 투자 시스템의 중앙 컨트롤러입니다.
"""

import sys
import os
import argparse
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
import signal
from typing import Optional
from loguru import logger

# 프로젝트 모듈 임포트
from src.core.market_season_filter import MarketSeasonFilter, MarketSeason
from src.core.portfolio_manager import PortfolioManager, AssetAllocation
from src.core.rebalancer import Rebalancer
from src.core.dynamic_execution_engine import DynamicExecutionEngine

# 새로운 고급 시스템 임포트
from src.core.multi_timeframe_analyzer import MultiTimeframeAnalyzer
from src.core.adaptive_portfolio_manager import AdaptivePortfolioManager
from src.core.dca_plus_strategy import DCAPlus
from src.core.risk_parity_model import RiskParityModel
from src.core.tax_optimization_system import TaxOptimizationSystem
from src.core.macro_economic_analyzer import MacroEconomicAnalyzer
from src.core.onchain_data_analyzer import OnchainDataAnalyzer
from src.core.scenario_response_system import ScenarioResponseSystem
from src.core.behavioral_bias_prevention import BehavioralBiasPrevention
from src.core.advanced_performance_analytics import AdvancedPerformanceAnalytics

from src.trading.coinone_client import CoinoneClient
from src.trading.order_manager import OrderManager
from src.risk.risk_manager import RiskManager
from src.monitoring.alert_system import AlertSystem
from src.monitoring.performance_tracker import PerformanceTracker
from src.utils.config_loader import ConfigLoader, REQUIRED_CONFIG_KEYS
from src.utils.database_manager import DatabaseManager
from src.utils.market_data_provider import MarketDataProvider
from src.core.multi_account_manager import MultiAccountManager


class KairosSystem:
    """
    KAIROS-1 시스템 메인 클래스
    
    전체 시스템을 초기화하고 관리하는 중앙 컨트롤러입니다.
    """
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """
        Args:
            config_path: 설정 파일 경로
        """
        self.config_path = config_path
        self.running = False
        self.components_initialized = False
        
        # 시스템 컴포넌트들
        self.config = None
        self.db_manager = None
        self.coinone_client = None
        self.market_filter = None
        self.portfolio_manager = None
        self.order_manager = None
        self.rebalancer = None
        self.risk_manager = None
        self.alert_system = None
        self.performance_tracker = None
        self.execution_engine = None
        
        # 고급 시스템 컴포넌트들
        self.multi_timeframe_analyzer = None
        self.adaptive_portfolio_manager = None
        self.dca_plus_strategy = None
        self.risk_parity_model = None
        self.tax_optimization_system = None
        self.macro_economic_analyzer = None
        self.onchain_data_analyzer = None
        self.scenario_response_system = None
        self.bias_prevention_system = None
        self.advanced_performance_analytics = None
        
        # 시그널 핸들러 설정
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("KAIROS-1 시스템 초기화 시작")
    
    def initialize(self) -> bool:
        """
        시스템 초기화
        
        Returns:
            초기화 성공 여부
        """
        try:
            logger.info("=== KAIROS-1 시스템 초기화 ===")
            
            # 1. 설정 파일 로드
            if not self._load_configuration():
                return False
            
            # 2. 로깅 설정
            self._setup_logging()
            
            # 3. 핵심 컴포넌트 초기화
            if not self._initialize_components():
                return False
            
            # 4. 시스템 상태 체크
            if not self._perform_system_checks():
                return False
            
            self.components_initialized = True
            logger.info("✅ KAIROS-1 시스템 초기화 완료")
            
            return True
            
        except Exception as e:
            logger.error(f"시스템 초기화 실패: {e}")
            return False
    
    def _load_configuration(self) -> bool:
        """설정 파일 로드"""
        try:
            if not os.path.exists(self.config_path):
                logger.error(f"설정 파일을 찾을 수 없습니다: {self.config_path}")
                print("config/config.example.yaml을 복사하여 config/config.yaml을 생성하고 설정을 입력하세요.")
                return False
            
            self.config = ConfigLoader(self.config_path)
            
            # 멀티 계정 관리자가 있는지 먼저 확인
            multi_account_manager = MultiAccountManager()
            has_multi_accounts = False
            try:
                import asyncio
                asyncio.run(multi_account_manager.initialize())
                has_multi_accounts = bool(multi_account_manager.accounts)
                logger.info(f"멀티 계정 관리자 사전 확인: {len(multi_account_manager.accounts) if has_multi_accounts else 0}개 계정")
            except Exception as e:
                logger.debug(f"멀티 계정 관리자 사전 확인 실패: {e}")
            
            # 필수 설정 검증 (멀티 계정이 있으면 API 키 검증 스킵)
            required_keys = REQUIRED_CONFIG_KEYS.copy()
            if has_multi_accounts:
                # 멀티 계정이 있으면 API 키 관련 필수 검증 제거
                required_keys = [key for key in required_keys if not key.startswith("api.coinone")]
                logger.info("멀티 계정 관리자 사용으로 인해 API 키 검증 스킵")
            
            if not self.config.validate_required_config(required_keys):
                logger.error("필수 설정 값이 누락되었습니다.")
                return False
            
            logger.info("설정 파일 로드 완료")
            return True
            
        except Exception as e:
            logger.error(f"설정 파일 로드 실패: {e}")
            return False
    
    def _setup_logging(self):
        """로깅 시스템 설정"""
        try:
            log_level = self.config.get("logging.level", "INFO")
            log_file = self.config.get("logging.file_path", "./logs/kairos1_main.log")
            
            # 로그 디렉토리 생성
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            
            # 기본 핸들러 제거
            logger.remove()
            
            # 파일 로깅 설정
            logger.add(
                log_file,
                level=log_level,
                rotation=self.config.get("logging.rotation", "100 MB"),
                retention=self.config.get("logging.retention", "30 days"),
                format=self.config.get("logging.format", 
                    "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}")
            )
            
            # 콘솔 로깅 설정
            logger.add(sys.stdout, level=log_level)
            
            logger.info("로깅 시스템 설정 완료")
            
        except Exception as e:
            print(f"로깅 설정 실패: {e}")
    
    def _initialize_components(self) -> bool:
        """핵심 컴포넌트 초기화"""
        try:
            logger.info("핵심 컴포넌트 초기화 시작")
            
            # 데이터베이스 관리자
            self.db_manager = DatabaseManager(self.config)
            
            # 멀티 계정 관리자 초기화
            self.multi_account_manager = MultiAccountManager()
            
            # 멀티 계정 관리자에서만 계정 가져오기
            try:
                import asyncio
                # 멀티 계정 관리자 초기화
                asyncio.run(self.multi_account_manager.initialize())
                
                if self.multi_account_manager.accounts:
                    # 멀티 계정이 있으면 첫 번째 계정 사용 (또는 primary 계정)
                    primary_account_id = "main"  # 우선 main 계정 찾기
                    if primary_account_id not in self.multi_account_manager.accounts:
                        # main 계정이 없으면 첫 번째 계정 사용
                        primary_account_id = list(self.multi_account_manager.accounts.keys())[0]
                    
                    if primary_account_id in self.multi_account_manager.clients:
                        self.coinone_client = self.multi_account_manager.clients[primary_account_id]
                        logger.info(f"멀티 계정 관리자 사용: {primary_account_id} 계정")
                    else:
                        raise ValueError(f"계정 {primary_account_id}의 클라이언트 초기화 실패")
                else:
                    raise ValueError("등록된 계정이 없습니다. --setup-multi-account 명령으로 계정을 먼저 등록하세요.")
                    
            except Exception as e:
                logger.error(f"멀티 계정 관리자 초기화 실패: {e}")
                raise ValueError("멀티 계정 관리자 초기화에 실패했습니다. --setup-multi-account 명령으로 계정을 등록하세요.")
            
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
            
            # 시장 데이터 제공자
            self.market_data_provider = MarketDataProvider()
            
            # 리밸런서
            self.rebalancer = Rebalancer(
                coinone_client=self.coinone_client,
                db_manager=self.db_manager,
                portfolio_manager=self.portfolio_manager,
                market_season_filter=self.market_filter,
                order_manager=self.order_manager
            )
            
            # 리스크 관리자
            self.risk_manager = RiskManager(self.config)
            
            # 알림 시스템
            self.alert_system = AlertSystem(self.config)
            
            # 성과 추적기
            self.performance_tracker = PerformanceTracker(self.config, self.db_manager)
            
            # 동적 실행 엔진
            self.execution_engine = DynamicExecutionEngine(
                coinone_client=self.coinone_client,
                db_manager=self.db_manager,
                rebalancer=self.rebalancer,  # Add rebalancer instance
                alert_system=self.alert_system
            )
            
            # 고급 시스템 컴포넌트 초기화
            self._initialize_advanced_systems()
            
            logger.info("모든 컴포넌트 초기화 완료")
            return True
            
        except Exception as e:
            logger.error(f"컴포넌트 초기화 실패: {e}")
            return False
    
    def _initialize_advanced_systems(self):
        """고급 시스템 컴포넌트 초기화"""
        try:
            logger.info("고급 시스템 컴포넌트 초기화 시작")
            
            # 멀티 타임프레임 분석기
            if self.config.get("risk_management.multi_timeframe.enabled", True):
                self.multi_timeframe_analyzer = MultiTimeframeAnalyzer(
                    market_season_filter=self.market_filter
                )
                logger.info("✅ 멀티 타임프레임 분석기 초기화")
            
            # 적응형 포트폴리오 관리자
            if self.config.get("risk_management.adaptive_portfolio.enabled", True):
                self.adaptive_portfolio_manager = AdaptivePortfolioManager(
                    base_portfolio_manager=self.portfolio_manager
                )
                logger.info("✅ 적응형 포트폴리오 관리자 초기화")
            
            # DCA+ 전략
            if self.config.get("risk_management.dca_plus.enabled", True):
                self.dca_plus_strategy = DCAPlus(
                    market_data_provider=self.market_data_provider
                )
                logger.info("✅ DCA+ 전략 초기화")
            
            # 리스크 패리티 모델
            if self.config.get("risk_management.risk_parity.enabled", True):
                self.risk_parity_model = RiskParityModel()
                logger.info("✅ 리스크 패리티 모델 초기화")
            
            # 세금 최적화 시스템
            if self.config.get("risk_management.tax_optimization.enabled", True):
                self.tax_optimization_system = TaxOptimizationSystem()
                logger.info("✅ 세금 최적화 시스템 초기화")
            
            # 매크로 경제 분석기
            if self.config.get("risk_management.macro_economic.enabled", True):
                macro_api_keys = self.config.get("risk_management.macro_economic.api_keys", {})
                self.macro_economic_analyzer = MacroEconomicAnalyzer(api_keys=macro_api_keys)
                logger.info("✅ 매크로 경제 분석기 초기화")
            
            # 온체인 데이터 분석기
            if self.config.get("risk_management.onchain_analysis.enabled", True):
                onchain_api_keys = self.config.get("risk_management.onchain_analysis.api_keys", {})
                self.onchain_data_analyzer = OnchainDataAnalyzer(api_keys=onchain_api_keys)
                logger.info("✅ 온체인 데이터 분석기 초기화")
            
            # 시나리오 대응 시스템
            if self.config.get("risk_management.scenario_response.enabled", True):
                self.scenario_response_system = ScenarioResponseSystem()
                logger.info("✅ 시나리오 대응 시스템 초기화")
            
            # 심리적 편향 방지 시스템
            if self.config.get("risk_management.bias_prevention.enabled", True):
                self.bias_prevention_system = BehavioralBiasPrevention()
                logger.info("✅ 심리적 편향 방지 시스템 초기화")
            
            # 고급 성과 분석기
            if self.config.get("risk_management.performance_analytics.enabled", True):
                self.advanced_performance_analytics = AdvancedPerformanceAnalytics()
                logger.info("✅ 고급 성과 분석기 초기화")
            
            logger.info("고급 시스템 컴포넌트 초기화 완료")
            
        except Exception as e:
            logger.error(f"고급 시스템 컴포넌트 초기화 실패: {e}")
            # 고급 시스템 초기화 실패는 기본 시스템 동작을 중단시키지 않음
            logger.warning("기본 시스템은 고급 기능 없이 계속 동작합니다")
    
    def _perform_system_checks(self) -> bool:
        """시스템 상태 체크"""
        try:
            logger.info("시스템 상태 체크 시작")
            
            # 1. API 연결 체크
            try:
                account_info = self.coinone_client.get_account_info()
                if not account_info:
                    logger.error("코인원 API 연결 실패")
                    return False
                logger.info("✅ 코인원 API 연결 정상")
            except Exception as e:
                logger.error(f"API 연결 체크 실패: {e}")
                return False
            
            # 2. 데이터베이스 체크
            try:
                # 간단한 쿼리로 데이터베이스 연결 확인
                self.db_manager.get_latest_market_analysis()
                logger.info("✅ 데이터베이스 연결 정상")
            except Exception as e:
                logger.error(f"데이터베이스 연결 실패: {e}")
                logger.error("데이터베이스 없이는 시스템이 정상 작동하지 않을 수 있습니다.")
                logger.info("해결 방법:")
                logger.info("  1. 데이터베이스 서비스가 실행 중인지 확인")
                logger.info("  2. 데이터베이스 URL 및 자격 증명 확인")
                logger.info("  3. 네트워크 연결 상태 확인")
                
                # 중요한 기능들은 데이터베이스가 필요하므로 초기화 실패로 처리
                if not self.config.get("development.ignore_db_errors", False):
                    logger.error("데이터베이스 연결 실패로 시스템 초기화를 중단합니다.")
                    return False
                else:
                    logger.warning("개발 모드: 데이터베이스 오류 무시하고 계속 진행")
            
            # 3. 포트폴리오 상태 체크
            try:
                portfolio = self.coinone_client.get_portfolio_value()
                total_value = portfolio.get("total_krw", 0)
                if total_value <= 0:
                    logger.warning("포트폴리오 총 가치가 0입니다.")
                else:
                    logger.info(f"✅ 포트폴리오 가치: {total_value:,.0f} KRW")
            except Exception as e:
                logger.error(f"포트폴리오 상태 체크 실패: {e}")
                return False
            
            # 4. 알림 시스템 체크 (선택적)
            if self.config.get("notifications.slack.enabled") or self.config.get("notifications.email.enabled"):
                try:
                    # 테스트 알림은 수동으로만 발송
                    logger.info("✅ 알림 시스템 준비 완료")
                except Exception as e:
                    logger.warning(f"알림 시스템 체크 경고: {e}")
            
            logger.info("✅ 시스템 상태 체크 완료")
            return True
            
        except Exception as e:
            logger.error(f"시스템 상태 체크 실패: {e}")
            return False
    

    
    def run_weekly_analysis(self, dry_run: bool = False) -> dict:
        """주간 시장 분석 실행. 시장 계절 변화 시 즉시 리밸런싱을 실행할 수 있습니다."""
        try:
            logger.info(f"주간 시장 분석 실행 {'(DRY RUN)' if dry_run else ''}")
            
            # BTC 가격 데이터 수집 (실제로는 외부 API에서)
            import yfinance as yf
            btc_ticker = yf.Ticker("BTC-USD")
            price_data = btc_ticker.history(period="3y")
            
            # 시장 분석 실행
            analysis_result = self.market_filter.analyze_weekly(price_data)
            
            if analysis_result.get("success"):
                # 데이터베이스에 저장
                self.db_manager.save_market_analysis(analysis_result)
                
                # 시장 계절 변화 시 알림 및 즉시 리밸런싱
                if analysis_result.get("season_changed"):
                    logger.info("시장 계절 변화 감지! 전략적 자산 재배치를 시작합니다.")
                    self._send_season_change_notification(analysis_result, immediate_rebalance=True)
                    
                    # TWAP 리밸런싱 실행
                    rebalance_result = self.run_quarterly_rebalance_twap(dry_run=dry_run)
                    analysis_result["rebalance_triggered"] = True
                    analysis_result["rebalance_result"] = rebalance_result
                    
                    # 리밸런싱 시작 후 추가 알림
                    if rebalance_result.get("success"):
                        self._send_immediate_rebalance_notification(analysis_result, rebalance_result)
                    
                else:
                    logger.info("시장 계절에 변화가 없습니다. 기존 전략을 유지합니다.")
                
                logger.info("주간 시장 분석 완료")
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"주간 시장 분석 실패: {e}")
            return {"success": False, "error": str(e)}
    
    def run_quarterly_rebalance(self, dry_run: bool = False, use_twap: bool = False) -> dict:
        """분기별 리밸런싱 실행"""
        try:
            logger.info(f"분기별 리밸런싱 실행 {'(DRY RUN)' if dry_run else ''} {'(TWAP)' if use_twap else ''}")
            
            if use_twap:
                # TWAP 실행 방식
                return self.run_quarterly_rebalance_twap(dry_run)
            else:
                # 기존 즉시 실행 방식
                result = self.rebalancer.execute_quarterly_rebalance()
                
                if result.success:
                    # 결과 저장
                    self.db_manager.save_rebalance_result(result.to_dict())
                    
                    # 결과 알림
                    self._send_rebalance_notification(result)
                    
                    logger.info("분기별 리밸런싱 완료")
                
                return result.to_dict()
            
        except Exception as e:
            logger.error(f"분기별 리밸런싱 실패: {e}")
            return {"success": False, "error": str(e)}
    
    def run_quarterly_rebalance_twap(self, dry_run: bool = False) -> dict:
        """TWAP 방식 분기별 리밸런싱 실행"""
        try:
            logger.info(f"TWAP 분기별 리밸런싱 실행 {'(DRY RUN)' if dry_run else ''}")
            
            # 1. 리밸런싱 계획 수립 (실제 주문은 하지 않음)
            rebalance_plan = self.rebalancer.calculate_rebalancing_orders()
            
            if not rebalance_plan.get("success"):
                return rebalance_plan
            
            # 2. 현재 시장 계절과 목표 배분 정보 수집
            market_season = rebalance_plan.get("market_season", "neutral")
            target_weights = rebalance_plan.get("target_weights", {})
            
            # target_weights를 allocation 형태로 변환
            target_allocation = {}
            if target_weights:
                crypto_total = sum(weight for asset, weight in target_weights.items() 
                                 if asset not in ["KRW"])
                krw_weight = target_weights.get("KRW", 0.3)
                
                target_allocation = {
                    "crypto": crypto_total,
                    "krw": krw_weight
                }
                # 개별 자산 비중도 추가
                target_allocation.update(target_weights)
            
            # 3. TWAP 실행 시작 (시장 정보 포함)
            rebalance_orders = rebalance_plan.get("rebalance_orders", {})
            execution_result = self.execution_engine.start_twap_execution(
                rebalance_orders, 
                market_season=market_season, 
                target_allocation=target_allocation
            )
            
            if execution_result.get("success"):
                # 4. TWAP 실행 계획 알림
                self._send_twap_start_notification(execution_result)
                logger.info("TWAP 분기별 리밸런싱 시작 완료")
            
            return execution_result
            
        except Exception as e:
            logger.error(f"TWAP 분기별 리밸런싱 실패: {e}")
            return {"success": False, "error": str(e)}
    
    def process_twap_orders(self) -> dict:
        """TWAP 주문 처리"""
        try:
            logger.info("TWAP 주문 처리 시작")
            
            # 모든 주문 처리 로직은 DynamicExecutionEngine에 위임
            # check_market_conditions=False로 설정하여 순수하게 주문 실행만 담당
            result = self.execution_engine.process_pending_twap_orders(check_market_conditions=False)
            
            # TWAP 실행 결과가 있고 실제로 처리된 주문이 있을 때만 알림 발송
            if result.get("success") and result.get("processed_orders", 0) > 0:
                self._send_twap_execution_notification(result)
            
            return result

        except Exception as e:
            logger.error(f"TWAP 주문 처리 중 오류: {e}")
            return {"success": False, "error": str(e)}
    
    def _is_next_slice_due(self, order) -> bool:
        """다음 슬라이스 실행 시간인지 확인"""
        if not order.last_execution_time:
            return False # 처음 실행된 주문은 다음 슬라이스가 없음
            
        next_execution_time = order.last_execution_time + timedelta(minutes=order.slice_interval_minutes)
        return datetime.now() >= next_execution_time
    
    def _send_twap_execution_notification(self, execution_result: dict):
        """TWAP 실행 결과 알림"""
        try:
            processed_count = execution_result.get("processed_orders", 0)
            completed_count = execution_result.get("completed_orders", 0)
            remaining_count = execution_result.get("remaining_orders", 0)
            details = execution_result.get("details", [])
            
            # 에러 발생 여부 확인
            has_errors = any(not detail.get("result", {}).get("success", False) for detail in details)
            
            if has_errors:
                status_emoji = "⚠️"
                status_text = "TWAP 주문 실행 (오류 발생)"
            else:
                status_emoji = "🔄"
                status_text = "TWAP 주문 실행 완료"
            
            message = f"""
{status_emoji} **{status_text}**

**실행 현황**:
• 이번에 처리된 주문: {processed_count}개
• 완료된 주문: {completed_count}개  
• 남은 주문: {remaining_count}개

**실행 내역**:
            """.strip()
            
            # 실행된 주문들의 상세 내역 추가
            error_details = []
            success_count = 0
            
            for detail in details:
                asset = detail.get("asset", "Unknown")
                executed_slices = detail.get("executed_slices", 0)
                total_slices = detail.get("total_slices", 0)
                result = detail.get("result", {})
                next_execution = detail.get("next_execution_time", "N/A")
                
                if result.get("success"):
                    if result.get("skipped"):
                        # 건너뛴 슬라이스 (최소량 미달로 다음과 합침)
                        progress = f"{executed_slices}/{total_slices}"
                        skip_message = result.get("message", "최소량 미달로 건너뜀")
                        
                        message += f"""
• **{asset}**: {progress} 슬라이스 건너뜀 ⏭️
  - 상태: {skip_message}
  - 다음 실행: {next_execution}"""
                        success_count += 1
                    else:
                        # 정상 실행된 슬라이스
                        amount_krw = result.get("amount_krw", 0)
                        order_id = result.get("order_id", "N/A")
                        progress = f"{executed_slices}/{total_slices}"
                        remaining_amount = result.get("remaining_amount", 0)
                        
                        message += f"""
• **{asset}**: {progress} 슬라이스 완료 ✅
  - 실행 금액: {amount_krw:,.0f} KRW
  - 주문 ID: {order_id}
  - 남은 금액: {remaining_amount:,.0f} KRW
  - 다음 실행: {next_execution}"""
                        success_count += 1
                else:
                    error = result.get("error", "Unknown error")
                    error_code = result.get("error_code", "unknown")
                    amount_krw = result.get("amount_krw", 0)
                    
                    message += f"""
• **{asset}**: {executed_slices}/{total_slices} 슬라이스 실행 실패 ❌
  - 시도 금액: {amount_krw:,.0f} KRW
  - 오류 코드: {error_code}
  - 오류 내용: {error}
  - 다음 실행: {next_execution}"""
                    
                    # 에러 상세 정보 수집
                    error_details.append({
                        "asset": asset,
                        "error_code": error_code,
                        "error": error,
                        "amount": amount_krw
                    })
            
            # 에러 발생 시 문제 해결 방안 추가
            if error_details:
                message += "\n\n🔧 **문제 해결 방안**:"
                
                for error_detail in error_details:
                    asset = error_detail["asset"]
                    error_code = error_detail["error_code"]
                    amount = error_detail["amount"]
                    
                    if error_code == "103":  # Lack of Balance
                        message += f"""
• **{asset} 잔액 부족 (103)**:
  - 현재 보유량을 확인하여 매도 가능한 수량인지 점검
  - 다른 주문이 진행 중인지 확인
  - 다음 실행 시 자동으로 조정된 수량으로 재시도"""
                        
                    elif error_code == "307":  # 최대 주문 금액 초과
                        message += f"""
• **{asset} 최대 주문 금액 초과 (307)**:
  - 한 번에 거래 가능한 최대 금액: {amount/2:,.0f} KRW (추정)
  - 다음 실행 시 자동으로 크기가 조정되어 재시도
  - 필요시 TWAP 분할 횟수를 늘려서 주문 크기 축소 고려"""
                        
                    elif error_code == "405":  # 최소 주문 금액 미달
                        message += f"""
• **{asset} 최소 주문 금액 미달 (405)**:
  - 코인원 최소 주문 금액 미달로 거래 불가
  - 남은 금액이 너무 적어 마지막 슬라이스 실행 어려움"""
                        
                    else:
                        message += f"""
• **{asset} 기타 오류 ({error_code})**:
  - 일시적 네트워크 문제 또는 거래소 시스템 이슈
  - 자동 재시도 후에도 지속될 경우 수동 확인 필요"""
                
                message += "\n\n💡 **자동 대응**: 시스템이 자동으로 주문 크기를 조정하고 재시도합니다."
            
            if remaining_count > 0:
                message += f"\n\n⏳ {remaining_count}개 주문이 계속 실행 중입니다."
            elif completed_count > 0:
                message += "\n\n🎉 모든 TWAP 주문이 완료되었습니다!"
            
            # 성공/실패 비율 표시
            if processed_count > 0:
                success_rate = (success_count / processed_count) * 100
                message += f"\n\n📊 **이번 실행 성공률**: {success_rate:.1f}% ({success_count}/{processed_count})"
            
            # 에러 발생 시 경고 레벨로, 정상 시 정보 레벨로 알림
            alert_type = "warning" if has_errors else "info"
            
            self.alert_system.send_alert(
                "TWAP 주문 실행 완료",
                message,
                alert_type
            )
            
        except Exception as e:
            logger.error(f"TWAP 실행 알림 실패: {e}")
    
    def get_twap_status(self) -> dict:
        """TWAP 주문 상태 상세 조회"""
        try:
            active_orders = self.execution_engine.active_twap_orders
            current_execution_id = self.execution_engine.current_execution_id
            
            if not active_orders:
                return {
                    "success": True,
                    "message": "활성 TWAP 주문이 없습니다",
                    "active_orders": [],
                    "execution_id": current_execution_id,
                    "total_orders": 0
                }
            
            orders_detail = []
            for order in active_orders:
                # 다음 실행 시간 계산
                if order.last_execution_time:
                    next_execution = order.last_execution_time + timedelta(minutes=order.slice_interval_minutes)
                else:
                    next_execution = order.start_time
                
                remaining_minutes = (next_execution - datetime.now()).total_seconds() / 60
                
                orders_detail.append({
                    "asset": order.asset,
                    "side": order.side,
                    "status": order.status,
                    "progress": f"{order.executed_slices}/{order.slice_count}",
                    "remaining_amount_krw": order.remaining_amount_krw,
                    "next_execution": next_execution.strftime("%Y-%m-%d %H:%M:%S"),
                    "minutes_until_next": max(0, remaining_minutes),
                    "is_overdue": remaining_minutes < 0
                })
            
            status_summary = {
                "pending": len([o for o in active_orders if o.status == "pending"]),
                "executing": len([o for o in active_orders if o.status == "executing"]),
                "completed": len([o for o in active_orders if o.status == "completed"]),
                "failed": len([o for o in active_orders if o.status == "failed"])
            }
            
            return {
                "success": True,
                "execution_id": current_execution_id,
                "total_orders": len(active_orders),
                "status_summary": status_summary,
                "orders_detail": orders_detail,
                "next_process_time": min([datetime.fromisoformat(o["next_execution"]) for o in orders_detail if not o["is_overdue"]], default=None)
            }
            
        except Exception as e:
            logger.error(f"TWAP 상태 조회 실패: {e}")
            return {"success": False, "error": str(e)}
    
    def _send_twap_status_notification(self, status: dict):
        """TWAP 상태 알림"""
        try:
            active_orders = status.get("active_orders", 0)
            orders = status.get("orders", [])
            
            message = f"""
📊 **TWAP 실행 상태 현황**

**활성 주문**: {active_orders}개

**주문별 진행 상황**:
            """.strip()
            
            for order in orders:
                asset = order.get("asset", "Unknown")
                progress = order.get("progress", "0%")
                executed_slices = order.get("executed_slices", 0)
                total_slices = order.get("total_slices", 0)
                remaining_amount = order.get("remaining_amount_krw", 0)
                remaining_time = order.get("remaining_time_hours", 0)
                
                # 진행률 바 생성 (간단한 텍스트 버전)
                progress_percent = (executed_slices / total_slices * 100) if total_slices > 0 else 0
                progress_bar = "█" * int(progress_percent / 10) + "░" * (10 - int(progress_percent / 10))
                
                message += f"""

• **{asset}** [{progress_bar}] {progress}
  - 진행: {executed_slices}/{total_slices} 슬라이스
  - 남은 금액: {remaining_amount:,.0f} KRW
  - 남은 시간: {remaining_time:.1f}시간"""
            
            message += "\n\n💡 TWAP 주문들이 계획대로 단계적으로 실행되고 있습니다."
            
            self.alert_system.send_info_alert(
                "TWAP 실행 상태",
                message,
                "twap_status"
            )
            
        except Exception as e:
            logger.error(f"TWAP 상태 알림 실패: {e}")
    
    def generate_performance_report(self, period_days: int = 30) -> dict:
        """성과 보고서 생성"""
        try:
            logger.info(f"성과 보고서 생성: {period_days}일간")
            
            report = self.performance_tracker.generate_performance_report(period_days)
            
            # 성과 알림 발송
            if "error" not in report:
                metrics = report.get("performance_metrics", {})
                self.alert_system.send_performance_alert(metrics)
            
            return report
            
        except Exception as e:
            logger.error(f"성과 보고서 생성 실패: {e}")
            return {"error": str(e)}
    
    def _send_season_change_notification(self, analysis_result: dict, immediate_rebalance: bool = False):
        """시장 계절 변화 알림"""
        try:
            market_season = analysis_result.get("market_season")
            allocation_weights = analysis_result.get("allocation_weights", {})
            
            if immediate_rebalance:
                next_action = "**다음 조치**: 즉시 TWAP 방식의 리밸런싱을 시작합니다."
            else:
                # 이 케이스는 현재 로직상 발생하지 않지만, 유연성을 위해 유지합니다.
                next_action = "**다음 조치**: 분기별 리밸런싱 시 새로운 배분 적용 예정"

            message = f"""
🔄 **시장 계절 변화 감지**

**새로운 시장 계절**: {market_season.upper()}
**권장 자산 배분**:
• 암호화폐: {allocation_weights.get('crypto', 0):.0%}
• 원화 (KRW): {allocation_weights.get('krw', 0):.0%}

{next_action}
            """.strip()
            
            self.alert_system.send_info_alert(
                f"시장 계절 변화: {market_season.upper()}",
                message,
                "season_change"
            )
            
        except Exception as e:
            logger.error(f"시장 계절 변화 알림 실패: {e}")
    
    def _send_rebalance_notification(self, result):
        """리밸런싱 결과 알림"""
        try:
            summary = result.rebalance_summary
            
            message = f"""
📊 **분기별 리밸런싱 완료**

**결과**: {'성공' if result.success else '실패'}
**시장 계절**: {summary.get('market_season', 'N/A').upper()}
**실행된 주문**: {len(result.executed_orders)}개
**실패한 주문**: {len(result.failed_orders)}개
**포트폴리오 가치 변화**: {summary.get('value_change', 0):+,.0f} KRW
            """.strip()
            
            self.alert_system.send_info_alert(
                "분기별 리밸런싱 완료",
                message,
                "quarterly_rebalance"
            )
            
        except Exception as e:
            logger.error(f"리밸런싱 알림 실패: {e}")
    
    def _send_twap_start_notification(self, execution_result):
        """TWAP 실행 시작 알림"""
        try:
            execution_plan = execution_result.get("execution_plan", {})
            twap_orders = execution_result.get("twap_orders", [])
            
            message = f"""
🔄 **TWAP 리밸런싱 시작**

**실행 계획**:
• 주문 개수: {len(twap_orders)}개
• 실행 시간: {execution_plan.get('total_execution_hours', 0)}시간
• 분할 간격: {execution_plan.get('slice_interval_minutes', 0)}분
• 시작 시간: {execution_plan.get('start_time', datetime.now()).strftime('%Y-%m-%d %H:%M:%S')}

**TWAP 주문 목록**:
            """.strip()
            
            for order in twap_orders:
                message += f"\n• {order['asset']}: {order['side']} {order['total_amount_krw']:,.0f} KRW ({order['slice_count']}회 분할)"
            
            message += "\n\n✅ TWAP 실행이 시작되었습니다. 주문들이 자동으로 분할 실행됩니다."
            
            self.alert_system.send_info_alert(
                "TWAP 리밸런싱 시작",
                message,
                "twap_start"
            )
            
        except Exception as e:
            logger.error(f"TWAP 시작 알림 실패: {e}")
    
    def _send_immediate_rebalance_notification(self, analysis_result: dict, rebalance_result: dict):
        """즉시 리밸런싱 시작 알림"""
        try:
            market_season = analysis_result.get("market_season", "Unknown")
            twap_orders = rebalance_result.get("twap_orders", [])
            execution_plan = rebalance_result.get("execution_plan", {})
            
            message = f"""
🚨 **시장 계절 변화로 즉시 리밸런싱 시작**

**트리거 이벤트**: 주간 시장 분석에서 시장 계절 변화 감지
**새로운 시장 계절**: {market_season.upper()}

**즉시 시작된 TWAP 리밸런싱**:
• 주문 개수: {len(twap_orders)}개
• 예상 실행 시간: {execution_plan.get('total_execution_hours', 0)}시간
• 분할 간격: {execution_plan.get('slice_interval_minutes', 0)}분

**TWAP 주문 목록**:
            """.strip()
            
            for order in twap_orders:
                message += f"\n• {order['asset']}: {order['side']} {order['total_amount_krw']:,.0f} KRW ({order['slice_count']}회 분할)"
            
            message += """

⚡ **자동 실행 중**: 시장 상황 변화에 따라 자동으로 리밸런싱이 시작되었습니다.
🔄 **진행 상황**: `--process-twap` 명령으로 실시간 진행 상황을 확인할 수 있습니다.
📊 **상태 확인**: `--twap-status` 명령으로 현재 상태를 조회할 수 있습니다."""
            
            self.alert_system.send_info_alert(
                f"🚨 즉시 리밸런싱 시작 - {market_season.upper()}",
                message,
                "immediate_rebalance"
            )
            
        except Exception as e:
            logger.error(f"즉시 리밸런싱 알림 실패: {e}")
    
    def _send_market_change_rebalance_notification(self, twap_result: dict, rebalance_result: dict, cancel_result: dict = None):
        """시장 상황 변화로 인한 리밸런싱 알림"""
        try:
            remaining_orders = twap_result.get("remaining_orders", 0)
            new_orders = len(rebalance_result.get("twap_orders", []))
            
            # 거래소 주문 취소 정보
            cancel_info = ""
            if cancel_result:
                cancelled_count = cancel_result.get("cancelled_count", 0)
                failed_count = cancel_result.get("failed_count", 0)
                if cancelled_count > 0 or failed_count > 0:
                    cancel_info = f"""
**거래소 주문 취소**: {cancelled_count}개 성공, {failed_count}개 실패"""
            
            message = f"""🔄 **시장 상황 변화 감지 - 리밸런싱 조정**
            
**기존 TWAP 중단**: {remaining_orders}개 주문 중단{cancel_info}
**새로운 TWAP 시작**: {new_orders}개 주문 시작

✅ 시장 상황에 맞는 최적 포트폴리오로 자동 조정되었습니다.
⚡ 기존 미완료 거래소 주문들이 안전하게 취소되었습니다."""

            self.alert_system.send_notification(
                title="🔄 시장 변화 대응 - 자동 리밸런싱",
                message=message,
                alert_type="rebalancing",
                priority="high"
            )
            
        except Exception as e:
            logger.error(f"시장 변화 리밸런싱 알림 발송 실패: {e}")
    
    def _signal_handler(self, signum, frame):
        """시그널 핸들러"""
        logger.info(f"시그널 수신: {signum}")
        self.shutdown()
    
    def shutdown(self):
        """시스템 종료"""
        try:
            logger.info("KAIROS-1 시스템 종료 시작")
            
            self.running = False
            

            
            logger.info("✅ KAIROS-1 시스템 종료 완료")
            
        except Exception as e:
            logger.error(f"시스템 종료 중 오류: {e}")
    
    def get_system_status(self) -> dict:
        """시스템 상태 조회"""
        try:
            # 포트폴리오 상태
            portfolio = self.coinone_client.get_portfolio_value()
            
            # 최근 시장 분석
            latest_analysis = self.db_manager.get_latest_market_analysis()
            
            # 활성 주문
            active_orders = self.order_manager.get_active_orders()
            
            # 리스크 지표
            risk_score = self.risk_manager.calculate_risk_score(portfolio)
            
            status = {
                "system_time": datetime.now(),
                "components_initialized": self.components_initialized,
                "portfolio": {
                    "total_value_krw": portfolio.get("total_krw", 0),
                    "asset_count": len(portfolio.get("assets", {}))
                },
                "market_analysis": {
                    "last_analysis": latest_analysis.get("analysis_date") if latest_analysis else None,
                    "current_season": latest_analysis.get("market_season") if latest_analysis else None
                },
                "trading": {
                    "active_orders": len(active_orders),
                    "last_rebalance": self._get_last_rebalance_date()
                },
                "risk": {
                    "risk_score": risk_score,
                    "risk_level": "low" if risk_score < 0.3 else "medium" if risk_score < 0.6 else "high"
                }
            }
            
            return status
            
        except Exception as e:
            logger.error(f"시스템 상태 조회 실패: {e}")
            return {"error": str(e)}
    
    def _get_last_rebalance_date(self) -> Optional[str]:
        """
        마지막 리밸런싱 실행 날짜 조회
        
        Returns:
            마지막 리밸런싱 날짜 (ISO 형식) 또는 None
        """
        try:
            # 데이터베이스에서 가장 최근 리밸런싱 기록 조회
            last_rebalance = self.db_manager.get_latest_rebalance_record()
            
            if last_rebalance and last_rebalance.get("timestamp"):
                timestamp = last_rebalance["timestamp"]
                if isinstance(timestamp, str):
                    return timestamp
                elif hasattr(timestamp, 'isoformat'):
                    return timestamp.isoformat()
                else:
                    return str(timestamp)
            
            return None
            
        except Exception as e:
            logger.warning(f"마지막 리밸런싱 날짜 조회 실패: {e}")
            return None


def main():
    """메인 실행 함수"""
    parser = argparse.ArgumentParser(description="KAIROS-1 자동 투자 시스템")
    parser.add_argument("--config", default="config/config.yaml", help="설정 파일 경로")
    parser.add_argument("--weekly-analysis", action="store_true", help="주간 시장 분석 실행")
    parser.add_argument("--quarterly-rebalance", action="store_true", help="분기별 리밸런싱 실행")
    parser.add_argument("--quarterly-rebalance-twap", action="store_true", help="TWAP 방식 분기별 리밸런싱 실행")
    parser.add_argument("--process-twap", action="store_true", help="대기 중인 TWAP 주문 처리")
    parser.add_argument("--twap-status", action="store_true", help="TWAP 주문 상태 조회")
    parser.add_argument("--clear-failed-twap", action="store_true", help="실패한 TWAP 주문 정리")
    parser.add_argument("--performance-report", type=int, metavar="DAYS", help="성과 보고서 생성 (기간 일수)")
    parser.add_argument("--advanced-performance-report", type=int, metavar="DAYS", help="고급 성과 분석 보고서 생성")
    parser.add_argument("--multi-timeframe-analysis", action="store_true", help="멀티 타임프레임 분석 실행")
    parser.add_argument("--macro-analysis", action="store_true", help="매크로 경제 분석 실행")
    parser.add_argument("--onchain-analysis", action="store_true", help="온체인 데이터 분석 실행")
    parser.add_argument("--scenario-check", action="store_true", help="시나리오 대응 체크")
    parser.add_argument("--dca-schedule", action="store_true", help="DCA+ 일정 확인")
    parser.add_argument("--bias-check", action="store_true", help="심리적 편향 체크 (데모)")
    parser.add_argument("--tax-report", action="store_true", help="세금 최적화 보고서 생성")
    parser.add_argument("--system-status", action="store_true", help="시스템 상태 조회")
    parser.add_argument("--dry-run", action="store_true", help="실제 거래 없이 시뮬레이션")
    parser.add_argument("--test-alerts", action="store_true", help="알림 시스템 테스트")
    
    # 멀티 계정 관리 명령어들
    parser.add_argument("--multi-accounts", action="store_true", help="멀티 계정 관리 CLI 실행")
    parser.add_argument("--account-status", action="store_true", help="모든 계정 상태 조회")
    parser.add_argument("--setup-multi-account", action="store_true", help="멀티 계정 초기 설정")
    
    args = parser.parse_args()
    
    try:
        # KAIROS-1 시스템 초기화
        kairos = KairosSystem(args.config)
        
        if not kairos.initialize():
            print("❌ 시스템 초기화 실패")
            sys.exit(1)
        
        # 명령에 따른 실행
        if args.weekly_analysis:
            print("🔍 주간 시장 분석 실행...")
            result = kairos.run_weekly_analysis(args.dry_run)
            if result.get("success"):
                print("✅ 주간 시장 분석 완료")
                print(f"시장 계절: {result.get('market_season', 'unknown')}")
                if result.get("rebalance_triggered"):
                    print("🔄 시장 계절 변화로 TWAP 리밸런싱이 시작되었습니다.")
                    rebalance_result = result.get("rebalance_result", {})
                    if rebalance_result.get("success"):
                        print("✅ TWAP 리밸런싱 시작 완료")
                    else:
                        print(f"❌ TWAP 리밸런싱 시작 실패: {rebalance_result.get('error')}")
            else:
                print("❌ 주간 시장 분석 실패")
                
        elif args.quarterly_rebalance:
            print("⚖️ 분기별 리밸런싱 실행...")
            result = kairos.run_quarterly_rebalance(args.dry_run)
            if result.get("success"):
                print("✅ 분기별 리밸런싱 완료")
                print(f"실행된 주문: {len(result.get('executed_orders', []))}개")
            else:
                print("❌ 분기별 리밸런싱 실패")
                
        elif args.quarterly_rebalance_twap:
            print("🔄 TWAP 분기별 리밸런싱 실행...")
            result = kairos.run_quarterly_rebalance_twap(args.dry_run)
            if result.get("success"):
                print("✅ TWAP 분기별 리밸런싱 시작 완료")
                twap_orders = result.get("twap_orders", [])
                print(f"TWAP 주문 수: {len(twap_orders)}개")
                for order in twap_orders:
                    print(f"  • {order['asset']}: {order['side']} {order['total_amount_krw']:,.0f} KRW "
                          f"({order['slice_count']}회 분할, {order['execution_hours']}시간)")
            else:
                print("❌ TWAP 분기별 리밸런싱 실패")
                
        elif args.process_twap:
            print("🔄 TWAP 주문 처리...")
            result = kairos.process_twap_orders()
            if result.get("success"):
                processed = result.get("processed_orders", 0)
                completed = result.get("completed_orders", 0)
                remaining = result.get("remaining_orders", 0)
                print(f"✅ TWAP 주문 처리 완료")
                print(f"처리된 주문: {processed}개")
                print(f"완료된 주문: {completed}개")
                print(f"남은 주문: {remaining}개")
            else:
                print("❌ TWAP 주문 처리 실패")
                
        elif args.twap_status:
            print("📊 TWAP 주문 상태 조회...")
            result = kairos.get_twap_status()
            if result.get("success"):
                total_orders = result.get("total_orders", 0)
                if total_orders == 0:
                    print("✅ 활성 TWAP 주문이 없습니다")
                else:
                    print(f"📈 활성 TWAP 주문: {total_orders}개")
                    
                    status_summary = result.get("status_summary", {})
                    print(f"상태 요약:")
                    print(f"  • 대기 중: {status_summary.get('pending', 0)}개")
                    print(f"  • 실행 중: {status_summary.get('executing', 0)}개") 
                    print(f"  • 완료: {status_summary.get('completed', 0)}개")
                    print(f"  • 실패: {status_summary.get('failed', 0)}개")
                    
                    orders_detail = result.get("orders_detail", [])
                    print(f"\n상세 정보:")
                    for order in orders_detail:
                        status_icon = {
                            "pending": "⏳",
                            "executing": "🔄", 
                            "completed": "✅",
                            "failed": "❌"
                        }.get(order["status"], "❓")
                        
                        print(f"  {status_icon} {order['asset']} ({order['side']})")
                        print(f"    진행률: {order['progress']}")
                        print(f"    상태: {order['status']}")
                        print(f"    남은 금액: {order['remaining_amount_krw']:,.0f} KRW")
                        
                        if order["status"] in ["pending", "executing"]:
                            if order["is_overdue"]:
                                print(f"    ⚠️ 실행 지연 중 (즉시 실행 예정)")
                            else:
                                print(f"    다음 실행: {order['next_execution']}")
                                print(f"    남은 시간: {order['minutes_until_next']:.1f}분")
                        print()
            else:
                print("❌ TWAP 상태 조회 실패")
                
        elif args.clear_failed_twap:
            print("🧹 실패한 TWAP 주문 정리...")
            # 실패한 주문들을 강제로 정리하는 기능
            try:
                active_orders = kairos.execution_engine.active_twap_orders
                failed_orders = [order for order in active_orders if order.status == "failed"]
                
                if not failed_orders:
                    print("✅ 정리할 실패한 주문이 없습니다")
                else:
                    print(f"🗑️ 실패한 주문 {len(failed_orders)}개 정리 중...")
                    for order in failed_orders:
                        print(f"  • {order.asset}: {order.executed_slices}/{order.slice_count} 슬라이스")
                        kairos.execution_engine.active_twap_orders.remove(order)
                    
                    # 데이터베이스 업데이트
                    kairos.execution_engine._save_twap_orders_to_db()
                    print("✅ 실패한 TWAP 주문 정리 완료")
                    
            except Exception as e:
                print(f"❌ 실패한 TWAP 주문 정리 실패: {e}")
                
        elif args.performance_report:
            print(f"📊 성과 보고서 생성... ({args.performance_report}일간)")
            report = kairos.generate_performance_report(args.performance_report)
            if "error" not in report:
                print("✅ 성과 보고서 생성 완료")
                metrics = report.get("performance_metrics", {})
                print(f"수익률: {metrics.get('total_return', 0):+.2%}")
                print(f"샤프 비율: {metrics.get('sharpe_ratio', 0):.2f}")
            else:
                print("❌ 성과 보고서 생성 실패")
                
        elif args.system_status:
            print("📋 시스템 상태 조회...")
            status = kairos.get_system_status()
            if "error" not in status:
                print("✅ 시스템 상태:")
                print(f"포트폴리오 가치: {status['portfolio']['total_value_krw']:,.0f} KRW")
                print(f"현재 시장 계절: {status['market_analysis']['current_season'] or 'N/A'}")
                print(f"리스크 수준: {status['risk']['risk_level']}")
            else:
                print("❌ 시스템 상태 조회 실패")
                
        elif args.advanced_performance_report:
            print(f"📊 고급 성과 분석 보고서 생성... ({args.advanced_performance_report}일간)")
            if kairos.advanced_performance_analytics:
                # 샘플 데이터로 테스트 (실제로는 포트폴리오 데이터 사용)
                import pandas as pd
                import numpy as np
                dates = pd.date_range(end=datetime.now(), periods=args.advanced_performance_report)
                returns = pd.Series(np.random.normal(0.001, 0.02, len(dates)), index=dates)
                
                try:
                    metrics = kairos.advanced_performance_analytics.calculate_comprehensive_metrics(returns)
                    print("✅ 고급 성과 분석 완료")
                    print(f"샤프 비율: {metrics.sharpe_ratio:.3f}")
                    print(f"소르티노 비율: {metrics.sortino_ratio:.3f}")
                    print(f"최대 드로우다운: {metrics.max_drawdown:.2%}")
                    print(f"수익률: {metrics.total_return:.2%}")
                except Exception as e:
                    print(f"❌ 고급 성과 분석 실패: {e}")
            else:
                print("❌ 고급 성과 분석기가 비활성화되어 있습니다")
                
        elif args.multi_timeframe_analysis:
            print("📈 멀티 타임프레임 분석 실행...")
            if kairos.multi_timeframe_analyzer:
                try:
                    # BTC 가격 데이터 수집 (실제로는 더 정교한 데이터 소스 사용)
                    import yfinance as yf
                    btc_ticker = yf.Ticker("BTC-USD")
                    price_data = btc_ticker.history(period="2y")
                    
                    analysis = kairos.multi_timeframe_analyzer.analyze_multi_timeframe(
                        "BTC", price_data["Close"]
                    )
                    print("✅ 멀티 타임프레임 분석 완료")
                    print(f"단기 트렌드: {analysis.short_term_trend.value}")
                    print(f"중기 트렌드: {analysis.medium_term_trend.value}") 
                    print(f"장기 트렌드: {analysis.long_term_trend.value}")
                    print(f"전체 신호: {analysis.overall_signal.value}")
                except Exception as e:
                    print(f"❌ 멀티 타임프레임 분석 실패: {e}")
            else:
                print("❌ 멀티 타임프레임 분석기가 비활성화되어 있습니다")
                
        elif args.macro_analysis:
            print("🌍 매크로 경제 분석 실행...")
            if kairos.macro_economic_analyzer:
                try:
                    indicators = kairos.macro_economic_analyzer.get_current_indicators()
                    analysis = kairos.macro_economic_analyzer.analyze_macro_environment(indicators)
                    print("✅ 매크로 경제 분석 완료")
                    print(f"경제 체제: {analysis.economic_regime.value}")
                    print(f"인플레이션 체제: {analysis.inflation_regime.value}")
                    print(f"금리 환경: {analysis.rate_environment.value}")
                    print(f"암호화폐 우호도: {analysis.crypto_favorability:.3f}")
                    print(f"권장 암호화폐 비중: {analysis.recommended_allocation.get('crypto', 0.5):.1%}")
                except Exception as e:
                    print(f"❌ 매크로 경제 분석 실패: {e}")
            else:
                print("❌ 매크로 경제 분석기가 비활성화되어 있습니다")
                
        elif args.onchain_analysis:
            print("⛓️ 온체인 데이터 분석 실행...")
            if kairos.onchain_data_analyzer:
                try:
                    metrics = kairos.onchain_data_analyzer.collect_onchain_metrics("BTC")
                    analysis = kairos.onchain_data_analyzer.analyze_onchain_data(metrics, "BTC")
                    print("✅ 온체인 데이터 분석 완료")
                    print(f"전체 트렌드: {analysis.overall_trend.value}")
                    print(f"고래 활동: {analysis.whale_activity.value}")
                    print(f"거래소 흐름: {analysis.exchange_flow.value}")
                    print(f"축적 점수: {analysis.accumulation_score:.1f}/100")
                    print(f"네트워크 건강도: {analysis.network_health_score:.1f}/100")
                    print("주요 인사이트:")
                    for insight in analysis.key_insights:
                        print(f"  • {insight}")
                except Exception as e:
                    print(f"❌ 온체인 데이터 분석 실패: {e}")
            else:
                print("❌ 온체인 데이터 분석기가 비활성화되어 있습니다")
                
        elif args.scenario_check:
            print("🔍 시나리오 대응 체크...")
            if kairos.scenario_response_system:
                try:
                    # 샘플 시장 데이터로 시나리오 감지 테스트
                    sample_market_data = {
                        "price_change_24h": -0.12,  # 12% 하락
                        "volume_surge": 2.5,        # 거래량 2.5배 증가
                        "fear_greed_index": 30      # 공포 상태
                    }
                    
                    scenarios = kairos.scenario_response_system.detect_scenarios(sample_market_data)
                    if scenarios:
                        print(f"✅ {len(scenarios)}개 시나리오 감지")
                        for scenario in scenarios:
                            print(f"  • {scenario.scenario_type.value} ({scenario.severity.value})")
                    else:
                        print("✅ 감지된 시나리오 없음 (정상 상태)")
                        
                    # 활성 시나리오 모니터링
                    monitoring = kairos.scenario_response_system.monitor_active_scenarios()
                    print(f"활성 시나리오: {len(monitoring)}개")
                    
                except Exception as e:
                    print(f"❌ 시나리오 체크 실패: {e}")
            else:
                print("❌ 시나리오 대응 시스템이 비활성화되어 있습니다")
                
        elif args.dca_schedule:
            print("💰 DCA+ 일정 확인...")
            if kairos.dca_plus_strategy:
                try:
                    # 샘플 시장 데이터
                    market_conditions = {
                        "fear_greed_index": 35,     # 공포
                        "price_volatility": 0.06,   # 6% 변동성
                        "trend_direction": "down"   # 하락 추세
                    }
                    
                    dca_signal = kairos.dca_plus_strategy.calculate_dca_signal(
                        "BTC", 1000000, market_conditions  # 100만원 기본 DCA
                    )
                    
                    print("✅ DCA+ 일정 분석 완료")
                    print(f"DCA 신호: {dca_signal.signal_strength:.2f}")
                    print(f"권장 금액: {dca_signal.recommended_amount:,.0f} KRW")
                    print(f"다음 실행: {dca_signal.next_execution_date}")
                    print(f"시장 상황 조정: {dca_signal.market_adjustment_factor:.2f}")
                    
                except Exception as e:
                    print(f"❌ DCA+ 일정 확인 실패: {e}")
            else:
                print("❌ DCA+ 전략이 비활성화되어 있습니다")
                
        elif args.bias_check:
            print("🧠 심리적 편향 체크 (데모)...")
            if kairos.bias_prevention_system:
                try:
                    # 샘플 거래 요청 (FOMO 시뮬레이션)
                    trade_request = {
                        "side": "buy",
                        "amount": 5000000,  # 500만원 (큰 금액)
                        "confidence_level": 0.95
                    }
                    
                    # 샘플 시장 데이터
                    market_data = {
                        "price_change_24h": 0.18,      # 18% 상승
                        "volume_ratio": 4.0,           # 거래량 4배 증가
                        "fear_greed_index": 85         # 극도의 탐욕
                    }
                    
                    # 샘플 포트폴리오 상태
                    portfolio_state = {
                        "total_return": 0.15,          # 15% 수익
                        "recent_big_win": True
                    }
                    
                    biases = kairos.bias_prevention_system.detect_bias(
                        trade_request, market_data, portfolio_state
                    )
                    
                    if biases:
                        print(f"⚠️ {len(biases)}개 편향 감지")
                        for bias in biases:
                            print(f"  • {bias.bias_type.value} ({bias.severity.value})")
                            print(f"    신뢰도: {bias.confidence:.0%}")
                            print(f"    트리거 요인: {', '.join(bias.trigger_factors)}")
                        
                        # 방지 조치 시뮬레이션
                        prevention_result = kairos.bias_prevention_system.apply_prevention(
                            biases, trade_request
                        )
                        
                        if not prevention_result["allowed"]:
                            print("🚫 거래 차단")
                        if prevention_result["warnings"]:
                            print("경고사항:")
                            for warning in prevention_result["warnings"]:
                                print(f"  • {warning}")
                                
                    else:
                        print("✅ 감지된 편향 없음")
                        
                except Exception as e:
                    print(f"❌ 편향 체크 실패: {e}")
            else:
                print("❌ 심리적 편향 방지 시스템이 비활성화되어 있습니다")
                
        elif args.tax_report:
            print("📄 세금 최적화 보고서 생성...")
            if kairos.tax_optimization_system:
                try:
                    # 샘플 거래 기록으로 테스트
                    report = kairos.tax_optimization_system.generate_tax_report(2024)
                    print("✅ 세금 보고서 생성 완료")
                    print(f"총 실현손익: {report.get('total_realized_gains', 0):,.0f} KRW")
                    print(f"예상 세금: {report.get('estimated_tax', 0):,.0f} KRW")
                    
                    optimization_summary = kairos.tax_optimization_system.get_optimization_summary()
                    print(f"최적화된 로트 수: {optimization_summary.get('optimized_lots', 0)}개")
                    print(f"절약된 세금: {optimization_summary.get('tax_savings', 0):,.0f} KRW")
                    
                except Exception as e:
                    print(f"❌ 세금 보고서 생성 실패: {e}")
            else:
                print("❌ 세금 최적화 시스템이 비활성화되어 있습니다")
                
        elif args.test_alerts:
            print("📧 알림 시스템 테스트...")
            results = kairos.alert_system.test_notifications()
            for channel, success in results.items():
                status = "✅" if success else "❌"
                print(f"{status} {channel} 알림 테스트")
                
        elif args.multi_accounts:
            print("🏦 멀티 계정 관리 CLI 실행...")
            from src.cli.multi_account_cli import main as cli_main
            try:
                cli_main()
            except Exception as e:
                print(f"❌ 멀티 계정 CLI 실행 실패: {e}")
                
        elif args.account_status:
            print("📊 모든 계정 상태 조회...")
            try:
                # 멀티 계정 관리자를 통해 계정 정보 조회
                accounts = kairos.multi_account_manager.accounts
                if not accounts:
                    print("📝 등록된 계정이 없습니다. --setup-multi-account로 계정을 추가하세요.")
                else:
                    print(f"🏦 총 {len(accounts)}개 계정:")
                    for account_id, account in accounts.items():
                        status = kairos.multi_account_manager.account_status.get(account_id, "unknown")
                        print(f"  • {account.account_name} ({account_id}): {status}")
            except Exception as e:
                print(f"❌ 계정 상태 조회 실패: {e}")
                
        elif args.setup_multi_account:
            print("🔧 멀티 계정 초기 설정...")
            try:
                # 현재 config의 API 키를 첫 번째 계정으로 마이그레이션
                api_config = kairos.config.get("api.coinone", {})
                if api_config.get("api_key"):
                    print("⚙️ 기존 config API 키를 메인 계정으로 등록합니다...")
                    
                    # 계정 설정 생성
                    from src.core.multi_account_manager import AccountConfig
                    from src.core.types import RiskLevel
                    
                    main_account = AccountConfig(
                        account_id="main",
                        account_name="메인 계정",
                        description="기존 config에서 마이그레이션된 메인 계정",
                        risk_level=RiskLevel.MODERATE,
                        initial_capital=1000000,  # 100만원
                        max_investment=10000000   # 1천만원
                    )
                    
                    # 계정 추가 (비동기 실행)
                    import asyncio
                    asyncio.run(kairos.multi_account_manager.add_account(
                        main_account,
                        api_config["api_key"],
                        api_config["secret_key"]
                    ))
                    
                    print("✅ 메인 계정 설정 완료")
                    print("📝 추가 계정은 --multi-accounts CLI를 사용하여 관리할 수 있습니다.")
                else:
                    print("❌ config에 API 키가 설정되어 있지 않습니다")
                    
            except Exception as e:
                print(f"❌ 멀티 계정 설정 실패: {e}")
                
        else:
            print("🚀 KAIROS-1 시스템이 성공적으로 초기화되었습니다.")
            print("\n📊 기본 명령어:")
            print("  --weekly-analysis           : 주간 시장 분석")
            print("  --quarterly-rebalance       : 분기별 리밸런싱 (즉시 실행)")
            print("  --quarterly-rebalance-twap  : TWAP 방식 분기별 리밸런싱")
            print("  --process-twap              : 대기 중인 TWAP 주문 처리")
            print("  --twap-status               : TWAP 실행 상태 조회")
            print("  --clear-failed-twap         : 실패한 TWAP 주문 정리")
            print("  --performance-report N      : N일간 기본 성과 보고서")
            print("  --system-status             : 시스템 상태 조회")
            print("  --test-alerts               : 알림 시스템 테스트")
            
            print("\n🔬 고급 분석 명령어:")
            print("  --advanced-performance-report N : N일간 고급 성과 분석")
            print("  --multi-timeframe-analysis  : 멀티 타임프레임 분석")
            print("  --macro-analysis            : 매크로 경제 분석")
            print("  --onchain-analysis          : 온체인 데이터 분석")
            print("  --scenario-check            : 시나리오 대응 체크")
            print("  --dca-schedule              : DCA+ 일정 확인")
            print("  --bias-check                : 심리적 편향 체크 (데모)")
            print("  --tax-report                : 세금 최적화 보고서")
            
            print("\n🏦 멀티 계정 관리:")
            print("  --multi-accounts            : 멀티 계정 관리 CLI 실행")
            print("  --account-status            : 모든 계정 상태 조회")
            print("  --setup-multi-account       : config API 키를 멀티 계정으로 마이그레이션")
            
            print("\n💡 옵션:")
            print("  --dry-run                   : 실제 거래 없이 시뮬레이션 모드")
            print("  --config PATH               : 사용자 정의 설정 파일 경로")
            
            # 계정 설정 상태 표시
            if hasattr(kairos, 'multi_account_manager') and kairos.multi_account_manager.accounts:
                accounts_count = len(kairos.multi_account_manager.accounts)
                print(f"\n🏦 멀티 계정 모드: {accounts_count}개 계정 등록됨")
            else:
                api_config = kairos.config.get("api.coinone", {})
                if api_config.get("api_key"):
                    print("\n🗃️ 레거시 config 모드: --setup-multi-account로 업그레이드 권장")
                    
            print("\n🎯 고급 시스템이 활성화되었습니다:")
            advanced_systems = []
            if kairos.multi_timeframe_analyzer:
                advanced_systems.append("멀티 타임프레임 분석")
            if kairos.adaptive_portfolio_manager:
                advanced_systems.append("적응형 포트폴리오")  
            if kairos.dca_plus_strategy:
                advanced_systems.append("DCA+ 전략")
            if kairos.risk_parity_model:
                advanced_systems.append("리스크 패리티")
            if kairos.tax_optimization_system:
                advanced_systems.append("세금 최적화")
            if kairos.macro_economic_analyzer:
                advanced_systems.append("매크로 경제 분석")
            if kairos.onchain_data_analyzer:
                advanced_systems.append("온체인 데이터 분석")
            if kairos.scenario_response_system:
                advanced_systems.append("시나리오 대응")
            if kairos.bias_prevention_system:
                advanced_systems.append("편향 방지")
            if kairos.advanced_performance_analytics:
                advanced_systems.append("고급 성과 분석")
                
            if advanced_systems:
                for system in advanced_systems:
                    print(f"  ✅ {system}")
            else:
                print("  ⚠️ 고급 시스템이 비활성화되어 있습니다")
        
        # 정상 종료
        kairos.shutdown()
        
    except KeyboardInterrupt:
        print("\n⏹️ 사용자에 의해 중단되었습니다.")
        sys.exit(0)
    except Exception as e:
        print(f"❌ 예기치 못한 오류: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 