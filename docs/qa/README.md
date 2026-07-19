# QA

| 문서 | 내용 |
|---|---|
| [test-plan.md](test-plan.md) | E2E 4-ring 테스트 플랜 (Ring 0 preflight / Ring 1 features / Ring 2 journeys / Ring 3 negative) |
| [runs/](runs/) | 분석 품질 eval 리포트 (최신만 유지) — `eval-round4-2026-07-04/`(GATE PASS 4/4 · 평균 10.0) · `eval-stream-b-2026-07-06/`(스트리밍 옵션 B 재판정 fresh 10.0) |

## Ring 인벤토리 (2026-07-16 실측 — spec 44파일 · test 선언 188개)

- **Ring 0** (4 spec · 18 선언): 인프라 sanity — 00-stack-up · 02-error-boundary · 03-tier-hook · stats-aggregate(Langfuse 집계 회귀)
- **Ring 1** (25 spec · 99 선언): 기능별 동작 — f01~f10 · m01 · f11-landing · f12-feedback · a11y · d-perf · d9-bottomnav · phase-b/c-ux-sweep · preview-api · mobile-sheet-open 등
- **Ring 2** (6 spec · 13 선언): 사용자 여정 — j01~j05 + j06-ux-a2f-integration
- **Ring 3** (7 spec · 35 선언): 부정/회귀 — neg-no-district · neg-prompt-injection · neg-feedback-missing · ops-endpoints · l1-langfuse(E02/E03 v3 — active 7 + skip 4) · p0-regression · reg-2026-04-17
- **기타**: prod-smoke (1 spec · 11 선언, active 9 + skip 2 — 외부 도메인 smoke) · 레거시 루트 phase3-scenario (1 spec · 12 선언)

> 실행 케이스 수는 Playwright project 4종(chromium/mobile-iphone/mobile-galaxy/tablet-ipad) 곱 + 런타임 skip 으로 가변.

## 실행

```bash
cd frontend && npm run test:e2e             # 전체 (⚠ `npm test` 스크립트는 없음)
cd frontend && npm run test:e2e:ring1       # 링별 (ring0~ring3)
```

또는 `/e2e-run <ring>` 스킬 (USE_MOCK preflight 포함, 수동 호출만). Mock(D3001…) vs Real(3110032…) district code 가 다르므로 실행 전 USE_MOCK 상태 확인.
