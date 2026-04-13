"""Scenario D: Semaphore saturation — 25 users exceed the 20-chat limit.

Run:
    locust -f scenarios/d_semaphore_saturation.py --host=http://localhost:8002 \
        --headless -u 25 -r 25 -t 60s --csv=results/scenario_d

Pass criteria:
  - First 20 get normal streaming
  - Users 21-25 wait (queued), not HTTP 5xx
  - No request returns 5xx
  - After completion, semaphore is fully released
"""

from __future__ import annotations

import asyncio
import time
import uuid

import httpx
from locust import User, constant_pacing, events, task

from sse_client import send_chat_sse


class SemaphoreSaturationUser(User):
    # Fire requests as fast as possible to saturate semaphore
    wait_time = constant_pacing(2)

    def on_start(self):
        self.session_id = f"scenD-{uuid.uuid4().hex[:8]}"
        self.client = httpx.AsyncClient(base_url=self.host)
        self._loop = asyncio.new_event_loop()

    def on_stop(self):
        self._loop.run_until_complete(self.client.aclose())
        self._loop.close()

    @task
    def saturate(self):
        start = time.monotonic()
        result = self._loop.run_until_complete(
            send_chat_sse(
                self.client,
                message="강남역 상권 분석해줘",
                session_id=self.session_id,
                district_code="D3001",
                timeout=120.0,  # longer timeout — may be queued behind semaphore
            )
        )
        elapsed_ms = (time.monotonic() - start) * 1000

        events.request.fire(
            request_type="SSE",
            name="D/semaphore",
            response_time=elapsed_ms,
            response_length=len(result.collected_text),
            exception=None if result.success else Exception(result.error),
            context={"ttfb_ms": result.ttfb * 1000},
        )
