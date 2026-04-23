from server.agent.tools.registry import register_tool
from server.repositories import get_data_access
from server.services.cache import get_cache_service


@register_tool(
    "get_floating_population",
    progress_label="유동인구 데이터 조회 중...",
    done_label="유동인구 조회 완료",
)
async def get_floating_population(district_code: str, quarter: str | None = None) -> dict:
    """Query floating population data for a district."""
    cache = get_cache_service()
    cache_key = f"fp:{district_code}:{quarter or 'latest'}"
    cached = await cache.get(cache_key)
    if cached is not None:
        return cached

    da = get_data_access()
    result = await da.floating_pop.get_floating_population(district_code, quarter)

    if "error" not in result:
        await cache.set(cache_key, result, ttl=86400)
    return result
