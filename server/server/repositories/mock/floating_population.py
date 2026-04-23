"""Mock floating population repository."""

from __future__ import annotations

from server.agent.tools.mock_data import FLOATING_POPULATION


class MockFloatingPopulationRepository:
    async def get_floating_population(self, district_code: str, quarter: str | None = None) -> dict:
        result = FLOATING_POPULATION.get(district_code)
        if result is None:
            return {"error": "해당 상권의 유동인구 데이터가 없습니다.", "district_code": district_code}
        return result
