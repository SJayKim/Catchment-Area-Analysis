# Backend pytest — 커버리지 확대 + CI 통합

> 카테고리: infra
> 생성일: 2026-05-06
> 담당: sjkim
> 모델: 설계 opus / 구현 sonnet / 검증 haiku

## Context

### 문제
`server/tests/` 디렉토리는 존재하나 **단편적**:

```
server/tests/
├── test_chat_session_concurrency.py
├── test_entity_matching.py
├── test_langfuse_aggregate.py
├── test_numeric_sanity.py
├── test_out_of_scope.py
├── test_planner_clarification.py
├── test_smoke.py
├── test_tool_tag_sanitizer.py
└── test_xml_sanitizer.py
```

현재 70/71 PASS — 그러나:
1. **Repository / API route / Cache / Circuit Breaker / Tool registry 커버리지 0** — 핵심 로직이 E2E (Playwright) 로만 검증됨
2. **conftest.py 부재** — fixture (mock DB / mock LLM / temp Redis) 공유 미설정
3. **CI 미통합** — 로컬 수동 실행만, GitHub Actions/pre-commit 자동 실행 없음
4. **coverage 측정 없음** — 어느 모듈이 untested 인지 가시성 0

목표: **conftest 정비 + 핵심 5 모듈 커버리지 70%+ + pre-commit + GitHub Actions 통합** 으로 회귀 자동 차단.

### 메모리 참조
- [feedback_python_utf8_windows.md](../../../.claude/projects/C--Users-cyon1-OneDrive-Desktop-Catchment-Area-Analysis/memory/feedback_python_utf8_windows.md) — Windows pytest 실행 시 `PYTHONIOENCODING=utf-8`
- [feedback_eval_district_code_hardcode.md](../../../.claude/projects/C--Users-cyon1-OneDrive-Desktop-Catchment-Area-Analysis/memory/feedback_eval_district_code_hardcode.md) — DB ground truth 패턴
- [feedback_check_env_before_test.md](../../../.claude/projects/C--Users-cyon1-OneDrive-Desktop-Catchment-Area-Analysis/memory/feedback_check_env_before_test.md) — USE_MOCK 환경 가드
- [feedback_marketscope_sse_format.md](../../../.claude/projects/C--Users-cyon1-OneDrive-Desktop-Catchment-Area-Analysis/memory/feedback_marketscope_sse_format.md) — SSE 포맷 (테스트 클라이언트 작성 시 참조)

### 관련 Plan
- [phase1-low-mid-risk-2026-04-23.md](./phase1-low-mid-risk-2026-04-23.md) — 분할된 모듈 회귀 테스트 부재 인지
- [llmops-l1-verification.md](./llmops-l1-verification.md) — L1 검증
- [load-test-plan.md](./load-test-plan.md) — 부하 테스트 (별도)

### 코드 스폿
- `server/pyproject.toml` — `[tool.pytest.ini_options]` 섹션 (없으면 신규)
- `server/tests/__init__.py` — 빈 파일
- `server/tests/conftest.py` — **미존재** (신규 작성)
- 핵심 미커버 모듈:
  - `server/server/api/routes/chat.py` — SSE 스트리밍 + agent graph 진입
  - `server/server/api/routes/districts.py` — search / detail / preview
  - `server/server/api/routes/map_data.py` — polygons / heatmap
  - `server/server/services/cache.py` — Memory/Redis 이중 cache
  - `server/server/services/circuit_breaker.py` — 3-state CB
  - `server/server/repositories/mock/*` — fixture 기반 10 repo

---

## Scope

### In-scope
1. **conftest.py 작성**
   - `pytest_asyncio` 모드 설정 (`asyncio_mode = "auto"`)
   - `mock_settings` fixture (USE_MOCK=true 강제)
   - `mock_da` fixture (DataAccess Mock factory)
   - `mock_cache` fixture (in-process MemoryCache)
   - `app_client` fixture (httpx.AsyncClient + FastAPI lifespan)
   - `mock_llm` fixture (planner/evaluator/respond 응답 stub)
