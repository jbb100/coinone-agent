#!/usr/bin/env python3
"""
기회적 매수 실행 스크립트

crontab 설정 예시:
# 30분마다 실행
*/30 * * * * /path/to/python /path/to/execute_opportunistic_buy.py

# 매 시간 정각 실행
0 * * * * /path/to/python /path/to/execute_opportunistic_buy.py
"""

import sys
from pathlib import Path
from datetime import datetime
import asyncio
from loguru import logger

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.opportunistic_buyer import OpportunisticBuyer
from src.utils.database_manager import DatabaseManager
from src.utils.config_loader import ConfigLoader
from src.core.multi_account_manager import MultiAccountManager
from src.monitoring.alert_system import AlertSystem


async def main():
    """기회적 매수 메인 실행 함수"""
    try:
        logger.info("=" * 50)
        logger.info(f"기회적 매수 실행 시작: {datetime.now()}")
        
        # 설정 파일 로드
        config_path = project_root / "config" / "config.yaml"
        if config_path.exists():
            config = ConfigLoader(str(config_path))
        else:
            # 간단한 config 객체 생성
            class SimpleConfig:
                def get(self, key, default=None):
                    if key == "database.sqlite_path":
                        return str(project_root / "data" / "kairos.db")
                    return default
            config = SimpleConfig()
        
        # 멀티 계정 관리자 초기화
        multi_account_manager = MultiAccountManager()
        await multi_account_manager.initialize()
        
        if not multi_account_manager.accounts:
            logger.error("등록된 계정이 없습니다.")
            logger.info("다음 명령으로 계정을 먼저 등록하세요:")
            logger.info("  python kairos1_multi.py add main '메인계정' 'API_KEY' 'SECRET_KEY'")
            return
        
        # 기본 계정 선택 (main 또는 첫 번째 계정)
        primary_account_id = "main"
        if primary_account_id not in multi_account_manager.accounts:
            primary_account_id = list(multi_account_manager.accounts.keys())[0]
        
        if primary_account_id not in multi_account_manager.clients:
            logger.error(f"계정 {primary_account_id}의 클라이언트 초기화 실패")
            return
            
        coinone_client = multi_account_manager.clients[primary_account_id]
        logger.info(f"사용 중인 계정: {primary_account_id}")
        
        # 데이터베이스 관리자 초기화
        db_manager = DatabaseManager(config)
        
        # AlertSystem은 선택적으로 초기화 (Slack 사용)
        alert_system = None
        try:
            alert_system = AlertSystem(config)
        except Exception as e:
            logger.warning(f"AlertSystem 초기화 실패, 알림 없이 진행: {e}")
        
        # 기회적 매수 시스템 초기화 (실제 공포탐욕지수 사용)
        from src.utils.fear_greed_provider import FearGreedProvider
        opportunistic_buyer = OpportunisticBuyer(
            coinone_client=coinone_client,
            db_manager=db_manager,
            cash_reserve_ratio=0.15,  # 15% 현금 보유
            fear_greed_provider=FearGreedProvider(db_manager=db_manager)
        )
        
        # 현재 포트폴리오 조회
        portfolio = coinone_client.get_portfolio_value()
        available_cash = portfolio["assets"].get("KRW", {}).get("balance", 0)
        
        logger.info(f"사용 가능한 현금: {available_cash:,.0f} KRW")
        
        # 최소 현금 확인 (10만원 이상)
        if available_cash < 100000:
            logger.info("사용 가능한 현금이 10만원 미만으로 기회적 매수 건너뜀")
            return
        
        # 현금 활용 전략 조회
        strategy = opportunistic_buyer.get_cash_utilization_strategy()
        logger.info(f"현재 전략: {strategy['mode']} - {strategy['description']}")
        fng = strategy.get('current_fear_greed')
        logger.info(f"공포탐욕 지수: {f'{fng:.1f}' if fng is not None else '데이터 없음'}")
        
        # 매수 기회 식별 (반환값: (기회 목록, 기회 없는 이유))
        target_assets = strategy.get("target_assets", ["BTC", "ETH", "SOL", "AVAX"])
        opportunities, no_opportunity_reasons = opportunistic_buyer.identify_opportunities(target_assets)

        if not opportunities:
            logger.info("현재 매수 기회가 없습니다")
            for asset, reason in no_opportunity_reasons.items():
                logger.info(f"  {asset}: {reason}")
            return

        logger.info(f"총 {len(opportunities)}개의 매수 기회 발견")

        # 매수 한도: 현금 전략 + 배분 조정자 밴드 (매수 후 crypto 비중이 밴드 상단을 넘지 않도록)
        max_buy_amount = available_cash * strategy.get("cash_deploy_ratio", 0.2)

        try:
            from src.core.allocation_arbiter import AllocationArbiter

            total_value = portfolio.get("total_krw", 0)
            crypto_value = sum(
                float(info.get("value_krw", 0) or 0)
                for asset, info in portfolio.get("assets", {}).items()
                if asset != "KRW" and isinstance(info, dict)
            )

            # 목표 crypto 비중: DB의 최근 국면 분석 결과 (없으면 중립 50%)
            target_crypto_weight = 0.50
            latest = db_manager.get_latest_market_analysis()
            if latest:
                allocation = latest.get("allocation_weights") or {}
                if allocation.get("crypto"):
                    target_crypto_weight = float(allocation["crypto"])

            arbiter = AllocationArbiter(
                db_manager=db_manager,
                band_width=config.get("strategy.arbiter.band_width", 0.08),
            )
            band_limit = arbiter.max_opportunistic_buy(
                total_value_krw=total_value,
                crypto_value_krw=crypto_value,
                target_crypto_weight=target_crypto_weight,
            )
            max_buy_amount = min(max_buy_amount, band_limit)

            if max_buy_amount < 10000:
                logger.info("허용 밴드 내 매수 여력이 없어 종료합니다.")
                return
        except Exception as e:
            logger.warning(f"배분 조정자 한도 계산 실패 (현금 전략 한도만 적용): {e}")

        results = opportunistic_buyer.execute_opportunistic_buys(
            opportunities=opportunities,
            available_cash=available_cash,
            max_total_buy=max_buy_amount
        )
        
        # 결과 요약
        if results["executed_orders"]:
            success_msg = f"✅ 기회적 매수 완료\n"
            success_msg += f"실행 주문: {len(results['executed_orders'])}개\n"
            success_msg += f"총 투자 금액: {results['total_invested']:,.0f} KRW\n"
            success_msg += f"남은 현금: {results['remaining_cash']:,.0f} KRW\n"
            
            for order in results["executed_orders"]:
                success_msg += f"  - {order['asset']}: {order['amount']:,.0f} KRW "
                success_msg += f"(신뢰도: {order['confidence']:.1%})\n"
            
            logger.info(success_msg)
            
            # 알림 전송 (alert_system이 있을 경우만)
            if alert_system:
                alert_system.send_alert(
                    title="기회적 매수 실행",
                    message=success_msg,
                    alert_type="info"
                )
        else:
            logger.info("실행된 매수 주문이 없습니다")
        
        if results["failed_orders"]:
            logger.warning(f"실패한 주문: {len(results['failed_orders'])}개")
            for order in results["failed_orders"]:
                logger.warning(f"  - {order['asset']}: {order['reason']}")
        
        logger.info(f"기회적 매수 실행 완료: {datetime.now()}")
        logger.info("=" * 50)
        
    except Exception as e:
        logger.error(f"기회적 매수 실행 중 오류 발생: {e}")
        
        # 오류 알림
        if 'alert_system' in locals() and alert_system:
            alert_system.send_alert(
                title="기회적 매수 실행 오류",
                message=str(e),
                alert_type="error"
            )
        
        raise


def sync_main():
    """동기 래퍼 함수"""
    return asyncio.run(main())


if __name__ == "__main__":
    sync_main()