"""Langfuse tracer — LLMOps L1 진입점.

graceful degrade 원칙:
- Langfuse 비활성/키 미설정/import 실패/런타임 오류 시 **None** 반환.
- `/api/chat` 는 Langfuse 유무와 무관하게 동작 (best-effort tracing).
- 반복 실패 시 `_tracer_valid` 플래그로 재시도 회피 (`_anthropic_valid` 패턴 답습).

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
    # secrets.randbelow 기반 결정적 샘플링 — 매번 새 난수
    return secrets.randbelow(10_000) < int(rate * 10_000)


def get_langfuse_handler(session_id: str, request_id: str):
    """CallbackHandler 생성 또는 None.

    None 반환 조건:
    - Langfuse disabled (키 미설정)
    - 이전 실패로 `_tracer_valid=False`
    - 샘플링 탈락
    - import 실패
    - 생성자 예외

    모든 오류는 warn 로그만 남기고 서비스에는 영향 없음.
    """
    global _tracer_valid

    if not _tracer_valid:
        return None
    if not settings.langfuse_enabled:
        return None
    if not should_sample():
        return None

    try:
        from langfuse.callback import CallbackHandler
    except ImportError:
        logger.warning("langfuse package unavailable, tracing disabled")
        _tracer_valid = False
        return None
    except Exception:
        logger.warning("langfuse import failed unexpectedly, tracing disabled", exc_info=True)
        _tracer_valid = False
        return None

    try:
        handler = CallbackHandler(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
            session_id=_hash_session(session_id),
            trace_name="marketscope.pae",
            metadata={
                "request_id": request_id,
                "llm_provider": settings.llm_provider,
                "agent_mode": settings.agent_mode,
                "use_mock": settings.use_mock,
            },
        )
    except Exception:
        # 인증/네트워크/버전 불일치 모두 포함. 한 번만 경고.
        logger.warning("langfuse handler creation failed, tracing disabled", exc_info=True)
        _tracer_valid = False
        return None

    return handler


def get_trace_id(handler) -> str | None:
    """handler 에서 trace_id 추출. v2 SDK 는 `.trace_id`, 구버전 fallback 포함."""
    if handler is None:
        return None
    for attr in ("trace_id", "last_trace_id"):
        val = getattr(handler, attr, None)
        if val:
            return str(val)
    # get_trace_id() 메서드 방식 (langfuse>=2.x 일부 버전)
    fn = getattr(handler, "get_trace_id", None)
    if callable(fn):
        try:
            val = fn()
            if val:
                return str(val)
        except Exception:
            pass
    return None


def flush(handler) -> None:
    """동기/비동기 flush 모두 best-effort. 예외 삼킴."""
    if handler is None:
        return
    fn = getattr(handler, "flush", None)
    if not callable(fn):
        return
    try:
        fn()
    except Exception:
        logger.debug("langfuse flush failed", exc_info=True)
