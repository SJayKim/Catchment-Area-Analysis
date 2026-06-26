"""Tool result envelope for the agentic loop (agent_mode="agentic").

Wraps a raw tool dict in a uniform structure the agentic tool-use loop consumes:
- llm_view()  → compact, LLM-safe JSON (corrected field names + unit anchors)
- card_data   → payload for the `card` SSE event (frozen frontend contract)
- data/units  → numeric grounding
- source      → citation

The legacy PAE actor path does NOT use this (it keeps the raw dict), so this
layer is purely additive and leaves the pae path byte-identical.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# LLM-facing relabel: repos return 'daily_avg'/'dailyAvg' for a value that is
# actually the quarter-wide time-slot SUM, not a per-day average. The LLM only
# ever sees the corrected name via llm_view(); card_data keeps the frozen
# frontend key. (Renaming the repo field itself is a deferred follow-up — see
# docs/plan/infra/agentic-loop-rebuild.md Scope.)
_LLM_RELABEL = {"daily_avg": "quarter_total_pop", "dailyAvg": "quarter_total_pop"}


def _relabel(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {_LLM_RELABEL.get(k, k): _relabel(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_relabel(v) for v in obj]
    return obj


@dataclass
class ToolEnvelope:
    """Uniform wrapper around one tool's raw result for the agentic loop."""

    tool: str
    data: dict[str, Any] = field(default_factory=dict)
    units: dict[str, str] = field(default_factory=dict)
    source: list[dict] = field(default_factory=list)
    quarter: str = ""
    truncated: bool = False
    card_type: str | None = None
    card_data: dict[str, Any] | None = None
    error: str | None = None
    needs_category: bool = False
    llm_omit: tuple[str, ...] = ()

    def llm_view(self) -> dict[str, Any]:
        """Compact, LLM-safe view: corrected field names + unit anchors.

        On error, returns only {tool, error[, needs_category]}.
        """
        if self.error:
            view: dict[str, Any] = {"tool": self.tool, "error": self.error}
            if self.needs_category:
                view["needs_category"] = True
            return view
        result = _relabel(self.data)
        for key in self.llm_omit:
            result.pop(key, None)
        view = {"tool": self.tool, "result": result}
        if self.quarter:
            view["quarter"] = self.quarter
        if self.units:
            view["units"] = self.units
        if self.truncated:
            view["truncated"] = True
        return view
