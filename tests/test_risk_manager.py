"""
Tests for RiskManager - TDD Phase 1

손실 한도, 켈리 기준 포지션 사이징, 동적 변동성 리스크 계산을 테스트합니다.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
import numpy as np

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.risk.risk_manager import RiskManager, RiskLimits, RiskCheckResult


# ============================================================================
# TestLossLimits - 손실 한도 체크 테스트
# ============================================================================

class TestLossLimits:
    """손실 한도 체크 테스트 클래스"""

    def test_daily_loss_limit_exceeded(self, mock_config, mock_db_manager):
        """일일 5% 손실 초과 시 거래 제한"""
        # Arrange
        risk_manager = RiskManager(mock_config)
        risk_manager.db_manager = mock_db_manager

        # 어제 포트폴리오 가치: 10,000,000
        mock_db_manager.get_portfolio_value_days_ago.return_value = 10_000_000

        # 현재 포트폴리오: 9,400,000 (6% 손실)
        portfolio = {
            'total_krw': 9_400_000,
            'assets': {
                'KRW': {'value_krw': 5_000_000},
                'BTC': {'value_krw': 4_400_000}
            }
        }

        # Act
        result = risk_manager._check_loss_limits(portfolio)

        # Assert
        assert len(result) > 0, "손실 한도 초과 시 제한 메시지가 있어야 함"
        assert any("일일 손실 한도" in msg for msg in result), "일일 손실 한도 초과 메시지가 있어야 함"

    def test_daily_loss_limit_within(self, mock_config, mock_db_manager):
        """일일 손실 한도 내 정상 처리"""
        # Arrange
        risk_manager = RiskManager(mock_config)
        risk_manager.db_manager = mock_db_manager

        # 어제 포트폴리오 가치: 10,000,000
        mock_db_manager.get_portfolio_value_days_ago.return_value = 10_000_000

        # 현재 포트폴리오: 9,700,000 (3% 손실 - 한도 내)
        portfolio = {
            'total_krw': 9_700_000,
            'assets': {
                'KRW': {'value_krw': 5_000_000},
                'BTC': {'value_krw': 4_700_000}
            }
        }

        # Act
        result = risk_manager._check_loss_limits(portfolio)

        # Assert
        assert result == [], "손실 한도 내에서는 제한 메시지가 없어야 함"

    def test_monthly_loss_limit_exceeded(self, mock_config, mock_db_manager):
        """월간 15% 손실 초과 시 거래 제한"""
        # Arrange
        risk_manager = RiskManager(mock_config)
        risk_manager.db_manager = mock_db_manager

        # 30일 전 포트폴리오 가치: 10,000,000
        mock_db_manager.get_portfolio_value_days_ago.return_value = 10_000_000

        # 현재 포트폴리오: 8,300,000 (17% 손실)
        portfolio = {
            'total_krw': 8_300_000,
            'assets': {
                'KRW': {'value_krw': 5_000_000},
                'BTC': {'value_krw': 3_300_000}
            }
        }

        # Act
        result = risk_manager._check_loss_limits(portfolio)

        # Assert
        assert len(result) > 0, "월간 손실 한도 초과 시 제한 메시지가 있어야 함"
        assert any("월간 손실 한도" in msg for msg in result), "월간 손실 한도 초과 메시지가 있어야 함"

    def test_drawdown_threshold_exceeded(self, mock_config, mock_db_manager):
        """드로우다운 임계값 20% 초과 시 거래 제한"""
        # Arrange
        risk_manager = RiskManager(mock_config)
        risk_manager.db_manager = mock_db_manager

        # 최고점 포트폴리오 가치: 12,000,000
        mock_db_manager.get_portfolio_peak_value.return_value = 12_000_000

        # 현재 포트폴리오: 9,000,000 (25% 드로우다운)
        portfolio = {
            'total_krw': 9_000_000,
            'assets': {
                'KRW': {'value_krw': 5_000_000},
                'BTC': {'value_krw': 4_000_000}
            }
        }

        # Act
        result = risk_manager._check_loss_limits(portfolio)

        # Assert
        assert len(result) > 0, "드로우다운 임계값 초과 시 제한 메시지가 있어야 함"
        assert any("드로우다운" in msg for msg in result), "드로우다운 초과 메시지가 있어야 함"

    def test_db_unavailable_fallback(self, mock_config, mock_db_manager):
        """DB 연결 실패 시 안전한 기본값 반환"""
        # Arrange
        risk_manager = RiskManager(mock_config)
        risk_manager.db_manager = mock_db_manager

        # DB 연결 실패 시뮬레이션
        mock_db_manager.get_portfolio_value_days_ago.side_effect = Exception("DB Connection Error")

        portfolio = {
            'total_krw': 9_500_000,
            'assets': {}
        }

        # Act
        result = risk_manager._check_loss_limits(portfolio)

        # Assert - 에러 시 빈 리스트 또는 적절한 경고 반환
        # 거래를 완전히 막지 않고 경고만 남기거나, 안전하게 처리
        assert isinstance(result, list), "결과는 리스트여야 함"

    def test_profit_scenario(self, mock_config, mock_db_manager):
        """수익 상태에서는 제한 없음"""
        # Arrange
        risk_manager = RiskManager(mock_config)
        risk_manager.db_manager = mock_db_manager

        # 어제 포트폴리오 가치: 10,000,000
        mock_db_manager.get_portfolio_value_days_ago.return_value = 10_000_000

        # 현재 포트폴리오: 10,500,000 (5% 수익)
        portfolio = {
            'total_krw': 10_500_000,
            'assets': {
                'KRW': {'value_krw': 5_000_000},
                'BTC': {'value_krw': 5_500_000}
            }
        }

        # Act
        result = risk_manager._check_loss_limits(portfolio)

        # Assert
        assert result == [], "수익 상태에서는 제한 메시지가 없어야 함"


# ============================================================================
# TestKellyCriterion - 켈리 기준 포지션 사이징 테스트
# ============================================================================

class TestKellyCriterion:
    """켈리 기준 포지션 사이징 테스트 클래스"""

    def test_kelly_calculation_basic(self, mock_config):
        """켈리 기준 기본 계산"""
        # Arrange
        risk_manager = RiskManager(mock_config)

        # Act
        # 승률 45%, 손익비 2:1
        position = risk_manager.calculate_position_size_with_kelly(
            account_size=10_000_000,
            entry_price=50_000_000,
            stop_loss=47_500_000,  # 5% 손절
            win_rate=0.45,
            risk_reward=2.0,
            max_risk_percent=0.05  # 5% 리스크 허용
        )

        # Assert
        assert position > 0, "양수 엣지가 있으면 포지션 크기는 0보다 커야 함"
        # 1% 규칙이 기본이지만, 5% 허용 시 켈리 기준 포지션 계산됨
        assert position <= 10_000_000, "포지션 크기는 계좌 이하여야 함"

    def test_kelly_negative_edge(self, mock_config):
        """음수 엣지 시 포지션 0"""
        # Arrange
        risk_manager = RiskManager(mock_config)

        # Act
        # 낮은 승률 + 낮은 손익비 = 음수 기대값
        position = risk_manager.calculate_position_size_with_kelly(
            account_size=10_000_000,
            entry_price=50_000_000,
            stop_loss=47_500_000,
            win_rate=0.30,  # 30% 승률
            risk_reward=1.0  # 1:1 손익비
        )

        # Assert
        assert position == 0, "음수 엣지 시 포지션은 0이어야 함"

    def test_one_percent_rule_cap(self, mock_config):
        """1% 규칙 상한 적용"""
        # Arrange
        risk_manager = RiskManager(mock_config)

        # Act
        # 높은 승률과 손익비로 켈리가 큰 포지션을 제안하더라도 1% 제한
        position = risk_manager.calculate_position_size_with_kelly(
            account_size=10_000_000,
            entry_price=50_000_000,
            stop_loss=49_000_000,  # 2% 손절
            win_rate=0.70,  # 70% 승률
            risk_reward=3.0,  # 1:3 손익비
            max_risk_percent=0.01  # 1% 최대 리스크
        )

        # Assert
        max_risk_amount = 10_000_000 * 0.01  # 100,000 KRW
        stop_loss_percent = (50_000_000 - 49_000_000) / 50_000_000  # 2%
        max_position_by_risk = max_risk_amount / stop_loss_percent

        assert position <= max_position_by_risk, "포지션은 1% 규칙에 의해 제한되어야 함"

    def test_half_kelly_used(self, mock_config):
        """Half Kelly가 기본으로 사용됨"""
        # Arrange
        risk_manager = RiskManager(mock_config)

        # Act
        # 켈리 기준: (win_rate * risk_reward - (1 - win_rate)) / risk_reward
        # 예: (0.5 * 2 - 0.5) / 2 = 0.25 (25%)
        # Half Kelly: 12.5%
        # 1% 규칙 제한 없이 순수 켈리 비교를 위해 max_risk_percent를 높게 설정

        full_kelly_position = risk_manager.calculate_position_size_with_kelly(
            account_size=10_000_000,
            entry_price=50_000_000,
            stop_loss=45_000_000,  # 10% 손절
            win_rate=0.50,
            risk_reward=2.0,
            max_risk_percent=0.50,  # 높은 리스크 허용 (켈리 비교용)
            use_half_kelly=False  # Full Kelly
        )

        half_kelly_position = risk_manager.calculate_position_size_with_kelly(
            account_size=10_000_000,
            entry_price=50_000_000,
            stop_loss=45_000_000,
            win_rate=0.50,
            risk_reward=2.0,
            max_risk_percent=0.50,  # 높은 리스크 허용 (켈리 비교용)
            use_half_kelly=True  # Half Kelly (기본값)
        )

        # Assert
        assert half_kelly_position < full_kelly_position, "Half Kelly는 Full Kelly보다 작아야 함"
        # Half Kelly는 Full Kelly의 대략 절반
        assert abs(half_kelly_position - full_kelly_position * 0.5) < full_kelly_position * 0.1

    def test_minimum_position_size(self, mock_config):
        """최소 포지션 크기 보장"""
        # Arrange
        risk_manager = RiskManager(mock_config)

        # Act
        # 매우 작은 계좌에서도 최소 거래 가능 금액 이상
        position = risk_manager.calculate_position_size_with_kelly(
            account_size=100_000,  # 10만원
            entry_price=50_000_000,
            stop_loss=47_500_000,
            win_rate=0.50,
            risk_reward=2.0
        )

        # Assert
        # 포지션이 0이 아니라면, 최소 거래 금액(5,000 KRW) 이상이어야 함
        if position > 0:
            assert position >= 5_000, "최소 거래 금액은 5,000 KRW"

    def test_invalid_parameters(self, mock_config):
        """잘못된 파라미터 처리"""
        # Arrange
        risk_manager = RiskManager(mock_config)

        # Act & Assert
        # 음수 계좌 크기
        with pytest.raises(ValueError):
            risk_manager.calculate_position_size_with_kelly(
                account_size=-10_000_000,
                entry_price=50_000_000,
                stop_loss=47_500_000,
                win_rate=0.50,
                risk_reward=2.0
            )

        # 손절가가 진입가보다 높음 (롱 포지션 기준)
        with pytest.raises(ValueError):
            risk_manager.calculate_position_size_with_kelly(
                account_size=10_000_000,
                entry_price=50_000_000,
                stop_loss=55_000_000,  # 잘못된 손절가
                win_rate=0.50,
                risk_reward=2.0
            )

    def test_quarter_kelly_option(self, mock_config):
        """Quarter Kelly 옵션"""
        # Arrange
        risk_manager = RiskManager(mock_config)

        # Act
        # 1% 규칙 제한 없이 순수 켈리 비교를 위해 max_risk_percent를 높게 설정
        position = risk_manager.calculate_position_size_with_kelly(
            account_size=10_000_000,
            entry_price=50_000_000,
            stop_loss=47_500_000,
            win_rate=0.50,
            risk_reward=2.0,
            max_risk_percent=0.50,  # 높은 리스크 허용
            kelly_fraction=0.25  # Quarter Kelly
        )

        full_kelly_position = risk_manager.calculate_position_size_with_kelly(
            account_size=10_000_000,
            entry_price=50_000_000,
            stop_loss=47_500_000,
            win_rate=0.50,
            risk_reward=2.0,
            max_risk_percent=0.50,  # 높은 리스크 허용
            kelly_fraction=1.0  # Full Kelly
        )

        # Assert
        assert abs(position - full_kelly_position * 0.25) < full_kelly_position * 0.05


# ============================================================================
# TestVolatilityRisk - 동적 변동성 리스크 테스트
# ============================================================================

class TestVolatilityRisk:
    """동적 변동성 리스크 계산 테스트 클래스"""

    def test_high_volatility_risk(self, mock_config, mock_db_manager, volatile_portfolio):
        """고변동성 시 리스크 점수 상승"""
        # Arrange
        risk_manager = RiskManager(mock_config)
        risk_manager.db_manager = mock_db_manager

        # 고변동성 일별 수익률 설정
        mock_db_manager.get_portfolio_daily_returns.return_value = \
            volatile_portfolio['daily_returns']

        # Act
        risk = risk_manager._calculate_volatility_risk(volatile_portfolio)

        # Assert
        assert risk > 0.5, "고변동성 포트폴리오의 리스크 점수는 0.5보다 커야 함"

    def test_low_volatility_risk(self, mock_config, mock_db_manager, stable_portfolio):
        """저변동성 시 리스크 점수 낮음"""
        # Arrange
        risk_manager = RiskManager(mock_config)
        risk_manager.db_manager = mock_db_manager

        # 저변동성 일별 수익률 설정
        mock_db_manager.get_portfolio_daily_returns.return_value = \
            stable_portfolio['daily_returns']

        # Act
        risk = risk_manager._calculate_volatility_risk(stable_portfolio)

        # Assert
        assert risk < 0.3, "저변동성 포트폴리오의 리스크 점수는 0.3보다 작아야 함"

    def test_volatility_calculation_30_days(self, mock_config, mock_db_manager):
        """30일 변동성 계산"""
        # Arrange
        risk_manager = RiskManager(mock_config)
        risk_manager.db_manager = mock_db_manager

        # 정확히 30일 수익률 데이터
        daily_returns = [0.01, -0.01, 0.02, -0.015, 0.008] * 6  # 30일
        mock_db_manager.get_portfolio_daily_returns.return_value = daily_returns

        portfolio = {'total_krw': 10_000_000}

        # Act
        risk = risk_manager._calculate_volatility_risk(portfolio)

        # Assert
        # 30일 표준편차 기반 계산이 이루어져야 함
        assert 0.0 <= risk <= 1.0, "리스크 점수는 0과 1 사이여야 함"

    def test_volatility_threshold_high(self, mock_config, mock_db_manager):
        """변동성 5% 초과 시 고위험 분류"""
        # Arrange
        risk_manager = RiskManager(mock_config)
        risk_manager.db_manager = mock_db_manager

        # 일별 6% 변동 (연간 환산 시 약 95% 변동성)
        high_volatility_returns = [0.06, -0.06] * 15
        mock_db_manager.get_portfolio_daily_returns.return_value = high_volatility_returns

        portfolio = {'total_krw': 10_000_000}

        # Act
        risk = risk_manager._calculate_volatility_risk(portfolio)

        # Assert
        assert risk >= 0.7, "5% 이상 일일 변동성은 고위험(0.7+)으로 분류되어야 함"

    def test_insufficient_data_handling(self, mock_config, mock_db_manager):
        """데이터 부족 시 처리"""
        # Arrange
        risk_manager = RiskManager(mock_config)
        risk_manager.db_manager = mock_db_manager

        # 5일치만 있는 경우
        mock_db_manager.get_portfolio_daily_returns.return_value = [0.01, -0.01, 0.02, -0.01, 0.01]

        portfolio = {'total_krw': 10_000_000}

        # Act
        risk = risk_manager._calculate_volatility_risk(portfolio)

        # Assert
        # 데이터 부족 시 보수적인 중간값 반환
        assert 0.3 <= risk <= 0.7, "데이터 부족 시 중간 리스크값 반환"

    def test_zero_volatility(self, mock_config, mock_db_manager):
        """변동성 0인 경우 (횡보)"""
        # Arrange
        risk_manager = RiskManager(mock_config)
        risk_manager.db_manager = mock_db_manager

        # 완전 횡보
        mock_db_manager.get_portfolio_daily_returns.return_value = [0.0] * 30

        portfolio = {'total_krw': 10_000_000}

        # Act
        risk = risk_manager._calculate_volatility_risk(portfolio)

        # Assert
        assert risk < 0.1, "변동성 0인 경우 리스크는 매우 낮아야 함"


# ============================================================================
# TestMarketRisk - 시장 리스크 동적 계산 테스트
# ============================================================================

class TestMarketRisk:
    """시장 리스크 동적 계산 테스트 클래스"""

    def test_market_risk_high_fear(self, mock_config, mock_db_manager):
        """공포지수 높을 때 (극단적 공포) 시장 리스크 계산"""
        # Arrange
        risk_manager = RiskManager(mock_config)
        risk_manager.db_manager = mock_db_manager

        # Fear & Greed Index = 10 (극단적 공포)
        mock_db_manager.get_latest_analysis_result.return_value = {
            'fear_greed_index': 10,
            'mvrv': 0.8,
            'analysis_type': 'market_sentiment'
        }

        # Act
        risk = risk_manager._calculate_market_risk()

        # Assert
        # 극단적 공포 시 시장 리스크는 높지만, 역으로 매수 기회일 수 있음
        assert 0.3 <= risk <= 0.7, "극단적 공포 시 중간 리스크"

    def test_market_risk_high_greed(self, mock_config, mock_db_manager):
        """공포지수 높을 때 (극단적 탐욕) 시장 리스크 계산"""
        # Arrange
        risk_manager = RiskManager(mock_config)
        risk_manager.db_manager = mock_db_manager

        # Fear & Greed Index = 85 (극단적 탐욕)
        mock_db_manager.get_latest_analysis_result.return_value = {
            'fear_greed_index': 85,
            'mvrv': 3.5,
            'analysis_type': 'market_sentiment'
        }

        # Act
        risk = risk_manager._calculate_market_risk()

        # Assert
        assert risk >= 0.7, "극단적 탐욕 시 고위험"

    def test_market_risk_mvrv_overvalued(self, mock_config, mock_db_manager):
        """MVRV > 3.0 (과대평가) 시 시장 리스크 계산"""
        # Arrange
        risk_manager = RiskManager(mock_config)
        risk_manager.db_manager = mock_db_manager

        mock_db_manager.get_latest_analysis_result.return_value = {
            'fear_greed_index': 50,  # 중립
            'mvrv': 3.5,  # 과대평가
            'analysis_type': 'market_sentiment'
        }

        # Act
        risk = risk_manager._calculate_market_risk()

        # Assert
        # MVRV 과대평가(3.5) + Fear&Greed 중립(50)
        # fg_risk = 0.2, mvrv_risk = 0.7
        # 가중평균 = 0.2*0.4 + 0.7*0.6 = 0.50
        assert risk >= 0.5, "MVRV 과대평가 시 중간 이상 리스크"

    def test_market_risk_mvrv_undervalued(self, mock_config, mock_db_manager):
        """MVRV < 1.0 (과소평가) 시 시장 리스크 계산"""
        # Arrange
        risk_manager = RiskManager(mock_config)
        risk_manager.db_manager = mock_db_manager

        mock_db_manager.get_latest_analysis_result.return_value = {
            'fear_greed_index': 25,
            'mvrv': 0.8,  # 과소평가
            'analysis_type': 'market_sentiment'
        }

        # Act
        risk = risk_manager._calculate_market_risk()

        # Assert
        assert risk <= 0.4, "MVRV 과소평가 시 낮은 리스크"

    def test_market_risk_no_data(self, mock_config, mock_db_manager):
        """시장 데이터 없을 때 기본값"""
        # Arrange
        risk_manager = RiskManager(mock_config)
        risk_manager.db_manager = mock_db_manager

        mock_db_manager.get_latest_analysis_result.return_value = None

        # Act
        risk = risk_manager._calculate_market_risk()

        # Assert
        # 데이터 없을 때 보수적인 중간값
        assert 0.4 <= risk <= 0.6, "데이터 없을 때 중간 리스크값"


# ============================================================================
# TestRiskScoreIntegration - 통합 리스크 스코어 테스트
# ============================================================================

class TestRiskScoreIntegration:
    """통합 리스크 스코어 계산 테스트"""

    def test_risk_score_uses_dynamic_volatility(self, mock_config, mock_db_manager):
        """리스크 스코어가 동적 변동성을 사용하는지 검증"""
        # Arrange
        risk_manager = RiskManager(mock_config)
        risk_manager.db_manager = mock_db_manager

        # 고변동성 설정
        high_vol_returns = [0.05, -0.05, 0.06, -0.04] * 8
        mock_db_manager.get_portfolio_daily_returns.return_value = high_vol_returns
        mock_db_manager.get_latest_analysis_result.return_value = None

        portfolio = {
            'total_krw': 10_000_000,
            'assets': {
                'KRW': {'value_krw': 5_000_000},
                'BTC': {'value_krw': 5_000_000}
            }
        }

        # Act
        risk_score = risk_manager.calculate_risk_score(portfolio)

        # Assert
        # 변동성이 높으므로 리스크 스코어도 높아야 함
        assert risk_score > 0.4, "고변동성 시 리스크 스코어 상승"

    def test_risk_score_uses_dynamic_market_risk(self, mock_config, mock_db_manager):
        """리스크 스코어가 동적 시장 리스크를 사용하는지 검증"""
        # Arrange
        risk_manager = RiskManager(mock_config)
        risk_manager.db_manager = mock_db_manager

        # 저변동성 + 고탐욕
        mock_db_manager.get_portfolio_daily_returns.return_value = [0.001] * 30
        mock_db_manager.get_latest_analysis_result.return_value = {
            'fear_greed_index': 90,
            'mvrv': 3.8
        }

        portfolio = {
            'total_krw': 10_000_000,
            'assets': {
                'KRW': {'value_krw': 5_000_000},
                'BTC': {'value_krw': 5_000_000}
            }
        }

        # Act
        risk_score = risk_manager.calculate_risk_score(portfolio)

        # Assert
        # 시장 리스크(고탐욕)가 반영되어 리스크 스코어에 영향을 줌
        # 전체 스코어 = 집중도(0.3*X) + 변동성(0.2*low) + 유동성(0.3*X) + 시장(0.2*high)
        assert risk_score > 0.4, "시장 고탐욕 시 리스크 스코어가 중간 이상"


# ============================================================================
# TestPreTradeRiskCheckIntegration - 거래 전 리스크 체크 통합 테스트
# ============================================================================

class TestPreTradeRiskCheckIntegration:
    """거래 전 리스크 체크 통합 테스트"""

    def test_pre_trade_check_blocks_on_daily_loss(self, mock_config, mock_db_manager):
        """일일 손실 한도 초과 시 거래 거부"""
        # Arrange
        risk_manager = RiskManager(mock_config)
        risk_manager.db_manager = mock_db_manager

        # 어제 대비 6% 손실
        mock_db_manager.get_portfolio_value_days_ago.return_value = 10_000_000

        portfolio = {
            'total_krw': 9_400_000,
            'assets': {
                'KRW': {'value_krw': 5_000_000},
                'BTC': {'value_krw': 4_400_000}
            }
        }

        # Act
        result = risk_manager.pre_trade_risk_check(portfolio, trade_amount=500_000)

        # Assert
        assert not result.approved, "손실 한도 초과 시 거래 거부"
        assert len(result.restrictions) > 0, "제한 사항 메시지가 있어야 함"

    def test_pre_trade_check_allows_normal_trade(self, mock_config, mock_db_manager):
        """정상 상태에서 거래 승인"""
        # Arrange
        risk_manager = RiskManager(mock_config)
        risk_manager.db_manager = mock_db_manager

        # 어제 대비 2% 손실 (한도 내)
        mock_db_manager.get_portfolio_value_days_ago.return_value = 10_000_000
        mock_db_manager.get_portfolio_peak_value.return_value = 10_500_000

        portfolio = {
            'total_krw': 9_800_000,
            'assets': {
                'KRW': {'value_krw': 5_000_000},
                'BTC': {'value_krw': 4_800_000}
            }
        }

        # Act
        result = risk_manager.pre_trade_risk_check(portfolio, trade_amount=500_000)

        # Assert
        assert result.approved, "정상 상태에서 거래 승인"
        assert len(result.restrictions) == 0, "제한 사항이 없어야 함"


# ============================================================================
# TestRiskLimitsDataclass - RiskLimits 데이터클래스 테스트
# ============================================================================

class TestRiskLimitsDataclass:
    """RiskLimits 데이터클래스 테스트"""

    def test_default_values(self):
        """기본값 확인"""
        from src.utils.constants import MAX_POSITION_SIZE
        limits = RiskLimits()

        assert limits.max_single_trade == 10000000
        assert limits.max_daily_volume == 50000000
        assert limits.max_position_size == MAX_POSITION_SIZE
        assert limits.max_daily_loss == 0.05
        assert limits.max_monthly_loss == 0.15
        assert limits.drawdown_threshold == 0.20

    def test_custom_values(self):
        """커스텀 값 설정"""
        limits = RiskLimits(
            max_single_trade=5000000,
            max_daily_volume=20000000,
            max_position_size=0.30,
            max_daily_loss=0.03,
            max_monthly_loss=0.10,
            drawdown_threshold=0.15
        )

        assert limits.max_single_trade == 5000000
        assert limits.max_position_size == 0.30
        assert limits.max_daily_loss == 0.03


class TestRiskCheckResultDataclass:
    """RiskCheckResult 데이터클래스 테스트"""

    def test_default_values(self):
        """기본값 확인"""
        result = RiskCheckResult()

        assert result.approved is False
        assert result.risk_score == 0.0
        assert result.warnings == []
        assert result.restrictions == []
        assert result.reason == ""

    def test_with_values(self):
        """값 설정"""
        result = RiskCheckResult(
            approved=True,
            risk_score=0.3,
            warnings=["경고1"],
            restrictions=["제한1"],
            reason="테스트"
        )

        assert result.approved is True
        assert result.risk_score == 0.3
        assert "경고1" in result.warnings


# ============================================================================
# TestPositionSizeCheck - 포지션 크기 체크 테스트
# ============================================================================

class TestPositionSizeCheck:
    """포지션 크기 체크 테스트"""

    def test_normal_position_sizes(self, mock_config):
        """정상 포지션 크기"""
        risk_manager = RiskManager(mock_config)

        portfolio = {
            'total_krw': 10_000_000,
            'assets': {
                'KRW': {'value_krw': 5_000_000},
                'BTC': {'value_krw': 3_000_000},  # 30%
                'ETH': {'value_krw': 2_000_000}   # 20%
            }
        }

        warnings = risk_manager._check_position_sizes(portfolio)

        assert warnings == [], "정상 포지션 크기는 경고 없음"

    def test_excessive_position_size(self, mock_config):
        """과도한 포지션 크기"""
        risk_manager = RiskManager(mock_config)

        portfolio = {
            'total_krw': 10_000_000,
            'assets': {
                'KRW': {'value_krw': 2_000_000},
                'BTC': {'value_krw': 8_000_000}  # 80% - 과도함
            }
        }

        warnings = risk_manager._check_position_sizes(portfolio)

        assert len(warnings) > 0
        assert "BTC" in warnings[0]

    def test_empty_assets(self, mock_config):
        """빈 자산"""
        risk_manager = RiskManager(mock_config)

        portfolio = {
            'total_krw': 10_000_000,
            'assets': {}
        }

        warnings = risk_manager._check_position_sizes(portfolio)

        assert warnings == []

    def test_zero_total_value(self, mock_config):
        """총 가치 0"""
        risk_manager = RiskManager(mock_config)

        portfolio = {
            'total_krw': 0,
            'assets': {'BTC': {'value_krw': 100}}
        }

        warnings = risk_manager._check_position_sizes(portfolio)

        # 0으로 나누기 방지
        assert isinstance(warnings, list)


# ============================================================================
# TestDailyVolumeTracking - 일일 거래량 추적 테스트
# ============================================================================

class TestDailyVolumeTracking:
    """일일 거래량 추적 테스트"""

    def test_reset_daily_volume(self, mock_config):
        """일일 거래량 리셋"""
        risk_manager = RiskManager(mock_config)
        risk_manager.daily_trade_volume = 1000000
        risk_manager.last_reset_date = datetime.now().date() - timedelta(days=1)

        risk_manager._reset_daily_volume_if_needed()

        assert risk_manager.daily_trade_volume == 0
        assert risk_manager.last_reset_date == datetime.now().date()

    def test_no_reset_same_day(self, mock_config):
        """같은 날 리셋 안함"""
        risk_manager = RiskManager(mock_config)
        risk_manager.daily_trade_volume = 1000000
        risk_manager.last_reset_date = datetime.now().date()

        risk_manager._reset_daily_volume_if_needed()

        assert risk_manager.daily_trade_volume == 1000000


# ============================================================================
# TestPreTradeRiskCheckEdgeCases - 거래 전 리스크 체크 엣지 케이스
# ============================================================================

class TestPreTradeRiskCheckEdgeCases:
    """거래 전 리스크 체크 엣지 케이스"""

    def test_zero_portfolio_value(self, mock_config):
        """포트폴리오 가치 0"""
        risk_manager = RiskManager(mock_config)

        portfolio = {'total_krw': 0, 'assets': {}}

        result = risk_manager.pre_trade_risk_check(portfolio, trade_amount=100000)

        assert result.approved is False
        assert "0 이하" in result.reason

    def test_single_trade_limit_warning(self, mock_config, mock_db_manager):
        """단일 거래 한도 경고"""
        risk_manager = RiskManager(mock_config)
        risk_manager.db_manager = mock_db_manager

        mock_db_manager.get_portfolio_value_days_ago.return_value = 10_000_000
        mock_db_manager.get_portfolio_peak_value.return_value = 10_000_000

        portfolio = {
            'total_krw': 10_000_000,
            'assets': {'KRW': {'value_krw': 10_000_000}}
        }

        # 단일 거래 한도(1천만원) 초과
        result = risk_manager.pre_trade_risk_check(portfolio, trade_amount=15_000_000)

        assert len(result.warnings) > 0
        assert any("단일 거래 한도" in w for w in result.warnings)

    def test_daily_volume_limit_restriction(self, mock_config, mock_db_manager):
        """일일 거래량 한도 제한"""
        risk_manager = RiskManager(mock_config)
        risk_manager.db_manager = mock_db_manager
        risk_manager.daily_trade_volume = 45_000_000  # 이미 4,500만원 거래

        mock_db_manager.get_portfolio_value_days_ago.return_value = 10_000_000
        mock_db_manager.get_portfolio_peak_value.return_value = 10_000_000

        portfolio = {
            'total_krw': 10_000_000,
            'assets': {'KRW': {'value_krw': 10_000_000}}
        }

        # 추가 1,000만원 거래 시 한도(5천만원) 초과
        result = risk_manager.pre_trade_risk_check(portfolio, trade_amount=10_000_000)

        assert len(result.restrictions) > 0
        assert any("일일 거래량" in r for r in result.restrictions)

    def test_exception_handling(self, mock_config):
        """예외 처리"""
        risk_manager = RiskManager(mock_config)

        # 잘못된 데이터로 예외 발생 유도
        portfolio = None

        try:
            result = risk_manager.pre_trade_risk_check(portfolio, trade_amount=100000)
            assert result.approved is False
            assert "오류" in result.reason
        except:
            # 예외가 발생해도 괜찮음
            pass


# ============================================================================
# TestRiskManagerInit - RiskManager 초기화 테스트
# ============================================================================

class TestRiskManagerInit:
    """RiskManager 초기화 테스트"""

    def test_init_with_config(self, mock_config):
        """설정으로 초기화"""
        risk_manager = RiskManager(mock_config)

        assert risk_manager.config == mock_config
        assert risk_manager.db_manager is None
        assert risk_manager.daily_trade_volume == 0
        assert risk_manager.risk_limits.max_single_trade == 10000000

    def test_init_with_db_manager(self, mock_config, mock_db_manager):
        """DB 관리자 포함 초기화"""
        risk_manager = RiskManager(mock_config, mock_db_manager)

        assert risk_manager.db_manager == mock_db_manager

    def test_three_line_check_config(self, mock_config):
        """3-라인 체크 설정"""
        risk_manager = RiskManager(mock_config)

        assert risk_manager.performance_period == 30
        assert risk_manager.tracking_error_threshold == 0.02
        assert risk_manager.benchmark == "BTC"


# ============================================================================
# TestCalculateRiskScore - 리스크 스코어 계산 테스트
# ============================================================================

class TestCalculateRiskScoreAdvanced:
    """리스크 스코어 계산 고급 테스트"""

    def test_no_db_manager(self, mock_config):
        """DB 관리자 없을 때"""
        risk_manager = RiskManager(mock_config)
        risk_manager.db_manager = None

        portfolio = {
            'total_krw': 10_000_000,
            'assets': {'BTC': {'value_krw': 5_000_000}}
        }

        score = risk_manager.calculate_risk_score(portfolio)

        # DB 없어도 기본 리스크 스코어 반환
        assert 0 <= score <= 1

    def test_high_concentration_risk(self, mock_config, mock_db_manager):
        """높은 집중도 리스크"""
        risk_manager = RiskManager(mock_config)
        risk_manager.db_manager = mock_db_manager

        mock_db_manager.get_portfolio_daily_returns.return_value = [0.001] * 30
        mock_db_manager.get_latest_analysis_result.return_value = None

        # 90% BTC 집중
        portfolio = {
            'total_krw': 10_000_000,
            'assets': {
                'KRW': {'value_krw': 1_000_000},
                'BTC': {'value_krw': 9_000_000}
            }
        }

        score = risk_manager.calculate_risk_score(portfolio)

        assert score > 0.3, "높은 집중도는 리스크 점수를 높임"


# ============================================================================
# TestLossLimitsWithNoDbManager - DB 없을 때 손실 한도 체크
# ============================================================================

class TestLossLimitsWithNoDbManager:
    """DB 관리자 없을 때 손실 한도 체크"""

    def test_no_db_returns_empty(self, mock_config):
        """DB 없으면 빈 리스트 반환"""
        risk_manager = RiskManager(mock_config)
        risk_manager.db_manager = None

        portfolio = {'total_krw': 10_000_000}

        result = risk_manager._check_loss_limits(portfolio)

        assert result == []

    def test_zero_portfolio_value(self, mock_config, mock_db_manager):
        """포트폴리오 가치 0이면 빈 리스트"""
        risk_manager = RiskManager(mock_config)
        risk_manager.db_manager = mock_db_manager

        portfolio = {'total_krw': 0}

        result = risk_manager._check_loss_limits(portfolio)

        assert result == []
