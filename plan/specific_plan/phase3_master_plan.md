# Phase 3 상세 구현 계획 — 로깅 & 모니터링

> 최종 업데이트: 2026-03-21
> 상태: 🟡 구현 대기
> 상위 문서: `plan/phase/phase3.md`

---

## S1: structlog 전환 + Langfuse 활성화

### S1-1. structlog 파이프라인 구축

#### 의존성 추가
- `pyproject.toml`에 `structlog >= 24.1.0` 추가

#### `app/logging_config.py` 재작성

기존 `StructuredFormatter` + stdlib 기반 로깅을 structlog로 교체한다.

```python
"""구조화 로깅 설정 — structlog 기반."""
import logging
import sys
import structlog
from app.config import get_settings

def setup_logging(level: str = "DEBUG") -> None:
    settings = get_settings()
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.app_env.value == "production":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.DEBUG))
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    if root.handlers:
        root.handlers.clear()
    root.addHandler(handler)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(f"marketscope.{name}")


def get_agent_logger(agent_name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(f"marketscope.agents.{agent_name}").bind(
        agent_name=agent_name,
    )
```

#### 하위 호환 전략
- `get_logger()`, `get_agent_logger()` 시그니처 유지
- structlog BoundLogger는 `.info()`, `.error()` 등 stdlib 호환 API 제공
- 기존 `logging.getLogger()` 직접 호출부를 `get_logger()` 로 교체
- `extra={}` 패턴 → `logger.info("event", key=value)` 바인딩 패턴으로 변경

#### 교체 대상 파일

| 파일 | 현재 방식 | 변경 |
|------|----------|------|
| `agents/base.py` | `get_agent_logger(self.name)` | 반환 타입만 변경 (호환) |
| `agents/commander.py` | `get_agent_logger("commander")` | 호환 |
| `agents/debate/orchestrator.py` | `get_logger("debate.orchestrator")` | 호환 |
| `graph/nodes.py` | `get_logger("graph.nodes")` | 호환 |
| `memory/task_memory.py` | `get_logger("memory.task")` | 호환 |
| `memory/personal_memory.py` | `get_logger("memory.personal")` | 호환 |
| `memory/lightrag_client.py` | `get_logger("memory.lightrag")` | 호환 |
| `tools/mcp_client.py` | `get_logger("tools.mcp")` | 호환 |
| `monitoring/quality_checker.py` | `logging.getLogger("monitoring.quality")` | `get_logger()` 교체 |

---

### S1-2. Langfuse LLM 트레이싱

#### `app/monitoring/langfuse_handler.py` 신규 생성

```python
"""Langfuse LLM 트레이싱 핸들러."""
from __future__ import annotations
from typing import Optional
import litellm
from app.config import Settings
from app.logging_config import get_logger

logger = get_logger("monitoring.langfuse")

_langfuse_client = None

def setup_langfuse(settings: Settings) -> None:
    global _langfuse_client
    if not settings.langfuse_enabled:
        logger.info("langfuse.disabled")
        return

    from langfuse import Langfuse
    _langfuse_client = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )

    # LiteLLM 네이티브 콜백 등록
    litellm.success_callback = ["langfuse"]
    litellm.failure_callback = ["langfuse"]

    # Langfuse 환경변수 설정 (LiteLLM이 참조)
    import os
    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key or "")
    os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key or "")
    os.environ.setdefault("LANGFUSE_HOST", settings.langfuse_host)

    logger.info("langfuse.enabled", host=settings.langfuse_host)


def get_langfuse():
    return _langfuse_client


def create_trace(session_id: str, name: str, metadata: Optional[dict] = None):
    """분석 세션용 Langfuse trace 생성."""
    if not _langfuse_client:
        return None
    return _langfuse_client.trace(
        name=name,
        session_id=session_id,
        metadata=metadata or {},
    )


async def flush_langfuse() -> None:
    if _langfuse_client:
        _langfuse_client.flush()
        logger.info("langfuse.flushed")


async def shutdown_langfuse() -> None:
    if _langfuse_client:
        _langfuse_client.flush()
        _langfuse_client.shutdown()
        logger.info("langfuse.shutdown")
```

