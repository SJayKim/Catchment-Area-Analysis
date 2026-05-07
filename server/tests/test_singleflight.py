"""Singleflight regression — Plan: docs/plan/infra/heatmap-singleflight-reintroduce.md."""

from __future__ import annotations

import asyncio

import pytest

from server.services.singleflight import Singleflight


@pytest.mark.asyncio
async def test_basic_single_caller_executes_fn_once() -> None:
    sf = Singleflight()
    calls = 0

    async def fn() -> int:
        nonlocal calls
        calls += 1
        return 42

    assert await sf.do("k", fn) == 42
    assert calls == 1
    assert sf.coalesced_count == 0


@pytest.mark.asyncio
async def test_concurrent_callers_share_single_execution() -> None:
    sf = Singleflight()
    calls = 0
    gate = asyncio.Event()

    async def fn() -> str:
        nonlocal calls
        calls += 1
        await gate.wait()
        return "shared"

    async def waiter() -> str:
        return await sf.do("k", fn)

    tasks = [asyncio.create_task(waiter()) for _ in range(50)]
    await asyncio.sleep(0.05)
    gate.set()
    results = await asyncio.gather(*tasks)

    assert calls == 1
    assert results == ["shared"] * 50
    assert sf.coalesced_count == 49


@pytest.mark.asyncio
async def test_different_keys_run_in_parallel() -> None:
    sf = Singleflight()
    calls: dict[str, int] = {"a": 0, "b": 0}

    async def make_fn(key: str):
        async def fn() -> str:
            calls[key] += 1
            await asyncio.sleep(0.01)
            return key

        return fn

    fa, fb = await make_fn("a"), await make_fn("b")
    a_res, b_res = await asyncio.gather(sf.do("a", fa), sf.do("b", fb))

    assert (a_res, b_res) == ("a", "b")
    assert calls == {"a": 1, "b": 1}
    assert sf.coalesced_count == 0


@pytest.mark.asyncio
async def test_exception_propagates_to_all_awaiters() -> None:
    sf = Singleflight()
    calls = 0
    gate = asyncio.Event()

    async def fn() -> None:
        nonlocal calls
        calls += 1
        await gate.wait()
        raise RuntimeError("boom")

    async def waiter() -> None:
        await sf.do("k", fn)

    tasks = [asyncio.create_task(waiter()) for _ in range(10)]
    await asyncio.sleep(0.05)
    gate.set()
    results = await asyncio.gather(*tasks, return_exceptions=True)

    assert calls == 1
    assert all(isinstance(r, RuntimeError) and str(r) == "boom" for r in results)


@pytest.mark.asyncio
async def test_inflight_dict_cleared_after_completion() -> None:
    sf = Singleflight()

    async def fn() -> int:
        return 1

    await sf.do("k", fn)
    assert "k" not in sf._inflight  # noqa: SLF001 (private attr used for invariant check)


@pytest.mark.asyncio
async def test_inflight_dict_cleared_after_exception() -> None:
    sf = Singleflight()

    async def fn() -> None:
        raise ValueError("x")

    with pytest.raises(ValueError):
        await sf.do("k", fn)

    assert "k" not in sf._inflight  # noqa: SLF001


@pytest.mark.asyncio
async def test_awaiter_cancellation_does_not_affect_leader() -> None:
    """Cancelling a follower should NOT cancel the leader's fn() execution."""
    sf = Singleflight()
    calls = 0
    gate = asyncio.Event()

    async def fn() -> str:
        nonlocal calls
        calls += 1
        await gate.wait()
        return "ok"

    leader = asyncio.create_task(sf.do("k", fn))
    await asyncio.sleep(0.01)
    follower = asyncio.create_task(sf.do("k", fn))
    await asyncio.sleep(0.01)

    follower.cancel()
    with pytest.raises(asyncio.CancelledError):
        await follower

    gate.set()
    result = await leader
    assert result == "ok"
    assert calls == 1


@pytest.mark.asyncio
async def test_sequential_keys_reuse_same_singleflight() -> None:
    sf = Singleflight()
    calls = 0

    async def fn() -> int:
        nonlocal calls
        calls += 1
        return calls

    r1 = await sf.do("k", fn)
    r2 = await sf.do("k", fn)
    assert r1 == 1 and r2 == 2
    assert sf.coalesced_count == 0


@pytest.mark.asyncio
async def test_module_singleton_returns_same_instance() -> None:
    from server.services.singleflight import get_singleflight

    a = get_singleflight()
    b = get_singleflight()
    assert a is b
