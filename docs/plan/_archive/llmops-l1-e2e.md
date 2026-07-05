# LLMOps L1 — E2E 검증 Plan

> **Status**: Active → ✅ 완료 (2026-07-04 문서 정합성 감사에서 구현 완료 확인 — spec 실존 + 7/7 PASS 기록: [llmops-l1-verification.md](llmops-l1-verification.md))
> **Parent plan**: `docs/plan/infra/llmops-platform.md` §3.3.1 / §4.3
> **ADR**: `docs/plan/infra/llmops-l1-adr-hosting.md`
> **Date**: 2026-04-21

## 1. Context

L1 (Langfuse trace wiring) 구현 직후 **서비스 계약 회귀 0** 을 입증하는 것이 본 plan 의 단일 목표.

Plan 상위 문서 §4.2 재검토 결과 중 아래 4개 제약이 E2E 검증 범위로 떨어진다:

1. **SSE 포맷 불변** — `event:` 라인 신설 금지, 기존 9종 이벤트 type/필드 불변, `trace_id` 는 `done` 안쪽에만.
2. **Langfuse 다운 = 정상 서비스** — Langfuse 키 미설정/SDK 부재/잘못된 키/네트워크 단절 상태에서 `/api/chat` 모든 경로 그대로 동작.
3. **UTF-8 I/O 강제** — session 해시가 멀티바이트 session_id 에서도 결정적.
4. **hash 결정적 + salt 독립** — 같은 salt + 같은 session_id → 항상 같은 해시. salt 다르면 다른 해시.

### 1.1 이미 검증된 항목 (L1 작업 중 수행)

| 항목 | 방법 | 결과 |
|------|------|------|
| Python AST 4 파일 | `ast.parse` | OK |
| `_hash_session` 단일 호출 | `docker exec python -c` | `4cad75f238dd7abe` (16 hex) |
| Langfuse v4 SDK + 키 미설정 → None | 동일 | None |
| v4 SDK + 잘못된 키 + 생성자 → warn + None | 동일 | None |
| 5-쿼리 smoke (summary/compare/recommend/risk/simulate, Mock D3001) | `scripts/_l1_smoke.py` (1회용, 제거됨) | `all_ok=True` — 각 쿼리 9~17 SSE 이벤트 |
| Ring 0 (4 tests) | Playwright | 4/4 PASS (1.9s) |

> ⚠ 2026-07-04 정정: 본 문서 곳곳의 "Langfuse **v4** SDK" 표기(위 §1.1 표 · §3.2 L1-E02 · §3.3 의사코드 · §4.2)와 §5.3 커밋 템플릿의 "SDK **v2.x** 핀" 은 서로 모순이며 둘 다 현행 핀과 불일치한다. 실제 고정 버전은 **v3** — `server/pyproject.toml` 이 `langfuse>=3,<4` + `langchain>=1,<2` 로 핀(L1 작업 중 v2→v3 포팅됨, 근거: [llmops-l1-verification.md](llmops-l1-verification.md)). L1-E02/E03 의 graceful-degrade(키 미설정/SDK 부재/잘못된 키 → None) 검증 취지는 SDK 메이저 버전과 무관하게 유효하다.

### 1.2 본 Plan 이 추가로 확인할 항목

| Gap | 이유 |
|-----|------|
| L1-E01 ~ L1-E07 자동 회귀 spec | smoke 는 1회성. 회귀 방지용 영구 spec 필요. |
| hash salt 교체 독립성 | 배포 환경에서 salt 변경 시 해시 격리 보장 |
| 멀티바이트 session_id | "강남-세션-001" 등 한글 포함 session_id 에서 encode 깨짐 없음 |
| SSE `event:` 라인 grep | 파서가 아닌 **원시 raw text** 에서 `event:` 가 다시 생기지 않는지 상시 검증 |

---

## 2. Scope

### 2.1 In-Scope

- L1 관련 7 시나리오 자동 회귀 spec (Playwright Ring 3 에 편입)
- 기존 Ring 0/Ring 3 회귀 (L1 변경이 기존 E2E 깨지지 않음)

### 2.2 Out-of-Scope

- **R1-TRACE-BASIC** (실제 Langfuse Cloud 연결) — 본 작업 단계에서는 Langfuse Cloud 계정 키가 없음. 키 발급 후 별도 수동 smoke.
- **L2~L5** 관련 검증 (별도 Plan)
- Real 모드 — L1 변경은 LLM 레이어만 건드리므로 Real 전환 없이 Mock 에서 충분 (Plan §2.2 Out-of-Scope 의 "PII 정책 전면" 과 정합)
- 부하 테스트 — `docs/plan/infra/load-test-plan.md` 트랙

---

## 3. Design

### 3.1 Spec 배치