#### `agents/base.py` 변경사항

`_call_llm()` 메서드에 Langfuse 메타데이터 전달:

```python
# litellm.acompletion() 호출 시 metadata 추가
response = await litellm.acompletion(
    model=self.model_name,
    messages=messages,
    metadata={
        "trace_name": f"{self.name}.analyze",
        "session_id": state.get("session_id", ""),
        "agent_name": self.name,
    },
    ...
)
```

LiteLLM이 Langfuse 콜백을 통해 자동으로 trace_name, token usage, latency를 기록한다.

#### `main.py` lifespan 추가

```python
from app.monitoring.langfuse_handler import setup_langfuse, shutdown_langfuse

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... 기존 초기화
    setup_langfuse(settings)
    yield
    # ... 기존 정리
    await shutdown_langfuse()
```

---

### S1-3. 에이전트 실행 컨텍스트 로깅

#### 로그 이벤트 스펙

| 이벤트명 | 필드 | 레벨 |
|---------|------|------|
| `agent.start` | agent_name, session_id, location, industry | INFO |
| `agent.llm_call` | model, prompt_tokens, completion_tokens, latency_ms | INFO |
| `agent.mcp_call` | tool_name, server_prefix, latency_ms, success, error_type | INFO/ERROR |
| `agent.complete` | agent_name, confidence, score, duration_ms | INFO |
| `agent.error` | agent_name, error_type, error_message | ERROR |

#### `agents/base.py` 구현 패턴

```python
async def run(self, state):
    self.logger.info("agent.start", session_id=state.get("session_id"))
    start = time.monotonic()
    try:
        result = await self._analyze(state)
        duration_ms = (time.monotonic() - start) * 1000
        self.logger.info("agent.complete",
            confidence=getattr(result, "confidence", None),
            duration_ms=round(duration_ms, 1),
        )
        return result
    except Exception as e:
        self.logger.error("agent.error",
            error_type=type(e).__name__,
            error_message=str(e),
        )
        raise
```

---

## S2: MCP 모니터링 + DAG 관측성

### S2-1. MCP 모니터링 미들웨어

#### `app/monitoring/mcp_monitor.py` 신규 생성

```python
"""MCP 호출 모니터링 미들웨어."""
import time
from typing import Any
from app.logging_config import get_logger

logger = get_logger("monitoring.mcp")


class MCPMonitoringMiddleware:
    def __init__(self, router):
        self._router = router
        self._stats: dict[str, dict] = {}  # server_prefix → {calls, errors, total_ms}

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        server_prefix = tool_name.split(".")[0] if "." in tool_name else "public_data"
        start = time.monotonic()

        try:
            result = await self._router.call_tool(tool_name, arguments)
            latency_ms = (time.monotonic() - start) * 1000
            self._record(server_prefix, latency_ms, success=True)
            logger.info("mcp.call.success",
                tool=tool_name, server=server_prefix,
                latency_ms=round(latency_ms, 1),
            )
            return result
        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            self._record(server_prefix, latency_ms, success=False)
            logger.error("mcp.call.error",
                tool=tool_name, server=server_prefix,
                error_type=type(e).__name__,
                latency_ms=round(latency_ms, 1),
            )
            raise

    def _record(self, server: str, latency_ms: float, success: bool):
        if server not in self._stats:
            self._stats[server] = {"calls": 0, "errors": 0, "total_ms": 0.0}
        self._stats[server]["calls"] += 1
        self._stats[server]["total_ms"] += latency_ms
        if not success:
            self._stats[server]["errors"] += 1

    def get_stats(self) -> dict:
        return {
            server: {
                **s,
                "avg_ms": round(s["total_ms"] / s["calls"], 1) if s["calls"] else 0,
                "error_rate": round(s["errors"] / s["calls"], 3) if s["calls"] else 0,
            }
            for server, s in self._stats.items()
        }
```

#### `tools/mcp_client.py` 적용

`MCPClientRouter` 를 직접 수정하지 않고, `mcp_monitor.py`의 미들웨어가 래핑하는 구조.
`nodes.py`의 `_get_mcp_router()`에서 미들웨어 적용:

```python
_mcp_monitor = None

def _get_mcp_monitor():
    global _mcp_monitor
    if _mcp_monitor is None:
        router = _get_mcp_router()
        _mcp_monitor = MCPMonitoringMiddleware(router)
    return _mcp_monitor
```

---

### S2-2. LangGraph DAG 관측성

#### `app/monitoring/dag_tracer.py` 신규 생성

```python
"""LangGraph DAG 노드 트레이싱."""
import functools
import time
from typing import Any, Callable
from app.logging_config import get_logger

logger = get_logger("monitoring.dag")


class DAGTracer:
    """워크플로우 실행 추적기."""

    def __init__(self):
        self._timings: dict[str, float] = {}
        self._pipeline_start: float | None = None

    def start_pipeline(self, session_id: str):
        self._pipeline_start = time.monotonic()
        logger.info("pipeline.start", session_id=session_id)

    def record_node(self, node_name: str, duration_ms: float):
        self._timings[node_name] = duration_ms

    def end_pipeline(self, session_id: str):
        if self._pipeline_start:
            total_ms = (time.monotonic() - self._pipeline_start) * 1000
            logger.info("pipeline.complete",
                session_id=session_id,
                total_ms=round(total_ms, 1),
                node_timings=self._timings,
            )

    def get_timings(self) -> dict[str, float]:
        return dict(self._timings)


def trace_node(func: Callable) -> Callable:
    """노드 함수 트레이싱 데코레이터."""

    @functools.wraps(func)
    async def wrapper(state: dict[str, Any]) -> dict[str, Any]:
        node_name = func.__name__
        logger.info("node.start", node=node_name)
        start = time.monotonic()

        try:
            result = await func(state)
            duration_ms = (time.monotonic() - start) * 1000
            logger.info("node.complete",
                node=node_name,
                duration_ms=round(duration_ms, 1),
            )
            return result
        except Exception as e:
            duration_ms = (time.monotonic() - start) * 1000
            logger.error("node.error",
                node=node_name,
                error_type=type(e).__name__,
                duration_ms=round(duration_ms, 1),
            )
            raise

    return wrapper
```

#### `graph/nodes.py` 적용

```python
from app.monitoring.dag_tracer import trace_node

@trace_node
async def population_node(state: dict) -> dict:
    ...  # 기존 코드 그대로

@trace_node
async def competition_node(state: dict) -> dict:
    ...
```

#### `graph/edges.py` 분기 로깅

```python
def should_run_group3(state: dict) -> str:
    result = ...  # 기존 분기 로직
    logger.info("edge.decision", edge="should_run_group3", result=result)
    return result
```

---

### S2-3. 토론 시스템 모니터링

#### `agents/debate/orchestrator.py` 로그 이벤트

| 이벤트 | 필드 | 시점 |
|--------|------|------|
| `debate.start` | session_id, trigger_reason | 토론 시작 |
| `debate.round.start` | round_number | 라운드 시작 |
| `debate.advocate` | argument_count, key_claims | Advocate 완료 |
| `debate.critic` | counter_argument_count | Critic 완료 |
| `debate.judge` | confidence, is_converged, verdict_summary | Judge 완료 |
| `debate.complete` | total_rounds, revised_score, converged | 토론 종료 |

#### Langfuse 토론 span

```python
trace = create_trace(session_id, "debate")
if trace:
    span = trace.span(name=f"round_{round_num}")
    span.update(metadata={"advocate_claims": ..., "critic_claims": ...})
    span.end()
```

---

## S3: 메트릭 엔드포인트 + 대시보드

### S3-1. Prometheus 메트릭

#### 의존성 추가
- `pyproject.toml`에 `prometheus-client >= 0.20.0` 추가

#### `app/monitoring/metrics.py` 신규 생성

