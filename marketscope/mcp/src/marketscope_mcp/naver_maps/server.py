"""Naver Maps MCP Server — 네이버 지도/장소 도구 서버."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from marketscope_mcp.naver_maps.api_client import NaverMapsClient
from marketscope_mcp.naver_maps.tools import TOOL_REGISTRY

logger = logging.getLogger("mcp.naver_maps.server")

_naver_client: NaverMapsClient | None = None


def _get_naver_client() -> NaverMapsClient:
    if _naver_client is None:
        raise RuntimeError("NaverMapsClient가 초기화되지 않았습니다.")
    return _naver_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _naver_client
    client_id = os.environ.get("DATA_API_NAVER_CLIENT_ID", "")
    client_secret = os.environ.get("DATA_API_NAVER_CLIENT_SECRET", "")
    if not client_id:
        logger.warning("DATA_API_NAVER_CLIENT_ID 환경변수가 설정되지 않았습니다.")
    _naver_client = NaverMapsClient(client_id, client_secret)
    logger.info("Naver Maps MCP Server 시작")
    yield
    await _naver_client.close()
    _naver_client = None
    logger.info("Naver Maps MCP Server 종료")


app = FastAPI(title="MarketScope Naver Maps MCP Server", lifespan=lifespan)


class ToolCallRequest(BaseModel):
    name: str
    arguments: dict[str, Any] = {}


TOOL_LIST = [
    {"name": "naver_maps.geocode", "description": "주소 → 좌표 변환 (네이버)"},
    {"name": "naver_maps.reverse_geocode", "description": "좌표 → 주소 변환 (네이버)"},
    {"name": "naver_maps.local_search", "description": "장소 검색 (네이버 검색 API)"},
    {"name": "naver_maps.directions", "description": "경로 탐색 (네이버 길찾기)"},
    {"name": "naver_maps.static_map", "description": "정적 지도 이미지 URL 생성"},
]


@app.get("/health")
async def health():
    return {"status": "ok", "server": "naver_maps"}


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
        client = _get_naver_client()
        return await tool_fn(request.arguments, client)
    except Exception as e:
        logger.exception("도구 실행 중 오류: %s", request.name)
        return {"error": f"도구 실행 실패: {e}"}


if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
    uvicorn.run(app, host="0.0.0.0", port=5108)
