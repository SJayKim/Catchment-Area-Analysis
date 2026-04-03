from server.repositories import get_data_access
from server.services.cache import get_cache_service


async def compare_districts(district_codes: list[str]) -> dict:
    """Compare key metrics across 2-3 districts."""
    if len(district_codes) < 2 or len(district_codes) > 3:
        return {"error": "비교는 2~3개 상권만 가능합니다."}

    cache = get_cache_service()
    cache_key = f"compare:{'_'.join(sorted(district_codes))}"
    cached = await cache.get(cache_key)
    if cached is not None:
        return cached

    da = get_data_access()
    result = await da.comparison.compare_districts(district_codes)

    if "error" not in result:
        await cache.set(cache_key, result, ttl=86400)
    return result
