#!/usr/bin/env python3
"""
KAIROS-1 주간 시장 분석 스크립트

매주 월요일에 실행되어 BTC 가격과 200주 이동평균을 분석하고
시장 계절 변화를 감지합니다.
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf
from loguru import logger

# 프로젝트 루트 디렉토리를 PYTHONPATH에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.market_season_filter import MarketSeasonFilter, MarketSeason
from src.monitoring.alert_system import AlertSystem
from src.utils.config_loader import ConfigLoader
from src.utils.database_manager import DatabaseManager


class WeeklyAnalyzer:
    """주간 시장 분석기"""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """
        Args:
            config_path: 설정 파일 경로
        """
        self.config = ConfigLoader(config_path)
        self.market_filter = MarketSeasonFilter(
            buffer_band=self.config.get("strategy.market_season.buffer_band", 0.05)
        )
        self.alert_system = AlertSystem(self.config)
        self.db_manager = DatabaseManager(self.config)
        
        # 로깅 설정
        log_level = self.config.get("logging.level", "INFO")
        log_file = self.config.get("logging.file_path", "./logs/weekly_analysis.log")
        
        logger.remove()  # 기본 핸들러 제거
        logger.add(
            log_file,
            level=log_level,
            rotation=self.config.get("logging.rotation", "100 MB"),
            retention=self.config.get("logging.retention", "30 days"),
            format=self.config.get("logging.format", 
                "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}")
        )
        logger.add(sys.stdout, level=log_level)  # 콘솔 출력도 유지
        
        logger.info("WeeklyAnalyzer 초기화 완료")
    
    def fetch_btc_price_data(self, period: str = "3y") -> pd.DataFrame:
        """
        BTC 가격 데이터 수집
        
        Args:
            period: 데이터 수집 기간 (기본값: 3년)
            
        Returns:
            BTC 가격 데이터 DataFrame
        """
        try:
            logger.info("BTC 가격 데이터 수집 시작")
            
            # Yahoo Finance에서 BTC-USD 데이터 수집
            btc_ticker = yf.Ticker("BTC-USD")
            price_data = btc_ticker.history(period=period)
            
            if price_data.empty:
                raise ValueError("BTC 가격 데이터를 가져올 수 없습니다.")
            
            # 인덱스를 DatetimeIndex로 변환
            price_data.index = pd.to_datetime(price_data.index)
            
            logger.info(f"BTC 가격 데이터 수집 완료: {len(price_data)}일치 데이터")
            return price_data
            
        except Exception as e:
            logger.error(f"BTC 가격 데이터 수집 실패: {e}")
            raise
    
    def save_analysis_result(self, analysis_result: dict):
        """
        분석 결과를 데이터베이스에 저장
        
        Args:
            analysis_result: 분석 결과 딕셔너리
        """
        try:
            self.db_manager.save_market_analysis(analysis_result)
            logger.info("분석 결과 데이터베이스 저장 완료")
            
        except Exception as e:
            logger.error(f"분석 결과 저장 실패: {e}")
    
    def check_season_change(self, current_analysis: dict) -> bool:
        """
        시장 계절 변화 확인
        
        Args:
            current_analysis: 현재 분석 결과
            
        Returns:
            계절 변화 여부
        """
        try:
            # 이전 분석 결과 조회
            previous_analysis = self.db_manager.get_latest_market_analysis()
            
            if not previous_analysis:
                logger.info("이전 분석 결과 없음 - 첫 번째 실행")
                return True
            
            current_season = current_analysis.get("market_season")
            previous_season = previous_analysis.get("market_season")
            
            season_changed = current_season != previous_season
            
            if season_changed:
                logger.info(f"시장 계절 변화 감지: {previous_season} → {current_season}")
            else:
                logger.info(f"시장 계절 유지: {current_season}")
            
            return season_changed
            
        except Exception as e:
            logger.error(f"시장 계절 변화 확인 실패: {e}")
            return False
    
    def run_weekly_analysis(self) -> dict:
        """
        주간 시장 분석 실행
        
        Returns:
            분석 결과 딕셔너리
        """
        try:
            logger.info("=== KAIROS-1 주간 시장 분석 시작 ===")
            
            # 1. BTC 가격 데이터 수집
            price_data = self.fetch_btc_price_data()
            
            # 2. 직전 시장 계절 조회 (완충 밴드 히스테리시스용)
            from src.core.market_season_filter import season_from_string
            previous_season = None
            try:
                previous_analysis = self.db_manager.get_latest_market_analysis()
                if previous_analysis:
                    previous_season = season_from_string(previous_analysis.get("market_season"))
            except Exception as e:
                logger.warning(f"직전 시장 계절 조회 실패 (최초 실행으로 간주): {e}")

            # 3. 시장 계절 분석
            analysis_result = self.market_filter.analyze_weekly(
                price_data, previous_season=previous_season
            )
            
            if not analysis_result.get("success"):
                raise RuntimeError(f"시장 분석 실패: {analysis_result.get('error')}")
            
            # 3. 시장 계절 변화 확인
            season_changed = self.check_season_change(analysis_result)
            analysis_result["season_changed"] = season_changed
            
            # 4. 분석 결과 저장
            self.save_analysis_result(analysis_result)
            
            # 5. 알림 발송 (계절 변화시)
            if season_changed:
                self.send_season_change_alert(analysis_result)
            
            # 6. 결과 요약
            summary = self.create_analysis_summary(analysis_result)
            logger.info(f"주간 분석 완료: {summary}")
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"주간 시장 분석 실패: {e}")
            
            # 오류 알림 발송
            self.alert_system.send_error_alert(
                title="주간 시장 분석 실패",
                message=f"오류 내용: {str(e)}",
                error_type="weekly_analysis_failure"
            )
            
            return {
                "success": False,
                "error": str(e),
                "analysis_date": datetime.now()
            }
    
    def send_season_change_alert(self, analysis_result: dict):
        """
        시장 계절 변화 알림 발송
        
        Args:
            analysis_result: 분석 결과
        """
        try:
            market_season = analysis_result.get("market_season")
            allocation_weights = analysis_result.get("allocation_weights", {})
            analysis_info = analysis_result.get("analysis_info", {})
            
            # 알림 메시지 생성
            message = f"""
