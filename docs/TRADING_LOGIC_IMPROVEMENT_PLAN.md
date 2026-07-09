# 거래 로직 개선 계획 (2026-07)

> 근거 문서: [`TRADING_LOGIC_REVIEW.md`](./TRADING_LOGIC_REVIEW.md)
> 목표: ① 데이터 장애가 매수 신호로 변환되는 fail-unsafe 제거, ② 계층 간 전략 충돌 해소,
> ③ "하락장 매집 / 상승장 분배" 철학으로 최상위 배분 로직 전환.

## 대원칙: Real-Data-Only (2026-07 확정)

**실제로 갱신되는 데이터가 없는 지표는 의사결정에서 전부 제외한다. 심플하고 명확하게.**

유지하는 지표 (모두 실데이터):
- BTC 200주 이동평균 및 가격 비율 R — Binance 실가격 (24h 캐시 허용)
- RSI / 고점 대비 하락률 / 변동성 / 거래량 — 거래소 실가격·거래량에서 직접 계산
- 공포탐욕지수 — alternative.me 실제 API (24h 캐시 허용, 조회 불가 시 None → 중립 처리)

제외한 지표 (목업/추정/하드코딩이었음):
- ❌ 변동성 기반 "추정 공포탐욕지수" (OpportunisticBuyer 자체 계산) → 실제 API로 교체
- ❌ RSI 기반 "추정 공포탐욕지수" (DCAPlus) → 실제 API로 교체
- ❌ BTC 도미넌스 (하드코딩 0.6) → 축적 점수에서 제거
- ❌ 계절 배수 (12월 보너스/1월 새해 등 임의 가정) → DCA 배수에서 제거
- ❌ 온체인/매크로/멀티타임프레임/센티먼트 "신호 수집" (항상 0.0 반환) → 리밸런서에서 제거
- ❌ 모든 하드코딩 fallback 값 (MA 5천만 원, 현재가×0.9, BTC $50,000) → 판단 중단으로 교체

공통 규칙: **실데이터를 얻지 못하면 추정치를 만들지 않는다.**
지표는 None을 반환하고, 소비자는 해당 조정을 적용하지 않거나(중립) 판단 자체를 중단한다.

## 진행 상태

- ✅ **Phase 0 완료** — fail-safe 안전장치 (아래 0-1 ~ 0-4)
- ✅ **Phase 1 완료** — P1 버그 수정 + real-data-only 목업 지표 제거
- ✅ **Phase 2 완료** — 가치 앵커 국면 모델 (`market_valuation_filter.py`,
  config `strategy.regime_model: legacy|valuation` 스위치, 기본값 legacy)
- ✅ **Phase 3 완료** — `allocation_arbiter.py`(클로백 면제 + 허용 밴드),
  `opportunistic_seller.py`(4단계 익절), 매수/매도 실행 스크립트에 밴드 한도 적용
- ✅ **Phase 4 완료** — Rebalancer의 목업 메서드 4개를 `tests/rebalancer_test_double.py`
  (`SimulatedRebalancer`)로 이동, 리밸런싱 임계값 5%로 전역 단일화,
  `_expand_crypto_orders` 하드코딩 70:30 제거(설정 가중치 사용), README 갱신
- 🟡 **Phase 5 — 하네스 완성, 실데이터 실행 대기** (**valuation 모드 라이브 전환의 게이트**)
  - ✅ 백테스트 하네스 완성: `scripts/backtest_regime_models.py`
    - legacy vs valuation vs Buy&Hold vs 고정 50:50 비교 (주간, 수수료 0.2%, 5% 임계값)
    - in-sample(~2022) 격자 탐색(경계 4세트 × 히스테리시스 2종) → out-of-sample(2023~) 검증
    - Real-data-only: Binance/CoinGecko 실데이터 수집 실패 시 합성하지 않고 중단
    - 시뮬레이션 엔진은 `tests/test_backtest_harness.py`(8개)로 검증 완료
  - ⚠️ **이 원격 개발 환경의 네트워크 정책이 시장 데이터 API(Binance/CoinGecko/Yahoo)를
    차단해 실데이터 실행은 불가.** 다음 중 한 곳에서 실행할 것:
    1. 운영 머신(이미 Binance API를 사용 중이므로 접근 가능):
       `python scripts/backtest_regime_models.py`
       → 결과가 `docs/BACKTEST_REGIME_MODELS.md`로 저장됨
    2. 또는 Claude Code 웹 환경 설정에서 네트워크 정책을 완화 후 재실행 요청
  - ⬜ 백테스트 결과 검토 → 전환 결정
  - ⬜ 롤아웃: dry-run 2주 → 소액(일일 한도 5%) 2주 → `strategy.regime_model: valuation` 전환

