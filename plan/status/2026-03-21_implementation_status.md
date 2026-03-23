# MarketScope AI — 구현 현황 (2026-03-21 최종 업데이트)

> 이 문서는 AI Agent가 현재 프로젝트 상태를 빠르게 파악할 수 있도록 작성됨
> **마지막 업데이트**: 2026-03-21 — Phase 5 기능 테스트 & 버그 수정 완료 후

---

## 1. 프로젝트 개요

- **목적**: 상권 분석 AI Agent Swarm (서울 상권 기반 Phase 1 MVP)
- **기술 스택**: FastAPI + LangGraph + LiteLLM + Pydantic + SSE
- **코드 위치**: `/root/Catchment-Area-Analysis/marketscope/`
- **설계서 위치**: `/root/Catchment-Area-Analysis/document/specs/` (21개 파일)
- **초기 계획서**: `/root/Catchment-Area-Analysis/document/`
- **Phase 계획**: `/root/Catchment-Area-Analysis/plan/phase/` (phase 1~3)
- **세부 계획**: `/root/Catchment-Area-Analysis/plan/specific_plan/` (phase4 체크리스트)
- **데이터 계획**: `/root/Catchment-Area-Analysis/plan/data/`

---

## 2. 파일 구조 및 구현 상태

### 실구현 완료 (✅)

