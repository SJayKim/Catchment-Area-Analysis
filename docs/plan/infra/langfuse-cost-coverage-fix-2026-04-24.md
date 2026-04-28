# Langfuse Cost Coverage Fix (2026-04-24)

## Context
- **배경**: Anthropic 대시보드 비용과 Langfuse 대시보드 비용 간 큰 갭 확인. 전수 점검 결과 dev 컨테이너의 Langfuse SDK 버전 드리프트로 **dev 환경 LLM 호출 전량이 Langfuse 에 미집계**.
- **핵심 증거**:
  - `catchment-area-analysis-backend-1` 컨테이너: `langfuse==2.60.10` (pyproject 은 `langfuse>=3,<4`). `from langfuse.langchain import CallbackHandler` → `ModuleNotFoundError`.
  - `langfuse_tracer.py:178-183` 이 ImportError 잡아 `_tracer_valid=False` 로 고정 → `get_langfuse_handler()` 이후 100% `None` 반환.
  - `docker logs` 최근 300줄 `agent_done` 기록 100%가 `trace_id=-`.
  - Prod (`marketscope.robitlabs.co.kr`) 는 정상 (실 trace_id `89ab12176a…` 발행 확인).
- **누락 범위 (dev, 2026-04-24 하루)**:
  - E2E Quality Sweep Pass 1+2 = 214회
  - Trust regression = 30회
  - Accuracy eval Round 2 S1~S8 = 8회+
  - 로컬 개발/수동 chat = 상당수
  → 전량 Anthropic 에 과금되지만 Langfuse cost 0.
- **Memory 참조**:
  - [feedback_langfuse_v2_langchain1_incompatible.md](../../../../.claude/projects/C--Users-cyon1-OneDrive-Desktop-Catchment-Area-Analysis/memory/feedback_langfuse_v2_langchain1_incompatible.md) — v2↔langchain 1.x 비호환, v3 + create_trace_id pre-assign 필수
  - [feedback_otlp_http_cert_override.md](../../../../.claude/projects/C--Users-cyon1-OneDrive-Desktop-Catchment-Area-Analysis/memory/feedback_otlp_http_cert_override.md) — MITM 환경 시 `_certificate_file=False` 추가 필요
  - [feedback_env_convention_inverted.md](../../../../.claude/projects/C--Users-cyon1-OneDrive-Desktop-Catchment-Area-Analysis/memory/feedback_env_convention_inverted.md) — `.env`=prod, `.env.dev`=dev 관례

## Scope
- **In Scope**:
  - Dev 컨테이너 langfuse v3 재설치 + 재시작 후 trace_id 발행 검증
  - `server/Dockerfile` 에서 v3 강제 (사실상 pyproject 이미 pin 돼 있으나 stale layer 캐시 회피 명시)
  - `scripts/eval/run_quality_sweep.py` / `scripts/eval/trust_scenarios.py` 에 `--require-trace` 가드 추가 (done.trace_id 없으면 즉시 실패)
  - Langfuse Cloud Models 페이지 점검 체크리스트 문서화 (UI 작업은 사용자가 수행)
  - 회귀 방지: `scripts/validate_env.py` 에 langfuse SDK import path 자가 점검 추가
- **Out of Scope**:
  - Prod 재배포 (prod 는 이미 정상 작동, 재배포 불필요)
  - Retry 별 generation 분리 기록 (기존 1회 span 으로 충분 판단, 실 영향 미미)
  - Langfuse self-host 전환

## Design
- **접근 방식**:
  1. 컨테이너 수동 복구 — `docker exec … pip install --upgrade 'langfuse>=3,<4'` 로 즉시 SDK 상향 후 재시작. Dockerfile 은 이미 `pyproject.toml` 에서 pin 하고 있어 다음 `docker compose build backend` 가 정상 v3 이미지 생성. (status 2026-04-23 메모: "pypi SSL 실패 → docker cp + 컨테이너 내 pip install 우회" — 즉 이미지 재빌드 없이 수동 설치된 dev 상태가 stale 의 원인)
  2. 설치 검증 — `from langfuse.langchain import CallbackHandler`, `from langfuse.types import TraceContext` 임포트 sanity 후 `/api/chat` 실호출로 `done.trace_id` 존재 확인.
  3. 자동 가드 — eval harness 는 trace_id 검증 실패 시 abort. `validate_env.py` 가 startup 시 SDK 경로 점검 경고.
- **변경 파일**:
  - `server/Dockerfile`: v3 강제용 comment (현 pin 확인), 별도 COPY 없음
  - `scripts/eval/run_quality_sweep.py`: `--require-trace` CLI 플래그 + done.trace_id 누락 시 fail-fast
  - `scripts/eval/trust_scenarios.py`: 동일 가드
  - `scripts/validate_env.py`: langfuse SDK v3 import 점검 섹션 추가
  - `docs/ops/runbook.md` (없으면 신규 항목): Langfuse Cloud Models 등록 체크리스트
  - `docs/status/current-status.md`: 기록 추가
- **의존성 / 선행 Plan**:
  - [llmops-l1-verification.md](llmops-l1-verification.md) — SDK v2→v3 포팅 원본 (이미 완료됐으나 이미지 재빌드 누락으로 재발)

## Checklist
- [ ] Phase 1 — Dev 컨테이너 SDK 수동 복구
  - [ ] `docker exec catchment-area-analysis-backend-1 pip install --upgrade 'langfuse>=3,<4'`
  - [ ] `docker compose restart backend`
  - [ ] import sanity: `from langfuse.langchain import CallbackHandler` / `from langfuse.types import TraceContext` 둘 다 OK
  - [ ] `curl /api/chat` 로 분석 호출 1회 → `done.trace_id` 존재 확인
  - [ ] 백엔드 로그 `agent_done` 라인에 실 trace_id 기록 확인
