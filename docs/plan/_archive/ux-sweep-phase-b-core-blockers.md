# UX Sweep — Phase B · 핵심 기능 막힘 해소

> 시리즈: **UX Sweep 2026-04-30** (38건 점검 → 6 phase 분할)
> 본 phase 영역: 챗·지도·카드 핵심 흐름 6건 · 예상 3~4h
> 타 phase: [A Quick Wins](ux-sweep-phase-a-trust-legal.md) · [C 자연스러움](ux-sweep-phase-c-polish.md) · [D A11y/마감](ux-sweep-phase-d-a11y.md) · [E Premium defer](ux-sweep-phase-e-premium-deferred.md) · [F Tier hook](ux-sweep-phase-f-tier-hook.md)

## Context

직전 38건 점검 중 **사용자가 "어? 안되네" 라고 느끼는 6개 흐름 차단**을 해소. 같은 상권 재클릭 deselect 안 됨, 비교 4번째 클릭 silent fail, PDF 실패 silent, PDF regex 미매칭, deeplink history 잔존, CompareCard 상권 제거 불가.

핵심 인프라: **toastStore 자체 구현** (deps 추가 회피, ~80 LOC). B.2 가 인프라 도입처 → B.4 가 첫 사용처. 이후 D.4·D.5 도 같은 토스트 사용.

- 메모리 참조: `district-click-race-2026-04-28.md` Stale-while-cancel 패턴 → B.4 PDF 재시도에 적용.
- 인접 plan 충돌 없음.

## Checklist

- [ ] **B.1** 같은 상권 재클릭 deselect (비교 모드 ON 시 `removeFromCompare`) [M]
- [ ] **B.2** toastStore + Toast 컴포넌트 신규 (인프라) + 비교 한도 토스트 [S]
- [ ] **B.3** CompareCard 컬럼 헤더 × 버튼 + 토스트 안내 [M]
- [ ] **B.4** PDF 실패 토스트 + 재시도 (B.2 후) [M]
- [ ] **B.5** PDF regex 확장 (`다운|출력|내보` 추가) + false positive 가드 [S]
- [ ] **B.6** deeplink `?q=` history scrub (`replaceState`) [S]

## 변경 사양

### B.1 deselect
- 파일: `frontend/src/components/map/DistrictLayer.tsx:136-147` + `stores/districtStore.ts:28-31`
- polygon click 안에서 `selectedCodeRef.current === feature.code` 일 때:
  - 비교 모드 OFF → `useDistrictStore.getState().deselect()` (이미 존재).
  - 비교 모드 ON → `removeFromCompare(feature.code)` (이미 존재 — `districtStore.ts:48-51`).
- `useMapSync` 에서 deselect 시 `chatStore.clearPreview()` 호출 추가 (preview 카드 잔존 방지).

### B.2 toastStore + 비교 한도
- 신규: `frontend/src/components/feedback/Toast.tsx` (~80 LOC) + `frontend/src/stores/toastStore.ts` (~60 LOC)
- 수정: `frontend/src/stores/districtStore.ts:43` `addToCompare` 한도 초과 시 `toastStore.show('비교는 최대 3개까지 가능합니다', 'warning')` 호출 후 return.
- 마운트: `app/layout.tsx` 에 토스트 컨테이너 (클라이언트 only).
- API: `show(message, level, options?: { actionLabel?, onAction?, durationMs? })`. level: `info|success|warning|error`.

### B.3 CompareCard ×
- 파일: `frontend/src/components/chat/cards/CompareCard.tsx:111-117` (column header)
- `<th>` 안 상권 이름 옆 `<button aria-label="비교에서 제거">×</button>`.
- 클릭 시 `removeFromCompare(code)` (기존) + 토스트 "(상권명) 이 다음 비교에서 제외됩니다".
- 결정: 카드 자체는 SSE 시점 스냅샷 → 즉시 리렌더 X. 사용자가 "다시 비교해줘" 보내야 적용. 토스트로 명시.

### B.4 PDF 토스트 + retry
- 파일: `frontend/src/hooks/useReportExport.ts:69-73`
- `console.error` → `toastStore.show('PDF 생성에 실패했어요. 다시 시도해 주세요.', 'error', { actionLabel: '재시도', onAction: () => generatePDF() })`.
- 자동 retry off (사용자 명시 트리거만, 무한 루프 방지).

### B.5 PDF regex 확장
- 파일: `frontend/src/stores/chatStore.ts:259`
- 통합 regex:
  ```ts
  /pdf|리포트.*(저장|만들|내보|내려|다운|출력)|보고서.*(저장|만들|내보|내려|다운|출력)|pdf.*(저장|내보|만들|다운|출력)/i
  ```
- False positive 가드: 매칭된 메시지가 ≤ 30자 + 끝이 `(줘|해|해줘)?` 일 때만 트리거 ("PDF 가 뭐예요?" 차단).