```
marketscope/
├── pyproject.toml                          # 의존성 정의
├── .env                                    # 개발 환경 설정 (API 키 포함)
├── .env.example                            # 환경변수 템플릿
├── docker-compose.yml                      # 메인 Docker Compose (11 서비스)
├── docker-compose.monitoring.yml           # 모니터링 스택 (Prometheus+Grafana+Loki)
└── app/
    ├── main.py                             # FastAPI 앱 (CORS, 라우터, lifespan)
    ├── config.py                           # Pydantic Settings (240줄, 프로덕션 검증 포함)
    │                                       #   - mcp_servers: 9개 서버 URL dict 등록
    ├── constants.py                        # Enum 정의 (AnalysisMode, ConfidenceLevel 등)
    ├── exceptions.py                       # 8개 예외 클래스 (DataCollectionError 포함)
    ├── logging_config.py                   # 구조화된 로깅 (JSON 포맷, structlog)
    │
    ├── agents/                             # 에이전트 레이어 ✅ (15개 에이전트)
    │   ├── base.py                         # BaseAgent[T] 추상 클래스 (408줄)
    │   │                                   #   - LLM Provider 주입 (litellm 직접 의존 제거)
    │   │                                   #   - call_llm(): 재시도 + 구조화 출력 파싱
    │   │                                   #   - call_tool(): MCP 도구 호출
    │   │                                   #   - call_tools_parallel(): 동시 도구 실행
    │   │                                   #   - run(): LangGraph 노드 래퍼 (Pydantic→dict 변환)
    │   ├── commander.py                    # CommanderAgent (357줄)
    │   │                                   #   - run_planning(): 분석 계획 수립
    │   │                                   #   - run_judgment(): 최종 종합 판단
    │   ├── population.py                   # PopulationAgent (133줄) — 유동/주민/직장인구
    │   ├── competition.py                  # CompetitionAgent (126줄) — 경쟁/포화도
    │   ├── revenue.py                      # RevenueAgent (130줄) — 매출 추정
    │   ├── location.py                     # LocationAgent (137줄) — 입지/교통/앵커시설
    │   ├── trend.py                        # TrendAgent (119줄) — 시장 트렌드/검색량
    │   ├── real_estate.py                  # RealEstateAgent (124줄) — 임대료/권리금/공실
    │   ├── regulatory.py                   # RegulatoryAgent (119줄) — 인허가/용도지역
    │   ├── financial.py                    # FinancialAgent (127줄) — 투자비용/수익성
    │   ├── risk.py                         # RiskAgent (131줄) — 리스크/완화전략
    │   ├── narrative.py                    # NarrativeAgent (90줄) — 리포트 텍스트 생성
    │   ├── visualization.py               # VisualizationAgent (107줄) — 차트/지도 설정
    │   └── debate/                         # 토론 시스템 ✅
    │       ├── advocate.py                 # AdvocateAgent — 찬성 논거
    │       ├── critic.py                   # CriticAgent — 비판 논거
    │       ├── judge.py                    # JudgeAgent — 판정
    │       └── orchestrator.py             # DebateOrchestrator — 토론 진행
    │
    ├── llm/                                # LLM 추상화 레이어 ✅
    │   ├── provider.py                     # LLMProvider Protocol + LLMResponse 데이터클래스
    │   └── litellm_provider.py             # LiteLLMProvider 구현체 (Claude/Gemini/GPT 지원)
    │
    ├── graph/                              # LangGraph 오케스트레이션 ✅ (20개 노드)
    │   ├── workflow.py                     # StateGraph DAG (병렬 fan-out/fan-in 패턴)
    │   │                                   #   - 엔트리포인트: user_input → commander_plan
    │   │                                   #   - Group 1: population + competition 병렬
    │   │                                   #   - Group 2: revenue + location 병렬
    │   │                                   #   - Group 3: trend + real_estate + regulatory 병렬
    │   │                                   #   - financial → risk → debate_check
    │   │                                   #   - debate_check → conditional(debate|judgment)
    │   │                                   #   - narrative → visualization → report_assembly
    │   ├── nodes.py                        # 20개 노드 함수 + 에이전트 팩토리
    │   │                                   #   - user_input_node: 입력 파싱/검증
    │   │                                   #   - debate_check_node: 토론 트리거 4조건 평가
    │   │                                   #   - @trace_node 데코레이터 적용
    │   ├── edges.py                        # 조건부 엣지 (분석모드, 리포트 스킵, 비교모드)
    │   │                                   #   - route_after_debate_check(): debate_decision 기반 라우팅
    │   └── builder.py                      # 그래프 빌더
    │
    ├── models/                             # 데이터 모델 ✅
    │   ├── state.py                        # MarketScopeState TypedDict (50+ 필드)
    │   │                                   #   - debate_decision: "trigger" | "skip"
    │   │                                   #   - debate_trigger_reasons: list[str]
    │   ├── agent_outputs.py                # 에이전트 출력 Pydantic 모델
    │   ├── common.py                       # 공통 타입 (TimeSlot, AgeDistribution 등)
    │   ├── debate.py                       # DebateArgument, DebateRound, DebateResult
    │   └── report.py                       # FinalReport 모델
    │
    ├── api/                                # REST API ✅
    │   ├── deps.py                         # FastAPI 의존성
    │   └── routes/
    │       ├── health.py                   # GET /health
    │       └── analysis.py                 # POST /, GET /{id}, GET /{id}/stream (SSE)
    │                                       #   - TTL 기반 자동 만료 (1시간)
    │                                       #   - asyncio.Queue 기반 SSE (레이스 컨디션 해결)
    │                                       #   - 15초 heartbeat keepalive
    │
    ├── services/                           # 서비스 레이어 ✅
    │   └── analysis_service.py             # LangGraph 워크플로우 실행 래퍼
    │
    └── tools/                              # MCP 도구 클라이언트 ✅
        ├── mcp_client.py                   # MCPClient (191줄)
        │                                   #   - async context manager 지원
        │                                   #   - httpx.Limits 커넥션 풀 (max 10)
        │                                   #   - 3회 재시도 + 지수 백오프 (502/503/504)
        └── registry.py                     # ToolRegistry (에이전트→도구 매핑)
```

### MCP 서버 (✅ 9종 구현)

