# Refactoring Phase 1 — 저위험/중위험 일괄 정리 (2026-04-23)

## Context

2026-04-23 리팩터링 검토 결과 7개 기준(R1~R7: 계층경계 / SSE 무결성 / async·타입 안정 / 테스트 격리 / 팽창 임계 / env·문서 drift / 도메인 집약) 중, 서비스 회귀 위험이 낮으면서 즉시 가치를 내는 항목을 1 Pass 로 묶어 처리한다. Phase 2(Premium) 착수 전 코드베이스 정돈 목적.

**검토 근거**:
- 백엔드 audit: `agent/nodes/respond.py` 502 LOC · `planner.py` 399 LOC · blanket `except Exception` 9건 · `singleflight.py` 호출처 0 · `routes/*.py` 에서 `HTTPException` 15건 직접 raise (errors.py 래퍼 미사용)
- 프론트 audit: `chatStore.ts` 381 LOC (state 13 + action 18) · 레거시 `feature1~7-*.spec.ts` 8건과 `ring1/f01~f03` 중복
- 횡단 audit: `docs/status/current-status.md` 411줄 (status-compress 400줄 임계 초과)

**Memory 참조** (2026-07-04 정정: 리포 루트 `memory/` 디렉토리 부재로 링크 제거, 교훈 요지만 보존):
- [[feedback_formatter_strips_unused_imports]] — `Any` 미사용 import 정리 시 ruff/prettier 가 제거. "사용 지점" 분리 Edit 금지 → 단일 Edit 또는 lazy import.
- [[feedback_structlog_extra_silent]] — except 좁히기 후 추가 로그는 printf-style 유지, `extra=` kwargs 드롭.
- [[feedback_read_large_doc_chunking]] — current-status.md 압축 시 limit=150~200 청크 Read.
- [[feedback_e2e_user_message_pollution]] — 레거시 spec 삭제 전 ring1 이 동일 키워드 검증 실제 커버하는지 확인.
- [[feedback_react_event_keys_unique]] — chatStore slice 분할 시 message key 유일성 회귀 주의.

## Scope

**In Scope (Pass 1 — 저위험, 30분~1시간)**:
- `server/server/services/singleflight.py` 삭제 + 모듈 레퍼런스 정리
- `frontend/e2e/feature{1..7}-*.spec.ts` 8개 삭제 (ring1/f01~f03 중복 확인 후)
- `docs/status/current-status.md` 400줄 초과분 이력 테이블 압축
- 백엔드 미사용 `Any` / `typing` import 정리 (`planner.py:8` 등)

**In Scope (Pass 2 — 중위험, 1주 내)**:
- `server/server/api/errors.py::make_error_response` 래퍼로 routes 15건 HTTPException 통합
- blanket `except Exception` 9건 → `TimeoutError | CircuitOpenError | SQLAlchemyError` 좁히기
- `agent/nodes/respond.py` (502 LOC) → `agent/utils/formatting.py` 로 `_compute_hints` / `_format_tool_results` / `_format_history` 추출
- `frontend/src/stores/chatStore.ts` (381 LOC) → slice 분할 (`previewSlice`/`mobileSlice`/`feedbackSlice` — 단, Zustand single-store 유지, 섹션 주석으로만 나누거나 별도 파일 `stores/slices/*.ts` 후 combine)

**Out of Scope**:
- Service layer 신설 (routes→services→repositories) — Phase 2 결합 시 처리
- Agent tool DI 전환 — 테스트 커버리지 확보 후
- `config.py` 4그룹 분할 — 영향 넓음, 별도 Plan
- Next.js 15 승격 — 검증 분량 별도 Plan
- SSE 9 이벤트 스키마 및 TTFT 경로 — 회귀 절대 금지

## Design

### Pass 1 변경 파일

| 경로 | 변경 |
|---|---|
| `server/server/services/singleflight.py` | 파일 삭제 |
| `server/server/services/__init__.py` | `get_singleflight` export 제거 (있다면) |
| `server/server/main.py` | lifespan 에서 singleflight 초기화 제거 (있다면) |
| `frontend/e2e/feature1-polygon-summary.spec.ts` | 삭제 |
| `frontend/e2e/feature2-context-retention.spec.ts` | 삭제 |
| `frontend/e2e/feature3-bidirectional-sync.spec.ts` | 삭제 |
| `frontend/e2e/feature4-progress-indicator.spec.ts` | 삭제 |
| `frontend/e2e/feature5-card-rendering.spec.ts` | 삭제 |
| `frontend/e2e/feature6-streaming-ux.spec.ts` | 삭제 |
| `frontend/e2e/feature7-error-handling.spec.ts` | 삭제 |
| `docs/status/current-status.md` | 2026-04-22 이전 일자 섹션 → 이력 테이블 1행. 최근 2일(2026-04-23 포함) + Next Items + 참고 문서 + 이력 요약 유지 |
| `server/server/agent/nodes/planner.py` | 미사용 `from typing import Any` 제거 |
| `server/server/agent/**/*.py` | ruff --fix 로 unused import 스윕 |