Phase 0-1 구현 내역 요약:
- `market_season_filter`: MA 계산 불가 시 None 반환(대체 MA 금지), `determine_market_season`이
  데이터 오류 시 직전 계절 유지, NEUTRAL = 기존 비중 유지, `season_from_string` 유틸 추가
- `rebalancer`: `_get_current_market_season`이 판단 불가 시 None 반환 → 리밸런싱 중단(주문 0건),
  DB 직전 계절을 히스테리시스에 반영, **KRW 이중 환산 버그 수정**(MA가 이미 KRW인데
  USD로 간주해 재환산하던 문제), $50,000 하드코딩 제거, 목업 신호 수집 제거
- `market_data_provider`: fallback 경로 전면 삭제, 실패 시 `MarketDataUnavailableError`
- `fear_greed_provider` 신설: alternative.me 실제 API + 24h 캐시, 실패 시 None
- `dca_plus_strategy`: 월 한도를 당월 누적 집행액 기준으로 수정(`month_spent_krw`),
  공포탐욕 구간 통일(25/45/55/75), 도미넌스·계절 배수 제거, signal_strength 정규화
- `opportunistic_buyer`: 하락률을 평균 대비 → **N일 고점 대비**로 교체, 최소수량 상향 클램프
  제거(예산 초과 매수 금지), 매수 이력 DB 영속화 + 재매수 조건(72h 내 직전 매수가 대비 -3%),
  전체 예산 기준 레벨별 배분
- `tests/test_failsafe.py` 신설 (32개 테스트, 전부 통과)

Phase 2-3 구현 내역 요약:
- `market_valuation_filter.py` 신설: R = 가격/200주 MA 기준 5국면
  (DEEP_VALUE 75% / ACCUMULATION 65% / NEUTRAL 50% / DISTRIBUTION 35% / EUPHORIA 25%),
  경계 ±5% 히스테리시스, 국면 전환 시 회당 최대 10%p 단계 이동, 데이터 없으면 판단 중단
- `rebalancer.py`: `_get_target_allocation()` 단일 진입점으로 legacy/valuation 스위치,
  valuation 분석 결과를 DB에 저장해 다음 사이클 히스테리시스에 사용
- `allocation_arbiter.py` 신설: ① 최근 30일 기회적 매수분을 리밸런싱 매도에서 차감
  (클로백 면제 — "사자마자 팔리는" 왕복 매매 차단), ② 목표 비중 ±8%p 허용 밴드로
  기회적 매수/매도 한도 계산
- `opportunistic_seller.py` 신설: 30일 저점 대비 상승률 + RSI + 실제 탐욕지수 기반
  4단계 익절 (5%/10%/15%/20%), 탐욕지수·R값 실데이터 없으면 해당 레벨 미발동,
  재매도 조건(4h 간격 + 72h 내 +5% 추가 상승), 매도 이력 DB 영속화
- `scripts/execute_opportunistic_sell.py` 신설 (cron 실행용),
  `execute_opportunistic_buy.py`에 밴드 한도 적용 + 튜플 반환값 버그 수정
- config: `strategy.regime_model`, `strategy.valuation.*`, `strategy.arbiter.*` 추가
- `tests/test_valuation_filter.py`(24개), `tests/test_arbiter_and_seller.py`(20개) 신설

## 전체 로드맵

| Phase | 내용 | 성격 | 의존성 |
|---|---|---|---|
| 0 | 안전장치 (P0 버그) | 버그 수정 — 전략 변경 없음 | 없음 |
| 1 | 동작 정확성 (P1 버그) | 버그 수정 — 전략 변경 없음 | 없음 (Phase 0과 병행 가능) |
| 2 | 시장 국면 모델 전환 | 전략 변경 | Phase 0 완료 |
| 3 | 전략 조정자(Arbiter) + 익절 모듈 | 신규 기능 | Phase 2 |
| 4 | 코드 정리 및 문서 일치 | 리팩터링 | Phase 0-1 |
| 5 | 백테스트 검증 + 단계적 롤아웃 | 검증 | Phase 2-3 |

