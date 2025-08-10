"""
Backtesting Engine

KAIROS-1 투자 전략을 역사적 데이터로 검증하는 백테스팅 시스템
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import copy
from loguru import logger

from ..core.portfolio_manager import PortfolioManager, AssetAllocation
from ..core.market_season_filter import MarketSeasonFilter, MarketSeason
from ..core.dynamic_portfolio_optimizer import DynamicPortfolioOptimizer


class BacktestMode(Enum):
    """백테스팅 모드"""
    SIMPLE = "simple"           # 간단한 리밸런싱만
    ADVANCED = "advanced"       # 동적 최적화 포함
    COMPARISON = "comparison"   # 여러 전략 비교


@dataclass
class BacktestConfig:
    """백테스팅 설정"""
    start_date: str              # 시작일 (YYYY-MM-DD)
    end_date: str                # 종료일 (YYYY-MM-DD)
    initial_capital: float       # 초기 자본 (KRW)
    rebalance_frequency: str     # 리밸런싱 주기 (daily, weekly, monthly, quarterly)
    mode: BacktestMode          # 백테스팅 모드
    risk_level: str = "moderate" # 리스크 수준
    transaction_cost: float = 0.001  # 거래 수수료 (0.1%)
    slippage: float = 0.0005    # 슬리피지 (0.05%)
    
    # 고급 설정
    use_dynamic_optimization: bool = False
    max_drawdown_threshold: float = 0.20  # 20% 최대 낙폭 임계값
    stop_loss: Optional[float] = None     # 손절매 설정
    take_profit: Optional[float] = None   # 익절 설정


@dataclass
class Trade:
    """거래 기록"""
    timestamp: datetime
    asset: str
    side: str              # buy/sell
    quantity: float
    price: float
    amount_krw: float
    fee: float
    portfolio_value: float
    reason: str           # 거래 사유


@dataclass
class PerformanceMetrics:
    """성과 지표"""
    total_return: float          # 총 수익률
    annualized_return: float     # 연간 수익률
    volatility: float            # 변동성
    sharpe_ratio: float          # 샤프 비율
    max_drawdown: float          # 최대 낙폭
    win_rate: float              # 승률
    profit_factor: float         # 수익 팩터
    
    # 상세 지표
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    
    # 시기별 수익률
    monthly_returns: List[float] = field(default_factory=list)
    yearly_returns: List[float] = field(default_factory=list)


class BacktestingEngine:
    """
    백테스팅 엔진
    
    KAIROS-1 투자 전략의 역사적 성과를 분석합니다.
    """
    
    def __init__(
        self,
        config: BacktestConfig,
        historical_data: Optional[Dict[str, pd.DataFrame]] = None
    ):
        """
        Args:
            config: 백테스팅 설정
            historical_data: 역사적 가격 데이터 (asset -> DataFrame)
        """
        self.config = config
        self.historical_data = historical_data or {}
        
        # 포트폴리오 관리 구성 요소
        self.portfolio_manager = PortfolioManager(
            use_dynamic_optimization=config.use_dynamic_optimization,
            risk_level=config.risk_level
        )
        self.market_filter = MarketSeasonFilter()
        
        # 백테스팅 상태
        self.current_date = None
        self.portfolio_value_history = []
        self.portfolio_weights_history = []
        self.trade_history = []
        self.current_portfolio = {
            'total_krw': config.initial_capital,
            'assets': {'KRW': config.initial_capital}
        }
        
        # 성과 추적
        self.daily_returns = []
        self.benchmark_returns = []  # BTC 대비 성과
        
        logger.info(f"백테스팅 엔진 초기화: {config.start_date} ~ {config.end_date}")
        logger.info(f"초기 자본: {config.initial_capital:,.0f}원, 모드: {config.mode.value}")
    
    def load_historical_data(self, data_source: str = "yfinance") -> bool:
        """
        역사적 데이터 로드
        
        Args:
            data_source: 데이터 소스 (yfinance, coinone, binance 등)
            
        Returns:
            로드 성공 여부
        """
        try:
            logger.info(f"역사적 데이터 로드 시작 ({data_source})")
            
            if data_source == "yfinance":
                return self._load_yfinance_data()
            elif data_source == "demo":
                return self._load_demo_data()
            else:
                logger.error(f"지원하지 않는 데이터 소스: {data_source}")
                return False
                
        except Exception as e:
            logger.error(f"역사적 데이터 로드 실패: {e}")
            return False
    
    def _load_yfinance_data(self) -> bool:
        """Yahoo Finance에서 데이터 로드"""
        try:
            import yfinance as yf
            
            symbols = ["BTC-USD", "ETH-USD", "XRP-USD", "SOL-USD", "ADA-USD", "DOT-USD"]
            
            for symbol in symbols:
                asset = symbol.replace("-USD", "")
                ticker = yf.Ticker(symbol)
                
                # 기간 설정
                hist = ticker.history(
                    start=self.config.start_date,
                    end=self.config.end_date,
                    interval="1d"
                )
                
                if not hist.empty:
                    # USD 가격을 KRW로 변환 (간단히 1200배)
                    hist['Close'] = hist['Close'] * 1200
                    hist['Volume_KRW'] = hist['Volume'] * hist['Close']
                    
                    self.historical_data[asset] = hist
                    logger.info(f"{asset} 데이터 로드: {len(hist)}일")
                else:
                    logger.warning(f"{asset} 데이터 없음")
            
            return len(self.historical_data) > 0
            
        except ImportError:
            logger.error("yfinance 패키지가 필요합니다: pip install yfinance")
            return False
        except Exception as e:
            logger.error(f"yfinance 데이터 로드 실패: {e}")
            return False
    
    def _load_demo_data(self) -> bool:
        """데모용 모의 데이터 생성"""
        try:
            logger.info("데모 데이터 생성 (고정 시드 사용)")
            
            # 고정 시드 설정으로 일관된 결과 보장
            np.random.seed(42)
            
            start = pd.to_datetime(self.config.start_date)
            end = pd.to_datetime(self.config.end_date)
            dates = pd.date_range(start=start, end=end, freq='D')
            
            # 모의 암호화폐 데이터 생성
            assets = {
                'BTC': {'initial_price': 50000000, 'volatility': 0.04, 'drift': 0.0003},
                'ETH': {'initial_price': 2500000, 'volatility': 0.05, 'drift': 0.0004},
                'XRP': {'initial_price': 600, 'volatility': 0.06, 'drift': 0.0002},
                'SOL': {'initial_price': 150000, 'volatility': 0.07, 'drift': 0.0005}
            }
            
            for asset, params in assets.items():
                # 기하 브라운 운동으로 가격 생성
                returns = np.random.normal(
                    params['drift'], 
                    params['volatility'], 
                    len(dates)
                )
                
                prices = [params['initial_price']]
                for ret in returns:
                    new_price = prices[-1] * (1 + ret)
                    prices.append(max(new_price, prices[-1] * 0.8))  # 80% 이하 하락 방지
                
                prices = prices[1:]  # 첫 번째 가격 제거
                
                # DataFrame 생성
                df = pd.DataFrame({
                    'Close': prices,
                    'Volume': np.random.uniform(1e9, 10e9, len(dates)),
                    'High': [p * np.random.uniform(1.01, 1.05) for p in prices],
                    'Low': [p * np.random.uniform(0.95, 0.99) for p in prices]
                }, index=dates)
                
                self.historical_data[asset] = df
                logger.info(f"{asset} 데모 데이터 생성: {len(df)}일")
            
            return True
            
        except Exception as e:
            logger.error(f"데모 데이터 생성 실패: {e}")
            return False
    
    def run_backtest(self, calculate_benchmarks: bool = True) -> PerformanceMetrics:
        """
        백테스팅 실행
        
        Args:
            calculate_benchmarks: Buy-and-Hold 벤치마크 계산 여부
        
        Returns:
            성과 지표
        """
        try:
            logger.info("🚀 백테스팅 실행 시작")
            
            # 1. 데이터 검증
            if not self.historical_data:
                logger.error("역사적 데이터가 없습니다")
                raise ValueError("역사적 데이터가 필요합니다")
            
            # 2. 날짜 범위 설정
            start_date = pd.to_datetime(self.config.start_date)
            end_date = pd.to_datetime(self.config.end_date)
            
            # 3. 리밸런싱 주기 설정
            rebalance_dates = self._get_rebalance_dates(start_date, end_date)
            logger.info(f"리밸런싱 날짜: {len(rebalance_dates)}회")
            
            # 4. 일별 백테스팅 루프
            current_date = start_date
            last_rebalance_date = None
            
            while current_date <= end_date:
                try:
                    self.current_date = current_date
                    
                    # 해당 날짜의 가격 데이터 가져오기
                    daily_prices = self._get_daily_prices(current_date)
                    if not daily_prices:
                        current_date += timedelta(days=1)
                        continue
                    
                    # 포트폴리오 가치 업데이트
                    self._update_portfolio_value(daily_prices)
                    
                    # 리밸런싱 확인 및 실행
                    if current_date in rebalance_dates:
                        self._execute_rebalance(current_date, daily_prices)
                        last_rebalance_date = current_date
                    
                    # 일일 수익률 계산
                    self._calculate_daily_return()
                    
                    # 기록 저장
                    self._save_daily_record(current_date, daily_prices)
                    
                except Exception as e:
                    logger.warning(f"{current_date} 백테스팅 오류: {e}")
                
                current_date += timedelta(days=1)
            
            # 5. 최종 성과 계산
            performance = self._calculate_performance_metrics()
            
            # 6. Buy-and-Hold 벤치마크 계산
            if calculate_benchmarks:
                self.benchmarks = self._calculate_buy_and_hold_benchmarks()
                logger.info("\n📊 Buy-and-Hold 벤치마크와 비교:")
                for asset, benchmark in self.benchmarks.items():
                    logger.info(f"{asset}: {benchmark['total_return']:.2%} (연간: {benchmark['annualized_return']:.2%})")
                logger.info(f"전략 수익률: {performance.total_return:.2%} (연간: {performance.annualized_return:.2%})")
                
                # 전략이 벤치마크를 이긴 자산 계산
                outperformed = [asset for asset, bench in self.benchmarks.items() 
                              if performance.total_return > bench['total_return']]
                logger.info(f"전략이 우수한 자산: {', '.join(outperformed) if outperformed else '없음'}")
            
            logger.info("\n✅ 백테스팅 완료")
            logger.info(f"총 수익률: {performance.total_return:.2%}")
            logger.info(f"연간 수익률: {performance.annualized_return:.2%}")
            logger.info(f"샤프 비율: {performance.sharpe_ratio:.2f}")
            
            return performance
            
        except Exception as e:
            logger.error(f"백테스팅 실행 실패: {e}")
            raise
    
    def _get_rebalance_dates(self, start_date: pd.Timestamp, end_date: pd.Timestamp) -> List[pd.Timestamp]:
        """리밸런싱 날짜 목록 생성"""
        dates = []
        current = start_date
        
        if self.config.rebalance_frequency == "daily":
            freq = 'D'
        elif self.config.rebalance_frequency == "weekly":
            freq = 'W-MON'  # 매주 월요일
        elif self.config.rebalance_frequency == "monthly":
            freq = 'MS'     # 매월 첫날
        elif self.config.rebalance_frequency == "quarterly":
            freq = 'QS'     # 매분기 첫날
        else:
            freq = 'MS'     # 기본값: 월간
        
        dates = pd.date_range(start=start_date, end=end_date, freq=freq)
        return dates.tolist()
    
    def _get_daily_prices(self, date: pd.Timestamp) -> Dict[str, float]:
        """특정 날짜의 모든 자산 가격 조회"""
        prices = {}
        
        for asset, data in self.historical_data.items():
            try:
                if date in data.index:
                    prices[asset] = data.loc[date, 'Close']
                else:
                    # 가장 가까운 이전 날짜 사용
                    valid_dates = data.index[data.index <= date]
                    if len(valid_dates) > 0:
                        closest_date = valid_dates[-1]
                        prices[asset] = data.loc[closest_date, 'Close']
                        
            except Exception as e:
                logger.warning(f"{asset} {date} 가격 조회 실패: {e}")
                continue
        
        return prices
    
    def _update_portfolio_value(self, prices: Dict[str, float]):
        """현재 가격으로 포트폴리오 가치 업데이트"""
        total_value = 0
        updated_assets = {}
        
        # KRW 잔고
        krw_balance = self.current_portfolio['assets'].get('KRW', 0)
        updated_assets['KRW'] = krw_balance
        total_value += krw_balance
        
        # 암호화폐 자산들
        for asset, quantity in self.current_portfolio['assets'].items():
            if asset == 'KRW':
                continue
                
            if asset in prices:
                price = prices[asset]
                value = quantity * price
                updated_assets[asset] = quantity
                total_value += value
            else:
                # 가격 정보가 없으면 이전 가치 유지
                updated_assets[asset] = quantity
        
        self.current_portfolio['total_krw'] = total_value
        self.current_portfolio['assets'] = updated_assets
    
    def _execute_rebalance(self, date: pd.Timestamp, prices: Dict[str, float]):
        """리밸런싱 실행"""
        try:
            logger.info(f"🔄 {date.strftime('%Y-%m-%d')} 리밸런싱 실행 (전략: {self.config.risk_level})")
            
            # 1. 시장 계절 판단 (간단한 BTC 추세 기반)
            market_season = self._determine_market_season(date)
            
            # 2. 리스크 수준에 따른 기본 배분 설정
            if self.config.risk_level == "conservative":
                # 보수적: 낮은 암호화폐 비중
                base_allocation = 0.3
                risk_on_bonus = 0.1
                risk_off_penalty = 0.1
            elif self.config.risk_level == "aggressive":
                # 공격적: 높은 암호화폐 비중
                base_allocation = 0.7
                risk_on_bonus = 0.2
                risk_off_penalty = 0.2
            else:  # moderate
                # 중간: 균형잡힌 비중
                base_allocation = 0.5
                risk_on_bonus = 0.15
                risk_off_penalty = 0.15
            
            # 3. 시장 상황에 따른 조정
            if market_season == MarketSeason.RISK_ON:
                crypto_allocation = min(base_allocation + risk_on_bonus, 0.9)
            elif market_season == MarketSeason.RISK_OFF:
                crypto_allocation = max(base_allocation - risk_off_penalty, 0.1)
            else:
                crypto_allocation = base_allocation
            
            # 4. 전략별 자산 비중 조정
            if self.config.risk_level == "conservative":
                # 보수적: BTC/ETH 중심
                core_weight = 0.8  # Core 자산 비중 높임
                satellite_weight = 0.2
            elif self.config.risk_level == "aggressive":
                # 공격적: 고위험 자산 비중 증가
                core_weight = 0.5  # Core 자산 비중 낮춤
                satellite_weight = 0.5
            else:  # moderate
                core_weight = 0.7
                satellite_weight = 0.3
            
            # 5. 목표 비중 계산 (전략별 가중치 반영)
            target_weights = self._calculate_strategy_weights(
                crypto_allocation, core_weight, satellite_weight, prices
            )
            
            # 4. 현재 비중과 비교하여 주문 생성
            current_total = self.current_portfolio['total_krw']
            trades_executed = []
            
            for asset, target_weight in target_weights.items():
                if asset not in prices and asset != 'KRW':
                    continue
                    
                # 현재 보유량 및 가치
                current_quantity = self.current_portfolio['assets'].get(asset, 0)
                
                if asset == 'KRW':
                    current_value = current_quantity
                    target_value = target_weight * current_total
                    price = 1.0
                else:
                    price = prices[asset]
                    current_value = current_quantity * price
                    target_value = target_weight * current_total
                
                # 거래 필요량 계산
                value_diff = target_value - current_value
                
                # 임계값 확인 (총 자산의 1% 이상)
                if abs(value_diff) > current_total * 0.01:
                    trade = self._execute_trade(
                        date, asset, value_diff, price, 
                        f"Rebalance to {target_weight:.1%}"
                    )
                    if trade:
                        trades_executed.append(trade)
            
            logger.info(f"리밸런싱 완료: {len(trades_executed)}건 거래")
            
        except Exception as e:
            logger.error(f"리밸런싱 실행 실패: {e}")
    
    def _calculate_strategy_weights(
        self, 
        crypto_allocation: float, 
        core_weight: float, 
        satellite_weight: float,
        prices: Dict[str, float]
    ) -> Dict[str, float]:
        """전략별 자산 비중 계산"""
        weights = {}
        
        # KRW 비중
        weights['KRW'] = 1.0 - crypto_allocation
        
        # Core 자산 (BTC, ETH)
        core_assets = ['BTC', 'ETH']
        satellite_assets = ['XRP', 'SOL']
        
        # 가격이 있는 자산만 필터링
        available_core = [a for a in core_assets if a in prices]
        available_satellite = [a for a in satellite_assets if a in prices]
        
        # Core 자산 비중 분배
        if available_core:
            core_allocation = crypto_allocation * core_weight
            per_core_weight = core_allocation / len(available_core)
            for asset in available_core:
                weights[asset] = per_core_weight
        
        # Satellite 자산 비중 분배
        if available_satellite:
            satellite_allocation = crypto_allocation * satellite_weight
            per_satellite_weight = satellite_allocation / len(available_satellite)
            for asset in available_satellite:
                weights[asset] = per_satellite_weight
        
        return weights
    
    def _execute_trade(
        self, 
        date: pd.Timestamp, 
        asset: str, 
        amount_diff: float, 
        price: float,
        reason: str
    ) -> Optional[Trade]:
        """거래 실행"""
        try:
            if amount_diff > 0:
                # 매수
                side = "buy"
                amount_krw = amount_diff
                
                # 수수료 및 슬리피지 적용
                total_cost = amount_krw * (1 + self.config.transaction_cost + self.config.slippage)
                
                # KRW 잔고 확인
                krw_balance = self.current_portfolio['assets'].get('KRW', 0)
                if krw_balance < total_cost:
                    logger.warning(f"{asset} 매수 실패: KRW 잔고 부족")
                    return None
                
                if asset == 'KRW':
                    # KRW는 별도 처리 (실제로는 다른 자산 매도의 결과)
                    return None
                else:
                    # 암호화폐 매수
                    quantity = amount_krw / price
                    fee = total_cost - amount_krw
                    
                    # 포트폴리오 업데이트
                    self.current_portfolio['assets']['KRW'] -= total_cost
                    current_quantity = self.current_portfolio['assets'].get(asset, 0)
                    self.current_portfolio['assets'][asset] = current_quantity + quantity
                    
            else:
                # 매도
                side = "sell"
                amount_krw = abs(amount_diff)
                
                if asset == 'KRW':
                    return None
                else:
                    quantity_to_sell = amount_krw / price
                    current_quantity = self.current_portfolio['assets'].get(asset, 0)
                    
                    if current_quantity < quantity_to_sell:
                        logger.warning(f"{asset} 매도 실패: 보유량 부족")
                        return None
                    
                    # 수수료 및 슬리피지 적용
                    net_proceeds = amount_krw * (1 - self.config.transaction_cost - self.config.slippage)
                    fee = amount_krw - net_proceeds
                    
                    # 포트폴리오 업데이트
                    self.current_portfolio['assets'][asset] -= quantity_to_sell
                    self.current_portfolio['assets']['KRW'] += net_proceeds
                    quantity = quantity_to_sell
            
            # 거래 기록 생성
            trade = Trade(
                timestamp=date,
                asset=asset,
                side=side,
                quantity=quantity,
                price=price,
                amount_krw=amount_krw,
                fee=fee,
                portfolio_value=self.current_portfolio['total_krw'],
                reason=reason
            )
            
            self.trade_history.append(trade)
            logger.debug(f"{asset} {side} {amount_krw:,.0f}원 (수수료: {fee:,.0f}원)")
            
            return trade
            
        except Exception as e:
            logger.error(f"거래 실행 실패 ({asset}): {e}")
            return None
    
    def _determine_market_season(self, date: pd.Timestamp) -> MarketSeason:
        """시장 계절 판단 (BTC 기준)"""
        try:
            if 'BTC' not in self.historical_data:
                return MarketSeason.NEUTRAL
            
            btc_data = self.historical_data['BTC']
            
            # 30일 이전 데이터까지 확인
            end_date = date
            start_date = date - timedelta(days=30)
            
            recent_data = btc_data[(btc_data.index >= start_date) & (btc_data.index <= end_date)]
            
            if len(recent_data) < 10:  # 최소 10일 데이터 필요
                return MarketSeason.NEUTRAL
            
            # 30일 수익률 계산
            first_price = recent_data.iloc[0]['Close']
            last_price = recent_data.iloc[-1]['Close']
            return_30d = (last_price - first_price) / first_price
            
            # 시장 계절 판단
            if return_30d > 0.20:  # 20% 이상 상승
                return MarketSeason.RISK_ON
            elif return_30d < -0.20:  # 20% 이상 하락
                return MarketSeason.RISK_OFF
            else:
                return MarketSeason.NEUTRAL
                
        except Exception as e:
            logger.warning(f"시장 계절 판단 실패: {e}")
            return MarketSeason.NEUTRAL
    
    def _calculate_daily_return(self):
        """일일 수익률 계산"""
        if len(self.portfolio_value_history) > 0:
            previous_value = self.portfolio_value_history[-1]['total_value']
            current_value = self.current_portfolio['total_krw']
            daily_return = (current_value - previous_value) / previous_value
            self.daily_returns.append(daily_return)
        else:
            self.daily_returns.append(0.0)
    
    def _save_daily_record(self, date: pd.Timestamp, prices: Dict[str, float]):
        """일일 기록 저장"""
        # 포트폴리오 가치 기록
        self.portfolio_value_history.append({
            'date': date,
            'total_value': self.current_portfolio['total_krw'],
            'assets': copy.deepcopy(self.current_portfolio['assets'])
        })
        
        # 포트폴리오 비중 기록
        total_value = self.current_portfolio['total_krw']
        weights = {}
        
        for asset, quantity in self.current_portfolio['assets'].items():
            if asset == 'KRW':
                weights[asset] = quantity / total_value
            elif asset in prices:
                value = quantity * prices[asset]
                weights[asset] = value / total_value
            else:
                weights[asset] = 0
        
        self.portfolio_weights_history.append({
            'date': date,
            'weights': weights
        })
    
    def _calculate_performance_metrics(self) -> PerformanceMetrics:
        """최종 성과 지표 계산"""
        try:
            if not self.daily_returns or len(self.portfolio_value_history) < 2:
                raise ValueError("충분한 데이터가 없습니다")
            
            # 기본 수익률 계산
            initial_value = self.config.initial_capital
            final_value = self.portfolio_value_history[-1]['total_value']
            total_return = (final_value - initial_value) / initial_value
            
            # 기간 계산
            start_date = pd.to_datetime(self.config.start_date)
            end_date = pd.to_datetime(self.config.end_date)
            days = (end_date - start_date).days
            years = days / 365.25
            
            # 연간 수익률
            annualized_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else total_return
            
            # 변동성 (일일 수익률 표준편차 * sqrt(252))
            returns_array = np.array(self.daily_returns)
            volatility = np.std(returns_array) * np.sqrt(252)
            
            # 샤프 비율 (무위험 수익률 2% 가정)
            risk_free_rate = 0.02
            excess_return = annualized_return - risk_free_rate
            sharpe_ratio = excess_return / volatility if volatility > 0 else 0
            
            # 최대 낙폭 계산
            values = [record['total_value'] for record in self.portfolio_value_history]
            peak = values[0]
            max_drawdown = 0
            
            for value in values:
                if value > peak:
                    peak = value
                drawdown = (peak - value) / peak
                max_drawdown = max(max_drawdown, drawdown)
            
            # 거래 분석
            profitable_trades = [t for t in self.trade_history 
                               if self._is_profitable_trade(t)]
            
            win_rate = len(profitable_trades) / len(self.trade_history) if self.trade_history else 0
            
            # 월별/연별 수익률
            monthly_returns = self._calculate_period_returns('M')
            yearly_returns = self._calculate_period_returns('Y')
            
            return PerformanceMetrics(
                total_return=total_return,
                annualized_return=annualized_return,
                volatility=volatility,
                sharpe_ratio=sharpe_ratio,
                max_drawdown=max_drawdown,
                win_rate=win_rate,
                profit_factor=self._calculate_profit_factor(),
                total_trades=len(self.trade_history),
                winning_trades=len(profitable_trades),
                losing_trades=len(self.trade_history) - len(profitable_trades),
                avg_win=self._calculate_avg_win(),
                avg_loss=self._calculate_avg_loss(),
                largest_win=self._calculate_largest_win(),
                largest_loss=self._calculate_largest_loss(),
                monthly_returns=monthly_returns,
                yearly_returns=yearly_returns
            )
            
        except Exception as e:
            logger.error(f"성과 지표 계산 실패: {e}")
            raise
    
    def _is_profitable_trade(self, trade: Trade) -> bool:
        """거래가 수익성이 있는지 판단 (간단한 구현)"""
        # 실제로는 더 복잡한 로직이 필요 (매수-매도 쌍 추적)
        return True  # 임시로 모든 거래를 수익성 있다고 가정
    
    def _calculate_profit_factor(self) -> float:
        """수익 팩터 계산"""
        total_profit = sum(t.amount_krw for t in self.trade_history if t.side == 'sell')
        total_loss = sum(t.amount_krw for t in self.trade_history if t.side == 'buy')
        return total_profit / total_loss if total_loss > 0 else 0
    
    def _calculate_avg_win(self) -> float:
        """평균 수익 거래"""
        profitable = [t for t in self.trade_history if self._is_profitable_trade(t)]
        return np.mean([t.amount_krw for t in profitable]) if profitable else 0
    
    def _calculate_avg_loss(self) -> float:
        """평균 손실 거래"""
        losing = [t for t in self.trade_history if not self._is_profitable_trade(t)]
        return np.mean([t.amount_krw for t in losing]) if losing else 0
    
    def _calculate_largest_win(self) -> float:
        """최대 수익 거래"""
        if not self.trade_history:
            return 0
        return max(t.amount_krw for t in self.trade_history)
    
    def _calculate_largest_loss(self) -> float:
        """최대 손실 거래"""
        if not self.trade_history:
            return 0
        return min(t.amount_krw for t in self.trade_history)
    
    def _calculate_period_returns(self, period: str) -> List[float]:
        """기간별 수익률 계산"""
        try:
            df = pd.DataFrame([
                {'date': record['date'], 'value': record['total_value']}
                for record in self.portfolio_value_history
            ])
            df.set_index('date', inplace=True)
            
            if period == 'M':
                resampled = df.resample('M').last()
            else:  # 'Y'
                resampled = df.resample('Y').last()
            
            returns = resampled['value'].pct_change().dropna().tolist()
            return returns
            
        except Exception as e:
            logger.warning(f"기간별 수익률 계산 실패: {e}")
            return []
    
    def get_portfolio_history(self) -> pd.DataFrame:
        """포트폴리오 가치 히스토리를 DataFrame으로 반환"""
        return pd.DataFrame([
            {
                'date': record['date'],
                'total_value': record['total_value'],
                'daily_return': ret
            }
            for record, ret in zip(self.portfolio_value_history, [0] + self.daily_returns)
        ])
    
    def get_trade_history(self) -> pd.DataFrame:
        """거래 히스토리를 DataFrame으로 반환"""
        if not self.trade_history:
            return pd.DataFrame()
        
        return pd.DataFrame([
            {
                'timestamp': trade.timestamp,
                'asset': trade.asset,
                'side': trade.side,
                'quantity': trade.quantity,
                'price': trade.price,
                'amount_krw': trade.amount_krw,
                'fee': trade.fee,
                'reason': trade.reason
            }
            for trade in self.trade_history
        ])
    
    def _calculate_buy_and_hold_benchmarks(self) -> Dict[str, Dict[str, float]]:
        """Buy-and-Hold 벤치마크 계산"""
        benchmarks = {}
        
        try:
            start_date = pd.to_datetime(self.config.start_date)
            end_date = pd.to_datetime(self.config.end_date)
            days = (end_date - start_date).days
            years = days / 365.25
            
            # 각 자산별 Buy-and-Hold 수익률 계산
            for asset, data in self.historical_data.items():
                try:
                    # 시작일과 종료일의 가격 찾기
                    start_prices = data[data.index >= start_date]
                    end_prices = data[data.index <= end_date]
                    
                    if len(start_prices) > 0 and len(end_prices) > 0:
                        initial_price = start_prices.iloc[0]['Close']
                        final_price = end_prices.iloc[-1]['Close']
                        
                        # 총 수익률
                        total_return = (final_price - initial_price) / initial_price
                        
                        # 연간 수익률
                        annualized_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else total_return
                        
                        # 변동성 계산
                        returns = data['Close'].pct_change().dropna()
                        volatility = returns.std() * np.sqrt(252)
                        
                        # 샤프 비율
                        risk_free_rate = 0.02
                        sharpe_ratio = (annualized_return - risk_free_rate) / volatility if volatility > 0 else 0
                        
                        # 최대 낙폭
                        peak = data['Close'].expanding().max()
                        drawdown = (data['Close'] - peak) / peak
                        max_drawdown = drawdown.min()
                        
                        benchmarks[asset] = {
                            'total_return': total_return,
                            'annualized_return': annualized_return,
                            'volatility': volatility,
                            'sharpe_ratio': sharpe_ratio,
                            'max_drawdown': max_drawdown,
                            'initial_price': initial_price,
                            'final_price': final_price
                        }
                        
                        logger.debug(f"{asset} Buy-and-Hold: {total_return:.2%} (연간: {annualized_return:.2%})")
                        
                except Exception as e:
                    logger.warning(f"{asset} 벤치마크 계산 실패: {e}")
                    continue
            
            # 균등 가중 포트폴리오 벤치마크
            if benchmarks:
                equal_weight_return = np.mean([b['total_return'] for b in benchmarks.values()])
                equal_weight_annual = np.mean([b['annualized_return'] for b in benchmarks.values()])
                equal_weight_volatility = np.mean([b['volatility'] for b in benchmarks.values()])
                equal_weight_sharpe = (equal_weight_annual - 0.02) / equal_weight_volatility if equal_weight_volatility > 0 else 0
                
                benchmarks['EQUAL_WEIGHT'] = {
                    'total_return': equal_weight_return,
                    'annualized_return': equal_weight_annual,
                    'volatility': equal_weight_volatility,
                    'sharpe_ratio': equal_weight_sharpe,
                    'max_drawdown': np.mean([b['max_drawdown'] for b in benchmarks.values() if 'max_drawdown' in b])
                }
                
                logger.info(f"균등 가중 포트폴리오: {equal_weight_return:.2%} (연간: {equal_weight_annual:.2%})")
            
            return benchmarks
            
        except Exception as e:
            logger.error(f"벤치마크 계산 실패: {e}")
            return {}
    
    def get_benchmark_comparison(self) -> Dict[str, Any]:
        """전략과 벤치마크 비교 데이터 반환"""
        if not hasattr(self, 'benchmarks'):
            return {"error": "벤치마크 계산이 필요합니다"}
        
        performance = self._calculate_performance_metrics()
        
        comparison = {
            'strategy': {
                'total_return': performance.total_return,
                'annualized_return': performance.annualized_return,
                'sharpe_ratio': performance.sharpe_ratio,
                'max_drawdown': performance.max_drawdown,
                'volatility': performance.volatility
            },
            'benchmarks': self.benchmarks,
            'outperformance': {}
        }
        
        # 각 벤치마크 대비 초과 수익률 계산
        for asset, benchmark in self.benchmarks.items():
            comparison['outperformance'][asset] = {
                'return_diff': performance.total_return - benchmark['total_return'],
                'sharpe_diff': performance.sharpe_ratio - benchmark['sharpe_ratio'],
                'is_better': performance.total_return > benchmark['total_return']
            }
        
        return comparison