# QA

| 문서 | 내용 |
|---|---|
| [test-plan.md](test-plan.md) | E2E 4-ring 테스트 플랜 (Ring 0 preflight / Ring 1 features / Ring 2 journeys / Ring 3 negative) |
| [runs/](runs/) | 날짜별 실행 리포트 (최근 실행만 유지) |

## Ring 개요

- **Ring 0** (1 spec): 인프라 sanity — docker 스택 부팅 + Mock/Real 양쪽 접근성
- **Ring 1** (10+1 spec): 기능별 동작 — f01~f10 + m01 (Mock data)
- **Ring 2** (5 spec): 사용자 여정 — j01 first-time / j02 comparison / j03 risk-first / j04 recovery / j05 pdf-stakeholder
- **Ring 3** (4 spec): 부정 케이스 — no-district / prompt-injection / p0-regression / reg-<날짜>

## 실행

```bash
cd frontend && npm test              # 전체 Playwright E2E
cd frontend && npx playwright test ring1-features/  # Ring 1 만
```

또는 `/e2e-run <ring>` 스킬 (USE_MOCK preflight 포함, 수동 호출만).
