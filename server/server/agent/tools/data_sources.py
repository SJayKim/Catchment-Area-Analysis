"""Data source registry — maps tool names to their public data sources.

Single source of truth for citation metadata displayed in Card footers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

@dataclass(frozen=True)
class DataSource:
    id: str
    name: str
    organization: str
    platform: str
    api_endpoint: str
    url: str
    license: str
    collection_method: str

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Seoul Open Data sources
# ---------------------------------------------------------------------------

SEOUL_FLOATING_POP = DataSource(
    id="seoul_floating_pop",
    name="상권-유동인구",
    organization="서울특별시",
    platform="서울 열린데이터광장",
    api_endpoint="VwsmTrdarFlpopQq",
    url="https://data.seoul.go.kr",
    license="공공누리 제1유형",
    collection_method="API",
)

SEOUL_ESTIMATED_SALES = DataSource(
    id="seoul_estimated_sales",
    name="상권-추정매출",
    organization="서울특별시",
    platform="서울 열린데이터광장",
    api_endpoint="VwsmTrdarSelngQq",
    url="https://data.seoul.go.kr",
    license="공공누리 제1유형",
    collection_method="API",
)

SEOUL_STORE_INFO = DataSource(
    id="seoul_store_info",
    name="상권-점포",
    organization="서울특별시",
    platform="서울 열린데이터광장",
    api_endpoint="VwsmTrdarStorW",
    url="https://data.seoul.go.kr",
    license="공공누리 제1유형",
    collection_method="API",
)

SEOUL_RESIDENT_POP = DataSource(
    id="seoul_resident_pop",
    name="상권-상주인구",
    organization="서울특별시",
    platform="서울 열린데이터광장",
    api_endpoint="OA-15584",
    url="https://data.seoul.go.kr",
    license="공공누리 제1유형",
    collection_method="CSV",
)

SEOUL_WORKER_POP = DataSource(
    id="seoul_worker_pop",
    name="상권-직장인구",
    organization="서울특별시",
    platform="서울 열린데이터광장",
    api_endpoint="VwsmTrdarWrcPopltnQq",
    url="https://data.seoul.go.kr",
    license="공공누리 제1유형",
    collection_method="API",
)

SEOUL_DISTRICT_POLYGON = DataSource(
    id="seoul_district_polygon",
    name="상권영역",
    organization="서울특별시",
    platform="서울 열린데이터광장",
    api_endpoint="OA-15560",
    url="https://data.seoul.go.kr",
    license="공공누리 제1유형",
    collection_method="SHP",
)

# ---------------------------------------------------------------------------
# Mock source
# ---------------------------------------------------------------------------

MOCK_SOURCE = DataSource(
    id="mock",
    name="샘플 데이터",
    organization="",
    platform="",
    api_endpoint="",
    url="",
    license="",
    collection_method="",
)

# ---------------------------------------------------------------------------
# Tool → DataSource mapping
# ---------------------------------------------------------------------------

TOOL_SOURCES: dict[str, list[DataSource]] = {
    "get_floating_population": [SEOUL_FLOATING_POP],
    "get_estimated_sales": [SEOUL_ESTIMATED_SALES],
    "get_store_info": [SEOUL_STORE_INFO],
    "get_population_info": [SEOUL_RESIDENT_POP, SEOUL_WORKER_POP],
    "get_store_history": [SEOUL_STORE_INFO],
    "get_district_summary": [SEOUL_FLOATING_POP, SEOUL_ESTIMATED_SALES, SEOUL_STORE_INFO],
    "compare_districts": [SEOUL_FLOATING_POP, SEOUL_ESTIMATED_SALES, SEOUL_STORE_INFO],
    "recommend_business": [SEOUL_ESTIMATED_SALES, SEOUL_STORE_INFO, SEOUL_FLOATING_POP],
    "simulate_revenue": [SEOUL_ESTIMATED_SALES, SEOUL_STORE_INFO],
}


def get_sources_for_tool(tool_name: str) -> list[dict]:
    """Return serializable source list for a tool.

    In mock mode, always returns [MOCK_SOURCE].
    """
    from server.config import settings

    if settings.use_mock:
        return [MOCK_SOURCE.to_dict()]
    sources = TOOL_SOURCES.get(tool_name, [])
    return [s.to_dict() for s in sources]