- [ ] Phase 2 — 이미지 재빌드 + 재현성 확보
  - [ ] `docker compose build backend` (Dockerfile pin 반영 확인)
  - [ ] 재빌드 이미지 내 `pip show langfuse` → `Version: 3.x`
  - [ ] `docker compose up -d backend` → 재시작 후 trace_id 재검증
- [ ] Phase 3 — 자동 가드
  - [ ] `scripts/eval/run_quality_sweep.py` `--require-trace` 추가 (기본 on 권장)
  - [ ] `scripts/eval/trust_scenarios.py` 동일 가드 추가
  - [ ] `scripts/validate_env.py` langfuse SDK 경로 점검 섹션 추가
  - [ ] Dry-run: trace_id 없는 응답 fixture 로 harness abort 동작 확인
- [ ] Phase 4 — 문서/운영
  - [ ] Langfuse Cloud Models 등록 체크리스트 `docs/ops/` 추가 (`claude-sonnet-4-20250514`, `gemini-2.5-pro`, `gemini-2.5-flash`)
  - [ ] `docs/status/current-status.md` 에 본 Plan 결과 요약 추가

## 재검토 (Self-Review Gate)
- [x] 엣지 케이스
  - [x] pip SSL 실패 환경 (status 2026-04-23 메모의 MITM) — `pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org` 폴백 권장. Plan 본문 Phase 1 코멘트.
  - [x] Langfuse Cloud 의 `LANGFUSE_OTEL_INSECURE=true` 설정 유지 필요 (dev MITM) — 재빌드 후에도 env 그대로 → 회귀 없음.
  - [x] prod 는 건드리지 않음 — dev 만 수정.
- [x] Memory 교훈 반영
  - [x] `feedback_langfuse_v2_langchain1_incompatible.md` — v3 고정 확인
  - [x] `feedback_otlp_http_cert_override.md` — `_session.verify=False` + `_certificate_file=False` 둘 다 이미 `_disable_otel_tls_verify()` 에 구현돼 있음. 회귀 방지 위해 Phase 2 후 1회 span export 확인.
  - [x] `feedback_env_convention_inverted.md` — dev 는 `.env.dev` 로드 (compose 에서 env 패스스루). 재빌드 시 env 파일 관례 건드리지 않음.
- [x] 타 Plan 충돌
  - [x] `llmops-l1-verification.md` 의 후속으로 동작. 충돌 없음.
  - [x] 2026-04-24 `accuracy-gap-eval-round2` / `e2e-quality-improvement` 의 harness 에 가드 추가 — 회귀 없도록 기존 동작 preserve.

## Scenario (E2E Ring Mapping)
- **Ring**: 0 (infra sanity). Langfuse tracing 은 SSE 스트림 규약 외부 관측 레이어.
- **Scenario ID**: `R0-LF-TRACE-DEV` / `R0-LF-TRACE-EVAL-GUARD`
- **사전조건**: dev stack 기동 (`docker compose up -d`), `.env.dev` 에 LANGFUSE_* 5개 세팅됨
- **실행 단계**:
  1. `R0-LF-TRACE-DEV`: pip 업그레이드 → `curl -X POST /api/chat` 분석 쿼리 → `done.trace_id` grep
  2. `R0-LF-TRACE-EVAL-GUARD`: `trace_id` 빈 응답 mock 을 harness 에 주입 → exit code != 0 확인
- **기대 결과**:
  - R0-LF-TRACE-DEV: trace_id 16~64자 hex, backend 로그 `agent_done` 라인에도 동일 값
  - R0-LF-TRACE-EVAL-GUARD: harness 즉시 종료 + stderr "trace_id missing" 메시지

## Pass 반복 (Iteration Plan)
- **Pass 1** (기본 구현):
  - Phase 1 수동 복구 + Phase 3 harness 가드 추가
  - `/api/chat` 1회 smoke → trace_id 존재
- **Pass 2** (엣지):
  - Phase 2 이미지 재빌드
  - trust_scenarios 1 세션 실행 → 모든 응답 trace_id 존재
  - Langfuse Cloud UI 에서 실 trace 열람 확인
- **Pass 3** (회귀):
  - `compose down && compose up -d --build backend` → 재빌드 이미지로 다시 기동
  - `pip show langfuse` → 3.x
  - quality sweep 10 시나리오 샘플 돌려서 trace_id 100% 확인

## Agent 모델 선택
- **설계**: opus (SDK 드리프트 근본원인 + eval harness 재설계 포함)
- **구현**: sonnet (명확한 CLI 가드/pip 명령 적용)
- **검증**: haiku (trace_id grep 1건 확인)
- **근거**: Phase 1 은 단순 pip/docker. Phase 3 의 guard 는 기존 harness 구조 파악 필요 (opus 가 유리). 실행은 sonnet, 확인은 haiku.

## Validation
- **수동 검증**:
  1. `docker exec catchment-area-analysis-backend-1 python -c "from langfuse.langchain import CallbackHandler; print('ok')"`
  2. `curl -s -X POST http://localhost:8002/api/chat -H "Content-Type: application/json" -d '{"message":"강남역 요약"}' | grep trace_id`
  3. `docker logs catchment-area-analysis-backend-1 --tail 20 | grep agent_done` → trace_id 실 값
  4. Langfuse Cloud UI (`https://cloud.langfuse.com`) 에서 발행된 trace_id 열람
- **자동 검증**:
  - `scripts/validate_env.py` startup 시 SDK import 점검 passing
  - `scripts/eval/run_quality_sweep.py --require-trace --limit 3` exit 0

## Metadata
- 작성일: 2026-04-24
- 작성자: Claude Code (plan-new skill)
