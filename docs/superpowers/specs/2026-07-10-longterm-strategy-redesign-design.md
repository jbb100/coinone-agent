# KAIROS-Simple: 장기 역발상 매집형 전면 개편 설계

- 날짜: 2026-07-10
- 상태: 사용자 승인 완료 (목표 비중 크립토 60/KRW 40, 밴드 ±5%p, 주간 DCA)
- 배경: 기존 시스템은 (1) 추세추종형 시장 계절 필터(강세장 70%/약세장 30%)와 역발상 DCA 승수가 서로 반대 방향으로 작동하고, (2) 온체인/매크로 분석이 100% 목업 데이터인데 그 가짜 신호가 자산 배분에 ±20%까지 반영되며, (3) src/core에 30개+ 모듈이 중복 난립해 있다.

## 1. 통일 철학

**"싸질수록 사고, 비싸질수록 판다" — 장기 역발상 매집.**

세 가지 메커니즘이 모두 같은 방향으로 작동한다:

1. **고정 목표 비중 + 밴드 리밸런싱**: 가격이 오르면 크립토 비중이 목표를 초과 → 초과분 매도(익절). 가격이 내리면 비중 미달 → KRW로 매수(저가 매집). 시장 계절에 따라 목표 비중 자체를 바꾸는 로직(risk_on 70%/risk_off 30%)은 폐지한다 — 이것이 기존 시스템의 추세추종(고점 매수·저점 매도) 원인이었다.
2. **주간 DCA + 역발상 승수**: 공포에 더 사고 탐욕에 덜 산다.
3. **fail-loud 원칙**: 데이터를 못 구하면 하드코딩 값으로 거래하지 않고, 거래를 멈추고 알린다.

## 2. 핵심 파라미터

### 2.1 목표 비중
- 크립토 60% / KRW 40%
- 크립토 내부: BTC 50% / ETH 30% / XRP 10% / SOL 10%
- 리밸런싱 밴드: 크립토 총비중 기준 **±5%p** (절대), 개별 코인은 크립토 내 상대비중 ±20% (상대)
- 근거: 수수료(0.2%)+슬리피지(0.2%) 왕복 비용 대비 밴드가 충분히 넓어야 잦은 매매(churn)를 막는다. 기존 1% 임계값은 폐지.

### 2.2 주간 DCA 승수
```
buy_amount = base_amount × fg_mult × valuation_mult   (0.3 ≤ 곱 ≤ 3.0으로 클램프)
```
- **Fear & Greed 승수** (alternative.me, 실 API):
  - 0–24 (극공포): 2.0
  - 25–44 (공포): 1.5
  - 45–55 (중립): 1.0
  - 56–74 (탐욕): 0.7
  - 75–100 (극탐욕): 0.3
- **밸류에이션 승수** (BTC 현재가 / 200주 이동평균, Binance 주봉 실데이터):
  - ratio < 1.0 (200주MA 아래, 역사적 바닥권): 1.5
  - 1.0 ≤ ratio < 2.0: 1.0
  - 2.0 ≤ ratio < 3.0: 0.7
  - ratio ≥ 3.0 (사이클 과열권): 0.5
- 상한: 단일 DCA 500만원, 월간 총 DCA 한도(config), KRW 잔고의 25% 초과 불가.

### 2.3 리스크 가드 (모든 주문이 통과해야 하는 단일 관문)
- 단일 거래 최대: 1,000만원
- 일일 거래량 최대: 5,000만원
- 최소 KRW 비중: 10% (전량 몰빵 방지 — DCA·리밸런스 매수 모두 이 하한을 침범 불가)
- FOMO 가드: 24시간 +15% 이상 급등한 자산은 DCA 외 추가 매수 금지 (쿨다운 24h)
- 데이터 무결성 가드: 시세·F&G·MA 계산 실패 또는 스테일(>24h) 시 해당 사이클 거래 중단 + 알림. 하드코딩 폴백(5천만원 MA, $50k 앵커, 5% 벤치마크) 전면 제거.
- 주문 실행: 지정가 우선, 슬리피지 상한 0.5%, 재시도 3회(지수 백오프), 부분 체결 잔량 처리, 코인원 rate limit 준수. 500만원 초과 주문은 TWAP 분할.

### 2.4 스케줄
- 주간(월 09:00 KST): DCA 매수 실행
- 일간(09:00): 밴드 이탈 체크 → 이탈 시에만 리밸런싱 주문 생성
- 월간(1일): 성과 리포트 (실제 BTC 단순보유 벤치마크 대비)

## 3. 모듈 구조 (30+ → 8)