Phase 0-1은 현재 전략을 유지한 채 즉시 적용 가능하고, Phase 2-3이 본격적인 전략 전환입니다.

---

## Phase 0 — 안전장치: 장애 시 절대 매수하지 않기 (P0)

**원칙: 데이터를 신뢰할 수 없으면 "판단 불가"이지 "강세장"이 아니다. 판단 불가 시
직전 상태 유지 + 거래 중단 + 알림.**

### 0-1. Fallback 값 전면 제거

| 위치 | 현재 | 변경 |
|---|---|---|
| `rebalancer.py:901` | MA 실패 시 `현재가 × 0.9` → 강제 RISK_ON | MA 실패 시 `MarketDataError` 발생 → 리밸런싱 사이클 중단, 직전 계절 유지, `AlertSystem` 경보 |
| `market_season_filter.py:55,61,67,109` | MA 기본값 5,000만 원 하드코딩 | 계산 불가 시 `None` 반환. 호출부에서 `None`이면 `MarketSeason` 판정 스킵 |
| `market_season_filter.py:82` | 200주 데이터 부족 시 200일 MA로 조용히 대체 | 대체 금지. 데이터 부족 = 판단 불가로 처리 |
| `rebalancer.py:937,941` | BTC USD $50,000 하드코딩 | 환율 조회 실패 시 캐시(24h 이내)만 허용, 없으면 판단 불가 |
| `constants.py:53` | `MA_CALCULATION_FALLBACK_RATIO` | 상수 자체 삭제 (참조 지점 모두 제거) |

- 신규 예외 타입: `src/core/exceptions.py`에 `MarketDataUnavailableError` 추가.
- "판단 불가" 시 동작을 한 곳에 집약: `Rebalancer._get_current_market_season()`이
  `Optional[MarketSeason]`을 반환하고, `None`이면 실행 계층에서
  **거래 없음 + CRITICAL 알림**으로 통일.

### 0-2. 완충 밴드 히스테리시스 복구

- `db_manager.get_latest_market_analysis()`로 직전 계절을 읽어
  `determine_market_season(previous_season=...)`에 전달:
  - `market_season_filter.py:223` (`analyze_weekly`) — 시그니처에 `previous_season` 추가
  - `rebalancer.py:905-909` — DB 조회 결과 전달
- 밴드 내(0.95~1.05) 판정 시 **직전 계절의 배분을 그대로 유지** (NEUTRAL 강제 전환 금지).
- 직전 상태가 아예 없을 때(최초 실행)만 NEUTRAL 허용.
- `analyze_weekly` 결과를 항상 DB에 저장해 다음 사이클의 `previous_season` 소스로 사용.

### 0-3. NEUTRAL 의미 확정

- README("기존 비중 유지")와 코드(50:50 강제)의 불일치 해소.
- 결정: **NEUTRAL = 현상 유지**(리밸런싱은 자산 간 편차 교정만 수행, crypto:KRW 총비중은
  직전 값 유지). `get_allocation_weights()`가 NEUTRAL일 때 현재 비중을 입력받아 반환하도록 변경.

### 0-4. 테스트 (Phase 0 완료 조건)

- [ ] MA 데이터 소스 전면 장애 시뮬레이션 → 주문 0건 + CRITICAL 알림 발생 검증
- [ ] ratio 1.06 → 1.04 → 1.06 시퀀스에서 매매 발생 0건 (히스테리시스 검증)
- [ ] 빈 DataFrame / NaN / 200주 미만 데이터 각각에 대해 판정 스킵 검증
- [ ] 기존 `test_rebalancing_engine.py` 통과 유지

---

## Phase 1 — 동작 정확성 (P1)

### 1-1. DCA+ 월 한도 수정 (`dca_plus_strategy.py:287-298`)

- DB에 월별 DCA 집행액 누적 테이블 추가 (`db_manager`).
- `calculate_dca_amount()`에서 `이번 집행액 + 당월 누적 > max_monthly_amount`이면
  잔여 한도만큼만 집행(0 이하면 스킵).
