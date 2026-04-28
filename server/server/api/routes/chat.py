"""Chat API route — SSE streaming endpoint connected to LangGraph agent."""

import asyncio
import json
import logging
import re
import secrets
import time

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from server.agent.graph import run_agent
from server.agent.history import ConversationHistory
from server.config import settings
from server.middleware.metrics import sse_connection_closed, sse_connection_opened
from server.repositories import get_data_access

router = APIRouter(prefix="/api", tags=["chat"])
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory session storage for district context retention
# ---------------------------------------------------------------------------

_sessions: dict[str, dict] = {}
_SESSION_TTL = 1800  # 30 minutes
_sessions_lock = asyncio.Lock()
_PRUNE_INTERVAL = 60  # seconds
_last_prune_time: float = 0.0
_MAX_CONCURRENT_CHATS = 20
_chat_semaphore = asyncio.Semaphore(_MAX_CONCURRENT_CHATS)

# GAP-C helper — mirrors EXCLUSION_PATTERNS in agent.utils.rewriter so
# chat-route auto-detection skips when the user is explicitly dropping an
# entity ("X 말고 Y", "X 대신 Y", "X 빼고 Y", "X 제외").
_EXCLUSION_PHRASE = re.compile(r"(말고|대신|빼고|제외)")


def _has_exclusion_phrase(message: str) -> bool:
    return bool(message and _EXCLUSION_PHRASE.search(message))


async def _get_session(session_id: str) -> dict:
    """Get or create session, pruning expired entries."""
    global _last_prune_time
    now = time.time()

    async with _sessions_lock:
        # 쓰로틀 pruning (60초에 1회)
        if now - _last_prune_time > _PRUNE_INTERVAL:
            expired = [k for k, v in _sessions.items() if now - v.get("last_active", 0) > _SESSION_TTL]
            for k in expired:
                del _sessions[k]
            _last_prune_time = now

        if session_id not in _sessions:
            # Evict oldest session if at capacity
            if len(_sessions) >= settings.session_max_count:
                oldest_key = min(_sessions, key=lambda k: _sessions[k].get("last_active", 0))
                del _sessions[oldest_key]
                logger.info(
                    "Session evicted (max_count=%d): %s",
                    settings.session_max_count,
                    oldest_key,
                )

            _sessions[session_id] = {
                "last_district_code": None,
                "last_district_name": None,
                "last_active": now,
                "history": ConversationHistory(
                    max_turns=settings.max_history_turns,
                    content_limit=settings.history_content_limit,
                ),
            }
        else:
            _sessions[session_id]["last_active"] = now

        return _sessions[session_id]


# ---------------------------------------------------------------------------
# Greeting shortcut pattern
# ---------------------------------------------------------------------------

_GREETING_PATTERN = re.compile(
    r"^(안녕하세요|안녕|하이|헬로|hi|hello|반갑습니다|반갑|감사합니다|감사|고마워|ㅎㅇ|좋은\s*아침|좋은\s*저녁)[!?.ㅎㅋ요]*\s*$",
    re.IGNORECASE,
)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=settings.chat_message_max_length)
    session_id: str | None = Field(None, max_length=64)
    district_code: str | None = Field(None, max_length=20)


@router.get("/health/detail")
async def health_detail(request: Request) -> dict:
    """Expose runtime metrics for load testing & monitoring."""
    from server.services.cache import get_cache_service

    # DB pool stats
    engine = getattr(request.app.state, "db_engine", None)
    if engine is not None:
        pool = engine.pool
        db_info = {
            "db_pool_size": pool.size(),
            "db_pool_checkedout": pool.checkedout(),
            "db_pool_overflow": pool.overflow(),
            "db_pool_checkedin": pool.checkedin(),
        }
    else:
        db_info = {
            "db_pool_size": 0,
            "db_pool_checkedout": 0,
            "db_pool_overflow": 0,
            "db_pool_checkedin": 0,
        }

    # Redis status
    cache = get_cache_service()
    redis_connected = False
    if hasattr(cache, "_redis") and cache._redis is not None:
        try:
            await cache._redis.ping()
            redis_connected = True
        except Exception:
            pass

    return {
        "semaphore_available": _chat_semaphore._value,
        "semaphore_max": _MAX_CONCURRENT_CHATS,
        "active_sessions": len(_sessions),
        **db_info,
        "redis_connected": redis_connected,
        "agent_mode": settings.agent_mode,
        "llm_provider": settings.llm_provider,
        "use_mock": settings.use_mock,
    }


