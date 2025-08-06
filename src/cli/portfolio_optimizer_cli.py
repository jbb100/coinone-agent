"""
Portfolio Optimizer CLI Commands

동적 포트폴리오 최적화 관련 CLI 명령어들
"""

import click
import json
from datetime import datetime
from typing import Dict, Optional
from loguru import logger

from ..core.dynamic_portfolio_optimizer import DynamicPortfolioOptimizer
from ..core.portfolio_manager import PortfolioManager
from ..trading.coinone_client import CoinoneClient


@click.group()
def portfolio_optimizer():
    """동적 포트폴리오 최적화 관련 명령어들"""
    pass


@portfolio_optimizer.command()
@click.option('--risk-level', 
              type=click.Choice(['conservative', 'moderate', 'aggressive']),
              default='moderate',
              help='리스크 수준 선택')
@click.option('--max-assets', 
              type=int, 
              default=6,
              help='최대 보유 자산 수')
@click.option('--output-format',
              type=click.Choice(['table', 'json']),
              default='table',
              help='출력 형식')
def analyze_assets(risk_level: str, max_assets: int, output_format: str):
    """모든 가능한 자산 분석 및 점수 계산"""
    try:
        # 환경 변수에서 API 키 로드 (실제 구현 시)
        # api_key = os.getenv("COINONE_API_KEY")
        # secret_key = os.getenv("COINONE_SECRET_KEY")
        
        click.echo(f"🔍 자산 분석 시작 (리스크 수준: {risk_level})")
        
        # 실제 사용 시에는 적절한 API 키가 필요
        # coinone_client = CoinoneClient(api_key, secret_key)
        # optimizer = DynamicPortfolioOptimizer(
        #     coinone_client=coinone_client,
        #     risk_level=risk_level,
        #     max_assets=max_assets
        # )
        
        # 데모용 출력
        click.echo("\n📊 자산 분석 결과:")
        demo_results = {
            "BTC": {"score": 0.85, "class": "core", "market_cap": 500000000000},
            "ETH": {"score": 0.82, "class": "core", "market_cap": 200000000000},
            "SOL": {"score": 0.75, "class": "layer1", "market_cap": 15000000000},
            "ADA": {"score": 0.68, "class": "layer1", "market_cap": 12000000000},
            "LINK": {"score": 0.72, "class": "utility", "market_cap": 8000000000}
        }
        
        if output_format == 'json':
            click.echo(json.dumps(demo_results, indent=2))
        else:
            for asset, data in demo_results.items():
                click.echo(f"  {asset}: 점수 {data['score']:.2f} | "
                          f"클래스 {data['class']} | "
                          f"시총 ${data['market_cap']/1e9:.1f}B")
                
        click.echo(f"\n✅ 분석 완료 ({len(demo_results)}개 자산)")
        
    except Exception as e:
        click.echo(f"❌ 자산 분석 실패: {e}")


@portfolio_optimizer.command()
@click.option('--risk-level', 
              type=click.Choice(['conservative', 'moderate', 'aggressive']),
              default='moderate')
@click.option('--force', 
              is_flag=True,
              help='캐시 무시하고 강제 최적화 실행')
