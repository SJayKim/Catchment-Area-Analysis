# AGENTS.md — MarketScope AI (상권분석 AI 서비스)

## 프로젝트 개요

지도 기반 AI 챗봇으로 서울시 **1,650개 상권**을 분석하는 Freemium SaaS.
소상공인/부동산 투자자가 "지도에서 상권 선택 → AI가 분석/추천" 하는 서비스.

- **디렉토리별 가이드**: 프론트 작업은 [frontend/AGENTS.md](frontend/AGENTS.md), 백엔드/에이전트 작업은 [server/AGENTS.md](server/AGENTS.md) (Codex 가 작업 디렉토리별 자동 로드).
- **기술 스택 / 시스템 구성 상세**: @docs/architecture/overview.md

## 리포지토리 구조

```
Catchment-Area-Analysis/
├── frontend/       # Next.js 14 (src/app, components, stores, hooks, lib) → frontend/AGENTS.md
├── server/         # FastAPI (server/server/* 안에 실제 패키지) → server/AGENTS.md
├── data/           # SHP 폴리곤, seed 덤프
├── scripts/        # 운영 유틸 (deploy/, eval/, verify_sales_units, …)
├── deploy/systemd/ # 자동배포 systemd 유닛 (marketscope-autodeploy.{service,timer})
├── nginx/          # 내장 + 외부 리버스 프록시
├── docker-compose{,.prod,.e2e}.yml   # 개발 / 프로덕션 / E2E(:3001·:8002)
└── docs/           # 문서 (아래 문서 구조)
```

## 문서 구조

- `docs/architecture/` — 시스템 설계 (overview → backend/frontend/agent/data/deployment). **각 사실의 canonical source**.
- `docs/spec/` — 기능 스펙 (feature-list + F01~F13 · business/B01 · data/D01).
- `docs/ops/` — 운영 (quickstart · runbook · disaster-recovery · database-setup · production-deployment · serving-stability).
- `docs/plan/` — 진행 중/미래 계획만 (business/fix/infra/qa). 완료분은 git history.
- `docs/qa/` — test-plan + runs/ (최신 eval 만 유지).
- `docs/status/current-status.md` — **단일 마스터 상태** (미결/블로커 + Next Items).

## 핵심 불변식 (자주 틀리는 것)

- **매출 단위**: `estimated_sales.monthly_sales` = 서울 열린데이터 `THSMON_SELNG_AMT` = **분기 누적**. Repository 가 월 환산 후 응답. 유동인구 집계는 `quarter_total` ('일평균' 아님).
- **Mock/Real**: `USE_MOCK` 플래그. Mock 은 DB/Redis 없이 기동, **Agent 는 항상 PAE 폴백**(mock LLM tool-call 불가). Real 은 v2 loop.
- **SSE 포맷**: `event:` 라인 없이 `data: {json}` 안에 type 임베드 — 표준 SSE 파서 금지 ([frontend/AGENTS.md](frontend/AGENTS.md)).
- **env 관례 뒤집힘**: `.env`=prod, `.env.dev`=로컬. config.py/next.config.mjs/scripts 전부 `.env.dev` 우선 로드.

## 핵심 아키텍처 패턴

- **AI Agent**: **v2 agentic loop** (모델주도 function-calling, 스키마 12 = 도메인 9 + 메타 3 · budget governor 6턴/12툴/90s) 기본, Mock·롤백 시 legacy **PAE**(Planner-Actor-Evaluator) 그래프 폴백. 상세 @docs/architecture/agent.md
- **Trust Kernel**: 응답 수치를 tool 반환값에 ±5% 바인딩 검증 → 교정 1회 → 잔존 시 `[미확인]` 마스킹 / grounded fallback (anti-fabrication).
- **Mock/Real 전환**: `USE_MOCK` + Repository 패턴(`mock/`·`real/`). 캐싱 Redis TTL 24h + 메모리 fallback. Circuit Breaker 3-state.
- **지도-챗봇 연동**: Zustand 4 스토어(map/chat/district/toast) + `useMapSync` 훅. 공간쿼리 PostGIS `ST_Intersects` / `ST_AsGeoJSON`.

## 코딩 컨벤션

- TypeScript: strict, 2-space, ESLint + Prettier. Python: type hints 필수, ruff(lint+format), async/await 우선.
- API: RESTful, snake_case(Python) / camelCase(TS). DB: Alembic, 테이블명 복수형 snake_case.
- 컴포넌트: Tailwind + CSS 변수 기반 다크 테마.

## 개발 워크플로우

1. **스펙 확인**: [docs/spec/features/F##-*.md](docs/spec/features/) 먼저 읽기
2. **아키텍처 확인**: [docs/architecture/](docs/architecture/) 의 해당 레이어만 참조 (토큰 절감)
3. **계획 작성**: `docs/plan/<category>/` — `/plan-new <category> <name>` 스킬
4. **구현** → **상태 업데이트**: [current-status.md](docs/status/current-status.md) — `/status-update`
5. **spec 수용 기준 체크**: 기능 spec 의 체크박스를 실제 구현에 맞게 갱신

## Reflection Loop (프로젝트 로컬)

Global `~/.Codex/settings.json` 훅이 도구 실패 교훈을 auto memory 에 저장. 규칙:
- **새 Plan 작성 전** `memory/MEMORY.md` 를 grep → 관련 feedback(SSE, USE_MOCK, UTF-8 등)을 Plan **Context** 에 인용. 중복 저장 금지(파일명만 참조). `/plan-new` 가 자동화.

## Plan 필수 구조 (`docs/plan/**/*.md`)

1. Checklist(원자적·검증가능) · 2. 재검토(엣지/메모리교훈/타 Plan 충돌) · 3. Scenario(Ring 0~3, `<RING>-<FEATURE>-<CASE>`) · 4. Pass 반복(기본/엣지/성능) · 5. Agent 모델(설계 opus / 구현 sonnet / 검증 haiku)

## 하네스 명령어

- `/plan-new <category> <name>` · `/status-update "<요약>"` · `/e2e-run <ring>`(수동 호출만)
- Subagent: `code-reviewer` / `db-validator` / `qa-scenario-runner` — Agent 도구로 호출 (`.Codex/agents/` 실파일 기준)

## Health Stack

- typecheck `cd frontend && npx tsc --noEmit` · lint `cd frontend && npm run lint` ; `cd server && ruff check .` · test `cd server && pytest`
- CI `.github/workflows/ci.yml` — 5 잡: backend-lint(ruff) · frontend-lint(next lint + tsc) · backend-test(`pytest -m "not real"` + cov) · docker-build · security-audit. 자동배포가 이 check-runs green 게이트를 조회.

## 참고 문서 (@ 자동 로드)

- 전체 구조 요약: @docs/architecture/overview.md
- Agent 상세: @docs/architecture/agent.md
- 기능 목록: @docs/spec/feature-list.md
- 현재 상태: @docs/status/current-status.md
