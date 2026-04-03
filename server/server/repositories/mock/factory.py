"""Factory for building a Mock DataAccess instance."""

from __future__ import annotations

from server.repositories.data_access import DataAccess
from server.repositories.mock.comparison import MockComparisonRepository
from server.repositories.mock.districts import MockDistrictRepository
from server.repositories.mock.estimated_sales import MockEstimatedSalesRepository
from server.repositories.mock.floating_population import MockFloatingPopulationRepository
from server.repositories.mock.population import MockPopulationRepository
from server.repositories.mock.recommendation import MockRecommendationRepository
from server.repositories.mock.stores import MockStoreRepository


def build_mock_data_access() -> DataAccess:
    """Build DataAccess with all Mock repository implementations."""
    return DataAccess(
        districts=MockDistrictRepository(),
        floating_pop=MockFloatingPopulationRepository(),
        sales=MockEstimatedSalesRepository(),
        stores=MockStoreRepository(),
        population=MockPopulationRepository(),
        comparison=MockComparisonRepository(),
        recommendation=MockRecommendationRepository(),
    )
