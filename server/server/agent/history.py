"""Session-based conversation history for multi-turn PAE agent."""

from __future__ import annotations

from datetime import UTC, datetime

from server.config import settings


class ConversationHistory:
    """Stores and formats per-session conversation turns."""

    def __init__(self, max_turns: int = 10, content_limit: int = 300) -> None:
        self.max_turns = max_turns
        self.content_limit = content_limit
        self.turns: list[dict] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_turn(
        self,
        role: str,
        content: str,
        district_code: str | None = None,
        intent: str | None = None,
        tool_results_keys: list[str] | None = None,
    ) -> None:
        """Append a turn, truncating assistant content to *content_limit*."""
        truncated = content
        if role == "assistant" and len(content) > self.content_limit:
            truncated = content[: self.content_limit] + "..."

        self.turns.append(
            {
                "role": role,
                "content": truncated,
                "district_code": district_code,
                "intent": intent,
                "tool_results_keys": tool_results_keys or [],
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
        self._truncate()
        self._enforce_memory_limit()

    def get_recent(self, max_turns: int | None = None) -> list[dict]:
        """Return the most recent *max_turns* turns."""
        n = max_turns or self.max_turns
        return self.turns[-n:]

    def format_for_planner(self) -> str:
        """Compact text representation for the Planner prompt."""
        lines: list[str] = []
        for t in self.turns:
            if t["role"] == "user":
                district = f"({t['district_code']})" if t.get("district_code") else ""
                intent = t.get("intent") or ""
                tools = ",".join(t.get("tool_results_keys") or [])
                tools_str = f" tools:[{tools}]" if tools else ""
                lines.append(f'[User] {district} "{t["content"]}" → {intent}{tools_str}')
            else:
                lines.append(f'[AI] "{t["content"]}"')
        return "\n".join(lines)

    def get_last_district(self) -> str | None:
        """Walk backwards to find the most recent district_code."""
        for t in reversed(self.turns):
            if t.get("district_code"):
                return t["district_code"]
        return None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _truncate(self) -> None:
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns :]

    def _estimate_size(self) -> int:
        """Estimate total memory footprint by summing content lengths."""
        return sum(len(t.get("content", "")) for t in self.turns)

    def _enforce_memory_limit(self) -> None:
        """Pop oldest turns until estimated size is under the configured limit."""
        limit = settings.session_memory_limit_bytes
        while self.turns and self._estimate_size() > limit:
            self.turns.pop(0)