```
src/
├── data/
│   └── market_data.py        # Binance OHLCV, 코인원 시세, F&G, USD/KRW — 실 API만, fail-loud
├── strategy/
│   ├── valuation.py          # 200주MA 괴리율 + F&G → 승수 산출 (순수 함수)
│   ├── dca.py                # 주간 매수 금액/자산별 배분 계산 (순수 함수)
│   └── rebalance.py          # 목표 비중 대비 이탈 계산 → 주문 목록 생성 (순수 함수)
├── risk/
│   └── guard.py              # 2.3의 모든 한도를 단일 validate(order) 관문으로
├── execution/
│   └── executor.py           # 코인원 주문 실행: 지정가/재시도/부분체결/TWAP/rate limit
├── portfolio/
│   └── portfolio.py          # 잔고 조회, 평가액, 거래 기록(DB)
└── report/
    └── reporter.py           # 성과 지표(실제 벤치마크), Slack/이메일 알림
```

- 전략 모듈(valuation/dca/rebalance)은 **순수 함수**로: 입력(시세·잔고·설정) → 출력(주문 목록). 부수효과 없음 → 테스트·백테스트 동일 코드 재사용, look-ahead bias 원천 차단.
- 유지·재사용: `coinone_client.py`, `rate_limited_client.py`, `external_api_client.py`(폴백 상수 제거), `binance_data_provider.py`, `database_manager.py`, `alert_system.py`, TWAP 실행 로직(기존 rebalancer에서 추출).
- 엔트리포인트: `kairos1_main.py` 1개만 유지(대폭 축소). `kairos1_multi.py`, `kairos1_enhanced_multi.py` 삭제.

## 4. 삭제 목록

**완전 가짜 데이터 (즉시 삭제):**
- `src/core/onchain_stub_data.py`, `src/core/onchain_data_analyzer.py`, `src/core/macro_economic_analyzer.py`

**철학 충돌 / 중복 / 범위 축소 (삭제):**
- `market_season_filter.py` (70/30 계절 스위칭 — 200주MA 계산만 valuation.py로 이관)
- `multi_account_manager.py`, `multi_account_coordinator.py`, `multi_account_feature_manager.py`, `multi_portfolio_manager.py`, `multi_rebalancing_engine.py`, `enhanced_multi_account_cli.py`, `multi_account_cli.py`
- `tax_optimization_system.py`, `scenario_response_system.py`, `behavioral_bias_prevention.py`(FOMO 가드만 risk/guard.py로 이관)
- `risk_parity_model.py`, `adaptive_portfolio_manager.py`, `dynamic_portfolio_optimizer.py`, `portfolio_optimizer_cli.py`
- `dynamic_execution_engine.py`, `smart_execution_engine.py`(TWAP 로직만 executor.py로 이관)
- `multi_timeframe_analyzer.py`, `composite_signal_analyzer.py`(단기 TA — 장기 전략에 불필요)
- `opportunistic_buyer.py`(극공포 매수는 DCA 승수 2.0이 대체), `system_coordinator.py`, `advanced_performance_analytics.py`(핵심 지표만 reporter.py로), `tax`·`scenario`·`bias` 관련 스크립트
- 해당 모듈들의 테스트 전부

**수정 (유지하되 가짜 제거):**
- `performance_tracker.py`: 벤치마크 5% 하드코딩 → 실제 BTC 기간 수익률
- `market_data_provider.py`: $50k/5천만원 폴백 → 예외 발생(fail-loud)

## 5. 검증 계획

- **TDD**: 전략 순수 함수(승수 경계값, 밴드 이탈 판정, 주문 수량 계산), 리스크 가드(각 한도 위반 케이스), 실행(재시도·부분체결 모킹) 순으로 Red→Green→Refactor.
- **백테스트**: 순수 함수 전략을 그대로 사용. 수수료 0.2% + 슬리피지 0.2% 왕복 반영, 2018–2025 구간(상승·하락·횡보 포함), 벤치마크 = BTC 단순보유 및 60/40 무리밸런싱. 과적합 방지: 튜닝 파라미터 5개 이하(목표비중, 밴드, F&G 승수표, 밸류 승수표, DCA 기본금액).
- **성공 기준**: 기존 2786개 테스트 중 유지 모듈 테스트 전부 통과, 신규 모듈 커버리지 90%+, 백테스트에서 하락장 구간 매수·상승장 구간 매도 비율로 역발상 동작 확인.

## 6. 비범위 (Non-goals)

- 멀티 계좌, 세금 최적화, 온체인/매크로 신호, 단기 트레이딩 신호, 레버리지·마진, 신규 코인 자동 상장 대응.
