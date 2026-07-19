# MarketScope AI

## Architecture map

- `frontend/`: Next.js 14 App Router, TypeScript, Zustand, Kakao Maps/deck.gl, Playwright.
- `server/server/`: FastAPI package. The default v2 agentic loop and Trust Kernel live under `agent/loop/`; `agent/graph.py` is the legacy PAE fallback.
- `server/alembic/`: database migrations; `scripts/`: operations, ETL, deployment, and eval utilities.
- Read only the relevant architecture page first: `docs/architecture/{overview,backend,frontend,agent,data,deployment}.md`. Feature contracts are indexed by `docs/spec/feature-list.md`; current truth is `docs/status/current-status.md`.

## Commands

```bash
# full development stack
docker compose up -d

# backend
cd server
pip install -e ".[dev]"
pytest
ruff check .
ruff format --check .
mypy server

# frontend
cd frontend
npm install
npm run lint
npx tsc --noEmit
npm run build
npm run test:e2e:ring0
```

Use the Playwright CLI and repository E2E scripts for browser flows. Confirm `USE_MOCK` before tests: mock supports D3001-D3005; real mode expects the 1,650-district dataset. Health is `/health`; detailed readiness is `/api/health/detail`.

## Critical invariants

- Never edit `.env`, `.env.e2e`, credentials, keys, or certificates. `.env.example` and templates may be documented without real values.
- SSE events carry `type` inside the JSON in each `data:` payload; do not use an `event:`-line-dependent parser.
- Trust Kernel binds every numeric response to tool output within ±5%, allows one correction pass, then masks unsupported values as `[미확인]` or uses the grounded fallback.
- `estimated_sales.monthly_sales` stores quarterly accumulated sales from Seoul data; repositories convert it to monthly values before returning it.
- Python file I/O must specify UTF-8. Keep Python 3.12 type hints and ruff line length 120.
- Preserve `USE_MOCK` repository boundaries and Redis memory fallback. Mock LLM cannot tool-call and therefore uses the legacy PAE path.
- React keys must be unique per event instance, not only per event/tool type.
- New or changed behavior needs the matching feature acceptance criteria, status update, and E2E ring scenario when applicable.

## Verification

- Backend changes: `cd server && ruff check . && ruff format --check . && pytest` plus `mypy server` for typed surfaces.
- Frontend changes: `cd frontend && npm run lint && npx tsc --noEmit && npm run build`.
- Cross-layer changes: run the smallest relevant Playwright ring through `$e2e-run`; capture artifacts under `docs/qa/runs/`.
- Database changes: verify Alembic head/current and district data separately; migrations create schema, while ETL/seed loads the 1,650 districts.

