# Plan — 구현 계획

구현 계획 문서를 카테고리별로 보관한다. **완료된 plan 도 의사결정·이력 기록으로 삭제하지 않고 유지**한다
(2026-07-04 문서 정합성 감사: 기존 "완료 plan 은 제거" 원칙은 실제 운용과 달라 폐기 — 현재 60+ 문서 잔존이 정상 상태).
진행/대기 상태의 단일 마스터는 [../status/current-status.md](../status/current-status.md) 의 "Next Items".

## 카테고리

| 카테고리 | 내용 | 대표 문서 |
|---|---|---|
| business/ | 상용화 / 비즈니스 | [commercialization-plan.md](business/commercialization-plan.md) — Phase 2 로드맵 (미착수) |
| docs/ | 문서 / 학습 자료 계획 | [learning-materials.md](docs/learning-materials.md) |
| fix/ | 버그 / 정확도 hotfix | data-reliability, s7-coref, deferred-backlog … |
| infra/ | 배포 / 안정성 / 관측성 / refactoring | auto-deploy-on-push, [load-test-plan.md](infra/load-test-plan.md) … |
| qa/ | QA sweep / E2E 회귀 / accuracy eval | ux-final-e2e-regression-plan, accuracy-eval … |
| ui/ | UX Sweep / 랜딩 / 모바일 | ux-sweep-phase-{a~f}, mobile-responsive … |

## Plan 작성 규칙

새 Plan 은 5 섹션 구조를 따를 것 (`/plan-new <category> <name>` 스킬 사용):

1. **Checklist** — 원자적이고 검증 가능한 항목
2. **재검토 (Self-Review Gate)** — 엣지케이스 / 메모리 교훈 / 타 Plan 충돌
3. **Scenario (E2E Ring Mapping)** — Ring 0~3 매핑, `<RING>-<FEATURE>-<CASE>`
4. **Pass 반복** — Pass 1(기본) / Pass 2(엣지) / Pass 3(성능)
5. **Agent 모델 선택** — 설계 opus / 구현 sonnet / 검증 haiku

## 완료 처리

- 구현이 완료돼도 plan 파일은 **유지** (당시 판단의 기록 — 삭제 금지)
- 상태 요약은 [../status/current-status.md](../status/current-status.md) 에 반영
- 교훈이 있으면 auto memory (`feedback_*` 항목) 에 저장 (자동 훅이 처리)