| 메트릭명 | 타입 | Labels | 용도 |
|---------|------|--------|------|
| `http_request_duration_seconds` | Histogram | method, path, status | HTTP 요청 레이턴시 |
| `http_requests_total` | Counter | method, path, status | HTTP 요청 수 |
| `agent_execution_seconds` | Histogram | agent_name | 에이전트 실행 시간 |
| `agent_errors_total` | Counter | agent_name, error_type | 에이전트 에러 |
| `llm_tokens_total` | Counter | model, type(prompt/completion) | 토큰 사용량 |
| `llm_cost_dollars_total` | Counter | model | LLM 비용 |
| `mcp_call_duration_seconds` | Histogram | server, tool | MCP 호출 레이턴시 |
| `mcp_errors_total` | Counter | server, error_type | MCP 에러 |
| `debate_rounds_total` | Histogram | — | 토론 라운드 수 |
| `pipeline_duration_seconds` | Histogram | — | 파이프라인 전체 시간 |
| `pipeline_node_duration_seconds` | Histogram | node | 노드별 실행 시간 |

#### `main.py` `/metrics` 엔드포인트

```python
from prometheus_client import make_asgi_app

metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)
```

#### FastAPI HTTP 미들웨어

```python
from app.monitoring.metrics import http_request_duration, http_requests_total

@app.middleware("http")
async def metrics_middleware(request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    duration = time.monotonic() - start
    http_request_duration.labels(
        method=request.method,
        path=request.url.path,
        status=response.status_code,
    ).observe(duration)
    http_requests_total.labels(...).inc()
    return response
```

---

### S3-2. 헬스체크 확장

#### `app/api/health.py` 확장

```python
@router.get("/health/live")
async def liveness():
    return {"status": "ok"}

@router.get("/health/ready")
async def readiness(db: AsyncSession = Depends(get_db)):
    checks = {
        "database": await check_db(db),
        "redis": await check_redis(),
        "mcp_public_data": await check_mcp("public_data"),
        "mcp_maps": await check_mcp("maps"),
        "mcp_real_estate": await check_mcp("real_estate"),
        "mcp_news": await check_mcp("news"),
        "mcp_regulatory": await check_mcp("regulatory"),
    }
    all_ok = all(v["status"] == "ok" for v in checks.values())
    return {"status": "ok" if all_ok else "degraded", "checks": checks}

@router.get("/health/detailed")
async def detailed_health():
    return {
        "components": ...,  # 위 readiness + 버전, 가동시간
        "mcp_stats": mcp_monitor.get_stats(),
        "dag_timings": dag_tracer.get_timings(),
    }
```

---

### S3-3. Docker Compose 모니터링 스택

#### `docker-compose.monitoring.yml`

```yaml
version: "3.8"
services:
  prometheus:
    image: prom/prometheus:v2.51.0
    ports: ["9090:9090"]
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana:10.4.0
    ports: ["3001:3000"]
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin
    volumes:
      - ./monitoring/grafana/dashboards:/var/lib/grafana/dashboards
      - ./monitoring/grafana/provisioning:/etc/grafana/provisioning
    depends_on: [prometheus]

  loki:
    image: grafana/loki:2.9.0
    ports: ["3100:3100"]
    command: -config.file=/etc/loki/local-config.yaml
```

#### `monitoring/prometheus.yml`

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: "marketscope"
    static_configs:
      - targets: ["host.docker.internal:8000"]
```

#### Grafana 대시보드 프로비저닝

4개 패널 구성:
1. **에이전트 실행 현황**: agent_execution_seconds by agent_name
2. **MCP 서버 상태**: mcp_call_duration_seconds, mcp_errors_total by server
3. **LLM 토큰/비용**: llm_tokens_total, llm_cost_dollars_total by model
4. **파이프라인 실행 시간**: pipeline_duration_seconds, pipeline_node_duration_seconds

---

## 구현 순서 (권장)

```
1. pyproject.toml 의존성 추가 (structlog, prometheus-client)
2. logging_config.py 재작성 (structlog)
3. 기존 로거 호출부 교체 확인 (하위 호환)
4. monitoring/langfuse_handler.py 생성
5. main.py lifespan에 Langfuse 연결
6. agents/base.py — 에이전트 로그 이벤트 + Langfuse 메타데이터
7. monitoring/mcp_monitor.py 생성
8. monitoring/dag_tracer.py 생성 + nodes.py 데코레이터 적용
9. debate/orchestrator.py 토론 로깅 강화
10. monitoring/metrics.py 생성 + main.py /metrics 마운트
11. api/health.py 확장
12. docker-compose.monitoring.yml (선택)
```