- 테스트: 주간 3배 부스트가 4주 연속 발생해도 월 합계가 한도를 넘지 않음을 검증.

### 1-2. 기회적 매수 로직 교정 (`opportunistic_buyer.py`)

1. **하락률 기준 교체**: `현재가/N일 평균` → `현재가/N일 고점(rolling max)`.
   `BuyOpportunity` 필드명도 `drawdown_from_7d_high` 등으로 변경해 의미 명확화.
2. **레벨 임계값 재보정**: 고점 대비 기준으로 MINOR -5% / MODERATE -10% /
   MAJOR -20% / EXTREME -30% 유지 (이제 실제로 도달 가능해짐).
3. **수량 상향 클램프 제거** (`:424`): `max(min_limit, ...)` 삭제.
   최소 수량 미달이면 **매수 스킵** (예산 초과 매수 금지).
4. **`recent_buys` 영속화**: DB 테이블로 이전, 기동 시 로드. 추가로 레벨별 재매수
   조건 도입 — 같은 레벨에서는 4시간 간격이어도 **직전 매수가 대비 추가 -3% 하락 시에만**
   재매수 (떨어지는 칼날에 대한 예산 소진 방지).
5. **레벨별 예산 분할**: 전체 가용 현금을 레벨별로 사전 배정
   (MINOR 10% / MODERATE 20% / MAJOR 30% / EXTREME 40%)해 초반 소진 방지.

### 1-3. 공포탐욕지수 단일화

- 신규 `src/utils/fear_greed_provider.py`:
  - 1순위: alternative.me API (24h 캐시)
  - 2순위: 캐시 (7일 이내)
  - 3순위: **`None` 반환** (가짜 수치 생성 금지)
- `OpportunisticBuyer.get_fear_greed_index()`, `DCAPlus`의 RSI 추정 제거 → provider 주입.
- 지수 `None`일 때: 공포탐욕 배수 = 1.0 (중립)로 처리, 알림 1회.
- 구간 기준 통일: EXTREME_FEAR ≤25 / FEAR ≤45 / NEUTRAL ≤55 / GREED ≤75 / EXTREME_GREED >75
  (enum 주석과 일치, `calculate_dca_signal`의 ≤40도 이 기준으로 수정).

### 1-4. 테스트 (Phase 1 완료 조건)

- [ ] 월 한도 초과 시나리오 (부스트 연속 발생)
- [ ] 지속 하락장 30일 시뮬레이션에서 현금 소진 속도 검증 (레벨별 예산 준수)
- [ ] API 장애 시 공포탐욕 배수 1.0 폴백 검증
- [ ] 프로세스 재시작 후 중복매수 방지 유지 검증

---

## Phase 2 — 시장 국면 모델 전환: "하락장 매집 / 상승장 분배"

리뷰 권고안 A 채택. 200주 MA를 "추세 이탈 매도선"에서 **"가치 앵커"**로 전환합니다.

### 2-1. 신규 국면 정의 (`MarketSeasonFilter` → `MarketValuationFilter`로 개편)

판정 지표: `R = BTC 현재가 / 200주 MA` (주 1회 산출, DB 저장)

| 국면 | 조건 (R) | 목표 crypto 비중 | 의도 |
|---|---|---|---|
| DEEP_VALUE | R < 1.0 | **75%** | 사이클 바닥권 — 최대 매집 |
| ACCUMULATION | 1.0 ≤ R < 1.4 | 65% | 저평가 — 적극 매집 |
| NEUTRAL | 1.4 ≤ R < 2.0 | 50% | 중립 |
| DISTRIBUTION | 2.0 ≤ R < 2.8 | 35% | 고평가 — 단계적 분배 |
| EUPHORIA | R ≥ 2.8 | **25%** | 과열 — 최대 분배 |

- 경계마다 **±5% 히스테리시스** 적용 (경계 재돌파 시에만 국면 전환, Phase 0-2의
  previous_season 메커니즘 재사용). 국면 전환 시에도 한 번에 목표로 점프하지 않고
  **월 최대 10%p씩 단계 이동** (급격한 일괄 매매 방지).
