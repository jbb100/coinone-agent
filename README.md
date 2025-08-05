# KAIROS-1: 장기 투자 시스템 (코인원 거래소 맞춤 버전)

**🔄 최신 업데이트 (2025.01)**: 동적 실행 엔진 추가
- **코인원 공식 API v2/v2.1** 명세 100% 준수
- **TWAP (시간 가중 평균 가격) 분할 매매** 지원
- **ATR 기반 변동성 적응형 실행** 
- **시장 충격 최소화** 알고리즘
- **Reference**: [코인원 공식 API 문서](https://docs.coinone.co.kr/reference)

## 🎯 핵심 철학: Lean, Smart, and Resilient

복잡한 예측을 배제하고, 시장의 큰 흐름에 순응하는 간결하고(Lean), 지능적인(Smart) 규칙을 통해, 어떤 시장 상황에서도 살아남는 회복탄력성(Resilient)을 갖추는 자동 투자 시스템입니다.

## 🏗️ 시스템 아키텍처

### 모듈 1: 시장 계절 필터 (Market Season Filter)
- **주기**: 매주 1회
- **기준**: BTC 가격 vs 200주 이동평균선 (±5% 완충 밴드)
- **결과**: 위험자산(암호화폐) vs 안전자산(원화) 비중 결정

### 모듈 2: 포트폴리오 리밸런싱 (Portfolio Rebalancing)
- **주기**: 분기별 1회
- **범위**: 코인원 상장 암호화폐
- **구성**: Core(70%) + Satellite(30%)

### 모듈 3: 동적 실행 엔진 (Dynamic Execution Engine) 🆕
**TWAP (시간 가중 평균 가격) 분할 매매**로 시장 충격을 최소화하는 지능형 실행 시스템

#### 핵심 기능:
- **ATR (Average True Range) 변동성 측정**: 14일 ATR 지표로 시장 상태 자동 판단
- **적응형 실행 전략**:
  - 🟢 **안정 시장** (ATR ≤ 5%): 6시간 동안 12회 분할 신속 실행 (30분 간격)
  - 🔴 **변동 시장** (ATR > 5%): 24시간 동안 24회 분할 보수적 실행 (1시간 간격)
- **최소 주문 금액 보장**: 코인원 거래소 최소 주문 금액(5,000원) 자동 준수
- **실시간 모니터링**: 슬라이스별 실행 진행률 및 남은 시간 실시간 추적

## 📊 투자 전략

### 시장 상황별 자산 배분
```
📈 강세장 (Risk-On): BTC > 200주 MA × 1.05 → 암호화폐 70% / KRW 30%
📉 약세장 (Risk-Off): BTC < 200주 MA × 0.95 → 암호화폐 30% / KRW 70%
➡️ 횡보장 (Neutral): 밴드 내 위치 → 기존 비중 유지
```

### 암호화폐 포트폴리오 구성
```
Core Assets (70%):
├── BTC: 40%
└── ETH: 30%

Satellite Assets (30%):
├── XRP: 15%
└── SOL: 15%
```

## 🛠️ 설치 및 설정

### 1. 환경 설정
```bash
# 가상환경 생성
python -m venv kairos_env
source kairos_env/bin/activate  # macOS/Linux
# kairos_env\Scripts\activate  # Windows

# 의존성 설치
pip install -r requirements.txt
```

### 2. 설정 파일 구성
```bash
# 설정 파일 복사
cp config/config.example.yaml config/config.yaml

# API 키 및 개인 설정 입력
vim config/config.yaml
```

### 3. 보안 설정 및 API 구성
- **코인원 API 키 발급** 및 IP 주소 등록
- **API 권한 설정**: 거래, 잔고 조회 권한만 활성화 (출금 권한 비활성화)
- **2채널 인증(OTP) 설정** 필수
- **API 버전**: Public API v2 / Private API v2.1 사용
- **Mock 모드**: 테스트용 가상 데이터 모드 지원

## 🚀 실행

### 통합 실행 (권장)
메인 실행 파일 `kairos1_main.py`를 통한 통합 실행:

```bash
# 주간 시장 분석
python kairos1_main.py --weekly-analysis

# 분기별 리밸런싱 (즉시 실행)
python kairos1_main.py --quarterly-rebalance

# TWAP 방식 분기별 리밸런싱 (시장 충격 최소화)
python kairos1_main.py --quarterly-rebalance-twap

# 대기 중인 TWAP 주문 처리
python kairos1_main.py --process-twap

# TWAP 주문 상태 조회
python kairos1_main.py --twap-status

# 실패한 TWAP 주문 정리
python kairos1_main.py --clear-failed-twap

# 성과 보고서 생성 (예: 최근 30일)
python kairos1_main.py --performance-report 30

# 시스템 상태 확인
python kairos1_main.py --system-status

# 시뮬레이션 모드 (실제 거래 없이 테스트)
python kairos1_main.py --quarterly-rebalance-twap --dry-run

# 알림 시스템 테스트
python kairos1_main.py --test-alerts
```

### 개별 스크립트 실행
```bash
# 주간 시장 분석 
python scripts/weekly_check.py

# 분기별 리밸런싱
python scripts/quarterly_rebalance.py

# 성과 분석
python scripts/performance_report.py
```

### 자동 실행 (스케줄러)

`crontab`을 사용해 주요 작업을 자동화할 수 있습니다. 아래 예시를 참고하여 시스템에 맞게 경로를 설정하세요.

```bash
# crontab -e 명령어로 편집기를 열어 아래 내용을 추가합니다.
# 시스템 환경에 따라 PATH를 명시적으로 설정해주는 것이 안정적입니다.
# PATH=/path/to/kairos_env/bin:/usr/bin:/bin

# --------------------------------------------------------------------------
# KAIROS-1 자동 실행 스케줄
# --------------------------------------------------------------------------

# 1. 주간 시장 분석 (매주 월요일 09:00)
# 시장 계절(Market Season)을 분석하여 위험자산 비중을 결정합니다.
0 9 * * 1 /path/to/kairos_env/bin/python /path/to/kairos-1/kairos1_main.py --weekly-analysis

# 2. 분기별 포트폴리오 리밸런싱 (매 분기 첫째 주 월요일 09:00)
# TWAP 분할 매매를 시작하여 포트폴리오를 목표 비중으로 조정합니다.
# (1월, 4월, 7월, 10월의 첫 7일 중 월요일에만 실행)
0 9 1-7 1,4,7,10 1 /path/to/kairos_env/bin/python /path/to/kairos-1/kairos1_main.py --quarterly-rebalance-twap

# 3. 대기 중인 TWAP 주문 처리 (15분마다 실행)
# 분할 매매가 시작된 주문을 지속적으로 처리합니다.
# 15분 주기로 실행하여 TWAP 슬라이스 지연을 최소화합니다.
*/15 * * * * /path/to/kairos_env/bin/python /path/to/kairos-1/kairos1_main.py --process-twap

# 4. 일일 시스템 모니터링 (매일 09:00, 18:00)
# 시스템의 전반적인 상태를 점검하고 알림을 보냅니다.
0 9,18 * * * /path/to/kairos_env/bin/python /path/to/kairos-1/kairos1_main.py --system-status
```

## 📈 모니터링

### 3-라인 체크 시스템
1. **성과 기록**: 포트폴리오 수익률 및 벤치마크 대비 성과
2. **의사결정 로그**: 모든 거래 및 리밸런싱 결정 기록
3. **추적오차 알림**: 설정 비중과 실제 비중 간 차이 모니터링

### 알림 시스템
- 이메일/슬랙 알림
- 중요 이벤트 실시간 통지
- 시스템 오류 및 보안 이슈 알림

## 📱 슬랙 알림 설정

### 기본 슬랙 알림 설정
`config/config.yaml` 파일에서 슬랙 알림을 설정할 수 있습니다:

```yaml
notifications:
  slack:
    enabled: true
    webhook_url: "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK"
    channel: "#trading-alerts"
    username: "KAIROS-1"
```

### 슬랙 멘션 기능 🔔

리밸런싱 등 중요한 알림에서 특정 사용자를 멘션할 수 있습니다:

```yaml
notifications:
  slack:
    # ... 기본 설정 ...
    
    # 멘션 설정
    mentions:
      # 기본 멘션 사용자들
      default_users: ["U1234567890", "U0987654321"]
      
      # 특정 알림 유형별 멘션 설정
      by_alert_type:
        # 리밸런싱 관련 알림
        quarterly_rebalance: ["U1234567890"]      # 분기별 리밸런싱
        immediate_rebalance: ["U1234567890"]      # 즉시 리밸런싱
        twap_start: ["U1234567890"]               # TWAP 시작
        
        # 시스템 오류
        system_error: ["@channel"]                # 전체 채널 멘션
        
      # 전체 채널 멘션이 필요한 알림 유형들
      channel_mention_types: ["system_error", "critical_risk"]
```

#### 슬랙 사용자 ID 찾는 방법

1. **슬랙 웹/앱에서 확인:**
   - 사용자 프로필 클릭
   - "Copy member ID" 선택
   - `U1234567890` 형태의 ID 복사

2. **슬랙 API 사용:**
   ```bash
   curl -H "Authorization: Bearer xoxb-your-token" \
   https://slack.com/api/users.list
   ```

#### 지원되는 멘션 형태

- **개별 사용자**: `["U1234567890", "U0987654321"]`
- **채널 전체**: `["@channel"]`
- **온라인 사용자**: `["@here"]`
- **혼합 사용**: `["U1234567890", "@channel"]`

#### 리밸런싱 알림에서 멘션 예시

```yaml
mentions:
  by_alert_type:
    quarterly_rebalance: ["U1234567890"]  # 분기별 리밸런싱 시 멘션
    immediate_rebalance: ["U1234567890", "U0987654321"]  # 즉시 리밸런싱 시 두 명 멘션
    twap_start: ["@here"]  # TWAP 시작 시 온라인 사용자 모두 멘션
```

### 멘션 기능 테스트

```bash
# 알림 시스템 테스트 (멘션 포함)
python kairos1_main.py --test-alerts
```

## ⚠️ 리스크 관리

### 보안
- API 키 암호화 저장
- IP 화이트리스트 관리
- 접근 권한 최소화

### 규제 대응
- 특정금융정보법(특금법) 준수
- 트래블룰(Travel Rule) 대응
- 규제 변경사항 모니터링

## 🔄 TWAP 실행 모니터링

### 실행 상태 확인
```bash
# TWAP 실행 상태 조회
python kairos1_main.py --twap-status

# 출력 예시:
# ✅ TWAP 상태:
# 활성 주문 수: 2개
#   • BTC: 66.7% (8/12 슬라이스)
#     남은 금액: 27,510 KRW
#     남은 시간: 2.0시간
#   • ETH: 50.0% (6/12 슬라이스)
#     남은 금액: 30,949 KRW  
#     남은 시간: 3.0시간
```

### 수동 주문 처리
```bash
# 대기 중인 TWAP 주문 수동 처리 (스케줄러 외)
python kairos1_main.py --process-twap
```

## 📈 업데이트 내역

### v2.0.0 (2025.01) - Dynamic Execution Engine
- ✅ **TWAP 분할 매매 시스템** 추가
- ✅ **ATR 기반 변동성 적응형 실행**  
- ✅ **코인원 공식 API v2.1** 완전 지원
- ✅ **시장 충격 최소화** 알고리즘

### v1.0.0 (2024.12) - Core System
- ✅ 시장 계절 판단기 (200주 이동평균 기반)
- ✅ 포트폴리오 리밸런서 (분기별)
- ✅ 리스크 관리 시스템
- ✅ Slack 알림 시스템

## 📞 지원 및 문의

- **문서**: `/docs` 폴더 참조
- **로그**: `/logs` 폴더에서 시스템 동작 확인
- **이슈**: GitHub Issues 활용

---

> **한 줄 요약**: "ATR로 시장 변동성을 측정하고, TWAP으로 시장 충격을 최소화하며, 200주 이동평균선 기준으로 ±5% 벗어날 때만 큰 포지션 변경을 시도한다." 

### TWAP 관련 트러블슈팅

**문제**: TWAP 주문이 완료되었는데 다시 주문이 들어가고 잔고 부족에서도 계속 실행됨

**원인**:
1. 새로운 분기별 리밸런싱 시작 시 기존 완료된 주문이 정리되지 않음
2. 잔고 부족으로 실패한 주문이 계속 재시도됨

**해결 방법**:
```bash
# 1. 현재 TWAP 상태 확인
python kairos1_main.py --twap-status

# 2. 실패한 주문들 정리
python kairos1_main.py --clear-failed-twap

# 3. 필요시 시스템 재시작으로 완전 초기화
# (새로운 시작 시 완료된 주문은 자동으로 제외됨)
```

**예방**:
- 분기별 리밸런싱은 정해진 스케줄에 따라 자동 실행하고 수동 실행은 최소화
- 정기적으로 `--twap-status`로 상태 모니터링
- 잔고 부족 등의 문제 발생 시 즉시 `--clear-failed-twap`로 정리 