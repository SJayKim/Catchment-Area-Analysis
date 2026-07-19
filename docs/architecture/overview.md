# Overview — MarketScope AI

> 시스템 전체 구조를 한 문서로 요약. 세부 레이어는 backend / frontend / agent / data / deployment 개별 문서 참조.

## 1. 서비스 개요

지도 기반 AI 챗봇으로 서울시 **1,650개 상권**을 분석하는 Freemium SaaS.
사용자가 지도에서 상권을 선택하면 AI가 공공데이터를 해석해 요약·비교·추천·리스크 분석을 제공한다.

## 2. 시스템 구성

```
┌──────────────────────────────────────────────────────────────┐
│  CLIENT (Next.js 14)                                         │
│  ┌──────────────────┬─────────────────────────────────────┐  │
│  │  Map Panel       │  Chat Panel                          │  │
│  │  (Kakao Map SDK) │  (SSE streaming + Rich Cards)        │  │
│  └──────────────────┴─────────────────────────────────────┘  │
└──────────────────────────┬───────────────────────────────────┘
                           │ REST + SSE (POST /api/chat)
                           ▼
┌──────────────────────────────────────────────────────────────┐
│  API SERVER (FastAPI, Python 3.12)                           │
│  ├─ /api/chat      SSE agent streaming                       │
│  ├─ /api/districts 검색/상세                                   │
│  └─ /api/map-data  폴리곤 / 히트맵                             │
└─────────┬────────────────────────────────┬───────────────────┘
          │                                │
          ▼                                ▼
┌──────────────────────┐        ┌──────────────────────────────┐
│  AI Agent (v2 loop)  │        │  Data Layer                  │
│  model-driven        │─tool──▶│  PostgreSQL 16 + PostGIS     │
│  function-calling    │        │  Redis 7 (cache, TTL 24h)    │
│  + Trust Kernel      │        │  SQLAlchemy async repos      │
└──────────────────────┘        └──────────────────────────────┘
```

> Agent 기본 경로는 **v2 agentic loop**(모델주도 function-calling + Trust Kernel, `agent/loop/`).
> LLM 은 단일 tool-calling 모델 preferred-first fallback chain(`claude-sonnet-4-6` → `gpt-5.4-mini` → `gemini-2.5-pro` → `gemini-2.5-flash`, `LLM_PROVIDER` 가 선호 프로바이더를 맨 앞으로 승격)으로 호출한다.
> 레거시 **PAE(Planner-Actor-Evaluator) 그래프**(`agent/graph.py`)는 Mock 모드 · `AGENT_LOOP_VERSION=pae` 롤백용 폴백으로 유지.

## 3. 기술 스택 (요약)

| 레이어 | 기술 | 버전 |
|---|---|---|
| Frontend | Next.js App Router, TypeScript | 14.2 / TS 5 |
| Map | Kakao Map SDK + deck.gl | deck.gl 9.2 |
| Chat UI | React + shadcn-style + Tailwind | React 18.3 |
| Charts | Recharts | 2.15 |
| PDF | @react-pdf/renderer + html2canvas | 4.3 / 1.4 |
| State | Zustand | 5.0 |
| API | FastAPI (slowapi 는 config 정의만 — 라우트 실적용 미결) | 0.115 |
| Agent | v2 agentic loop (자체 구현 function-calling + Trust Kernel, `agent/loop/`) / 레거시 PAE = LangGraph | — / 0.2 |
| LLM | preferred-first fallback chain: `claude-sonnet-4-6` → `gpt-5.4-mini` → `gemini-2.5-pro` → `gemini-2.5-flash` (v2 는 단일 tool-calling 모델 — 역할별 분리는 레거시 PAE 전용) | — |
| DB | PostgreSQL + PostGIS | 16 / 3.4 |
| Cache | Redis | 7 |
| Container | Docker Compose | — |

## 4. 핵심 아키텍처 원칙

