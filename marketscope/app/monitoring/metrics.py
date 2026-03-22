"""Prometheus 메트릭 정의 — MarketScope AI 관측성."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ── HTTP 메트릭 ──

HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP 요청 처리 시간",
    ["method", "path", "status"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0],
)

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "HTTP 요청 총 수",
    ["method", "path", "status"],
)

# ── 에이전트 메트릭 ──

AGENT_EXECUTION_SECONDS = Histogram(
    "agent_execution_seconds",
    "에이전트 실행 시간 (초)",
    ["agent_name"],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0],
)

AGENT_ERRORS_TOTAL = Counter(
    "agent_errors_total",
    "에이전트 에러 횟수",
    ["agent_name", "error_type"],
)

# ── LLM 메트릭 ──

LLM_TOKENS_TOTAL = Counter(
    "llm_tokens_total",
    "LLM 토큰 사용량",
    ["model", "type"],  # type: prompt / completion
)

LLM_COST_DOLLARS = Counter(
    "llm_cost_dollars_total",
    "LLM 비용 (USD)",
    ["model"],
)

# ── MCP 메트릭 ──

MCP_CALL_DURATION = Histogram(
    "mcp_call_duration_seconds",
    "MCP 도구 호출 시간 (초)",
    ["server", "tool"],
    buckets=[0.1, 0.5, 1.0, 3.0, 5.0, 10.0, 30.0],
)

MCP_ERRORS_TOTAL = Counter(
    "mcp_errors_total",
    "MCP 도구 호출 에러 횟수",
    ["server", "error_type"],
)

# ── 토론 메트릭 ──

DEBATE_ROUNDS = Histogram(
    "debate_rounds_total",
    "토론 라운드 수",
    buckets=[1, 2, 3],
)

DEBATE_CONVERGENCE = Gauge(
    "debate_convergence_last",
    "마지막 토론 수렴 여부 (1=수렴, 0=미수렴)",
)

# ── 파이프라인 메트릭 ──

PIPELINE_DURATION = Histogram(
    "pipeline_duration_seconds",
    "전체 파이프라인 실행 시간 (초)",
    buckets=[10.0, 30.0, 60.0, 120.0, 300.0],
)

PIPELINE_NODE_DURATION = Histogram(
    "pipeline_node_duration_seconds",
    "노드별 실행 시간 (초)",
    ["node"],
    buckets=[0.1, 1.0, 5.0, 10.0, 30.0, 60.0],
)


# ── 헬퍼 함수 (모듈 외부에서 편리하게 호출) ──


def observe_http_request(method: str, path: str, status: int, duration: float) -> None:
    """HTTP 요청 메트릭을 기록한다."""
    labels = {"method": method, "path": _normalize_path(path), "status": str(status)}
    HTTP_REQUEST_DURATION.labels(**labels).observe(duration)
    HTTP_REQUESTS_TOTAL.labels(**labels).inc()


def observe_agent_execution(agent_name: str, duration_seconds: float) -> None:
    """에이전트 실행 시간을 기록한다."""
    AGENT_EXECUTION_SECONDS.labels(agent_name=agent_name).observe(duration_seconds)


def inc_agent_error(agent_name: str, error_type: str) -> None:
    """에이전트 에러를 기록한다."""
    AGENT_ERRORS_TOTAL.labels(agent_name=agent_name, error_type=error_type).inc()


def observe_mcp_call(server: str, tool: str, duration_seconds: float) -> None:
    """MCP 호출 메트릭을 기록한다."""
    # tool에서 server prefix 제거
    actual_tool = tool.split(".", 1)[-1] if "." in tool else tool
    MCP_CALL_DURATION.labels(server=server, tool=actual_tool).observe(duration_seconds)


def inc_mcp_error(server: str, error_type: str) -> None:
    """MCP 에러를 기록한다."""
    MCP_ERRORS_TOTAL.labels(server=server, error_type=error_type).inc()


def record_llm_usage(model: str, prompt_tokens: int, completion_tokens: int) -> None:
    """LLM 토큰 사용량과 비용을 Prometheus에 기록한다."""
    if prompt_tokens > 0:
        LLM_TOKENS_TOTAL.labels(model=model, type="prompt").inc(prompt_tokens)
    if completion_tokens > 0:
        LLM_TOKENS_TOTAL.labels(model=model, type="completion").inc(completion_tokens)

    from app.llm.pricing import calculate_cost
    cost_info = calculate_cost(model, prompt_tokens, completion_tokens)
    total_cost = float(cost_info["total_cost_usd"])
    if total_cost > 0:
        LLM_COST_DOLLARS.labels(model=model).inc(total_cost)


def observe_debate(rounds: int, converged: bool) -> None:
    """토론 메트릭을 기록한다."""
    DEBATE_ROUNDS.observe(rounds)
    DEBATE_CONVERGENCE.set(1.0 if converged else 0.0)


def observe_pipeline_duration(duration_seconds: float) -> None:
    """파이프라인 전체 실행 시간을 기록한다."""
    PIPELINE_DURATION.observe(duration_seconds)


def observe_node_duration(node: str, duration_seconds: float) -> None:
    """노드별 실행 시간을 기록한다."""
    PIPELINE_NODE_DURATION.labels(node=node).observe(duration_seconds)


def _normalize_path(path: str) -> str:
    """경로를 정규화하여 카디널리티를 제한한다."""
    # /api/v1/analysis/{uuid} → /api/v1/analysis/:id
    parts = path.strip("/").split("/")
    normalized = []
    for part in parts:
        if len(part) == 36 and "-" in part:
            # UUID 패턴
            normalized.append(":id")
        else:
            normalized.append(part)
    return "/" + "/".join(normalized)
