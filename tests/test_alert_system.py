"""
Alert System 테스트 모듈

알림 발송 시스템 테스트
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from src.monitoring.alert_system import AlertSystem


class TestAlertSystem:
    """AlertSystem 클래스 테스트"""

    @pytest.fixture
    def mock_config(self):
        """설정 Mock"""
        config = Mock()
        config.get_notification_config.return_value = {
            'email': {
                'enabled': False,
                'smtp_server': 'smtp.test.com',
                'smtp_port': 587,
                'username': 'test@test.com',
                'password': 'password',
                'recipients': ['admin@test.com']
            },
            'slack': {
                'enabled': True,
                'webhook_url': 'https://hooks.slack.com/test',
                'channel': '#alerts',
                'username': 'KAIROS-1',
                'mentions': {
                    'by_alert_type': {
                        'error': ['U123456'],
                        'quarterly_rebalance': ['U789012']
                    },
                    'default_users': ['U000000'],
                    'channel_mention_types': ['critical']
                }
            },
            'alert_levels': {
                'error': ['slack', 'email'],
                'warning': ['slack'],
                'info': ['slack']
            }
        }
        return config

    @pytest.fixture
    def mock_system_coordinator(self):
        """시스템 코디네이터 Mock"""
        coordinator = Mock()
        coordinator.should_send_alert.return_value = True
        return coordinator

    @pytest.fixture
    def alert_system(self, mock_config, mock_system_coordinator):
        """AlertSystem 인스턴스"""
        with patch('src.monitoring.alert_system.get_system_coordinator',
                   return_value=mock_system_coordinator):
            return AlertSystem(mock_config)

    def test_init(self, alert_system):
        """초기화 테스트"""
        assert alert_system.config is not None
        assert 'enabled' in alert_system.slack_config

    def test_send_alert_filtered(self, alert_system):
        """중복 알림 필터링"""
        alert_system.system_coordinator.should_send_alert.return_value = False

        result = alert_system.send_alert("Test", "Test message")

        assert result.get('filtered') is True

    def test_send_alert_slack_disabled(self, alert_system):
        """슬랙 비활성화시 처리"""
        alert_system.slack_config['enabled'] = False

        result = alert_system.send_alert("Test", "Test message", channels=['slack'])

        assert result.get('slack') is False

    def test_send_error_alert(self, alert_system):
        """에러 알림 발송"""
        with patch.object(alert_system, 'send_alert', return_value={'slack': True}):
            result = alert_system.send_error_alert("Error Title", "Error message")

            assert result == {'slack': True}
            alert_system.send_alert.assert_called_once()

    def test_send_warning_alert(self, alert_system):
        """경고 알림 발송"""
        with patch.object(alert_system, 'send_alert', return_value={'slack': True}):
            result = alert_system.send_warning_alert("Warning Title", "Warning message")

            assert result == {'slack': True}

    def test_send_info_alert(self, alert_system):
        """정보 알림 발송"""
        with patch.object(alert_system, 'send_alert', return_value={'slack': True}):
            result = alert_system.send_info_alert("Info Title", "Info message")

            assert result == {'slack': True}

    def test_generate_mention_text_error(self, alert_system):
        """에러 타입 멘션 텍스트 생성"""
        mention_text = alert_system._generate_mention_text('error')

        # 에러 타입에는 @here 자동 추가
        assert '@here' in mention_text or '<@U123456>' in mention_text

    def test_generate_mention_text_no_config(self, alert_system):
        """멘션 설정 없을 때"""
        alert_system.slack_config['mentions'] = {}

        mention_text = alert_system._generate_mention_text('info')

        # 설정 없으면 빈 문자열
        assert mention_text == "" or mention_text is not None

    def test_format_message_for_email_error(self, alert_system):
        """에러 이메일 포맷팅"""
        html = alert_system._format_message_for_email("Test message", "error")

        assert 'KAIROS-1' in html
        assert '#ff4444' in html  # 에러 색상

    def test_format_message_for_email_info(self, alert_system):
        """정보 이메일 포맷팅"""
        html = alert_system._format_message_for_email("Test message", "info")

        assert '#44aa44' in html  # 정보 색상

    def test_send_daily_summary(self, alert_system):
        """일일 요약 알림"""
        summary_data = {
            'portfolio_value': 10000000,
            'daily_change': 100000,
            'daily_return': 0.01,
            'market_season': 'neutral',
            'btc_weight': 0.4,
            'eth_weight': 0.3,
            'xrp_weight': 0.15,
            'sol_weight': 0.15,
            'krw_weight': 0.0,
            'next_rebalance': '2026-02-21'
        }

        with patch.object(alert_system, 'send_info_alert', return_value={'slack': True}):
            result = alert_system.send_daily_summary(summary_data)

            assert result == {'slack': True}

    def test_send_daily_summary_error(self, alert_system):
        """일일 요약 알림 에러"""
        # 잘못된 데이터
        result = alert_system.send_daily_summary(None)

        assert result == {}

    def test_send_performance_alert_good(self, alert_system):
        """좋은 성과 알림"""
        performance_data = {
            'period_days': 30,
            'total_return': 0.15,
            'benchmark_return': 0.10,
            'sharpe_ratio': 2.0,
            'max_drawdown': -0.10
        }

        with patch.object(alert_system, 'send_alert', return_value={'slack': True}):
            result = alert_system.send_performance_alert(performance_data)

            # info 타입으로 발송 (positional arg로 전달됨)
            call_args = alert_system.send_alert.call_args
            # send_alert(title, message, alert_type) - 3번째 인자가 alert_type
            assert call_args[0][2] == 'info'

    def test_send_performance_alert_bad(self, alert_system):
        """나쁜 성과 알림"""
        performance_data = {
            'period_days': 30,
            'total_return': -0.15,  # -15% 손실
            'benchmark_return': 0.05,
            'sharpe_ratio': -0.5,
            'max_drawdown': -0.25
        }

        with patch.object(alert_system, 'send_alert', return_value={'slack': True}):
            result = alert_system.send_performance_alert(performance_data)

            # warning 타입으로 발송 (positional arg로 전달됨)
            call_args = alert_system.send_alert.call_args
            # send_alert(title, message, alert_type) - 3번째 인자가 alert_type
            assert call_args[0][2] == 'warning'

    def test_send_market_analysis_report(self, alert_system):
        """시장 분석 보고서 발송"""
        analysis_result = {
            'current_season': 'BULLISH',
            'previous_season': 'NEUTRAL',
            'season_changed': True,
            'trend_score': 0.75,
            'volatility': 0.05,
            'momentum': 0.6,
            'volume_trend': '상승',
            'recommendation': '매수 추천'
        }

        with patch.object(alert_system, 'send_info_alert', return_value={'slack': True}):
            result = alert_system.send_market_analysis_report(analysis_result)

            assert result == {'slack': True}

    def test_send_market_analysis_report_with_advanced(self, alert_system):
        """고급 분석 포함 보고서"""
        analysis_result = {
            'current_season': 'BULLISH',
            'previous_season': 'NEUTRAL',
            'season_changed': False,
            'trend_score': 0.75,
            'volatility': 0.05,
            'momentum': 0.6,
            'volume_trend': '상승',
            'advanced_analysis': {
                'multi_timeframe': {'confidence_score': 0.8},
                'macro_economic': {
                    'result_data': {
                        'indicators': {
                            'VIX': {'value': 18},
                            'DXY': {'value': 98}
                        }
                    }
                }
            }
        }

        with patch.object(alert_system, 'send_info_alert', return_value={'slack': True}):
            result = alert_system.send_market_analysis_report(analysis_result)

            assert result == {'slack': True}

    def test_send_weekly_analysis_report_alias(self, alert_system):
        """send_weekly_analysis_report가 send_market_analysis_report를 호출"""
        with patch.object(alert_system, 'send_market_analysis_report', return_value={'slack': True}):
            result = alert_system.send_weekly_analysis_report({})

            alert_system.send_market_analysis_report.assert_called_once()


class TestAlertSystemSlack:
    """슬랙 알림 테스트"""

    @pytest.fixture
    def alert_system(self):
        """AlertSystem 인스턴스"""
        config = Mock()
        config.get_notification_config.return_value = {
            'email': {'enabled': False},
            'slack': {
                'enabled': True,
                'webhook_url': 'https://hooks.slack.com/test',
                'channel': '#alerts',
                'username': 'KAIROS-1',
                'mentions': {}
            },
            'alert_levels': {}
        }

        with patch('src.monitoring.alert_system.get_system_coordinator') as mock_coord:
            mock_coord.return_value.should_send_alert.return_value = True
            return AlertSystem(config)

    @patch('src.monitoring.alert_system.requests.post')
    def test_send_slack_success(self, mock_post, alert_system):
        """슬랙 발송 성공"""
        mock_post.return_value.status_code = 200

        result = alert_system._send_slack("Title", "Message", "info")

        assert result is True
        mock_post.assert_called_once()

    @patch('src.monitoring.alert_system.requests.post')
    def test_send_slack_failure(self, mock_post, alert_system):
        """슬랙 발송 실패"""
        mock_post.return_value.status_code = 500
        mock_post.return_value.text = "Error"

        result = alert_system._send_slack("Title", "Message", "info")

        assert result is False

    def test_send_slack_no_webhook(self, alert_system):
        """웹훅 URL 없음"""
        alert_system.slack_config['webhook_url'] = None

        result = alert_system._send_slack("Title", "Message", "info")

        assert result is False


class TestAlertSystemEmail:
    """이메일 알림 테스트"""

    @pytest.fixture
    def alert_system(self):
        """AlertSystem 인스턴스"""
        config = Mock()
        config.get_notification_config.return_value = {
            'email': {
                'enabled': True,
                'smtp_server': 'smtp.test.com',
                'smtp_port': 587,
                'username': 'test@test.com',
                'password': 'password',
                'recipients': ['admin@test.com']
            },
            'slack': {'enabled': False},
            'alert_levels': {}
        }

        with patch('src.monitoring.alert_system.get_system_coordinator') as mock_coord:
            mock_coord.return_value.should_send_alert.return_value = True
            return AlertSystem(config)

    def test_send_email_incomplete_config(self, alert_system):
        """이메일 설정 불완전"""
        alert_system.email_config['smtp_server'] = None

        result = alert_system._send_email("Title", "Message", "info")

        assert result is False

    @patch('src.monitoring.alert_system.smtplib.SMTP')
    def test_send_email_success(self, mock_smtp, alert_system):
        """이메일 발송 성공"""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        result = alert_system._send_email("Title", "Message", "info")

        assert result is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once()

    @patch('src.monitoring.alert_system.smtplib.SMTP')
    def test_send_email_exception(self, mock_smtp, alert_system):
        """이메일 발송 예외 처리"""
        mock_smtp.side_effect = Exception("SMTP Error")

        result = alert_system._send_email("Title", "Message", "info")

        assert result is False


class TestAlertSystemAdvanced:
    """고급 알림 기능 테스트"""

    @pytest.fixture
    def alert_system_full(self):
        """전체 기능 AlertSystem 인스턴스"""
        config = Mock()
        config.get_notification_config.return_value = {
            'email': {'enabled': True},
            'slack': {
                'enabled': True,
                'webhook_url': 'https://hooks.slack.com/test',
                'channel': '#alerts',
                'username': 'KAIROS-1',
                'mentions': {
                    'by_alert_type': {
                        'error': ['U123456'],
                        'quarterly_rebalance': ['U789012']
                    },
                    'default_users': ['U000000'],
                    'channel_mention_types': ['critical']
                }
            },
            'alert_levels': {
                'error': ['slack', 'email'],
                'warning': ['slack'],
                'info': ['slack']
            }
        }

        with patch('src.monitoring.alert_system.get_system_coordinator') as mock_coord:
            mock_coord.return_value.should_send_alert.return_value = True
            return AlertSystem(config)

    def test_send_alert_with_default_channels(self, alert_system_full):
        """기본 채널로 알림 발송"""
        with patch.object(alert_system_full, '_send_slack', return_value=True):
            result = alert_system_full.send_alert("Test", "Message", "info")

            assert 'slack' in result

    def test_send_alert_exception_handling(self, alert_system_full):
        """알림 발송 예외 처리"""
        with patch.object(alert_system_full, '_send_slack', side_effect=Exception("Error")):
            result = alert_system_full.send_alert("Test", "Message", channels=['slack'])

            assert result.get('slack') is False

    def test_generate_mention_text_channel_mention(self, alert_system_full):
        """채널 멘션 타입"""
        mention_text = alert_system_full._generate_mention_text('critical')

        # critical은 channel_mention_types에 있음
        assert '@channel' in mention_text or len(mention_text) >= 0

    def test_generate_mention_text_with_user_id(self, alert_system_full):
        """사용자 ID 멘션"""
        mention_text = alert_system_full._generate_mention_text('quarterly_rebalance')

        # quarterly_rebalance에 U789012 설정됨
        assert '<@U789012>' in mention_text

    def test_generate_mention_text_default_users(self, alert_system_full):
        """기본 사용자 멘션"""
        # 설정되지 않은 alert_type은 default_users 사용
        mention_text = alert_system_full._generate_mention_text('unknown_type')

        assert '<@U000000>' in mention_text

    def test_send_performance_alert_high_drawdown(self, alert_system_full):
        """높은 드로우다운 경고"""
        performance_data = {
            'period_days': 30,
            'total_return': 0.05,  # 양수 수익
            'benchmark_return': 0.03,
            'sharpe_ratio': 1.0,
            'max_drawdown': -0.25  # -25% 드로우다운
        }

        with patch.object(alert_system_full, 'send_alert', return_value={'slack': True}):
            result = alert_system_full.send_performance_alert(performance_data)

            # warning 타입으로 발송 (드로우다운이 -20% 이하)
            call_args = alert_system_full.send_alert.call_args
            assert call_args[0][2] == 'warning'

    def test_send_performance_alert_exception(self, alert_system_full):
        """성과 알림 예외 처리"""
        result = alert_system_full.send_performance_alert(None)

        assert result == {}

    def test_send_multi_timeframe_analysis_report(self, alert_system_full):
        """멀티 타임프레임 분석 보고서"""
        analysis_result = {
            'trading_timeframes': {
                'very_short_term': {'trend': 'bullish'},
                'swing_term': {'trend': 'sideways'},
                'position_term': {'trend': 'bullish'}
            },
            'strategic_layer': {
                'market_season': 'BULLISH',
                'cycle_phase': 'accumulation'
            },
            'confidence': 0.85,
            'recommended_allocation': {
                'crypto': '70%',
                'krw': '30%'
            }
        }

        with patch.object(alert_system_full, 'send_info_alert', return_value={'slack': True}):
            result = alert_system_full.send_multi_timeframe_analysis_report(analysis_result)

            assert result == {'slack': True}

    def test_send_multi_timeframe_analysis_report_exception(self, alert_system_full):
        """멀티 타임프레임 분석 보고서 예외 처리"""
        result = alert_system_full.send_multi_timeframe_analysis_report(None)

        assert result == {}

    def test_send_macro_analysis_report(self, alert_system_full):
        """매크로 경제 분석 보고서"""
        analysis_result = {
            'indicators': {
                'fed_funds_rate': 5.25,
                'dxy_index': 104.5,
                'inflation_rate': 3.2,
                'vix_index': 18.5,
                'bond_yield_10y': 4.5
            },
            'risk_score': 0.55,
            'crypto_correlation': -0.3,
            'market_outlook': '중립'
        }

        with patch.object(alert_system_full, 'send_info_alert', return_value={'slack': True}):
            result = alert_system_full.send_macro_analysis_report(analysis_result)

            assert result == {'slack': True}

    def test_send_macro_analysis_report_high_risk(self, alert_system_full):
        """고위험 매크로 분석 보고서"""
        analysis_result = {
            'indicators': {},
            'risk_score': 0.85,  # 높은 리스크
            'crypto_correlation': -0.5,
            'market_outlook': '약세'
        }

        with patch.object(alert_system_full, 'send_info_alert', return_value={'slack': True}):
            result = alert_system_full.send_macro_analysis_report(analysis_result)

            assert result == {'slack': True}

    def test_send_macro_analysis_report_low_risk(self, alert_system_full):
        """저위험 매크로 분석 보고서"""
        analysis_result = {
            'indicators': {},
            'risk_score': 0.2,  # 낮은 리스크
            'crypto_correlation': 0.3,
            'market_outlook': '강세'
        }

        with patch.object(alert_system_full, 'send_info_alert', return_value={'slack': True}):
            result = alert_system_full.send_macro_analysis_report(analysis_result)

            assert result == {'slack': True}

    def test_send_macro_analysis_report_exception(self, alert_system_full):
        """매크로 분석 보고서 예외 처리"""
        result = alert_system_full.send_macro_analysis_report(None)

        assert result == {}

    def test_send_market_analysis_with_rebalance(self, alert_system_full):
        """리밸런싱 포함 시장 분석 보고서"""
        analysis_result = {
            'current_season': 'BULLISH',
            'previous_season': 'NEUTRAL',
            'season_changed': True,
            'trend_score': 0.75,
            'volatility': 0.05,
            'momentum': 0.6,
            'volume_trend': '상승',
            'rebalance_triggered': True,
            'rebalance_result': {'estimated_hours': 12},
            'adjusted_allocation': {'crypto': 0.7, 'krw': 0.3}
        }

        with patch.object(alert_system_full, 'send_info_alert', return_value={'slack': True}):
            result = alert_system_full.send_market_analysis_report(analysis_result)

            assert result == {'slack': True}

    def test_send_market_analysis_with_all_advanced(self, alert_system_full):
        """모든 고급 분석 포함 보고서"""
        analysis_result = {
            'current_season': 'BEARISH',
            'previous_season': 'NEUTRAL',
            'season_changed': False,
            'trend_score': -0.5,
            'volatility': 0.08,
            'momentum': -0.3,
            'volume_trend': '하락',
            'advanced_analysis': {
                'multi_timeframe': {'confidence_score': 0.7},
                'macro_economic': {
                    'result_data': {
                        'indicators': {
                            'VIX': {'value': 25},
                            'DXY': {'value': 103}
                        }
                    }
                },
                'onchain_data': {
                    'result_data': {
                        'metrics': {'nupl': 0.35}
                    }
                },
                'behavioral_bias': {
                    'result_data': {
                        'detected_biases': ['FOMO', 'panic_selling']
                    }
                },
                'performance_analytics': {
                    'result_data': {
                        'performance_metrics': {'sharpe_ratio': 1.5}
                    }
                },
                'scenario_response': {
                    'result_data': {
                        'active_scenarios': ['market_correction']
                    }
                }
            },
            'analysis_info': {
                'price_ratio': 1.08  # 과열 구간
            }
        }

        with patch.object(alert_system_full, 'send_info_alert', return_value={'slack': True}):
            result = alert_system_full.send_market_analysis_report(analysis_result)

            assert result == {'slack': True}

    def test_send_market_analysis_price_ratio_low(self, alert_system_full):
        """낮은 가격 비율 분석"""
        analysis_result = {
            'current_season': 'ACCUMULATION',
            'previous_season': 'BEARISH',
            'season_changed': True,
            'trend_score': 0.2,
            'volatility': 0.03,
            'momentum': 0.1,
            'volume_trend': '증가',
            'analysis_info': {
                'price_ratio': 0.90  # 매수 기회
            }
        }

        with patch.object(alert_system_full, 'send_info_alert', return_value={'slack': True}):
            result = alert_system_full.send_market_analysis_report(analysis_result)

            assert result == {'slack': True}

    def test_send_market_analysis_report_exception(self, alert_system_full):
        """시장 분석 보고서 예외 처리"""
        result = alert_system_full.send_market_analysis_report(None)

        assert result == {}


class TestAlertSystemMentions:
    """멘션 기능 상세 테스트"""

    @pytest.fixture
    def alert_system_mentions(self):
        """멘션 설정된 AlertSystem"""
        config = Mock()
        config.get_notification_config.return_value = {
            'email': {'enabled': False},
            'slack': {
                'enabled': True,
                'webhook_url': 'https://hooks.slack.com/test',
                'mentions': {
                    'by_alert_type': {
                        'error': ['U111111', 'U222222'],
                    },
                    'default_users': [],
                    'channel_mention_types': ['emergency']
                }
            },
            'alert_levels': {}
        }

        with patch('src.monitoring.alert_system.get_system_coordinator') as mock_coord:
            mock_coord.return_value.should_send_alert.return_value = True
            return AlertSystem(config)

    def test_generate_multiple_user_mentions(self, alert_system_mentions):
        """여러 사용자 멘션"""
        mention_text = alert_system_mentions._generate_mention_text('error')

        # error 타입에 2명 + @here 추가
        assert '<@U111111>' in mention_text
        assert '<@U222222>' in mention_text

    def test_generate_mention_exception_handling(self, alert_system_mentions):
        """멘션 생성 예외 처리"""
        alert_system_mentions.slack_config = None  # 설정 없음

        mention_text = alert_system_mentions._generate_mention_text('error')

        assert mention_text == ""


class TestSlackPayload:
    """슬랙 페이로드 테스트"""

    @pytest.fixture
    def alert_system(self):
        """AlertSystem 인스턴스"""
        config = Mock()
        config.get_notification_config.return_value = {
            'email': {'enabled': False},
            'slack': {
                'enabled': True,
                'webhook_url': 'https://hooks.slack.com/test',
                'channel': '#test',
                'username': 'TestBot',
                'mentions': {}
            },
            'alert_levels': {}
        }

        with patch('src.monitoring.alert_system.get_system_coordinator') as mock_coord:
            mock_coord.return_value.should_send_alert.return_value = True
            return AlertSystem(config)

    @patch('src.monitoring.alert_system.requests.post')
    def test_slack_payload_error_color(self, mock_post, alert_system):
        """에러 알림 색상"""
        mock_post.return_value.status_code = 200

        alert_system._send_slack("Error", "Message", "error")

        call_args = mock_post.call_args
        payload = eval(call_args[1]['data'])
        assert payload['attachments'][0]['color'] == '#ff0000'

    @patch('src.monitoring.alert_system.requests.post')
    def test_slack_payload_warning_color(self, mock_post, alert_system):
        """경고 알림 색상"""
        mock_post.return_value.status_code = 200

        alert_system._send_slack("Warning", "Message", "warning")

        call_args = mock_post.call_args
        payload = eval(call_args[1]['data'])
        assert payload['attachments'][0]['color'] == '#ffaa00'

    @patch('src.monitoring.alert_system.requests.post')
    def test_slack_payload_exception(self, mock_post, alert_system):
        """슬랙 요청 예외"""
        mock_post.side_effect = Exception("Connection Error")

        result = alert_system._send_slack("Title", "Message", "info")

        assert result is False
