# MarketScope AI - 상권 분석 서비스

> LangGraph 기반 멀티 에이전트 DAG 오케스트레이션으로 상권 분석을 자동화하는 AI 서비스

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)]()
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-purple.svg)]()

---

## 목차

- [시스템 아키텍처](#시스템-아키텍처)
- [User Flow](#user-flow)
- [LangGraph DAG 구조](#langgraph-dag-구조)
- [MCP 서버 아키텍처](#mcp-서버-아키텍처)
- [에이전트 상세](#에이전트-상세)
- [기술 스택](#기술-스택)
- [프로젝트 구조](#프로젝트-구조)
- [Quick Start](#quick-start)
- [API 엔드포인트](#api-엔드포인트)
- [분석 모드](#분석-모드)
- [모니터링](#모니터링)
- [설계 문서](#설계-문서)

---

## 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Client Layer                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                      │
│  │   Web App    │  │  Mobile App  │  │   API Client │                      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                      │
│         └─────────────────┼─────────────────┘                              │
│                           │ HTTP / SSE                                      │
└───────────────────────────┼─────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FastAPI Application (:8000)                          │
│                                                                             │
│  ┌─────────────┐  ┌─────────────────┐  ┌──────────────┐  ┌─────────────┐  │
│  │  /api/v1/   │  │  /api/v1/       │  │  /api/v1/    │  │  /metrics   │  │
│  │  analysis   │  │  health/*       │  │  analysis/   │  │ (Prometheus)│  │
│  │  (REST)     │  │  (Probes)       │  │  {id}/stream │  │             │  │
│  └──────┬──────┘  └─────────────────┘  │  (SSE)       │  └─────────────┘  │
│         │                              └──────┬───────┘                    │
│         │         ┌────────────────────────────┘                           │
│         ▼         ▼                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │                    AnalysisService                                │      │
│  │  ┌──────────────────────────────────────────────────────────┐    │      │
│  │  │              LangGraph StateGraph (20 Nodes)             │    │      │
│  │  │                                                          │    │      │
│  │  │  user_input → commander_plan → [Group 1..3 Parallel]    │    │      │
│  │  │  → financial → risk → debate_check → [debate]           │    │      │
│  │  │  → commander_judgment → narrative → viz → report        │    │      │
│  │  └──────────────────────┬───────────────────────────────────┘    │      │
│  └─────────────────────────┼────────────────────────────────────────┘      │
│                            │                                               │
│  ┌─────────────────────────▼───────────────────────────────────────┐       │
│  │                   BaseAgent[T] Framework                         │       │
│  │                                                                  │       │
│  │  ┌──────────┐  ┌──────────────┐  ┌────────────────────────┐    │       │
│  │  │ call_llm │  │  call_tool   │  │ call_tools_parallel    │    │       │
│  │  │ (retry)  │  │  (MCP route) │  │ (semaphore=5)          │    │       │
│  │  └────┬─────┘  └──────┬───────┘  └────────────┬───────────┘    │       │
│  │       │               │                        │                │       │
│  └───────┼───────────────┼────────────────────────┼────────────────┘       │
│          │               │                        │                        │
└──────────┼───────────────┼────────────────────────┼────────────────────────┘
           │               │                        │
           ▼               ▼                        ▼
┌──────────────────┐  ┌─────────────────────────────────────────────────────┐
│   LLM Providers  │  │              MCPClientRouter (Prefix Routing)       │
│                  │  │                                                     │
│  ┌────────────┐  │  │  tool_name="maps.geocode"                          │
│  │ Claude     │  │  │       ↓ split(".") → prefix="maps"                │
│  │ (Anthropic)│  │  │       ↓ lookup mcp_servers["maps"]                │
│  ├────────────┤  │  │       ↓ route to :5101                            │
│  │ Gemini     │  │  │                                                     │
│  │ (Google)   │  │  │  Fallback: no prefix → "public_data" (:5100)      │
│  └────────────┘  │  └──────────────────────┬──────────────────────────────┘
│  via LiteLLM     │                         │
└──────────────────┘                         ▼
                          ┌──────────────────────────────────────────────┐
                          │          9 MCP Servers (FastAPI)              │
                          │                                              │
                          │  :5100 public_data   :5101 maps              │
                          │  :5102 real_estate   :5103 news              │
                          │  :5104 regulatory    :5105 finance           │
                          │  :5106 database      :5107 google_maps       │
                          │  :5108 naver_maps                            │
                          └──────────┬───────────────────────────────────┘
                                     │
                                     ▼
                          ┌──────────────────────────────────────────────┐
                          │           External Data Sources               │
                          │                                              │
                          │  ┌──────────┐ ┌──────────┐ ┌──────────┐    │
                          │  │ KOSIS    │ │ Seoul    │ │ Google   │    │
                          │  │ 통계청   │ │ Open API │ │ Maps API │    │
                          │  ├──────────┤ ├──────────┤ ├──────────┤    │
                          │  │ Naver    │ │ 국토교통 │ │ 뉴스/    │    │
                          │  │ Maps API │ │ 실거래가 │ │ 트렌드   │    │
                          │  └──────────┘ └──────────┘ └──────────┘    │
                          └──────────────────────────────────────────────┘

           ┌─────────────────────────────────────────────────────────┐
           │                  Infrastructure Layer                    │
           │                                                         │
           │  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
           │  │PostgreSQL│  │  Redis   │  │ Langfuse │             │
           │  │ (상권DB) │  │ (Cache)  │  │(Tracing) │             │
           │  │  :5432   │  │  :6379   │  │          │             │
           │  └──────────┘  └──────────┘  └──────────┘             │
           └─────────────────────────────────────────────────────────┘
```

---

## User Flow

### 전체 사용자 흐름

```
┌──────────┐     POST /api/v1/analysis         ┌───────────────────┐
│          │ ──────────────────────────────────▶│   FastAPI Server   │
│          │     {"query": "강남역 카페 창업",    │                   │
│          │      "depth": "standard"}          │  1. request_id 생성│
│  Client  │◀────────────────────────────────── │  2. 202 Accepted  │
│          │     {request_id, stream_url}        │  3. 백그라운드 실행 │
│          │                                    └────────┬──────────┘
│          │     GET /analysis/{id}/stream                │
│          │ ──────────────────────────────────▶          │
│          │                                             ▼
│          │     SSE Event Stream              ┌───────────────────┐
│          │◀╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌│ LangGraph 워크플로우│
│          │  data: {"phase":0, "pct":2}       │                   │
│          │  data: {"phase":1, "pct":5}       │  20 Node DAG 실행  │
│          │  data: {"phase":3, "pct":25}      │  (상세 아래 참조)   │
│          │  data: {"phase":4, "pct":45}      │                   │
│          │  data: {"phase":5, "pct":60}      └────────┬──────────┘
│          │  data: {"phase":6, "pct":100}               │
│          │  data: {"status":"completed"}               ▼
│          │                                   ┌───────────────────┐
│          │     GET /analysis/{id}             │  Result Store     │
│          │ ──────────────────────────────────▶│  (In-Memory)      │
│          │◀────────────────────────────────── │                   │
│          │     {final_report: {...}}          └───────────────────┘
└──────────┘
```

### 상세 처리 단계

```
 User Request
      │
      ▼
 ┌─────────────────────────────────────────────────────────────────────┐
 │  Phase 0: 입력 파싱                                                 │
 │  ┌───────────────┐                                                  │
 │  │  user_input   │  사용자 쿼리 검증 (빈 입력 체크)                    │
 │  │  [progress 2%]│  → 실패 시 has_critical_failure=true             │
 │  └───────┬───────┘                                                  │
 │          ▼                                                          │
 │  Phase 1: 전략 수립                                                  │
 │  ┌───────────────┐                                                  │
 │  │ commander_plan│  LLM이 분석 전략 수립                              │
 │  │  [progress 5%]│  → analysis_mode (quick/standard/deep)           │
 │  └───────┬───────┘  → target_location, target_industry              │
 │          │          → agents_to_run, force_debate 여부               │
 │          │                                                          │
 │          ├── clarification_needed? ──YES──▶ [사용자에게 재질문] END   │
 │          │                                                          │
 │          ▼ NO                                                       │
 │  Phase 2: 데이터 수집 (병렬 실행)                                     │
 │  ┌──────────────────────────────────────────────────────────┐       │
 │  │  Group 1 (Fan-out)                    [progress → 25%]   │       │
 │  │  ┌──────────────┐  ┌──────────────┐                      │       │
 │  │  │  population  │  │ competition  │   병렬 실행           │       │
 │  │  │  인구분석     │  │  경쟁분석    │                       │       │
 │  │  └──────┬───────┘  └──────┬───────┘                      │       │
 │  │         └────────┬────────┘                              │       │
 │  │                  ▼                                       │       │
 │  │         group1_complete (Fan-in Barrier)                 │       │
 │  └──────────────────┬───────────────────────────────────────┘       │
 │                     │                                               │
 │          ┌──────────┤ quick mode? ──YES──▶ [commander_judgment]      │
 │          │          │                                               │
 │          ▼ NO       │                                               │
 │  ┌──────────────────────────────────────────────────────────┐       │
 │  │  Group 2 (Fan-out)                    [progress → 45%]   │       │
 │  │  ┌──────────────┐  ┌──────────────┐                      │       │
 │  │  │   revenue    │  │   location   │   병렬 실행           │       │
 │  │  │  매출분석     │  │  입지분석    │                       │       │
 │  │  └──────┬───────┘  └──────┬───────┘                      │       │
 │  │         └────────┬────────┘                              │       │
 │  │                  ▼                                       │       │
 │  │         group2_complete (Fan-in Barrier)                 │       │
 │  └──────────────────┬───────────────────────────────────────┘       │
 │                     │                                               │
 │  ┌──────────────────────────────────────────────────────────┐       │
 │  │  Group 3 (Fan-out)                    [progress → 60%]   │       │
 │  │  ┌──────────┐  ┌──────────────┐  ┌──────────────┐       │       │
 │  │  │  trend   │  │ real_estate  │  │  regulatory  │       │       │
 │  │  │ 트렌드   │  │  부동산분석   │  │  규제분석    │       │       │
 │  │  └────┬─────┘  └──────┬───────┘  └──────┬───────┘       │       │
 │  │       └───────────────┼─────────────────┘               │       │
 │  │                       ▼                                  │       │
 │  │              group3_complete (Fan-in Barrier)            │       │
 │  └───────────────────────┬──────────────────────────────────┘       │
 │                          ▼                                          │
 │  Phase 3: 종합 분석 (순차 실행)                                       │
 │  ┌──────────────┐  ┌──────────────┐                                 │
 │  │  financial   │─▶│    risk      │  재무 → 리스크 순차 분석           │
 │  │  재무분석     │  │  리스크분석   │                                  │
 │  └──────────────┘  └──────┬───────┘                                 │
 │                           ▼                                         │
 │  Phase 4: 품질 검증                                                  │
 │  ┌──────────────────────────────────────────────────┐               │
 │  │  debate_check                                    │               │
 │  │  4가지 트리거 조건 평가:                            │               │
 │  │  ① force_debate 플래그                            │               │
 │  │  ② 평균 confidence < 0.6                         │               │
 │  │  ③ 매출 추정 분산 > 30%                           │               │
 │  │  ④ 에이전트 간 결론 충돌 (차이 > 0.3)              │               │
 │  └───────────┬──────────────────────────────────────┘               │
 │              │                                                      │
 │         trigger? ──YES──▶ ┌──────────────────────────┐              │
 │              │            │  debate                   │              │
 │              │            │  ┌─────────┐              │              │
 │              │            │  │Advocate │ (찬성 논증)   │              │
 │              │            │  │Gemini   │              │              │
 │              │            │  └────┬────┘              │              │
 │              │            │       ▼                   │              │
 │              │            │  ┌─────────┐              │              │
 │              │            │  │ Critic  │ (반박 논증)   │              │
 │              │            │  │ Claude  │              │              │
 │              │            │  └────┬────┘              │              │
 │              │            │       ▼                   │              │
 │              │            │  ┌─────────┐              │              │
 │              │            │  │  Judge  │ (최종 판결)   │              │
 │              │            │  │ Opus    │              │              │
 │              │            │  └────┬────┘              │              │
 │              │            └───────┼──────────────────┘               │
 │              │                    │                                  │
 │              ▼ NO                 │                                  │
 │              └────────────────────┘                                  │
 │                         │                                           │
 │                         ▼                                           │
 │  Phase 5: 최종 판단                                                  │
 │  ┌──────────────────────────────┐                                   │
 │  │   commander_judgment         │                                   │
 │  │   - overall_score (0~100)    │                                   │
 │  │   - grade (A/B/C/D/F)       │                                   │
 │  │   - recommendation          │                                   │
 │  │   - key_findings[]          │                                   │
 │  └──────────────┬───────────────┘                                   │
 │                 │                                                   │
 │       critical_failure? ──YES──▶ [report_assembly] (최소 리포트)     │
 │                 │                                                   │
 │                 ▼ NO                                                │
 │  Phase 6: 리포트 생성           [progress → 100%]                    │
 │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐          │
 │  │  narrative   │─▶│visualization │─▶│ report_assembly  │          │
 │  │  보고서 작성  │  │ 차트/지도 설정│  │  최종 리포트 조립 │          │
 │  └──────────────┘  └──────────────┘  └────────┬─────────┘          │
 │                                               │                    │
 └───────────────────────────────────────────────┼────────────────────┘
                                                 ▼
                                          ┌─────────────┐
                                          │ final_report│
                                          │  반환        │
                                          └─────────────┘
```

---

## LangGraph DAG 구조

### 노드 연결 다이어그램 (20 Nodes)

```
                        ┌───────────┐
                        │__start__  │
                        └─────┬─────┘
                              │
                        ┌─────▼─────┐
                        │user_input │ ─── 빈 입력 → 에러
                        └─────┬─────┘
                              │
                     ┌────────▼────────┐
                     │ commander_plan  │
                     └────────┬────────┘
                              │
               should_continue_after_commander
                     │                    │
              clarification           parallel_group_1
                  needed                    │
                     │              ┌───────┴───────┐
                   [END]            │               │
                           ┌───────▼──┐     ┌──────▼───────┐
                           │population│     │ competition  │
                           └───────┬──┘     └──────┬───────┘
                                   │               │
                              ┌────▼───────────────▼───┐
                              │    group1_complete      │
                              └────────────┬───────────┘
                                           │
                                 should_run_group2
                              │                    │
                        quick mode           parallel_group_2
                              │                    │
                              │            ┌───────┴───────┐
                              │            │               │
                              │     ┌──────▼──┐    ┌───────▼───┐
                              │     │ revenue │    │ location  │
                              │     └──────┬──┘    └───────┬───┘
                              │            │               │
                              │       ┌────▼───────────────▼───┐
                              │       │    group2_complete      │
                              │       └────────────┬───────────┘
                              │                    │
                              │          should_run_group3
                              │       │                    │
                              │  quick mode          parallel_group_3
                              │       │                    │
                              │       │      ┌─────────────┼─────────────┐
                              │       │      │             │             │
                              │       │ ┌────▼───┐  ┌─────▼──────┐ ┌───▼────────┐
                              │       │ │ trend  │  │real_estate │ │ regulatory │
                              │       │ └────┬───┘  └─────┬──────┘ └───┬────────┘
                              │       │      │            │            │
                              │       │ ┌────▼────────────▼────────────▼───┐
                              │       │ │        group3_complete           │
                              │       │ └─────────────────┬───────────────┘
                              │       │                   │
                              │       │          ┌────────▼────────┐
                              │       └─────────▶│   financial    │
                              │                  └────────┬───────┘
                              │                           │
                              │                  ┌────────▼────────┐
                              │                  │      risk      │
                              │                  └────────┬───────┘
                              │                           │
                              │                  ┌────────▼────────┐
                              └─────────────────▶│  debate_check  │
                                                 └────────┬───────┘
                                                          │
                                           route_after_debate_check
                                                 │              │
                                              trigger          skip
                                                 │              │
                                          ┌──────▼──────┐       │
                                          │   debate    │       │
                                          └──────┬──────┘       │
                                                 │              │
                                          ┌──────▼──────────────▼───┐
                                          │  commander_judgment     │
                                          └────────────┬───────────┘
                                                       │
                                            should_skip_reports
                                                 │            │
                                           report_gen    critical_failure
                                                 │            │
                                          ┌──────▼──────┐     │
                                          │  narrative  │     │
                                          └──────┬──────┘     │
                                                 │            │
                                          ┌──────▼────────┐   │
                                          │visualization  │   │
                                          └──────┬────────┘   │
                                                 │            │
                                          ┌──────▼────────────▼───┐
                                          │   report_assembly     │
                                          └────────────┬──────────┘
                                                       │
                                                 ┌─────▼─────┐
                                                 │  __end__   │
                                                 └───────────┘
```

### 조건부 라우팅 함수 (Edge Functions)

| 함수 | 입력 조건 | 분기 결과 |
|------|----------|----------|
| `should_continue_after_commander` | `clarification_needed` | `parallel_group_1` / `end` |
| `should_run_group2` | `analysis_mode == "quick"` | `parallel_group_2` / `commander_judgment` |
| `should_run_group3` | `analysis_mode == "quick"` | `parallel_group_3` / `financial` |
| `route_after_debate_check` | `debate_decision == "trigger"` | `debate` / `commander_judgment` |
| `should_skip_reports` | `has_critical_failure` | `report_generation` / `report_assembly` |

---

## MCP 서버 아키텍처

```
                   ┌─────────────────────────────┐
                   │     MCPClientRouter          │
                   │                             │
                   │  tool_name.split(".") ──┐   │
                   │                        │   │
                   │  prefix → server 매핑   │   │
                   │  (no prefix → fallback) │   │
                   └─────────────┬───────────┘   │
                                │               │
           ┌────────────────────┼───────────────┘
           │                    │
           ▼                    ▼
  ┌─────────────────────────────────────────────────────────────┐
  │                    9 MCP Servers                             │
  │                                                             │
  │  ┌─────────────────┐  ┌─────────────────┐  ┌────────────┐ │
  │  │ public_data     │  │ maps            │  │ real_estate│ │
  │  │ :5100           │  │ :5101           │  │ :5102      │ │
  │  │ KOSIS, 서울 API  │  │ 일반 지오코딩    │  │ 부동산 시세 │ │
  │  └─────────────────┘  └─────────────────┘  └────────────┘ │
  │                                                             │
  │  ┌─────────────────┐  ┌─────────────────┐  ┌────────────┐ │
  │  │ news            │  │ regulatory      │  │ finance    │ │
  │  │ :5103           │  │ :5104           │  │ :5105      │ │
  │  │ 뉴스/트렌드 분석 │  │ 인허가/규제 조회 │  │ 재무 계산  │ │
  │  └─────────────────┘  └─────────────────┘  └────────────┘ │
  │                                                             │
  │  ┌─────────────────┐  ┌─────────────────┐  ┌────────────┐ │
  │  │ database        │  │ google_maps     │  │ naver_maps │ │
  │  │ :5106           │  │ :5107           │  │ :5108      │ │
  │  │ 공간 DB 쿼리    │  │ Google Maps API │  │ Naver API  │ │
  │  └─────────────────┘  └─────────────────┘  └────────────┘ │
  │                                                             │
  │  Protocol: HTTP (POST /tools/call, GET /tools/list)        │
  │  Health:   GET /health                                     │
  └─────────────────────────────────────────────────────────────┘
```

### MCP 도구 라우팅 예시

```
call_tool("maps.geocode", {"address": "강남역"})
    → prefix: "maps"
    → server: http://localhost:5101
    → POST /tools/call  {"name": "geocode", "arguments": {"address": "강남역"}}

call_tool("get_population", {"district": "강남구"})
    → prefix: 없음 (fallback)
    → server: http://localhost:5100 (public_data)
    → POST /tools/call  {"name": "get_population", "arguments": {...}}
```

---

## 에이전트 상세

### 에이전트 목록 및 LLM 모델

| 에이전트 | 역할 | LLM 모델 | 실행 그룹 |
|---------|------|---------|----------|
| **Commander** | 전략 수립 & 최종 판단 | `claude-sonnet-4-6` | 순차 |
| **Population** | 인구/유동인구 분석 | `gemini-2.5-flash` | Group 1 (병렬) |
| **Competition** | 경쟁업체 분석 | `gemini-2.5-flash` | Group 1 (병렬) |
| **Revenue** | 매출 추정 | `gemini-2.5-flash` | Group 2 (병렬) |
| **Location** | 입지/교통 분석 | `gemini-2.5-flash` | Group 2 (병렬) |
| **Trend** | 시장 트렌드 분석 | `gemini-2.5-pro` | Group 3 (병렬) |
| **RealEstate** | 부동산 시세 분석 | `gemini-2.5-flash` | Group 3 (병렬) |
| **Regulatory** | 규제/인허가 분석 | `claude-sonnet-4-6` | Group 3 (병렬) |
| **Financial** | 재무 종합 분석 | `claude-sonnet-4-6` | 순차 |
| **Risk** | 리스크 평가 | `claude-sonnet-4-6` | 순차 |
| **Debate (Advocate)** | 찬성 논증 | `gemini-2.5-pro` | 조건부 |
| **Debate (Critic)** | 반박 논증 | `claude-sonnet-4-6` | 조건부 |
| **Debate (Judge)** | 최종 판결 | `claude-opus-4-6` | 조건부 |
| **Narrative** | 보고서 텍스트 생성 | `gemini-2.5-flash` | 순차 |
| **Visualization** | 차트/지도 설정 생성 | `gemini-2.5-flash` | 순차 |

### BaseAgent[T] 패턴

```
┌───────────────────────────────────────────┐
│             BaseAgent[T]                  │
│                                           │
│  Abstract Methods:                        │
│  ├─ execute(state) → T (Pydantic)        │
│  │                                        │
│  Concrete Methods:                        │
│  ├─ run(state) → dict    # 노드 진입점   │
│  ├─ call_llm()           # 재시도 포함     │
│  │   └─ max_retries=2, exponential backoff│
│  ├─ call_tool()          # MCP 라우팅     │
│  │   └─ timeout=30s                       │
│  ├─ call_tools_parallel()# 병렬 MCP 호출  │
│  │   └─ semaphore=5 concurrent            │
│  └─ calculate_confidence() → float       │
│      └─ 데이터 완성도(30%) + 신선도(25%)   │
│         + 소스 수(20%) + 교차검증(25%)     │
└───────────────────────────────────────────┘
```

---

## 기술 스택

```
┌─────────────────────────────────────────────────────────┐
│  Application Layer                                       │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐  │
│  │ FastAPI  │ │ LangGraph│ │ Pydantic │ │ LiteLLM    │  │
│  │ 0.115+  │ │ 0.2+     │ │ v2       │ │ (LLM 통합) │  │
│  └─────────┘ └──────────┘ └──────────┘ └────────────┘  │
├─────────────────────────────────────────────────────────┤
│  AI/LLM Layer                                           │
│  ┌──────────────────┐ ┌────────────────────┐            │
│  │ Claude (Anthropic)│ │ Gemini (Google)    │            │
│  │ sonnet/opus       │ │ flash/pro          │            │
│  └──────────────────┘ └────────────────────┘            │
├─────────────────────────────────────────────────────────┤
│  Data Layer                                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                │
│  │PostgreSQL│ │  Redis   │ │ MCP      │                │
│  │ + PostGIS│ │ (캐싱)   │ │ Protocol │                │
│  └──────────┘ └──────────┘ └──────────┘                │
├─────────────────────────────────────────────────────────┤
│  Monitoring Layer                                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                │
│  │Prometheus│ │ Langfuse │ │structlog │                │
│  │ (메트릭) │ │(LLM 추적)│ │ (로깅)   │                │
│  └──────────┘ └──────────┘ └──────────┘                │
├─────────────────────────────────────────────────────────┤
│  Infrastructure                                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                │
│  │  Docker  │ │ Docker   │ │  Python  │                │
│  │ Compose  │ │          │ │  3.11+   │                │
│  └──────────┘ └──────────┘ └──────────┘                │
└─────────────────────────────────────────────────────────┘
```

---

## 프로젝트 구조

```
marketscope/
├── app/
│   ├── main.py                  # FastAPI 앱 & lifespan
│   ├── config.py                # Settings (pydantic-settings)
│   ├── logging_config.py        # structlog 설정
│   │
│   ├── api/
│   │   └── routes/
│   │       ├── analysis.py      # POST/GET/SSE 분석 API
│   │       └── health.py        # 헬스체크 (live/ready/detailed)
│   │
│   ├── agents/                  # 에이전트 구현
│   │   ├── base.py              # BaseAgent[T] 추상 클래스
│   │   ├── commander.py         # 전략 수립 & 최종 판단
│   │   ├── population.py        # 인구 분석
│   │   ├── competition.py       # 경쟁 분석
│   │   ├── revenue.py           # 매출 추정
│   │   ├── location.py          # 입지 분석
│   │   ├── trend.py             # 트렌드 분석
│   │   ├── real_estate.py       # 부동산 분석
│   │   ├── regulatory.py        # 규제 분석
│   │   ├── financial.py         # 재무 종합
│   │   ├── risk.py              # 리스크 평가
│   │   ├── narrative.py         # 보고서 생성
│   │   ├── visualization.py     # 시각화 설정
│   │   └── debate/
│   │       ├── orchestrator.py  # Advocate→Critic→Judge
│   │       ├── advocate.py
│   │       ├── critic.py
│   │       └── judge.py
│   │
│   ├── graph/                   # LangGraph 워크플로우
│   │   ├── workflow.py          # DAG 빌드 (20 노드)
│   │   ├── nodes.py             # 노드 함수 + 싱글톤
│   │   └── edges.py             # 조건부 라우팅 함수
│   │
│   ├── tools/
│   │   └── mcp_client.py        # MCPClientRouter (prefix 라우팅)
│   │
│   ├── mcp_servers/             # 9개 MCP 서버
│   │   ├── public_data/         # KOSIS, 서울 Open API
│   │   ├── maps/                # 지오코딩
│   │   ├── real_estate/         # 부동산 데이터
│   │   ├── news/                # 뉴스/트렌드
│   │   ├── regulatory/          # 인허가/규제
│   │   ├── finance/             # 재무 계산 도구
│   │   ├── database/            # 공간 DB 쿼리
│   │   ├── google_maps/         # Google Maps API
│   │   └── naver_maps/          # Naver Maps API
│   │
│   ├── models/
│   │   └── state.py             # MarketScopeState TypedDict
│   │
│   ├── llm/
│   │   └── provider.py          # LiteLLM 래퍼
│   │
│   ├── db/                      # PostgreSQL 연결
│   ├── cache/                   # Redis 캐시 레이어
│   ├── memory/                  # LangGraph 체크포인트
│   └── monitoring/
│       ├── dag_tracer.py        # @trace_node 데코레이터
│       └── mcp_monitor.py       # MCP 호출 모니터링
│
├── tests/
│   ├── conftest.py              # 공통 fixture
│   ├── unit/
│   │   ├── test_agents.py       # BaseAgent 단위 테스트 (11)
│   │   ├── test_nodes.py        # 노드 함수 테스트 (11)
│   │   ├── test_edges.py        # 엣지 함수 테스트 (14)
│   │   ├── test_mcp_client.py   # MCPClientRouter 테스트 (13)
│   │   └── test_mcp_tools.py    # MCP 서버 도구 테스트 (14)
│   └── integration/
│       └── test_workflow.py     # 워크플로우 구조 테스트 (6)
│
├── docker-compose.yml           # 전체 서비스 오케스트레이션
├── Dockerfile                   # 앱 이미지
├── pyproject.toml               # 프로젝트 설정
└── .env                         # 환경 변수 (gitignore)
```

---

## Quick Start

### 사전 요구사항

- Python 3.11+
- Docker & Docker Compose
- API Keys: Anthropic, Google AI, (선택) Naver Maps

### 설치 및 실행

```bash
# 1. 저장소 클론
git clone <repository-url>
cd Catchment-Area-Analysis/marketscope

# 2. 환경 변수 설정
cp .env.example .env
# .env 파일에서 API 키 설정

# 3. Docker Compose로 전체 스택 실행
docker compose up -d

# 4. 상태 확인
curl http://localhost:8000/api/v1/health/ready
```

### 개발 환경

```bash
# 가상환경 생성 및 의존성 설치
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 테스트 실행
pytest tests/ -v

# 앱 단독 실행 (외부 서비스 필요)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## API 엔드포인트

### 분석 요청

```bash
# 분석 생성
curl -X POST http://localhost:8000/api/v1/analysis \
  -H "Content-Type: application/json" \
  -d '{"query": "강남역 카페 창업 분석", "depth": "standard"}'

# 응답 (202 Accepted)
{
  "request_id": "abc-123",
  "status": "queued",
  "stream_url": "/api/v1/analysis/abc-123/stream"
}
```

### SSE 실시간 스트림

```bash
# 진행 상황 실시간 수신
curl -N http://localhost:8000/api/v1/analysis/abc-123/stream

# SSE 이벤트 예시
data: {"type": "status", "phase": 0, "progress_pct": 2, "message": "입력 파싱 중"}
data: {"type": "status", "phase": 1, "progress_pct": 5, "message": "분석 전략 수립"}
data: {"type": "status", "phase": 3, "progress_pct": 25, "message": "Group 1 완료"}
data: {"type": "status", "phase": 6, "progress_pct": 100, "status": "completed"}
```

### 결과 조회

```bash
# 최종 리포트 조회
curl http://localhost:8000/api/v1/analysis/abc-123

# 응답 구조
{
  "final_report": {
    "report_id": "...",
    "overall_score": 72,
    "overall_grade": "B",
    "recommendation": "조건부 추천",
    "executive_summary": "...",
    "key_findings": [...],
    "population_result": {...},
    "revenue_result": {...},
    "narrative_report": "...",
    "visualization_config": {...}
  }
}
```

### 헬스체크

| 엔드포인트 | 용도 |
|-----------|------|
| `GET /api/v1/health` | 기본 상태 |
| `GET /api/v1/health/live` | K8s Liveness |
| `GET /api/v1/health/ready` | K8s Readiness (DB/Redis/MCP) |
| `GET /api/v1/health/detailed` | 전체 진단 |
| `GET /metrics` | Prometheus 메트릭 |

---

## 분석 모드

| 모드 | 실행 에이전트 | 예상 시간 | 설명 |
|------|-------------|----------|------|
| **quick** | Group 1 → Commander | ~60s | 인구+경쟁 기본 분석만 |
| **standard** | Group 1~3 → 전체 | ~180s | 7개 에이전트 + 디베이트 |
| **deep** | 전체 + 추가 검증 | ~420s | 심층 분석 + 강화 디베이트 |

---

## 모니터링

```
┌────────────────────────────────────────────────────────────┐
│                   Monitoring Stack                          │
│                                                            │
│  ┌──────────────────┐     ┌──────────────────────┐        │
│  │   @trace_node    │────▶│  DAG Tracer          │        │
│  │   (데코레이터)    │     │  - 노드별 실행 시간   │        │
│  └──────────────────┘     │  - 에러 추적          │        │
│                           │  - 재시도 횟수         │        │
│  ┌──────────────────┐     └──────────────────────┘        │
│  │ MCPMonitoring    │                                      │
│  │ Middleware       │     ┌──────────────────────┐        │
│  │  - MCP 호출 횟수  │────▶│  Prometheus /metrics │        │
│  │  - 응답 시간      │     │  - http_latency      │        │
│  │  - 에러율         │     │  - mcp_call_duration │        │
│  └──────────────────┘     │  - llm_tokens_used   │        │
│                           └──────────────────────┘        │
│  ┌──────────────────┐                                      │
│  │   Langfuse       │     ┌──────────────────────┐        │
│  │   Integration    │────▶│  LLM Trace Dashboard │        │
│  │  - 프롬프트 추적  │     │  - 토큰 사용량        │        │
│  │  - 비용 계산      │     │  - 모델별 레이턴시    │        │
│  │  - 품질 평가      │     │  - 비용 분석          │        │
│  └──────────────────┘     └──────────────────────┘        │
│                                                            │
│  ┌──────────────────┐                                      │
│  │   structlog      │     JSON 구조화 로깅                  │
│  │  - session_id    │     모든 로그에 컨텍스트 자동 포함     │
│  │  - node_id       │                                      │
│  │  - latency_ms    │                                      │
│  └──────────────────┘                                      │
└────────────────────────────────────────────────────────────┘
```

---

## 설계 문서

| 문서 | 설명 |
|------|------|
| `plan/spec/01_orchestration_langgraph.md` | LangGraph DAG 오케스트레이션 |
| `plan/spec/02_state_management.md` | State 관리 & 체크포인트 |
| `plan/spec/03_base_agent.md` | BaseAgent 프레임워크 |
| `plan/spec/04_mcp_client_router.md` | MCP 클라이언트 라우팅 |
| `plan/spec/05_llm_provider.md` | LLM Provider 추상화 |
| `plan/spec/06_monitoring.md` | 모니터링 & 추적 |
| `plan/spec/07_api_endpoints.md` | REST API 설계 |
| `plan/spec/08_debate_system.md` | 디베이트 시스템 |
| `plan/spec/09_mcp_servers.md` | MCP 서버 구현 |
| `plan/spec/10_error_recovery.md` | 에러 복구 전략 |
| `plan/spec/11_caching.md` | Redis 캐싱 전략 |

---

## 라이선스

Private - All rights reserved.
