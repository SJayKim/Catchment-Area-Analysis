# Prod Baked-URL Regression Smoke

## Context

- **2026-04-24 프로덕션 핫픽스 사건**: `.env` 잔여 dev 값 `NEXT_PUBLIC_API_URL=http://localhost:3000` 이 19시간 전 v0.4.0 (`c6cc60e`) 프론트엔드 빌드 시 JS 번들에 baked-in. 사용자 브라우저에서 `/api/chat` 요청이 **본인 PC 의 localhost:3000** 으로 향해 mixed-content 차단 + 잘못된 호스트로 실패 → agent 응답이 화면에 나오지 않음.
- **기존 prod-smoke 한계**: P1~P6 은 server-side `request.newContext()` 기반 curl 유사 호출로 baked-in URL 과 무관하게 prod origin 으로 직접 POST. P7 은 실제 브라우저지만 Kakao map 주입만 검증하고 `/api/chat` 은 건드리지 않음 → 번들 내 URL 회귀 미탐지.
- **근본 원인**: `NEXT_PUBLIC_*` 는 Next.js 빌드 타임에 정적 substitution 이라 런타임 env 변경으로 복구 불가. 빌드 파이프라인 자체를 감시해야 함.
- **Memory 참조**: 참조 없음 (memory/ 비어 있음 — 본 사건에서 `feedback_baked_env_url_regression.md` 신규 작성 후보).

## Scope

- **In Scope**:
  - `frontend/e2e/prod-smoke/prod-smoke.spec.ts` 에 `P8 real-browser chat round-trip` 추가 — 실제 페이지에서 ChatInput 으로 메시지 전송 → SSE 응답이 화면에 렌더되는지 검증.
  - 동일 spec 에 `P9 bundle URL scan` 추가 — `/app` HTML 이 참조하는 `_next/static/chunks/*.js` 전량을 다운로드해 `http://localhost:\d+` · `http://127\.0\.0\.1` 패턴 grep 후 검출 시 fail.
  - P8/P9 모두 `E2E_BASE_URL` 가 prod 도메인일 때만 assert (dev 로컬 실행 시 skip).
- **Out of Scope**:
  - Next.js build-time lint plugin (compile 시점 방어).
  - Secret scanner / env linting.
  - dev/e2e stack 용 변형 — 본 spec 는 prod-only regression guard.
  - `LANGFUSE_TRACING_ENVIRONMENT` 같은 **런타임** env 값 검증 (별도 ops 쪽에서 담당).

## Design

### P9 — bundle URL scan (빠름 · 결정적)

1. `request.newContext()` 로 `GET ${BASE}/app` HTML fetch.
2. `/_next/static/chunks/[^"]+\.js` 정규식으로 chunk 경로 전수 추출.
3. 각 chunk 다운로드 후 `/\bhttps?:\/\/(localhost|127\.0\.0\.1)(:\d+)?\b/` 매칭 검사.
4. 검출 시 `expect.soft` 대신 `expect(matches).toEqual([])` 로 fail + 첫 매칭 chunk 이름 메시지에 표시.

### P8 — real-browser chat round-trip (현실 시나리오 반영)

1. `page.goto(`${BASE}/app`, { waitUntil: 'domcontentloaded' })`.
2. `page.on('pageerror')` · `console.error` 수집.
3. `textarea[placeholder*="메시지"]` (ChatInput aria-label 또는 placeholder) 찾아 `'강남역 요약'` 입력.
4. `button[type="submit"]` 또는 aria-label "전송" click.
5. `page.waitForResponse(r => r.url().endsWith('/api/chat') && r.status() === 200, { timeout: 60_000 })`.
6. `MessageList` 에 assistant bubble 렌더 대기 (`[data-role="assistant"]` 또는 텍스트 일부 `/유동인구|월 추정/` 매칭).
7. `consoleErrors` 에서 `Mixed Content` · `ERR_BLOCKED_BY_CLIENT` 필터링해 0 이어야 함.

### 변경 파일

- `frontend/e2e/prod-smoke/prod-smoke.spec.ts`: P8/P9 test 2건 신규 추가. import/setup 변경 없음.

### 의존성 / 선행 Plan

- 선행 없음. `c6cc60e` 재배포 + 2026-04-24 핫픽스 완료 상태가 baseline.
- ChatInput DOM 구조 확인 필요 — `frontend/src/components/chat/ChatInput.tsx` 의 placeholder/aria 속성 확인 후 selector 확정.

## Checklist

- [ ] ChatInput selector 확인 (`frontend/src/components/chat/ChatInput.tsx` 열람)
- [ ] MessageList assistant bubble 의 data-role / class 확인 (`MessageBubble.tsx`)
- [ ] P9 구현 (30~50 LOC) — chunk 다운로드 + regex scan
- [ ] P9 skip 가드: `BASE` 가 `marketscope.robitlabs.co.kr` 호스트가 아니면 `test.skip`
- [ ] P8 구현 (50~80 LOC)
- [ ] P8 skip 가드 (P9 와 동일)
- [ ] P8 timeout 60s 설정 (PAE max 3 rounds 고려)
- [ ] `npx playwright test prod-smoke --project chromium` 로컬 실행 → P1~P9 전수 PASS
- [ ] 4 viewport (`playwright.config.ts` projects) × 9 test = 36 total 로 증가 — CI 예산 영향 확인
- [ ] 회귀 시뮬레이션: `.env` 에 localhost URL 재주입 → frontend 재빌드 → P9 fail 확인 (롤백 전 필수)

