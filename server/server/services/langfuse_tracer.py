"""Langfuse tracer — LLMOps L1 진입점 (langfuse v3 API).

graceful degrade 원칙:
- Langfuse 비활성/키 미설정/import 실패/런타임 오류 시 **None** 반환.
- `/api/chat` 는 Langfuse 유무와 무관하게 동작 (best-effort tracing).
- 반복 실패 시 `_tracer_valid` 플래그로 재시도 회피 (`_anthropic_valid` 패턴 답습).

v3 포팅 배경: langfuse 2.x `from langfuse.callback import CallbackHandler` 는
legacy `langchain.callbacks.base` 에 의존하나 langchain 1.x 에서 제거됨.
v3 (`from langfuse.langchain import CallbackHandler`) 는 `langchain_core` 기반
OpenTelemetry 구조로 전환되어 `langchain_anthropic`/`langchain_google_genai` 4.x 와
공존 가능.

v3 에서 trace_id 는 handler 생성 시점에 `Langfuse.create_trace_id(seed)` 로
미리 배정하고 `TraceContext(trace_id=...)` 로 handler 에 주입. 이 방식이
post-hoc `get_current_trace_id()` 보다 async/context 누락에 안전.

Plan 근거: `docs/plan/infra/llmops-platform.md` §3.3.1, §4.2 재검토.
"""

from __future__ import annotations

import hashlib
import logging
import secrets

from server.config import settings

logger = logging.getLogger(__name__)

# 반복 실패 시 tracing 포기 (이후 요청에서 import/auth 재시도 스킵)
_tracer_valid = True

# 기동 시 salt 가 비어 있으면 랜덤 생성 (인스턴스 고유값, 재시작 시 세션 해시가 바뀜)
_SESSION_SALT: str = settings.langfuse_session_salt or secrets.token_hex(16)

# Langfuse client 싱글톤 (v3 는 Handler 와 분리)
_client = None


def _hash_session(session_id: str) -> str:
    """session_id → salted sha256. 원본 session_id 는 Langfuse 에 저장 금지."""
    if not session_id:
        return "anonymous"
    digest = hashlib.sha256((_SESSION_SALT + session_id).encode("utf-8")).hexdigest()
    return digest[:16]  # 16 chars = 64 bit 충분히 유일


def should_sample() -> bool:
    """샘플링 비율 기반 trace 생성 여부. 1.0=항상, 0.0=끔."""
    rate = settings.langfuse_sampling_rate
    if rate >= 1.0:
        return True
    if rate <= 0.0:
        return False
    return secrets.randbelow(10_000) < int(rate * 10_000)


def _get_client():
    """Langfuse client 싱글톤 초기화.

    None 반환 조건:
    - Langfuse disabled (키 미설정)
    - 이전 실패로 `_tracer_valid=False`
    - import 실패
    - 생성자 예외 (auth/network 등)
    """
    global _client, _tracer_valid
    if _client is not None:
        return _client
    if not _tracer_valid:
        return None
    if not settings.langfuse_enabled:
        return None

    try:
        from langfuse import Langfuse
    except ImportError:
        logger.warning("langfuse package unavailable, tracing disabled")
        _tracer_valid = False
        return None
    except Exception:
        logger.warning("langfuse import failed unexpectedly, tracing disabled", exc_info=True)
        _tracer_valid = False
        return None

    try:
        _client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
            sample_rate=settings.langfuse_sampling_rate,
        )
    except Exception:
        logger.warning("langfuse client init failed", exc_info=True)
        _tracer_valid = False
        return None

    if settings.langfuse_otel_insecure:
        _disable_otel_tls_verify()

    return _client


def _disable_otel_tls_verify() -> None:
    """OTEL span export 시 TLS 검증 비활성화 (MITM/사내망 우회).

    공식 HTTP exporter 에는 verify 토글이 없어 SDK 내부 session 을 monkey-patch.
    Langfuse v3 경로: `get_tracer_provider()._active_span_processor._span_processors[i]
    .span_exporter._session.verify`.

    ⚠ 프로덕션 비권장. 사내 MITM 환경에서만 `LANGFUSE_OTEL_INSECURE=true` 로 명시 opt-in.
    """
    try:
        import urllib3
        from opentelemetry import trace as otel_trace

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        prov = otel_trace.get_tracer_provider()
        asp = getattr(prov, "_active_span_processor", None)
        if asp is None:
            return
        sps = getattr(asp, "_span_processors", None) or [asp]
        patched = 0
        for sp in sps:
            exp = getattr(sp, "span_exporter", None)
            if exp is None:
                continue
            # OTLP HTTP exporter 는 `session.post(..., verify=self._certificate_file)` 로
            # session 의 기본 verify 를 override. 그래서 둘 다 False 로 내려야 함.
            if hasattr(exp, "_certificate_file"):
                exp._certificate_file = False
            sess = getattr(exp, "_session", None)
            if sess is not None:
                sess.verify = False
            if hasattr(exp, "_certificate_file") or sess is not None:
                patched += 1
        if patched:
            logger.warning(
                "Langfuse OTEL TLS verify disabled (LANGFUSE_OTEL_INSECURE=true). "
                "Patched %d exporter session(s). DO NOT use in production.",
                patched,
            )
    except Exception:
        logger.warning("langfuse OTEL TLS verify patch failed", exc_info=True)


