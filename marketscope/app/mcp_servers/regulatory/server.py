"""Regulatory MCP Server — 규제/인허가 정보 도구 서버."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

from app.mcp_servers.regulatory.tools import TOOL_REGISTRY

logger = logging.getLogger("mcp.regulatory.server")

_http_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _http_client
    _http_client = httpx.AsyncClient(timeout=30.0)
    logger.info("Regulatory MCP Server 시작")
    yield
    await _http_client.aclose()
    _http_client = None
    logger.info("Regulatory MCP Server 종료")


app = FastAPI(title="MarketScope Regulatory MCP Server", lifespan=lifespan)


class ToolCallRequest(BaseModel):
    name: str
    arguments: dict[str, Any] = {}


TOOL_LIST = [
    {"name": "regulatory.get_permits", "description": "업종별 필요 인허가 목록 조회"},
    {"name": "regulatory.get_zoning", "description": "용도지역 정보 조회"},
    {"name": "regulatory.get_business_requirements", "description": "업종별 영업 요건 조회"},
]


@app.get("/health")
async def health():
    return {"status": "ok", "server": "regulatory"}


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
        result = await tool_fn(request.arguments, _http_client)
        return result
    except Exception as e:
        logger.exception("도구 실행 중 오류: %s", request.name)
        return {"error": f"도구 실행 실패: {e}"}


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
    uvicorn.run(app, host="0.0.0.0", port=5104)
