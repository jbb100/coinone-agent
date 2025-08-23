# KAIROS-1 시스템 아키텍처 설계 문서

## 1. 시스템 개요
KAIROS-1은 코인원 거래소 맞춤형 자동 투자 시스템으로, 장기 투자와 리스크 관리를 위한 다양한 모듈들이 상호작용하는 복잡한 시스템입니다.

## 2. 모듈 구성 및 상호작용

### 2.1 핵심 모듈 (Core Modules)

#### 데이터 계층
- **DatabaseManager** (`src.utils.database_manager`)
  - 모든 모듈에서 데이터 저장/조회를 위해 사용
  - 시장 분석 결과, 리밸런싱 기록, 거래 내역 저장
  - 주요 연결: `PerformanceTracker`, `DynamicExecutionEngine`, `OpportunisticBuyer`

- **ConfigLoader** (`src.utils.config_loader`)
  - 시스템 초기화 시 설정 파일 로드
  - 모든 모듈의 설정 정보 제공
  - 필수 설정 값 검증

#### 거래 계층
- **CoinoneClient** (`src.trading.coinone_client`)
  - 코인원 거래소 API와 직접 통신
  - `rate_limited_client`로 래핑되어 속도 제한 적용
  - 주요 연결: `OrderManager`, `DynamicExecutionEngine`, `OpportunisticBuyer`, `Rebalancer`

- **OrderManager** (`src.trading.order_manager`)
  - 주문 생성 및 관리
  - `CoinoneClient`를 통해 실제 주문 실행
  - 주요 연결: `Rebalancer`, `OpportunisticBuyer`

- **MultiAccountManager** (`src.core.multi_account_manager`)
  - 멀티 계정 관리 및 초기화
  - 각 계정별 `CoinoneClient` 인스턴스 관리
  - 메인 시스템에서 primary 계정 선택

#### 전략 계층
- **MarketSeasonFilter** (`src.core.market_season_filter`)
  - 시장 계절(상승장/하락장) 판단
  - 주간 분석 시 사용
  - 리밸런싱 트리거 제공

- **PortfolioManager** (`src.core.portfolio_manager`)
  - 자산 배분 비율 관리
  - BTC, ETH, XRP, SOL 가중치 설정
  - 주요 연결: `Rebalancer`, `AdaptivePortfolioManager`

- **Rebalancer** (`src.core.rebalancer`)
  - 포트폴리오 리밸런싱 계획 수립 및 실행
  - 의존성: `CoinoneClient`, `DatabaseManager`, `PortfolioManager`, `OrderManager`
  - 분기별 리밸런싱 및 TWAP 실행

- **OpportunisticBuyer** (`src.core.opportunistic_buyer`)
  - 매수 기회 탐지 및 실행
  - 의존성: `CoinoneClient`, `DatabaseManager`, `OrderManager`
  - RSI, 볼린저 밴드 기반 기회 포착

#### 실행 엔진
- **DynamicExecutionEngine** (`src.core.dynamic_execution_engine`)
  - TWAP 주문 실행 및 관리
  - 의존성: `CoinoneClient`, `DatabaseManager`, `AlertSystem`
  - 대규모 주문을 시간 분할 실행

#### 리스크 및 모니터링
- **RiskManager** (`src.risk.risk_manager`)
  - 포트폴리오 리스크 점수 계산
  - 리스크 한도 관리
  - 시스템 상태 체크 시 사용

- **AlertSystem** (`src.monitoring.alert_system`)
  - 모든 중요 이벤트 알림 발송
  - 주요 연결: `DynamicExecutionEngine`, 주간 분석, 리밸런싱, 매수 기회
  - Slack/Email 알림 지원

- **PerformanceTracker** (`src.monitoring.performance_tracker`)
  - 성과 측정 및 보고서 생성
  - 의존성: `DatabaseManager`
  - 수익률, 샤프 비율 등 메트릭 계산

### 2.2 고급 시스템 모듈 (Advanced Modules)

