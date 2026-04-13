import logging

from server.agent.tools.registry import register_tool
from server.repositories import get_data_access
from server.services.cache import get_cache_service

logger = logging.getLogger(__name__)


def _enrich_recommendations(result: dict) -> dict:
    """Add saturation, risk_flag, cost_category to each recommendation."""
    for rec in result.get("recommendations", []):
        # Saturation based on store count
        sc = rec.get("store_count", 0)
        if sc >= 200:
            rec["saturation"] = "과포화"
        elif sc >= 100:
            rec["saturation"] = "포화"
        else:
            rec["saturation"] = "여유"

        # Risk flag based on close rate
        cr = rec.get("close_rate", 0)
        if cr > 8:
            rec["risk_flag"] = f"폐업률 {cr}% — 고위험"
        elif cr > 6:
            rec["risk_flag"] = f"폐업률 {cr}% — 주의"

        # Cost category based on startup_cost (만원)
        cost = rec.get("startup_cost", 0)
        if cost >= 10000:
            rec["cost_category"] = "대자본"
        elif cost >= 5000:
            rec["cost_category"] = "중간"
        else:
            rec["cost_category"] = "소자본"

    return result


@register_tool(
    "recommend_business",
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
            result = _enrich_recommendations(result)
            await cache.set(cache_key, result, ttl=86400)
        return result
    except Exception as exc:
        logger.exception("recommend_business tool failed")
        return {"error": f"업종 추천 도구 오류: {type(exc).__name__}"}
