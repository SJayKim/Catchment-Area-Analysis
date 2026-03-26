"""Chat API route — SSE streaming endpoint connected to LangGraph agent."""

import json
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from server.agent.graph import run_agent
from server.config import settings

router = APIRouter(prefix="/api", tags=["chat"])
logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    district_code: str | None = None


@router.post("/chat")
async def chat(request: ChatRequest) -> EventSourceResponse:
    """Chat endpoint with SSE streaming via LangGraph ReAct agent."""

    # Resolve district info if code provided
    district_name = "미선택"
    data_quarter = "최신"
    district_center: dict | None = None

    if request.district_code:
        if settings.use_mock:
            from server.agent.tools.mock_data import DISTRICTS
            d = DISTRICTS.get(request.district_code)
            if d:
                district_name = d["name"]
                data_quarter = d["quarter"]
                district_center = d.get("center")
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

    async def event_generator():
        # Emit map_cmd to move map to the district being discussed
        if district_center:
            yield {"data": json.dumps({
                "type": "map_cmd",
                "action": "move",
                "params": {
                    "lat": district_center["lat"],
                    "lng": district_center["lng"],
                    "zoom": 5,
                },
            }, ensure_ascii=False)}

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
