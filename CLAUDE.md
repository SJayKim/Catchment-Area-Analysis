# CLAUDE.md — MarketScope AI (상권분석 AI 서비스)

## 프로젝트 개요

지도 기반 AI 챗봇으로 서울시 **1,650개 상권**을 분석하는 Freemium SaaS.
소상공인/부동산 투자자가 "지도에서 상권 선택 → AI가 분석/추천" 하는 서비스.

## 기술 스택

| 레이어 | 기술 |
|--------|------|
| Frontend | Next.js 14 (App Router, TypeScript), Kakao Map SDK, deck.gl, Recharts, Zustand, Tailwind |
| Backend | FastAPI (Python 3.12, async), v2 agentic loop (function-calling + Trust Kernel; LangGraph PAE 는 legacy 폴백), Claude/Gemini API |
| Database | PostgreSQL 16 + PostGIS, Redis 7 |
| Infra | Docker Compose (dev + prod + e2e), 외부 Nginx (프로덕션), 자동배포 (systemd timer 폴링) |
| Observability | Langfuse (L1 trace wiring 적용, graceful degrade) |

## 리포지토리 구조

```
Catchment-Area-Analysis/
├── frontend/                # Next.js 14 (src/app, components, stores, hooks, lib)
├── server/                  # FastAPI (server/server/* 안에 실제 패키지)
│   ├── server/
│   │   ├── main.py         # FastAPI 앱 + lifespan
│   │   ├── config.py       # pydantic-settings
│   │   ├── api/            # routes, middleware, rate_limiter, errors
│   │   ├── agent/          # loop/ (v2 엔진 + Trust Kernel) + graph.py (PAE legacy), nodes, tools, prompts
│   │   ├── data/etl/       # 공공데이터 수집
│   │   ├── repositories/   # mock/, real/ 분리 + protocols.py
│   │   ├── models/         # SQLAlchemy
│   │   └── services/       # cache, circuit_breaker, category_resolver, langfuse_tracer
│   ├── alembic/            # 001~005 마이그레이션
│   └── tests/              # backend pytest (테스트 모듈 22개)
├── data/                    # SHP 폴리곤, seed 덤프
├── scripts/                 # 운영 유틸 (verify_sales_units, validate_env, setup_db, deploy/, eval/, …)
├── deploy/systemd/          # 자동배포 systemd 유닛 (marketscope-autodeploy.{service,timer})
├── nginx/                   # 내장 + 외부 리버스 프록시 설정
├── docker-compose.yml       # 개발
├── docker-compose.prod.yml  # 프로덕션
├── docker-compose.e2e.yml   # E2E 전용 스택 (:3001/:8002)
└── docs/                    # 아래 참조
```

## 문서 구조 (토큰 효율 위해 계층화)

```
docs/
├── README.md                        # 문서 전체 네비게이션
├── architecture/                    # 계층 1: 시스템 설계
│   ├── overview.md                 # 전체 요약 (먼저 읽기)
│   ├── backend.md                  # FastAPI / API / 서비스
│   ├── frontend.md                 # Next.js / Zustand / SSE 파서
│   ├── agent.md                    # Agent (v2 loop + Trust Kernel · PAE legacy) / Tool 9종
│   ├── data.md                     # DB 스키마 / 레포 / ETL / 캐시
│   └── deployment.md               # Docker / Nginx / 환경변수
├── spec/                            # 계층 2: 기능 스펙
│   ├── feature-list.md             # 인덱스
│   ├── features/F01~F13-*.md       # 기능 상세
│   ├── business/B01-business-model.md
│   └── data/D01-data-pipeline.md
├── ops/                             # 운영
│   ├── quickstart.md
│   ├── runbook.md
│   ├── disaster-recovery.md
│   ├── database-setup.md
│   ├── production-deployment.md
│   └── serving-stability.md
├── plan/                            # 진행 중 / 미래 계획만
│   ├── business/                   # commercialization-plan.md
│   ├── fix/                        # 버그 / 정확도 hotfix
│   ├── infra/                      # 배포 / 안정성 / refactoring
│   ├── qa/                         # QA sweep + UX 회귀 (ux-final-e2e 등)
│   └── ui/                         # UX Sweep phase 묶음 (a/b/c/d/e/f)
├── qa/
│   ├── test-plan.md                # E2E 4-ring 플랜
│   └── runs/                       # 최근 실행 로그
└── status/
    └── current-status.md           # 단일 마스터 상태
```