🚨 **KAIROS-1 시장 계절 변화 알림**

📅 **분석 날짜**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
📊 **새로운 시장 계절**: {market_season.upper()}

💰 **권장 자산 배분**:
• 암호화폐: {allocation_weights.get('crypto', 0):.0%}
• 원화 (KRW): {allocation_weights.get('krw', 0):.0%}

📈 **시장 분석**:
• BTC 현재가: {analysis_info.get('current_price', 0):,.0f} USD
• 200주 이동평균: {analysis_info.get('ma_200w', 0):,.0f} USD
• 가격 비율: {analysis_info.get('price_ratio', 0):.3f}

⚡ **다음 조치**: 분기별 리밸런싱 시 새로운 배분 비율 적용 예정
            """.strip()
            
            self.alert_system.send_info_alert(
                title=f"시장 계절 변화: {market_season.upper()}",
                message=message,
                alert_type="season_change"
            )
            
            logger.info("시장 계절 변화 알림 발송 완료")
            
        except Exception as e:
            logger.error(f"시장 계절 변화 알림 발송 실패: {e}")
    
    def create_analysis_summary(self, analysis_result: dict) -> str:
        """
        분석 결과 요약 생성
        
        Args:
            analysis_result: 분석 결과
            
        Returns:
            요약 문자열
        """
        if not analysis_result.get("success"):
            return f"분석 실패 - {analysis_result.get('error', 'Unknown error')}"
        
        market_season = analysis_result.get("market_season", "unknown")
        season_changed = analysis_result.get("season_changed", False)
        allocation = analysis_result.get("allocation_weights", {})
        
        change_indicator = "🔄 변화" if season_changed else "➡️ 유지"
        
        return (f"{change_indicator} | 시장계절: {market_season} | "
                f"암호화폐: {allocation.get('crypto', 0):.0%} | "
                f"KRW: {allocation.get('krw', 0):.0%}")


def main():
    """메인 실행 함수"""
    try:
        # 설정 파일 경로 확인
        config_path = os.environ.get("KAIROS_CONFIG", "config/config.yaml")
        
        if not os.path.exists(config_path):
            print(f"❌ 설정 파일을 찾을 수 없습니다: {config_path}")
            print("config/config.example.yaml을 복사하여 config/config.yaml을 생성하고 설정을 입력하세요.")
            sys.exit(1)
        
        # 주간 분석기 실행
        analyzer = WeeklyAnalyzer(config_path)
        result = analyzer.run_weekly_analysis()
        
        # 결과 출력
        if result.get("success"):
            print("✅ 주간 시장 분석 완료")
            market_season = result.get("market_season", "unknown")
            season_changed = result.get("season_changed", False)
            
            if season_changed:
                print(f"🔄 시장 계절 변화: {market_season}")
            else:
                print(f"➡️ 시장 계절 유지: {market_season}")
        else:
            print("❌ 주간 시장 분석 실패")
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