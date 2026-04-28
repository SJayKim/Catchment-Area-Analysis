"""Per-session in-flight task pre-emption tests.

When the user clicks district A and then quickly clicks district B (sending
a second /api/chat request from the *same* session_id while the first is
still streaming), the backend must cancel the in-flight task before the
new one starts. Otherwise both tasks race on the shared
ConversationHistory and the front-end receives interleaved SSE events.

Plan: docs/plan/fix/district-click-race-2026-04-28.md §3.4.
"""

from __future__ import annotations

import asyncio

import pytest


@pytest.mark.asyncio
async def test_claim_session_slot_cancels_previous_task() -> None:
    """A second claim_session_slot call cancels the previously registered task."""
    from server.api.routes import chat as chat_route

    session_id = "test-session-rapid-switch-1"

    # Reset the registry to ensure a clean slot.
    async with chat_route._session_inflight_lock:
        chat_route._session_inflight.pop(session_id, None)

    cancelled = asyncio.Event()
    started = asyncio.Event()

    async def long_running() -> None:
        started.set()
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    task = asyncio.create_task(long_running())
    # Yield once so the task actually enters the sleep before we cancel,
    # otherwise CancelledError fires at coroutine entry and the except
    # block never runs.
    await started.wait()
    await chat_route._register_session_task(session_id, task)

    # Now a "new request" claims the slot — the previous task should be
    # cancelled and awaited within the timeout.
    await chat_route._claim_session_slot(session_id)

    assert task.cancelled() or task.done()
    assert cancelled.is_set()

    # Slot is released — registry no longer holds the previous task.
    async with chat_route._session_inflight_lock:
        assert session_id not in chat_route._session_inflight


@pytest.mark.asyncio
async def test_claim_session_slot_no_op_for_unknown_session() -> None:
    """Claiming a slot for an unseen session_id is a fast no-op."""
    from server.api.routes import chat as chat_route

    # Should complete immediately without raising.
    await asyncio.wait_for(
        chat_route._claim_session_slot("never-registered-session-xyz"),
        timeout=1.0,
    )


@pytest.mark.asyncio
async def test_register_release_lifecycle() -> None:
    """register → release removes the task from the registry."""
    from server.api.routes import chat as chat_route

    session_id = "test-session-lifecycle"

    async def trivial() -> None:
        return None

    task = asyncio.create_task(trivial())
    await chat_route._register_session_task(session_id, task)

    async with chat_route._session_inflight_lock:
        assert chat_route._session_inflight.get(session_id) is task

    await task
    await chat_route._release_session_task(session_id, task)

    async with chat_route._session_inflight_lock:
        assert session_id not in chat_route._session_inflight


@pytest.mark.asyncio
async def test_release_does_not_remove_newer_task() -> None:
    """If a newer task replaces the previous one, the older release is a no-op."""
    from server.api.routes import chat as chat_route

    session_id = "test-session-race"

    async def trivial() -> None:
        return None

    old_task = asyncio.create_task(trivial())
    new_task = asyncio.create_task(trivial())

    await chat_route._register_session_task(session_id, old_task)
    # Simulate a new request claiming the slot — registry now points at new_task.
    await chat_route._register_session_task(session_id, new_task)

    # Old task's release should not evict the newer registration.
    await chat_route._release_session_task(session_id, old_task)

    async with chat_route._session_inflight_lock:
        assert chat_route._session_inflight.get(session_id) is new_task

    # Cleanup
    await old_task
    await new_task
    await chat_route._release_session_task(session_id, new_task)
