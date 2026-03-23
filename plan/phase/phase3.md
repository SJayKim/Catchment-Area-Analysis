# Phase 3 구현 계획 — MarketScope AI

> **작성일:** 2026-03-21
> **선행 조건:** Phase 2 완료 (`phase 2.md`)
> **목표:** 로깅 & 모니터링 시스템 구축

---

## 목표

Phase 2에서 구축한 9개 에이전트 + 토론 시스템 + 메모리 시스템의 **운영 가시성**을 확보한다.
Phase 4(테스트) 진입 전에 모니터링 인프라를 갖추어, 테스트 실행 시 병목·오류·비용을 즉시 파악할 수 있도록 한다.

---

## 전체 일정 개요

| 스프린트 | 기간 | 핵심 목표 |
|---------|------|----------|
| S1 | Week 1 | structlog 전환 + Langfuse LLM 트레이싱 활성화 |
| S2 | Week 2 | MCP 모니터링 미들웨어 + LangGraph DAG 관측성 |
| S3 | Week 3 | Prometheus 메트릭 + 헬스체크 + 모니터링 스택 |

---

## 현황 분석

| 항목 | 현재 상태 | 목표 |
|------|-----------|------|
| 로깅 | `StructuredFormatter` (stdlib, 텍스트) | **structlog** JSON 파이프라인 |
| LLM 트레이싱 | `langfuse_enabled=False`, config만 존재 | **Langfuse** 콜백, 전 에이전트 트레이스 |
| MCP 모니터링 | 없음 | 요청/응답 로깅, 레이턴시, 에러율 |
| DAG 관측성 | 없음 | 노드별 실행 시간, 토큰 사용량 |
| 데이터 품질 | `quality_checker.py` 구현됨 | 기존 유지 + 메트릭 연동 |
| 메트릭 수집 | 없음 | **Prometheus** `/metrics` 엔드포인트 |

---

## 프레임워크 선정

| 영역 | 프레임워크 | 선정 이유 | 대안 검토 |
|------|-----------|----------|----------|
| 구조화 로깅 | **structlog** | JSON 출력, 컨텍스트 바인딩(`bind(session_id=...)`), stdlib 호환 | loguru (구조화 약함), stdlib (현재, 컨텍스트 바인딩 없음) |
| LLM Observability | **Langfuse** | 이미 `pyproject.toml` + `config.py` 설정 존재, LiteLLM 네이티브 콜백 | LangSmith (LangChain 종속), Helicone (프록시), OpenTelemetry (LLM 특화 부족) |
| 메트릭 수집 | **Prometheus** | 산업 표준, FastAPI 통합 용이, Grafana 연계 | StatsD (push 방식), DataDog (유료) |
| 로그 수집 | **Loki** (선택) | structlog JSON 네이티브, Grafana 통합 | ELK (과대), CloudWatch (AWS 종속) |

---

## S1: structlog 전환 + Langfuse 활성화 (Week 1)

### S1-1. structlog 파이프라인 구축

현재 `logging_config.py`의 `StructuredFormatter`를 structlog 기반으로 교체한다.

```python
# 목표 구조 (logging_config.py)
import structlog

def setup_logging(env: str = "development") -> None:
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]
    if env == "production":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(processors=processors, ...)
```

**적용 대상:** `agents/base.py`, `agents/commander.py`, `agents/debate/orchestrator.py`, `graph/nodes.py`, `memory/*.py`, `tools/mcp_client.py`

### S1-2. Langfuse LLM 트레이싱

`langfuse` 의존성과 config 설정이 이미 존재하므로, 콜백 핸들러만 구현하면 활성화 가능하다.

```python
# 목표 구조 (monitoring/langfuse_handler.py)
import litellm
from langfuse import Langfuse

def setup_langfuse(settings):
    if not settings.langfuse_enabled:
        return
    langfuse = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )
    litellm.success_callback = ["langfuse"]
    litellm.failure_callback = ["langfuse"]
```

**핵심:** LiteLLM → Langfuse 콜백 등록으로 모든 에이전트 LLM 호출이 자동 트레이싱됨.

### S1-3. 에이전트 실행 컨텍스트 로깅

모든 에이전트 `run()` 메서드에 구조화 로그 이벤트 5종 추가:

| 이벤트 | 필드 | 시점 |
|--------|------|------|
| `agent.start` | agent_name, session_id, input_summary | 실행 시작 |
| `agent.llm_call` | model, prompt_tokens, completion_tokens, latency_ms | LLM 호출 |
| `agent.mcp_call` | tool_name, server_prefix, latency_ms, success | MCP 호출 |
| `agent.complete` | agent_name, confidence, duration_ms | 실행 완료 |
| `agent.error` | agent_name, error_type, error_message | 에러 발생 |

---

## S2: MCP 모니터링 + DAG 관측성 (Week 2)

### S2-1. MCP 모니터링 미들웨어

```python
# 목표 구조 (monitoring/mcp_monitor.py)
class MCPMonitoringMiddleware:
    async def call_tool(self, tool_name, arguments):
        start = time.monotonic()
        try:
            result = await self._router.call_tool(tool_name, arguments)
            logger.info("mcp.call.success", tool=tool_name, latency_ms=...)
            return result
        except Exception as e:
            logger.error("mcp.call.error", tool=tool_name, error_type=type(e).__name__)
            raise
```

