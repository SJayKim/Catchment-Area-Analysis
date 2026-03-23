"""Database MCP Server — PostGIS 공간쿼리 도구 서버."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from marketscope_mcp.database.db_client import close_pool, get_pool
from marketscope_mcp.database.tools import TOOL_REGISTRY

logger = logging.getLogger("mcp.database.server")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await get_pool()
        logger.info("Database MCP Server 시작 (커넥션 풀 초기화)")
    except Exception as e:
        logger.warning("Database 커넥션 풀 초기화 실패: %s", e)
    yield
    await close_pool()
    logger.info("Database MCP Server 종료")


app = FastAPI(title="MarketScope Database MCP Server", lifespan=lifespan)


class ToolCallRequest(BaseModel):
    name: str
    arguments: dict[str, Any] = {}


TOOL_LIST = [
    {"name": "database.query_nearby_stores", "description": "반경 내 점포 조회 (PostGIS)"},
    {"name": "database.query_population_grid", "description": "격자별 인구 데이터 조회"},
    {"name": "database.query_revenue_by_area", "description": "지역별 매출 데이터 조회"},
    {"name": "database.query_commercial_district", "description": "상권 정보 조회"},
    {"name": "database.execute_spatial_query", "description": "범용 공간 쿼리 (SELECT 전용)"},
]


@app.get("/health")
async def health():
    return {"status": "ok", "server": "database"}


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
        return await tool_fn(request.arguments)
    except Exception as e:
        logger.exception("도구 실행 중 오류: %s", request.name)
        return {"error": f"도구 실행 실패: {e}"}


if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
    uvicorn.run(app, host="0.0.0.0", port=5106)
