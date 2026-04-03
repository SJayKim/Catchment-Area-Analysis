"""Chat API route — SSE streaming endpoint connected to LangGraph agent."""

import asyncio
import json
import logging
import re
import time

from fastapi import APIRouter
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from server.agent.graph import run_agent
from server.agent.history import ConversationHistory
from server.config import settings
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
# Summary detection patterns (used in ReAct mode only)
# ---------------------------------------------------------------------------

_GREETING_PATTERN = re.compile(
    r"^(안녕|하이|헬로|hi|hello|반갑|감사합니다|고마워|ㅎㅇ|좋은\s*아침|좋은\s*저녁)\s*[!?.ㅎㅋ]*\s*$",
    re.IGNORECASE,
)

_SUMMARY_PATTERNS = re.compile(
    r"(요약|분석|알려줘|어때|보여줘|정보|현황|상권을? 선택)"
)
_NON_SUMMARY_PATTERNS = re.compile(
    r"(비교|추천|뭐.*하면|위험|리스크|폐업|히트맵|시뮬|카페|한식|커피|치킨)"
)


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    district_code: str | None = None


@router.post("/chat")
async def chat(request: ChatRequest) -> EventSourceResponse:
    """Chat endpoint with SSE streaming via LangGraph agent."""

    session_id = request.session_id or "anonymous"
    session = await _get_session(session_id)
    da = get_data_access()

    # Resolve district info if code provided
    district_name = "미선택"
    data_quarter = "최신"
    district_center: dict | None = None
    district_type: str = "발달상권"

    if request.district_code:
        d = await da.districts.resolve_district(request.district_code)
        if d:
            district_name = d["name"]
            data_quarter = d.get("quarter", "최신")
            district_center = d.get("center")
            district_type = d.get("type", "발달상권")

        session["last_district_code"] = request.district_code
        session["last_district_name"] = district_name

    # Auto-detect district from message text — ONLY when no explicit code
    if not request.district_code:
        # 먼저 세션 컨텍스트 복원 시도
        if session.get("last_district_code"):
            request.district_code = session["last_district_code"]
            district_name = session.get("last_district_name", "미선택")
            d = await da.districts.resolve_district(request.district_code)
            if d:
                data_quarter = d.get("quarter", "최신")
                district_center = d.get("center")
                district_type = d.get("type", "발달상권")

        # 세션에도 없으면 자동감지
        if not request.district_code:
            detected = await da.districts.detect_district_by_name(request.message)
            if detected:
                request.district_code = detected["code"]
                district_name = detected["name"]
                d = await da.districts.resolve_district(detected["code"])
                if d:
                    data_quarter = d.get("quarter", "최신")
                    district_center = d.get("center")
                    district_type = d.get("type", "발달상권")
                session["last_district_code"] = detected["code"]
                session["last_district_name"] = detected["name"]

    # Summary pre-emit (ReAct mode only — PAE handles this via Planner+Actor)
    is_pae = settings.agent_mode == "pae"
    is_summary_request = False
    if not is_pae and request.district_code and _SUMMARY_PATTERNS.search(request.message):
        if not _NON_SUMMARY_PATTERNS.search(request.message):
            is_summary_request = True

    # Conversation history for PAE
    history: ConversationHistory = session["history"]
    conversation_history = history.get_recent() if is_pae else None

    async def event_generator():
        async with _chat_semaphore:
            # 인사 단축 (Agent 파이프라인 스킵 → <1s)
            if _GREETING_PATTERN.match(request.message.strip()):
                yield {"data": json.dumps({
                    "type": "text",
                    "content": "안녕하세요! 서울 상권 분석 AI 마켓스코프입니다.\n지도에서 상권을 선택하시거나, 분석할 상권명을 알려주세요!",
                }, ensure_ascii=False)}
                yield {"data": json.dumps({
                    "type": "suggestion",
                    "questions": ["강남역 상권 분석해줘", "홍대 어때?", "업종 추천해줘", "상권 비교하고 싶어"],
                }, ensure_ascii=False)}
                yield {"data": json.dumps({"type": "done"}, ensure_ascii=False)}
                return

            # Emit map_cmd to move map to the district being discussed
            if district_center:
                yield {"data": json.dumps({
                    "type": "map_cmd",
                    "action": "move",
                    "params": {
                        "lat": district_center["lat"],
                        "lng": district_center["lng"],
                        "zoom": 4,
                    },
                    "district_code": request.district_code,
                    "district_name": district_name,
                    "district_type": district_type,
                }, ensure_ascii=False)}

            # Emit summary card directly (ReAct mode only)
            if is_summary_request and request.district_code:
                try:
                    from server.agent.tools.district_summary import get_district_summary
                    summary_data = await get_district_summary(request.district_code)
                    if "error" not in summary_data:
                        yield {"data": json.dumps({
                            "type": "card",
                            "card_type": "summary",
                            "data": summary_data,
                        }, ensure_ascii=False)}
                except Exception:
                    logger.exception("Failed to generate summary card")

            collected_text = ""

            try:
                async for event in run_agent(
                    message=request.message,
                    district_code=request.district_code or "",
                    district_name=district_name,
                    data_quarter=data_quarter,
                    conversation_history=conversation_history,
                ):
                    # Collect text for history
                    if event.get("type") == "text":
                        collected_text += event.get("content", "")

                    yield {"data": json.dumps(event, ensure_ascii=False, default=str)}
            except Exception:
                logger.exception("SSE event generation failed")
                yield {"data": json.dumps(
                    {"type": "text", "content": "죄송합니다. 서비스에 일시적인 오류가 발생했습니다."},
                    ensure_ascii=False,
                )}
                yield {"data": json.dumps({"type": "done"}, ensure_ascii=False)}

            # Save conversation turns (PAE mode)
            if is_pae:
                history.add_turn(
                    role="user",
                    content=request.message,
                    district_code=request.district_code,
                )
                if collected_text:
                    history.add_turn(
                        role="assistant",
                        content=collected_text,
                        district_code=request.district_code,
                    )

    return EventSourceResponse(event_generator())
