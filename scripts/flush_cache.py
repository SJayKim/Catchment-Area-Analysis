"""Flush MarketScope Redis cache by prefix.

Usage:
    python scripts/flush_cache.py                    # flush all 5 report prefixes
    python scripts/flush_cache.py --prefix sales:   # flush only sales:* keys

Targets 5 tool cache prefixes:
    sales:*       (get_estimated_sales)
    compare:*     (compare_districts)
    recommend:*   (recommend_business)
    simulation:*  (simulate_revenue)
    summary:*     (district_summary)

Run from host shell or inside the server container:
    docker compose exec server python scripts/flush_cache.py
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "server"))

from server.config import settings  # noqa: E402
from server.services.cache import (  # noqa: E402
    MemoryCacheService,
    RedisCacheService,
    set_cache_service,
)

DEFAULT_PREFIXES = [
    "sales:",
    "compare:",
    "recommend:",
    "simulation:",
    "summary:",
]


async def _flush(prefixes: list[str]) -> int:
    if settings.use_mock:
        print("[flush_cache] USE_MOCK=true — MemoryCacheService in use (in-process only).")
        cache = MemoryCacheService()
    else:
        print(f"[flush_cache] Connecting to Redis: {settings.redis_url}")
        cache = RedisCacheService(settings.redis_url)
    set_cache_service(cache)

    total = 0
    for p in prefixes:
        count = await cache.flush_by_prefix(p)
        print(f"  {p:<14s} → {count} keys deleted")
        total += count

    await cache.close()
    print(f"[flush_cache] Total removed: {total}")
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prefix",
        action="append",
        default=None,
        help="Prefix to flush (repeatable). Defaults to all 5 report prefixes.",
    )
    args = parser.parse_args()
    prefixes = args.prefix if args.prefix else DEFAULT_PREFIXES
    asyncio.run(_flush(prefixes))


if __name__ == "__main__":
    main()
