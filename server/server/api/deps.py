"""Dependency injection for FastAPI routes."""

from server.repositories import get_data_access
from server.repositories.data_access import DataAccess


def get_da() -> DataAccess:
    """Provide the global DataAccess instance."""
    return get_data_access()
