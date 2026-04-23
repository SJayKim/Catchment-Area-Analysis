# E2E Spec Hotfix — 4건 PASS 100% 복구 (2026-04-23)

> 2026-04-23 저녁 전체 회귀 Run 에서 FAIL 4건이 모두 **spec/runner 이슈**로 확인됨.
> 프로덕션 서비스는 정상(prod-smoke 28/28). 본 plan 은 spec 의 견고성을 끌어올려 PASS 100% 를 달성한다.

## Context

[Run log](../../qa/runs/e2e-run-2026-04-23-full.md) · [현재 상태](../../status/current-status.md)

### 근본 원인 4건

| # | Test | 근본 원인 | 증거 |
|---|------|----------|------|
| 1 | `F01-H3 store-driven select` | 진성 타이밍 플레이크 (`clickPolygonByCode` → StatusBar 8s 대기 중 2회 중 1회 race) | 재실행 PASS (5.1s) |
| 2 | `F12-FAB-KAKAO` | `FeedbackFab` 가 env 없을 때 `return null` (DOM 미존재) → `locator.getAttribute()` 가 **unlimited** default timeout 으로 대기 → `.catch()` 절대 fire 안 함 → 60s 테스트 타임아웃 | `FeedbackFab.tsx:25` + `f12-feedback.spec.ts:13` |
| 3 | `P0-6 fast district switch` | `page.locator('.h-8').first()` 가 **StatusBar 가 아닌** MessageList SVG/Map spinner/TimeSlider 버튼 중 첫 것을 집음 → `textContent=""` | StatusBar DOM dump 상 `선택: 건대입구 발달상권` 정상 표시 |
| 4 | `3-REG-VALIDATE-ENV-FAIL` | Playwright Docker 이미지에 `python` 명령 無 (`python3` 만). spec 기본값 `'python'` → ENOENT → `r.status=null !== 1` → 9ms 즉시 fail | `mcr.microsoft.com/playwright:v1.58.0-jammy` = Ubuntu jammy + python3 |

### Memory 참조

- [feedback_stale_container_vs_source.md](../../../memory/feedback_stale_container_vs_source.md) — 재빌드 후 동일 FAIL 재현 여부로 spec vs 서비스 구분.
- [feedback_probe_endpoint_shape_first.md](../../../memory/feedback_probe_endpoint_shape_first.md) — 셀렉터/응답 스키마 spec 작성 전 실제 DOM 확인. **P0-6 셀렉터 실수의 직접 교훈**.

## Scope

**In scope**:
- `frontend/e2e/ring1-features/f12-feedback.spec.ts` — `fab.count()` precheck 로 skip guard 보강
- `frontend/src/components/layout/StatusBar.tsx` — `data-testid="statusbar"` 추가
- `frontend/e2e/ring3-negative/p0-regression.spec.ts` — `.h-8` → `[data-testid="statusbar"]`
- `frontend/e2e/ring3-negative/reg-2026-04-17.spec.ts` — `PY` 기본값 `'python'` → `'python3'`
- `frontend/e2e/ring1-features/f01-map-selection.spec.ts` — `waitForStatusBarContains` 8s → 15s 타임아웃 (타이밍 여유)

**Out of scope**:
- `clickPolygonByCode` 의 근본 설계 개선 (별도 Plan)
- StatusBar 컴포넌트 리팩토링 (h-8 클래스 기반 → semantic)
- Playwright 설정 전역 retries 설정 (플레이크 숨김보다 원인 수정 선호)

## Design

### D1 — F12 skip guard 보강

```ts
// Before
const mode = await fab.getAttribute('data-feedback-mode').catch(() => null);
if (mode === 'hidden' || mode === null) { test.skip(...); return; }

// After
if ((await fab.count()) === 0) {
  test.skip(true, 'Feedback FAB not rendered (env vars unset)');
  return;
}
const mode = await fab.getAttribute('data-feedback-mode');
```

`count()` 은 auto-wait 가 아니라 즉시 반환 → 요소 부재면 0, skip fire.

### D2 — StatusBar data-testid + selector 교체

```tsx
// StatusBar.tsx
<div data-testid="statusbar" className="h-8 bg-gray-50 ...">
```

```ts
// p0-regression.spec.ts (P0-6)
const sb = (await page.locator('[data-testid="statusbar"]').first().textContent()) || '';
```

F01-H3 / F01-H4 등 다른 테스트들도 `.h-8` 사용 여부 조사. 동일 셀렉터 있으면 일괄 치환.

### D3 — PY 기본값 교체