- 임계값(1.0/1.4/2.0/2.8)과 국면별 비중은 `config.yaml`로 외부화 —
  Phase 5 백테스트에서 격자 탐색으로 최종 확정. 위 표는 초기값.
- 근거: R<1.0은 역사적으로 2015·2018-19·2020.3·2022 바닥권,
  R>2.8은 2017.12·2021 정점권. `DCAPlus._calculate_accumulation_score()`의
  기존 논리(200주 MA -25% = 최강 매집)와 방향 일치.

### 2-2. 하위 전략 신호 통일

- DCA+ 배수, 기회적 매수 예산, (신규) 기회적 매도 강도가 **모두 같은 국면 값**을 입력받도록
  `MarketRegimeService` (신규, `src/core/market_regime_service.py`) 신설:
  - 200주 MA (실데이터 + 캐시), R값, 국면, 공포탐욕지수(1-3 provider), 주간 RSI를
    한 곳에서 산출·캐시·DB 저장.
  - `Rebalancer`, `DCAPlus`, `OpportunisticBuyer/Seller`는 이 서비스만 참조.
  - 기존 각 모듈의 자체 RSI/변동성/추정 지수 계산 제거.

### 2-3. 마이그레이션

- 기존 `MarketSeason(RISK_ON/RISK_OFF/NEUTRAL)` enum은 유지하되 deprecated 처리,
  DB 스키마는 국면 문자열 컬럼 추가로 하위 호환.
- config에 `strategy.regime_model: legacy | valuation` 스위치를 두어
  롤아웃 중 즉시 롤백 가능하게 함.

### 2-4. 테스트 (Phase 2 완료 조건)

- [ ] R값 구간별 국면 판정 + 히스테리시스 단위 테스트
- [ ] 국면 전환 시 월 10%p 단계 이동 검증
- [ ] legacy/valuation 스위치 전환 시 양쪽 모두 정상 동작

---

## Phase 3 — 전략 조정자(Arbiter) + 기회적 매도 모듈

### 3-1. AllocationArbiter (신규, `src/core/allocation_arbiter.py`)

계층 간 반대 매매를 구조적으로 차단하는 단일 관문:

- 국면이 **허용 밴드**를 정의: 목표 비중 ± 8%p (예: ACCUMULATION 65% → 57~73%).
- 모든 매수/매도 주문(리밸런싱·DCA·기회적 매수/매도)은 실행 전 arbiter를 통과:
  - 주문 실행 후 예상 crypto 비중이 밴드를 벗어나면 **초과분 축소 또는 거부**.
- **클로백 면제 태그**: 기회적 매수분은 매수 시점부터 30일간 리밸런싱 매도 대상에서 제외
  (DB에 lot 단위 기록, `tax_optimization_system`의 lot 관리와 연동).
  → "급락에 산 물량을 다음 리밸런싱이 도로 파는" 문제의 직접 해결.
- 리밸런싱 트리거도 arbiter 기준으로 통일: 비중이 밴드를 벗어났을 때만 실행
  (분기 스케줄 + 밴드 이탈의 hybrid).

### 3-2. OpportunisticSeller (신규, `src/core/opportunistic_seller.py`)

`OpportunisticBuyer`와 대칭인 단계적 익절 모듈:

| 레벨 | 조건 (그리고 조건) | 매도 비율 (crypto 보유분 대비) |
|---|---|---|
| MINOR | 30일 저점 대비 +25% AND RSI > 70 | 5% |
| MODERATE | +40% AND RSI > 75 | 10% |
| MAJOR | +60% AND 탐욕지수 > 75 | 15% |
| EXTREME | R ≥ 2.8 AND 탐욕지수 > 85 | 20% |

- 매도 간격/중복 방지: Buyer와 동일 메커니즘 (DB 영속화, 레벨별 재매도 조건:
  직전 매도가 대비 추가 +5% 상승 시에만).
- 매도 대상 lot 선정은 `tax_optimization_system`에 위임 (보유기간·세율 고려).
- 매도 대금은 KRW로 보전 → DEEP_VALUE/ACCUMULATION 국면에서 Buyer의 탄약이 됨
  (사이클 순환 구조 완성).
- arbiter 밴드 하한을 뚫는 매도는 자동 축소.

### 3-3. 심리 편향 방지 시스템과의 정합