## 재검토 (Self-Review Gate)

- [ ] **dev false-positive**: `BASE` 호스트 체크로 skip. `E2E_BASE_URL=http://localhost:3000` 같이 로컬 스택 돌리는 경우 자동 skip.
- [ ] **allowlist 유지 필요성**: 현 시점 bundle 에 localhost 리터럴이 정당하게 들어가는 케이스 없음 (환경변수 substitution 만 사용). 만약 후속 코드가 의도적으로 localhost 참조하면 allowlist comment 추가 정책 수립.
- [ ] **mobile project 에서 P8 안정성**: iPhone 12 / Galaxy S9+ viewport 에서 mobile layout (BottomSheet 4-snap) 적용됨 → ChatInput 이 BottomSheet 내부에 있어 textarea selector 가 가려질 수 있음. `sheetSnap = 'full'` 트리거 필요할 수 있음 — 필요 시 `chatStore.setSheetSnap('full')` 을 `page.evaluate` 로 강제.
- [ ] **Memory 교훈**: 해당 없음 (memory dir 비어 있음).
- [ ] **타 Plan 충돌**: `docs/plan/ui/mobile-responsive.md` Phase F (E2E) 와 중복 가능성 — 해당 Plan 은 Ring 1~3 의 spec 추가 범위이고, 본 Plan 은 Ring 3 prod-smoke 전용으로 scope 분리.
- [ ] **SSE 이벤트 규약 무결성**: P8 은 chat SSE 응답을 화면 렌더로 관찰 — 서버 측 9 이벤트 규약 자체는 P5/P6 이 이미 커버.

## Scenario (E2E Ring Mapping)

- **Ring**: 3 (regression) — 특정 prod 배포 설정 회귀 전용 가드.
- **Scenario ID**:
  - `R3-PROD-SMOKE-P8-BROWSER-CHAT`
  - `R3-PROD-SMOKE-P9-BUNDLE-URL-SCAN`
- **사전조건**: `https://marketscope.robitlabs.co.kr/app` 200, `/api/chat` SSE 정상.
- **실행 단계** (P8):
  1. goto `/app`
  2. ChatInput 에 "강남역 요약" 입력 + 전송
  3. `/api/chat` 200 수신 + assistant bubble 렌더 대기
  4. `Mixed Content` · `ERR_BLOCKED_BY_CLIENT` 콘솔 에러 0 확인
- **실행 단계** (P9):
  1. GET `/app` HTML
  2. chunk 경로 추출 → 각 chunk 다운로드
  3. `http://localhost:\d+` · `http://127.0.0.1` 매칭 스캔
  4. 매칭 0 assert
- **기대 결과**: 둘 다 PASS. 회귀 (env-split 반복) 시 P9 즉시 fail + 오염 chunk 이름 노출 / P8 콘솔 Mixed Content 에러 + assistant bubble 미렌더.

## Pass 반복 (Iteration Plan)

- **Pass 1 (기본)**: P9 (정적 scan) 먼저 구현. 실행 <2s, 결정적. 핫픽스 회귀 감지에 충분.
- **Pass 2 (엣지)**: P8 (real-browser) 추가. selector 조정 · mobile project 에서 BottomSheet 트리거 필요 여부 판단.
- **Pass 3 (성능/안정)**: 4 viewport × 9 test = 36 total 의 실행 시간 측정 (기존 28 test ~58s → 추정 75~90s). flaky 발생 시 P8 에 `test.retry(1)` 적용.
- 각 Pass 후 local `npx playwright test prod-smoke --project chromium` 실행. Fail → 수정 → 재실행.

## Agent 모델 선택

- **설계**: opus (본 Plan 작성 · Context 연결 이미 완료).
- **구현**: sonnet — Playwright spec 은 기존 P1~P7 패턴 따라 반복 작성 가능.
- **검증**: haiku — P8/P9 PASS/FAIL 판정만 필요.
- **근거**: 신규 로직 2개 모두 스펙 명확. 설계 잔여 판단 (selector 후보, skip 가드 임계) 는 sonnet 으로도 충분.

## Validation

- **수동**:
  ```bash
  cd /home/sjkim/Catchment-Area-Analysis/frontend
  npx playwright test prod-smoke --project chromium --reporter=list
  ```
  → 9/9 PASS 기대. 각 test 소요: P1~P4 <2s / P5~P6 ~20s / P7 ~10s / P8 ~15s / P9 <3s. 총 ~55s.
- **회귀 시뮬레이션**:
  1. 임시 `.env` 복사 후 `NEXT_PUBLIC_API_URL=http://localhost:3000` 재주입
  2. `docker compose -f docker-compose.prod.yml build frontend`
  3. `npx playwright test prod-smoke -g P9` → **FAIL** 확인 (chunk 파일명 에러 메시지에 포함)
  4. `.env` 원상복구 + 재빌드 + 재실행 → PASS
- **CI 영향**: GitHub Actions / Playwright runner 돌릴 경우 prod-smoke 는 이미 post-deploy hook 으로 돌아가는 관례 (docs/qa/runs 기록 기준). 시간 +17s 이내이므로 수용 가능.

## Metadata

- 작성일: 2026-04-24
- 작성자: Claude Code (plan-new skill)
- 카테고리: `infra` (prod 배포 regression guard — qa 성격이나 스킬 허용 카테고리 제한으로 infra 선택)
- 관련 사건: 2026-04-24 프로덕션 핫픽스 (current-status.md 최상단 bullet 참조, commit `21ad053`)