- **Mock/Real 전환**: `USE_MOCK` 플래그. Mock은 DB/Redis 없이 FastAPI 단독 기동 (JSON fixture).
- **Repository 패턴**: `repositories/protocols.py` 에 10개 인터페이스 정의 → `mock/` · `real/` 두 구현체.
- **Tool Registry**: Agent Tool 9종이 `@register_tool` 데코레이터로 자체 등록 (`agent/tools/registry.py`).
- **v2 agentic loop (기본 경로)**: `agent/runtime.py` 가 `agent_loop_version == "v2"` 이고 `llm_provider != "mock"` 이면 모델주도 function-calling 루프(`agent/loop/engine.py`)로 디스패치. budget governor(모델 턴 6 / tool call 12 / wall-clock 90s)가 종결을 보장하고, LLM 은 per-invoke preferred-first fallback chain(anthropic → openai → gemini pro → flash, `LLM_PROVIDER` 가 선호 프로바이더를 맨 앞으로 승격)으로 호출. 최종 턴은 astream 버퍼링 + `thinking` 진행 이벤트("응답 작성 중 n%", 옵션 B — 롤백 `AGENT_LOOP_STREAM_FINAL=false`)로 수신.
- **Trust Kernel**: 최종 답변의 모든 수치를 도구 반환값(또는 compute 파생값)에 ±5%(`trust_numeric_tolerance=0.05`) 이내로 바인딩 검사(`agent/loop/trust.py`) — unbound/스케일 오기(×10/×100) 검출 → prose 전용 교정 패스 → 잔존 시 `[미확인]` 마스킹 또는 결정론적 grounded_fallback (카드 발행 시 abstention 금지).
- **PAE 레거시 폴백**: Planner-Actor-Evaluator 그래프(`agent/graph.py`)는 Mock 모드 및 `AGENT_LOOP_VERSION=pae` 롤백 스위치용으로 유지 — mock 의 FakeListChatModel 은 tool-call 불가라 Mock E2E 는 항상 PAE 로 돈다.
- **SSE 스트리밍**: v2 루프는 thinking / tool / tool_end / card / text / suggestion / done **7종** 방출. `plan` · `warning` 은 레거시 PAE 전용, `map_cmd` 와 greeting 단축 응답은 `api/routes/chat.py` 가 에이전트 밖에서 방출 (프론트 `SSEEvent` 유니온은 `error` 포함 10종).
- **Map–Chat 양방향 동기화**: Zustand 4 store (chat/district/map/toast) + `useMapSync` 훅.
- **Circuit Breaker + Singleflight**: LLM/DB 장애 시 degraded 동작, 캐시 미스 시 중복 호출 방지.
- **요청/세션 격리**: per-request 에이전트 실행 + 인메모리 세션 저장소 (세션당 메모리 512KB 상한).

## 5. 레이어별 상세 문서

| 문서 | 다루는 범위 |
|---|---|
| [backend.md](backend.md) | FastAPI 앱 구성, API 라우트, 서비스(cache/circuit_breaker/category_resolver), 미들웨어, 에러 규약 |
| [frontend.md](frontend.md) | App Router, 레이아웃·맵·챗 컴포넌트, Zustand 스토어, 훅, SSE 파서 |
| [agent.md](agent.md) | Agent 런타임 — v2 agentic loop + Trust Kernel (레거시 PAE 그래프 폴백), Tool 9종, 프롬프트 구조, 세션 히스토리 |
| [data.md](data.md) | DB 스키마, PostGIS 인덱스, Alembic 마이그레이션, ETL 파이프라인, 캐시 키 규약 |
| [deployment.md](deployment.md) | Docker Compose (dev / prod), Nginx 리버스프록시, 환경변수, 운영 플래그 |

## 6. 개발 Phase 요약

| Phase | 범위 | 상태 |
|---|---|---|
| 1A — Mock E2E | 지도·챗봇·Card UI + Mock fixtures | ✅ 완료 |
| 1B — Real Data | 공공데이터 ETL + 1,650개 상권 적재 | ✅ 완료 |
| 3 — 확장 | 히트맵 · 매출 시뮬레이션 · PDF 리포트 | ✅ 완료 |
| 2 — Premium | OAuth2 · 결제 · Tier 게이팅 · 업종 심층 | ⏳ 진행 전 |
| Prod | marketscope.robitlabs.co.kr 라이브 | ✅ 완료 |

> Phase 2 상용화 로드맵은 [plan/business/commercialization-plan.md](../plan/business/commercialization-plan.md) 참조.

## 7. 현재 서비스 지표

- Mock 상권: 5개 (강남역 / 홍대 / 건대 / 명동 / 서울역)
- Real 상권: 1,650개 (서울 전체)
- ETL 적재: floating_population 9,888 / estimated_sales 21,333 / stores 75,985 / resident_population 39,288 (2025Q4 기준)
- Agent Tool: 9종 (등록 기준; `get_district_benchmarks` 는 내부 헬퍼) / Card 타입: 5종 / SSE 이벤트: v2 루프 7종 방출 + chat.py `map_cmd` (레거시 PAE 는 `plan`·`warning` 포함 9종, 프론트 `SSEEvent` 유니온은 `error` 포함 10종)
- E2E (Playwright): spec **44파일 · test 선언 188개** (ring0~3 = 42파일·165선언, prod-smoke 1파일·11선언(active 9 + skip 2), 레거시 루트 phase3-scenario 1파일·12선언 — 2026-07-16 실측, skip 선언 포함). 실행 케이스 수는 project 4종 곱·런타임 skip 으로 가변 — 최근 실측 2026-07-02 Mock 전체: 131 passed / 25 failed(loop 무관 사전결함) / 8 skip. UX Sweep 회귀 매트릭스 43 시나리오는 [`plan/qa/ux-final-e2e-regression-plan.md`](../plan/qa/ux-final-e2e-regression-plan.md) 참조
