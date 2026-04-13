"""Custom SSE client for MarketScope AI load testing.

MarketScope uses a non-standard SSE format:
  - No `event:` line
  - `data:` line contains JSON with embedded `type` field
  - e.g. `data: {"type": "text", "content": "..."}`

Standard SSE parsers must NOT be used (see memory: feedback_marketscope_sse_format).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

import httpx


@dataclass
class SseResult:
    """Collected metrics from a single SSE chat request."""

    success: bool = False
    error: str | None = None

    # Timing (seconds)
    ttfb: float = 0.0  # Time to first byte
    first_text_time: float = 0.0  # Time to first 'text' event
    total_time: float = 0.0  # Time to 'done' event

    # Event counters
    event_counts: dict[str, int] = field(default_factory=dict)
    total_events: int = 0

    # Content
    collected_text: str = ""
    card_types: list[str] = field(default_factory=list)
    district_codes_in_map_cmd: list[str] = field(default_factory=list)

    # Raw events for debugging
    events: list[dict] = field(default_factory=list)


async def send_chat_sse(
    client: httpx.AsyncClient,
    message: str,
    session_id: str,
    district_code: str | None = None,
    timeout: float = 90.0,
    collect_events: bool = False,
) -> SseResult:
    """Send a chat request and consume the SSE stream, collecting metrics.

    Args:
        client: Reusable httpx async client.
        message: User message text.
        session_id: Unique session identifier.
        district_code: Optional district code.
        timeout: Max seconds to wait for 'done' event.
        collect_events: If True, store raw events in result.events.

    Returns:
        SseResult with timing, counters, and content.
    """
    result = SseResult()
    payload: dict = {"message": message, "session_id": session_id}
    if district_code:
        payload["district_code"] = district_code

    start = time.monotonic()
    first_byte_received = False
    first_text_received = False

    try:
        async with client.stream(
            "POST",
            "/api/chat",
            json=payload,
            timeout=httpx.Timeout(timeout, connect=10.0),
        ) as response:
            if response.status_code != 200:
                result.error = f"HTTP {response.status_code}"
                result.total_time = time.monotonic() - start
                return result

            async for raw_line in response.aiter_lines():
                now = time.monotonic()

                if not first_byte_received:
                    result.ttfb = now - start
                    first_byte_received = True

                line = raw_line.strip()
                if not line or not line.startswith("data:"):
                    continue

                data_str = line[len("data:"):].strip()
                if not data_str:
                    continue

                try:
                    event = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                event_type = event.get("type", "unknown")
                result.event_counts[event_type] = result.event_counts.get(event_type, 0) + 1
                result.total_events += 1

                if collect_events:
                    result.events.append(event)

                # Collect text content
                if event_type == "text":
                    content = event.get("content", "")
                    result.collected_text += content
                    if not first_text_received:
                        result.first_text_time = now - start
                        first_text_received = True

                # Track card types
                elif event_type == "card":
                    card_type = event.get("card_type", "unknown")
                    result.card_types.append(card_type)

                # Track map commands
                elif event_type == "map_cmd":
                    dc = event.get("district_code") or event.get("params", {}).get("district_code")
                    if dc:
                        result.district_codes_in_map_cmd.append(dc)

                # Done — success
                elif event_type == "done":
                    result.success = True
                    result.total_time = now - start
                    return result

        # Stream ended without 'done'
        result.total_time = time.monotonic() - start
        if not result.success:
            result.error = "Stream ended without 'done' event"

    except httpx.TimeoutException:
        result.total_time = time.monotonic() - start
        result.error = f"Timeout after {result.total_time:.1f}s"
    except httpx.HTTPError as e:
        result.total_time = time.monotonic() - start
        result.error = f"HTTP error: {e}"
    except Exception as e:
        result.total_time = time.monotonic() - start
        result.error = f"Unexpected: {e}"

    return result
