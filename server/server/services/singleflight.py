"""Singleflight — coalesce concurrent calls for the same key into one.

Re-introduced 2026-05-07 (Plan: docs/plan/infra/heatmap-singleflight-reintroduce.md).
Earlier removal in Refactor Pass 1 was premature once heatmap cold-start
load tests showed N duplicate PostGIS queries on cache miss.

Design:
- Per-key in-flight Future tracked under an ``asyncio.Lock``.
- First caller runs ``fn()``; subsequent callers ``await`` the same Future.
- Caller cancellation of an awaiter does NOT cancel the in-flight ``fn()``
  — the leader future is shielded so unrelated cancellations cannot leak.
- Exceptions propagate to every awaiter (intentional — share fate).
- In-process only; multi-instance coalescing requires Redis (out of scope).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class Singleflight:
    """Per-key request coalescing for async callables."""

    def __init__(self) -> None:
        self._inflight: dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()
        self.coalesced_count: int = 0

    async def do(self, key: str, fn: Callable[[], Awaitable[T]]) -> T:
        """Run ``fn()`` for ``key`` once; concurrent callers share the result."""
        async with self._lock:
            existing = self._inflight.get(key)
            if existing is not None:
                self.coalesced_count += 1
                future = existing
                is_leader = False
            else:
                future = asyncio.get_running_loop().create_future()
                self._inflight[key] = future
                is_leader = True

        if not is_leader:
            return await asyncio.shield(future)

        try:
            result = await fn()
        except BaseException as exc:
            if not future.done():
                future.set_exception(exc)
            raise
        else:
            if not future.done():
                future.set_result(result)
            return result
        finally:
            async with self._lock:
                if self._inflight.get(key) is future:
                    self._inflight.pop(key, None)
            # If the leader ran alone (no followers awaited), the future's
            # exception would be flagged as "never retrieved" at GC.
            # Consume it here — followers, if any, already retrieved via await.
            if future.done() and not future.cancelled():
                try:
                    future.exception()
                except asyncio.InvalidStateError:
                    pass


# ---------------------------------------------------------------------------
# Module-level singleton (per-process)
# ---------------------------------------------------------------------------

_singleflight: Singleflight | None = None


def get_singleflight() -> Singleflight:
    """Return the per-process Singleflight instance (lazy)."""
    global _singleflight
    if _singleflight is None:
        _singleflight = Singleflight()
    return _singleflight


def get_coalesced_count() -> int:
    """Return total coalesced calls since process start (0 if never used)."""
    return _singleflight.coalesced_count if _singleflight is not None else 0
