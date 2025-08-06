# KAIROS-1 멀티 계정 관리 시스템 사용 가이드

## 개요

KAIROS-1 멀티 계정 관리 시스템은 여러 코인원 계정을 동시에 관리하고 자동화된 투자 전략을 실행할 수 있는 통합 시스템입니다.

## 주요 기능

### 🏦 멀티 계정 관리
- **다중 계정 지원**: 여러 코인원 계정을 동시에 관리
- **개별 설정**: 각 계정별로 독립적인 투자 전략 및 리스크 수준 설정
- **통합 모니터링**: 모든 계정의 성과를 한눈에 확인

### ⚖️ 자동 리밸런싱
- **스케줄 기반**: 설정된 주기(일간, 주간, 월간)에 따른 자동 실행
- **조건 기반 트리거**: 시장 상황이나 포트폴리오 편차에 따른 자동 실행
- **수동 실행**: 필요시 즉시 리밸런싱 실행

### 🔐 보안 관리
- **암호화된 API 키 저장**: AES-256 암호화로 API 키 안전 보관
- **키 로테이션**: 정기적인 API 키 교체 지원
- **접근 감사**: 모든 API 키 접근 로그 기록

### 📊 포트폴리오 관리
- **개별 및 통합 조회**: 계정별 또는 전체 포트폴리오 현황 확인
- **성과 분석**: 수익률, 변동성, 샤프 비율 등 다양한 지표 제공
- **리스크 관리**: 계정별 리스크 수준에 따른 자산 배분

## 시작하기

### 1. 시스템 초기 설정

```bash
# 의존성 설치 확인
pip3 install croniter click tabulate

# 시스템 헬스체크
python3 kairos1_multi.py health
```

### 2. 첫 번째 계정 추가

```bash
# 새 계정 추가 (테스트 모드)
python3 kairos1_multi.py add my_account "내 투자계정" "YOUR_API_KEY" "YOUR_SECRET_KEY" --dry-run

# 실제 거래 모드로 계정 추가
python3 kairos1_multi.py add my_account "내 투자계정" "YOUR_API_KEY" "YOUR_SECRET_KEY" --live
```

### 3. 계정 확인

```bash
# 기본 계정 목록
python3 kairos1_multi.py accounts

# 상세 정보 포함
python3 kairos1_multi.py accounts -d
```

## 사용법

### 계정 관리

#### 계정 추가
```bash
# 기본 설정으로 추가
python3 kairos1_multi.py add account_002 "보조계정" "API_KEY" "SECRET_KEY"

# 상세 설정으로 추가
python3 kairos1_multi.py add account_003 "적극투자계정" "API_KEY" "SECRET_KEY" \
  --risk-level aggressive \
  --initial-capital 5000000 \
  --max-investment 20000000 \
  --live
```

#### 계정 제거
```bash
python3 kairos1_multi.py remove account_002
```

#### 계정 목록 조회
```bash
# 기본 목록
python3 kairos1_multi.py accounts

# 상세 정보
python3 kairos1_multi.py accounts --detailed
```

### 포트폴리오 관리

#### 통합 포트폴리오 현황
```bash
python3 kairos1_multi.py portfolio
```

#### 특정 계정 포트폴리오
```bash
python3 kairos1_multi.py portfolio -a my_account
```

### 리밸런싱

#### 전체 계정 리밸런싱
```bash
# 자동 판단 (필요시에만 실행)
python3 kairos1_multi.py rebalance

# 강제 실행
python3 kairos1_multi.py rebalance --force
```

#### 특정 계정 리밸런싱
```bash
python3 kairos1_multi.py rebalance -a my_account
```

### 스케줄 관리

#### 스케줄 현황 확인
```bash
python3 kairos1_multi.py schedules
```

#### 시스템 상태 확인
```bash
python3 kairos1_multi.py health
```

## 설정 파일

### 계정 설정 파일 (`config/accounts.json`)

```json
{
  "accounts": [
    {
      "account_id": "my_account",
      "account_name": "내 투자계정",
      "description": "주 투자 계정",
      "risk_level": "moderate",
      "initial_capital": 1000000.0,
      "max_investment": 5000000.0,
      "auto_rebalance": true,
      "rebalance_frequency": "weekly",
      "core_allocation": 0.7,
      "satellite_allocation": 0.3,
      "cash_reserve": 0.1,
      "max_position_size": 0.4,
      "dry_run": false
    }
  ],
  "global_settings": {
    "concurrent_operations": 3,
    "health_check_interval": 300,
    "notification_channels": ["slack", "email"]
  }
}
```

### 계정별 설정 옵션

