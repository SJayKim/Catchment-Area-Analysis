"""Lightweight application metrics -- no external dependency required.

Tracks request counts (by endpoint + status code) and active SSE connections
using plain Python data structures. Exposes a ``GET /metrics`` JSON endpoint
for quick observability without Prometheus or StatsD.

Usage in ``main.py``::

    from server.middleware.metrics import MetricsMiddleware, metrics_router

    app.add_middleware(MetricsMiddleware)
    app.include_router(metrics_router)
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared metrics state (thread-safe via lock)
# ---------------------------------------------------------------------------

_lock = threading.Lock()

# {(method, path, status_code): count}
_request_counts: dict[tuple[str, str, int], int] = defaultdict(int)

# {(method, path): list[float]}  -- last N response times in seconds
_response_times: dict[tuple[str, str], list[float]] = defaultdict(list)
_MAX_RESPONSE_TIME_SAMPLES = 500

# Active SSE connections gauge
_sse_active_connections: int = 0

# ---------------------------------------------------------------------------
# Public helpers for SSE connection tracking
# ---------------------------------------------------------------------------


def sse_connection_opened() -> None:
    """Increment the active SSE connections gauge."""
    global _sse_active_connections
    with _lock:
        _sse_active_connections += 1


def sse_connection_closed() -> None:
    """Decrement the active SSE connections gauge."""
    global _sse_active_connections
    with _lock:
        _sse_active_connections = max(0, _sse_active_connections - 1)


def get_sse_active_connections() -> int:
    """Return the current number of active SSE connections."""
    with _lock:
        return _sse_active_connections


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


def _normalize_path(path: str) -> str:
    """Collapse path parameters into placeholders to avoid cardinality explosion.

    Examples:
        /api/districts/D3001       -> /api/districts/{code}
        /api/map-data/heatmap/all  -> /api/map-data/heatmap/all  (no change)
    """
    parts = path.rstrip("/").split("/")
    normalised: list[str] = []
    for part in parts:
        # Heuristic: if a path segment looks like a district code (D + digits),
        # a UUID, or a purely numeric value, replace it.
        if part and (
            part.isdigit()
            or (len(part) > 4 and part[0] in ("D", "d") and part[1:].isdigit())
            or (len(part) == 36 and part.count("-") == 4)
        ):
            normalised.append("{id}")
        else:
            normalised.append(part)
    return "/".join(normalised) or "/"


class MetricsMiddleware(BaseHTTPMiddleware):
    """Record per-request metrics (count + latency)."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.monotonic()
        response = await call_next(request)
        elapsed = time.monotonic() - start

        method = request.method
        path = _normalize_path(request.url.path)
        status = response.status_code

        with _lock:
            _request_counts[(method, path, status)] += 1
            bucket = _response_times[(method, path)]
            bucket.append(elapsed)
            # Keep only the latest samples to bound memory
            if len(bucket) > _MAX_RESPONSE_TIME_SAMPLES:
                _response_times[(method, path)] = bucket[-_MAX_RESPONSE_TIME_SAMPLES:]

        return response


# ---------------------------------------------------------------------------
# /metrics endpoint
# ---------------------------------------------------------------------------

metrics_router = APIRouter(tags=["ops"])


def _percentile(values: list[float], p: float) -> float:
    """Return the *p*-th percentile (0-100) from a sorted list."""
    if not values:
        return 0.0
    sorted_v = sorted(values)
    k = (len(sorted_v) - 1) * (p / 100.0)
    f = int(k)
    c = f + 1
    if c >= len(sorted_v):
        return sorted_v[f]
    return sorted_v[f] + (k - f) * (sorted_v[c] - sorted_v[f])


@metrics_router.get("/metrics")
async def get_metrics() -> JSONResponse:
    """Return a JSON summary of application metrics."""
    from server.services.singleflight import get_coalesced_count

    with _lock:
        counts_snapshot = dict(_request_counts)
        times_snapshot = {k: list(v) for k, v in _response_times.items()}
        sse_conns = _sse_active_connections
    coalesced_total = get_coalesced_count()

    # Build request counts grouped by endpoint
    request_summary: list[dict] = []
    for (method, path, status), count in sorted(counts_snapshot.items()):
        request_summary.append(
            {
                "method": method,
                "path": path,
                "status": status,
                "count": count,
            }
        )

    # Build latency summary grouped by endpoint
    latency_summary: list[dict] = []
    for (method, path), samples in sorted(times_snapshot.items()):
        if not samples:
            continue
        latency_summary.append(
            {
                "method": method,
                "path": path,
                "samples": len(samples),
                "p50_ms": round(_percentile(samples, 50) * 1000, 2),
                "p95_ms": round(_percentile(samples, 95) * 1000, 2),
                "p99_ms": round(_percentile(samples, 99) * 1000, 2),
                "avg_ms": round(sum(samples) / len(samples) * 1000, 2),
            }
        )

    return JSONResponse(
        {
            "sse_active_connections": sse_conns,
            "singleflight_coalesced_total": coalesced_total,
            "request_counts": request_summary,
            "latency": latency_summary,
        }
    )
