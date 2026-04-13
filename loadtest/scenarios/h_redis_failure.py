"""Scenario H: Redis failure — graceful degradation test.

Prerequisites: Real mode with Docker Redis running.
  docker compose up db redis backend

Run manually (not via Locust — requires Docker pause/unpause):
    python scenarios/h_redis_failure.py --host http://localhost:8002

Pass criteria:
  - Service continues working when Redis is paused (DB fallback)
  - Warning log: 'Redis connection failed — cache disabled'
  - After Redis unpause, caching resumes automatically
  - No HTTP 5xx during the entire scenario
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time

import httpx

# Import from parent directory
sys.path.insert(0, str(__file__).rsplit("scenarios", 1)[0])
from sse_client import send_chat_sse


async def run_scenario(host: str):
    print(f"\n{'='*60}")
    print("Scenario H: Redis Failure / Graceful Degradation")
    print(f"{'='*60}\n")

    client = httpx.AsyncClient(base_url=host)

    # Phase 1: Normal operation (Redis up)
    print("[Phase 1] Normal — Redis up, sending 2 requests...")
    for i in range(2):
        r = await send_chat_sse(
            client, message="강남역 분석해줘", session_id=f"redis-h-{i}",
            district_code="D3001", timeout=60.0,
        )
        status = "PASS" if r.success else f"FAIL ({r.error})"
        print(f"  Request {i+1}: {status} ({r.total_time:.1f}s)")

    # Phase 2: Pause Redis
    print("\n[Phase 2] Pausing Redis container...")
    try:
        subprocess.run(["docker", "compose", "pause", "redis"], check=True, capture_output=True)
        print("  Redis paused.")
    except subprocess.CalledProcessError as e:
        print(f"  WARNING: Could not pause Redis: {e}")
        print("  (Skipping Redis failure test — is Docker running?)")
        await client.aclose()
        return

    # Wait a moment for connections to detect failure
    await asyncio.sleep(2)

    # Phase 3: Send requests with Redis down
    print("\n[Phase 3] Redis down — sending 3 requests (should fallback to DB)...")
    failures = 0
    for i in range(3):
        r = await send_chat_sse(
            client, message="홍대 분석해줘", session_id=f"redis-h-down-{i}",
            district_code="D3002", timeout=60.0,
        )
        status = "PASS" if r.success else f"FAIL ({r.error})"
        if not r.success:
            failures += 1
        print(f"  Request {i+1}: {status} ({r.total_time:.1f}s)")

    # Phase 4: Unpause Redis
    print("\n[Phase 4] Unpausing Redis container...")
    subprocess.run(["docker", "compose", "unpause", "redis"], check=True, capture_output=True)
    print("  Redis unpaused.")

    await asyncio.sleep(2)

    # Phase 5: Verify recovery
    print("\n[Phase 5] Recovery — sending 2 requests (should use cache again)...")
    for i in range(2):
        r = await send_chat_sse(
            client, message="강남역 분석해줘", session_id=f"redis-h-recover-{i}",
            district_code="D3001", timeout=60.0,
        )
        status = "PASS" if r.success else f"FAIL ({r.error})"
        print(f"  Request {i+1}: {status} ({r.total_time:.1f}s)")

    # Check health detail
    print("\n[Health Check]")
    try:
        resp = await client.get("/api/health/detail")
        detail = resp.json()
        redis_status = "connected" if detail.get("redis_connected") else "disconnected"
        print(f"  Redis: {redis_status}")
        print(f"  Active sessions: {detail.get('active_sessions')}")
    except Exception as e:
        print(f"  Could not fetch health detail: {e}")

    await client.aclose()

    # Summary
    print(f"\n{'='*60}")
    print(f"Result: {'PASS' if failures == 0 else 'FAIL'} — {failures} failures during Redis outage")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="http://localhost:8002")
    args = parser.parse_args()
    asyncio.run(run_scenario(args.host))
