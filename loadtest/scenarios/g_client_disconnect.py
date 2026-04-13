"""Scenario G: Client disconnect — abort SSE mid-stream.

Run:
    locust -f scenarios/g_client_disconnect.py --host=http://localhost:8002 \
        --headless -u 10 -r 10 -t 30s --csv=results/scenario_g

Pass criteria:
  - Server logs 'Client disconnected mid-stream'
  - Semaphore is properly released (check /api/health/detail)
  - No memory leak (server RSS stays stable)
  - Subsequent requests from same session succeed
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid

import httpx
from locust import User, between, events, task

from sse_client import send_chat_sse


class DisconnectUser(User):
    wait_time = between(3, 6)

    def on_start(self):
        self.session_id = f"scenG-{uuid.uuid4().hex[:8]}"
        self.client = httpx.AsyncClient(base_url=self.host)
        self._loop = asyncio.new_event_loop()
        self._request_count = 0

    def on_stop(self):
        self._loop.run_until_complete(self.client.aclose())
        self._loop.close()

    @task(3)
    def disconnect_midstream(self):
        """Start SSE stream, read a few events, then abort."""
        self._request_count += 1
        start = time.monotonic()
        result = self._loop.run_until_complete(
            self._early_disconnect()
        )
        elapsed_ms = (time.monotonic() - start) * 1000

        events.request.fire(
            request_type="SSE",
            name="G/disconnect",
            response_time=elapsed_ms,
            response_length=0,
            exception=None,  # Disconnect is intentional, not an error
            context={"events_before_disconnect": result},
        )

    @task(1)
    def normal_after_disconnect(self):
        """Send a normal request to verify server recovered."""
        start = time.monotonic()
        result = self._loop.run_until_complete(
            send_chat_sse(
                self.client,
                message="안녕하세요",
                session_id=self.session_id,
                timeout=15.0,
            )
        )
        elapsed_ms = (time.monotonic() - start) * 1000

        events.request.fire(
            request_type="SSE",
            name="G/recovery",
            response_time=elapsed_ms,
            response_length=len(result.collected_text),
            exception=None if result.success else Exception(result.error),
            context={},
        )

    async def _early_disconnect(self) -> int:
        """Open SSE stream and disconnect after receiving 2-3 events."""
        events_received = 0
        payload = {
            "message": "강남역 상권 분석해줘",
            "session_id": self.session_id,
            "district_code": "D3001",
        }

        try:
            async with self.client.stream(
                "POST", "/api/chat", json=payload,
                timeout=httpx.Timeout(30.0, connect=5.0),
            ) as response:
                async for line in response.aiter_lines():
                    line = line.strip()
                    if line.startswith("data:"):
                        events_received += 1
                        # Disconnect after 2 events
                        if events_received >= 2:
                            break
        except Exception:
            pass

        return events_received
