"""뉴스/SNS MCP 도구 구현 - 네이버 검색 API 기반."""

from __future__ import annotations

import logging
from typing import Any, Callable, Coroutine

import httpx

logger = logging.getLogger("mcp.news.tools")

NAVER_API_BASE = "https://openapi.naver.com/v1/search"


async def search_blog(args: dict[str, Any], client: httpx.AsyncClient) -> dict[str, Any]:
    """네이버 블로그 검색."""
    query = args.get("query", "")
    count = args.get("count", 10)
    sort = args.get("sort", "sim")  # sim(정확도) | date(날짜)

    try:
        response = await client.get(
            f"{NAVER_API_BASE}/blog.json",
            params={"query": query, "display": min(count, 100), "sort": sort},
        )
        if response.status_code == 200:
            data = response.json()
            items = data.get("items", [])
            return {
                "total": data.get("total", 0),
                "count": len(items),
                "items": [
                    {
                        "title": item.get("title", "").replace("<b>", "").replace("</b>", ""),
                        "description": item.get("description", "").replace("<b>", "").replace("</b>", ""),
                        "link": item.get("link", ""),
                        "postdate": item.get("postdate", ""),
                        "bloggername": item.get("bloggername", ""),
                    }
                    for item in items
                ],
            }
    except Exception as e:
        logger.warning("블로그 검색 실패: %s", e)

    return {"total": 0, "count": 0, "items": [], "error": "블로그 검색 실패"}


async def search_news(args: dict[str, Any], client: httpx.AsyncClient) -> dict[str, Any]:
    """네이버 뉴스 검색."""
    query = args.get("query", "")
    count = args.get("count", 10)
    sort = args.get("sort", "date")

    try:
        response = await client.get(
            f"{NAVER_API_BASE}/news.json",
            params={"query": query, "display": min(count, 100), "sort": sort},
        )
        if response.status_code == 200:
            data = response.json()
            items = data.get("items", [])
            return {
                "total": data.get("total", 0),
                "count": len(items),
                "items": [
                    {
                        "title": item.get("title", "").replace("<b>", "").replace("</b>", ""),
                        "description": item.get("description", "").replace("<b>", "").replace("</b>", ""),
                        "link": item.get("originallink", item.get("link", "")),
                        "pubDate": item.get("pubDate", ""),
                    }
                    for item in items
                ],
            }
    except Exception as e:
        logger.warning("뉴스 검색 실패: %s", e)

    return {"total": 0, "count": 0, "items": [], "error": "뉴스 검색 실패"}


async def get_naver_datalab(args: dict[str, Any], client: httpx.AsyncClient) -> dict[str, Any]:
    """네이버 데이터랩 검색어 트렌드 조회."""
    keyword = args.get("keyword", "")
    period = args.get("period", "12m")

    # 네이버 데이터랩 API는 별도 인증 필요
    # 현재는 검색 API로 간접 추정
    try:
        response = await client.get(
            f"{NAVER_API_BASE}/blog.json",
            params={"query": keyword, "display": 1, "sort": "date"},
        )
        if response.status_code == 200:
            data = response.json()
            total = data.get("total", 0)
            return {
                "keyword": keyword,
                "period": period,
                "total_blog_posts": total,
                "estimated_interest": "높음" if total > 10000 else "보통" if total > 1000 else "낮음",
                "note": "네이버 데이터랩 API 직접 연동 시 정확한 트렌드 데이터 제공 가능",
            }
    except Exception as e:
        logger.warning("데이터랩 조회 실패: %s", e)

    return {
        "keyword": keyword,
        "period": period,
        "error": "트렌드 데이터 조회 실패",
    }


TOOL_REGISTRY: dict[str, Callable[..., Coroutine[Any, Any, dict[str, Any]]]] = {
    "search_blog": search_blog,
    "search_news": search_news,
    "get_naver_datalab": get_naver_datalab,
}