Ring 3 (negative + regression) 에 **새 파일 1 개** 추가:

```
frontend/e2e/ring3-negative/l1-langfuse.spec.ts
```

- 기존 `helpers/setup.ts` · `sseCapture.ts` · `evalPacket.ts` 재사용
- `MSYS_NO_PATHCONV` + `docker compose exec` 패턴은 `reg-2026-04-17.spec.ts` 에서 기 검증 완료, 동일 방식으로 backend 컨테이너 내부 python 실행
- backend 접근이 필요 없는 시나리오(hash 결정성 등)는 Playwright `request.post` 로 SSE 직접 파싱

### 3.2 7 시나리오 명세

| ID | 대상 | 방법 | PASS 기준 |
|----|------|------|-----------|
| **L1-E01** TRACE-DOWN-BASELINE | SSE 계약 보존 | POST `/api/chat` mock D3001, message="강남역 분석해줘" | events ≥ 5, `done` 수신, `trace_id` None, `event:` 라인 0 |
| **L1-E02** TRACE-SDK-MISSING | v4 SDK + `langfuse.callback` import 실패 시 handler None | backend 컨테이너 python 으로 직접 `get_langfuse_handler()` 호출 | `None` 반환 + log warn `langfuse package unavailable` |
| **L1-E03** TRACE-BAD-KEY | 잘못된 키로 생성자 시도 | 환경변수 `LANGFUSE_*_KEY` 주입 + 동일 경로 | `None` + `_tracer_valid=False` 상태 이후 재시도 스킵 |
| **L1-E04** HASH-DETERMINISTIC | 동일 salt + session_id → 동일 해시 | backend python 으로 `_hash_session("abc")` 2회 호출 + 멀티바이트 session 포함 | 2회 결과 동일, 16 hex, 한글 session 깨짐 없음 |
| **L1-E05** HASH-SALT-INDEPENDENT | salt 교체 시 해시 격리 | LANGFUSE_SESSION_SALT 덮어쓰고 재호출 | 두 해시 서로 다름, 각자 16 hex |
| **L1-E06** DONE-TRACE-ID-OPTIONAL | `trace_id` 없는 `done` 이벤트에서 frontend 파서 무사 통과 | L1-E01 의 JSON을 frontend types/eventHandlers 로 쳐서 검증 (Playwright page 경유) | 마지막 메시지 정상 렌더, 콘솔 에러 0 |
| **L1-E07** SSE-CONTRACT-GREP | SSE raw stream 에 `event:` 라인 금지 | L1-E01 의 raw bytes 에서 `/^event:/m` 검색 | 0 match |

### 3.3 spec 구조 (의사 코드)

```ts
test.describe('Ring 3 — LLMOps L1 Langfuse wiring', () => {
  test('L1-E01 TRACE-DOWN baseline (no keys → normal SSE)', async ({ request }) => { ... });
  test('L1-E02 TRACE-SDK-MISSING v4 import fail', async () => { dockerExec ... });
  test('L1-E03 TRACE-BAD-KEY constructor fails', async () => { dockerExec ... });
  test('L1-E04 HASH-DETERMINISTIC', async () => { dockerExec ... });
  test('L1-E05 HASH-SALT-INDEPENDENT', async () => { dockerExec ... });
  test('L1-E06 DONE-TRACE-ID-OPTIONAL frontend parser', async ({ page }) => { ... });
  test('L1-E07 SSE-CONTRACT-GREP no event: line', async ({ request }) => { ... });
});
```

### 3.4 회귀 범위

- L1-E01/E06/E07 은 **L1 없이도** 깨지면 PAE SSE 계약이 부서진 것 — 장기적 회귀 가치 높음
- L1-E02~E05 는 Langfuse SDK 업그레이드/salt 정책 변경 시 자동 감지

### 3.5 실행 정책

| 항목 | 값 |
|------|-----|
| 모드 | Mock only (Plan §2.2 와 정합) |
| Stack | 기존 `docker-compose.e2e.yml` + `marketscope-e2e` project 재사용 |
| Preflight | 기존 `scripts/e2e/preflight.sh` (Ring 0 통과 후 진행) |
| 타임아웃 | test 별 45s. 컨테이너 exec 15s. SSE 파싱 30s |
| Artifact | `frontend/e2e/artifacts/run-{date}/l1-*` — EvalPacket 표준 |

---

## 4. Checklist · 재검토 · Scenario · Pass · Agent 모델

### 4.1 Checklist

- [x] Plan 문서 작성 (본 문서)
- [x] `frontend/e2e/ring3-negative/l1-langfuse.spec.ts` 구현 (7 test)
- [x] Pass 1 실행 → 실패 root cause → 수정
- [x] Ring 0 회귀 (4 tests) 재확인
- [x] status 문서 (`docs/status/current-status.md`) 반영
- [x] 단일 커밋 + push