### Pass 2 변경 파일

| 경로 | 변경 |
|---|---|
| `server/server/api/errors.py` | `make_error_response(code, message, status)` 래퍼 확인/추가 |
| `server/server/api/routes/districts.py` | 9건 `raise HTTPException` → 래퍼 호출 |
| `server/server/api/routes/map_data.py` | 6건 동일 |
| `server/server/api/routes/chat.py:130` | Redis 폴 실패 `except Exception: pass` → `except (ConnectionError, TimeoutError) as e: logger.warning(...)` |
| `server/server/agent/graph.py:348` | `except Exception` → 구체 exception tuple |
| `server/server/agent/nodes/planner.py:304` | 동일 |
| `server/server/agent/utils/formatting.py` | **신규** — `_compute_hints`, `_format_tool_results`, `_format_history` 이식 |
| `server/server/agent/nodes/respond.py` | formatting.py import 사용, LOC 502 → ~300 목표 |
| `frontend/src/stores/chatStore.ts` | state/action 섹션 주석 분리 또는 `stores/slices/{preview,mobile,feedback}.ts` 추출 후 combine |

### 의존성 / 선행 Plan

- 선행: 없음 (모두 독립)
- 병행 금지: SSE 경로 개선(별도 Plan 필요), Service layer 신설

## Checklist

### Pass 1 (저위험)

- [ ] `singleflight.py` 호출처 재확인(`grep -r "singleflight" server/`) 후 파일 삭제
- [ ] `services/__init__.py` export 정리 · `main.py` lifespan 참조 제거
- [ ] `pytest server/tests/test_smoke.py` 그린 확인
- [ ] `ring1/f01-map-selection.spec.ts` · `f02-agent-chat.spec.ts` · `f03-summary-report.spec.ts` 가 `feature1~3` 시나리오 커버하는지 grep 대조
- [ ] `feature1~7-*.spec.ts` 8개 `git rm`
- [ ] `npx playwright test --list` → 신규 총 테스트 수 38(37-8+ring5+추가) 확인
- [ ] `current-status.md` 2026-04-22 이하 일자별 섹션 → 이력 요약 테이블 1행씩 압축 (Ring 0~3 전체 그린 · eval 7/7 같은 팩트는 유지)
- [ ] `current-status.md` 최종 LOC < 400
- [ ] `ruff check --fix server/` → unused import 정리, `ruff check server/` 0 에러
- [ ] `cd frontend && npx tsc --noEmit` 0 에러

### Pass 2 (중위험)

- [ ] `make_error_response` 시그니처 확인(`errors.py`), 부재 시 추가
- [ ] `districts.py` · `map_data.py` · `chat.py` · `feedback.py` 의 `HTTPException` raise 전수 치환 — error code enum 정의
- [ ] `except Exception` 9건 각각 실패 유형 식별 후 구체 타입 지정, 필요 시 `logger.warning("%s failed", op)` 추가
- [ ] `agent/utils/formatting.py` 생성 — respond.py 내부 헬퍼 3종 이식, signature 동일 유지
- [ ] `respond.py` import 전환 후 단위 smoke (Mock 세션 1회 `/api/chat` 응답 본문 동일성 확인)
- [ ] `chatStore.ts` slice 분할 후 `npx tsc --noEmit` + `npx next build` 0 에러
- [ ] Ring 1 `f02-agent-chat`, `f03-summary-report` 실행 → 스트리밍 UX 회귀 없음

## 재검토 (Self-Review Gate)

