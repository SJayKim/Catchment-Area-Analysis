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
│  AI Agent (LangGraph)│        │  Data Layer                  │
│  Planner→Actor→      │─tool──▶│  PostgreSQL 16 + PostGIS     │
│  Evaluator→Respond   │        │  Redis 7 (cache, TTL 24h)    │
│  LLM: Claude/Gemini  │        │  SQLAlchemy async repos      │
└──────────────────────┘        └──────────────────────────────┘
```

## 3. 기술 스택 (요약)

| 레이어 | 기술 | 버전 |
|---|---|---|
| Frontend | Next.js App Router, TypeScript | 14.2 / TS 5 |
| Map | Kakao Map SDK + deck.gl | deck.gl 9.2 |
| Chat UI | React + shadcn-style + Tailwind | React 18.3 |
| Charts | Recharts | 2.15 |
| PDF | @react-pdf/renderer + html2canvas | 4.3 / 1.4 |
| State | Zustand | 5.0 |
| API | FastAPI + slowapi rate-limit | 0.115 |
| Agent | LangGraph (custom PAE graph) | 0.2 |
| LLM | Claude Sonnet 4 (planner) / Gemini 2.5 (role-based) | — |
| DB | PostgreSQL + PostGIS | 16 / 3.4 |
| Cache | Redis | 7 |
| Container | Docker Compose | — |

## 4. 핵심 아키텍처 원칙

- **Mock/Real 전환**: `USE_MOCK` 플래그. Mock은 DB/Redis 없이 FastAPI 단독 기동 (JSON fixture).
- **Repository 패턴**: `repositories/protocols.py` 에 9개 인터페이스 정의 → `mock/` · `real/` 두 구현체.
- **Tool Registry**: Agent Tool 11종이 `@register_tool` 데코레이터로 자체 등록 (`agent/tools/registry.py`).
- **SSE 스트리밍**: thinking → plan → tool → tool_end → card → text → suggestion → done 순차 이벤트.
- **Map–Chat 양방향 동기화**: Zustand 3 store (chat/district/map) + `useMapSync` 훅.
- **Circuit Breaker + Singleflight**: LLM/DB 장애 시 degraded 동작, 캐시 미스 시 중복 호출 방지.
- **Per-request agent graph (PAE)**: 세션 단위 상태 격리, 메모리 512KB 상한.

## 5. 레이어별 상세 문서

| 문서 | 다루는 범위 |
|---|---|
| [backend.md](backend.md) | FastAPI 앱 구성, API 라우트, 서비스(cache/circuit_breaker/category_resolver), 미들웨어, 에러 규약 |
| [frontend.md](frontend.md) | App Router, 레이아웃·맵·챗 컴포넌트, Zustand 스토어, 훅, SSE 파서 |
| [agent.md](agent.md) | Planner-Actor-Evaluator 그래프, Tool 11종, 프롬프트 구조, 세션 히스토리 |
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
- Agent Tool: 11종 / Card 타입: 5종 / SSE 이벤트: 9종
- E2E: Ring 0~3 총 45 시나리오 + 최신 회귀 15 시나리오
