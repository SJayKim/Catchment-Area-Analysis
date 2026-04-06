import logging

from server.agent.tools.registry import register_tool
from server.repositories import get_data_access
from server.services.cache import get_cache_service

logger = logging.getLogger(__name__)


@register_tool(
    "recommend_business",
    emoji="💡",
    card_type="recommend",
    progress_label="업종 추천 분석 중...",
    done_label="업종 추천 완료",
)
async def recommend_business(
    district_code: str,
    budget: int | None = None,
    preference: str | None = None,
) -> dict:
    """Recommend top 5 business categories for a district."""
    try:
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
    except Exception as exc:
        logger.exception("recommend_business tool failed")
        return {"error": f"업종 추천 도구 오류: {type(exc).__name__}"}
