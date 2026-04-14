"""Rate limiting configuration using slowapi."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from server.api.errors import RATE_LIMITED, make_error_response
from server.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.rate_limit_global],
)


def register_rate_limiter(app: FastAPI) -> None:
    """Attach the rate limiter to the FastAPI app."""
    app.state.limiter = limiter

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        retry_after = exc.detail.split("per")[-1].strip() if exc.detail else "60"
        return JSONResponse(
            status_code=429,
            content=make_error_response(
                RATE_LIMITED,
                f"Rate limit exceeded. {exc.detail}",
                request_id,
            ),
            headers={"Retry-After": retry_after},
        )
