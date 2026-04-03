"""Mock population repository."""

from __future__ import annotations

from server.agent.tools.mock_data import POPULATION_INFO


class MockPopulationRepository:
    async def get_population_info(self, district_code: str) -> dict:
        result = POPULATION_INFO.get(district_code)
        if result is None:
            return {"error": "해당 상권의 인구 데이터가 없습니다.", "district_code": district_code}
        return result
