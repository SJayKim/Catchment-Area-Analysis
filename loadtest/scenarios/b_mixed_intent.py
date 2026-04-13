"""Scenario B: Mixed intent — 5 intent types at random weights.

Run:
    locust -f scenarios/b_mixed_intent.py --host=http://localhost:8002 \
        --headless -u 10 -r 2 -t 120s --csv=results/scenario_b

Pass criteria:
  - Error rate < 3%
  - Comparison requests produce card_type=comparison
  - Recommendation requests produce card_type=recommendation
"""

from __future__ import annotations

import asyncio
import random
import time
import uuid

import httpx
from locust import User, between, events, task

from sse_client import send_chat_sse

INTENT_POOL = [
    # (message, district_code, intent_name, weight)
    ("강남역 상권 분석해줘", "D3001", "summary", 30),
    ("강남역이랑 홍대 비교해줘", "D3001", "comparison", 20),
    ("건대입구에서 뭐하면 좋을까?", "D3003", "recommendation", 20),
    ("명동 이 자리 위험하지 않아?", "D3004", "risk", 15),
    ("서울역에서 카페 하면 매출 얼마나?", "D3005", "simulation", 15),
]

_WEIGHTED: list[tuple] = []
for item in INTENT_POOL:
    _WEIGHTED.extend([item] * item[3])


class MixedIntentUser(User):
    wait_time = between(3, 8)

    def on_start(self):
        self.session_id = f"scenB-{uuid.uuid4().hex[:8]}"
        self.client = httpx.AsyncClient(base_url=self.host)
        self._loop = asyncio.new_event_loop()

    def on_stop(self):
        self._loop.run_until_complete(self.client.aclose())
        self._loop.close()

    @task
    def mixed_request(self):
        msg, dc, intent, _ = random.choice(_WEIGHTED)
        start = time.monotonic()
        result = self._loop.run_until_complete(
            send_chat_sse(
                self.client,
                message=msg,
                session_id=self.session_id,
                district_code=dc,
                timeout=90.0,
                collect_events=True,
            )
        )
        elapsed_ms = (time.monotonic() - start) * 1000

        events.request.fire(
            request_type="SSE",
            name=f"B/{intent}",
            response_time=elapsed_ms,
            response_length=len(result.collected_text),
            exception=None if result.success else Exception(result.error),
            context={"intent": intent, "card_types": result.card_types},
        )
