"""Singleflight — coalesce concurrent calls for the same key into one."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)


class Singleflight:
    """Prevent thundering herd on cache miss.

    When multiple concurrent requests miss the same cache key, only the first
    one actually executes the DB query. The rest await the same result.

    Usage::

        sf = Singleflight()
        result = await sf.do("cache_key", lambda: db_query())
    """

    def __init__(self) -> None:
        self._inflight: dict[str, asyncio.Future[Any]] = {}

    async def do(self, key: str, coro_fn: Callable[[], Awaitable[Any]]) -> Any:
        """Execute *coro_fn* once per key, sharing the result with waiters."""
        if key in self._inflight:
            logger.debug("Singleflight join: %s", key)
            return await self._inflight[key]

        loop = asyncio.get_running_loop()
        future: asyncio.Future[Any] = loop.create_future()
        self._inflight[key] = future

        try:
            result = await coro_fn()
            future.set_result(result)
            return result
        except Exception as exc:
            future.set_exception(exc)
            raise
        finally:
            self._inflight.pop(key, None)


# Module-level singleton
_singleflight = Singleflight()


def get_singleflight() -> Singleflight:
    return _singleflight
