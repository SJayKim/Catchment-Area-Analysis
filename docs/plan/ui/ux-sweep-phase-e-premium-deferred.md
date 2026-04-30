# UX Sweep — Phase E · Premium 의존 (Deferred, 코드 변경 0)

> 시리즈: **UX Sweep 2026-04-30** (38건 점검 → 6 phase 분할)
> 본 phase 영역: Phase 2 OAuth/결제/Tier 게이팅 의존 항목 3건 · 코드 변경 0
> 타 phase: [A Quick Wins](ux-sweep-phase-a-trust-legal.md) · [B 핵심 막힘](ux-sweep-phase-b-core-blockers.md) · [C 자연스러움](ux-sweep-phase-c-polish.md) · [D A11y/마감](ux-sweep-phase-d-a11y.md) · [F Tier hook](ux-sweep-phase-f-tier-hook.md)

## Context

본 phase 는 **차단 사유 + 선행 요건 명시만**. 점검 결과 발견된 3건이 Phase 2 (OAuth/결제/Tier 게이팅) 인프라 없이는 완성도 있게 구현 불가. 임시 조치로 일부 보강 가능 항목은 별도 표시.

## Checklist

- [ ] **E.1** F06 평일/주말 토글 — 백엔드 ETL 확장 후 [defer]
- [ ] **E.2** F09 SimulationCard What-If 입력 UI — `/api/simulate` 입력 파라미터 확장 후 [defer]
- [ ] **E.3** FreeLimitSurvey 트리거 + Premium CTA — 결제 wiring 후 활성화 [defer]

## 차단 사유 / 선행 요건

### E.1 F06 평일/주말 토글
- **차단**: 백엔드 `/api/heatmap/all` 응답이 시간 차원만. weekday/weekend 컬럼 노출 X.
- **선행 요건**:
  1. `floating_population` 테이블 weekday/weekend 컬럼 활용 ETL 변경.
  2. `server/server/repositories/real/heatmap_repository.py` 시그니처 확장.
  3. `frontend/src/lib/api.ts::fetchHeatmap` 파라미터 추가.
  4. F06 spec 업데이트 (`docs/spec/features/F06-heatmap.md`).
- **임시 조치 가능** (defer 아님): TimeSlider 에 "평일 데이터 (서울 평균)" 라벨만 추가 → Phase D 에 포함 가능. 단 사용자 기대 vs 실제 데이터 정합 명시 필요.

### E.2 F09 SimulationCard What-If
- **차단**: SimulationCard 는 read-only display. What-If 는 form 컴포넌트가 카드/sidebar 로 필요.
- **선행 요건**:
  1. 백엔드 `/api/simulate` 가 `unit_price`, `target_revenue`, `competitor_count` 등 입력 파라미터 전체를 받도록 확장.
  2. F09 spec § What-If 절 구체화 (`docs/spec/features/F09-revenue-simulation.md`).
  3. 사이드바 또는 모달 UI 디자인 결정.
  4. Premium tier 게이팅 (Phase 2 의존).
- **임시 조치 없음** — read-only 카드 그대로 유지.

### E.3 FreeLimitSurvey 트리거 + Premium CTA
- **현황**: `app/app/page.tsx:74,91` 에서 `messageCount >= DAILY_FREE_LIMIT` (5) 시 노출.
- **차단**: Free tier 자체가 미구현 — DAILY_FREE_LIMIT 가 임의값이고 backend rate-limit 과 무관. 설문은 노출되지만 사용자가 5회 보낸 후 계속 사용 가능.
- **선행 요건**:
  1. Phase 2 OAuth + 결제 wiring (`docs/plan/business/commercialization-plan.md`).
  2. backend `/api/chat` rate-limit 을 tier 별 차등 적용.
  3. `mood >= 4` 시 노출되는 "Premium 9,900원" UI 의 결제 페이지 라우트 신설.
- **임시 결정**:
  - 트리거 자체는 유지 (UX 피드백 수집 가치).
  - **Premium CTA UI 는 결제 wiring 전까지 A/B test off** 권장 (사용자가 클릭하면 404 또는 대기 페이지로 빠지므로).
  - 환경변수 `NEXT_PUBLIC_PREMIUM_CTA_ENABLED=false` 추가해 toggle.

## 재검토 (Self-Review Gate)

### 엣지케이스
- **E.1 임시 라벨**: "평일 데이터" 표기가 실제 데이터 (서울 평균) 와 정합하지 않으면 사용자 오해. spec 변경 전까지는 라벨 추가 자체 보류 권장.
- **E.3 Premium CTA toggle**: env 미설정 시 default off 강제 (fallback `'false'`).

### 메모리 교훈
- `project_sales_quarterly_unit.md` — F09 What-If 입력 시 매출 단위 일관성 (분기 누적 vs 월 환산) 주의.

### 타 plan 충돌
- `commercialization-plan.md` (Phase 2) 와 정합. 본 phase 가 그 의존 표면을 미리 식별.

## Scenario (E2E Ring Mapping)

본 phase 는 코드 변경 0 → E2E 테스트 추가 없음. 단:

| Test ID | Spec | Case |
|---------|------|------|
| `Ring1-F12-E3` | `e2e/ring1-features/f12-feedback.spec.ts` | `NEXT_PUBLIC_PREMIUM_CTA_ENABLED=false` 시 mood ≥ 4 응답에도 Premium CTA 미노출 |

(E3 의 toggle env 만 추가한다면 단 하나의 spec 보강.)

## Pass 반복

본 phase 는 코드 변경 0. Pass 개념 없음. **Phase 2 시작 시 본 phase 의 선행 요건 체크리스트를 그대로 다시 체크**.

## Agent 모델

본 phase 는 사양 정리만 — agent 모델 선택 N/A.

## Critical Files (Phase 2 시작 시 변경 대상)

### 백엔드 (Phase 2)
- `server/server/repositories/real/heatmap_repository.py` (E.1)
- `server/server/api/routes/map_data.py` (E.1)
- `server/server/agent/tools/simulate_revenue.py` (E.2)
- `server/server/api/routes/simulate.py` 또는 chat.py 안의 simulate 헬퍼 (E.2)

### 프론트 (Phase 2)
- `frontend/src/components/map/TimeSlider.tsx` (E.1 토글 UI)
- `frontend/src/components/chat/cards/SimulationCard.tsx` + 신규 `WhatIfPanel.tsx` (E.2)
- `frontend/src/components/feedback/FreeLimitSurvey.tsx` (E.3)
- `frontend/src/app/app/page.tsx` (E.3 trigger 조건)
- `frontend/.env.example` 또는 `.env.production` (E.3 `NEXT_PUBLIC_PREMIUM_CTA_ENABLED`)

### 참조
- `docs/plan/business/commercialization-plan.md` — Phase 2 마스터 plan.
- `docs/spec/features/F06-heatmap.md`, `F09-revenue-simulation.md` — spec 업데이트 대상.

## Rollout

본 phase 는 머지 대상 없음. **Phase 2 OAuth/결제/Tier 게이팅 머지 시점에 본 문서를 다시 참조해 E.1~E.3 항목을 한 번에 처리**.
