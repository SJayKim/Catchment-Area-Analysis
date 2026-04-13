"""Locust load test for MarketScope AI — SSE chat endpoint.

Usage:
    locust -f locustfile.py --host=http://localhost:8002
    locust -f locustfile.py --host=http://localhost:8002 --headless -u 20 -r 5 -t 120s

Requires backend running with USE_MOCK=true LLM_PROVIDER=mock for zero-cost testing.
"""

from __future__ import annotations

import asyncio
import random
import time
import uuid

import httpx
from locust import User, between, events, task

from sse_client import SseResult, send_chat_sse

# ---------------------------------------------------------------------------
# Chat query pool — grouped by intent
# ---------------------------------------------------------------------------

QUERIES: list[dict] = [
    # Summary (30%)
    {"message": "강남역 상권 분석해줘", "district_code": "D3001", "weight": 30},
    {"message": "홍대입구 상권 요약해줘", "district_code": "D3002", "weight": 30},
    {"message": "건대입구 상권 현황 알려줘", "district_code": "D3003", "weight": 30},
    # Comparison (20%)
    {"message": "강남역이랑 홍대 비교해줘", "district_code": "D3001", "weight": 20},
    {"message": "건대랑 명동 비교해줘", "district_code": "D3003", "weight": 20},
    # Recommendation (20%)
    {"message": "건대입구에서 뭐하면 좋을까?", "district_code": "D3003", "weight": 20},
    {"message": "강남역에서 창업 추천해줘", "district_code": "D3001", "weight": 20},
    # Risk (15%)
    {"message": "명동 이 자리 위험하지 않아?", "district_code": "D3004", "weight": 15},
    {"message": "서울역 폐업률 높아?", "district_code": "D3005", "weight": 15},
    # Simulation (15%)
    {"message": "서울역에서 카페 하면 매출 얼마나?", "district_code": "D3005", "weight": 15},
    {"message": "강남역에서 한식 하면?", "district_code": "D3001", "weight": 15},
]

GREETING_QUERIES = [
    {"message": "안녕하세요", "district_code": None},
    {"message": "하이", "district_code": None},
    {"message": "hello", "district_code": None},
]

# Build weighted pool
_WEIGHTED_POOL: list[dict] = []
for q in QUERIES:
    _WEIGHTED_POOL.extend([q] * q["weight"])


def _pick_query() -> dict:
    return random.choice(_WEIGHTED_POOL)


def _pick_greeting() -> dict:
    return random.choice(GREETING_QUERIES)


# ---------------------------------------------------------------------------
# Async event loop helper
# ---------------------------------------------------------------------------

def _get_loop() -> asyncio.AbstractEventLoop:
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


# ---------------------------------------------------------------------------
# Locust User classes
# ---------------------------------------------------------------------------


class ChatUser(User):
    """Simulates a user sending varied chat queries via SSE."""

    wait_time = between(2, 5)

    def on_start(self):
        self.session_id = f"loadtest-{uuid.uuid4().hex[:12]}"
        self.client = httpx.AsyncClient(base_url=self.host)
        self._loop = _get_loop()

    def on_stop(self):
        self._loop.run_until_complete(self.client.aclose())

    @task(7)
    def send_chat(self):
        query = _pick_query()
        self._do_request(
            query["message"],
            query.get("district_code"),
            request_name=f"chat/{query['message'][:20]}",
        )

    @task(3)
    def send_greeting(self):
        query = _pick_greeting()
        self._do_request(
            query["message"],
            query.get("district_code"),
            request_name="chat/greeting",
        )

    def _do_request(self, message: str, district_code: str | None, request_name: str):
        start = time.monotonic()
        result: SseResult = self._loop.run_until_complete(
            send_chat_sse(
                self.client,
                message=message,
                session_id=self.session_id,
                district_code=district_code,
                timeout=90.0,
            )
        )
        elapsed_ms = (time.monotonic() - start) * 1000

        if result.success:
            events.request.fire(
                request_type="SSE",
                name=request_name,
                response_time=elapsed_ms,
                response_length=len(result.collected_text),
                exception=None,
                context={
                    "ttfb_ms": result.ttfb * 1000,
                    "first_text_ms": result.first_text_time * 1000,
                    "total_events": result.total_events,
                    "card_types": result.card_types,
                },
            )
        else:
            events.request.fire(
                request_type="SSE",
                name=request_name,
                response_time=elapsed_ms,
                response_length=0,
                exception=Exception(result.error),
                context={},
            )


class GreetingFloodUser(User):
    """Lightweight user that only sends greetings — tests agent-skip path."""

    wait_time = between(0.1, 0.5)

    def on_start(self):
        self.session_id = f"greet-{uuid.uuid4().hex[:8]}"
        self.client = httpx.AsyncClient(base_url=self.host)
        self._loop = _get_loop()

    def on_stop(self):
        self._loop.run_until_complete(self.client.aclose())

    @task
    def send_greeting(self):
        start = time.monotonic()
        result = self._loop.run_until_complete(
            send_chat_sse(
                self.client,
                message="안녕하세요",
                session_id=self.session_id,
                timeout=10.0,
            )
        )
        elapsed_ms = (time.monotonic() - start) * 1000
        events.request.fire(
            request_type="SSE",
            name="greeting/flood",
            response_time=elapsed_ms,
            response_length=len(result.collected_text),
            exception=None if result.success else Exception(result.error),
            context={},
        )
