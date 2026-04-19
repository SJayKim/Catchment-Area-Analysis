# Plan — 구현 계획

현재 **진행 중**이거나 **착수 대기** 중인 계획만 보관. 완료된 plan 은 git history 에 남기고 이 디렉토리에서 제거한다.

## 현재 계획

| 카테고리 | 문서 | 상태 |
|---|---|---|
| business | [commercialization-plan.md](business/commercialization-plan.md) | Phase 2 상용화 로드맵 (OAuth2 / 결제 / Tier 게이팅) |
| infra | [e2e-regression-plan-2026-04-19.md](infra/e2e-regression-plan-2026-04-19.md) | 2026-04-19 회귀 테스트 플랜 |
| infra | [load-test-plan.md](infra/load-test-plan.md) | 동시 사용자 부하 테스트 (미착수) |

## Plan 작성 규칙

새 Plan 은 5 섹션 구조를 따를 것 (`/plan-new <category> <name>` 스킬 사용):

1. **Checklist** — 원자적이고 검증 가능한 항목
2. **재검토 (Self-Review Gate)** — 엣지케이스 / 메모리 교훈 / 타 Plan 충돌
3. **Scenario (E2E Ring Mapping)** — Ring 0~3 매핑, `<RING>-<FEATURE>-<CASE>`
4. **Pass 반복** — Pass 1(기본) / Pass 2(엣지) / Pass 3(성능)
5. **Agent 모델 선택** — 설계 opus / 구현 sonnet / 검증 haiku

## 완료 처리

- 구현이 완료되면 **이 디렉토리에서 파일 삭제**
- 상태 요약은 [../status/current-status.md](../status/current-status.md) 에 반영
- 교훈이 있으면 `memory/feedback_*.md` 에 저장 (자동 훅이 처리)
