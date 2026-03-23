"""부동산 MCP 도구 구현."""

from __future__ import annotations

import logging
from typing import Any, Callable, Coroutine

import httpx

logger = logging.getLogger("mcp.real_estate.tools")


async def get_rent_info(args: dict[str, Any], client: httpx.AsyncClient) -> dict[str, Any]:
    """상가 임대료 정보 조회.

    국토교통부 실거래가 API 또는 한국부동산원 데이터를 활용하여
    해당 지역의 상가 임대료 시세를 조회한다.
    """
    location = args.get("location", "")
    radius = args.get("radius", 500)

    try:
        api_key = client._api_key  # noqa: SLF001
        response = await client.get(
            "http://apis.data.go.kr/1613000/RTMSDataSvcSHRent/getRTMSDataSvcSHRent",
            params={"serviceKey": api_key, "LAWD_CD": location[:5], "DEAL_YMD": "202601", "numOfRows": 20},
        )
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.warning("실거래가 API 호출 실패: %s", e)

    # 폴백: 일반적인 시세 추정치 반환
    return {
        "status": "estimated",
        "location": location,
        "avg_rent_per_pyeong": 0,
        "rent_range": {"min": 0, "max": 0},
        "message": "실거래가 데이터를 가져올 수 없습니다. LLM이 지역 특성을 기반으로 추정합니다.",
    }


async def get_transaction_price(args: dict[str, Any], client: httpx.AsyncClient) -> dict[str, Any]:
    """상가 실거래가 조회."""
    location = args.get("location", "")

    try:
        api_key = client._api_key  # noqa: SLF001
        response = await client.get(
            "http://apis.data.go.kr/1613000/RTMSDataSvcNrgTrade/getRTMSDataSvcNrgTrade",
            params={"serviceKey": api_key, "LAWD_CD": location[:5], "DEAL_YMD": "202601", "numOfRows": 20},
        )
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.warning("실거래가 API 호출 실패: %s", e)

    return {
        "status": "estimated",
        "location": location,
        "message": "실거래가 데이터를 가져올 수 없습니다.",
    }


async def get_vacancy_rate(args: dict[str, Any], client: httpx.AsyncClient) -> dict[str, Any]:
    """상가 공실률 조회."""
    location = args.get("location", "")

    # 한국부동산원 상업용 부동산 공실률 데이터
    return {
        "status": "estimated",
        "location": location,
        "vacancy_rate": 0.0,
        "message": "공실률 데이터를 가져올 수 없습니다. LLM이 지역 특성을 기반으로 추정합니다.",
    }


async def get_premium_estimate(args: dict[str, Any], client: httpx.AsyncClient) -> dict[str, Any]:
    """권리금 추정."""
    location = args.get("location", "")
    industry = args.get("industry", "")

    return {
        "status": "estimated",
        "location": location,
        "industry": industry,
        "premium_estimate": 0,
        "message": "권리금 데이터를 가져올 수 없습니다. LLM이 지역/업종 특성을 기반으로 추정합니다.",
    }


TOOL_REGISTRY: dict[str, Callable[..., Coroutine[Any, Any, dict[str, Any]]]] = {
    "get_rent_info": get_rent_info,
    "get_transaction_price": get_transaction_price,
    "get_vacancy_rate": get_vacancy_rate,
    "get_premium_estimate": get_premium_estimate,
}
