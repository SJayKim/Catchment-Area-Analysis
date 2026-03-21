"""Google Maps MCP Server — Google Places/Geocoding 도구 서버."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from app.mcp_servers.google_maps.api_client import GoogleMapsClient
from app.mcp_servers.google_maps.tools import TOOL_REGISTRY

logger = logging.getLogger("mcp.google_maps.server")

_google_client: GoogleMapsClient | None = None


def _get_google_client() -> GoogleMapsClient:
    if _google_client is None:
        raise RuntimeError("GoogleMapsClient가 초기화되지 않았습니다.")
    return _google_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _google_client
    api_key = os.environ.get("DATA_API_GOOGLE_MAPS_KEY", "")
    if not api_key:
        logger.warning("DATA_API_GOOGLE_MAPS_KEY 환경변수가 설정되지 않았습니다.")
    _google_client = GoogleMapsClient(api_key)
    logger.info("Google Maps MCP Server 시작")
    yield
    await _google_client.close()
    _google_client = None
    logger.info("Google Maps MCP Server 종료")


app = FastAPI(title="MarketScope Google Maps MCP Server", lifespan=lifespan)


class ToolCallRequest(BaseModel):
    name: str
    arguments: dict[str, Any] = {}


TOOL_LIST = [
    {"name": "google_maps.geocode", "description": "주소 → 좌표 변환 (Google)"},
    {"name": "google_maps.reverse_geocode", "description": "좌표 → 주소 변환 (Google)"},
    {"name": "google_maps.nearby_search", "description": "주변 장소 검색 (Google Places)"},
    {"name": "google_maps.place_details", "description": "장소 상세 정보 (리뷰, 영업시간)"},
    {"name": "google_maps.directions", "description": "경로 탐색 (Google Directions)"},
]


@app.get("/health")
async def health():
    return {"status": "ok", "server": "google_maps"}


@app.get("/tools/list")
async def list_tools():
    return TOOL_LIST


@app.post("/tools/call")
async def call_tool(request: ToolCallRequest):
    logger.info("도구 호출: %s", request.name)
    tool_fn = TOOL_REGISTRY.get(request.name)
    if tool_fn is None:
        return {"error": f"알 수 없는 도구입니다: {request.name}", "available_tools": [t["name"] for t in TOOL_LIST]}
    try:
        client = _get_google_client()
        return await tool_fn(request.arguments, client)
    except Exception as e:
        logger.exception("도구 실행 중 오류: %s", request.name)
        return {"error": f"도구 실행 실패: {e}"}


if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
    uvicorn.run(app, host="0.0.0.0", port=5107)