```ts
// Before
const PY = process.env.E2E_PYTHON || 'python';

// After
const PY = process.env.E2E_PYTHON || 'python3';
```

`python3` 는 Ubuntu jammy(Playwright 이미지 base) + 대부분 Linux 환경 기본. 호스트에서 Python 2 를 써야 하는 레거시는 `E2E_PYTHON=python` 명시로 override.

### D4 — F01-H3 타이밍 여유

`waitForStatusBarContains(page, '홍대', 8000)` → `15000` 으로 확대. 직전 polygon click 의 Zustand update → React re-render → DOM paint 사이 race 허용. 8s 로 부족 → 15s 면 3σ 커버.

**왜 그냥 retry 올리지 않나**: 플레이크를 retry 로 덮는 것보다 타임아웃 여유가 명확. `playwright.config.ts` 의 `retries=0` 유지 (regression 회피 명확성).

## Checklist

### Phase A — 코드 수정
- [ ] D1 · `f12-feedback.spec.ts` `fab.count()` precheck
- [ ] D2-1 · `StatusBar.tsx` `data-testid="statusbar"`
- [ ] D2-2 · `p0-regression.spec.ts` selector 교체
- [ ] D2-3 · 기타 `.h-8` 사용 spec 일괄 확인/치환
- [ ] D3 · `reg-2026-04-17.spec.ts` PY 기본값
- [ ] D4 · `f01-map-selection.spec.ts` waitForStatusBarContains timeout 확대

### Phase B — 재검증
- [ ] e2e stack 재기동 (postgis init race 대응)
- [ ] 4건 개별 재실행 → 4/4 PASS
- [ ] 전체 ring0~3 재실행 → PASS 100 % 확인 (이전 FAIL 외 새 regression 없음)
- [ ] prod-smoke 영향 無 (서비스 수정은 StatusBar data-testid 만, HTML semantic 영향 0)

### Phase C — 기록/커밋
- [ ] Run log 섹션 추가 (비교표: before 94/106 → after 100% 목표)
- [ ] status-update 한 줄 추가
- [ ] 단일 커밋 + push

## Self-Review Gate

| 엣지 | 대응 |
|-----|-----|
| StatusBar data-testid 추가가 prod 렌더링에 영향 | HTML attribute 만 추가 → CSS/JS 영향 無. prod-smoke P1/P7 은 `MarketScope AI` 텍스트 / Kakao DOM 체크라 무관. |
| `[data-testid="statusbar"]` 가 빌드된 `_next` chunk 에 포함되려면 프론트 컨테이너 재빌드 필요 | e2e stack 의 frontend 가 `next dev` 모드인지 확인. dev 모드면 즉시 HMR 반영. runner 모드면 재빌드 필요. |
| fab.count() 이 auto-wait 없어 FAB 가 mount 지연 시 0 반환 | F12 spec 은 `page.goto('/')` 직후라 `domcontentloaded` 완료 = React hydration 완료 대기 추가 필요 여부 검토. 필요하면 `page.waitForLoadState('networkidle')` 보강. |
| python3 default 가 Windows/Mac 호스트에서 깨짐 | `E2E_PYTHON` override 문서화. 현재 CI/로컬 모두 Linux → 실영향 無. |
| 15s timeout 이 CI 에서 여전히 부족 | 실패 재현 시 `fullyParallel: false` · `workers: 1` 이미 적용, 추가 여유는 network idle wait. 이번 Pass 에서는 15s 고정. |

## Scenario — E2E Ring Mapping

| Ring | Test | Expected |
|-----|------|---------|
| R1 | F01-H3 store-driven select | 15s 여유로 flake 소거 |
| R1 | F12-FAB-KAKAO | count=0 skip 정상 fire |
| R3 | P0-6 fast district switch | testid 셀렉터로 StatusBar=건대 단독 |
| R3 | 3-REG-VALIDATE-ENV-FAIL | python3 exit=1, stderr 에 NEXT_PUBLIC_API_URL |

## Pass 반복

- **Pass 1**: 4건 재실행 → 4/4 PASS 확인 → 전체 ring0~3 재실행 → 이전 PASS 도 유지.
- **Pass 2** (엣지): StatusBar dev-mode 가 아닌 runner 모드면 frontend 이미지 rebuild 1회.
- **Pass 3**: 생략 (성능 아님).

## Agent 모델 선택

- 설계: Opus (본 plan)
- 구현: 간단한 동치 치환 (Sonnet 충분, 현재 Opus 유지)
- 검증: Playwright 공식 이미지 (별도 agent 불요)

---

*작성: 2026-04-23 / 실행 대상: `main d2b9073` 이후 + 본 hotfix*
