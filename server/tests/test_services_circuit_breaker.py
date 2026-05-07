"""CircuitBreaker — 3-state transition regression."""

from __future__ import annotations

import asyncio

import pytest

from server.services.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
)


def test_starts_closed_and_check_passes() -> None:
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.1, name="t")
    assert cb.state == CircuitState.CLOSED
    cb.check()  # no exception


@pytest.mark.asyncio
async def test_opens_after_threshold_failures() -> None:
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.1, name="t")
    for _ in range(3):
        await cb.record_failure()
    assert cb.state == CircuitState.OPEN
    with pytest.raises(CircuitOpenError):
        cb.check()


@pytest.mark.asyncio
async def test_open_transitions_to_half_open_after_timeout() -> None:
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.05, name="t")
    await cb.record_failure()
    await cb.record_failure()
    assert cb.state == CircuitState.OPEN

    await asyncio.sleep(0.06)
    cb.check()  # should transition to HALF_OPEN
    assert cb.state == CircuitState.HALF_OPEN


@pytest.mark.asyncio
async def test_half_open_success_closes_circuit() -> None:
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.01, name="t")
    await cb.record_failure()
    await cb.record_failure()
    await asyncio.sleep(0.02)
    cb.check()
    assert cb.state == CircuitState.HALF_OPEN

    await cb.record_success()
    assert cb.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_half_open_failure_reopens() -> None:
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.01, name="t")
    await cb.record_failure()
    await cb.record_failure()
    await asyncio.sleep(0.02)
    cb.check()
    assert cb.state == CircuitState.HALF_OPEN

    await cb.record_failure()
    assert cb.state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_circuit_open_error_carries_recovery_remaining() -> None:
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=10.0, name="t")
    await cb.record_failure()
    with pytest.raises(CircuitOpenError) as exc:
        cb.check()
    assert exc.value.recovery_remaining > 0
    assert exc.value.recovery_remaining <= 10.0


@pytest.mark.asyncio
async def test_success_resets_failure_count() -> None:
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.1, name="t")
    await cb.record_failure()
    await cb.record_failure()
    assert cb.state == CircuitState.CLOSED  # not yet open
    await cb.record_success()
    # next two failures should NOT open (counter reset)
    await cb.record_failure()
    await cb.record_failure()
    assert cb.state == CircuitState.CLOSED
