"""Factory for building a Real (DB-backed) DataAccess instance."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from server.repositories.data_access import DataAccess
from server.repositories.real.comparison import RealComparisonRepository
from server.repositories.real.districts import RealDistrictRepository
from server.repositories.real.estimated_sales import RealEstimatedSalesRepository
from server.repositories.real.floating_population import RealFloatingPopulationRepository
from server.repositories.real.population import RealPopulationRepository
from server.repositories.real.recommendation import RealRecommendationRepository
from server.repositories.real.stores import RealStoreRepository


def build_real_data_access(session_factory: async_sessionmaker[AsyncSession]) -> DataAccess:
    """Build DataAccess with all Real (DB-backed) repository implementations."""
    return DataAccess(
        districts=RealDistrictRepository(session_factory),
        floating_pop=RealFloatingPopulationRepository(session_factory),
        sales=RealEstimatedSalesRepository(session_factory),
        stores=RealStoreRepository(session_factory),
        population=RealPopulationRepository(session_factory),
        comparison=RealComparisonRepository(session_factory),
        recommendation=RealRecommendationRepository(session_factory),
    )
