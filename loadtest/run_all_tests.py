"""Run all load test scenarios and produce a summary report."""

from __future__ import annotations

import asyncio
import sys
import time

import httpx

sys.path.insert(0, str(__file__).rsplit("loadtest", 1)[0] + "loadtest")
from sse_client import send_chat_sse

BASE = "http://localhost:8003"

QUERIES = [
    ("강남역 상권 분석해줘", "D3001"),
    ("홍대입구 상권 요약해줘", "D3002"),
    ("건대입구 상권 현황 알려줘", "D3003"),
    ("명동 상권 분석해줘", "D3004"),
    ("서울역 상권 분석해줘", "D3005"),
]

DISTRICTS = [
    ("강남역 분석해줘", "D3001", "강남", ["홍대", "건대", "명동", "서울역"]),
    ("홍대입구 분석해줘", "D3002", "홍대", ["강남", "건대", "명동", "서울역"]),
    ("건대입구 분석해줘", "D3003", "건대", ["강남", "홍대", "명동", "서울역"]),
    ("명동 분석해줘", "D3004", "명동", ["강남", "홍대", "건대", "서울역"]),
    ("서울역 분석해줘", "D3005", "서울역", ["강남", "홍대", "건대", "명동"]),
]


async def run_concurrent(n: int) -> dict:
    async with httpx.AsyncClient(base_url=BASE) as c:
        tasks = [
            send_chat_sse(c, message=QUERIES[i % 5][0], session_id=f"c-{n}-{i}",
                          district_code=QUERIES[i % 5][1], timeout=90.0)
            for i in range(n)
        ]
        start = time.monotonic()
        results = await asyncio.gather(*tasks)
        wall = time.monotonic() - start

    ok = [r for r in results if r.success]
    ttfbs = sorted([r.ttfb for r in ok])
    totals = sorted([r.total_time for r in ok])
    p95i = min(int(len(ttfbs) * 0.95), len(ttfbs) - 1) if ttfbs else 0
    err_pct = (n - len(ok)) / n * 100
    return {
        "n": n, "ok": len(ok), "err_pct": err_pct, "wall": wall,
        "ttfb_p95": ttfbs[p95i] if ttfbs else 0,
        "total_p95": totals[p95i] if totals else 0,
    }


async def test_greeting(n: int = 20) -> dict:
    async with httpx.AsyncClient(base_url=BASE) as c:
        tasks = [
            send_chat_sse(c, message="안녕하세요", session_id=f"g-{i}", timeout=15.0)
            for i in range(n)
        ]
        start = time.monotonic()
        results = await asyncio.gather(*tasks)
        wall = time.monotonic() - start

    ok = [r for r in results if r.success]
    totals = sorted([r.total_time for r in ok])
    p99 = totals[min(int(len(totals) * 0.99), len(totals) - 1)] if totals else 0
    has_kw = sum(1 for r in ok if "마켓스코프" in r.collected_text)
    return {"n": n, "ok": len(ok), "wall": wall, "p99": p99, "has_kw": has_kw}


async def test_isolation() -> dict:
    async with httpx.AsyncClient(base_url=BASE) as c:
        tasks = []
        for i in range(10):
            msg, dc, own, forbidden = DISTRICTS[i % 5]
            tasks.append(
                send_chat_sse(c, message=msg, session_id=f"iso-{i}",
                              district_code=dc, timeout=60.0)
            )
        results = await asyncio.gather(*tasks)

    leaks = 0
    for i, r in enumerate(results):
        expected_dc = DISTRICTS[i % 5][1]
        for dc in r.district_codes_in_map_cmd:
            if dc != expected_dc:
                leaks += 1
    return {"leaks": leaks, "ok": sum(1 for r in results if r.success)}