#### 분석 모듈
- **MultiTimeframeAnalyzer** (`src.core.multi_timeframe_analyzer`)
  - 다양한 시간대 기술적 분석
  - 초기화되지만 메인 플로우에서 직접 사용 안 함
  - CLI 명령어로만 실행 (`--multi-timeframe-analysis`)

- **MacroEconomicAnalyzer** (`src.core.macro_economic_analyzer`)
  - 매크로 경제 지표 분석
  - API 키 필요 (선택적)
  - CLI 명령어로만 실행 (`--macro-analysis`)

- **OnchainDataAnalyzer** (`src.core.onchain_data_analyzer`)
  - 온체인 데이터 분석
  - API 키 필요 (선택적)
  - CLI 명령어로만 실행 (`--onchain-analysis`)

#### 포트폴리오 최적화
- **AdaptivePortfolioManager** (`src.core.adaptive_portfolio_manager`)
  - 기본 `PortfolioManager`를 감싸는 래퍼
  - 시장 상황에 따른 동적 자산 배분
  - 현재 메인 플로우에서 미사용

- **RiskParityModel** (`src.core.risk_parity_model`)
  - 리스크 패리티 모델
  - 초기화되지만 실제 사용 안 함

#### 전략 모듈
- **DCAPlus** (`src.core.dca_plus_strategy`)
  - 고급 DCA(Dollar Cost Averaging) 전략
  - 초기화되지만 실제 사용 안 함
  - CLI 명령어로만 확인 (`--dca-schedule`)

- **TaxOptimizationSystem** (`src.core.tax_optimization_system`)
  - 세금 최적화 시스템
  - 초기화되지만 실제 사용 안 함
  - CLI 명령어로만 실행 (`--tax-report`)

#### 행동 분석
- **BehavioralBiasPrevention** (`src.core.behavioral_bias_prevention`)
  - 심리적 편향 방지 시스템
  - 초기화되지만 실제 사용 안 함
  - CLI 명령어로만 실행 (`--bias-check`)

- **ScenarioResponseSystem** (`src.core.scenario_response_system`)
  - 시나리오 대응 시스템
  - 초기화되지만 실제 사용 안 함
  - CLI 명령어로만 실행 (`--scenario-check`)

#### 성과 분석
- **AdvancedPerformanceAnalytics** (`src.core.advanced_performance_analytics`)
  - 고급 성과 분석
  - 초기화되지만 실제 사용 안 함
  - CLI 명령어로만 실행 (`--advanced-performance-report`)

### 2.3 유틸리티 모듈
- **MarketDataProvider** (`src.utils.market_data_provider`)
  - Import만 되고 실제 사용 안 함
  - **⚠️ 연결 고리 없음**

- **system_integration_helper** (`src.core.system_integration_helper`)
  - `get_system_status` 함수만 import
  - 시스템 상태 조회 시 사용

## 3. 주요 작업 플로우

### 3.1 주간 분석 플로우
```
1. run_weekly_analysis()
   ├── MarketSeasonFilter.get_current_season()
   ├── DatabaseManager.save_market_analysis()
   ├── AlertSystem.send_weekly_analysis_report()
   └── [트리거] 시장 계절 변화 시 → run_quarterly_rebalance()
```

### 3.2 리밸런싱 플로우
```
1. run_quarterly_rebalance()
   ├── Rebalancer.rebalance()
   │   ├── CoinoneClient.get_balances()
   │   ├── PortfolioManager.get_target_allocation()
   │   └── OrderManager.create_orders()
   └── DatabaseManager.save_rebalance_result()

2. run_quarterly_rebalance_twap()
   ├── Rebalancer.plan_rebalance()
   └── DynamicExecutionEngine.start_twap_execution()
       └── [비동기] process_pending_twap_orders()
```

### 3.3 매수 기회 탐지 플로우
```
1. check_opportunistic_buying()
   ├── OpportunisticBuyer.identify_opportunities()
   │   ├── 기술적 지표 분석 (RSI, 볼린저 밴드)
   │   └── 기회 레벨 판단
   └── OpportunisticBuyer.execute_opportunistic_buys()
       └── OrderManager.create_buy_order()
```

