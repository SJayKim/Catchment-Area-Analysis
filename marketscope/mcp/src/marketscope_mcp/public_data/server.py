"""Public Data MCP Server — 공공데이터 도구 서버 (port 5100).

8개 도구 + 3개 리소스를 제공:
- 유동인구, 추정매출, 점포, 주민등록인구, 직장인구, 생활인구, 카드매출
- 업종코드, 상권코드, 행정동코드 리소스
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from marketscope_mcp.public_data.resources import RESOURCE_REGISTRY
from marketscope_mcp.public_data.tools import TOOL_REGISTRY, create_api_clients

logger = logging.getLogger("mcp.public_data.server")

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

_api_clients: dict[str, Any] | None = None


def get_api_clients() -> dict[str, Any]:
    if _api_clients is None:
        raise RuntimeError("API 클라이언트가 초기화되지 않았습니다.")
    return _api_clients


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _api_clients

    _api_clients = create_api_clients()
    logger.info(
        "Public Data MCP Server 시작 (API 키: 서울=%s, KOSIS=%s, SEMAS=%s)",
        "✅" if _api_clients.get("seoul_key") else "❌",
        "✅" if _api_clients.get("kosis_key") else "❌",
        "✅" if _api_clients.get("semas_key") else "❌",
    )

    yield

    # httpx 클라이언트 정리
    client = _api_clients.get("http_client")
    if client:
        await client.aclose()
    _api_clients = None
    logger.info("Public Data MCP Server 종료")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="MarketScope Public Data MCP Server", lifespan=lifespan)


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
    {"name": "public_data.get_floating_population", "description": "유동인구 조회 (SEMAS 분기별)"},
    {"name": "public_data.get_estimated_revenue", "description": "추정매출 조회 (SEMAS 분기별)"},
    {"name": "public_data.get_store_list", "description": "점포 목록 조회 (위치/업종 기반)"},
    {"name": "public_data.get_store_count_change", "description": "점포 증감 추이 (분기 비교)"},
    {"name": "public_data.get_resident_population", "description": "주민등록인구 조회 (KOSIS)"},
    {"name": "public_data.get_worker_population", "description": "직장인구 조회 (KOSIS)"},
    {"name": "public_data.get_seoul_living_population", "description": "서울 생활인구 조회 (서울열린데이터)"},
    {"name": "public_data.get_card_sales", "description": "카드매출 조회 (서울열린데이터)"},
]

RESOURCE_LIST = [
    {"uri": "public-data://industry-codes", "description": "업종코드 목록"},
    {"uri": "public-data://district-codes", "description": "상권코드 목록"},
    {"uri": "public-data://dong-codes", "description": "행정동코드 목록"},
]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    clients = get_api_clients()
    return {
        "status": "ok",
        "server": "public_data",
        "api_keys": {
            "seoul": bool(clients.get("seoul_key")),
            "kosis": bool(clients.get("kosis_key")),
            "semas": bool(clients.get("semas_key")),
        },
    }


@app.get("/tools/list")
async def list_tools():
    return TOOL_LIST


@app.get("/resources/list")
async def list_resources():
    return RESOURCE_LIST


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
        clients = get_api_clients()
        result = await tool_fn(request.arguments, clients)
        return result
    except Exception as e:
        logger.exception("도구 실행 중 오류: %s", request.name)
        return {"error": f"도구 실행 실패: {e}"}


class ResourceReadRequest(BaseModel):
    uri: str


@app.post("/resources/read")
async def read_resource(request: ResourceReadRequest):
    handler = RESOURCE_REGISTRY.get(request.uri)
    if handler is None:
        return {
            "error": f"알 수 없는 리소스입니다: {request.uri}",
            "available_resources": [r["uri"] for r in RESOURCE_LIST],
        }
    return await handler()


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5100)