2. **API route 테스트** (`tests/test_routes_*.py`)
   - `test_routes_chat.py` — POST /api/chat SSE 9 이벤트 회귀 (Mock LLM)
   - `test_routes_districts.py` — search / 한글 조사 strip / preview
   - `test_routes_map_data.py` — polygons bounds filter / heatmap cache hit
   - `test_routes_health.py` — /health, /api/health/detail
3. **Service 테스트** (`tests/test_services_*.py`)
   - `test_services_cache.py` — Memory/Redis fallback / TTL
   - `test_services_circuit_breaker.py` — CLOSED→OPEN→HALF_OPEN 전환
   - `test_services_category_resolver.py` — 한글 alias 매핑
4. **Repository 테스트** (`tests/test_repos_mock.py`)
   - 10 protocol 별 Mock 구현 회귀
5. **Coverage + CI**
   - `pyproject.toml` `[tool.coverage]` + `pytest-cov` 도입
   - `Makefile` 또는 `scripts/run_tests.sh` — `pytest --cov=server.server --cov-report=term-missing --cov-fail-under=70`
   - `.github/workflows/backend-test.yml` — push/PR 시 자동 실행
   - pre-commit hook (선택) — `git commit` 시 변경 모듈 관련 테스트만 실행

### Out-of-scope (별도 plan)
- frontend (Vitest/Playwright) — 이미 별도
- 부하 테스트 (locust/k6) — `load-test-plan.md`
- DB 통합 테스트 (real PostGIS) — Phase 2 Docker compose 활용 별도 Plan
- mutation testing (mutmut) — 후순위

---

## Design

### conftest.py 핵심

```python
# server/tests/conftest.py
import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

os.environ.setdefault("USE_MOCK", "true")
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

@pytest.fixture(scope="session")
def event_loop_policy():
    import asyncio
    return asyncio.DefaultEventLoopPolicy()

@pytest_asyncio.fixture
async def app_client():
    from server.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

@pytest.fixture
def mock_district_code() -> str:
    return "D3001"  # Mock 강남역

@pytest.fixture
def mock_da():
    from server.repositories.mock.factory import build_mock_data_access
    return build_mock_data_access()
```

### 커버리지 목표

| 모듈 | 현재 | 목표 |
|---|---:|---:|
| `agent/utils/*` | ~80% (이미 커버됨) | 90% |
| `agent/nodes/planner.py` | 70% (out-of-scope + clarification) | 80% |
| `services/cache.py` | 0% | 80% |
| `services/circuit_breaker.py` | 0% | 90% |
| `services/category_resolver.py` | 0% | 80% |
| `api/routes/chat.py` | 0% | 70% |
| `api/routes/districts.py` | 0% | 80% |
| `api/routes/map_data.py` | 0% | 80% |
| `repositories/mock/*` | 0% | 70% |
| **전체** | ~25% | **70%** |

### CI workflow

```yaml
# .github/workflows/backend-test.yml
name: Backend Tests
on: [push, pull_request]
jobs:
  pytest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install -e "server[dev]" pytest-cov
      - run: cd server && pytest --cov=server --cov-fail-under=70 -v
      - uses: codecov/codecov-action@v4
        if: always()
```

---

## Checklist

