"""분석 엔드포인트 — Redis 브로커 기반 서비스 분리 버전."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from marketscope_common.broker.redis_broker import RedisBroker

router = APIRouter()

# ---------------------------------------------------------------------------
# Redis Broker 싱글턴 (app lifespan에서 초기화)
# ---------------------------------------------------------------------------
_broker: RedisBroker | None = None


async def init_broker(redis_url: str) -> RedisBroker:
    """API 시작 시 Redis Broker 초기화. lifespan에서 호출."""
    global _broker
    _broker = RedisBroker(redis_url=redis_url)
    await _broker.connect()
    return _broker


async def close_broker() -> None:
    """API 종료 시 Redis Broker 정리."""
    global _broker
    if _broker is not None:
        await _broker.close()
        _broker = None


def _get_broker() -> RedisBroker:
    if _broker is None:
        raise RuntimeError("RedisBroker not initialized. Call init_broker() first.")
    return _broker


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
async def create_analysis(request: AnalysisCreateRequest):
    """새 분석 요청 생성 → Redis Stream에 발행."""
    broker = _get_broker()
    request_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    # Redis Stream에 분석 요청 발행 (Engine Worker가 소비)
    await broker.publish_request(
        request_id=request_id,
        query=request.query,
        depth=request.depth,
        location=request.location or "",
        industry=request.industry or "",
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
    """분석 상태/결과 조회 — Redis Hash에서 조회."""
    broker = _get_broker()

    status_data = await broker.get_status(request_id)
    if status_data is None:
        return _error_response(
            status_code=404,
            code="ANALYSIS_NOT_FOUND",
            message="분석을 찾을 수 없습니다",
            request_id=request_id,
        )

    response: dict[str, Any] = {
        "request_id": request_id,
        **status_data,
    }

    # 완료 상태면 결과도 포함
    if status_data.get("status") == "completed":
        result = await broker.get_result(request_id)
        if result is not None:
            response["result"] = result

    return response


@router.get("/{request_id}/cost")
async def get_analysis_cost(request_id: str):
    """분석 요청의 토큰 사용량 및 비용 상세 조회."""
    broker = _get_broker()

    status_data = await broker.get_status(request_id)
    if status_data is None:
        return _error_response(
            status_code=404,
            code="ANALYSIS_NOT_FOUND",
            message="분석을 찾을 수 없습니다",
            request_id=request_id,
        )

    if status_data.get("status") != "completed":
        return JSONResponse(
            status_code=200,
            content={
                "request_id": request_id,
                "status": status_data.get("status", "unknown"),
                "message": "분석이 아직 완료되지 않아 비용 정보가 없습니다",
                "token_usage": None,
            },
        )

    result = await broker.get_result(request_id)
    token_usage = result.get("token_usage") if result else None

    if token_usage is None:
        token_usage = {
            "total_tokens": 0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_cost_usd": 0.0,
            "per_agent": [],
        }

    return {
        "request_id": request_id,
        "status": "completed",
        **token_usage,
    }


@router.get("/{request_id}/stream")
async def stream_analysis(request_id: str, request: Request):
    """분석 진행 상태 SSE 스트리밍 — Redis Pub/Sub 구독."""
    broker = _get_broker()

    # 상태 확인: 존재하는 요청인지 검증
    status_data = await broker.get_status(request_id)
    if status_data is None:
        return _error_response(
            status_code=404,
            code="ANALYSIS_NOT_FOUND",
            message="분석을 찾을 수 없습니다",
            request_id=request_id,
        )

    # 이미 완료된 경우 즉시 done 이벤트 반환
    if status_data.get("status") in ("completed", "failed"):
        async def _replay():
            yield f"data: {json.dumps({'type': 'done', 'status': status_data.get('status', 'completed')}, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            _replay(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    async def event_generator():
        """Redis Pub/Sub에서 진행률 이벤트를 SSE로 스트리밍."""
        try:
            async for event in broker.subscribe_progress(request_id):
                # 클라이언트 연결 끊김 확인
                if await request.is_disconnected():
                    break

                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

                # done 또는 error면 subscribe_progress에서 자동 종료
        except Exception:
            yield f"data: {json.dumps({'type': 'error', 'message': '스트리밍 연결 오류'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