| 설정 | 설명 | 기본값 |
|------|------|--------|
| `account_id` | 계정 고유 ID | - |
| `account_name` | 계정 표시명 | - |
| `risk_level` | 리스크 수준 (conservative/moderate/aggressive) | moderate |
| `initial_capital` | 초기 투자 자본 | 1,000,000 |
| `max_investment` | 최대 투자 한도 | 5,000,000 |
| `auto_rebalance` | 자동 리밸런싱 여부 | true |
| `rebalance_frequency` | 리밸런싱 주기 | weekly |
| `core_allocation` | 코어 자산 비중 | 0.7 |
| `satellite_allocation` | 위성 자산 비중 | 0.3 |
| `max_position_size` | 단일 자산 최대 비중 | 0.4 |
| `dry_run` | 테스트 모드 여부 | true |

## 투자 전략

### 리스크 수준별 자산 배분

#### Conservative (보수적)
- **현금 비중**: 70%
- **암호화폐 비중**: 30%
- **주요 자산**: BTC (60%), ETH (40%)

#### Moderate (중도적)
- **현금 비중**: 50%
- **암호화폐 비중**: 50%
- **주요 자산**: BTC (60%), ETH (40%)
- **위성 자산**: XRP (50%), SOL (50%)

#### Aggressive (공격적)
- **현금 비중**: 30%
- **암호화폐 비중**: 70%
- **높은 위험 자산 비중**

### 시장 상황별 조정

- **Risk On**: 암호화폐 비중 +20%
- **Risk Off**: 암호화폐 비중 -20%
- **Neutral**: 기본 배분 유지

## 모니터링 및 알림

### 시스템 상태 확인
```bash
# 전체 시스템 헬스체크
python3 kairos1_multi.py health

# 스케줄 상태 확인
python3 kairos1_multi.py schedules
```

### 로그 확인
- **위치**: 시스템 로그는 콘솔에 실시간 출력
- **수준**: INFO, WARNING, ERROR
- **내용**: 초기화, 거래 실행, 오류 상황 등

## 주의사항

### ⚠️ 보안
1. **API 키 보안**: API 키는 암호화되어 저장되지만, 마스터 키 설정 필요
2. **환경 변수**: `KAIROS_MASTER_KEY` 환경 변수 설정 권장
3. **접근 제한**: 시스템 파일에 대한 적절한 접근 권한 설정

### ⚠️ 거래 위험
1. **테스트 모드**: 처음에는 반드시 `--dry-run` 모드로 테스트
2. **소액 테스트**: 실제 거래 시 소액으로 먼저 테스트
3. **리스크 관리**: 적절한 리스크 수준 설정 및 모니터링

### ⚠️ 시스템 안정성
1. **정기 모니터링**: 시스템 상태 정기 확인
2. **백업**: 설정 파일 및 로그 정기 백업
3. **업데이트**: 시스템 업데이트 시 테스트 모드로 검증

## 문제 해결

### 일반적인 문제

#### 계정이 ERROR 상태인 경우
```bash
# 원인: API 키 없음 또는 잘못된 키
# 해결: API 키 재설정
python3 kairos1_multi.py remove problematic_account
python3 kairos1_multi.py add problematic_account "계정명" "NEW_API_KEY" "NEW_SECRET_KEY"
```

#### 리밸런싱이 실행되지 않는 경우
```bash
# 스케줄 상태 확인
python3 kairos1_multi.py schedules

# 강제 실행
python3 kairos1_multi.py rebalance --force
```

#### 포트폴리오 조회 실패
```bash
# 헬스체크로 문제 진단
python3 kairos1_multi.py health

# 계정 상태 확인
python3 kairos1_multi.py accounts -d
```

## 고급 사용법

### 프로그래밍 방식 접근
```python
from src.core.multi_account_manager import get_multi_account_manager
from src.core.multi_portfolio_manager import get_multi_portfolio_manager

# 계정 관리자 사용
manager = get_multi_account_manager()
await manager.initialize()

# 포트폴리오 관리자 사용
portfolio = get_multi_portfolio_manager()
await portfolio.initialize()
```

### API 확장
시스템은 확장 가능한 아키텍처로 설계되어 있어 새로운 기능을 쉽게 추가할 수 있습니다.

## 지원

- **GitHub Issues**: 버그 리포트 및 기능 요청
- **문서**: `docs/` 디렉토리의 추가 문서 참고
- **로그 분석**: 문제 발생 시 로그를 통한 상세 진단

---

**⚠️ 투자는 원금 손실의 위험이 있습니다. 충분한 검토와 테스트 후 사용하시기 바랍니다.**