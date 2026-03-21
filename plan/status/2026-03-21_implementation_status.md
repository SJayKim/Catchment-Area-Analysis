# MarketScope AI — 구현 현황 (2026-03-21)

> 이 문서는 AI Agent가 현재 프로젝트 상태를 빠르게 파악할 수 있도록 작성됨

---

## 1. 프로젝트 개요

- **목적**: 상권 분석 AI Agent Swarm (서울 상권 기반 Phase 1 MVP)
- **기술 스택**: FastAPI + LangGraph + LiteLLM + Pydantic + SSE
- **코드 위치**: `/workspace/Catchment-Area-Analysis/marketscope/`
- **설계서 위치**: `/workspace/Catchment-Area-Analysis/specs/` (14개 파일, ~30,000줄)
- **계획 문서**: `/workspace/Catchment-Area-Analysis/plan/`

---

## 2. 파일 구조 및 구현 상태

### 실구현 완료 (✅)

```
marketscope/
├── pyproject.toml                          # 의존성 정의
├── .env                                    # 개발 환경 설정 (API 키 포함)
├── .env.example                            # 환경변수 템플릿
└── app/
    ├── main.py                             # FastAPI 앱 (CORS, 라우터, lifespan)
    ├── config.py                           # Pydantic Settings (240줄, 프로덕션 검증 포함)
    ├── constants.py                        # Enum 정의 (AnalysisMode, ConfidenceLevel 등)
    ├── exceptions.py                       # 8개 예외 클래스 (DataCollectionError 포함)
    ├── logging_config.py                   # 구조화된 로깅 (JSON 포맷)
    │
    ├── agents/                             # 에이전트 레이어 ✅
    │   ├── base.py                         # BaseAgent[T] 추상 클래스 (341줄)
    │   │                                   #   - LLM Provider 주입 (litellm 직접 의존 제거)
    │   │                                   #   - call_llm(): 재시도 + 구조화 출력 파싱
    │   │                                   #   - call_tool(): MCP 도구 호출
    │   │                                   #   - run(): LangGraph 노드 래퍼 (Pydantic→dict 변환)
    │   │                                   #   - _RESULT_FIELD_MAP: narrative/visualization 필드명 매핑
    │   ├── commander.py                    # CommanderAgent (311줄)
    │   │                                   #   - run_planning(): 분석 계획 수립
    │   │                                   #   - run_judgment(): 최종 종합 판단
    │   ├── population.py                   # PopulationAgent (133줄) — 유동/주민/직장인구
    │   ├── competition.py                  # CompetitionAgent (126줄) — 경쟁/포화도
    │   ├── revenue.py                      # RevenueAgent (130줄) — 매출 추정
    │   ├── location.py                     # LocationAgent (137줄) — 입지/교통/앵커시설
    │   ├── narrative.py                    # NarrativeAgent (90줄) — 리포트 텍스트 생성
    │   └── visualization.py               # VisualizationAgent (107줄) — 차트/지도 설정
    │
    ├── llm/                                # LLM 추상화 레이어 ✅
    │   ├── provider.py                     # LLMProvider Protocol + LLMResponse 데이터클래스
    │   └── litellm_provider.py             # LiteLLMProvider 구현체 (Claude/Gemini/GPT 지원)
    │
    ├── graph/                              # LangGraph 오케스트레이션 ✅
    │   ├── workflow.py                     # StateGraph DAG (병렬 fan-out/fan-in 패턴)
    │   │                                   #   - Group 1: population + competition 병렬
    │   │                                   #   - Group 2: revenue + location 병렬
    │   │                                   #   - group1_complete / group2_complete 배리어 노드
    │   ├── nodes.py                        # 노드 함수 + 에이전트 팩토리 (MCPClient 싱글톤)
    │   └── edges.py                        # 조건부 엣지 (분석모드, 리포트 스킵, 비교모드)
    │
    ├── models/                             # 데이터 모델 ✅
    │   ├── state.py                        # MarketScopeState TypedDict (비교모드 필드 포함)
    │   ├── agent_outputs.py                # 4개 분석 결과 Pydantic 모델
    │   ├── common.py                       # 공통 타입 (TimeSlot, AgeDistribution 등)
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
        │                                   #   - JSON 파싱 에러 핸들링
        │                                   #   - MCPClientError/MCPConnectionError/MCPResponseError
        └── registry.py                     # ToolRegistry (에이전트→도구 매핑)
```

### 스텁/미구현 (🔲)

```
    ├── db/                                 # 데이터베이스 🔲 스텁
    │   ├── models.py                       # "Phase 2 스텁" — ORM 모델 없음
    │   ├── session.py                      # get_db_session() → None 반환
    │   └── repositories.py                 # "Phase 2 스텁"
    │
    ├── memory/                             # 메모리/RAG 🔲 스텁
    │   ├── reme_client.py                  # 인메모리 dict (Phase 1 스텁)
    │   └── lightrag_client.py              # query()→[], insert()→pass (Phase 2 스텁)
    │
    ├── models/
    │   └── debate.py                       # 토론 시스템 (Phase 2 스텁)
    │
    ├── collectors/                         # 🔲 존재하지 않음 — D1에서 신규 생성 예정
    ├── preprocessors/                      # 🔲 존재하지 않음 — D2에서 신규 생성 예정
    ├── mcp_servers/                        # 🔲 존재하지 않음 — D3/D4에서 신규 생성 예정
    ├── cache/                              # 🔲 존재하지 않음 — D5에서 신규 생성 예정
    ├── scheduler/                          # 🔲 존재하지 않음 — D5에서 신규 생성 예정
    └── monitoring/                         # 🔲 존재하지 않음 — D5에서 신규 생성 예정
```