def get_langfuse_handler(session_id: str, request_id: str):
    """CallbackHandler + pre-assigned trace_id 를 반환.

    None 반환 조건:
    - Langfuse disabled
    - 이전 실패 (`_tracer_valid=False`)
    - 샘플링 탈락
    - client init 실패
    - handler 생성 예외

    handler 에는 `_ms_trace_id`/`_ms_session_hash`/`_ms_request_id` 속성을
    심어 두어 graph.py 가 langchain `RunnableConfig.metadata` 로 재전달할 수 있게 한다.
    `trace_id` 는 `Langfuse.create_trace_id(seed=...)` 로 결정적 사전 배정 — astream
    종료 후 otel context 가 빠져도 `done` 이벤트에 동봉 가능.
    """
    global _tracer_valid

    if not _tracer_valid:
        return None
    if not settings.langfuse_enabled:
        return None
    if not should_sample():
        return None

    client = _get_client()
    if client is None:
        return None

    try:
        from langfuse.langchain import CallbackHandler
        from langfuse.types import TraceContext
    except ImportError:
        logger.warning("langfuse.langchain unavailable, tracing disabled")
        _tracer_valid = False
        return None

    try:
        seed = f"{session_id or 'anon'}:{request_id or secrets.token_hex(8)}"
        trace_id = client.create_trace_id(seed=seed)
        handler = CallbackHandler(trace_context=TraceContext(trace_id=trace_id))
        handler._ms_trace_id = trace_id
        handler._ms_session_hash = _hash_session(session_id)
        handler._ms_request_id = request_id
    except Exception:
        logger.warning("langfuse handler creation failed, tracing disabled", exc_info=True)
        _tracer_valid = False
        return None

    return handler


def build_langchain_metadata(handler) -> dict:
    """graph.py 가 `astream(config={..., metadata: ...})` 에 합칠 보조 메타.

    v3 반영 — `langfuse_session_id` 는 Langfuse Sessions 뷰의 1급 키. 원본
    session_id 는 노출 금지이므로 salted sha256 해시를 넣는다 (재식별은 불가하지만
    동일 세션끼리는 묶임). 현재 서비스는 OAuth 미도입 상태이므로 `langfuse_user_id`
    는 Phase 2 에서 authed user id 가 들어오면 추가.

    handler 가 None 이면 빈 dict.
    """
    if handler is None:
        return {}
    # lazy import — services 레이어에서 agent 로의 모듈-로드 순환 방지
    from server.agent.runtime import effective_loop_version

    session_hash = getattr(handler, "_ms_session_hash", "")
    return {
        # Langfuse v3 1급 키 — Sessions 뷰 활성화
        "langfuse_session_id": session_hash,
        # 도메인 메타 — Traces/Dashboards 필터
        "request_id": getattr(handler, "_ms_request_id", ""),
        "llm_provider": settings.llm_provider,
        # 실제 서빙 루프 (v2 | pae) — settings 원값이 아닌 실효값
        "agent_mode": effective_loop_version(),
        "use_mock": settings.use_mock,
    }


def build_langchain_tags() -> list[str]:
    """Per-request Langfuse tags. 대시보드 필터용으로 provider/mode 를 축으로 둔다."""
    return [
        "marketscope.pae",
        f"provider:{settings.llm_provider}",
        f"mode:{'mock' if settings.use_mock else 'real'}",
    ]


def get_trace_id(handler) -> str | None:
    """handler 에서 trace_id 추출. v3 는 pre-assigned `_ms_trace_id` 우선."""
    if handler is None:
        return None
    val = getattr(handler, "_ms_trace_id", None)
    if val:
        return str(val)
    # 구 v2 handler (fallback, 이론상 지금은 도달 안 함)
    for attr in ("trace_id", "last_trace_id"):
        v = getattr(handler, attr, None)
        if v:
            return str(v)
    fn = getattr(handler, "get_trace_id", None)
    if callable(fn):
        try:
            v = fn()
            if v:
                return str(v)
        except Exception:
            pass
    return None


