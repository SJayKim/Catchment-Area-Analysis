"""Real Estate MCP Server — 부동산 정보 도구 서버."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

from app.mcp_servers.real_estate.tools import TOOL_REGISTRY

logger = logging.getLogger("mcp.real_estate.server")

_http_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _http_client
    api_key = os.environ.get("DATA_API_PUBLIC_DATA_KEY", "")
    _http_client = httpx.AsyncClient(timeout=30.0)
    _http_client._api_key = api_key  # noqa: SLF001
    logger.info("Real Estate MCP Server 시작")
    yield
    await _http_client.aclose()
    _http_client = None
    logger.info("Real Estate MCP Server 종료")


app = FastAPI(title="MarketScope Real Estate MCP Server", lifespan=lifespan)


class ToolCallRequest(BaseModel):
    name: str
    arguments: dict[str, Any] = {}


TOOL_LIST = [
    {"name": "real_estate.get_rent_info", "description": "상가 임대료 시세 조회"},
    {"name": "real_estate.get_transaction_price", "description": "상가 실거래가 조회"},
    {"name": "real_estate.get_vacancy_rate", "description": "상가 공실률 조회"},
    {"name": "real_estate.get_premium_estimate", "description": "권리금 추정"},
]


@app.get("/health")
async def health():
    return {"status": "ok", "server": "real_estate"}


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
    uvicorn.run(app, host="0.0.0.0", port=5102)
