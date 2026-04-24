"""Quality Sweep runner (2026-04-24).

Runs all scenarios from scripts.eval.scenarios against a live /api/chat endpoint,
captures SSE, applies the 13-point rubric, and writes:
  <OUT>/raw/{id}.sse                 full SSE dump
  <OUT>/raw/{id}.json                parsed events + meta
  <OUT>/summary.md                   PASS/FAIL table
  <OUT>/fail-details.md              per-FAIL reason

Usage:
  BASE=http://localhost:8000 OUT=docs/qa/runs/quality-sweep-2026-04-24/pass1 \
    python3 scripts/eval/run_quality_sweep.py
  # Filter:
  FILTER=A- python3 scripts/eval/run_quality_sweep.py
  RESUME=1 python3 scripts/eval/run_quality_sweep.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import urllib.request

# Ensure UTF-8 output on Windows
sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

# Import scenarios from same dir.  SCENARIO_MODULE env switches pack.
sys.path.insert(0, str(Path(__file__).parent))
import importlib  # noqa: E402

_SCN_MOD = os.environ.get("SCENARIO_MODULE", "scenarios")
all_scenarios = importlib.import_module(_SCN_MOD).all_scenarios  # noqa: E402


BASE = os.environ.get("BASE", "http://localhost:8000")
OUT_DIR = Path(os.environ.get("OUT", "docs/qa/runs/quality-sweep-2026-04-24/pass1"))
FILTER = os.environ.get("FILTER", "")
RESUME = os.environ.get("RESUME", "") == "1"
TIMEOUT = int(os.environ.get("TIMEOUT", "120"))
# REQUIRE_TRACE=1 → abort the sweep (both preflight + per-scenario) if the
# backend fails to emit `done.trace_id`. Catches Langfuse SDK drift early so
# we don't burn real LLM cost without tracing (see docs/plan/infra/
# langfuse-cost-coverage-fix-2026-04-24.md).
REQUIRE_TRACE = os.environ.get("REQUIRE_TRACE", "1") == "1"


XML_LEAK_PATTERNS = [
    re.compile(r"<tool_use\b"),
    re.compile(r"<invoke\b"),
    re.compile(r"</tool_result>"),
    re.compile(r"<parameter\b"),
    re.compile(r"<function_calls>"),
    re.compile(r"</function_calls>"),
    re.compile(r"<tool_name\b"),
    re.compile(r"<tool_result\b"),
]

# Match number + unit not followed by (tool_xxx) attribution within 60 chars
UNATTR_PAT = re.compile(
    r"(\d[\d,\.]*)\s*(원|명|%|억|만|건|개|점|위|시|회)(?![^\n]{0,60}\([a-z_]+\))"
)


def post_sse(session_id: str, message: str, district_code: str | None = None) -> str:
    payload: dict[str, Any] = {"message": message, "session_id": session_id}
    if district_code:
        payload["district_code"] = district_code
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}/api/chat",
        data=body,
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_sse(text: str) -> dict[str, Any]:
    events: list[dict] = []
    for raw in text.splitlines():
        if not raw.startswith("data:"):
            continue
        body = raw[5:].strip()
        if not body:
            continue
        try:
            events.append(json.loads(body))
        except json.JSONDecodeError:
            continue
    text_parts: list[str] = []
    tools: list[str] = []
    tool_inputs: list[dict] = []
    cards: list[dict] = []
    suggestions: list[str] = []
    map_cmds: list[dict] = []
    plan_steps: list[str] = []
    intent: str | None = None
    trace_id: str | None = None
    done = False

    for e in events:
        t = e.get("type")
        if t == "text":
            text_parts.append(e.get("content", ""))
        elif t == "tool":
            tools.append(e.get("name", ""))
            tool_inputs.append({"name": e.get("name"), "input": e.get("input", {})})
        elif t == "card":
            cards.append({"card_type": e.get("card_type"), "data": e.get("data", {})})
        elif t == "suggestion":
            qs = e.get("questions") or []
            suggestions.extend(qs if isinstance(qs, list) else [])
        elif t == "map_cmd":
            map_cmds.append(e)
        elif t == "plan":
            for step in e.get("steps") or []:
                if isinstance(step, dict):
                    plan_steps.append(step.get("label") or step.get("name") or str(step))
                else:
                    plan_steps.append(str(step))
            if "intent" in e:
                intent = e.get("intent")
        elif t == "done":
            done = True
            trace_id = e.get("trace_id")

    full_text = "".join(text_parts)
    return {
        "events_count": len(events),
        "text": full_text,
        "tools": tools,
        "tool_inputs": tool_inputs,
        "cards": cards,
        "suggestions": suggestions,
        "map_cmds_count": len(map_cmds),
        "plan_steps": plan_steps,
        "intent": intent,
        "trace_id": trace_id,
        "done": done,
    }


def detect_pdf_trigger(text: str) -> bool:
    # PDF is triggered client-side via event. Backend may respond with acknowledgement.
    pat = re.compile(r"(PDF|pdf|리포트|보고서|저장)", re.I)
    return bool(pat.search(text))


def apply_rubric(scenario: dict, parsed: dict) -> dict:
    """Return {score: int, max: int, results: [(check, pass, detail), ...]}."""
    exp = scenario["expected"]
    text = parsed["text"]
    tools = parsed["tools"]
    cards = parsed["cards"]
    intent = parsed["intent"] or ""

    results: list[tuple[str, bool, str]] = []

    # 1. done event
    results.append(("done_event", parsed["done"], "" if parsed["done"] else "no done event"))

    # 2. trace_id
    results.append(("trace_id", bool(parsed["trace_id"]), ""))

    # 3. no_xml_leak
    if exp.get("no_xml_leak"):
        leaks = [p.pattern for p in XML_LEAK_PATTERNS if p.search(text)]
        results.append(("no_xml_leak", not leaks, ",".join(leaks)))

    # 4. min_text_chars
    if "min_text_chars" in exp:
        ok = len(text) >= exp["min_text_chars"]
        results.append(("min_text_chars", ok, f"got={len(text)} need={exp['min_text_chars']}"))

    # 5. intent / intent_any
    if "intent" in exp:
        ok = intent == exp["intent"]
        results.append(("intent", ok, f"got={intent} need={exp['intent']}"))
    if "intent_any" in exp:
        ok = intent in exp["intent_any"]
        results.append(("intent_any", ok, f"got={intent} need-any={exp['intent_any']}"))

    # 6. tool_names
    if "tool_names_include" in exp:
        missing = [t for t in exp["tool_names_include"] if t not in tools]
        results.append(("tool_names_include", not missing, f"missing={missing} got={tools}"))
    if "tool_names_include_any" in exp:
        ok = any(t in tools for t in exp["tool_names_include_any"])
        results.append(("tool_names_include_any", ok, f"got={tools} need-any={exp['tool_names_include_any']}"))

    # 7. card_types
    card_types = [c["card_type"] for c in cards]
    if "card_types_include" in exp:
        missing = [c for c in exp["card_types_include"] if c not in card_types]
        results.append(("card_types_include", not missing, f"missing={missing} got={card_types}"))
    if "card_types_include_any" in exp:
        ok = any(c in card_types for c in exp["card_types_include_any"])
        results.append(("card_types_include_any", ok, f"got={card_types} need-any={exp['card_types_include_any']}"))

    # 8. card_district_name
    def card_names() -> list[str]:
        names = []
        for c in cards:
            d = c.get("data") or {}
            if "districtName" in d:
                names.append(d["districtName"])
            # recommend card stores under district_name snake_case
            if "district_name" in d:
                names.append(d["district_name"])
            if "districts" in d and isinstance(d["districts"], dict):
                for v in d["districts"].values():
                    if isinstance(v, dict):
                        if "district_name" in v:
                            names.append(v["district_name"])
                        if "districtName" in v:
                            names.append(v["districtName"])
        return names

    if "card_district_name" in exp:
        names = card_names()
        ok = exp["card_district_name"] in names
        results.append(("card_district_name", ok, f"got={names} need={exp['card_district_name']}"))
    if "card_district_name_any" in exp:
        names = card_names()
        ok = any(n in names for n in exp["card_district_name_any"])
        results.append(("card_district_name_any", ok, f"got={names} need-any={exp['card_district_name_any']}"))
    if "card_district_type" in exp:
        types = [c.get("data", {}).get("districtType") for c in cards]
        ok = exp["card_district_type"] in types
        results.append(("card_district_type", ok, f"got={types} need={exp['card_district_type']}"))

    # 9. compare_district_count_min
    if "compare_district_count_min" in exp:
        cnt = 0
        for c in cards:
            d = c.get("data") or {}
            if isinstance(d.get("districts"), dict):
                cnt = max(cnt, len(d["districts"]))
        for ti in parsed["tool_inputs"]:
            if ti["name"] == "compare_districts":
                dc = ti.get("input", {}).get("district_codes") or []
                cnt = max(cnt, len(dc))
        need = exp["compare_district_count_min"]
        results.append(("compare_district_count_min", cnt >= need, f"got={cnt} need≥{need}"))

    # 10. must_contain / must_not_contain
    if "must_contain_any_in_text" in exp:
        ok = any(s in text for s in exp["must_contain_any_in_text"])
        results.append(("must_contain_any_in_text", ok, f"need-any={exp['must_contain_any_in_text']}"))
    if "must_not_contain_in_text" in exp:
        hits = [s for s in exp["must_not_contain_in_text"] if s in text]
        results.append(("must_not_contain_in_text", not hits, f"leaked={hits}"))

    # 11. abstention
    if exp.get("abstention"):
        # heuristic: very short text OR no card + contains decline keyword
        decline_kw = ["정보가 없", "찾을 수 없", "확인할 수 없", "제공할 수 없", "데이터가 없", "죄송", "지원하지"]
        ok = (not cards) and any(k in text for k in decline_kw)
        results.append(("abstention", ok, f"cards={len(cards)} has_decline_kw={any(k in text for k in decline_kw)}"))
    if exp.get("abstention_or_graceful"):
        # either no crash, or has cards, or short text — broadly graceful
        ok = parsed["done"] and (len(text) > 0 or cards)
        results.append(("abstention_or_graceful", ok, ""))

    # 12. graceful (for empty/junk)
    if exp.get("graceful"):
        ok = parsed["done"]
        results.append(("graceful", ok, ""))

    # 13. hallucinated numbers
    if exp.get("no_hallucinated_numbers") or exp.get("no_hallucinated_numbers_strict"):
        unattr = UNATTR_PAT.findall(text)
        threshold = 3 if exp.get("no_hallucinated_numbers_strict") else 8
        ok = len(unattr) <= threshold and not cards  # if cards exist, numbers have source
        # if cards exist, numbers are presumed sourced
        if cards:
            ok = True
        results.append(("no_hallucinated_numbers", ok, f"unattr={len(unattr)} threshold={threshold} cards={len(cards)}"))

    # 14. pdf_trigger
    if exp.get("pdf_trigger"):
        # client-side event — proxy via keyword acknowledgement + suggestion
        ok = detect_pdf_trigger(text) or any("PDF" in s or "저장" in s for s in parsed["suggestions"])
        results.append(("pdf_trigger", ok, ""))
    if exp.get("pdf_trigger_or_graceful"):
        ok = parsed["done"]
        results.append(("pdf_trigger_or_graceful", ok, ""))

    # 15. coref_resolved_to — check card or tool input matches
    if "coref_resolved_to" in exp:
        target = exp["coref_resolved_to"]
        names = card_names()
        # also check tool inputs district names (via lookup or just name match in text)
        ok = any(target in n or n in target for n in names) or target in text
        results.append(("coref_resolved_to", ok, f"need={target} names={names}"))

    # 16. suggestion_count_min
    if "suggestion_count_min" in exp:
        ok = len(parsed["suggestions"]) >= exp["suggestion_count_min"]
        results.append(("suggestion_count_min", ok, f"got={len(parsed['suggestions'])}"))

    total = len(results)
    passed = sum(1 for _, p, _ in results if p)
    return {"score": passed, "max": total, "results": results}


def run_scenario(scn: dict) -> dict:
    session_id = f"qs-{scn['id']}-{uuid.uuid4().hex[:8]}"
    turn_parses: list[dict] = []
    turn_sses: list[str] = []
    for turn in scn["turns"]:
        msg = turn["message"]
        code = turn.get("send_district_code")
        t0 = time.time()
        try:
            sse = post_sse(session_id, msg, code)
        except Exception as e:
            sse = f"__ERROR__ {e}"
        elapsed = time.time() - t0
        turn_sses.append(sse)
        parsed = parse_sse(sse) if not sse.startswith("__ERROR__") else {
            "events_count": 0, "text": "", "tools": [], "tool_inputs": [], "cards": [],
            "suggestions": [], "map_cmds_count": 0, "plan_steps": [], "intent": None,
            "trace_id": None, "done": False, "error": sse,
        }
        parsed["elapsed_s"] = round(elapsed, 2)
        parsed["user_message"] = msg
        turn_parses.append(parsed)

    # rubric applies to the LAST turn's parse
    rubric = apply_rubric(scn, turn_parses[-1])
    return {
        "id": scn["id"],
        "category": scn["category"],
        "turn_count": len(scn["turns"]),
        "session_id": session_id,
        "turns": turn_parses,
        "rubric": rubric,
        "total_elapsed_s": sum(t.get("elapsed_s", 0) for t in turn_parses),
        "_sse_concat": "\n".join(turn_sses),
    }


def write_report(results: list[dict], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    raw = out / "raw"
    raw.mkdir(exist_ok=True)

    summary_lines = [
        "# Quality Sweep — Summary\n",
        f"- Total: {len(results)}",
        f"- PASS (≥80%): {sum(1 for r in results if r['rubric']['score'] / max(r['rubric']['max'],1) >= 0.8)}",
        f"- FAIL (<80%): {sum(1 for r in results if r['rubric']['score'] / max(r['rubric']['max'],1) < 0.8)}",
        f"- Avg score %: {round(100 * sum(r['rubric']['score'] / max(r['rubric']['max'],1) for r in results) / max(len(results),1), 1)}",
        "",
        "## Per-scenario",
        "",
        "| ID | Cat | Turns | Score | % | Elapsed | Verdict |",
        "|----|-----|------:|------:|--:|--------:|:-------:|",
    ]
    fail_lines = ["# Quality Sweep — FAIL Details\n"]

    for r in results:
        s, m = r["rubric"]["score"], r["rubric"]["max"]
        pct = round(100 * s / max(m, 1))
        verdict = "PASS" if pct >= 80 else "FAIL"
        summary_lines.append(
            f"| {r['id']} | {r['category']} | {r['turn_count']} | {s}/{m} | {pct} | {r['total_elapsed_s']:.1f}s | {verdict} |"
        )
        if verdict == "FAIL":
            fail_lines.append(f"\n## {r['id']}  ({s}/{m} = {pct}%)\n")
            fail_lines.append(f"- user messages: {[t['user_message'] for t in r['turns']]}")
            last = r["turns"][-1]
            fail_lines.append(f"- intent: `{last.get('intent')}`  tools: `{last.get('tools')}`  cards: `{[c['card_type'] for c in last.get('cards', [])]}`")
            fail_lines.append(f"- text preview: {last.get('text', '')[:300].replace(chr(10), ' ')}")
            for check, ok, detail in r["rubric"]["results"]:
                mark = "✓" if ok else "✗"
                fail_lines.append(f"  - {mark} {check}  {detail}")
        # persist per-scenario raw
        (raw / f"{r['id']}.sse").write_text(r["_sse_concat"], encoding="utf-8")
        light = {k: v for k, v in r.items() if k != "_sse_concat"}
        (raw / f"{r['id']}.json").write_text(json.dumps(light, ensure_ascii=False, indent=2), encoding="utf-8")

    (out / "summary.md").write_text("\n".join(summary_lines), encoding="utf-8")
    (out / "fail-details.md").write_text("\n".join(fail_lines), encoding="utf-8")


def preflight_trace() -> None:
    """Ping /api/chat once; abort the sweep if `done.trace_id` is missing.

    Rationale: Langfuse SDK drift (v2 stuck in container while code imports v3
    paths) silently disables tracing. The sweep then burns real Anthropic
    cost without any Langfuse attribution. This preflight is the backstop.
    Set REQUIRE_TRACE=0 to bypass (e.g. for load-test packs that deliberately
    disable tracing).
    """
    if not REQUIRE_TRACE:
        print("[sweep] preflight skipped (REQUIRE_TRACE=0)")
        return
    session_id = f"qs-preflight-{uuid.uuid4().hex[:8]}"
    try:
        sse = post_sse(session_id, "강남역 요약해줘")
    except Exception as e:
        print(f"[sweep] preflight FAIL — /api/chat unreachable: {e}", file=sys.stderr)
        sys.exit(2)
    parsed = parse_sse(sse)
    if not parsed.get("trace_id"):
        print(
            "[sweep] preflight FAIL — done event missing trace_id.\n"
            "  Langfuse tracing appears inactive. Abort to avoid untracked cost.\n"
            "  See docs/plan/infra/langfuse-cost-coverage-fix-2026-04-24.md\n"
            "  Override: REQUIRE_TRACE=0",
            file=sys.stderr,
        )
        sys.exit(3)
    print(f"[sweep] preflight OK — trace_id={parsed['trace_id'][:16]}…")


def main() -> None:
    preflight_trace()
    scenarios = all_scenarios()
    if FILTER:
        scenarios = [s for s in scenarios if FILTER in s["id"]]
    print(f"[sweep] base={BASE}  out={OUT_DIR}  scenarios={len(scenarios)}  filter={FILTER!r}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw = OUT_DIR / "raw"
    raw.mkdir(exist_ok=True)

    results: list[dict] = []
    for i, scn in enumerate(scenarios, 1):
        json_path = raw / f"{scn['id']}.json"
        if RESUME and json_path.exists():
            print(f"[sweep] ({i}/{len(scenarios)}) RESUME skip {scn['id']}")
            r = json.loads(json_path.read_text(encoding="utf-8"))
            r["_sse_concat"] = (raw / f"{scn['id']}.sse").read_text(encoding="utf-8", errors="replace") if (raw / f"{scn['id']}.sse").exists() else ""
            results.append(r)
            continue
        t0 = time.time()
        print(f"[sweep] ({i}/{len(scenarios)}) running {scn['id']}  turns={len(scn['turns'])}")
        r = run_scenario(scn)
        s, m = r["rubric"]["score"], r["rubric"]["max"]
        pct = round(100 * s / max(m, 1))
        verdict = "PASS" if pct >= 80 else "FAIL"
        print(f"[sweep] ({i}/{len(scenarios)}) {scn['id']}  {s}/{m} = {pct}%  {verdict}  ({time.time()-t0:.1f}s)")
        results.append(r)
        # incremental write
        light = {k: v for k, v in r.items() if k != "_sse_concat"}
        json_path.write_text(json.dumps(light, ensure_ascii=False, indent=2), encoding="utf-8")
        (raw / f"{scn['id']}.sse").write_text(r["_sse_concat"], encoding="utf-8")

    write_report(results, OUT_DIR)
    print(f"[sweep] done.  {OUT_DIR}/summary.md")


if __name__ == "__main__":
    main()