def flush(handler) -> None:
    """Langfuse 배치 flush — best-effort, 예외 삼킴."""
    if handler is None:
        return
    client = _get_client()
    if client is None:
        return
    fn = getattr(client, "flush", None)
    if not callable(fn):
        return
    try:
        fn()
    except Exception:
        logger.debug("langfuse flush failed", exc_info=True)


def shutdown() -> None:
    """앱 종료 시 pending trace 드랍 방지 — lifespan 에서 1회 호출.

    SIGTERM 직후 컨테이너 재시작 시 in-flight 이벤트가 Langfuse 서버에 도달하지
    못하는 문제 방지 (SKILL 권고: 'No flush in scripts → 트레이스 유실').
    best-effort — 예외는 삼킨다.
    """
    global _client
    client = _client
    if client is None:
        return
    try:
        fn = getattr(client, "flush", None)
        if callable(fn):
            fn()
    except Exception:
        logger.debug("langfuse flush on shutdown failed", exc_info=True)
    try:
        fn = getattr(client, "shutdown", None)
        if callable(fn):
            fn()
    except Exception:
        logger.debug("langfuse shutdown failed", exc_info=True)


def get_client_or_none():
    """외부 모듈용 — score API 등에서 싱글톤 Langfuse 클라이언트 재사용."""
    return _get_client()


# ---------------------------------------------------------------------------
# Aggregate-stats helpers (Plan: langfuse-aggregate-stats-2026-04-28)
# ---------------------------------------------------------------------------

# District code prefix → 4 분류. 서울 열린데이터 코드 체계.
#   3110xxx 발달상권 / 3120xxx 골목상권 / 3130xxx 전통시장 / 3140xxx 관광특구
_DISTRICT_TYPE_BY_PREFIX = {
    "3110": "발달상권",
    "3120": "골목상권",
    "3130": "전통시장",
    "3140": "관광특구",
}


def district_type_for(code: str | None) -> str:
    """district_code → 한글 type 라벨. 매칭 실패 시 'unknown'."""
    if not code:
        return "unknown"
    return _DISTRICT_TYPE_BY_PREFIX.get(code[:4], "unknown")


def attach_summary_observation(
    trace_id: str | None,
    *,
    metadata: dict,
    output: dict | None = None,
) -> None:
    """그래프 종료 후 Planner/Actor/Evaluator 결정값을 trace 에 동봉.

    v3 API 한계 — `update_trace` 가 없어 동일 trace_id 로 0-duration agent
    span 을 추가 발행하는 우회 패턴. CallbackHandler 가 만든 langchain
    spans 와 동일 trace_id 로 묶이며, summary span 의 metadata 가 Langfuse UI
    의 trace 레벨 필터/groupby 에 그대로 반영됨.

    None / 비활성 / 예외 모두 silent — SSE 응답 경로에 차단 발생 금지.
    """
    if not trace_id:
        return
    if not _tracer_valid:
        return
    client = _get_client()
    if client is None:
        return
    try:
        from langfuse.types import TraceContext
    except ImportError:
        return

    clean_metadata = {k: v for k, v in metadata.items() if v is not None}
    try:
        span = client.start_observation(
            trace_context=TraceContext(trace_id=trace_id),
            name="marketscope.pae.summary",
            as_type="agent",
            metadata=clean_metadata,
            output=output,
        )
    except Exception:
        logger.debug("langfuse summary observation start failed", exc_info=True)
        return
    try:
        end_fn = getattr(span, "end", None)
        if callable(end_fn):
            end_fn()
    except Exception:
        logger.debug("langfuse summary observation end failed", exc_info=True)


# ---------------------------------------------------------------------------
# L2-A: per-LLM-call token/cost attach
# Plan: docs/plan/infra/langfuse-l2-token-cost-eval.md
# ---------------------------------------------------------------------------