## 빌드 & 실행

```bash
# 1) 개발 환경 기동 (DB + Redis + Backend + Frontend + Nginx)
docker compose up -d

# 2) 로컬 개발 (호스트에서 직접 실행, DB/Redis 만 컨테이너)
docker compose up -d db redis

# Frontend
cd frontend && npm install && npm run dev        # port 3000

# Backend
cd server && pip install -e ".[dev]"
uvicorn server.main:app --reload --port 8000

# 테스트
cd frontend && npm run test:e2e                   # Playwright E2E (`npm test` 스크립트 없음)
cd server && pytest                               # backend pytest (모듈 22개, CI 상시 게이트)

# 린트/포맷
npx prettier --write .                            # TypeScript
cd server && ruff check --fix . && ruff format .  # Python
```

> Mock 모드(USE_MOCK=true)는 DB/Redis 없이 FastAPI + Next.js 단독 기동 가능.
> Mock 모드의 Agent 는 항상 PAE 폴백 (mock LLM 은 tool-call 불가).
> 실제 데이터로 실행하려면 [ops/quickstart.md](docs/ops/quickstart.md) 참조.

## 개발 Phase

- **Phase 1A — Mock E2E** ✅ 완료. 5개 샘플 상권으로 전체 흐름 검증.
- **Phase 1B — Real Data** ✅ 완료. 1,650개 상권 ETL + PAE 전환 + 프로덕션 배포.
- **Phase 3 — 확장** ✅ 완료. F06 히트맵, F09 매출 시뮬레이션, F10 PDF.
- **v2 Agent 전환** ✅ 완료 (2026-07-03 main 머지). 모델주도 loop + Trust Kernel 기본, PAE 는 legacy 폴백.
- **Phase 2 — Premium** ⏳ 미착수. OAuth2, 결제, Tier 게이팅, F04 업종 심층.

## 핵심 아키텍처 패턴

- **AI Agent**: **v2 agentic loop** — 모델 주도 function-calling (도구 스키마 12개 = 도메인 9 + 메타 3: resolve_district/compute/abstain) + budget governor (모델 턴 6 / tool 12회 / 90s). `agent_loop_version="v2"` 기본, Mock 모드·롤백 시 legacy LangGraph **PAE**(Planner-Actor-Evaluator, max 3 rounds) 그래프 폴백
- **Trust Kernel**: 응답의 모든 수치를 tool 반환값에 ±5% 바인딩 검증 — 교정 패스 1회 → 잔존 시 `[미확인]` 마스킹 / grounded fallback (anti-fabrication)
- **통신**: FastAPI → SSE 스트리밍 — v2 는 thinking/tool/tool_end/card/text/suggestion/done 7종, `plan`·`warning` 은 PAE 전용, `map_cmd`·greeting 단축은 chat.py 가 방출
- **지도-챗봇 연동**: Zustand 4 스토어(map/chat/district/toast) + `useMapSync` 훅
- **공간 쿼리**: PostGIS `ST_Intersects`, `ST_AsGeoJSON`
- **Mock/Real 전환**: `USE_MOCK` 플래그 + Repository 패턴 (`mock/` · `real/`)
- **캐싱**: Redis (TTL 24h) + 메모리 fallback (graceful degradation)
- **Circuit Breaker**: LLM 호출 3-state 격리 (CLOSED → OPEN → HALF_OPEN)

## 코딩 컨벤션

- TypeScript: strict mode, 2-space indent, ESLint + Prettier
- Python: type hints 필수, ruff (lint + format), async/await 우선
- API: RESTful, snake_case (Python), camelCase (TypeScript)
- DB: Alembic 마이그레이션, 테이블명 복수형 snake_case
- 컴포넌트: Tailwind + CSS 변수 기반 다크 테마

