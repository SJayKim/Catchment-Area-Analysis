"""Repository layer — abstracts Mock/Real data access behind a unified interface."""

from __future__ import annotations

from server.repositories.data_access import DataAccess

_data_access: DataAccess | None = None


def get_data_access() -> DataAccess:
    """Return the global DataAccess instance. Raises if not initialized."""
    if _data_access is None:
        raise RuntimeError("DataAccess not initialized. Call set_data_access() first.")
    return _data_access


def set_data_access(da: DataAccess) -> None:
    """Set the global DataAccess instance (called once at startup)."""
    global _data_access
    _data_access = da