---

## 3. 완료된 개선 작업 (revising_plan1.md)

### P0: CRITICAL ✅
| ID | 내용 | 수정 파일 |
|----|------|-----------|
| P0-1 | nodes.py MCPClient 주입 + 에이전트 팩토리 | `graph/nodes.py` |
| P0-2 | LLM Provider 추상화 레이어 | `llm/` 패키지 신규, `agents/base.py` 리팩터링 |

### P1: HIGH ✅
| ID | 내용 | 수정 파일 |
|----|------|-----------|
| P1-1 | 인메모리 저장소 TTL + SSE Queue + heartbeat | `api/routes/analysis.py` |
| P1-2 | narrative/visualization run() 통일 | `agents/narrative.py`, `agents/visualization.py` |
| P1-3 | State 타입 일관성 (dict 통일) | `agents/base.py`, `commander.py`, `revenue.py`, `location.py` |
| P1-4 | 프로덕션 설정 검증 | `config.py` |

### P2: MEDIUM ✅
| ID | 내용 | 수정 파일 |
|----|------|-----------|
| P2-1 | 병렬 실행 (fan-out/fan-in 배리어 노드) | `graph/workflow.py`, `graph/nodes.py` |
| P2-2 | MCP 클라이언트 커넥션 관리 | `tools/mcp_client.py` |
| P2-3 | 비교모드 state 필드 + 에러 표준화 | `models/state.py`, `exceptions.py`, `graph/edges.py`, 4개 에이전트 |

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

### LLM 모델 설정
- 전 에이전트 `gemini/gemini-2.5-flash` 통일 (Anthropic 키 없이 테스트 가능)

---

## 5. 핵심 아키텍처 특성

### 에이전트 실행 흐름
```
사용자 요청
  → POST /api/v1/analysis
  → AnalysisService.run_analysis()
  → LangGraph StateGraph 실행:
      commander_plan
        → [fan-out] population + competition (병렬)
        → group1_complete (배리어)
        → [conditional] revenue + location (병렬) or commander_judgment
        → group2_complete (배리어)
        → commander_judgment
        → [conditional] narrative → visualization or report_assembly
        → report_assembly
  → SSE 스트리밍으로 진행 상황 전달
  → 최종 FinalReport 반환
```

### 에이전트 데이터 의존성
```
population ──→ revenue (인구 데이터 참조)
population ──→ location (인구 데이터 참조)
competition ──→ location (경쟁 데이터 참조)
4개 결과 ──→ commander_judgment (종합 판단)
judgment ──→ narrative (리포트 텍스트)
judgment ──→ visualization (차트 설정)
```

### 에이전트별 MCP 도구 호출 (현재 코드)
| 에이전트 | 호출하는 MCP 도구 | MCP 서버 |
|----------|------------------|----------|
| Population | `maps.geocode`, `public_data.get_seoul_living_population`, `public_data.get_resident_population`, `public_data.get_worker_population` | maps, public_data |
| Competition | `maps.geocode`, `public_data.get_store_count`, `public_data.get_store_openclose` | maps, public_data |
| Revenue | `maps.geocode`, `public_data.get_commercial_revenue`, `public_data.get_industry_revenue` | maps, public_data |
| Location | `maps.geocode`, `maps.get_transit_info`, `maps.search_nearby` | maps |

---

## 6. 다음 단계: 데이터 구축 (D0~D5)

상세 계획: `/workspace/Catchment-Area-Analysis/plan/data/data_process_plan.md`

| 단계 | 목표 | 상태 |
|------|------|------|
| **D0** | DB 스키마 + 코드 매핑 | 🔲 미착수 |
| **D1** | Collector (API → DB) | 🔲 미착수 |
| **D2** | Preprocessor (변환, 정제) | 🔲 미착수 |
| **D3** | MCP Server — Public Data (8개 도구) | 🔲 미착수 |
| **D4** | MCP Server — Maps/GIS (7개 도구) | 🔲 미착수 |
| **D5** | 캐싱 + 스케줄링 + 모니터링 | 🔲 미착수 |

### 빠른 검증 경로
- D4 (Maps MCP) → 카카오 API 키 확보 완료, DB 불필요 → Location 에이전트 E2E 최우선 테스트
- D3 일부 → 서울 열린데이터/KOSIS 직접 호출 (DB 없이 가능)

---

## 7. 미구현 Phase 2 항목 (참고)

| 항목 | 설계서 | 현재 상태 |
|------|--------|-----------|
| LightRAG 지식 그래프 | `specs/06_memory_and_rag.md` (3,100줄) | 스텁 |
| ReMe 세션 메모리 | `specs/06_memory_and_rag.md` | 스텁 |
| 토론 시스템 | `specs/04_debate_system.md` | 스텁 |
| 부동산 에이전트 | `specs/03_specialist_agents.md` | 미구현 |
| 규제/인허가 에이전트 | `specs/03_specialist_agents.md` | 미구현 |
| 트렌드 에이전트 | `specs/03_specialist_agents.md` | 미구현 |
| 리스크 에이전트 | `specs/03_specialist_agents.md` | 미구현 |
| 금융/대출 에이전트 | `specs/03_specialist_agents.md` | 미구현 |
| MCP Server #3~#6 | `specs/05_mcp_servers.md` | 미구현 |
| Next.js 프론트엔드 | `specs/09_frontend.md` | 미구현 |
