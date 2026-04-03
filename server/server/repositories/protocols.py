"""Repository protocols — define the contract for data access."""

from __future__ import annotations

from typing import Protocol


class DistrictRepository(Protocol):
    async def get_district_meta(self, district_code: str) -> dict | None: ...
    async def resolve_district(self, district_code: str) -> dict | None: ...
    async def detect_district_by_name(self, message: str) -> dict | None: ...
    async def list_districts(
        self, search: str | None, district_type: str | None, limit: int, offset: int
    ) -> tuple[int, list[dict]]: ...
    async def get_district_detail(self, code: str) -> dict | None: ...
    async def get_polygons_geojson(self, bounds: str | None) -> dict: ...


class FloatingPopulationRepository(Protocol):
    async def get_floating_population(
        self, district_code: str, quarter: str | None = None
    ) -> dict: ...


class EstimatedSalesRepository(Protocol):
    async def get_estimated_sales(
        self, district_code: str, category_code: str | None = None
    ) -> dict: ...


class StoreRepository(Protocol):
    async def get_store_info(
        self, district_code: str, category_code: str | None = None
    ) -> dict: ...
    async def get_store_history(self, district_code: str) -> dict: ...


class PopulationRepository(Protocol):
    async def get_population_info(self, district_code: str) -> dict: ...


class ComparisonRepository(Protocol):
    async def compare_districts(self, district_codes: list[str]) -> dict: ...


class RecommendationRepository(Protocol):
    async def recommend_business(
        self, district_code: str, budget: int | None = None, preference: str | None = None
    ) -> dict: ...
