"""Langfuse LLM 트레이싱 핸들러 — LiteLLM 콜백 연동."""

from __future__ import annotations

import os
from typing import Any, Optional

from app.logging_config import get_logger

logger = get_logger("monitoring.langfuse")

_langfuse_client: Any = None


def setup_langfuse(settings: Any) -> None:
    """Langfuse를 초기화하고 LiteLLM 콜백을 등록한다."""
    global _langfuse_client

    if not settings.langfuse_enabled:
        logger.info("langfuse.disabled")
        return

    try:
        import litellm
        from langfuse import Langfuse

        # LiteLLM이 참조하는 환경변수 설정
        os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key or "")
        os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key or "")
        os.environ.setdefault("LANGFUSE_HOST", settings.langfuse_host)

        _langfuse_client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )

        # LiteLLM 네이티브 콜백 등록
        litellm.success_callback = ["langfuse"]
        litellm.failure_callback = ["langfuse"]

        logger.info("langfuse.enabled", host=settings.langfuse_host)

    except ImportError as e:
        logger.warning("langfuse.import_error", error=str(e))
    except Exception as e:
        logger.error("langfuse.init_error", error=str(e))


def get_langfuse() -> Any:
    """Langfuse 클라이언트 인스턴스를 반환한다."""
    return _langfuse_client


def create_trace(
    session_id: str,
    name: str,
    metadata: Optional[dict[str, Any]] = None,
) -> Any:
    """분석 세션용 Langfuse trace를 생성한다."""
    if not _langfuse_client:
        return None
    try:
        return _langfuse_client.trace(
            name=name,
            session_id=session_id,
            metadata=metadata or {},
        )
    except Exception as e:
        logger.warning("langfuse.trace_error", error=str(e))
        return None


async def flush_langfuse() -> None:
    """Langfuse 버퍼를 플러시한다."""
    if _langfuse_client:
        try:
            _langfuse_client.flush()
            logger.info("langfuse.flushed")
        except Exception as e:
            logger.warning("langfuse.flush_error", error=str(e))


async def shutdown_langfuse() -> None:
    """Langfuse를 안전하게 종료한다."""
    global _langfuse_client
    if _langfuse_client:
        try:
            _langfuse_client.flush()
            _langfuse_client.shutdown()
            logger.info("langfuse.shutdown")
        except Exception as e:
            logger.warning("langfuse.shutdown_error", error=str(e))
        finally:
            _langfuse_client = None
