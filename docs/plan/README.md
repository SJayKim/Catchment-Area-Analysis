# Plan — 구현 계획

**진행 중 / 대기 상태의 구현 계획만** 카테고리별로 보관한다. 완료된 plan 은 **git history 로 이관하고 트리에서 제거**한다
(2026-07-07 docs diet 정책 — 완료 이력은 `git log` + [../status/current-status.md](../status/current-status.md) "이력 요약"으로 복원).
진행/대기 상태의 단일 마스터는 [../status/current-status.md](../status/current-status.md) 의 "미결/블로커" + "Next Items".

## 카테고리 (현재 활성 plan)

| 카테고리 | 내용 | 활성 문서 |
|---|---|---|
| business/ | 상용화 / 비즈니스 | [commercialization-plan.md](business/commercialization-plan.md) — Phase 2 로드맵 (미착수) |
| fix/ | 버그 / 정확도 hotfix | — (현재 활성 없음) |
| infra/ | 배포 / 안정성 / 관측성 / refactoring | [pass3-live-activation-2026-07-16](infra/pass3-live-activation-2026-07-16.md) · [llm-gateway-openai-2026-07-08](infra/llm-gateway-openai-2026-07-08.md) · [auto-deploy-on-push](infra/auto-deploy-on-push.md) · [v2-stream-final-option-b](infra/v2-stream-final-option-b-2026-07-06.md) · [langfuse-ops-hardening](infra/langfuse-ops-hardening-2026-07-06.md) · [langfuse-l2-token-cost-eval](infra/langfuse-l2-token-cost-eval.md) · [phase1-low-mid-risk](infra/phase1-low-mid-risk-2026-04-23.md) · [apps-in-toss-deploy](infra/apps-in-toss-deploy.md) · [docs-code-sync-2026-07-16](infra/docs-code-sync-2026-07-16.md) |
| qa/ | QA sweep / E2E 회귀 | [ux-final-e2e-regression-plan.md](qa/ux-final-e2e-regression-plan.md) |

## Plan 작성 규칙

새 Plan 은 5 섹션 구조를 따를 것 (`/plan-new <category> <name>` 스킬 사용):

1. **Checklist** — 원자적이고 검증 가능한 항목
2. **재검토 (Self-Review Gate)** — 엣지케이스 / 메모리 교훈 / 타 Plan 충돌
3. **Scenario (E2E Ring Mapping)** — Ring 0~3 매핑, `<RING>-<FEATURE>-<CASE>`
4. **Pass 반복** — Pass 1(기본) / Pass 2(엣지) / Pass 3(성능)
5. **Agent 모델 선택** — 설계 opus / 구현 sonnet / 검증 haiku

## 완료 처리

- 구현이 완료되면 plan 파일은 **git history 로 이관 후 트리에서 제거** (docs diet 정책, 2026-07-07)
- 상태 요약은 [../status/current-status.md](../status/current-status.md) 의 "이력 요약" 에 1행 반영
- 교훈이 있으면 auto memory (`feedback_*` 항목) 에 저장 (자동 훅이 처리)
