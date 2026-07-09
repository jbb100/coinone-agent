#!/usr/bin/env python3
"""
기회적 매도(단계적 익절) 실행 스크립트

시장 과열(30일 저점 대비 급등 + RSI 과매수 + 탐욕지수) 시
보유 암호화폐 일부를 매도해 KRW를 확보한다.
확보된 현금은 다음 하락장에서 기회적 매수의 재원이 된다.

crontab 설정 예시:
# 매 시간 정각 실행
0 * * * * /path/to/python /path/to/execute_opportunistic_sell.py
"""

import sys
from pathlib import Path
from datetime import datetime
import asyncio
from loguru import logger

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.opportunistic_seller import OpportunisticSeller
from src.core.allocation_arbiter import AllocationArbiter
from src.utils.database_manager import DatabaseManager
from src.utils.market_data_provider import MarketDataProvider
from src.utils.fear_greed_provider import FearGreedProvider
from src.utils.config_loader import ConfigLoader
from src.core.multi_account_manager import MultiAccountManager


async def main():
    """기회적 매도 메인 실행 함수"""
    try:
        logger.info("=" * 50)
        logger.info(f"기회적 매도(익절) 실행 시작: {datetime.now()}")

        # 설정 파일 로드
        config_path = project_root / "config" / "config.yaml"
        if config_path.exists():
            config = ConfigLoader(str(config_path))
        else:
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
            return

        primary_account_id = "main"
        if primary_account_id not in multi_account_manager.accounts:
            primary_account_id = list(multi_account_manager.accounts.keys())[0]

        if primary_account_id not in multi_account_manager.clients:
            logger.error(f"계정 {primary_account_id}의 클라이언트 초기화 실패")
            return

        coinone_client = multi_account_manager.clients[primary_account_id]
        logger.info(f"사용 중인 계정: {primary_account_id}")

        db_manager = DatabaseManager(config)
        market_data_provider = MarketDataProvider(db_manager=db_manager)
        fear_greed_provider = FearGreedProvider(db_manager=db_manager)

        seller = OpportunisticSeller(
            coinone_client=coinone_client,
            db_manager=db_manager,
            fear_greed_provider=fear_greed_provider,
            market_data_provider=market_data_provider,
        )

        # 현재 포트폴리오 조회
        portfolio = coinone_client.get_portfolio_value()
        total_value = portfolio.get("total_krw", 0)
        assets = portfolio.get("assets", {})

        holdings = {}
        crypto_value = 0.0
        for asset, info in assets.items():
            if asset == "KRW" or not isinstance(info, dict):
                continue
            holdings[asset] = {
                "amount": info.get("amount", 0),
                "value_krw": info.get("value_krw", 0),
            }
            crypto_value += float(info.get("value_krw", 0) or 0)

        if not holdings or total_value <= 0:
            logger.info("매도 가능한 암호화폐 보유분이 없습니다.")
            return

        # 매도 기회 식별
        opportunities, reasons = seller.identify_sell_opportunities(list(holdings.keys()))

        if not opportunities:
            logger.info("현재 매도(익절) 기회 없음:")
            for asset, reason in reasons.items():
                logger.info(f"  {asset}: {reason}")
            return

        # 배분 조정자: 밴드 하단 아래로 내려가지 않도록 총 매도 한도 계산
        # 목표 비중은 DB의 최근 국면 분석 결과를 사용 (없으면 중립 50%)
        target_crypto_weight = 0.50
        try:
            latest = db_manager.get_latest_market_analysis()
            if latest:
                allocation = latest.get("allocation_weights") or {}
                if allocation.get("crypto"):
                    target_crypto_weight = float(allocation["crypto"])
        except Exception as e:
            logger.warning(f"최근 국면 분석 조회 실패 (중립 50% 사용): {e}")

        arbiter = AllocationArbiter(
            db_manager=db_manager,
            band_width=config.get("strategy.arbiter.band_width", 0.08),
        )
        max_sell = arbiter.max_opportunistic_sell(
            total_value_krw=total_value,
            crypto_value_krw=crypto_value,
            target_crypto_weight=target_crypto_weight,
        )

        if max_sell < 10000:
            logger.info("허용 밴드 내 매도 여력이 없어 종료합니다.")
            return

        # 매도 실행
        results = seller.execute_opportunistic_sells(
            opportunities=opportunities,
            holdings=holdings,
            max_total_sell_krw=max_sell,
        )

        logger.info(f"기회적 매도 완료: 실행 {len(results['executed_orders'])}건, "
                    f"실패 {len(results['failed_orders'])}건, "
                    f"총 {results['total_sold_krw']:,.0f} KRW 확보")

    except Exception as e:
        logger.error(f"기회적 매도 실행 실패: {e}")


if __name__ == "__main__":
    asyncio.run(main())
