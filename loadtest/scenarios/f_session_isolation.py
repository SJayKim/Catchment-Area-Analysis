"""Scenario F: Session isolation — verify no data leakage between users.

Run:
    locust -f scenarios/f_session_isolation.py --host=http://localhost:8002 \
        --headless -u 10 -r 10 -t 60s --csv=results/scenario_f

Pass criteria:
  - User requesting 강남역 (D3001) never sees "홍대" in response
  - User requesting 홍대 (D3002) never sees "강남역" in response
  - Each map_cmd contains the correct district_code
  - All responses end with 'done' event
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid

import httpx
from locust import User, between, events, task

from sse_client import send_chat_sse

logger = logging.getLogger(__name__)

# Each user is pinned to one district
DISTRICTS = [
    ("강남역 상권 분석해줘", "D3001", "강남역", ["홍대", "건대", "명동", "서울역"]),
    ("홍대입구 상권 분석해줘", "D3002", "홍대", ["강남역", "건대", "명동", "서울역"]),
    ("건대입구 상권 분석해줘", "D3003", "건대", ["강남역", "홍대", "명동", "서울역"]),
    ("명동 상권 분석해줘", "D3004", "명동", ["강남역", "홍대", "건대", "서울역"]),
    ("서울역 상권 분석해줘", "D3005", "서울역", ["강남역", "홍대", "건대", "명동"]),
]

_user_counter = 0


class SessionIsolationUser(User):
    wait_time = between(5, 10)

    def on_start(self):
        global _user_counter
        idx = _user_counter % len(DISTRICTS)
        _user_counter += 1

        self.msg, self.district_code, self.own_name, self.forbidden = DISTRICTS[idx]
        self.session_id = f"isoF-{uuid.uuid4().hex[:8]}"
        self.client = httpx.AsyncClient(base_url=self.host)
        self._loop = asyncio.new_event_loop()
        self.leakage_count = 0

    def on_stop(self):
        self._loop.run_until_complete(self.client.aclose())
        self._loop.close()
        if self.leakage_count > 0:
            logger.error(
                "SESSION LEAKAGE DETECTED: user=%s district=%s leakages=%d",
                self.session_id, self.own_name, self.leakage_count,
            )

    @task
    def check_isolation(self):
        start = time.monotonic()
        result = self._loop.run_until_complete(
            send_chat_sse(
                self.client,
                message=self.msg,
                session_id=self.session_id,
                district_code=self.district_code,
                timeout=90.0,
                collect_events=True,
            )
        )
        elapsed_ms = (time.monotonic() - start) * 1000

        # Check for cross-session data leakage
        leakage = None
        text_lower = result.collected_text.lower()
        for forbidden_name in self.forbidden:
            if forbidden_name.lower() in text_lower:
                leakage = f"Found '{forbidden_name}' in response for {self.own_name}"
                self.leakage_count += 1
                break

        # Check map_cmd district codes
        for dc in result.district_codes_in_map_cmd:
            if dc != self.district_code:
                leakage = f"map_cmd has {dc}, expected {self.district_code}"
                self.leakage_count += 1
                break

        err = None
        if not result.success:
            err = Exception(result.error)
        elif leakage:
            err = Exception(f"ISOLATION VIOLATION: {leakage}")

        events.request.fire(
            request_type="SSE",
            name=f"F/isolation/{self.own_name}",
            response_time=elapsed_ms,
            response_length=len(result.collected_text),
            exception=err,
            context={"leakage": leakage},
        )
