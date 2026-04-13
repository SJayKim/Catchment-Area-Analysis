# Plan — 구현 계획

기능 구현/버그 수정/인프라 구성 등 모든 구현 계획 문서를 카테고리별로 분류.

## 카테고리

```
plan/
├── phase/              Phase 1/1B/2/3 로드맵
├── fix/                버그 수정, 리팩토링, P0 이슈
├── infra/              Docker, 문서 재구조화, E2E 인프라
├── data/               데이터 소스, 마이그레이션, 출처
├── ui/                 카드 UI, 다크 테마, 스트리밍 UX
├── business/           커머셜라이제이션
└── agent-improvement/  Agent 고도화 단계별 계획 (00~10)
```

## 주요 계획 문서

| 카테고리 | 문서 | 내용 |
|---|---|---|
| Phase | [phase/phase-1-implementation.md](phase/phase-1-implementation.md) | Phase 1 MVP 구현 계획 |
| Phase | [phase/phase-1b-implementation.md](phase/phase-1b-implementation.md) | Phase 1B Real Data 연결 종합 |
| Phase | [phase/phase-2-implementation.md](phase/phase-2-implementation.md) | Phase 2 Premium 기능 |
| Phase | [phase/phase-3-implementation.md](phase/phase-3-implementation.md) | Phase 3 확장 |
| Fix | [fix/p0-critical-fix-plan.md](fix/p0-critical-fix-plan.md) | P0 치명 이슈 수정 |
| Fix | [fix/refactoring-plan.md](fix/refactoring-plan.md) | 리팩토링 |
| Infra | [infra/docker-integration-plan.md](infra/docker-integration-plan.md) | Docker 통합 |
| Infra | [infra/docs-restructure-plan.md](infra/docs-restructure-plan.md) | 본 문서 재구조화 |
| Data | [data/data-preparation.md](data/data-preparation.md) | 데이터 수집/준비 |
| Business | [business/commercialization-plan.md](business/commercialization-plan.md) | 커머셜라이제이션 |
| Agent | [agent-improvement/00-overview.md](agent-improvement/00-overview.md) | Agent 고도화 개요 |

## 네이밍 규칙

- 모든 파일은 `kebab-case.md`
- Phase 관련: `phase-<n>-<keyword>.md`
- Fix 관련: `<target>-fix-plan.md` 또는 `<topic>-plan.md`