## 주요 DB 테이블

districts · floating_population · estimated_sales · stores · store_history · resident_population · category_metadata · learned_aliases · chat_sessions · chat_messages (세션은 인메모리 사용)

> ⚠ `estimated_sales.monthly_sales` 컬럼은 서울 열린데이터 `THSMON_SELNG_AMT` = **분기 누적**. Repository 에서 월 환산 후 응답.

## 데이터 소스

- **서울 열린데이터** (data.seoul.go.kr): SHP 폴리곤, 유동인구, 추정매출, 점포, 직장·상주인구
- **공공데이터포털** (data.go.kr): 점포 이력 (미연동, Phase 2)

## 개발 워크플로우

1. **스펙 확인**: 기능 관련 [docs/spec/features/F##-*.md](docs/spec/features/) 먼저 읽기
2. **아키텍처 확인**: 필요 시 [docs/architecture/](docs/architecture/) 의 해당 레이어만 참조 (토큰 절감)
3. **계획 작성**: 구현 계획을 `docs/plan/<category>/` 에 작성 — `/plan-new <category> <name>` 스킬
4. **구현**: 스펙과 계획대로 작성
5. **상태 업데이트**: [docs/status/current-status.md](docs/status/current-status.md) 갱신 — `/status-update "<요약>"`
6. **spec 수용 기준 체크**: 기능 spec 의 체크박스를 실제 구현에 맞게 갱신

## Reflection Loop (프로젝트 로컬)

Global `~/.claude/settings.json` 의 `PostToolUseFailure` + `Stop` 훅이 도구 실패 시 교훈을 auto memory 에 저장. 프로젝트 규칙:

- **새 Plan 작성 전** `memory/MEMORY.md` 를 grep 해 관련 키워드(SSE, USE_MOCK, UTF-8, korean-particle, asyncpg-batch 등) 매칭되는 feedback 파일을 Plan **Context** 섹션에 인용할 것
- 중복 저장 금지 — 기존 memory 와 겹치면 파일명만 참조
- `/plan-new` 스킬이 Memory 참조를 자동화

## Plan 필수 구조 (`docs/plan/**/*.md`)

1. **Checklist** — 원자적이고 검증 가능한 항목
2. **재검토 (Self-Review Gate)** — 엣지케이스 / 메모리교훈 / 타 Plan 충돌
3. **Scenario (E2E Ring Mapping)** — Ring 0~3 매핑, `<RING>-<FEATURE>-<CASE>`
4. **Pass 반복** — Pass 1(기본) / Pass 2(엣지) / Pass 3(성능). Fail → 수정 → 재실행
5. **Agent 모델 선택** — 설계 opus / 구현 sonnet / 검증 haiku

## 하네스 명령어

- `/plan-new <category> <name>` — 표준 5섹션 Plan 템플릿
- `/status-update "<요약>"` — 오늘 날짜 진행 기록 추가
- `/e2e-run <ring>` — USE_MOCK preflight 포함 E2E 실행 (수동 호출만)
- Subagent: `code-reviewer` / `db-validator` / `qa-scenario-runner` — Agent 도구로 호출 (`.claude/agents/` 실파일 기준)

## 참고 문서

- 전체 구조 요약: @docs/architecture/overview.md
- 백엔드 상세: @docs/architecture/backend.md
- 프론트 상세: @docs/architecture/frontend.md
- Agent 상세: @docs/architecture/agent.md
- 기능 목록: @docs/spec/feature-list.md
- 현재 상태: @docs/status/current-status.md

## Health Stack

- typecheck: cd frontend && npx tsc --noEmit
- lint: cd frontend && npm run lint ; cd server && ruff check .
- test: cd server && pytest
- CI: `.github/workflows/ci.yml` — push/PR(main) 5 잡: backend-lint(ruff) · frontend-lint(next lint + tsc) · backend-test(`pytest -m "not real"` + cov) · docker-build · security-audit. 자동배포 CI green 게이트가 이 check-runs 를 조회.
