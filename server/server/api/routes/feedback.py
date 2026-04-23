"""Feedback — thin Langfuse score proxy.

`/api/feedback/score` 는 프론트의 L1 (카드 👍👎) 에서만 호출된다.
Langfuse 가 미활성/오류일 때도 HTTP 204 로 silently drop — UX 영향 0.
(2026-04-23 Plan: landing-onboarding-feedback §6 L1)
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from server.config import settings
from server.services.cache import get_cache_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["feedback"])


class FeedbackScoreRequest(BaseModel):
    trace_id: str = Field(..., min_length=1, max_length=128)
    value: str = Field(..., pattern=r"^(up|down)$")
    reason: str | None = Field(None, max_length=32)
    comment: str | None = Field(None, max_length=120)


# 세션 스팸 가드 — trace_id 당 1회만 기록. 서버 재시작 시 휘발 (세션은 스토어에서도 dedup).
_IDEMP_TTL = 24 * 60 * 60  # 24h


async def _already_recorded(trace_id: str) -> bool:
    cache = get_cache_service()
    key = f"feedback:seen:{trace_id}"
    hit = await cache.get(key)
    if hit is not None:
        return True
    await cache.set(key, {"ts": int(time.time())}, ttl=_IDEMP_TTL)
    return False


@router.post("/feedback/score")
async def post_feedback_score(payload: FeedbackScoreRequest) -> Response:
    """Translate up/down to Langfuse numeric score. 204 when Langfuse is off."""
    if not settings.langfuse_enabled:
        return Response(status_code=204)

    # Idempotency — 동일 trace_id 두 번째 이후 요청은 204 silent drop
    if await _already_recorded(payload.trace_id):
        return Response(status_code=204)

    # Langfuse v3 — tracer 싱글톤을 재사용 (handler 와 동일 client 공유 → 연결 중복 제거).
    from server.services.langfuse_tracer import get_client_or_none

    client = get_client_or_none()
    if client is None:
        return Response(status_code=204)

    try:
        numeric = 1.0 if payload.value == "up" else -1.0
        comment_parts: list[str] = []
        if payload.reason:
            comment_parts.append(payload.reason)
        if payload.comment:
            comment_parts.append(payload.comment)
        comment = " | ".join(comment_parts) if comment_parts else None

        client.score(
            trace_id=payload.trace_id,
            name="user_feedback",
            value=numeric,
            comment=comment,
        )
        try:
            client.flush()
        except Exception:  # best effort
            pass
    except Exception:
        # 인증/네트워크/버전 어떤 오류든 UX 에 영향 주지 않음
        logger.warning("langfuse score failed", exc_info=True)
        return Response(status_code=204)

    return Response(status_code=202)
