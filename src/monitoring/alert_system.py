"""
Alert System

알림 발송 및 관리를 담당하는 모듈
"""

import smtplib
import requests
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, List, Optional, Any
from loguru import logger


class AlertSystem:
    """
    알림 시스템
    
    이메일, 슬랙 등 다양한 채널을 통해 알림을 발송합니다.
    """
    
    def __init__(self, config):
        """
        Args:
            config: ConfigLoader 인스턴스
        """
        self.config = config
        self.notification_config = config.get_notification_config()
        
        # 알림 채널 설정
        self.email_config = self.notification_config.get("email", {})
        self.slack_config = self.notification_config.get("slack", {})
        self.alert_levels = self.notification_config.get("alert_levels", {})
        
        logger.info("AlertSystem 초기화 완료")
    
    def send_alert(
        self,
        title: str,
        message: str,
        alert_type: str = "info",
        channels: Optional[List[str]] = None
    ) -> Dict[str, bool]:
        """
        알림 발송
        
        Args:
            title: 알림 제목
            message: 알림 내용
            alert_type: 알림 유형 ("error", "warning", "info")
            channels: 발송할 채널 리스트 (None인 경우 설정에서 자동 결정)
            
        Returns:
            채널별 발송 결과
        """
        results = {}
        
        # 채널 목록 결정
        if channels is None:
            channels = self.alert_levels.get(alert_type, ["slack"])
        
        # 각 채널로 알림 발송
        for channel in channels:
            try:
                if channel == "email" and self.email_config.get("enabled", False):
                    result = self._send_email(title, message, alert_type)
                    results["email"] = result
                    
                elif channel == "slack" and self.slack_config.get("enabled", False):
                    result = self._send_slack(title, message, alert_type)
                    results["slack"] = result
                    
                else:
                    logger.warning(f"알림 채널이 비활성화되거나 지원되지 않음: {channel}")
                    results[channel] = False
                    
            except Exception as e:
                logger.error(f"{channel} 알림 발송 실패: {e}")
                results[channel] = False
        
        return results
    
    def send_error_alert(
        self,
        title: str,
        message: str,
        error_type: str = "system_error"
    ) -> Dict[str, bool]:
        """
        오류 알림 발송
        
        Args:
            title: 알림 제목
            message: 오류 메시지
            error_type: 오류 유형
            
        Returns:
            발송 결과
        """
        formatted_message = f"""
🚨 **오류 발생**

**유형**: {error_type}
**시간**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**내용**:
{message}

**조치**: 시스템 관리자에게 문의하시기 바랍니다.
        """.strip()
        
        return self.send_alert(title, formatted_message, "error")
    
    def send_warning_alert(
        self,
        title: str,
        message: str,
        warning_type: str = "system_warning"
    ) -> Dict[str, bool]:
        """
        경고 알림 발송
        
        Args:
            title: 알림 제목
            message: 경고 메시지
            warning_type: 경고 유형
            
        Returns:
            발송 결과
        """
        formatted_message = f"""
⚠️ **경고**

**유형**: {warning_type}
**시간**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**내용**:
{message}
        """.strip()
        
        return self.send_alert(title, formatted_message, "warning")
    
    def send_info_alert(
        self,
        title: str,
        message: str,
        alert_type: str = "system_info"
    ) -> Dict[str, bool]:
        """
        정보 알림 발송
        
        Args:
            title: 알림 제목
            message: 정보 메시지
            alert_type: 알림 유형
            
        Returns:
            발송 결과
        """
        formatted_message = f"""
ℹ️ **정보**

**유형**: {alert_type}
**시간**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**내용**:
{message}
        """.strip()
        
        return self.send_alert(title, formatted_message, "info")
    
    def _send_email(self, title: str, message: str, alert_type: str) -> bool:
        """
        이메일 알림 발송
        
        Args:
            title: 제목
            message: 내용
            alert_type: 알림 유형
            
        Returns:
            발송 성공 여부
        """
        try:
            # 이메일 설정 확인
            smtp_server = self.email_config.get("smtp_server")
            smtp_port = self.email_config.get("smtp_port", 587)
            username = self.email_config.get("username")
            password = self.email_config.get("password")
            recipients = self.email_config.get("recipients", [])
            
            if not all([smtp_server, username, password, recipients]):
                logger.warning("이메일 설정이 완전하지 않음")
                return False
            
            # 이메일 메시지 생성
            msg = MIMEMultipart()
            msg['From'] = username
            msg['To'] = ", ".join(recipients)
            msg['Subject'] = f"[KAIROS-1] {title}"
            
            # HTML 형태로 메시지 포맷팅
            html_message = self._format_message_for_email(message, alert_type)
            msg.attach(MIMEText(html_message, 'html'))
            
            # SMTP 연결 및 발송
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(username, password)
                server.send_message(msg)
            
            logger.info("이메일 알림 발송 성공")
            return True
            
        except Exception as e:
            logger.error(f"이메일 발송 실패: {e}")
            return False
    
    def _send_slack(self, title: str, message: str, alert_type: str) -> bool:
        """
        슬랙 알림 발송
        
        Args:
            title: 제목
            message: 내용
            alert_type: 알림 유형
            
        Returns:
            발송 성공 여부
        """
        try:
            webhook_url = self.slack_config.get("webhook_url")
            channel = self.slack_config.get("channel", "#general")
            username = self.slack_config.get("username", "KAIROS-1")
            
            if not webhook_url:
                logger.warning("슬랙 webhook URL이 설정되지 않음")
                return False
            
            # 알림 유형에 따른 색상 및 이모지 설정
            color_map = {
                "error": "#ff0000",
                "warning": "#ffaa00",
                "info": "#00aa00"
            }
            
            emoji_map = {
                "error": "🚨",
                "warning": "⚠️",
                "info": "ℹ️"
            }
            
            color = color_map.get(alert_type, "#00aa00")
            emoji = emoji_map.get(alert_type, "ℹ️")
            
            # 슬랙 메시지 페이로드 생성
            payload = {
                "channel": channel,
                "username": username,
                "attachments": [
                    {
                        "color": color,
                        "title": f"{emoji} {title}",
                        "text": message,
                        "footer": "KAIROS-1 Trading System",
                        "ts": int(datetime.now().timestamp())
                    }
                ]
            }
            
            # 웹훅으로 전송
            response = requests.post(
                webhook_url,
                data=json.dumps(payload),
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("슬랙 알림 발송 성공")
                return True
            else:
                logger.error(f"슬랙 발송 실패: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"슬랙 발송 실패: {e}")
            return False
    
    def _format_message_for_email(self, message: str, alert_type: str) -> str:
        """
        이메일용 HTML 메시지 포맷팅
        
        Args:
            message: 원본 메시지
            alert_type: 알림 유형
            
        Returns:
            HTML 형식의 메시지
        """
        # 색상 설정
        color_map = {
            "error": "#ff4444",
            "warning": "#ffaa00",
            "info": "#44aa44"
        }
        
        color = color_map.get(alert_type, "#44aa44")
        
        html_template = f"""
        <html>
        <head>
            <meta charset="utf-8">
        </head>
        <body style="font-family: Arial, sans-serif; margin: 20px;">
            <div style="border-left: 4px solid {color}; padding-left: 20px; margin-bottom: 20px;">
                <h2 style="color: {color}; margin: 0;">KAIROS-1 Trading System</h2>
                <p style="color: #666; margin: 5px 0 0 0;">자동 투자 시스템 알림</p>
            </div>
            
            <div style="background-color: #f9f9f9; padding: 20px; border-radius: 5px;">
                <pre style="white-space: pre-wrap; font-family: Arial, sans-serif; margin: 0;">{message}</pre>
            </div>
            
            <div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #eee; color: #666; font-size: 12px;">
                <p>이 메시지는 KAIROS-1 자동 투자 시스템에서 발송되었습니다.</p>
                <p>발송 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
        </body>
        </html>
        """
        
        return html_template
    
    def test_notifications(self) -> Dict[str, bool]:
        """
        알림 시스템 테스트
        
        Returns:
            채널별 테스트 결과
        """
        test_title = "KAIROS-1 알림 시스템 테스트"
        test_message = f"""
알림 시스템이 정상적으로 작동하고 있습니다.

테스트 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
시스템: KAIROS-1 Trading System
        """.strip()
        
        logger.info("알림 시스템 테스트 시작")
        results = self.send_info_alert(test_title, test_message, "system_test")
        
        # 결과 로깅
        for channel, success in results.items():
            if success:
                logger.info(f"{channel} 알림 테스트 성공")
            else:
                logger.error(f"{channel} 알림 테스트 실패")
        
        return results
    
    def send_daily_summary(self, summary_data: Dict) -> Dict[str, bool]:
        """
        일일 요약 알림 발송
        
        Args:
            summary_data: 요약 데이터
            
        Returns:
            발송 결과
        """
        try:
            portfolio_value = summary_data.get("portfolio_value", 0)
            daily_change = summary_data.get("daily_change", 0)
            daily_return = summary_data.get("daily_return", 0)
            market_season = summary_data.get("market_season", "neutral")
            
            message = f"""
📊 **KAIROS-1 일일 요약 보고서**

💰 **포트폴리오 현황**:
• 총 자산 가치: {portfolio_value:,.0f} KRW
• 일간 변화: {daily_change:+,.0f} KRW ({daily_return:+.2%})

🎯 **현재 시장 계절**: {market_season.upper()}

📈 **자산 배분**:
• BTC: {summary_data.get('btc_weight', 0):.1%}
• ETH: {summary_data.get('eth_weight', 0):.1%}
• XRP: {summary_data.get('xrp_weight', 0):.1%}
• SOL: {summary_data.get('sol_weight', 0):.1%}
• KRW: {summary_data.get('krw_weight', 0):.1%}

🔄 **다음 리밸런싱**: {summary_data.get('next_rebalance', 'TBD')}
            """.strip()
            
            return self.send_info_alert("일일 포트폴리오 요약", message, "daily_summary")
            
        except Exception as e:
            logger.error(f"일일 요약 알림 발송 실패: {e}")
            return {}
    
    def send_performance_alert(self, performance_data: Dict) -> Dict[str, bool]:
        """
        성과 알림 발송
        
        Args:
            performance_data: 성과 데이터
            
        Returns:
            발송 결과
        """
        try:
            period = performance_data.get("period_days", 30)
            total_return = performance_data.get("total_return", 0)
            benchmark_return = performance_data.get("benchmark_return", 0)
            sharpe_ratio = performance_data.get("sharpe_ratio", 0)
            max_drawdown = performance_data.get("max_drawdown", 0)
            
            message = f"""
📈 **KAIROS-1 성과 보고서** ({period}일간)

💹 **수익률**:
• 포트폴리오 수익률: {total_return:+.2%}
• 벤치마크 수익률 (BTC): {benchmark_return:+.2%}
• 초과 수익률: {total_return - benchmark_return:+.2%}

📊 **리스크 지표**:
• 샤프 비율: {sharpe_ratio:.2f}
• 최대 드로우다운: {max_drawdown:.2%}

✅ **시스템 상태**: 정상 운영 중
            """.strip()
            
            # 성과에 따라 알림 레벨 결정
            if total_return < -0.10:  # -10% 이상 손실
                alert_type = "warning"
            elif max_drawdown < -0.20:  # -20% 이상 드로우다운
                alert_type = "warning"
            else:
                alert_type = "info"
            
            return self.send_alert(f"성과 보고서 ({period}일간)", message, alert_type)
            
        except Exception as e:
            logger.error(f"성과 알림 발송 실패: {e}")
            return {}


# 설정 상수
DEFAULT_ALERT_CHANNELS = ["slack"]
EMAIL_TIMEOUT = 30  # 이메일 발송 타임아웃 (초)
SLACK_TIMEOUT = 10  # 슬랙 발송 타임아웃 (초) 