### B.6 history scrub
- 파일: `frontend/src/app/app/page.tsx:47-55` (`DeepLinkHandler`)
- `setTimeout` 내 `sendMessage(prompt)` 직후:
  ```ts
  const url = new URL(window.location.href);
  url.searchParams.delete('q');
  window.history.replaceState({}, '', url.toString());
  ```
- **A.4 의 선행 요건** — 본 phase 가 먼저.

## 재검토 (Self-Review Gate)

### 엣지케이스
- **B.1 + 비교 한도 3 도달**: 같은 상권 재클릭 → `removeFromCompare` 로 length 2 → OK.
- **B.2 SSR**: 토스트는 `'use client'` 파일 + dynamic import 또는 `useEffect` 내 마운트.
- **B.3 카드/스토어 불일치**: 카드 SSE 시점 스냅샷 vs store 즉시 변경 → 토스트 안내로 회피.
- **B.4 무한 retry**: 자동 retry 비활성, 사용자 명시 트리거만.
- **B.5 false positive**: "PDF 가 뭐야" / "PDF 형식 알려줘" 등 → 길이/꼬리 가드.
- **B.6 + 외부 링크 공유**: `?q=` 가 검색엔진 인덱싱될 수 있음 → `noindex` 또는 robots.txt 검토.

### 메모리 교훈
- `feedback_chat_inflight_guard.md` — sendMessage 의 abort+restart 패턴은 이미 정착. B.5 regex 만 확장하면 충돌 0.
- `feedback_setpreview_lastcode_race.md` — B.1 의 `useMapSync.clearPreview` 호출은 monotonic seq 가드와 정합.

### 타 plan 충돌
- `mobile-responsive.md` 와 영역 중복 없음 (본 plan 은 desktop+mobile 공통 흐름).

## Scenario (E2E Ring Mapping)

| Test ID | Spec | Case |
|---------|------|------|
| `Ring1-F01-B1` | `e2e/ring1-features/f01-map-selection.spec.ts` | 강남 클릭 → 강남 다시 클릭 → 선택 해제 + preview 사라짐 |
| `Ring1-F05-B2` | `e2e/ring1-features/f05-compare.spec.ts` | 4번째 클릭 → 토스트 노출 + `compareList.length === 3` 유지 |
| `Ring1-F05-B3` | 동상 | 비교 카드 × 클릭 → 토스트 + compareList 2개로 감소 |
| `Ring1-F10-B4` | `e2e/ring1-features/f10-pdf-export.spec.ts` | Recharts 의도적 throw → 토스트 + 재시도 클릭 → 재호출 |
| `Ring3-Negative-B5` | `e2e/ring3-negative/p0-regression.spec.ts` 확장 | 7개 PDF 패턴 PASS + 3 negative ("PDF 가 뭐야" 등) 매칭 X |
| `Ring2-J01-B6` | `e2e/ring2-journeys/j01-first-time-user.spec.ts` | `?q=test` 진입 → 자동 전송 1회 → 새로고침 → 0회 + URL q 제거 |

## Pass 반복

- **Pass 1 (happy)**: 위 6 케이스 PASS.
- **Pass 2 (엣지)**: B.5 false positive 3건 추가 / B.1 비교 모드 + 한도 3 + 재클릭 / B.4 retry 5회 연속 (무한 루프 가드).
- **Pass 3 (성능)**: B.4 PDF 5s SLA / B.2 토스트 30개 동시 큐잉 (모바일 성능).

## Agent 모델

- 설계: opus
- 구현: sonnet (B.2 인프라 → B.5/B.6 short → B.1/B.3/B.4 atomic)
- 검증: haiku

## Critical Files

### 신규
- `frontend/src/components/feedback/Toast.tsx` (B.2)
- `frontend/src/stores/toastStore.ts` (B.2)

### 수정
- `frontend/src/components/map/DistrictLayer.tsx` (B.1)
- `frontend/src/hooks/useMapSync.ts` (B.1 — clearPreview 호출 추가)
- `frontend/src/stores/districtStore.ts` (B.2)
- `frontend/src/components/chat/cards/CompareCard.tsx` (B.3)
- `frontend/src/hooks/useReportExport.ts` (B.4)
- `frontend/src/stores/chatStore.ts` (B.5)
- `frontend/src/app/app/page.tsx` (B.6)
- `frontend/src/app/layout.tsx` (B.2 토스트 마운트)

### 참조
- `docs/plan/fix/district-click-race-2026-04-28.md` — Stale-while-cancel 패턴.
- `frontend/src/stores/chatStore.ts:144-187` — staleness 가드 reuse.

## Rollout 머지 순서

B.2 (토스트 인프라) → B.5 → B.6 → B.4 → B.1 → B.3 — 인프라 우선, 독립 항목 다음, 의존 항목 마지막.
