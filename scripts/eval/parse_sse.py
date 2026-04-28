"""Parse MarketScope SSE dumps into a structured eval report.

Usage: python scripts/eval/parse_sse.py docs/qa/runs/eval-round2-raw/ > report.md
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def parse_sse_file(path: Path) -> dict:
    events: list[dict] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not raw.startswith("data:"):
            continue
        body = raw[5:].strip()
        if not body:
            continue
        try:
            events.append(json.loads(body))
        except json.JSONDecodeError:
            continue

    # Aggregate
    text_parts: list[str] = []
    tools: list[str] = []
    tool_inputs: list[dict] = []
    cards: list[dict] = []
    thinking: list[str] = []
    suggestions: list[str] = []
    map_cmds: list[dict] = []
    plan: list[dict] = []
    trace_id: str | None = None

    for e in events:
        t = e.get("type")
        if t == "text":
            text_parts.append(e.get("content", ""))
        elif t == "tool":
            tools.append(e.get("name", ""))
            if "input" in e:
                tool_inputs.append({"name": e.get("name"), "input": e.get("input")})
        elif t == "card":
            cards.append({"card_type": e.get("card_type"), "data": e.get("data", {})})
        elif t == "thinking":
            thinking.append(e.get("step", ""))
        elif t == "suggestion":
            qs = e.get("questions") or []
            suggestions.extend(qs if isinstance(qs, list) else [str(qs)])
        elif t == "map_cmd":
            map_cmds.append(e)
        elif t == "plan":
            if "steps" in e:
                plan.extend(e.get("steps") or [])
            elif "intent" in e:
                plan.append({"intent": e.get("intent")})
        elif t == "done":
            trace_id = e.get("trace_id")

    full_text = "".join(text_parts)

    # GAP-D: unattributed numeric claims (number + unit without (tool_...))
    # Simplified check: count numbers with unit not followed by `(something)`
    unattr_pat = re.compile(
        r"(\d[\d,\.]*)\s*(원|명|%|억|만|건|개|점|위|시|회)(?![^\n]{0,60}\([a-z_]+\))"
    )
    unattr = unattr_pat.findall(full_text)

    return {
        "file": path.name,
        "events_total": len(events),
        "tools": tools,
        "tool_inputs": tool_inputs,
        "cards": [c["card_type"] for c in cards],
        "card_payloads": cards,
        "thinking_steps": thinking,
        "suggestions": suggestions,
        "map_cmds": map_cmds,
        "plan": plan,
        "trace_id": trace_id,
        "text_chars": len(full_text),
        "text_full": full_text,
        "unattributed_count": len(unattr),
        "unattributed_samples": unattr[:5],
    }


def format_report(results: list[dict]) -> str:
    lines = ["# Accuracy Round 2 — Raw SSE Extract", ""]
    for r in results:
        lines.append(f"## {r['file']}")
        lines.append("")
        lines.append(f"- events: {r['events_total']} · text_chars: {r['text_chars']} · trace: `{r['trace_id']}`")
        lines.append(f"- tools: {r['tools']}")
        lines.append(f"- cards: {r['cards']}")
        if r["plan"]:
            lines.append(f"- plan: {r['plan']}")
        if r["map_cmds"]:
            lines.append(f"- map_cmds: {len(r['map_cmds'])}")
        lines.append(f"- unattributed numbers: {r['unattributed_count']}  samples={r['unattributed_samples']}")
        lines.append(f"- suggestions: {r['suggestions'][:3]}")
        lines.append("")
        lines.append("### tool inputs")
        for ti in r["tool_inputs"][:10]:
            lines.append(f"  - {ti['name']}: {json.dumps(ti['input'], ensure_ascii=False, default=str)[:200]}")
        lines.append("")
        lines.append("### card payloads (truncated)")
        for c in r["card_payloads"][:4]:
            payload = json.dumps(c["data"], ensure_ascii=False, default=str)[:400]
            lines.append(f"  - **{c['card_type']}**: {payload}")
        lines.append("")
        lines.append("### response text")
        lines.append("```")
        lines.append(r["text_full"])
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: parse_sse.py <dir_or_file>", file=sys.stderr)
        sys.exit(2)
    target = Path(sys.argv[1])
    files = sorted(target.glob("*.sse")) if target.is_dir() else [target]
    results = [parse_sse_file(f) for f in files]
    print(format_report(results))


if __name__ == "__main__":
    main()
