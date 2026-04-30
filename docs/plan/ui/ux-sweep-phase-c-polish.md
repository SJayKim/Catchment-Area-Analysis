# UX Sweep — Phase C · UX 자연스러움 (Polish)

> 시리즈: **UX Sweep 2026-04-30** (38건 점검 → 6 phase 분할)
> 본 phase 영역: 챗·지도 미세 조정 5건 · 예상 2~3h
> 타 phase: [A Quick Wins](ux-sweep-phase-a-trust-legal.md) · [B 핵심 막힘](ux-sweep-phase-b-core-blockers.md) · [D A11y/마감](ux-sweep-phase-d-a11y.md) · [E Premium defer](ux-sweep-phase-e-premium-deferred.md) · [F Tier hook](ux-sweep-phase-f-tier-hook.md)

## Context

기능 막힘은 없지만 **"어색하다"고 느낄 만한** 5건. 빈 상태 가이드 부족, JumpFab 가시성, TimeSlider 드래그 lag, AgentProgressIndicator 완료 단계 fade-out 부재, PreviewCard CTA 클릭 후 active 시각 부재.

원본 점검에서 7건이었으나 코드 재확인 결과 2건 SKIP:
- **C.6 SuggestionChips 빈 배열 silent**: 부모 ChatPanel 이 default 3개를 항상 채움 (`chatStore.ts:107-111`) → 이미 처리됨.
- **C.7 useMapSync preview 인디케이터**: ChatPanel 이 `previewLoading` skeleton 이미 표시 → 추가 작업 불필요.

## Checklist

- [ ] **C.1** ChatPanel 빈 상태 → 3-step 가이드 + role 별 추천 칩 [S]
- [ ] **C.2** MessageList JumpFab 가시성 (bottom-3 → bottom-5 + box-shadow) [S]
- [ ] **C.3** TimeSlider rAF throttle (히트맵 재계산 cost 제거) [S]
- [ ] **C.4** AgentProgressIndicator completed step opacity 0.5 fade [S]
- [ ] **C.5** PreviewCard CTA 200ms active state ("분석 시작...") [S]

## 변경 사양

### C.1 빈 상태 강화
- 파일: `frontend/src/components/chat/MessageList.tsx:73-100`
- 현재 한 줄 → 3-step 진행 안내 + role 별 추천 칩 3개:
  - 사장님 → "이 자리 위험해?" / 투자자 → "유망 상권 추천" / 창업자 → "카페 하면 어때?"
- 재사용: `useChatStore.role`, 기존 SuggestionChips.

### C.2 JumpFab 가시성
- 파일: `frontend/src/components/chat/MessageList.tsx:159-182`
- `bottom-3` → `bottom-5` + `box-shadow: 0 4px 12px rgba(0,0,0,0.4)`.
- 검증: visual diff (Pass 3 만).

### C.3 TimeSlider throttle
- 파일: `frontend/src/components/map/TimeSlider.tsx:92`
- `useRef<number | null>` + `requestAnimationFrame` 8 LOC.
- onChange 가 매 frame 마다 store + HeatmapLayer 의 `useEffect([heatmapTimeSlot])` 재계산하던 cost 제거.
- 패턴:
  ```ts
  const rafRef = useRef<number | null>(null);
  const onChange = (e) => {
    const v = Number(e.target.value);
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    rafRef.current = requestAnimationFrame(() => setHeatmapTimeSlot(v));
  };
  ```

### C.4 step fade-out
- 파일: `frontend/src/components/chat/AgentProgressIndicator.tsx:47`
- completed step 에 `style={{ opacity: 0.5, transition: 'opacity 600ms ease' }}`.
- 위험: 완료 즉시 사라지면 사용자 인지 부족 → 0.5 유지 (0 으로 가지 X).

### C.5 PreviewCard active
- 파일: `frontend/src/components/chat/PreviewCard.tsx:189-201`
- `useState<boolean>` 추가, onClick 시 200ms 동안 active class:
  - 배경 톤 다운 (`bg-opacity-70`) + 라벨 "분석 시작...".
- ChatPanel 의 `isLoading` 이 true 가 되면 자연스럽게 다음 카드로 전환되므로 200ms 짧게.

## 재검토 (Self-Review Gate)

### 엣지케이스
- **C.1 role 미선택**: role null → default 3개 칩 fallback (이미 chatStore default).
- **C.3 rAF throttle + 사용자 키보드 화살표**: 키보드 ArrowLeft/Right 도 onChange 트리거 → throttle 일관 적용 OK.
- **C.4 transition 중 step 추가/제거**: in_progress → completed 외의 status (`failed`) 도 동일 transition 적용해야 jarring 방지.
- **C.5 200ms 짧음**: 모바일 저성능 기기에서 `isLoading` 전환이 200ms 안에 안 끝나면 active 풀린 후 ChatPanel 전환되어 빈 깜빡임 — 250ms 로 약간 늘리는 옵션 검토.

### 메모리 교훈
- `feedback_streaming_diagnose_ttft.md` — JumpFab 은 스트리밍 중에도 보여야 함. C.2 의 box-shadow 강화는 visual hierarchy 고려.

### 타 plan 충돌
- `mobile-responsive.md` 의 BottomSheet snap 처리와 C.2 JumpFab 위치 — 모바일에서 JumpFab 이 bottom sheet 핸들과 겹치지 않는지 확인 필요. 모바일 viewport 한정 추가 offset 가능.

## Scenario (E2E Ring Mapping)

| Test ID | Spec | Case |
|---------|------|------|
| `Ring1-F02-C1` | `e2e/ring1-features/f02-agent-chat.spec.ts` | 앱 첫 진입 → 3-step 가이드 + role 별 칩 3개 노출 |
| `Ring1-F02-C2` | 동상 | 스트리밍 중 위로 스크롤 → JumpFab 노출 + 가려지지 않음 |
| `Ring1-F06-C3` | `e2e/ring1-features/f06-heatmap.spec.ts` | slider 0→23 빠른 드래그 → INP < 200ms + 콘솔 warning 0 |
| `Ring1-F02-C4` | `e2e/ring1-features/f02-agent-chat.spec.ts` | tool_end 이벤트 후 step 의 opacity 0.5 로 부드럽게 전환 |
| `Ring1-F02-C5` | 동상 | PreviewCard CTA 클릭 → 200ms 안에 active class 적용 |

## Pass 반복

- **Pass 1 (happy)**: 위 5 케이스 PASS.
- **Pass 2 (엣지)**: C.1 role null + history clear / C.3 키보드 화살표 holding / C.4 failed step 동일 transition.
- **Pass 3 (성능)**: C.3 INP/LCP 측정 베이스라인 -10% 이내 / C.4 reflow count.

## Agent 모델

- 설계: opus
- 구현: sonnet (모두 single-file 단순 변경, 30분 단위)
- 검증: haiku

## Critical Files

### 수정
- `frontend/src/components/chat/MessageList.tsx` (C.1, C.2)
- `frontend/src/components/map/TimeSlider.tsx` (C.3)
- `frontend/src/components/chat/AgentProgressIndicator.tsx` (C.4)
- `frontend/src/components/chat/PreviewCard.tsx` (C.5)

### 참조
- `frontend/src/stores/chatStore.ts:107-111` (default suggestions)
- `frontend/src/components/chat/SuggestionChips.tsx` (C.1 reuse)

## Rollout 머지 순서

C.3 (성능 영향 검증) → C.4 → C.5 → C.1 → C.2 — 영향도 큰 것부터 머지하고 visual polish 마지막.