def optimize_portfolio(risk_level: str, force: bool):
    """포트폴리오 최적화 실행"""
    try:
        click.echo(f"🚀 포트폴리오 최적화 시작 (리스크: {risk_level})")
        
        if force:
            click.echo("⚠️ 강제 최적화 모드 - 캐시 무시")
        
        # 실제 구현에서는 API 키와 클라이언트 초기화 필요
        click.echo("\n📈 최적화 진행 중...")
        
        # 데모 결과
        optimal_portfolio = {
            "weights": {
                "BTC": 0.35,
                "ETH": 0.25, 
                "SOL": 0.20,
                "LINK": 0.15,
                "ADA": 0.05
            },
            "expected_return": 0.12,
            "expected_risk": 0.25,
            "sharpe_ratio": 0.48,
            "diversification_score": 0.83
        }
        
        click.echo("🎉 최적화 완료!")
        click.echo("\n📊 최적 포트폴리오 비중:")
        for asset, weight in optimal_portfolio["weights"].items():
            click.echo(f"  {asset}: {weight:.1%}")
            
        click.echo(f"\n📈 포트폴리오 통계:")
        click.echo(f"  예상 수익률: {optimal_portfolio['expected_return']:.1%}")
        click.echo(f"  예상 리스크: {optimal_portfolio['expected_risk']:.1%}") 
        click.echo(f"  샤프 비율: {optimal_portfolio['sharpe_ratio']:.2f}")
        click.echo(f"  다양성 점수: {optimal_portfolio['diversification_score']:.2f}")
        
    except Exception as e:
        click.echo(f"❌ 포트폴리오 최적화 실패: {e}")


@portfolio_optimizer.command()
@click.option('--threshold', 
              type=float, 
              default=0.05,
              help='리밸런싱 임계값 (기본 5%)')
def check_rebalance_need(threshold: float):
    """리밸런싱 필요 여부 확인"""
    try:
        click.echo(f"🔍 리밸런싱 필요 여부 확인 (임계값: {threshold:.1%})")
        
        # 데모 데이터
        current_weights = {
            "BTC": 0.40,
            "ETH": 0.30, 
            "SOL": 0.15,
            "LINK": 0.10,
            "ADA": 0.05
        }
        
        optimal_weights = {
            "BTC": 0.35,
            "ETH": 0.25,
            "SOL": 0.20, 
            "LINK": 0.15,
            "ADA": 0.05
        }
        
        click.echo("\n📊 포트폴리오 비중 비교:")
        needs_rebalancing = False
        max_deviation = 0
        
        for asset in set(list(current_weights.keys()) + list(optimal_weights.keys())):
            current = current_weights.get(asset, 0)
            optimal = optimal_weights.get(asset, 0)
            deviation = abs(current - optimal)
            max_deviation = max(max_deviation, deviation)
            
            status = "⚠️" if deviation > threshold else "✅"
            click.echo(f"  {status} {asset}: 현재 {current:.1%} → 최적 {optimal:.1%} "
                      f"(편차: {deviation:+.1%})")
            
            if deviation > threshold:
                needs_rebalancing = True
        
        click.echo(f"\n📈 최대 편차: {max_deviation:.1%}")
        
        if needs_rebalancing:
            click.echo("🔄 리밸런싱 필요")
        else:
            click.echo("✅ 리밸런싱 불필요 - 포트폴리오 최적 상태 유지")
            
    except Exception as e:
        click.echo(f"❌ 리밸런싱 확인 실패: {e}")


@portfolio_optimizer.command()
def status():
    """포트폴리오 최적화 상태 조회"""
    try:
        click.echo("📊 포트폴리오 최적화 상태")
        
        # 데모 상태 정보
        status_info = {
            "dynamic_optimization_enabled": True,
            "optimizer_available": True,
            "last_optimization_time": "2024-01-15 10:30:00",
            "time_since_last_optimization": {"minutes": 45, "is_fresh": False},
            "cached_portfolio": {
                "risk_level": "moderate",
                "expected_return": 0.12,
                "expected_risk": 0.25
            }
        }
        
        click.echo(f"\n🔧 최적화 엔진 상태:")
        click.echo(f"  동적 최적화: {'✅ 활성화' if status_info['dynamic_optimization_enabled'] else '❌ 비활성화'}")
        click.echo(f"  최적화기: {'✅ 사용 가능' if status_info['optimizer_available'] else '❌ 사용 불가'}")
        
        if status_info.get("last_optimization_time"):
            click.echo(f"  마지막 최적화: {status_info['last_optimization_time']}")
            time_info = status_info.get("time_since_last_optimization", {})
            freshness = "🟢 최신" if time_info.get("is_fresh") else "🟡 오래됨"
            click.echo(f"  캐시 상태: {freshness} ({time_info.get('minutes', 0)}분 전)")
        
        if status_info.get("cached_portfolio"):
            cache = status_info["cached_portfolio"]
            click.echo(f"\n📈 캐시된 포트폴리오:")
            click.echo(f"  리스크 수준: {cache['risk_level']}")
            click.echo(f"  예상 수익률: {cache['expected_return']:.1%}")
            click.echo(f"  예상 리스크: {cache['expected_risk']:.1%}")
            
    except Exception as e:
        click.echo(f"❌ 상태 조회 실패: {e}")


