# KAIROS-Simple: 장기 역발상 매집형 자동 트레이딩 (코인원)

**철학: 싸질수록 사고, 비싸질수록 판다.**

복잡한 예측·수십 개 모듈·목업 데이터를 전부 걷어내고, 검증된 세 가지 메커니즘만 남긴
장기 투자 시스템입니다. 세 메커니즘은 모두 같은 방향(역발상)으로 작동합니다.

## 핵심 전략

### 1. 고정 목표 비중 + 밴드 리밸런싱
- 목표: **크립토 60% / KRW 40%** (크립토 내부: BTC 50 / ETH 30 / XRP 10 / SOL 10)
- 총비중이 **±5%p** 이탈할 때만 거래:
  - 상승장 → 크립토 비중 초과 → 초과분 **자동 매도(익절)**
  - 하락장 → 크립토 비중 미달 → 미달분 **자동 매수(저가 매집)**
- 시장 상황에 따라 목표 비중 자체를 바꾸지 않습니다 (추세추종 스위칭 폐지 —
  구버전의 "강세장 70%/약세장 30%"는 구조적으로 고점 매수·저점 매도였음)

### 2. 주간 DCA + 역발상 승수
```
매수액 = 기본액 × F&G승수 × 밸류에이션승수   (0.3 ~ 3.0배 클램프)
```
| Fear & Greed | 승수 | | Mayer Ratio (가격/200주MA) | 승수 |
|---|---|---|---|---|
| 0–24 극공포 | 2.0 | | < 1.0 (역사적 바닥권) | 1.5 |
| 25–44 공포 | 1.5 | | 1.0–2.0 (적정) | 1.0 |
| 45–55 중립 | 1.0 | | 2.0–3.0 (확장) | 0.7 |
| 56–74 탐욕 | 0.7 | | ≥ 3.0 (사이클 과열) | 0.5 |
| 75–100 극탐욕 | 0.3 | | | |

### 3. 리스크 가드 (모든 주문의 단일 관문)
- 단일 거래 ≤ 1,000만원, 일일 거래량 ≤ 5,000만원
- 최소 KRW 비중 10% (전량 몰빵 방지)
- FOMO 가드: 24h +15% 급등 자산은 DCA 외 매수 금지
- **fail-loud**: 시세·지표 조회 실패 시 하드코딩 폴백 없이 거래 중단 + 알림

## 데이터 소스 (전부 무료 실 API — 목업 없음)

| 소스 | 용도 |
|---|---|
| Binance 공개 REST | BTC 200주MA, 24h 변동률 (주봉/일봉) |
| Coinone API | 실시간 시세, 잔고, 주문 체결 |
| alternative.me | Fear & Greed Index |

## 아키텍처

```
kairos1_main.py              # 오케스트레이터 + CLI
src/
├── data/market_data.py      # 실 API 래퍼 (fail-loud)
├── strategy/                # 순수 함수 — 백테스트와 실거래가 동일 코드
│   ├── valuation.py         #   F&G·Mayer 승수, 200주MA
│   ├── dca.py               #   주간 매수 계획
│   └── rebalance.py         #   밴드 이탈 판정 → 주문 목록
├── risk/guard.py            # 단일 리스크 관문
├── execution/executor.py    # 지정가(슬리피지 0.5% 상한)·재시도·TWAP 분할
├── portfolio/portfolio.py   # 잔고 스냅샷·거래 기록
└── report/reporter.py       # 성과 리포트 (벤치마크 = 실제 BTC 보유 수익률)
```

## 사용법

```bash
cp config/config.example.yaml config/config.yaml   # 후 API 키 설정
export COINONE_API_KEY=... COINONE_SECRET_KEY=...

python kairos1_main.py weekly-dca --dry-run    # 주간 DCA (매주 월 09:00 권장)
python kairos1_main.py daily-check --dry-run   # 일일 밴드 체크 (매일 09:00 권장)
python kairos1_main.py report                  # 월간 성과 리포트
python kairos1_main.py status                  # 현재 포트폴리오 상태
```

`--dry-run`을 빼면 실제 주문이 나갑니다. 스케줄링은 cron 예시:

```cron
0 9 * * 1  cd /path/to/repo && python kairos1_main.py weekly-dca
0 9 * * *  cd /path/to/repo && python kairos1_main.py daily-check
0 9 1 * *  cd /path/to/repo && python kairos1_main.py report
```

## 백테스트

실거래와 **동일한 순수 함수**를 사용하며 수수료 0.2% + 슬리피지 0.2%를 반영합니다.

```bash
python scripts/backtest_longterm.py
```

Binance 실데이터 261주(약 5년) 기준: 매수 > 매도(역발상 매집 확인), MDD -28%, Sharpe 1.67.
look-ahead bias 부재가 테스트로 검증됩니다 (`tests/test_backtest_longterm.py`).

## 테스트

```bash
pytest tests/ --cov=src        # 신규 핵심 모듈 커버리지 95–100%
```

## 설계 문서

- 스펙: `docs/superpowers/specs/2026-07-10-longterm-strategy-redesign-design.md`
- 구현 계획: `docs/superpowers/plans/2026-07-10-longterm-strategy-redesign.md`
- 트레이딩 원칙: `CLAUDE.md`

## 참고

- 코인원 API: https://docs.coinone.co.kr/reference
- Fear & Greed: https://alternative.me/crypto/fear-and-greed-index/
