"""Finance MCP Server — 금융/대출 도구 서버."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from app.mcp_servers.finance.api_client import FinanceAPIClient
from app.mcp_servers.finance.tools import TOOL_REGISTRY

logger = logging.getLogger("mcp.finance.server")

_finance_client: FinanceAPIClient | None = None


def _get_finance_client() -> FinanceAPIClient:
    if _finance_client is None:
        raise RuntimeError("FinanceAPIClient가 초기화되지 않았습니다.")
    return _finance_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _finance_client
    api_key = os.environ.get("DATA_API_PUBLIC_DATA_KEY", "")
    _finance_client = FinanceAPIClient(api_key)
    logger.info("Finance MCP Server 시작")
    yield
    await _finance_client.close()
    _finance_client = None
    logger.info("Finance MCP Server 종료")


app = FastAPI(title="MarketScope Finance MCP Server", lifespan=lifespan)


class ToolCallRequest(BaseModel):
    name: str
    arguments: dict[str, Any] = {}


TOOL_LIST = [
    {"name": "finance.search_startup_loans", "description": "소상공인/창업자 대출 상품 검색"},
    {"name": "finance.search_government_subsidies", "description": "정부/지자체 지원사업 검색"},
    {"name": "finance.calculate_loan_repayment", "description": "대출 상환 스케줄 계산"},
    {"name": "finance.get_franchise_disclosure", "description": "프랜차이즈 정보공개서 조회"},
    {"name": "finance.get_minimum_wage", "description": "최저임금 정보 조회"},
    {"name": "finance.get_insurance_rates", "description": "4대보험 요율 조회"},
]


@app.get("/health")
async def health():
    return {"status": "ok", "server": "finance"}


@app.get("/tools/list")
async def list_tools():
    return TOOL_LIST


@app.post("/tools/call")
async def call_tool(request: ToolCallRequest):
    logger.info("도구 호출: %s | arguments=%s", request.name, request.arguments)
    tool_fn = TOOL_REGISTRY.get(request.name)
    if tool_fn is None:
        return {"error": f"알 수 없는 도구입니다: {request.name}", "available_tools": [t["name"] for t in TOOL_LIST]}
    try:
        client = _get_finance_client()
        return await tool_fn(request.arguments, client)
    except Exception as e:
        logger.exception("도구 실행 중 오류: %s", request.name)
        return {"error": f"도구 실행 실패: {e}"}


if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
    uvicorn.run(app, host="0.0.0.0", port=5105)
