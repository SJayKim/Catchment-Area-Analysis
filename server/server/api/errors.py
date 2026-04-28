"""Standardized error response format."""

from __future__ import annotations

from typing import NoReturn

from fastapi import HTTPException

# Error codes
RATE_LIMITED = "RATE_LIMITED"
VALIDATION_ERROR = "VALIDATION_ERROR"
NOT_FOUND = "NOT_FOUND"
INTERNAL_ERROR = "INTERNAL_ERROR"
SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


def make_error_response(code: str, message: str, request_id: str | None = None) -> dict:
    """Create a standardized error response dict."""
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
        }
    }


def raise_db_unavailable() -> NoReturn:
    """Raise the canonical 503 for database OperationalError surfaces.

    Routes use this in ``except OperationalError`` blocks to keep the message
    consistent across endpoints (originally duplicated in districts.py and
    map_data.py — 6 sites pre-2026-04-27 refactor).
    """
    raise HTTPException(
        status_code=503,
        detail="Database temporarily unavailable",
    ) from None


def raise_not_found(entity: str, key: str) -> NoReturn:
    """Raise a 404 with a uniform ``"<entity> '<key>' not found"`` message."""
    raise HTTPException(
        status_code=404,
        detail=f"{entity} '{key}' not found",
    )
