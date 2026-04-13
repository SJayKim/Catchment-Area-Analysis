"""Scenario A: Basic summary — gradual ramp 1 → 5 → 10 → 20 concurrent users.

Run:
    locust -f scenarios/a_basic_summary.py --host=http://localhost:8002 \
        --headless -t 240s --csv=results/scenario_a

Pass criteria:
  - 10 concurrent: p95 TTFB < 3s, p95 total < 30s
  - 20 concurrent: p95 TTFB < 5s, error rate < 5%
  - All responses contain 'done' event
"""

from __future__ import annotations

import asyncio
import time
import uuid

import httpx
from locust import User, constant_pacing, events, task

from sse_client import send_chat_sse


class BasicSummaryUser(User):
    """Single intent: '강남역 상권 분석해줘' with gradual ramp."""

    # Pace each user to send 1 request every 10 seconds
    wait_time = constant_pacing(10)

    def on_start(self):
        self.session_id = f"scenA-{uuid.uuid4().hex[:8]}"
        self.client = httpx.AsyncClient(base_url=self.host)
        self._loop = asyncio.new_event_loop()

    def on_stop(self):
        self._loop.run_until_complete(self.client.aclose())
        self._loop.close()

    @task
    def summary_request(self):
        start = time.monotonic()
        result = self._loop.run_until_complete(
            send_chat_sse(
                self.client,
                message="강남역 상권 분석해줘",
                session_id=self.session_id,
                district_code="D3001",
                timeout=60.0,
            )
        )
        elapsed_ms = (time.monotonic() - start) * 1000

        events.request.fire(
            request_type="SSE",
            name="A/summary",
            response_time=elapsed_ms,
            response_length=len(result.collected_text),
            exception=None if result.success else Exception(result.error),
            context={
                "ttfb_ms": result.ttfb * 1000,
                "total_events": result.total_events,
            },
        )