> (2026-07-04 문서 정합성 감사에서 구현 완료 확인 — spec 파일 실존(7 test 선언), "7/7 PASS" 및 L1 커밋(`42b2209` 외)은 [llmops-l1-verification.md](llmops-l1-verification.md)·status 2026-04-21 기록 참조.)

### 4.2 재검토 (Self-Review Gate)

1. **엣지케이스**
   - v4 SDK 환경에서 L1-E02 가 "정상 PASS" 로 찍혀야 함 — Langfuse 재업그레이드 시 의도 역전 방지 — test 본문에 "이 PASS 는 v4 환경이 만든 graceful degrade 증거" 주석 필수
   - salt 재생성이 매 재시작마다 일어나므로 L1-E05 는 단일 프로세스 안에서 salt override 주입으로 검증 (재기동 없이)
   - Playwright `request.post` 가 SSE raw text 접근 가능 — `response.text()` 사용

2. **교훈 충돌**
   - `reg-2026-04-17.spec.ts` 처럼 `MSYS_NO_PATHCONV` 이슈 있음 → `process.env.MSYS_NO_PATHCONV='1'` 로컬 주입 불가. spawnSync env 에 넣어도 MSYS 는 spawn 시점 변환. 회피: backend 컨테이너 내부 스크립트로 `python -c "..."` 원라이너 사용 (경로 변환 불필요)
   - Windows UTF-8: python -c 안에 한글 들어가면 콘솔 codec 에러 가능 → **base64 인코딩 후 전달** 또는 ascii-safe 데이터만

3. **타 Plan 충돌**
   - 없음. Ring 1~2 시나리오 건드리지 않음.

### 4.3 Scenario (Parent plan §4.3 매핑)

| 본 spec ID | Parent R-ID | 범위 |
|-----------|-------------|------|
| L1-E01 | R1-TRACE-DOWN (완료 조건 중 SSE 정상성) | 직접 매핑 |
| L1-E02/E03 | R1-TRACE-DOWN (graceful degrade 세부) | 확장 |
| L1-E04/E05 | §4.2 재검토 "세션 해시 PII 정책" | 추가 |
| L1-E06 | (프론트 파서 호환) | 추가 |
| L1-E07 | §4.2 재검토 "SSE `event:` 신설 금지" | 핵심 |

### 4.4 Pass 반복

- **Pass 1** — 7 test 실행 + Ring 0 (4 test). 모두 green 목표.
- **Pass 2** (필요 시) — 엣지 환경 (Windows path 변환, 한글 session) 재검증.
- **Pass 3** — 생략 (성능 검증은 load-test plan 트랙).

### 4.5 Agent 모델

| 단계 | 모델 | 근거 |
|------|------|------|
| Plan 작성 (본 문서) | Opus | 교훈 상관, 회귀 범위 판단 |
| spec 구현 | Opus | 단일 호출로 끝내기 (sonnet 대체 비용 ↑) |
| 실행/수정 | Opus | 반복 실패 분석 |

---

## 5. Validation

### 5.1 성공 기준

| 항목 | 목표 |
|------|------|
| L1-E01~E07 | 7/7 PASS |
| Ring 0 (R0-1~R0-4) | 4/4 PASS |
| spec 파일 추가로 인한 기존 test 회귀 | 0 |
| TypeScript `tsc --noEmit` | 0 error |

### 5.2 Artifact

- `frontend/e2e/artifacts/run-2026-04-21-l1/` — EvalPacket (scenario/criteria/auto-verdict.json)
- `docs/status/current-status.md` — 최상단 진행 요약 한 줄 + "완료 항목" 블록

### 5.3 커밋 메시지 템플릿

```
feat(llmops): L1 Langfuse trace wiring + E2E 회귀 7 scenario

- Langfuse CallbackHandler 주입 (graceful degrade 우선)
- session_id salted hash (PII 보호)
- SSE done 이벤트에 trace_id optional 주입
- Ring 3 에 l1-langfuse.spec.ts 7 test 추가
- SDK v2.x 핀 (ADR: docs/plan/infra/llmops-l1-adr-hosting.md)
```

> ⚠ 2026-07-04 정정: 위 "SDK v2.x 핀" 은 오기 — 현행 실제 핀은 `langfuse>=3,<4`(v3, `server/pyproject.toml`). §1.1 정정 주석 참조.

---

## Metadata

- **작성자**: Claude (Opus)
- **작성일**: 2026-04-21
- **관련 커밋**: (pending)
- **상위**: `docs/plan/infra/llmops-platform.md`
- **수평 참조**: `docs/plan/infra/e2e-regression-plan-2026-04-19.md` (helpers/EvalPacket 계약)