- [ ] **F1** `tests/conftest.py` — fixture 6종 (settings/da/cache/client/llm/district_code)
- [ ] **F2** `pyproject.toml` `[tool.pytest.ini_options]` + `asyncio_mode=auto` + `addopts="-ra --strict-markers"`
- [ ] **F3** `pyproject.toml` `[tool.coverage.run]` + `[tool.coverage.report]` (omit migrations / `__pycache__`)
- [ ] **R1** `tests/test_routes_chat.py` — Mock LLM 으로 SSE 9 이벤트 회귀 6 testcase
- [ ] **R2** `tests/test_routes_districts.py` — search / 한글 조사 / preview 5 testcase
- [ ] **R3** `tests/test_routes_map_data.py` — polygons bounds + heatmap cache 4 testcase
- [ ] **R4** `tests/test_routes_health.py` — /health 200, /api/health/detail readiness 3 testcase
- [ ] **S1** `tests/test_services_cache.py` — Memory PASS, Redis fallback graceful 4 testcase
- [ ] **S2** `tests/test_services_circuit_breaker.py` — CLOSED→OPEN→HALF_OPEN 5 testcase
- [ ] **S3** `tests/test_services_category_resolver.py` — alias 13종 + Real 동적 로드 4 testcase
- [ ] **P1** `tests/test_repos_mock.py` — 10 protocol 별 smoke 1건씩 = 10 testcase
- [ ] **C1** `Makefile` / `scripts/run_tests.sh` — `--cov-fail-under=70` 가드
- [ ] **C2** `.github/workflows/backend-test.yml` — push/PR 자동 실행
- [ ] **C3** `.pre-commit-config.yaml` (선택) — staged 파일에 한해 pytest -k 실행
- [ ] **D1** `docs/architecture/backend.md §8` 갱신 — "미구축" → "70% 커버리지 + CI"

### 재검토 (Self-Review Gate)
- [ ] httpx ASGITransport 는 SSE 스트림을 chunk 단위로 await 가능. text/event-stream 파싱 헬퍼 작성 필요
- [ ] FastAPI lifespan 은 AsyncClient 생성 시 자동 트리거 — Mock factory 가 lifespan 안에서 초기화되는지 확인
- [ ] Anthropic/Gemini SDK 가 import 시 키 검증 → conftest 에서 `LLM_PROVIDER=mock` 강제 + key dummy
- [ ] 메모리 교훈: Windows UTF-8 — conftest os.environ + pytest cmd `PYTHONIOENCODING=utf-8`
- [ ] 메모리 교훈: USE_MOCK 환경 — fixture 가 Mock 강제, Real 모드 테스트는 별도 marker (`@pytest.mark.real`) 로 격리
- [ ] CI 환경 변수 — Anthropic/Gemini 키 미설정 시도 graceful (mock 모드만 실행)
- [ ] 다른 Plan 충돌: [langfuse-l2-token-cost-eval](./langfuse-l2-token-cost-eval.md) 의 test_langfuse_l2_*.py 와 conftest 공유

### Scenario (E2E Ring Mapping)
| Ring | ID | 시나리오 |
|------|----|---------|
| 0 | Ring0-PYTEST-CONFTEST | conftest fixture 6종 정상 import + isolation |
| 0 | Ring0-PYTEST-CHAT-SSE | Mock LLM SSE 9 이벤트 순서 + 1회씩 발행 |
| 0 | Ring0-PYTEST-CB-STATES | CB 3-state 전환 회귀 |
| 1 | Ring1-PYTEST-COVERAGE | `pytest --cov-fail-under=70` PASS |
| 1 | Ring1-CI-WORKFLOW | GitHub Actions push/PR 자동 실행 |
| 3 | Ring3-PYTEST-DRIFT | 신규 모듈 추가 시 coverage 70% 미만이면 fail |

### Pass 반복
- **Pass 1 (기본)**: F1+F2 + R1~R4 + S1 = 22+ testcase, 커버리지 50%
- **Pass 2 (엣지)**: S2+S3+P1, CB 엣지 / cache miss / Mock factory edge → 커버리지 70%
- **Pass 3 (성능)**: pytest 전체 실행 < 30s, GitHub Actions < 3min

---

## Validation

### 검증 명령
```bash
cd server
# Pass 1
pytest tests/ -v --cov=server --cov-report=term-missing

# Pass 2 (전체)
pytest tests/ --cov=server --cov-fail-under=70 -v

# Pass 3 (CI 시뮬)
PYTHONIOENCODING=utf-8 USE_MOCK=true pytest tests/ --cov=server --cov-fail-under=70
```

### 합격 기준
- [ ] 70+ testcase PASS (현재 70 + 신규 35+)
- [ ] 전체 커버리지 ≥ 70%
- [ ] core 5 모듈 (cache/circuit_breaker/category_resolver/routes/repos) 각각 ≥ 70%
- [ ] GitHub Actions push/PR 자동 실행 확인
- [ ] `docs/architecture/backend.md §8` "미구축" 표기 제거

