"""Chat API route — SSE streaming endpoint connected to LangGraph agent."""

import json
import logging
import re
import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from server.agent.graph import run_agent
from server.config import settings

router = APIRouter(prefix="/api", tags=["chat"])
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory session storage for district context retention (Feature 2)
# ---------------------------------------------------------------------------

_sessions: dict[str, dict] = {}
_SESSION_TTL = 1800  # 30 minutes


def _get_session(session_id: str) -> dict:
    """Get or create session, pruning expired entries."""
    now = time.time()
    # Prune expired sessions (lazy cleanup)
    expired = [k for k, v in _sessions.items() if now - v.get("last_active", 0) > _SESSION_TTL]
    for k in expired:
        del _sessions[k]

    if session_id not in _sessions:
        _sessions[session_id] = {
            "last_district_code": None,
            "last_district_name": None,
            "last_active": now,
        }
    else:
        _sessions[session_id]["last_active"] = now

    return _sessions[session_id]


# ---------------------------------------------------------------------------
# Summary detection patterns
# ---------------------------------------------------------------------------

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
    """Chat endpoint with SSE streaming via LangGraph ReAct agent."""

    session_id = request.session_id or "anonymous"
    session = _get_session(session_id)

    # Resolve district info if code provided
    district_name = "미선택"
    data_quarter = "최신"
    district_center: dict | None = None
    district_type: str = "발달상권"

    if request.district_code:
        if settings.use_mock:
            from server.agent.tools.mock_data import DISTRICTS
            d = DISTRICTS.get(request.district_code)
            if d:
                district_name = d["name"]
                data_quarter = d["quarter"]
                district_center = d.get("center")
                district_type = d.get("type", "발달상권")
        else:
            from sqlalchemy import select
            from server.api.deps import get_db
            from server.models.district import District

            async for db in get_db():
                result = await db.execute(
                    select(District.district_name, District.data_quarter).where(
                        District.district_code == request.district_code
                    )
                )
                row = result.first()
                if row:
                    district_name = row.district_name
                    data_quarter = row.data_quarter

        # Update session with explicitly provided district
        session["last_district_code"] = request.district_code
        session["last_district_name"] = district_name

    # Auto-detect district from message text (even when district_code is provided,
    # in case the user mentions a DIFFERENT district in their message)
    if settings.use_mock:
        from server.agent.tools.mock_data import DISTRICTS
        for code, d in DISTRICTS.items():
            if d["name"] in request.message and code != request.district_code:
                request.district_code = code
                district_name = d["name"]
                data_quarter = d["quarter"]
                district_center = d.get("center")
                district_type = d.get("type", "발달상권")
                session["last_district_code"] = code
                session["last_district_name"] = district_name
                break

    # Fallback: restore district from session if still not resolved
    if not request.district_code and session.get("last_district_code"):
        request.district_code = session["last_district_code"]
        district_name = session.get("last_district_name", "미선택")
        if settings.use_mock:
            from server.agent.tools.mock_data import DISTRICTS
            d = DISTRICTS.get(request.district_code)
            if d:
                data_quarter = d["quarter"]
                district_center = d.get("center")
                district_type = d.get("type", "발달상권")

    # Determine if this is a summary-type request
    is_summary_request = False
    if request.district_code and _SUMMARY_PATTERNS.search(request.message):
        if not _NON_SUMMARY_PATTERNS.search(request.message):
            is_summary_request = True

    async def event_generator():
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

        # Emit summary card directly when a summary request is detected
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

        try:
            async for event in run_agent(
                message=request.message,
                district_code=request.district_code or "",
                district_name=district_name,
                data_quarter=data_quarter,
            ):
                yield {"data": json.dumps(event, ensure_ascii=False, default=str)}
        except Exception:
            logger.exception("SSE event generation failed")
            yield {"data": json.dumps(
                {"type": "text", "content": "죄송합니다. 서비스에 일시적인 오류가 발생했습니다."},
                ensure_ascii=False,
            )}
            yield {"data": json.dumps({"type": "done"}, ensure_ascii=False)}

    return EventSourceResponse(event_generator())
