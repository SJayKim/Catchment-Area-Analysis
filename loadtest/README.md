# MarketScope AI — Load Test Suite

## Prerequisites

```bash
cd server && pip install -e ".[loadtest]"
```

## Quick Start

```bash
# 1. Start backend in Mock + Mock LLM mode (no DB, no API cost)
USE_MOCK=true LLM_PROVIDER=mock uvicorn server.main:app --host 0.0.0.0 --port 8002

# 2. Run Locust (Web UI at http://localhost:8089)
cd loadtest
locust -f locustfile.py --host=http://localhost:8002

# 3. Headless mode (CI)
locust -f locustfile.py --host=http://localhost:8002 \
  --users 20 --spawn-rate 5 --run-time 120s --headless \
  --csv=results/run --html=results/report.html
```

## Scenarios

| File | Description | Users | Duration |
|------|-------------|-------|----------|
| `locustfile.py` | All scenarios combined | configurable | configurable |
| `scenarios/a_basic_summary.py` | Gradual ramp 1->20 | 1-20 | 4x60s |
| `scenarios/b_mixed_intent.py` | 5 intent types random | 10 | 120s |
| `scenarios/c_greeting_shortcut.py` | Greeting (agent skip) | 50 | 30s |
| `scenarios/d_semaphore_saturation.py` | Exceed semaphore(20) | 25 | 60s |
| `scenarios/e_spike.py` | Spike 5->30->5 | 5-30 | 90s |
| `scenarios/f_session_isolation.py` | Cross-session leakage check | 10 | 60s |
| `scenarios/g_client_disconnect.py` | Mid-stream disconnect | 10 | 30s |
| `scenarios/h_redis_failure.py` | Redis pause/unpause | 5 | 60s |

## Monitoring

During load tests, check backend metrics:

```bash
curl http://localhost:8002/api/health/detail | python -m json.tool
```

## Results

Results are saved to `loadtest/results/` (gitignored).