def _normalize_usage(usage: object) -> tuple[int, int]:
    """Extract (input_tokens, output_tokens) from heterogeneous LLM responses.

    Handles:
    - LangChain ``response.usage_metadata = {"input_tokens", "output_tokens", ...}``
    - LangChain ``response.response_metadata.usage`` (older path)
    - Anthropic native ``response.usage = Usage(input_tokens, output_tokens)``
    - Gemini native ``response.usage_metadata = {"prompt_token_count",
      "candidates_token_count"}``
    - dict with any of the above key sets

    Returns ``(0, 0)`` when nothing usable is found — the attach helper
    treats that as "no usage to record" and silently skips.
    """
    if usage is None:
        return 0, 0

    # If it's a response wrapper, prefer usage_metadata first
    candidate = getattr(usage, "usage_metadata", None) or getattr(usage, "usage", None) or usage
    if candidate is None:
        return 0, 0

    # Allow attribute access OR dict access
    def _read(obj, *keys: str) -> int:
        for k in keys:
            v = getattr(obj, k, None)
            if v is None and isinstance(obj, dict):
                v = obj.get(k)
            if isinstance(v, int):
                return v
            if isinstance(v, float):
                return int(v)
        return 0

    input_tokens = _read(candidate, "input_tokens", "prompt_token_count", "prompt_tokens")
    output_tokens = _read(candidate, "output_tokens", "candidates_token_count", "completion_tokens")
    return input_tokens, output_tokens


def attach_generation_usage(
    trace_id: str | None,
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
    prompt_name: str | None = None,
    prompt_version: str | None = None,
    name: str = "marketscope.llm.generation",
) -> None:
    """Attach a generation-typed observation carrying token counts + prompt id.

    Langfuse Cloud maps ``model`` → unit price and computes cost server-side.
    ``prompt_name`` / ``prompt_version`` land in observation metadata so that
    Langfuse UI can group score deltas across prompt revisions.

    Silent on every failure path (disabled, no client, exception). Never
    raises into the request thread.
    """
    if not trace_id:
        return
    if input_tokens <= 0 and output_tokens <= 0:
        return
    if not _tracer_valid:
        return
    client = _get_client()
    if client is None:
        return
    try:
        from langfuse.types import TraceContext
    except ImportError:
        return

    metadata: dict = {}
    if prompt_name:
        metadata["prompt_name"] = prompt_name
    if prompt_version:
        metadata["prompt_version"] = prompt_version

    try:
        span = client.start_observation(
            trace_context=TraceContext(trace_id=trace_id),
            name=name,
            as_type="generation",
            model=model,
            usage_details={"input": int(input_tokens), "output": int(output_tokens)},
            metadata=metadata or None,
        )
    except Exception:
        logger.debug("langfuse generation observation start failed", exc_info=True)
        return
    try:
        end_fn = getattr(span, "end", None)
        if callable(end_fn):
            end_fn()
    except Exception:
        logger.debug("langfuse generation observation end failed", exc_info=True)


# ---------------------------------------------------------------------------
# L2-B: prompt version helper (git sha bake-in at module import time)
# ---------------------------------------------------------------------------


def _git_sha() -> str:
    """Short git SHA of current HEAD, or "unknown" outside a working tree.

    Used as a build-time tag for prompt files. Cheap (one subprocess call
    per Python process — module-import-time is the only call site).
    """
    import subprocess
    from pathlib import Path

    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "--short=7", "HEAD"],
                cwd=Path(__file__).parent,
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
    except Exception:
        return "unknown"


def prompt_version(major_minor_patch: str = "v1.0.0") -> str:
    """Return ``v<major>.<minor>.<patch>-<sha7>`` for a prompt file.

    Caller passes a stable semver tag; the git short-SHA gives mid-revision
    granularity. Bumping the semver is the human signal that the prompt's
    intent changed (and Langfuse experiments should branch).
    """
    return f"{major_minor_patch}-{_git_sha()}"


def emit_score(
    trace_id: str | None,
    name: str,
    value: float,
    *,
    comment: str | None = None,
    data_type: str | None = None,
) -> None:
    """trace_id 에 numeric score 를 attach. 실패는 silent.

    `feedback.py` 의 `client.score(...)` (user_feedback) 와 동일 시그니처를
    재사용. v3 SDK 에서 `score` 는 `create_score` 의 alias.
    """
    if not trace_id:
        return
    if not _tracer_valid:
        return
    client = _get_client()
    if client is None:
        return
    fn = getattr(client, "create_score", None) or getattr(client, "score", None)
    if not callable(fn):
        return
    kwargs: dict = {"trace_id": trace_id, "name": name, "value": value}
    if comment is not None:
        kwargs["comment"] = comment
    if data_type is not None:
        kwargs["data_type"] = data_type
    try:
        fn(**kwargs)
    except Exception:
        logger.debug("langfuse score emit failed (name=%s)", name, exc_info=True)