```
    ├── mcp_servers/                        # MCP 서버 ✅ 9종
    │   ├── public_data/                    # 공공데이터 MCP (port 5100) — 8 도구 + 3 리소스
    │   │   ├── server.py                   # FastAPI MCP 서버 (/tools/call, /resources/read)
    │   │   ├── tools.py                    # get_floating_population, get_estimated_revenue,
    │   │   │                               #   get_store_list, get_store_count_change,
    │   │   │                               #   get_resident_population, get_worker_population,
    │   │   │                               #   get_seoul_living_population, get_card_sales
    │   │   └── resources.py               # industry-codes, district-codes, dong-codes
    │   │
    │   ├── maps/                           # 카카오 지도 MCP (port 5101) — 7 도구
    │   │   ├── server.py, tools.py         # geocode, reverse_geocode, search_nearby,
    │   │   │                               #   search_keyword, get_walking_route,
    │   │   │                               #   get_transit_nearby, get_category_pois
    │   │   └── kakao_client.py             # httpx 카카오 API 클라이언트
    │   │
    │   ├── real_estate/                    # 부동산 MCP (port 5102) — 4 도구
    │   │   └── server.py, tools.py         # get_rent_info, get_transaction_price,
    │   │                                   #   get_vacancy_rate, get_premium_estimate
    │   │                                   #   ⚠️ 일부 폴백 데이터 반환 (API 연동 미완)
    │   │
    │   ├── news/                           # 뉴스/SNS MCP (port 5103) — 3 도구
    │   │   └── server.py, tools.py         # search_blog, search_news, get_naver_datalab
    │   │                                   #   ⚠️ 네이버 자격증명 필요
    │   │
    │   ├── regulatory/                     # 규제/인허가 MCP (port 5104) — 3 도구
    │   │   └── server.py, tools.py         # get_permits, get_zoning, get_business_requirements
    │   │                                   #   ⚠️ 내부 하드코딩 DB (API 연동 대기)
    │   │
    │   ├── finance/                        # 금융/대출 MCP (port 5105) — 6 도구 ✅ Phase 4 신규
    │   │   ├── server.py                   # FastAPI 앱, FinanceAPIClient lifecycle
    │   │   ├── tools.py                    # search_startup_loans, search_government_subsidies,
    │   │   │                               #   calculate_loan_repayment, get_franchise_disclosure,
    │   │   │                               #   get_minimum_wage, get_insurance_rates
    │   │   ├── api_client.py               # 기업마당/K-Startup/프랜차이즈 API
    │   │   └── schemas.py                  # LoanProduct, Subsidy, RepaymentSchedule 등
    │   │
    │   ├── database/                       # PostGIS 쿼리 MCP (port 5106) — 5 도구 ✅ Phase 4 신규
    │   │   ├── server.py                   # FastAPI 앱, asyncpg pool lifecycle
    │   │   ├── tools.py                    # query_nearby_stores (ST_DWithin),
    │   │   │                               #   query_population_grid, query_revenue_by_area,
    │   │   │                               #   query_commercial_district, execute_spatial_query
    │   │   │                               #   ⚠️ SELECT-only 보안 제한 (INSERT/UPDATE/DELETE 차단)
    │   │   ├── db_client.py               # asyncpg 커넥션풀 (min=2, max=10)
    │   │   └── schemas.py                  # NearbyStore, PopulationGrid 등
    │   │
    │   ├── google_maps/                    # Google Maps MCP (port 5107) — 5 도구 ✅ Phase 4 신규
    │   │   ├── server.py                   # FastAPI 앱, GoogleMapsClient lifecycle
    │   │   ├── tools.py                    # google_geocode, google_reverse_geocode,
    │   │   │                               #   google_nearby_search, google_place_details,
    │   │   │                               #   google_directions
    │   │   ├── api_client.py               # Google Maps Platform API (geocode/places/directions)
    │   │   └── schemas.py                  # GeocodingResult, NearbyPlace 등
    │   │
    │   └── naver_maps/                     # 네이버 지도 MCP (port 5108) — 5 도구 ✅ Phase 4 신규
    │       ├── server.py                   # FastAPI 앱, NaverMapsClient lifecycle
    │       ├── tools.py                    # naver_geocode, naver_reverse_geocode,
    │       │                               #   naver_local_search, naver_directions,
    │       │                               #   naver_static_map
    │       ├── api_client.py               # NCP 헤더 + Search 헤더 이중 인증
    │       └── schemas.py                  # NaverGeoResult, NaverLocalPlace 등
```