- `BehavioralBiasPrevention`의 공황매도 차단이 **시스템의 계획된 매도**(리밸런싱·익절)를
  차단하지 않도록 주문에 `origin: systematic | manual` 태그 추가. 편향 감지는 manual만 대상.

### 3-4. 테스트 (Phase 3 완료 조건)

- [ ] 약세장 시나리오: 기회적 매수 → 직후 리밸런싱에서 해당 물량 매도 0건 (클로백 면제)
- [ ] 밴드 초과 주문의 자동 축소/거부
- [ ] 2021년형 상승 시퀀스 리플레이에서 단계적 익절 발생 및 KRW 적립 검증
- [ ] systematic 매도가 편향 차단에 걸리지 않음

---

## Phase 4 — 코드 정리

1. **`Rebalancer`의 mock 메서드 제거** (`full_rebalancing_cycle`, `run_rebalancing_cycle`,
   `generate_rebalancing_plan`, `analyze_portfolio`의 테스트 기본값 등 360-471행 일대):
   테스트 호환 코드는 `tests/`의 fixture/fake 클래스로 이동. 프로덕션 경로에서
   "아무것도 안 하고 success 반환" 제거.
2. **임계값 단일화**: `REBALANCE_THRESHOLD`(1%) vs 각처 5% → `constants.py` 한 곳으로 통일,
   매직넘버(`rebalancer.py`의 0.05, 0.01 등) 제거.
3. **`_expand_crypto_orders` 하드코딩 제거** (`portfolio_manager.py:276-285`):
   core/satellite 70:30을 `AssetAllocation` 가중치에서 유도.
4. **`calculate_dca_signal`의 signal_strength 스케일 수정** (`dca_plus_strategy.py:195-199`):
   각 성분을 0-1로 정규화 후 가중합.
5. README를 새 전략(가치 기반 국면 모델)에 맞게 갱신, 구현 안 된 홍보 문구
   ("공포탐욕 지수 연동" 등) 제거 또는 실제 구현과 일치시킴.

---

## Phase 5 — 검증 및 롤아웃

### 5-1. 백테스트

- 기간: 2017-01 ~ 2026-06 (상승 사이클 2회 + 하락 사이클 2회 포함), 주간 봉.
- 비교군:
  1. legacy (현행 추세추종 + 버그 수정만)
  2. valuation 모델 (Phase 2-3 전체)
  3. 단순 DCA (벤치마크)
  4. Buy & Hold 50:50 (벤치마크)
- 지표: CAGR, MDD, Sharpe, Calmar, **회전율·수수료 차감 후 수익률**, 세후 수익률(22%).
- 국면 임계값(1.0/1.4/2.0/2.8)과 비중은 2017-2022 구간에서 격자 탐색 후
  **2023-2026 out-of-sample로 검증** (과최적화 방지).
- 기존 `backtesting_engine`의 mock 의존 제거가 선행 조건.

### 5-2. 장애 주입 테스트 (CI 편입)

- 시세 API 전면 장애 / 200주 MA 소스 장애 / 공포탐욕 API 장애 / DB 손상 각각에 대해
  "주문 0건 + 알림"을 검증하는 테스트를 `tests/test_failsafe.py`로 추가, CI 필수 통과.

### 5-3. 단계적 롤아웃

1. **dry-run 2주**: 실주문 없이 판단·주문 계획만 로그/알림 (기존 `dry_run` 경로 활용).
2. **소액 라이브 2주**: arbiter에 일일 총 거래 한도(예: 포트폴리오의 5%) 설정.
3. **전체 전환**: `regime_model: valuation`으로 스위치. 문제 시 config 한 줄로 legacy 롤백.

---

## 실행 순서 요약

```
Phase 0 (안전장치) ──┬── Phase 1 (P1 버그) ── Phase 4 (정리)
                     └── Phase 2 (국면 모델) ── Phase 3 (Arbiter/Seller) ── Phase 5 (검증/롤아웃)
```

- Phase 0은 다른 모든 것에 우선하며 단독 배포 가치가 있음 (현행 전략 그대로도 안전해짐).
- Phase 2-3이 실질적 전략 전환이며, Phase 5의 out-of-sample 백테스트 통과를
  라이브 전환의 게이트로 삼음.