## 4. 연결 고리가 없는 모듈들

### 완전히 미사용 모듈
- **MarketDataProvider**: Import만 되고 어디서도 사용되지 않음

### CLI 전용 모듈 (메인 플로우와 분리)
- **MultiTimeframeAnalyzer**: CLI 명령어로만 실행
- **AdaptivePortfolioManager**: 초기화만 되고 사용 안 함
- **DCAPlus**: 초기화만 되고 사용 안 함
- **RiskParityModel**: 초기화만 되고 사용 안 함
- **TaxOptimizationSystem**: 초기화만 되고 사용 안 함
- **MacroEconomicAnalyzer**: CLI 명령어로만 실행
- **OnchainDataAnalyzer**: CLI 명령어로만 실행
- **ScenarioResponseSystem**: CLI 명령어로만 실행
- **BehavioralBiasPrevention**: CLI 명령어로만 실행
- **AdvancedPerformanceAnalytics**: CLI 명령어로만 실행

## 5. 개선 제안

### 5.1 미사용 모듈 정리
- `MarketDataProvider`는 사용하지 않으므로 import 제거 권장
- 고급 시스템 모듈들은 선택적 초기화로 변경 (필요할 때만 초기화)

### 5.2 모듈 통합 제안
- 고급 분석 모듈들을 주간 분석이나 리밸런싱 플로우에 통합
- `AdaptivePortfolioManager`를 실제 포트폴리오 관리에 활용
- `DCAPlus` 전략을 정기 매수 로직에 통합

### 5.3 아키텍처 개선
- 고급 모듈들을 플러그인 형태로 재구성
- 설정 파일에서 사용할 모듈 선택 가능하도록 구조 변경
- 의존성 주입 패턴 활용하여 모듈 간 결합도 감소

## 6. 시스템 다이어그램

```
┌─────────────────────────────────────────────────────────────┐
│                        KairosSystem                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐ │
│  │ConfigLoader  │────│DatabaseManager│────│AlertSystem   │ │
│  └──────────────┘    └──────────────┘    └──────────────┘ │
│           │                  │                    │         │
│  ┌────────▼─────────────────▼────────────────────▼──────┐ │
│  │                  Core Components                      │ │
│  │  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐ │ │
│  │  │CoinoneClient├──│OrderManager  │  │RiskManager  │ │ │
│  │  └──────┬──────┘  └──────┬───────┘  └─────────────┘ │ │
│  │         │                 │                          │ │
│  │  ┌──────▼──────┐  ┌──────▼───────┐  ┌────────────┐ │ │
│  │  │Rebalancer   │  │Portfolio     │  │Market      │ │ │
│  │  │             │  │Manager       │  │SeasonFilter│ │ │
│  │  └─────────────┘  └──────────────┘  └────────────┘ │ │
│  │                                                      │ │
│  │  ┌─────────────┐  ┌──────────────┐                 │ │
│  │  │Opportunistic│  │Dynamic       │                 │ │
│  │  │Buyer        │  │ExecutionEngine│                 │ │
│  │  └─────────────┘  └──────────────┘                 │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐ │
│  │            Advanced Components (CLI Only)             │ │
│  │  ┌─────────────┐  ┌──────────────┐  ┌────────────┐ │ │
│  │  │MultiTimeframe│  │MacroEconomic│  │OnchainData │ │ │
│  │  │Analyzer      │  │Analyzer      │  │Analyzer    │ │ │
│  │  └─────────────┘  └──────────────┘  └────────────┘ │ │
│  │                                                      │ │
│  │  [기타 고급 모듈들 - 초기화만 되고 미사용]          │ │
│  └──────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## 7. 결론
KAIROS-1 시스템은 핵심 모듈들은 잘 연결되어 있으나, 고급 시스템 모듈들은 대부분 초기화만 되고 실제로 사용되지 않고 있습니다. 이들을 실제 워크플로우에 통합하거나, 선택적 초기화로 변경하는 것을 권장합니다.