from server.agent.tools.registry import register_tool
from server.repositories import get_data_access
from server.services.cache import get_cache_service


@register_tool(
    "get_population_info",
    progress_label="인구 데이터 조회 중...",
    done_label="인구 조회 완료",
)
async def get_population_info(district_code: str) -> dict:
    """Query resident and worker population for a district."""
    cache = get_cache_service()
    cache_key = f"pop:{district_code}"
    cached = await cache.get(cache_key)
    if cached is not None:
        return cached

    da = get_data_access()
    result = await da.population.get_population_info(district_code)

    if "error" not in result:
        await cache.set(cache_key, result, ttl=86400)
    return result