### D0~D5 데이터 파이프라인 (✅ 모두 완료)

```
    ├── db/                                 # 데이터베이스 ✅ 완료
    │   ├── models.py                       # 10개 ORM 모델 (PostGIS 지원)
    │   │                                   #   districts, population_stats, revenue_stats,
    │   │                                   #   stores, transit_stats, code_mappings,
    │   │                                   #   unit_prices, startup_costs, analysis_sessions,
    │   │                                   #   collection_logs
    │   ├── session.py                      # async SQLAlchemy 세션 (asyncpg, 커넥션풀 20/10)
    │   └── repositories.py                 # BaseRepository[T] + 6종 전문 레포지토리
    │
    ├── collectors/                         # 데이터 수집기 ✅ 완료
    │   ├── base.py                         # BaseCollector (~170줄) — 재시도, Rate Limit
    │   ├── seoul.py                        # SeoulCollector (~300줄) — 서울 열린데이터 3종
    │   ├── kosis.py                        # KosisCollector (~140줄) — 통계청 KOSIS
    │   └── semas.py                        # SemasCollector (~335줄) — 소상공인진흥공단 4종
    │
    ├── preprocessors/                      # 전처리기 ✅ 완료
    │   ├── coordinate_transformer.py       # TM/UTM-K/KATEC → WGS84, 서울 범위 검증
    │   ├── code_mapper.py                  # 인메모리 코드 매핑 캐시, 행정동→상권 변환
    │   ├── missing_handler.py              # Forward fill, 균등 분배, 인구 기본값
    │   └── outlier_detector.py             # IQR, 시계열, 변동률 이상치 감지
    │
    ├── cache/                              # 캐싱 ✅ 완료
    │   └── redis_client.py                 # async Redis + cached_call() 헬퍼
    │                                       #   키 패턴: {server}:{tool}:{sha256_hash}
    │                                       #   기본 TTL: 3600초
    │
    ├── scheduler/                          # 스케줄링 ✅ 완료
    │   └── jobs.py                         # APScheduler 8개 배치 작업
    │
    ├── monitoring/                         # 모니터링 ✅ 프레임워크 완료
    │   ├── metrics.py                      # Prometheus 메트릭 (11종)
    │   ├── dag_tracer.py                   # @trace_node 데코레이터
    │   ├── mcp_monitor.py                  # MCP 모니터링 미들웨어
    │   ├── langfuse_handler.py             # Langfuse 트레이싱
    │   └── quality_checker.py              # Freshness/Completeness/Anomaly/무결성 체크
    │
    └── memory/                             # 메모리/RAG 🔲 스텁
        ├── reme_client.py                  # 인메모리 dict (Phase 1 스텁)
        └── lightrag_client.py              # query()→[], insert()→pass (Phase 2 스텁)
```

### Grafana 대시보드 (✅ Phase 4 신규)

```
monitoring/
├── prometheus.yml                          # Prometheus 수집 설정
└── grafana/
    ├── provisioning/                       # 자동 프로비저닝 설정
    └── dashboards/
        └── marketscope_overview.json       # MarketScope AI Overview (12 패널)
                                            #   - API 요청 처리량, p95 레이턴시
                                            #   - 에이전트 실행시간, 에러율
                                            #   - LLM 토큰/비용 (시간당)
                                            #   - MCP 서버 레이턴시, 에러율
                                            #   - 토론 라운드, 수렴률 게이지
                                            #   - 파이프라인 노드 히트맵, 전체 실행시간
```

### Alembic 마이그레이션 (✅)

```
alembic/
├── env.py                                  # async 모드 설정
└── versions/
    └── 001_initial_schema.py               # 10 테이블 + PostGIS 확장 + GIST 인덱스
```

---

## 3. 완료된 작업 이력

### Phase 0 + Phase 1: 기반 + 핵심 에이전트 MVP ✅

