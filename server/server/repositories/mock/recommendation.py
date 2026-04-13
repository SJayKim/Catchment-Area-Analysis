"""Mock recommendation repository."""

from __future__ import annotations

from server.agent.tools.mock_data import get_recommendations


class MockRecommendationRepository:
    async def recommend_business(
        self, district_code: str, budget: int | None = None, preference: str | None = None
    ) -> dict:
        return get_recommendations(district_code, budget)
