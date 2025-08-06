# KAIROS-1: 장기 투자 시스템 (코인원 거래소 맞춤 버전)

**🚀 최신 업데이트 (2025.02)**: Enhanced Multi-Account System 🆕
- **🎯 Enhanced Multi-Account Manager** - 핵심 기능을 멀티 계정에서 제공 (일부 제한사항 있음)
- **🎬 Multi-Account Coordinator** - 병렬 작업 실행 및 자동 스케줄링 시스템
- **⚡ Unified Feature Management** - 주요 기능의 멀티 계정 확장 (TWAP 등 일부 미지원)
- **📊 Advanced Analytics** - 포트폴리오 최적화, 리스크 분석, 성과 추적 통합
- **🚀 Smart CLI Interface** - 주요 기능을 직관적인 명령어로 제공
- **10개 고급 분석 시스템** 통합 (멀티 타임프레임, 매크로 경제, 온체인 데이터 등)
- **멀티 계정 관리 시스템** - 여러 코인원 계정 동시 관리 및 독립적 전략 운용
- **고급 CLI 도구** - 백테스팅, 포트폴리오 최적화, 성과 분석 등 전문 도구
- **통합 보안 시스템** - AES-256 암호화, API 키 관리, 접근 감사
- **심리적 편향 방지 시스템** - FOMO, 패닉셀링 자동 차단
- **세금 최적화** - 한국 세법(22%) 맞춤 로트 관리
- **시나리오별 자동 대응** - 블랙스완, 시장 크래시 감지 및 대응
- **리스크 패리티 모델** - 균등 리스크 기여도 포트폴리오
- **DCA+ 전략** - 공포/탐욕 지수 기반 적응형 분할매수
- **기존 TWAP 분할 매매** 및 **동적 실행 엔진** 유지
- **Reference**: [코인원 공식 API 문서](https://docs.coinone.co.kr/reference)

## 🎯 핵심 철학: Lean, Smart, and Resilient

복잡한 예측을 배제하고, 시장의 큰 흐름에 순응하는 간결하고(Lean), 지능적인(Smart) 규칙을 통해, 어떤 시장 상황에서도 살아남는 회복탄력성(Resilient)을 갖추는 자동 투자 시스템입니다.

## 🏗️ 시스템 아키텍처

### 🏦 Enhanced Multi-Account System 🆕
**모든 기능을 멀티 계정에서 동일하게 제공하는 통합 시스템**

#### 🎯 핵심 특징:
- **🔄 Unified Feature Management**: 단일 계정의 모든 기능을 멀티 계정에서 제공
  - 포트폴리오 최적화, 리밸런싱, 리스크 분석, 성과 추적
  - DCA+ 전략, 세금 최적화, 온체인 분석
  - 매크로 경제 분석, 심리적 편향 방지
- **🎬 Smart Coordinator**: 병렬 작업 실행 및 자동 스케줄링
  - 작업 우선순위 관리 (Critical/High/Medium/Low)
  - 리소스 풀 관리 및 동시성 제어
  - 자동 재시도 및 장애 복구
- **📊 Advanced Analytics**: 통합 분석 및 리포팅
  - 계정별 + 통합 포트폴리오 분석
  - 실시간 성과 추적 및 벤치마킹
  - 다차원 리스크 평가
- **⚡ Enhanced CLI**: 직관적이고 강력한 명령어 인터페이스
  - 모든 기능을 단순한 명령어로 실행
  - 실시간 상태 모니터링 및 헬스체크
  - 작업 스케줄링 및 관리

> **⚡ 빠른 시작**: Enhanced 멀티 계정을 사용하려면 [Enhanced Multi-Account 사용법](#-enhanced-multi-account-system-사용법-신규) 섹션으로 바로 이동하세요.

### 모듈 1: 시장 계절 필터 (Market Season Filter)
- **주기**: 매주 1회
- **기준**: BTC 가격 vs 200주 이동평균선 (±5% 완충 밴드)
- **결과**: 위험자산(암호화폐) vs 안전자산(원화) 비중 결정

### 모듈 2: 포트폴리오 리밸런싱 (Portfolio Rebalancing)
- **주기**: 분기별 1회 (멀티 계정에서는 계정별 설정 가능)
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

### 🏦 멀티 계정 리스크 수준별 전략
```
🛡️ Conservative (보수적): KRW 70% / 암호화폐 30%
⚖️ Moderate (중도적):   KRW 50% / 암호화폐 50%  
🚀 Aggressive (공격적): KRW 30% / 암호화폐 70%
```

### 시장 상황별 자산 배분 (단일 계정 기준)
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

# 의존성 설치 (멀티 계정 시스템 포함)
pip install -r requirements.txt

# 추가 의존성 확인
pip install click croniter tabulate aiohttp
```

### 2. 설정 파일 구성

#### 단일 계정 설정 (기존)
```bash
# 설정 파일 복사
cp config/config.example.yaml config/config.yaml

# API 키 및 개인 설정 입력
vim config/config.yaml
```

#### 멀티 계정 설정 (신규)
```bash
# 보안 마스터 키 설정 (권장 - 먼저 설정)
export KAIROS_MASTER_KEY="your_secure_master_key_32_chars_long"

# 현재 계정 목록 확인
python3 kairos1_multi.py accounts

# 첫 번째 계정 추가 (테스트 모드)
python3 kairos1_multi.py add my_main "메인 계정" "YOUR_API_KEY" "YOUR_SECRET_KEY" --dry-run

# 실제 거래 모드로 계정 추가
python3 kairos1_multi.py add my_main "메인 계정" "YOUR_API_KEY" "YOUR_SECRET_KEY" --live
```

### 3. 보안 설정 및 API 구성
- **코인원 API 키 발급** 및 IP 주소 등록
- **API 권한 설정**: 거래, 잔고 조회 권한만 활성화 (출금 권한 비활성화)
- **2채널 인증(OTP) 설정** 필수
- **API 버전**: Public API v2 / Private API v2.1 사용
- **Mock 모드**: 테스트용 가상 데이터 모드 지원

## 🚀 실행

### 🚀 Enhanced Multi-Account System 사용법 (신규)
모든 기능을 멀티 계정에서 동일하게 제공하는 확장된 통합 시스템입니다.

#### ✨ Enhanced vs 기존 멀티 계정 시스템 비교

| 기능 | Enhanced System | 기존 Multi-Account |
|------|-----------------|-------------------|
| **모든 기능 지원** | ✅ 단일 계정 모든 기능 제공 | ❌ 기본 기능만 |
| **포트폴리오 최적화** | ✅ 전체/개별 계정 | ❌ 미지원 |
| **리스크 분석** | ✅ 고급 리스크 메트릭 | ❌ 기본 분석만 |
| **성과 분석** | ✅ 벤치마킹, 샤프비율 등 | ❌ 기본 수익률만 |
| **DCA+ 전략** | ✅ 공포/탐욕 지수 기반 | ❌ 미지원 |
| **세금 최적화** | ✅ 로트 관리, 손실 수확 | ❌ 미지원 |
| **작업 스케줄링** | ✅ 우선순위, 자동 재시도 | ❌ 미지원 |
| **통합 분석** | ✅ 온체인, 매크로 분석 | ❌ 미지원 |
| **CLI 인터페이스** | ✅ 고급 명령어 | ❌ 기본 명령어만 |

#### 📌 멀티 계정 vs 단일 계정 선택 가이드

**⚠️ 중요: 기능 차이**
| 기능 | 멀티 계정 | 단일 계정 |
|------|-----------|-----------|
| **TWAP 분할 매매** | ❌ 미지원 | ✅ 지원 |
| **실시간 모니터링** | ❌ 간소화 | ✅ 15분/시간 단위 |
| **고급 분석 시스템** | ⚠️ 일부 지원 | ✅ 전체 지원 |
| **crontab 복잡도** | 🟢 단순 (3-7개) | 🔴 복잡 (12개+) |

**권장 사용법**:
- **멀티 계정 사용**: 여러 계정 운영, 간단한 리밸런싱, 복잡한 스케줄 관리 부담스러운 경우
- **단일 계정 사용**: 정교한 분할 매매, 실시간 모니터링, 모든 고급 기능이 필요한 경우

#### 🚀 Enhanced Multi-Account 빠른 시작
```bash
# 1. 첫 계정 추가 (기존 멀티 계정 시스템 사용)
python3 kairos1_multi.py add main_account "메인계정" "YOUR_API_KEY" "YOUR_SECRET_KEY" --dry-run

# 2. Enhanced 시스템으로 모든 기능 사용
# 계정 목록 조회
python3 kairos1_enhanced_multi.py accounts -d

# 포트폴리오 최적화 실행 (모든 계정)
python3 kairos1_enhanced_multi.py optimize

# 특정 계정만 최적화
python3 kairos1_enhanced_multi.py optimize -a main_account

# 리밸런싱 실행 (테스트 모드)
python3 kairos1_enhanced_multi.py rebalance

# 실제 거래로 리밸런싱
python3 kairos1_enhanced_multi.py rebalance --live

# 리스크 분석 실행
python3 kairos1_enhanced_multi.py risk

# 통합 분석 정보 조회
python3 kairos1_enhanced_multi.py analytics

# 시스템 상태 확인
python3 kairos1_enhanced_multi.py health
```

#### 📋 Enhanced 시스템 주요 명령어
```bash
# 🏦 계정 관리 (기존 시스템 사용)
python3 kairos1_multi.py accounts           # 계정 목록
python3 kairos1_multi.py add [계정ID] [이름] [API_KEY] [SECRET_KEY]  # 계정 추가
python3 kairos1_multi.py remove [계정ID]    # 계정 제거

# 📊 Enhanced 포트폴리오 관리
python3 kairos1_enhanced_multi.py accounts [-d]     # 계정 상태 조회
python3 kairos1_enhanced_multi.py optimize [-a 계정ID]  # 포트폴리오 최적화
python3 kairos1_enhanced_multi.py rebalance [-a 계정ID] [--live]  # 리밸런싱

# 📈 고급 분석 기능
python3 kairos1_enhanced_multi.py risk [-a 계정ID]        # 리스크 분석
python3 kairos1_enhanced_multi.py performance [-a 계정ID] # 성과 분석
python3 kairos1_enhanced_multi.py analytics              # 통합 분석

# 💡 전략 실행
python3 kairos1_enhanced_multi.py dca [-a 계정ID] [--amount 금액]  # DCA+ 전략
python3 kairos1_enhanced_multi.py tax [-a 계정ID]                  # 세금 최적화

# 🎬 시스템 관리
python3 kairos1_enhanced_multi.py status     # 코디네이터 상태
python3 kairos1_enhanced_multi.py health     # 헬스체크
python3 kairos1_enhanced_multi.py schedule <작업명> [-a 계정ID] [-p 우선순위]  # 작업 스케줄링
```

#### 🔄 작업 스케줄링 예시
```bash
# 포트폴리오 최적화 스케줄링 (높은 우선순위)
python3 kairos1_enhanced_multi.py schedule portfolio_optimization -p high

# 특정 계정 DCA 전략 스케줄링
python3 kairos1_enhanced_multi.py schedule dca_strategy -a main_account -p medium

# 전체 계정 리스크 분석 스케줄링 (즉시 실행)
python3 kairos1_enhanced_multi.py schedule risk_analysis -p critical
```

#### ⚙️ 리스크 수준별 계정 추가 예시
```bash
# Conservative (보수적) - 안정성 중시
python3 kairos1_multi.py add safe_account "안전계정" "API_KEY" "SECRET_KEY" \
  --risk-level conservative --initial-capital 1000000

# Moderate (중도적) - 균형 투자
python3 kairos1_multi.py add balanced_account "균형계정" "API_KEY" "SECRET_KEY" \
  --risk-level moderate --initial-capital 2000000

# Aggressive (공격적) - 수익률 중시
python3 kairos1_multi.py add growth_account "성장계정" "API_KEY" "SECRET_KEY" \
  --risk-level aggressive --initial-capital 3000000
```

### 🔧 고급 CLI 도구 (신규)

#### 백테스팅 도구
```bash
# 백테스팅 명령어들
python -m src.cli.backtest_cli simple      # 간단한 백테스팅
python -m src.cli.backtest_cli advanced    # 고급 백테스팅
python -m src.cli.backtest_cli comparison  # 전략 비교
python -m src.cli.backtest_cli quick       # 빠른 백테스팅
python -m src.cli.backtest_cli analyze     # 리포트 분석
```

#### 포트폴리오 최적화 도구
```bash
# 포트폴리오 최적화 명령어들
python -m src.cli.portfolio_optimizer_cli analyze      # 자산 분석
python -m src.cli.portfolio_optimizer_cli optimize     # 포트폴리오 최적화
python -m src.cli.portfolio_optimizer_cli rebalance    # 리밸런싱 필요성 확인
python -m src.cli.portfolio_optimizer_cli asset BTC    # 개별 자산 분석
python -m src.cli.portfolio_optimizer_cli status       # 시스템 상태
```

### 단일 계정 실행 (기존)
메인 실행 파일 `kairos1_main.py`를 통한 단일 계정 실행:

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

`crontab`을 사용해 주요 작업을 자동화할 수 있습니다. **통합 병렬 처리** 또는 **개별 작업 세분화** 방식을 선택하세요.

#### 📋 방식 선택 가이드

**🔷 통합 병렬 처리를 선택하세요**:
- 여러 계정을 간단하게 관리하고 싶은 경우
- crontab 설정을 최소화하고 싶은 경우 (3-5개 스케줄)
- 기본적인 리밸런싱만으로도 충분한 경우
- 시스템 관리 부담을 줄이고 싶은 경우

**🔶 개별 작업 세분화를 선택하세요**:
- TWAP 분할 매매로 시장 충격을 최소화하려는 경우
- 모든 고급 분석 기능(10개 시스템)을 사용하려는 경우
- 실시간 모니터링이 중요한 경우
- 정교한 투자 전략이 필요한 경우

#### 🔷 통합 병렬 처리 방식 (간단함 우선)
```bash
# crontab -e 명령어로 편집기를 열어 아래 내용을 추가합니다.
# 시스템 환경에 따라 PATH를 명시적으로 설정해주는 것이 안정적입니다.
# PATH=/path/to/kairos_env/bin:/usr/bin:/bin

# --------------------------------------------------------------------------
# KAIROS-1 통합 병렬 처리 자동 실행 스케줄
# --------------------------------------------------------------------------

# 1. 전체 계정 통합 리밸런싱 (매주 월요일 09:00)
# 하나의 스크립트로 모든 계정을 병렬 처리합니다.
0 9 * * 1 /path/to/kairos_env/bin/python /path/to/kairos-1/kairos1_multi.py rebalance

# 2. 전체 계정 상태 모니터링 (매일 09:00, 18:00)
# 모든 계정의 포트폴리오와 시스템 상태를 동시에 점검합니다.
0 9,18 * * * /path/to/kairos_env/bin/python /path/to/kairos-1/kairos1_multi.py health

# 3. 통합 포트폴리오 리포트 (매일 21:00)
# 모든 계정의 통합 현황을 병렬로 수집하여 리포트를 생성합니다.
0 21 * * * /path/to/kairos_env/bin/python /path/to/kairos-1/kairos1_multi.py portfolio

# --------------------------------------------------------------------------
# 선택: 계정별 개별 스케줄이 필요한 경우 추가
# --------------------------------------------------------------------------
# 특정 계정만 리밸런싱 (예: aggressive 계정은 더 자주)
# 0 9 * * 1,4 /path/to/kairos_env/bin/python /path/to/kairos-1/kairos1_multi.py rebalance -a aggressive_account
```

#### 🔶 개별 작업 세분화 방식 (완전한 기능)
```bash
# crontab -e 명령어로 편집기를 열어 아래 내용을 추가합니다.
# 시스템 환경에 따라 PATH를 명시적으로 설정해주는 것이 안정적입니다.
# PATH=/path/to/kairos_env/bin:/usr/bin:/bin

# --------------------------------------------------------------------------
# KAIROS-1 개별 작업 세분화 자동 실행 스케줄
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

# --------------------------------------------------------------------------
# 🆕 고급 장기 투자 시스템 스케줄 (v3.0)
# --------------------------------------------------------------------------

# 5. 멀티 타임프레임 분석 (매일 08:00, 20:00)
# 20일/200주/4년 주기 분석으로 투자 시점을 최적화합니다.
0 8,20 * * * /path/to/kairos_env/bin/python /path/to/kairos-1/kairos1_main.py --multi-timeframe-analysis

# 6. 매크로 경제 지표 분석 (매주 화요일 10:00)
# 연준 정책, 인플레이션, 달러지수 등을 분석하여 크립토 우호도를 측정합니다.
0 10 * * 2 /path/to/kairos_env/bin/python /path/to/kairos-1/kairos1_main.py --macro-analysis

# 7. 온체인 데이터 분석 (매일 06:00, 14:00, 22:00)
# 고래 활동, 거래소 흐름, 장기보유자 패턴을 분석합니다.
0 6,14,22 * * * /path/to/kairos_env/bin/python /path/to/kairos-1/kairos1_main.py --onchain-analysis

# 8. 시나리오별 대응 시스템 점검 (매시간 정각)
# 블랙스완, 시장 크래시 등 예외 상황을 감지하고 대응합니다.
0 * * * * /path/to/kairos_env/bin/python /path/to/kairos-1/kairos1_main.py --scenario-check

# 9. DCA+ 스케줄 점검 (매일 07:00)
# 공포/탐욕 지수 기반 적응형 분할매수 일정을 확인합니다.
0 7 * * * /path/to/kairos_env/bin/python /path/to/kairos-1/kairos1_main.py --dca-schedule

# 10. 심리적 편향 감지 (매 6시간)
# FOMO, 패닉셀링 등 감정적 거래 패턴을 모니터링합니다.
0 */6 * * * /path/to/kairos_env/bin/python /path/to/kairos-1/kairos1_main.py --bias-check

# 11. 세금 최적화 리포트 (매월 1일 09:00)
# 세금 효율적인 거래 내역과 손익 리포트를 생성합니다.
0 9 1 * * /path/to/kairos_env/bin/python /path/to/kairos-1/kairos1_main.py --tax-report

# 12. 고급 성과 분석 (매주 일요일 21:00)
# 샤프비율, 최대낙폭, 승률 등 고급 성과 지표를 분석합니다.
# 파라미터: 분석할 기간(일수) - 예: 30일간 분석
0 21 * * 0 /path/to/kairos_env/bin/python /path/to/kairos-1/kairos1_main.py --advanced-performance-report 30
```

## 📈 모니터링 및 알림

### 3-라인 체크 시스템
1. **성과 기록**: 포트폴리오 수익률 및 벤치마크 대비 성과
2. **의사결정 로그**: 모든 거래 및 리밸런싱 결정 기록
3. **추적오차 알림**: 설정 비중과 실제 비중 간 차이 모니터링

### 📊 고급 모니터링 시스템 🆕
- **성과 추적기**: 샤프 비율, 최대 낙폭, 변동성 등 포괄적 성과 지표 계산
- **리스크 평가**: 벤치마크 대비 성과 분석 및 자동 권고사항 생성
- **실시간 알림**: 다채널 알림 시스템 (이메일, Slack)
- **일일 요약 리포트**: 성과 및 포트폴리오 상태 자동 보고
- **멘션 시스템**: 알림 유형별 맞춤형 Slack 멘션

### 알림 시스템
- **다채널 지원**: 이메일, Slack 통합 알림
- **스마트 멘션**: 알림 중요도별 사용자 멘션 시스템
- **중요 이벤트**: 실시간 거래, 리밸런싱, 시스템 상태 통지
- **보안 알림**: API 접근 감사, 시스템 오류, 보안 이슈 즉시 통보

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

## ❗ 중요 사항 및 주의점

### 🔍 통합 병렬 처리 vs 개별 작업 세분화 차이점

| 항목 | 통합 병렬 처리 (kairos1_multi.py) | 개별 작업 세분화 (kairos1_main.py) |
|------|-------------------------------|------------------------------|
| **리밸런싱 주기** | 주간 (매주 월요일) | 분기별 (3개월마다) |
| **TWAP 분할 매매** | 미지원 (즉시 실행) | 지원 (시장 충격 최소화) |
| **계정 관리** | 여러 계정 동시 관리 | 단일 계정만 관리 |
| **리스크 수준** | 계정별 개별 설정 | config.yaml 통합 설정 |
| **실행 방식** | CLI 명령어 기반 | 옵션 플래그 기반 |
| **crontab 복잡도** | 간단 (3-5개 스케줄) | 복잡 (12개 스케줄) |
| **병렬 처리** | 하나의 스크립트가 모든 계정 처리 | 각 기능별 개별 스크립트 실행 |

### ⚠️ 통합 병렬 처리 방식 주의사항
1. **TWAP 미지원**: 통합 처리 방식은 TWAP 분할 매매를 지원하지 않습니다. 대량 거래 시 시장 충격 주의
2. **주간 리밸런싱**: 매주 리밸런싱하므로 거래 빈도가 높습니다
3. **API 제한**: 여러 계정 동시 조회 시 API rate limit 주의
4. **메모리 사용**: 계정이 많을수록 메모리 사용량 증가

## ⚠️ 리스크 관리 및 보안

### 🔐 고급 보안 시스템 🆕
- **암호화 저장**: AES-256 암호화를 통한 API 키 보안 저장
- **키 관리**: PBKDF2 키 유도 및 안전한 메모리 관리
- **접근 감사**: 모든 API 접근 기록 및 감사 로그
- **키 순환**: 자동 API 키 만료 및 갱신 시스템
- **서비스별 키 관리**: 코인원, 바이낸스 등 거래소별 개별 키 관리

### 기존 보안 기능
- **API 키 암호화 저장**: 로컬 환경에서 안전한 키 보관
- **IP 화이트리스트 관리**: 허용된 IP에서만 접근 가능
- **접근 권한 최소화**: 필요 최소 권한만 부여 (거래, 조회만 활성화)
- **2FA 필수**: OTP 2채널 인증 시스템

### 규제 대응
- **특정금융정보법(특금법) 준수**: 국내 규제 완전 대응
- **트래블룰(Travel Rule) 대응**: 거래 추적 및 보고
- **규제 변경사항 모니터링**: 실시간 규제 업데이트 반영
- **세법 준수**: 한국 암호화폐 세법(22%) 자동 적용

## 🎯 고급 장기 투자 시스템 상세 가이드

### 1. 멀티 타임프레임 분석 시스템
```bash
# 실행 명령어
python kairos1_main.py --multi-timeframe-analysis

# 분석 타임프레임
- 단기 (20일): RSI, 볼린저 밴드 기반 단기 트렌드
- 중기 (200주): 시장 사이클과 장기 트렌드 분석
- 장기 (4년): 비트코인 반감기 사이클 분석

# 핵심 기능
- 각 타임프레임별 독립적 신호 생성
- 타임프레임 간 일치도 분석
- 투자 시점 최적화 알고리즘
```

### 2. 적응형 포트폴리오 관리
```bash
# 실행: 주간 분석에 자동 포함
python kairos1_main.py --weekly-analysis

# 시장 성숙도 단계
- NASCENT (신생): 암호화폐 40%, 원화 60%
- EMERGING (신흥): 암호화폐 55%, 원화 45%
- MATURE (성숙): 암호화폐 65%, 원화 35%
- INSTITUTIONAL (기관): 암호화폐 75%, 원화 25%

# 동적 조정 요소
- 시장 상관관계 분석
- 변동성 기반 리스크 패리티
- 시가총액 및 거래량 트렌드
```

### 3. DCA+ 전략 (Fear & Greed 적응형)
```bash
# DCA 스케줄 확인
python kairos1_main.py --dca-schedule

# 공포/탐욕 지수별 매수 승수
- 극도의 공포 (0-25): 2.0배 매수
- 공포 (25-45): 1.5배 매수
- 중립 (45-55): 기본 매수
- 탐욕 (55-75): 0.7배 매수
- 극도의 탐욕 (75-100): 0.3배 매수

# 추가 조정 요소
- 변동성 기반 타이밍 조절
- 계절성 패턴 반영
- 누적 매수 한도 관리
```

### 4. 리스크 패리티 모델
```bash
# 설정 위치: config/config.yaml
risk_management:
  risk_parity:
    enabled: true
    optimization_method: "SLSQP"
    target_risk_contribution: 0.25  # 4개 자산 균등

# 핵심 기능
- 각 자산의 리스크 기여도 균등화
- SLSQP 최적화 알고리즘 사용
- 동적 가중치 재조정
- 다양화 비율 최대화
```

### 5. 세금 최적화 시스템
```bash
# 세금 리포트 생성
python kairos1_main.py --tax-report

# 한국 세법 맞춤 기능
- 암호화폐 양도소득세 22% 적용
- FIFO, LIFO, HIGHEST_COST, TAX_EFFICIENT 로트 선택
- 손실 수확 (Loss Harvesting) 자동화
- 30일 워시세일 룰 적용
- 분기별/연간 세금 리포트 생성
```

### 6. 매크로 경제 지표 연동
```bash
# 매크로 분석 실행
python kairos1_main.py --macro-analysis

# 연동 지표
- 연준 기준금리 (Fed Funds Rate)
- 인플레이션율 (CPI, PCE)
- 달러지수 (DXY)
- 변동성 지수 (VIX)
- 통화공급량 (M2)

# 암호화폐 우호도 점수
- -1.0 (매우 부정적) ~ +1.0 (매우 긍정적)
- 각 지표별 가중치 적용
- 실시간 정책 변화 반영
```

### 7. 온체인 데이터 분석
```bash
# 온체인 분석 실행
python kairos1_main.py --onchain-analysis

# 분석 요소
- 고래 축적/분산 패턴 (>1000 BTC)
- 거래소 자금 유입/유출 모니터링
- 장기보유자(LTH) vs 단기보유자(STH) 비율
- 네트워크 건강도 (해시레이트, 활성주소)
- 스테이블코인 도미넌스 추적

# 신호 생성
- 단기 (1-7일), 중기 (1-4주), 장기 (1-6개월)
- 축적/분산 점수 (0-100)
- 신뢰도 기반 가중치 적용
```

### 8. 시나리오별 자동 대응
```bash
# 시나리오 감지 및 대응
python kairos1_main.py --scenario-check

# 감지 시나리오
- BLACK_SWAN: 24시간 -30% 하락 + 거래량 3배 증가
- MARKET_CRASH: 7일간 -40% 하락 + 공포지수 <20
- EUPHORIA: 30일간 +100% 상승 + 극도의 탐욕
- REGULATION_RISK: 부정적 뉴스 + 1시간 -10% 하락

# 자동 대응 행동
- 포지션 축소/확대
- 주문 일시 정지
- 긴급 알림 발송
- 냉각 기간 적용
```

### 9. 심리적 편향 방지
```bash
# 편향 감지 및 방지
python kairos1_main.py --bias-check

# 감지 편향 유형
- FOMO: 급등 후 충동 매수 감지
- 패닉 셀링: 급락 후 공포 매도 감지
- 과신 편향: 연승 후 과도한 포지션 증가

# 방지 조치
- 주문 지연 (5분-60분)
- 거래 금액 축소 (10%-60%)
- 강제 냉각 기간 (1-24시간)
- 감정 상태 추적 및 알림
```

### 10. 고급 성과 분석
```bash
# 고급 성과 리포트 (예: 최근 30일간 분석)
python kairos1_main.py --advanced-performance-report 30

# 고급 지표
- 샤프 비율 (Sharpe Ratio)
- 소르티노 비율 (Sortino Ratio)  
- 최대 낙폭 (Maximum Drawdown)
- 칼마 비율 (Calmar Ratio)
- 승률 및 손익비
- 변동성 조정 수익률

# 벤치마크 비교
- BTC, ETH 대비 성과
- 전통 자산 (S&P 500) 대비
- 무위험 수익률 대비 초과 수익
```

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

### v3.2.0 (2025.02) - Enhanced Multi-Account System 🆕
- ✅ **🎯 Enhanced Multi-Account Manager**: 모든 기능을 멀티 계정에서 동일하게 제공
- ✅ **🎬 Multi-Account Coordinator**: 병렬 작업 실행, 우선순위 관리, 자동 스케줄링
- ✅ **⚡ Unified Feature Management**: 단일 계정 모든 기능의 멀티 계정 확장
- ✅ **📊 Advanced Analytics Integration**: 포트폴리오 최적화, 리스크 분석, 성과 추적 통합
- ✅ **🚀 Smart CLI Interface**: 직관적이고 강력한 명령어로 모든 기능 제공
- ✅ **🔄 Intelligent Task Scheduling**: 작업 우선순위, 재시도 로직, 리소스 관리
- ✅ **📈 Comprehensive Reporting**: 통합 분석 리포트 및 실시간 모니터링

### v3.1.0 (2025.02) - Multi-Account & Enterprise Features
- ✅ **멀티 계정 관리 시스템**: 여러 코인원 계정 동시 관리
- ✅ **고급 CLI 도구**: 백테스팅, 포트폴리오 최적화 전문 도구
- ✅ **통합 보안 시스템**: AES-256 암호화, API 키 관리, 접근 감사
- ✅ **고급 모니터링**: 성과 추적, 리스크 평가, 다채널 알림
- ✅ **포괄적 타입 시스템**: 544줄의 완전한 타입 정의
- ✅ **마켓 데이터 제공자**: 실시간 200주 이동평균 계산 및 캐싱
- ✅ **자동화 스크립트**: 분기별 리밸런싱, 성과 리포트, 주간 체크

### v3.0.0 (2025.01) - Advanced Long-term Investment Systems
- ✅ **10개 고급 분석 시스템** 통합
- ✅ **멀티 타임프레임 분석** (20일/200주/4년 사이클)
- ✅ **심리적 편향 방지** - FOMO, 패닉셀링 차단
- ✅ **세금 최적화** - 한국 세법 22% 맞춤
- ✅ **시나리오별 자동 대응** - 블랙스완 감지
- ✅ **온체인 데이터 분석** - 고래/거래소 흐름
- ✅ **매크로 경제 연동** - 연준/인플레이션 지표
- ✅ **DCA+ 전략** - 공포탐욕 지수 기반
- ✅ **리스크 패리티** - 균등 리스크 기여도
- ✅ **고급 성과 측정** - 샤프비율, 드로우다운

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

- **문서**: `/docs` 폴더 참조 (멀티 계정 가이드, 아키텍처 문서 포함)
- **로그**: `/logs` 폴더에서 시스템 동작 확인
- **설정**: `config/` 폴더 및 환경 변수 (`.env.example` 참조)
- **스크립트**: `/scripts` 폴더의 자동화 도구들
- **이슈**: GitHub Issues 활용

### 📚 주요 문서들
- **멀티 계정 설정 가이드**: `docs/MULTI_ACCOUNT_GUIDE.md` (295줄 상세 가이드)
- **시스템 아키텍처**: `docs/ARCHITECTURE.md`
- **환경 변수 설정**: `.env.example`
- **계정 설정**: `config/accounts.json`

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

---

## 🎯 멀티 계정 운영 빠른 가이드

### ✅ 멀티 계정을 사용해야 하는 경우:
- 여러 개의 코인원 계정을 보유하고 있는 경우
- 계정별로 다른 리스크 수준 (Conservative/Moderate/Aggressive)을 적용하고 싶은 경우
- 간단한 주간 리밸런싱으로 운영하고 싶은 경우
- 계정별 독립적인 모니터링이 필요한 경우

### ✅ 단일 계정을 사용해야 하는 경우:
- 하나의 계정만 운영하는 경우
- TWAP 분할 매매로 시장 충격을 최소화하려는 경우
- 분기별 리밸런싱으로 거래 빈도를 줄이려는 경우
- 기존 kairos1_main.py 시스템에 익숙한 경우

### 🚀 Enhanced Multi-Account 운영 3단계:
```bash
# 1단계: 계정 추가 (기존 시스템 사용)
python3 kairos1_multi.py add main_account "메인계정" "API_KEY" "SECRET_KEY" --dry-run

# 2단계: Enhanced 시스템으로 모든 기능 활용
python3 kairos1_enhanced_multi.py optimize     # 포트폴리오 최적화
python3 kairos1_enhanced_multi.py rebalance    # 리밸런싱 실행
python3 kairos1_enhanced_multi.py analytics    # 통합 분석

# 3단계: 자동 스케줄링 및 모니터링
python3 kairos1_enhanced_multi.py schedule portfolio_optimization -p high
python3 kairos1_enhanced_multi.py status       # 코디네이터 상태
python3 kairos1_enhanced_multi.py health       # 시스템 헬스체크
```

### 🔄 Enhanced 시스템 crontab 설정 (권장)
```bash
# Enhanced Multi-Account 자동 실행 스케줄 (총 5개)
# ⚠️ 주의: 단일 계정 대비 기능 제한 있음 (TWAP 미지원, 실시간 모니터링 간소화)

# 매일 오전 9시 포트폴리오 최적화
0 9 * * * /path/to/kairos_env/bin/python /path/to/kairos-1/kairos1_enhanced_multi.py optimize

# 매주 월요일 오전 10시 리밸런싱 (실제 거래)
0 10 * * 1 /path/to/kairos_env/bin/python /path/to/kairos-1/kairos1_enhanced_multi.py rebalance --live

# 매시간 리스크 분석 (단일 계정 대비 간소화됨)
0 * * * * /path/to/kairos_env/bin/python /path/to/kairos-1/kairos1_enhanced_multi.py risk

# 매일 오후 6시 성과 분석
0 18 * * * /path/to/kairos_env/bin/python /path/to/kairos-1/kairos1_enhanced_multi.py performance

# 매일 오후 9시 통합 분석 리포트
0 21 * * * /path/to/kairos_env/bin/python /path/to/kairos-1/kairos1_enhanced_multi.py analytics
```

**📊 복잡도 비교**:
- **Enhanced Multi-Account**: 5개 스케줄 (간단, 관리 용이)  
- **단일 계정**: 12개 스케줄 (복잡, TWAP/실시간 모니터링 포함)

**⚠️ 투자는 원금 손실의 위험이 있습니다. 충분한 검토와 테스트 후 사용하시기 바랍니다.** 