| ID | 내용 | 수정 파일 |
|----|------|-----------|
| P0-1 | nodes.py MCPClient 주입 + 에이전트 팩토리 | `graph/nodes.py` |
| P0-2 | LLM Provider 추상화 레이어 | `llm/` 패키지 신규, `agents/base.py` 리팩터링 |
| P1-1 | 인메모리 저장소 TTL + SSE Queue + heartbeat | `api/routes/analysis.py` |
| P1-2 | narrative/visualization run() 통일 | `agents/narrative.py`, `agents/visualization.py` |
| P1-3 | State 타입 일관성 (dict 통일) | `agents/base.py`, `commander.py`, `revenue.py`, `location.py` |
| P1-4 | 프로덕션 설정 검증 | `config.py` |
| P2-1 | 병렬 실행 (fan-out/fan-in 배리어 노드) | `graph/workflow.py`, `graph/nodes.py` |
| P2-2 | MCP 클라이언트 커넥션 관리 | `tools/mcp_client.py` |
| P2-3 | 비교모드 state 필드 + 에러 표준화 | `models/state.py`, `exceptions.py`, `graph/edges.py`, 4개 에이전트 |

### D0~D5: 데이터 파이프라인 ✅

| 단계 | 목표 | 상태 | 구현 상세 |
|------|------|------|-----------|
| **D0** | DB 스키마 + 코드 매핑 | ✅ 완료 | 10 ORM 모델, Alembic 001, PostGIS, BaseRepository[T] + 6종 |
| **D1** | Collector (API → DB) | ✅ 완료 | BaseCollector + Seoul(3종) + KOSIS + SEMAS(4종), 재시도/Rate Limit |
| **D2** | Preprocessor (변환, 정제) | ✅ 완료 | 좌표변환(TM→WGS84), 코드매핑, 결측치, 이상치(IQR) |
| **D3** | MCP Server — Public Data | ✅ 완료 | 8 도구 + 3 리소스, port 5100, TOOL_REGISTRY |
| **D4** | MCP Server — Maps/GIS | ✅ 완료 | 7 도구, port 5101, 카카오 API |
| **D5** | 캐싱 + 스케줄링 + 모니터링 | ✅ 완료 | Redis cached_call, APScheduler 8작업, 품질체크 |

### Phase 4: 리팩토링 & 문서 보강 ✅ (2026-03-21 완료)

| ID | 내용 | 수정/생성 파일 |
|----|------|----------------|
| P4-1 | `user_input_node` 추가 (입력 파싱/검증 엔트리포인트) | `graph/nodes.py`, `graph/workflow.py` |
| P4-2 | `debate_check_node` 추가 (4조건 트리거 평가) | `graph/nodes.py`, `graph/edges.py`, `graph/workflow.py` |
| P4-3 | State 필드 추가 (`debate_decision`, `debate_trigger_reasons`) | `models/state.py` |
| P4-4 | `should_run_debate()` → `route_after_debate_check()` 엣지 대체 | `graph/edges.py` |
| P4-5 | 워크플로우 통합 검증 (18 → 20 노드) | `graph/workflow.py` |
| P4-6 | Finance MCP 서버 신규 (6 도구) | `mcp_servers/finance/` (5 파일) |
| P4-7 | Database MCP 서버 신규 (5 도구, PostGIS) | `mcp_servers/database/` (5 파일) |
| P4-8 | Google Maps MCP 서버 신규 (5 도구) | `mcp_servers/google_maps/` (5 파일) |
| P4-9 | Naver Maps MCP 서버 신규 (5 도구) | `mcp_servers/naver_maps/` (5 파일) |
| P4-10 | MCPClientRouter 9개 서버 등록 | `config.py` |
| P4-11 | Docker Compose 4개 MCP 서비스 추가 | `docker-compose.yml` |
| P4-12 | Grafana 대시보드 (12 패널) | `monitoring/grafana/dashboards/marketscope_overview.json` |
| P4-13 | MCP 스펙 문서 3건 (Database, Google Maps, Naver Maps) | `document/specs/05_mcp_servers_*.md` |
| P4-14 | 누락 문서 8건 (배포~개발자가이드) | `document/specs/11~17_*.md` |

