from server.repositories import get_data_access
from server.services.cache import get_cache_service


async def recommend_business(
    district_code: str,
    budget: int | None = None,
    preference: str | None = None,
) -> dict:
    """Recommend top 5 business categories for a district."""
    cache = get_cache_service()
    cache_key = f"recommend:{district_code}:{budget or 'all'}:{preference or 'all'}"
    cached = await cache.get(cache_key)
    if cached is not None:
        return cached

    da = get_data_access()
    result = await da.recommendation.recommend_business(district_code, budget, preference)

    if "error" not in result:
        await cache.set(cache_key, result, ttl=86400)
    return result