**적용:** `MCPClientRouter.call_tool()` 래핑. 서버별 호출 횟수, 평균 레이턴시, 에러율 집계.

### S2-2. LangGraph DAG 관측성

```python
# 목표 구조 (monitoring/dag_tracer.py)
def trace_node(func):
    """노드 실행 자동 트레이싱 데코레이터"""
    async def wrapper(state):
        logger.info("node.start", node=func.__name__)
        start = time.monotonic()
        result = await func(state)
        logger.info("node.complete", node=func.__name__, duration_ms=...)
        return result
    return wrapper
```

**적용:** `graph/nodes.py` 18개 노드 함수에 `@trace_node` 데코레이터. 파이프라인 전체 실행 시간 + 그룹별 병렬 실행 시간 측정.

### S2-3. 토론 시스템 모니터링

`debate/orchestrator.py`에 라운드별 로그 이벤트 추가:
- `debate.round.start` → `debate.advocate` → `debate.critic` → `debate.judge` → `debate.complete`
- Langfuse에 토론 라운드별 trace span 생성

---

## S3: 메트릭 엔드포인트 + 대시보드 (Week 3)

### S3-1. Prometheus 메트릭

```python
# 목표 구조 (monitoring/metrics.py)
from prometheus_client import Counter, Histogram, Gauge

# HTTP
request_duration = Histogram("request_duration_seconds", "...", ["method", "path"])
# Agent
agent_execution = Histogram("agent_execution_seconds", "...", ["agent_name"])
agent_errors = Counter("agent_errors_total", "...", ["agent_name"])
# LLM
llm_tokens = Counter("llm_tokens_total", "...", ["model", "type"])
llm_cost = Counter("llm_cost_dollars", "...", ["model"])
# MCP
mcp_duration = Histogram("mcp_call_duration_seconds", "...", ["server", "tool"])
# Pipeline
pipeline_duration = Histogram("pipeline_duration_seconds", "...")
```

**엔드포인트:** `main.py`에 `/metrics` 추가 (prometheus_client ASGI middleware).

### S3-2. 헬스체크 확장

| 엔드포인트 | 용도 |
|-----------|------|
| `/health/live` | 프로세스 생존 확인 |
| `/health/ready` | DB, Redis, MCP 서버 5개 연결 상태 |
| `/health/detailed` | 컴포넌트별 상세 + 최근 에러 요약 |

### S3-3. Docker Compose 모니터링 스택 (선택)

```yaml
# docker-compose.monitoring.yml
services:
  prometheus:
    image: prom/prometheus:v2.51.0
    ports: ["9090:9090"]
    volumes: ["./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml"]

  grafana:
    image: grafana/grafana:10.4.0
    ports: ["3001:3000"]
    depends_on: [prometheus]

  loki:
    image: grafana/loki:2.9.0
    ports: ["3100:3100"]
```

Grafana 대시보드: 에이전트 실행 현황, MCP 서버 상태, LLM 토큰/비용, 파이프라인 실행 시간 패널.

---

## 파일 변경 요약

| 유형 | 파일 | 스프린트 |
|------|------|----------|
| **재작성** | `app/logging_config.py` | S1 |
| **신규** | `app/monitoring/langfuse_handler.py` | S1 |
| **신규** | `app/monitoring/mcp_monitor.py` | S2 |
| **신규** | `app/monitoring/dag_tracer.py` | S2 |
| **신규** | `app/monitoring/metrics.py` | S3 |
| **신규** | `app/api/health.py` (확장) | S3 |
| **신규** | `docker-compose.monitoring.yml` (선택) | S3 |
| 수정 | `app/agents/base.py` | S1 |
| 수정 | `app/agents/commander.py` | S1 |
| 수정 | `app/agents/debate/orchestrator.py` | S2 |
| 수정 | `app/tools/mcp_client.py` | S2 |
| 수정 | `app/graph/nodes.py` | S2 |
| 수정 | `app/graph/workflow.py` | S2 |
| 수정 | `app/main.py` | S1, S3 |
| 수정 | `app/config.py` | S3 |
| 수정 | `pyproject.toml` | S1, S3 |

---

## 의존성 그래프

```
S1-1 (structlog 전환)  ──┐
S1-2 (Langfuse 활성화) ──┤
S1-3 (에이전트 로깅)   ──┤
                         ├──→ S2-1 (MCP 모니터링)
                         │    S2-2 (DAG 관측성)
                         │    S2-3 (토론 모니터링)
                         │         │
                         │         ▼
                         └──→ S3-1 (Prometheus 메트릭)
                              S3-2 (헬스체크 확장)
                              S3-3 (모니터링 스택)
```

---

## Phase 4 연계

Phase 3 완료 후 Phase 4(테스트) 진입 시:
- Langfuse에서 LLM 호출 패턴/비용 즉시 확인
- 실패 테스트의 정확한 노드/에이전트/MCP 호출 지점 파악
- 성능 병목 식별 (어느 에이전트가 느린지, 어느 MCP 서버가 불안정한지)
- 토큰 사용량 기반 비용 최적화 의사결정