### Phase 5: 기능 테스트 & 버그 수정 ✅ (2026-03-21 완료)

| ID | 내용 | 수정/생성 파일 |
|----|------|----------------|
| P5-1 | `.env` PHASE1_ALLOWED_DISTRICTS 파싱 오류 수정 (콤마→JSON 배열) | `.env` |
| P5-2 | `debate_check_node` commander_plan None 방어 코드 추가 | `graph/nodes.py` |
| P5-3 | conftest.py 공통 fixture 작성 (mock_settings, mock_mcp, mock_llm 등) | `tests/conftest.py` |
| P5-4 | 에이전트 단위 테스트 11건 (call_tool, call_llm, parallel, confidence) | `tests/unit/test_agents.py` |
| P5-5 | MCPClientRouter 단위 테스트 13건 (9서버 라우팅, lazy 생성, 폴백) | `tests/unit/test_mcp_client.py` |
| P5-6 | 그래프 노드 단위 테스트 11건 (user_input, debate_check) | `tests/unit/test_nodes.py` |
| P5-7 | Edge 함수 단위 테스트 14건 (5개 edge 함수 전체 분기) | `tests/unit/test_edges.py` |
| P5-8 | MCP 서버 도구 테스트 14건 (finance 계산, database SQL 차단) | `tests/unit/test_mcp_tools.py` |
| P5-9 | 워크플로우 통합 테스트 6건 (노드 수, 구조, State 초기화) | `tests/integration/test_workflow.py` |
| — | **총 71개 테스트 전체 pass (1.10s)** | — |

---

## 4. API 키 현황

| API | .env 변수 | 상태 | 테스트 결과 |
|-----|-----------|------|-------------|
| Gemini (LLM) | `GOOGLE_API_KEY` | ✅ 설정됨 | 미테스트 (LLM 호출) |
| 서울 열린데이터 | `DATA_API_SEOUL_OPEN_DATA_KEY` | ✅ 설정됨 | ✅ 생활인구 데이터 수신 확인 |
| 카카오 REST API | `DATA_API_KAKAO_REST_KEY` | ✅ 설정됨 | ✅ 키워드 검색 정상 (15건 수신) |
| KOSIS | `DATA_API_KOSIS_KEY` | ✅ 설정됨 | ✅ 통계목록 수신 확인 |
| data.go.kr (SEMAS) | `DATA_API_PUBLIC_DATA_KEY` | ❌ 미발급 | - |
| Anthropic (Claude) | `ANTHROPIC_API_KEY` | ❌ 비어있음 | - |
| Google Maps | `DATA_API_GOOGLE_MAPS_KEY` | ❌ 미설정 | - |
| Naver Maps (NCP) | `DATA_API_NAVER_CLIENT_ID/SECRET` | ❌ 미설정 | - |

### LLM 모델 설정
- Commander/Narrative: `claude-sonnet-4-6` (Anthropic 키 필요)
- 전문 에이전트 9개: `gemini/gemini-2.5-flash`
- Judge (토론 시): `claude-opus-4-6` (Anthropic 키 필요)

---

## 5. 핵심 아키텍처 특성

### 에이전트 실행 흐름 (20 노드 DAG)
```
사용자 요청
  → POST /api/v1/analysis
  → AnalysisService.run_analysis()
  → LangGraph StateGraph 실행:
      user_input (입력 검증)
        → commander_plan (분석 계획)
        → [fan-out] Group 1: population + competition (병렬)
        → group1_complete (배리어)
        → [conditional] Group 2: revenue + location (병렬) or skip
        → group2_complete (배리어)
        → [conditional] Group 3: trend + real_estate + regulatory (병렬) or skip
        → group3_complete (배리어)
        → financial → risk
        → debate_check (4조건 평가)
        → [conditional] debate (3라운드) or commander_judgment
        → commander_judgment
        → [conditional] narrative → visualization or report_assembly
        → report_assembly
  → SSE 스트리밍으로 진행 상황 전달
  → 최종 FinalReport 반환
```