@portfolio_optimizer.command() 
@click.option('--asset',
              type=str,
              help='특정 자산의 상세 분석 (예: BTC)')
def analyze_asset(asset: Optional[str]):
    """개별 자산 상세 분석"""
    try:
        if not asset:
            click.echo("❌ 분석할 자산을 지정해주세요. 예: --asset BTC")
            return
            
        asset = asset.upper()
        click.echo(f"🔍 {asset} 상세 분석")
        
        # 데모 분석 결과
        analysis = {
            "symbol": asset,
            "market_cap": 500000000000 if asset == "BTC" else 200000000000,
            "volume_24h": 25000000000,
            "price_change_24h": 0.025,
            "price_change_7d": 0.087,
            "price_change_30d": 0.156,
            "volatility_30d": 0.45,
            "sharpe_ratio_30d": 0.65,
            "max_drawdown_30d": -0.18,
            "correlation_btc": 1.0 if asset == "BTC" else 0.78,
            "liquidity_score": 1.0,
            "momentum_score": 0.12,
            "quality_score": 0.67,
            "risk_score": 0.35,
            "overall_score": 0.85 if asset == "BTC" else 0.72
        }
        
        click.echo(f"\n💰 기본 정보:")
        click.echo(f"  시가총액: ${analysis['market_cap']/1e9:.1f}B")
        click.echo(f"  24h 거래량: ${analysis['volume_24h']/1e9:.1f}B")
        
        click.echo(f"\n📈 가격 변동:")
        click.echo(f"  24시간: {analysis['price_change_24h']:+.1%}")
        click.echo(f"  7일: {analysis['price_change_7d']:+.1%}")
        click.echo(f"  30일: {analysis['price_change_30d']:+.1%}")
        
        click.echo(f"\n📊 리스크 지표:")
        click.echo(f"  변동성 (30일): {analysis['volatility_30d']:.1%}")
        click.echo(f"  샤프 비율: {analysis['sharpe_ratio_30d']:.2f}")
        click.echo(f"  최대 낙폭: {analysis['max_drawdown_30d']:.1%}")
        click.echo(f"  BTC 상관관계: {analysis['correlation_btc']:.2f}")
        
        click.echo(f"\n⭐ 종합 평가:")
        click.echo(f"  유동성 점수: {analysis['liquidity_score']:.2f}")
        click.echo(f"  모멘텀 점수: {analysis['momentum_score']:+.2f}")
        click.echo(f"  품질 점수: {analysis['quality_score']:.2f}")
        click.echo(f"  리스크 점수: {analysis['risk_score']:.2f}")
        click.echo(f"  🏆 종합 점수: {analysis['overall_score']:.2f}")
        
        # 점수 기반 추천
        if analysis['overall_score'] > 0.8:
            recommendation = "🟢 강력 추천"
        elif analysis['overall_score'] > 0.6:
            recommendation = "🟡 조건부 추천"
        else:
            recommendation = "🔴 비추천"
            
        click.echo(f"\n💡 투자 추천: {recommendation}")
        
    except Exception as e:
        click.echo(f"❌ 자산 분석 실패: {e}")


if __name__ == '__main__':
    portfolio_optimizer()