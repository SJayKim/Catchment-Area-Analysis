"""Scenario E: Spike test — 5 steady → 30 spike → 5 recovery.

Run with Locust LoadTestShape:
    locust -f scenarios/e_spike.py --host=http://localhost:8002 \
        --headless --csv=results/scenario_e

Pass criteria:
  - Spike: error rate < 10%
  - Recovery: p95 TTFB returns to normal (< 5s) within 30s
  - Memory does not grow unbounded during spike
"""

from __future__ import annotations

import asyncio
import time
import uuid

import httpx
from locust import LoadTestShape, User, between, events, task

from sse_client import send_chat_sse


class SpikeUser(User):
    wait_time = between(2, 5)

    def on_start(self):
        self.session_id = f"scenE-{uuid.uuid4().hex[:8]}"
        self.client = httpx.AsyncClient(base_url=self.host)
        self._loop = asyncio.new_event_loop()

    def on_stop(self):
        self._loop.run_until_complete(self.client.aclose())
        self._loop.close()

    @task
    def request(self):
        start = time.monotonic()
        result = self._loop.run_until_complete(
            send_chat_sse(
                self.client,
                message="홍대입구 상권 요약해줘",
                session_id=self.session_id,
                district_code="D3002",
                timeout=90.0,
            )
        )
        elapsed_ms = (time.monotonic() - start) * 1000

        events.request.fire(
            request_type="SSE",
            name="E/spike",
            response_time=elapsed_ms,
            response_length=len(result.collected_text),
            exception=None if result.success else Exception(result.error),
            context={"ttfb_ms": result.ttfb * 1000},
        )


class SpikeShape(LoadTestShape):
    """
    Timeline:
      0-30s:  5 users  (steady)
      30-60s: ramp to 30 users (spike)
      60-90s: 30 users (sustained spike)
      90-120s: ramp down to 5 (recovery)
      120-150s: 5 users (verify recovery)
    """

    stages = [
        {"duration": 30, "users": 5, "spawn_rate": 5},
        {"duration": 60, "users": 30, "spawn_rate": 10},
        {"duration": 90, "users": 30, "spawn_rate": 10},
        {"duration": 120, "users": 5, "spawn_rate": 10},
        {"duration": 150, "users": 5, "spawn_rate": 5},
    ]

    def tick(self):
        run_time = self.get_run_time()
        for stage in self.stages:
            if run_time < stage["duration"]:
                return stage["users"], stage["spawn_rate"]
        return None  # Stop