### debate_check_node 트리거 4조건
```
1. force_debate=True (사용자 명시 요청)
2. 에이전트 평균 confidence < 0.6
3. 매출 추정 변동률 > 30%
4. 에이전트 간 결론 상충 (긍정 vs 부정)
```

### MCP 서버 매핑 (9개)
| 서버 | 포트 | 도구 수 | 상태 |
|------|------|---------|------|
| public_data | 5100 | 8 | ✅ API 연동 완료 |
| maps (Kakao) | 5101 | 7 | ✅ API 연동 완료 |
| real_estate | 5102 | 4 | ⚠️ 폴백 데이터 |
| news | 5103 | 3 | ⚠️ 자격증명 필요 |
| regulatory | 5104 | 3 | ⚠️ 하드코딩 DB |
| finance | 5105 | 6 | ✅ Phase 4 신규 |
| database | 5106 | 5 | ✅ Phase 4 신규 |
| google_maps | 5107 | 5 | ✅ Phase 4 신규 (키 미설정) |
| naver_maps | 5108 | 5 | ✅ Phase 4 신규 (키 미설정) |

### 에이전트별 MCP 도구 호출 (현재 코드)
| 에이전트 | 호출하는 MCP 도구 | MCP 서버 |
|----------|------------------|----------|
| Population | `maps.geocode`, `public_data.get_seoul_living_population`, `public_data.get_resident_population`, `public_data.get_worker_population` | maps, public_data |
| Competition | `maps.geocode`, `public_data.get_store_count`, `public_data.get_store_openclose` | maps, public_data |
| Revenue | `maps.geocode`, `public_data.get_commercial_revenue`, `public_data.get_industry_revenue` | maps, public_data |
| Location | `maps.geocode`, `maps.get_transit_info`, `maps.search_nearby` | maps |
| Trend | `news.search_news`, `news.get_naver_datalab` | news |
| RealEstate | `real_estate.get_rent_info`, `real_estate.get_vacancy_rate` | real_estate |
| Regulatory | `regulatory.get_permits`, `regulatory.get_zoning` | regulatory |
| Financial | `finance.search_startup_loans`, `finance.get_minimum_wage` | finance |
| Risk | 이전 에이전트 결과 참조 (MCP 미호출) | - |

---

## 6. 설계 문서 현황 (21개)

| # | 파일 | 내용 | 상태 |
|---|------|------|------|
| 00 | `00_project_foundation.md` | 프로젝트 기반 아키텍처 | ✅ |
| 01 | `01_orchestration_langgraph.md` | LangGraph DAG 설계 | ✅ |
| 02 | `02_commander_agent.md` | Commander 에이전트 역할 | ✅ |
| 03 | `03_specialist_agents.md` | 전문 에이전트 명세 | ✅ |
| 04 | `04_debate_system.md` | 토론 시스템 프레임워크 | ✅ |
| 05 | `05_mcp_servers.md` | MCP 서버 통합 명세 (5종) | ✅ |
| 05a | `05_mcp_servers_database.md` | Database MCP 상세 | ✅ Phase 4 |
| 05b | `05_mcp_servers_google_maps.md` | Google Maps MCP 상세 | ✅ Phase 4 |
| 05c | `05_mcp_servers_naver_maps.md` | Naver Maps MCP 상세 | ✅ Phase 4 |
| 06 | `06_memory_and_rag.md` | 메모리/RAG 설계 | ✅ (구현 스텁) |
| 07 | `07_data_pipeline.md` | D0~D5 파이프라인 | ✅ |
| 08 | `08_api_endpoints.md` | REST API 명세 | ✅ |
| 09 | `09_frontend.md` | Next.js 프론트엔드 | ✅ (구현 0%) |
| 10 | `10_report_agents.md` | 리포트 생성 명세 | ✅ |
| 11 | `11_deployment.md` | 배포 & 인프라 | ✅ Phase 4 |
| 12 | `12_testing.md` | 테스트 전략 | ✅ Phase 4 |
| 13 | `13_cicd.md` | CI/CD 파이프라인 | ✅ Phase 4 |
| 14 | `14_security.md` | 보안 & 컴플라이언스 | ✅ Phase 4 |
| 15 | `15_operations.md` | 운영 & 트러블슈팅 | ✅ Phase 4 |
| 16 | `16_performance.md` | 성능 벤치마크 & SLA | ✅ Phase 4 |
| 17 | `17_developer_guide.md` | 개발자 온보딩 가이드 | ✅ Phase 4 |