async def test_disconnect() -> dict:
    async with httpx.AsyncClient(base_url=BASE) as c:
        events_read = 0
        try:
            async with c.stream("POST", "/api/chat", json={
                "message": "강남역 분석해줘", "session_id": "disc-test",
                "district_code": "D3001",
            }, timeout=httpx.Timeout(30.0)) as resp:
                async for line in resp.aiter_lines():
                    if line.strip().startswith("data:"):
                        events_read += 1
                        if events_read >= 3:
                            break
        except Exception:
            pass

        await asyncio.sleep(1)
        h = (await c.get("/api/health/detail")).json()
        r = await send_chat_sse(c, message="안녕", session_id="disc-recover", timeout=15.0)

    return {
        "events_before_dc": events_read,
        "sem_after": h["semaphore_available"],
        "sem_max": h["semaphore_max"],
        "recovery_ok": r.success,
    }


async def main():
    print("=" * 60)
    print("MarketScope AI Load Test Results")
    print("=" * 60)

    # Test 1: Concurrent ramp
    print("\n--- Test 1: Concurrent Users (ramp 1->5->10->20) ---")
    header = f"{'Users':>6} {'OK':>4} {'Err%':>6} {'TTFB p95':>10} {'Total p95':>11} {'Wall':>6} {'Pass':>6}"
    print(header)
    concurrent_pass = True
    for n in [1, 5, 10, 20]:
        r = await run_concurrent(n)
        ttfb_ok = r["ttfb_p95"] < (3 if n <= 10 else 5)
        err_ok = r["err_pct"] < (1 if n <= 10 else 5)
        passed = ttfb_ok and err_ok
        if not passed:
            concurrent_pass = False
        mark = "PASS" if passed else "FAIL"
        print(f"{r['n']:>6} {r['ok']:>4} {r['err_pct']:>5.1f}% {r['ttfb_p95']:>9.2f}s {r['total_p95']:>10.2f}s {r['wall']:>5.1f}s {mark:>6}")

    # Test 2: Greeting
    print("\n--- Test 2: Greeting Shortcut (20 users) ---")
    g = await test_greeting()
    g_pass = g["p99"] < 1.0 and g["ok"] == g["n"] and g["has_kw"] == g["ok"]
    print(f"  Success: {g['ok']}/{g['n']}, p99: {g['p99']:.3f}s, Wall: {g['wall']:.2f}s")
    print(f"  Contains 'marketscope': {g['has_kw']}/{g['ok']}")
    print(f"  Pass (p99 < 1s): {'PASS' if g_pass else 'FAIL'}")

    # Test 3: Isolation
    print("\n--- Test 3: Session Isolation (10 users, map_cmd check) ---")
    iso = await test_isolation()
    iso_pass = iso["leaks"] == 0
    print(f"  Success: {iso['ok']}/10, map_cmd leaks: {iso['leaks']}")
    print(f"  Pass: {'PASS' if iso_pass else 'FAIL'}")

    # Test 4: Disconnect
    print("\n--- Test 4: Client Disconnect + Recovery ---")
    dc = await test_disconnect()
    dc_pass = dc["sem_after"] == dc["sem_max"] and dc["recovery_ok"]
    print(f"  Events before disconnect: {dc['events_before_dc']}")
    print(f"  Semaphore after: {dc['sem_after']}/{dc['sem_max']}")
    print(f"  Recovery request: {'OK' if dc['recovery_ok'] else 'FAIL'}")
    print(f"  Pass: {'PASS' if dc_pass else 'FAIL'}")

    # Final summary
    async with httpx.AsyncClient(base_url=BASE) as c:
        h = (await c.get("/api/health/detail")).json()

    all_pass = concurrent_pass and g_pass and iso_pass and dc_pass
    print(f"\n{'=' * 60}")
    print(f"  Concurrent ramp:    {'PASS' if concurrent_pass else 'FAIL'}")
    print(f"  Greeting shortcut:  {'PASS' if g_pass else 'FAIL'}")
    print(f"  Session isolation:  {'PASS' if iso_pass else 'FAIL'}")
    print(f"  Disconnect recovery:{'PASS' if dc_pass else 'FAIL'}")
    print(f"  ---")
    print(f"  Semaphore: {h['semaphore_available']}/{h['semaphore_max']}")
    print(f"  Sessions:  {h['active_sessions']}")
    print(f"\n  OVERALL: {'ALL PASS' if all_pass else 'PARTIAL FAIL'}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
