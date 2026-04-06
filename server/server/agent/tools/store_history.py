import logging

from server.agent.tools.registry import register_tool
from server.repositories import get_data_access
from server.services.cache import get_cache_service

logger = logging.getLogger(__name__)


@register_tool(
    "get_store_history",
    emoji="📋",
    card_type="risk",
    progress_label="리스크 분석 중...",
    done_label="리스크 분석 완료",
)
async def get_store_history(district_code: str) -> dict:
    """Analyze store history and risk indicators for a district."""
    try:
        cache = get_cache_service()
        cache_key = f"history:{district_code}"
        cached = await cache.get(cache_key)
        if cached is not None:
            return cached

        da = get_data_access()
        result = await da.stores.get_store_history(district_code)

        if "error" not in result:
            await cache.set(cache_key, result, ttl=86400)
        return result
    except Exception as exc:
        logger.exception("get_store_history tool failed")
        return {"error": f"리스크 분석 도구 오류: {type(exc).__name__}"}
