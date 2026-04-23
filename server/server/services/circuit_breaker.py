"""Async circuit breaker for LLM/external service calls.

3-state model: CLOSED -> OPEN -> HALF_OPEN -> CLOSED
Pure asyncio, no external dependencies.
"""

from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """Raised when the circuit is open and calls are rejected."""

    def __init__(self, recovery_remaining: float):
        self.recovery_remaining = recovery_remaining
        super().__init__(f"Circuit breaker is OPEN. Retry after {recovery_remaining:.1f}s")


class CircuitBreaker:
    """Async circuit breaker with configurable failure threshold and recovery.

    Usage::

        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)

        async def call_llm():
            cb.check()          # raises CircuitOpenError if OPEN
            try:
                result = await llm.ainvoke(...)
                cb.record_success()
                return result
            except Exception:
                cb.record_failure()
                raise
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        name: str = "default",
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    def check(self) -> None:
        """Check if calls are allowed. Raises CircuitOpenError if OPEN."""
        if self._state == CircuitState.CLOSED:
            return

        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker [%s] transitioned to HALF_OPEN", self.name)
                return
            raise CircuitOpenError(self.recovery_timeout - elapsed)

        # HALF_OPEN: allow one probe request
        return

    async def record_success(self) -> None:
        """Record a successful call. Resets failure count, closes circuit."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                logger.info("Circuit breaker [%s] recovered -> CLOSED", self.name)
            self._failure_count = 0
            self._state = CircuitState.CLOSED

    async def record_failure(self) -> None:
        """Record a failed call. Opens circuit if threshold is reached."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning("Circuit breaker [%s] HALF_OPEN probe failed -> OPEN", self.name)
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit breaker [%s] threshold reached (%d/%d) -> OPEN",
                    self.name,
                    self._failure_count,
                    self.failure_threshold,
                )
