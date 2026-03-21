"""Maps/GIS MCP Server — 카카오 API 기반 지도 도구 서버."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from app.mcp_servers.maps.kakao_client import KakaoLocalClient
from app.mcp_servers.maps.tools import TOOL_REGISTRY

logger = logging.getLogger("mcp.maps.server")

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

_kakao_client: KakaoLocalClient | None = None


def _get_kakao_client() -> KakaoLocalClient:
    if _kakao_client is None:
        raise RuntimeError("KakaoLocalClient가 초기화되지 않았습니다.")
    return _kakao_client


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    global _kakao_client

    api_key = os.environ.get("DATA_API_KAKAO_REST_KEY", "")
    if not api_key:
        logger.warning("DATA_API_KAKAO_REST_KEY 환경변수가 설정되지 않았습니다.")

    _kakao_client = KakaoLocalClient(api_key)
    logger.info("Maps MCP Server 시작 (카카오 API 키 %s)", "설정됨" if api_key else "미설정")

    yield

    await _kakao_client.close()
    _kakao_client = None
    logger.info("Maps MCP Server 종료")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="MarketScope Maps MCP Server", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class ToolCallRequest(BaseModel):
    name: str
    arguments: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Tool metadata
# ---------------------------------------------------------------------------

TOOL_LIST = [
    {"name": "maps.geocode", "description": "주소 → 좌표 변환"},
    {"name": "maps.reverse_geocode", "description": "좌표 → 주소 변환"},
    {"name": "maps.search_nearby", "description": "주변 카테고리 검색"},
    {"name": "maps.search_keyword", "description": "키워드 검색"},
    {"name": "maps.get_walking_route", "description": "도보 경로 계산"},
    {"name": "maps.get_transit_nearby", "description": "주변 교통시설 검색"},
    {"name": "maps.get_category_pois", "description": "카테고리별 POI 검색"},
]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    return {"status": "ok", "server": "maps"}


@app.get("/tools/list")
async def list_tools():
    return TOOL_LIST


@app.post("/tools/call")
async def call_tool(request: ToolCallRequest):
    logger.info("도구 호출: %s | arguments=%s", request.name, request.arguments)

    tool_fn = TOOL_REGISTRY.get(request.name)
    if tool_fn is None:
        return {
            "error": f"알 수 없는 도구입니다: {request.name}",
            "available_tools": [t["name"] for t in TOOL_LIST],
        }

    try:
        kakao = _get_kakao_client()
        result = await tool_fn(request.arguments, kakao)
        return result
    except Exception as e:
        logger.exception("도구 실행 중 오류: %s", request.name)
        return {"error": f"도구 실행 실패: {e}"}


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
    uvicorn.run(app, host="0.0.0.0", port=5101)
