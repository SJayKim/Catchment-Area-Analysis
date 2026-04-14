"""Standardized error response format."""

from __future__ import annotations

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
