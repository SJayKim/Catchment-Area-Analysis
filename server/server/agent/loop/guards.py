"""Output guards for the agentic loop — numeric grounding + evidence classification.

P2 mirrors the PAE respond-node numeric-sanity gate: non-blocking, logs nothing
here, surfaces a single `warning` SSE event + quality fields on `done`. The
structural critic re-query and mid-conversation abstention injection are P4.
"""

from __future__ import annotations

from typing import Any

from server.agent.utils.numeric_sanity import evaluate_response


def classify_evidence(tool_results: dict[str, Any], tool_errors: dict[str, Any]) -> str:
    """'full' if any tool returned data this turn, 'partial' if only errors, else 'empty'."""
    if tool_results:
        return "full"
    if tool_errors:
        return "partial"
    return "empty"


def verify_numeric(text: str, tool_results: dict[str, Any]) -> tuple[list[dict], float, dict[str, Any] | None]:
    """Run the numeric-sanity gate.

    Returns (quality_flags, match_rate, warning_event|None) — mirrors
    respond.py's post-stream check exactly (same flag/match_rate shapes).
    """
    report = evaluate_response(text, tool_results or {})
    quality_flags: list[dict] = []
    warning: dict[str, Any] | None = None
    if report.flags:
        payload = report.as_payload()
        quality_flags = payload["flags"]
        if any(f["severity"] == "warning" for f in quality_flags):
            warning = {
                "type": "warning",
                "rules": [f["rule"] for f in quality_flags if f["severity"] == "warning"],
                "match_rate": payload["match_rate"],
            }
    match_rate = round(report.matched_numbers / report.total_numbers, 3) if report.total_numbers else 1.0
    return quality_flags, match_rate, warning
