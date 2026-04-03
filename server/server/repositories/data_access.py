"""DataAccess facade — unified entry point for all repositories."""

from __future__ import annotations

from server.repositories.protocols import (
    ComparisonRepository,
    DistrictRepository,
    EstimatedSalesRepository,
    FloatingPopulationRepository,
    PopulationRepository,
    RecommendationRepository,
    StoreRepository,
)


class DataAccess:
    """Facade aggregating all repository implementations."""

    def __init__(
        self,
        *,
        districts: DistrictRepository,
        floating_pop: FloatingPopulationRepository,
        sales: EstimatedSalesRepository,
        stores: StoreRepository,
        population: PopulationRepository,
        comparison: ComparisonRepository,
        recommendation: RecommendationRepository,
    ) -> None:
        self.districts = districts
        self.floating_pop = floating_pop
        self.sales = sales
        self.stores = stores
        self.population = population
        self.comparison = comparison
        self.recommendation = recommendation
