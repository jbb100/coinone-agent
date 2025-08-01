# KAIROS-1 배포 가이드

## 🚀 배포 준비

### 1. 시스템 요구사항

#### 최소 요구사항
- **운영체제**: Ubuntu 20.04+ / CentOS 8+ / macOS 10.15+
- **Python**: 3.9+
- **메모리**: 최소 2GB RAM
- **디스크**: 최소 10GB 여유 공간
- **네트워크**: 안정적인 인터넷 연결

#### 권장 요구사항
- **운영체제**: Ubuntu 22.04 LTS
- **Python**: 3.11+
- **메모리**: 4GB+ RAM
- **디스크**: 50GB+ SSD
- **네트워크**: 고속 인터넷 연결 (API 호출용)

### 2. 사전 준비

#### 코인원 API 설정
1. [코인원](https://coinone.co.kr) 계정 생성 및 인증 완료
2. API 키 발급:
   - 계정 설정 → API 관리 → 새 API 키 생성
   - 권한 설정: 거래, 계좌 조회 권한 활성화
   - IP 화이트리스트 등록 (보안 강화)

#### 알림 설정 (선택사항)
- **슬랙**: Webhook URL 발급
- **이메일**: SMTP 서버 정보 (Gmail 앱 비밀번호 권장)

## 📦 설치 과정

### 1. 프로젝트 클론
```bash
git clone <repository-url> kairos-1
cd kairos-1
```

### 2. Python 가상환경 설정
```bash
# 가상환경 생성
python3 -m venv kairos_env

# 가상환경 활성화
source kairos_env/bin/activate  # Linux/macOS
# kairos_env\Scripts\activate  # Windows

# 패키지 업그레이드
pip install --upgrade pip setuptools wheel
```

### 3. 의존성 설치
```bash
# 필수 패키지 설치
pip install -r requirements.txt

# TA-Lib 설치 (시스템별 상이)
# Ubuntu/Debian:
sudo apt-get install libta-lib-dev
pip install TA-Lib

# macOS (Homebrew):
brew install ta-lib
pip install TA-Lib

# CentOS/RHEL:
sudo yum install ta-lib-devel
pip install TA-Lib
```

### 4. 설정 파일 구성
```bash
# 설정 파일 복사
cp config/config.example.yaml config/config.yaml

# 설정 편집
vim config/config.yaml  # 또는 원하는 에디터 사용
```

#### 필수 설정 항목
```yaml
api:
  coinone:
    api_key: "YOUR_COINONE_API_KEY"
    secret_key: "YOUR_COINONE_SECRET_KEY"
    sandbox: false  # 실제 거래시 false

notifications:
  slack:
    enabled: true
    webhook_url: "YOUR_SLACK_WEBHOOK_URL"
  email:
    enabled: true
    username: "your_email@gmail.com"
    password: "your_app_password"
```

### 5. 디렉토리 구조 생성
```bash
# 필요한 디렉토리 생성
mkdir -p logs data backups reports

# 권한 설정
chmod 750 logs data backups reports
chmod +x scripts/*.py kairos1_main.py
```

## ⚙️ 시스템 검증

### 1. 기본 동작 테스트
```bash
# 시스템 초기화 테스트
python kairos1_main.py --system-status

# API 연결 테스트
python kairos1_main.py --test-alerts
```

### 2. 모듈별 테스트
```bash
# 주간 시장 분석 테스트
python kairos1_main.py --weekly-analysis

# DRY RUN 리밸런싱 테스트
python kairos1_main.py --quarterly-rebalance --dry-run

# 성과 보고서 테스트
python kairos1_main.py --performance-report 30
```

## 🔄 자동화 설정

### 1. 크론잡 설정
```bash
# 크론탭 편집
crontab -e

# 다음 내용 추가:
# 주간 시장 분석 (매주 월요일 09:00)
0 9 * * 1 /path/to/kairos_env/bin/python /path/to/kairos-1/scripts/weekly_check.py

# 분기별 리밸런싱 (분기 첫째주 월요일 09:00)
0 9 1-7 1,4,7,10 1 /path/to/kairos_env/bin/python /path/to/kairos-1/scripts/quarterly_rebalance.py

# 일일 성과 보고서 (매일 18:00)
0 18 * * * /path/to/kairos_env/bin/python /path/to/kairos-1/scripts/performance_report.py --periods 7 30 --send-alert
```

### 2. 시스템 서비스 등록 (Ubuntu)
```bash
# 서비스 파일 생성
sudo vim /etc/systemd/system/kairos1.service
```

```ini
[Unit]
Description=KAIROS-1 Trading System
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/kairos-1
Environment=PATH=/path/to/kairos_env/bin
ExecStart=/path/to/kairos_env/bin/python /path/to/kairos-1/kairos1_main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# 서비스 활성화
sudo systemctl daemon-reload
sudo systemctl enable kairos1.service
sudo systemctl start kairos1.service

# 상태 확인
sudo systemctl status kairos1.service
```

## 📊 모니터링 설정

### 1. 로그 관리
```bash
# 로그 로테이션 설정
sudo vim /etc/logrotate.d/kairos1
```

```
/path/to/kairos-1/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 your_username your_username
}
```

### 2. 백업 설정
```bash
# 백업 스크립트 생성
vim scripts/backup.sh
```

```bash
#!/bin/bash
# KAIROS-1 백업 스크립트

BACKUP_DIR="/path/to/backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# 데이터베이스 백업
cp data/*.db "$BACKUP_DIR/"

# 설정 파일 백업
cp config/config.yaml "$BACKUP_DIR/"

# 로그 파일 백업 (최근 7일)
find logs/ -name "*.log" -mtime -7 -exec cp {} "$BACKUP_DIR/" \;

echo "백업 완료: $BACKUP_DIR"
```

```bash
# 실행 권한 부여
chmod +x scripts/backup.sh

# 크론잡 추가 (매일 03:00)
0 3 * * * /path/to/kairos-1/scripts/backup.sh
```

## 🔒 보안 강화

### 1. 방화벽 설정
```bash
# UFW 방화벽 설정 (Ubuntu)
sudo ufw enable
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 443  # HTTPS만 허용
```

### 2. API 키 보안
```bash
# 설정 파일 권한 강화
chmod 600 config/config.yaml
chmod 600 config/.encryption_key

# 소유자만 접근 가능하도록 설정
chown your_username:your_username config/config.yaml
```

### 3. 시스템 업데이트
```bash
# 정기적인 시스템 업데이트
sudo apt update && sudo apt upgrade -y  # Ubuntu
# sudo yum update -y  # CentOS

# Python 패키지 업데이트
pip install --upgrade -r requirements.txt
```

## 🚨 장애 대응

### 1. 일반적인 문제들

#### API 연결 실패
```bash
# 1. 네트워크 연결 확인
ping api.coinone.co.kr

# 2. API 키 검증
python -c "
from src.trading.coinone_client import CoinoneClient
from src.utils.config_loader import ConfigLoader
config = ConfigLoader('config/config.yaml')
api_config = config.get('api.coinone')
client = CoinoneClient(api_config['api_key'], api_config['secret_key'])
print(client.get_account_info())
"
```

#### 데이터베이스 문제
```bash
# 데이터베이스 무결성 검사
sqlite3 data/kairos1.db ".schema"
sqlite3 data/kairos1.db "PRAGMA integrity_check;"
```

#### 메모리 부족
```bash
# 메모리 사용량 확인
free -h
ps aux | grep python

# 로그 파일 정리
find logs/ -name "*.log" -mtime +30 -delete
```

### 2. 긴급 정지 절차
```bash
# 시스템 즉시 정지
sudo systemctl stop kairos1.service

# 모든 Python 프로세스 확인
ps aux | grep kairos

# 필요시 강제 종료
sudo pkill -f kairos1_main.py
```

### 3. 복구 절차
```bash
# 1. 최근 백업에서 복원
cp /path/to/backups/latest/kairos1.db data/

# 2. 설정 파일 복원
cp /path/to/backups/latest/config.yaml config/

# 3. 시스템 재시작
sudo systemctl start kairos1.service

# 4. 상태 확인
python kairos1_main.py --system-status
```

## 📈 성능 최적화

### 1. 시스템 튜닝
```bash
# Python 최적화 모드로 실행
export PYTHONOPTIMIZE=1

# 메모리 사용량 최적화
export PYTHONDONTWRITEBYTECODE=1
```

### 2. 데이터베이스 최적화
```bash
# SQLite 최적화
sqlite3 data/kairos1.db "VACUUM;"
sqlite3 data/kairos1.db "ANALYZE;"
```

### 3. 네트워크 최적화
```yaml
# config.yaml에서 타임아웃 조정
api:
  coinone:
    timeout: 15  # 네트워크 상황에 맞게 조정
    rate_limit: 100
```

## 📞 지원 및 문의

### 로그 분석
```bash
# 오류 로그 확인
tail -f logs/kairos1_main.log | grep ERROR

# 특정 기간 로그 분석
grep "$(date +%Y-%m-%d)" logs/kairos1_main.log
```

### 문제 보고시 포함할 정보
1. 시스템 정보: `uname -a`
2. Python 버전: `python --version`
3. 패키지 버전: `pip freeze`
4. 오류 로그: 관련 로그 파일 내용
5. 설정 정보: 민감한 정보 제외한 config.yaml

---

**⚠️ 주의사항**
- 실제 거래 전 반드시 샌드박스 모드에서 충분히 테스트
- API 키는 절대 공개하지 말 것
- 정기적인 백업과 모니터링 필수
- 큰 금액 거래시 단계적 증액 권장 