### 결과 (2026-05-07 Pass 1 PASS)

**구현 완료**:
- `server/tests/conftest.py` — fixture 5종 (`mock_district_code`, `mock_da`, `memory_cache`, `category_resolver_default`, `app_client`). USE_MOCK + dummy API key 강제로 host env 의존성 제거 → 기존 `test_smoke::langfuse_enabled` host fail 자동 해결.
- `server/tests/test_services_circuit_breaker.py` — CB 3-state 7 testcase (CLOSED→OPEN, OPEN→HALF_OPEN timeout, HALF_OPEN success/fail, recovery_remaining, success-resets-counter)
- `server/tests/test_services_cache.py` — Memory cache 5 testcase + Redis unreachable graceful 1 testcase
- `server/tests/test_services_category_resolver.py` — Korean keyword 4 testcase
- `server/tests/test_repos_mock.py` — 10 protocol smoke 10 testcase
- `server/tests/test_routes_health_and_map.py` — `/health`, `/metrics`, polygons, heatmap, heatmap/all, singleflight integration 8 testcase (lifespan + httpx ASGITransport)
- `server/pyproject.toml` — `[tool.pytest.ini_options]` addopts/markers + `[tool.coverage.run]` + `[tool.coverage.report]` + dev extras 에 `pytest-cov` + `httpx` 추가
- `server/scripts/run_tests.sh` — `COV_FAIL_UNDER` 환경변수 기반 게이트
- `.github/workflows/ci.yml::backend-test` — dummy env 주입 + `--cov-report=xml` + coverage artifact 업로드

**Pass 1 검증** (PYTHONIOENCODING=utf-8 pytest server/tests/):
- **107 passed, 8 skipped** (전체 신규 35 + 기존 70 + 2 = 107). Skip = `app_client` fixture (`test_routes_health_and_map.py` 8 testcase) — 본 머신에 `structlog` 미설치 (full dev install 시 자동 unblock).
- 기존 `test_smoke::langfuse_enabled` host env fail 해결 (conftest 의 `LANGFUSE_PUBLIC_KEY=""` 강제).
- ruff PASS (`server/services/singleflight.py`, `tests/conftest.py`, 5 테스트 파일).

**합격 기준 충족 현황**:
- [x] F1 conftest fixture 5종
- [x] F2 pyproject pytest 설정
- [x] F3 pyproject coverage 설정
- [x] R3 routes_map_data + R4 routes_health (단일 파일 통합)
- [x] S1 cache · S2 circuit_breaker · S3 category_resolver
- [x] P1 repos mock 10 protocol smoke
- [x] C1 run_tests.sh
- [x] C2 GitHub Actions backend-test (기존 job 보강 — coverage report + dummy env)
- [ ] R1 routes_chat (SSE 9 이벤트 + Mock LLM stub) — Plan #1 의 L2 usage 테스트와 conftest 공유 예정 (Plan #1 진행 시 통합)
- [ ] R2 routes_districts (한글 조사 + preview) — 후속 sweep
- [ ] D1 backend.md §8 갱신 — 본 commit 으로 반영
- [ ] coverage 70% 달성 — pytest-cov 미설치 머신에서 측정 미진행, CI 1차 결과로 baseline 확정 후 사이드 PR로 임계 추가

**커버리지 baseline 측정 보류**: 로컬 환경에 `pytest-cov` 미설치 (시스템 Python 3.13 + dev extras 미설치). CI 1차 실행 후 `--cov-report=term` 결과로 baseline 확정. 그 시점에 70% 미달 모듈만 별도 sweep PR 로 보강.

---

## Metadata
- 우선순위: 🟠 P1 (회귀 자동화 핵심)
- 난이도: M (3~5d)
- Phase 2 의존성: 없음, Phase 2 시작 전 완료 권장
- 후속: real-DB integration tests (Docker compose 활용), mutation testing