---

## 7. 다음 단계: 즉시 착수 필요 항목

### ✅ 해결 완료 (Phase 5에서 확인)

| 항목 | 이전 판단 | 실제 상태 |
|------|-----------|-----------|
| MCP 멀티서버 라우팅 | ❌ 하드코딩 | ✅ `MCPClientRouter` prefix 기반 9서버 라우팅 구현됨 |
| 앱 Lifespan 통합 | ❌ 미연결 | ✅ `main.py`에서 Redis, MCPRouter, Langfuse 초기화됨 |
| `.env` 파싱 오류 | — | ✅ PHASE1_ALLOWED_DISTRICTS JSON 배열 변환 |
| `debate_check_node` None 방어 | — | ✅ `or {}` 추가 |

### P0 — 인프라 & API 키 (환경 설정 필요)

| 우선순위 | 작업 | 현상 |
|---------|------|------|
| 1 | **API 키 설정** | ANTHROPIC_API_KEY 비어있음 → Commander/Narrative/Judge 호출 실패 |
| 2 | **Docker 서비스 기동** | PostgreSQL, Redis, MCP 서버 9개 미기동 → 실 E2E 테스트 불가 |

### P1 — 코드 품질 & 안정성

| 우선순위 | 작업 | 현상 |
|---------|------|------|
| 3 | **CI/CD 파이프라인** | `.github/workflows/` 없음 (스펙 있으나 구현 0%) |
| 4 | **Docker 환경 E2E 테스트** | MCP 서버 기동 후 실제 파이프라인 실행 검증 필요 |
| 5 | **Debate 시스템 E2E 검증** | 에이전트+노드 단위테스트 통과, 실제 LLM 호출 E2E 미완 |

### P2 — 기능 완성

| 우선순위 | 작업 | 현상 |
|---------|------|------|
| 6 | **Memory/RAG 시스템** | 스텁만 존재 (빈 dict/no-op 반환) |
| 7 | **MCP 서버 API 연동** | real_estate, news, regulatory 서버 폴백/하드코딩 |
| 8 | **Frontend (Next.js)** | 스펙 09_frontend.md 존재, 코드 0% |

---

## 8. 코드 통계 요약

| 영역 | 파일 수 | 예상 LOC |
|------|--------|---------|
| agents/ (15개 + debate 4개) | 19 | ~2,650 |
| mcp_servers/ (9종) | 39 | ~3,720 |
| graph/ | 4 | ~650 |
| monitoring/ | 6 | ~800 |
| models/ | 6 | ~550 |
| api/ | 3 | ~250 |
| llm/ | 2 | ~130 |
| db/ | 3 | ~720 |
| collectors/ | 4 | ~950 |
| preprocessors/ | 4 | ~530 |
| cache+scheduler | 2 | ~250 |
| tools/ | 2 | ~250 |
| config+main+logging+etc | 5 | ~500 |
| alembic+scripts | 2 | ~510 |
| tests/ | 7 | ~530 |
| **합계** | **~123** | **~13,430** |

### 테스트 커버리지
- 71개 테스트 (unit 63 + integration 6 + conftest 2 fixture)
- 전체 pass (1.10s)
- 커버 영역: edges, nodes, mcp_client, mcp_tools, agents, workflow, state

### 설계 문서
- 21개 스펙 문서
- Grafana 대시보드 JSON 1개
- Phase 계획 4개 (1~5) + 세부 계획 3개 (phase4 restructuring/checklist, phase5 checklist)