- [ ] **엣지케이스**: singleflight 는 정말 0 호출? `grep -rn "singleflight\|Singleflight\|single_flight"` 전수
- [ ] **엣지케이스**: 레거시 spec 삭제 시 `helpers/setup.ts` 재사용 함수 누락되는지 (ring1 도 같은 helper 쓰는지)
- [ ] **엣지케이스**: current-status.md 압축 시 "Accuracy Gap W1/W2/W3 구현" · "Langfuse L1 확인" · "프로덕션 재배포" 3건 팩트 유지
- [ ] **엣지케이스**: respond.py 헬퍼 이식 후 closure/module-level 변수 의존 여부 확인 (settings, logger 재주입)
- [ ] **엣지케이스**: chatStore slice 분할 시 action 간 cross-reference (e.g. `sendMessage` 가 `setPreview` 호출) 보존
- [ ] **Memory 교훈**: `Any` 제거는 import 문 제거 Edit 1회로 — `feedback_formatter_strips_unused_imports.md` 위반 금지
- [ ] **Memory 교훈**: except 좁힌 후 추가 로그는 printf-style — `feedback_structlog_extra_silent.md`
- [ ] **타 Plan 충돌**: [accuracy-gap-fix.md](../fix/accuracy-gap-fix.md) W4 (Card-level PDF) 와 chatStore 분할 순서 — W4 deferred 상태라 무충돌
- [ ] **타 Plan 충돌**: [llmops-l1-verification.md](./llmops-l1-verification.md) C-8 프로덕션 재검증 이전에 respond.py 분할이 끝나지 않아야 함 → Pass 2 는 dev 검증까지만, 프로덕션 재빌드는 별도 세션

## Scenario (E2E Ring Mapping)

- **Ring**: 3 (regression) — 리팩터링이 기존 동작 보존하는지 회귀 검증 목적

### R3-REFACTOR-01 — Pass 1 저위험 회귀
- **사전조건**: Mock 모드, USE_MOCK=true
- **실행 단계**:
  1. `npm test -- ring0-preflight` (stack up)
  2. `npm test -- ring1-features/f02-agent-chat`
  3. `npm test -- ring1-features/f03-summary-report`
- **기대**: 3 spec 모두 PASS, SSE 이벤트 9종 유지, agentSteps 렌더

### R3-REFACTOR-02 — Pass 2 Respond.py 분할 회귀
- **사전조건**: Pass 2 완료, 로컬 backend + frontend 기동
- **실행 단계**:
  1. `curl POST /api/chat {"message":"강남역 요약","district_code":"3120189"}`
  2. SSE 이벤트 sequence · `text` 청크 누적 · `done.trace_id` 동봉 확인
  3. `card.summary.insights.weekendUplift` 숫자값 이전 빌드 대비 drift 없음
- **기대**: formatting.py 이식 전후 응답 의미적 동일

### R3-REFACTOR-03 — chatStore slice 분할 회귀
- **사전조건**: Pass 2 완료
- **실행 단계**:
  1. `npm test -- ring1-features/f12-feedback`
  2. `npm test -- ring1-features/preview-api` (F13)
  3. `npm test -- ring2-journeys/j05-pdf-stakeholder`
- **기대**: preview/mobile/feedback/PDF 경로 PASS, `window.__chatStore` 세이프 셀렉터 유지

## Pass 반복 (Iteration Plan)

- **Pass 1 (저위험 일괄)**: singleflight 제거 · 레거시 E2E 삭제 · status 압축 · Any import 정리. R3-REFACTOR-01 실행.
- **Pass 2 (errors · except · respond · chatStore)**: 순차 진행, 각 단계별 `npm test -- ring1` smoke. 모두 통과 시 R3-REFACTOR-02/03 실행.
- **Pass 3 (회귀 검증)**: Ring 0~3 full 1회 (Mock 39 + Real 24 목표). Fail → 수정 → 재실행 최대 2회.

## Agent 모델 선택

- **설계**: opus (본 Plan 이미 작성됨)
- **구현**: sonnet — 명확한 삭제/치환 작업. chatStore slice 분할만 opus 복귀 고려
- **검증**: haiku (Pass/Fail 판정 — spec green/red 만 보면 충분)

**근거**: 리팩터 중 삭제/이름변경/단순 추출이 대부분. respond.py 이식은 signature 동일성 유지라 sonnet 적합. chatStore 는 cross-reference 설계 필요 시 opus 스위치.

## Validation

### 수동 검증
1. `cd server && ruff check . && ruff format --check .` → 0 에러
2. `cd frontend && npx tsc --noEmit && npx next build` → 0 에러
3. `wc -l docs/status/current-status.md` < 400
4. `git diff --stat` — 삭제 줄 수 > 추가 줄 수 (리팩터 특성)

### 자동 검증
- `/e2e-run 0` — infra sanity
- `/e2e-run 1` — features 전수
- `/e2e-run 3` — regression

## Metadata
- 작성일: 2026-04-23
- 작성자: Claude Code (plan-new skill, infra 카테고리 배정 — refactor 미허용)
- 후속 Plan 후보:
  - `infra/service-layer-extraction.md` (R1 Service layer 신설)
  - `infra/config-split.md` (R5 config.py 4그룹 분할)
  - `agent-improvement/tool-dependency-injection.md` (R4 테스트 주입)
