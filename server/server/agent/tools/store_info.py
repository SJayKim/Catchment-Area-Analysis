from server.agent.tools.registry import register_tool
from server.repositories import get_data_access
from server.services.cache import get_cache_service


@register_tool(
    "get_store_info",
    emoji="🔍",
    progress_label="점포 현황 조회 중...",
    done_label="점포 현황 조회 완료",
)
async def get_store_info(
    district_code: str, category_code: str | None = None
) -> dict:
    """Query store information for a district."""
    cache = get_cache_service()
    cache_key = f"store:{district_code}:{category_code or 'all'}"
    cached = await cache.get(cache_key)
    if cached is not None:
        return cached

    da = get_data_access()
    result = await da.stores.get_store_info(district_code, category_code)

    if "error" not in result:
        await cache.set(cache_key, result, ttl=86400)
    return result
