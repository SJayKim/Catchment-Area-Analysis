"""News/SNS MCP Server — 네이버 API 기반 뉴스/블로그/트렌드 서버."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

from marketscope_mcp.news.tools import TOOL_REGISTRY

logger = logging.getLogger("mcp.news.server")

_http_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _http_client
    client_id = os.environ.get("DATA_API_NAVER_CLIENT_ID", "")
    client_secret = os.environ.get("DATA_API_NAVER_CLIENT_SECRET", "")

    _http_client = httpx.AsyncClient(
        timeout=30.0,
        headers={
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret,
        },
    )
    logger.info("News MCP Server 시작 (네이버 API 키 %s)", "설정됨" if client_id else "미설정")
    yield
    await _http_client.aclose()
    _http_client = None
    logger.info("News MCP Server 종료")


app = FastAPI(title="MarketScope News MCP Server", lifespan=lifespan)


class ToolCallRequest(BaseModel):
    name: str
    arguments: dict[str, Any] = {}


TOOL_LIST = [
    {"name": "news.search_blog", "description": "네이버 블로그 검색"},
    {"name": "news.search_news", "description": "네이버 뉴스 검색"},
    {"name": "news.get_naver_datalab", "description": "네이버 데이터랩 검색어 트렌드"},
]


@app.get("/health")
async def health():
    return {"status": "ok", "server": "news"}


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
    uvicorn.run(app, host="0.0.0.0", port=5103)
