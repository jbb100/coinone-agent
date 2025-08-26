#!/usr/bin/env python3
"""
시장 분석 시간별 실행 스크립트
- 매시간 시장 상황 모니터링
- 기회적 매수 시그널 감지
- 데이터베이스에 분석 결과 저장
"""

import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from datetime import datetime, timezone
from typing import Dict, Any
import pandas as pd
from loguru import logger

from src.utils.config_loader import ConfigLoader
from src.utils.database_manager import DatabaseManager
from src.utils.binance_data_provider import BinanceDataProvider
from src.core.market_season_filter import MarketSeasonFilter
from src.core.multi_timeframe_analyzer import MultiTimeframeAnalyzer
from src.core.behavioral_bias_prevention import BehavioralBiasPrevention
from src.core.macro_economic_analyzer import MacroEconomicAnalyzer
from src.core.onchain_data_analyzer import OnchainDataAnalyzer


class MarketAnalysisHourly:
    """시간별 시장 분석 실행기"""
    
    def __init__(self, config_file: str = "config/config.yaml"):
        """초기화"""
        self.config = ConfigLoader(config_file)
        self.db_manager = DatabaseManager(self.config)
        self.data_provider = BinanceDataProvider()
        
        # 분석 모듈들 초기화
        self.market_filter = MarketSeasonFilter(db_manager=self.db_manager)
        self.multi_timeframe = MultiTimeframeAnalyzer(
            market_season_filter=self.market_filter,
            db_manager=self.db_manager
        )
        self.behavioral_bias = BehavioralBiasPrevention(
            db_manager=self.db_manager
        )
        self.macro_analyzer = MacroEconomicAnalyzer(
            api_keys=self.config.get('api_keys', {}),
            db_manager=self.db_manager
        )
        self.onchain_analyzer = OnchainDataAnalyzer(
            db_manager=self.db_manager
        )
        
        # 분석 대상 자산들
        self.target_assets = self.config.get('trading_params', {}).get('target_assets', ['BTC', 'ETH'])
        
    async def analyze_asset(self, symbol: str) -> Dict[str, Any]:
        """개별 자산 분석"""
        try:
            logger.info(f"🔍 {symbol} 분석 시작...")
            
            # 1. 가격 데이터 가져오기
            symbol_usdt = f"{symbol}USDT"
            prices = self.data_provider.get_historical_klines(
                symbol=symbol_usdt, 
                interval='1h', 
                limit=168
            )
            if prices is None or prices.empty:
                logger.warning(f"❌ {symbol} 가격 데이터 없음")
                return {'symbol': symbol, 'success': False, 'error': 'No price data'}
            
            current_price = float(prices['Close'].iloc[-1])
            
            # 2. 멀티 타임프레임 분석
            multi_tf_result = self.multi_timeframe.analyze_multi_timeframe(
                symbol, prices['Close']
            )
            
            # 3. 행동 편향 체크 (간소화)
            try:
                # 올바른 형태로 데이터 전달
                decision_data = {
                    'symbol': symbol,
                    'current_price': current_price,
                    'order_side': 'buy',  # 매수 시그널 분석이므로
                    'amount': 100000,  # 기본 매수 금액
                    'timestamp': datetime.now(timezone.utc)
                }
                market_context_dict = {
                    'price_data': prices.to_dict('records'),
                    'price_change_24h': (prices['Close'].iloc[-1] / prices['Close'].iloc[-25] - 1) if len(prices) > 24 else 0,
                    'price_change_1h': (prices['Close'].iloc[-1] / prices['Close'].iloc[-2] - 1) if len(prices) > 1 else 0,
                    'volume_surge': 1.0,  # 기본값
                    'social_sentiment': 0.5  # 중립
                }
                bias_check = self.behavioral_bias.analyze_comprehensive_bias(
                    decision_data, market_context_dict
                )
            except Exception as e:
                logger.warning(f"⚠️ {symbol} 행동 편향 분석 실패, 기본값 사용: {e}")
                bias_check = {'detected_biases': [], 'overall_risk': 0.0}
            
            # 4. 매크로 경제 지표 분석  
            try:
                macro_result = self.macro_analyzer.analyze_comprehensive_macro()
            except Exception as e:
                logger.warning(f"⚠️ 매크로 분석 실패, 기본값 사용: {e}")
                macro_result = {'overall_score': 0.5}
            
            # 5. 온체인 데이터 분석 (BTC, ETH만)
            onchain_result = None
            if symbol in ['BTC', 'ETH']:
                try:
                    onchain_result = self.onchain_analyzer.analyze_comprehensive_onchain(symbol)
                except Exception as e:
                    logger.warning(f"⚠️ {symbol} 온체인 분석 실패, 기본값 사용: {e}")
                    onchain_result = {'overall_signal': 0.5}
            
            # 6. 종합 시그널 계산
            buy_signal = self._calculate_buy_signal(
                multi_tf_result, bias_check, macro_result, onchain_result
            )
            
            # 7. 결과 저장 (JSON 직렬화 가능한 형태로)
            analysis_result = {
                'symbol': symbol,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'current_price': current_price,
                'multi_timeframe': {
                    'confidence_score': multi_tf_result.get('confidence_score', 0),
                    'trend_direction': str(multi_tf_result.get('trend_direction', 'unknown')),
                    'key_metrics': multi_tf_result.get('key_metrics', {})
                },
                'behavioral_bias': {
                    'overall_risk': bias_check.get('overall_risk', 0),
                    'detected_count': len(bias_check.get('detected_biases', []))
                },
                'macro_indicators': {
                    'overall_score': macro_result.get('overall_score', 0.5),
                    'crypto_favorability': macro_result.get('crypto_favorability', 0)
                },
                'onchain_metrics': {
                    'overall_signal': onchain_result.get('overall_signal', 0.5) if onchain_result else None,
                    'accumulation_score': onchain_result.get('accumulation_score', 0) if onchain_result else None
                },
                'buy_signal': buy_signal,
                'success': True
            }
            
            # DB에 저장 (시도)
            try:
                self.db_manager.save_analysis_result('hourly_market_analysis', analysis_result)
            except Exception as e:
                logger.warning(f"⚠️ DB 저장 실패, 계속 진행: {e}")
            
            # 시그널 강도에 따른 로그
            if buy_signal['strength'] >= 0.7:
                logger.success(f"🚀 {symbol} 강한 매수 시그널! (강도: {buy_signal['strength']:.2%})")
            elif buy_signal['strength'] >= 0.5:
                logger.info(f"📈 {symbol} 중간 매수 시그널 (강도: {buy_signal['strength']:.2%})")
            else:
                logger.debug(f"📊 {symbol} 약한/없는 시그널 (강도: {buy_signal['strength']:.2%})")
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"❌ {symbol} 분석 실패: {e}")
            return {'symbol': symbol, 'success': False, 'error': str(e)}
    
    def _calculate_buy_signal(
        self,
        multi_tf: Dict,
        bias_check: Dict,
        macro: Dict,
        onchain: Dict = None
    ) -> Dict[str, Any]:
        """종합 매수 시그널 계산"""
        weights = {
            'multi_timeframe': 0.35,
            'behavioral': 0.20,
            'macro': 0.25,
            'onchain': 0.20
        }
        
        scores = {}
        
        # 멀티 타임프레임 점수
        if multi_tf and multi_tf.get('confidence_score'):
            scores['multi_timeframe'] = multi_tf['confidence_score']
        
        # 행동 편향 점수 (편향 없을수록 높은 점수)
        if bias_check:
            if isinstance(bias_check, dict) and 'overall_risk' in bias_check:
                scores['behavioral'] = max(0, 1 - bias_check.get('overall_risk', 0))
            else:
                bias_count = len(bias_check.get('detected_biases', []))
                scores['behavioral'] = max(0, 1 - (bias_count * 0.25))
        
        # 매크로 점수
        if macro and macro.get('overall_score'):
            scores['macro'] = macro['overall_score']
        
        # 온체인 점수
        if onchain:
            if hasattr(onchain, 'overall_signal'):
                scores['onchain'] = onchain.overall_signal
            elif onchain.get('overall_signal'):
                scores['onchain'] = onchain['overall_signal']
            else:
                # overall_signal이 없으면 accumulation_score를 사용하여 계산
                accumulation = onchain.get('accumulation_score', 50) / 100.0
                scores['onchain'] = max(0.3, min(0.8, accumulation))
        
        # 가중 평균 계산
        total_weight = 0
        weighted_sum = 0
        
        for key, score in scores.items():
            if score is not None:
                weight = weights.get(key, 0)
                weighted_sum += score * weight
                total_weight += weight
        
        final_score = weighted_sum / total_weight if total_weight > 0 else 0
        
        # 시그널 분류
        if final_score >= 0.7:
            signal_type = 'STRONG_BUY'
        elif final_score >= 0.5:
            signal_type = 'BUY'
        elif final_score >= 0.3:
            signal_type = 'WEAK_BUY'
        else:
            signal_type = 'NEUTRAL'
        
        return {
            'strength': final_score,
            'type': signal_type,
            'components': scores,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    
    async def run_hourly_analysis(self):
        """시간별 분석 실행"""
        try:
            logger.info("=" * 60)
            logger.info(f"📊 시간별 시장 분석 시작 - {datetime.now()}")
            logger.info("=" * 60)
            
            # 모든 자산 분석
            results = []
            for symbol in self.target_assets:
                result = await self.analyze_asset(symbol)
                results.append(result)
                await asyncio.sleep(1)  # API 레이트 리밋 방지
            
            # 강한 시그널이 있는지 확인
            strong_signals = [
                r for r in results
                if r.get('success') and r.get('buy_signal', {}).get('strength', 0) >= 0.7
            ]
            
            if strong_signals:
                logger.success(f"🎯 {len(strong_signals)}개 자산에서 강한 매수 기회 발견!")
                for signal in strong_signals:
                    logger.info(f"  - {signal['symbol']}: {signal['buy_signal']['strength']:.2%}")
                
                # 알림 또는 자동 실행 트리거 가능
                # self._trigger_opportunistic_buy(strong_signals)
            
            # 분석 요약
            logger.info("\n📋 분석 요약:")
            logger.info(f"  - 분석된 자산: {len(results)}")
            logger.info(f"  - 성공: {sum(1 for r in results if r.get('success'))}")
            logger.info(f"  - 실패: {sum(1 for r in results if not r.get('success'))}")
            logger.info(f"  - 강한 시그널: {len(strong_signals)}")
            
            logger.info("=" * 60)
            logger.info("✅ 시간별 분석 완료")
            logger.info("=" * 60)
            
            return results
            
        except Exception as e:
            logger.error(f"❌ 시간별 분석 실패: {e}")
            raise


async def main():
    """메인 실행 함수"""
    analyzer = MarketAnalysisHourly()
    await analyzer.run_hourly_analysis()


if __name__ == "__main__":
    # 로거 설정
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level="INFO"
    )
    
    # 비동기 실행
    asyncio.run(main())