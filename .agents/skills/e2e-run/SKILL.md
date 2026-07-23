---
name: e2e-run
description: Ring 0~3 E2E 실행. USE_MOCK preflight + 백엔드 health + 아티팩트 저장 자동화.
user-invocable: true
disable-model-invocation: true
allowed-tools: Bash, Read, Write
---

## 입력

`$ARGUMENTS = <ring-number>` (0 / 1 / 2 / 3)

## 절차

### 1. Preflight (실패 시 즉시 abort)

```bash
echo "USE_MOCK=$USE_MOCK"
[ -z "$USE_MOCK" ] && echo "ABORT: USE_MOCK 미설정" && exit 1
curl -sf http://localhost:8000/health || { echo "ABORT: backend 미기동"; exit 1; }
```

헬스는 루트 `/health` (main.py `@app.get("/health")`) — `/api/health` 라우트는 없음(404). 상세 readiness 는 `/api/health/detail`.

건너뛰지 말 것 ([[feedback_check_env_before_test]] 교훈): USE_MOCK 불일치 시 Mock(D3001) vs Real(3120189) district code 로 전체 tool 실패.

### 2. 실행

```bash
cd frontend && npm run test:e2e:ring$ARGUMENTS
```

### 3. 아티팩트 수집

```bash
DIR="docs/qa/runs/$(date +%Y-%m-%d)-ring$ARGUMENTS"
mkdir -p "$DIR"
cp -r frontend/playwright-report "$DIR/" 2>/dev/null || true
cp -r frontend/test-results "$DIR/" 2>/dev/null || true
```

### 4. 보고

```
Ring <N> E2E Run:
- USE_MOCK: <value>
- Pass/Fail: <P>/<F>
- Failed IDs: <list>
- Artifacts: <path>
```

## 완료 기준
- 아티팩트 경로 출력 + 종합 verdict.

## 주의

- `disable-model-invocation: true` — Codex 자동 호출 차단. 사용자가 `/e2e-run 1` 직접 입력해야 실행.
- Playwright SSE route 가로채기 금지 — 직접 backend POST 로 SSE 를 수집할 것 ([[feedback_playwright_sse_capture]] 교훈).
