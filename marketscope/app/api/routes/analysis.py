"""분석 엔드포인트."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.services.analysis_service import AnalysisService

router = APIRouter()

# ---------------------------------------------------------------------------
# In-memory analysis store with TTL-based auto-expiry
# ---------------------------------------------------------------------------
_STORE_TTL_SECONDS: int = 3600  # 1 hour

_analysis_store: dict[str, dict[str, Any]] = {}
_analysis_queues: dict[str, asyncio.Queue[dict[str, Any] | None]] = {}


def _cleanup_expired_entries() -> None:
    """Remove entries older than _STORE_TTL_SECONDS from the in-memory store."""
    now = time.monotonic()
    expired = [
        rid
        for rid, entry in _analysis_store.items()
        if now - entry.get("_created_mono", now) > _STORE_TTL_SECONDS
    ]
    for rid in expired:
        _analysis_store.pop(rid, None)
        _analysis_queues.pop(rid, None)


# ---------------------------------------------------------------------------
# Structured error response
# ---------------------------------------------------------------------------
class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: Optional[str] = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


def _error_response(
    status_code: int,
    code: str,
    message: str,
    request_id: str | None = None,
) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorDetail(code=code, message=message, request_id=request_id)
    )
    return JSONResponse(status_code=status_code, content=body.model_dump())


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------
class AnalysisCreateRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=500, description="분석 질의")
    location: Optional[str] = Field(None, description="위치 힌트")
    industry: Optional[str] = Field(None, description="업종 힌트")
    depth: Literal["quick", "standard", "deep"] = Field(
        "standard", description="분석 깊이 (quick | standard | deep)"
    )


class AnalysisCreateResponse(BaseModel):
    request_id: str
    status: str = "queued"
    estimated_duration_sec: int
    stream_url: str
    created_at: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.post("", response_model=AnalysisCreateResponse, status_code=202)
async def create_analysis(
    request: AnalysisCreateRequest,
    background_tasks: BackgroundTasks,
):
    """새 분석 요청 생성."""
    # Housekeeping: purge expired entries before creating a new one
    _cleanup_expired_entries()

    request_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
    _analysis_queues[request_id] = queue

    _analysis_store[request_id] = {
        "request_id": request_id,
        "status": "queued",
        "query": request.query,
        "depth": request.depth,
        "created_at": created_at,
        "result": None,
        "events": [],
        "_created_mono": time.monotonic(),
    }

    background_tasks.add_task(
        _run_analysis,
        request_id=request_id,
        query=request.query,
    )

    duration_map: dict[str, int] = {"quick": 60, "standard": 180, "deep": 420}

    return AnalysisCreateResponse(
        request_id=request_id,
        status="queued",
        estimated_duration_sec=duration_map[request.depth],
        stream_url=f"/api/v1/analysis/{request_id}/stream",
        created_at=created_at,
    )


@router.get("/{request_id}")
async def get_analysis(request_id: str):
    """분석 결과 조회."""
    if request_id not in _analysis_store:
        return _error_response(
            status_code=404,
            code="ANALYSIS_NOT_FOUND",
            message="분석을 찾을 수 없습니다",
            request_id=request_id,
        )
    entry = _analysis_store[request_id]
    # Strip internal bookkeeping keys before returning
    return {k: v for k, v in entry.items() if not k.startswith("_")}


@router.get("/{request_id}/stream")
async def stream_analysis(request_id: str, request: Request):
    """분석 진행 상태 SSE 스트리밍."""
    if request_id not in _analysis_store:
        return _error_response(
            status_code=404,
            code="ANALYSIS_NOT_FOUND",
            message="분석을 찾을 수 없습니다",
            request_id=request_id,
        )

    queue = _analysis_queues.get(request_id)
    if queue is None:
        # Analysis exists but already finished before a stream was opened.
        # Return a single done event.
        store = _analysis_store[request_id]

        async def _replay():
            for ev in store.get("events", []):
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'status': store.get('status', 'completed')}, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            _replay(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    async def event_generator():
        """Yield SSE events from the per-connection asyncio.Queue.

        A heartbeat comment is sent every 15 seconds to keep the
        connection alive through proxies / load balancers.
        """
        heartbeat_interval = 15.0  # seconds

        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break

                try:
                    event = await asyncio.wait_for(
                        queue.get(), timeout=heartbeat_interval
                    )
                except asyncio.TimeoutError:
                    # Send SSE comment as heartbeat
                    yield ": heartbeat\n\n"
                    continue

                # None is the sentinel that signals the stream is done
                if event is None:
                    break

                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        finally:
            # Cleanup: remove queue reference so memory can be reclaimed
            _analysis_queues.pop(request_id, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Background task
# ---------------------------------------------------------------------------
async def _run_analysis(request_id: str, query: str) -> None:
    """백그라운드에서 LangGraph 분석 파이프라인 실행."""
    store = _analysis_store.get(request_id)
    if store is None:
        return

    queue = _analysis_queues.get(request_id)

    def _emit(event: dict[str, Any]) -> None:
        """Append event to the store and push it to the queue."""
        store["events"].append(event)
        if queue is not None:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass  # drop if consumer cannot keep up

    store["status"] = "processing"
    _emit({"type": "status", "status": "processing", "message": "분석을 시작합니다..."})

    try:
        service = AnalysisService()
        result = await service.run_analysis(
            session_id=request_id,
            user_input=query,
            on_progress=_emit,
        )
        store["result"] = result
        store["status"] = "completed"
        _emit({"type": "status", "status": "completed", "message": "분석이 완료되었습니다."})

    except Exception as e:
        store["status"] = "failed"
        _emit({
            "type": "error",
            "code": "ANALYSIS_FAILED",
            "message": str(e),
        })
    finally:
        # Send sentinel to signal stream end
        if queue is not None:
            try:
                queue.put_nowait(None)
            except asyncio.QueueFull:
                pass
