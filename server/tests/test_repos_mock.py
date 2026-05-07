"""Mock repository smoke — every protocol returns a sensible shape for D3001."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_districts_resolve(mock_da, mock_district_code: str) -> None:
    meta = await mock_da.districts.resolve_district(mock_district_code)
    assert meta is not None
    assert "name" in meta and "type" in meta


@pytest.mark.asyncio
async def test_districts_detect_in_message(mock_da) -> None:
    found = await mock_da.districts.detect_districts_in_message("강남역에서 창업")
    assert found and any(d["code"] == "D3001" for d in found)


@pytest.mark.asyncio
async def test_floating_population_basic_shape(mock_da, mock_district_code) -> None:
    data = await mock_da.floating_pop.get_floating_population(mock_district_code)
    assert data is not None


@pytest.mark.asyncio
async def test_estimated_sales_returns_data(mock_da, mock_district_code) -> None:
    data = await mock_da.sales.get_estimated_sales(mock_district_code, None)
    assert data is not None


@pytest.mark.asyncio
async def test_stores_returns_data(mock_da, mock_district_code) -> None:
    data = await mock_da.stores.get_store_info(mock_district_code, None)
    assert data is not None


@pytest.mark.asyncio
async def test_population_returns_data(mock_da, mock_district_code) -> None:
    data = await mock_da.population.get_population_info(mock_district_code)
    assert data is not None


@pytest.mark.asyncio
async def test_recommendation_returns_data(mock_da, mock_district_code) -> None:
    data = await mock_da.recommendation.recommend_business(mock_district_code, None)
    assert data is not None


@pytest.mark.asyncio
async def test_simulation_returns_data(mock_da) -> None:
    data = await mock_da.simulation.get_sales_percentiles("CS100001", None)
    assert data is not None
    assert data["category_code"] == "CS100001"


@pytest.mark.asyncio
async def test_heatmap_get_data(mock_da) -> None:
    data = await mock_da.heatmap.get_heatmap_data(time_slot=12, quarter=None)
    assert "points" in data and isinstance(data["points"], list)
    assert all("lat" in p and "lng" in p and "weight" in p for p in data["points"])


@pytest.mark.asyncio
async def test_heatmap_get_all_24_slots(mock_da) -> None:
    data = await mock_da.heatmap.get_heatmap_all(quarter=None)
    assert "slots" in data
    assert len(data["slots"]) == 24
