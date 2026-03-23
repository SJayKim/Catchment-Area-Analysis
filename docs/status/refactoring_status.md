# MarketScope AI 서비스 분리 리팩토링 — 진행 상황

## 전체 진행률: 7/7 Phase 완료

| Phase | 대상 | 상태 | 완료일 | 파일 수 |
|-------|------|------|--------|---------|
| 1. common | 공유 라이브러리 | **완료** | 2026-03-23 | 27 |
| 2. mcp | MCP 도구 서버 | **완료** | 2026-03-23 | 39 |
| 3. agent | Agent/Engine | **완료** | 2026-03-23 | 40 |
| 4. api | REST API | **완료** | 2026-03-23 | 6 |
| 5. pipeline | 데이터 수집 | **완료** | 2026-03-23 | 15 |
| 6. docker | Docker 인프라 | **완료** | 2026-03-23 | 4 |
| 7. tests | 테스트 재편 | **완료** | 2026-03-23 | 12 |

## 패키지 현황

### marketscope-common (v0.1.0) — 완료
- 위치: `marketscope/common/`
- 내용: config, constants, exceptions, logging, models(5), db(3), cache(1), broker(1), monitoring(6)
- 의존: pydantic, sqlalchemy, redis, langgraph, structlog, prometheus-client, langfuse

### marketscope-mcp (v0.1.0) — 완료
- 위치: `marketscope/mcp/`
- 내용: 9개 MCP 서버 (maps, google_maps, naver_maps, public_data, finance, real_estate, news, regulatory, database)
- 의존: fastapi, uvicorn, pydantic, httpx, asyncpg (독립, common 불필요)

### marketscope-agent (v0.1.0) — 완료
- 위치: `marketscope/agent/`
- 내용: agents(19), graph(4), engine(4), services(2), llm(3), memory(5), tools(3)
- 의존: marketscope-common, langgraph, langchain-core, litellm, httpx, redis, structlog

### marketscope-api (v0.1.0) — 완료
- 위치: `marketscope/api/`
- 내용: main.py, deps.py, routes/analysis.py, routes/health.py
- 의존: marketscope-common, fastapi, uvicorn, prometheus-client, sse-starlette
- Agent 직접 의존 없음 (Redis Broker 통신), health.py에서 optional try/except 참조만

### marketscope-pipeline (v0.1.0) — 완료
- 위치: `marketscope/pipeline/`
- 내용: pipeline(main, __main__), collectors(base, kosis, semas, seoul), preprocessors(code_mapper, coordinate_transformer, missing_handler, outlier_detector), scheduler(jobs)
- 의존: marketscope-common, httpx, sqlalchemy, asyncpg, apscheduler, pyproj

## 워크스페이스 설정
```toml
[tool.uv.workspace]
members = ["common", "mcp", "agent", "api", "pipeline"]

[tool.uv.sources]
marketscope-common = { path = "common", editable = true }
marketscope-mcp = { path = "mcp", editable = true }
marketscope-agent = { path = "agent", editable = true }
marketscope-api = { path = "api", editable = true }
marketscope-pipeline = { path = "pipeline", editable = true }
```

## 호환성
- 기존 `app.*` import 경로 모두 동작 (shim 레이어)
- 모든 Phase 완료 후 shim 제거 및 `app/` 디렉토리 삭제 예정

## Docker 인프라 (Phase 6 완료)

### Dockerfile
- 워크스페이스 전체 설치: `pip install -e common/ -e mcp/ -e agent/ -e api/ -e pipeline/`
- 2단계 캐시 전략: pyproject.toml 먼저 복사 → 소스 복사
- 기본 CMD: `uvicorn marketscope_api.main:app`

### docker-compose.yml (16 서비스)
| 서비스 | 명령어 | 포트 |
|--------|--------|------|
| marketscope-api | `uvicorn marketscope_api.main:app` | 8000 |
| marketscope-engine | `python -m marketscope_agent.engine` | 9100 |
| marketscope-pipeline | `python -m marketscope_pipeline` | - |
| mcp-* (9개) | `uvicorn marketscope_mcp.{name}.server:app` | 5100-5108 |
| postgres | postgis/postgis:15-3.4 | 5432 |
| redis | redis:7-alpine | 6379 |
| prometheus | prom/prometheus:v3.4.0 | 9090 |
| grafana | grafana/grafana:11.6.0 | 3000 |

## 테스트 (Phase 7 완료)
- 12개 파일 (conftest.py + 10 unit + 1 integration) import 변환 완료
- 98 tests passed, 0 failed
- `app.*` 참조 0건 (테스트 코드 내)

## 다음 작업: 호환성 shim 제거
- 모든 Phase 완료 — `app/` 디렉토리의 shim 파일 제거 가능
- 외부 참조 확인 후 `app/` 디렉토리 삭제
