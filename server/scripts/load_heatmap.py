"""Heatmap load test — verify singleflight coalesces concurrent cache misses.

Plan: docs/plan/infra/heatmap-singleflight-reintroduce.md (T2 / Pass 3).

Usage::

    # Backend up at :8000 with USE_MOCK=false
    USE_MOCK=false python server/scripts/load_heatmap.py \\
        --concurrency 50 --duration 30s

Then::

    curl http://localhost:8000/metrics | python -m json.tool | grep coalesced

Expected: ``singleflight_coalesced_total`` ≥ concurrency-1 after a fresh
``flush_cache.py`` run (first request leads, others coalesce).
"""

from __future__ import annotations

import argparse
import asyncio
import time

import httpx


async def fetch(client: httpx.AsyncClient, url: str) -> tuple[int, float]:
    start = time.monotonic()
    try:
        r = await client.get(url, timeout=30.0)
        return r.status_code, time.monotonic() - start
    except Exception:
        return 0, time.monotonic() - start


async def burst(base: str, concurrency: int, path: str) -> list[tuple[int, float]]:
    async with httpx.AsyncClient() as client:
        url = f"{base}{path}"
        return await asyncio.gather(*[fetch(client, url) for _ in range(concurrency)])


def percentile(samples: list[float], p: float) -> float:
    if not samples:
        return 0.0
    sorted_v = sorted(samples)
    k = (len(sorted_v) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_v) - 1)
    return sorted_v[f] + (k - f) * (sorted_v[c] - sorted_v[f])


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:8000")
    parser.add_argument("--concurrency", type=int, default=50)
    parser.add_argument("--path", default="/api/map-data/heatmap/all")
    args = parser.parse_args()

    print(f"=== Heatmap load test ({args.concurrency} concurrent → {args.path}) ===")

    # Phase 1 — single warmup (populates cache)
    metrics_before = await fetch_metrics(args.base)
    coalesced_before = metrics_before.get("singleflight_coalesced_total", 0)

    print("\n[Phase 1] cold burst (cache miss) ...")
    print("  Tip: run server/scripts/flush_cache.py first for a true cold start.")
    results = await burst(args.base, args.concurrency, args.path)
    latencies = [s for code, s in results if code == 200]
    success = sum(1 for code, _ in results if code == 200)
    print(f"  success={success}/{args.concurrency}")
    print(
        f"  p50={percentile(latencies, 50) * 1000:.0f}ms  "
        f"p95={percentile(latencies, 95) * 1000:.0f}ms  "
        f"p99={percentile(latencies, 99) * 1000:.0f}ms"
    )

    metrics_after = await fetch_metrics(args.base)
    coalesced_after = metrics_after.get("singleflight_coalesced_total", 0)
    coalesced_delta = coalesced_after - coalesced_before
    print(f"  coalesced_delta={coalesced_delta} (expected ≥ {args.concurrency - 1} on cold start)")

    # Phase 2 — warm burst
    print("\n[Phase 2] warm burst (cache hit) ...")
    results = await burst(args.base, args.concurrency, args.path)
    latencies = [s for code, s in results if code == 200]
    print(f"  p50={percentile(latencies, 50) * 1000:.0f}ms  p99={percentile(latencies, 99) * 1000:.0f}ms")


async def fetch_metrics(base: str) -> dict:
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{base}/metrics", timeout=10.0)
            return r.json() if r.status_code == 200 else {}
        except Exception:
            return {}


if __name__ == "__main__":
    asyncio.run(main())
