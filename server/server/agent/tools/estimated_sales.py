from server.agent.tools.registry import register_tool
from server.repositories import get_data_access
from server.services.cache import get_cache_service


@register_tool(
    "get_estimated_sales",
    emoji="🔍",
    progress_label="매출 데이터 조회 중...",
    done_label="매출 조회 완료",
)
async def get_estimated_sales(
    district_code: str, category_code: str | None = None
) -> dict:
    """Query estimated sales for a district."""
    cache = get_cache_service()
    cache_key = f"sales:{district_code}:{category_code or 'all'}"
    cached = await cache.get(cache_key)
    if cached is not None:
        return cached

    da = get_data_access()
    result = await da.sales.get_estimated_sales(district_code, category_code)

    if "error" not in result:
        await cache.set(cache_key, result, ttl=86400)
    return result