@router.post("/chat")
async def chat(request: Request, body: ChatRequest) -> EventSourceResponse:
    """Chat endpoint with SSE streaming via LangGraph agent."""

    session_id = body.session_id or secrets.token_urlsafe(32)
    session = await _get_session(session_id)
    da = get_data_access()

    # Resolve district info if code provided
    district_name = "미선택"
    data_quarter = "최신"
    district_center: dict | None = None
    district_type: str = "발달상권"

    if body.district_code:
        d = await da.districts.resolve_district(body.district_code)
        if d:
            district_name = d["name"]
            data_quarter = d.get("quarter", "최신")
            district_center = d.get("center")
            district_type = d.get("type", "발달상권")

        session["last_district_code"] = body.district_code
        session["last_district_name"] = district_name

    # Auto-detect district from message text — ONLY when no explicit code.
    # Always *try* detection; only fall back to session when detection misses.
    # This fixes two bugs observed in Pass 1 sweep:
    #   (a) "아니 건대 요약으로 해줘" — session has 강남역, we'd reuse it
    #       instead of switching to the newly-named 건대.
    #   (b) "성수 카페말고 추천" — blanket 말고 skip drops 성수 detection,
    #       leaving Planner without a district → hallucination fallback.
    # Exclusion still takes effect via the Planner rewriter's excluded_tokens
    # (applied to the referenced-districts list).
    if not body.district_code:
        from server.agent.utils.rewriter import EXCLUSION_PATTERNS

        excluded: set[str] = set()
        for pat in EXCLUSION_PATTERNS:
            for m in pat.finditer(body.message or ""):
                tok = m.group(1)
                if tok:
                    excluded.add(tok)

        detected = await da.districts.detect_district_by_name(body.message)
        if detected:
            det_name = detected.get("name", "")
            det_in_excluded = any(e in det_name or det_name in e for e in excluded)
            if not det_in_excluded:
                body.district_code = detected["code"]
                district_name = det_name
                d = await da.districts.resolve_district(detected["code"])
                if d:
                    data_quarter = d.get("quarter", "최신")
                    district_center = d.get("center")
                    district_type = d.get("type", "발달상권")
                session["last_district_code"] = detected["code"]
                session["last_district_name"] = detected["name"]

        # Detection missed → fall back to session's last district.
        if not body.district_code and session.get("last_district_code"):
            body.district_code = session["last_district_code"]
            district_name = session.get("last_district_name", "미선택")
            d = await da.districts.resolve_district(body.district_code)
            if d:
                data_quarter = d.get("quarter", "최신")
                district_center = d.get("center")
                district_type = d.get("type", "발달상권")

    # Conversation history
    history: ConversationHistory = session["history"]
    conversation_history = history.get_recent()

    async def event_generator():
        sse_connection_opened()
        try:
            async for event in _event_generator_inner():
                yield event
        finally:
            sse_connection_closed()

    async def _event_generator_inner():
        async with _chat_semaphore:
            # Early bail-out: client already gone before we started.
            if await request.is_disconnected():
                logger.info("Client disconnected before chat stream started")
                return

            # 인사 단축 (Agent 파이프라인 스킵 → <1s)
            if _GREETING_PATTERN.match(body.message.strip()):
                yield {
                    "data": json.dumps(
                        {
                            "type": "text",
                            "content": (
                                "안녕하세요! 서울 상권 분석 AI 마켓스코프입니다.\n"
                                "지도에서 상권을 선택하시거나, 분석할 상권명을 알려주세요!"
                            ),
                        },
                        ensure_ascii=False,
                    )
                }
                yield {
                    "data": json.dumps(
                        {
                            "type": "suggestion",
                            "questions": [
                                "강남역 상권 분석해줘",
                                "홍대 어때?",
                                "업종 추천해줘",
                                "상권 비교하고 싶어",
                            ],
                        },
                        ensure_ascii=False,
                    )
                }
                yield {"data": json.dumps({"type": "done"}, ensure_ascii=False)}
                return

            # Emit map_cmd to move map to the district being discussed
            if district_center:
                if await request.is_disconnected():
                    return
                yield {
                    "data": json.dumps(
                        {
                            "type": "map_cmd",
                            "action": "move",
                            "params": {
                                "lat": district_center["lat"],
                                "lng": district_center["lng"],
                                "zoom": 4,
                            },
                            "district_code": body.district_code,
                            "district_name": district_name,
                            "district_type": district_type,
                        },
                        ensure_ascii=False,
                    )
                }

            collected_text = ""

            try:
                async with asyncio.timeout(settings.sse_connection_max_duration):
                    async for event in run_agent(
                        message=body.message,
                        district_code=body.district_code or "",
                        district_name=district_name,
                        data_quarter=data_quarter,
                        conversation_history=conversation_history,
                        session_id=session_id,
                        request_id=getattr(request.state, "request_id", ""),
                    ):
                        # Check for client disconnect each iteration
                        if await request.is_disconnected():
                            logger.info("Client disconnected mid-stream, cancelling agent")
                            return

                        # Collect text for history
                        if event.get("type") == "text":
                            collected_text += event.get("content", "")

                        # LLMOps L1 — request_id ↔ Langfuse trace_id 운영 로그 조인.
                        # trace_id=None 은 Langfuse 비활성/샘플링 탈락/timeout 시그널.
                        if event.get("type") == "done":
                            logger.info(
                                "agent_done request_id=%s session_id=%s district=%s trace_id=%s",
                                getattr(request.state, "request_id", "") or "-",
                                session_id,
                                body.district_code or "-",
                                event.get("trace_id") or "-",
                            )

                        yield {"data": json.dumps(event, ensure_ascii=False, default=str)}

            except TimeoutError:
                logger.warning(
                    "SSE connection exceeded max duration (%.0fs)",
                    settings.sse_connection_max_duration,
                )
                yield {
                    "data": json.dumps(
                        {"type": "text", "content": "\n\n(응답 시간이 초과되어 종료합니다.)"},
                        ensure_ascii=False,
                    )
                }
                yield {"data": json.dumps({"type": "done"}, ensure_ascii=False)}
            except Exception:
                logger.exception("SSE event generation failed")
                yield {
                    "data": json.dumps(
                        {"type": "text", "content": "죄송합니다. 서비스에 오류가 발생했습니다."},
                        ensure_ascii=False,
                    )
                }
                yield {"data": json.dumps({"type": "done"}, ensure_ascii=False)}

            # Save conversation turns
            history.add_turn(
                role="user",
                content=body.message,
                district_code=body.district_code,
            )
            if collected_text:
                history.add_turn(
                    role="assistant",
                    content=collected_text,
                    district_code=body.district_code,
                )

    return EventSourceResponse(
        event_generator(),
        ping=int(settings.sse_heartbeat_interval),  # keep-alive interval (seconds)
    )
