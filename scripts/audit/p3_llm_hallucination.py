"""Phase 3 audit: LLM response hallucination check.

- SSE end-to-end capture of 5 districts × 3 intents = 15 sessions
- Extract ground-truth numbers from card/tool_end events
- Extract numbers from text events
- Flag numbers that cannot be derived from ground-truth
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
import uuid

BACKEND = "http://localhost:8000"

SAMPLES = [
    ("3120189", "강남역"),
    ("3120103", "홍대입구역"),
    ("3120053", "건대입구역"),
    ("3120028", "명동"),
    ("3120043", "서울역"),
]

INTENTS = [
    ("summary", "{name} 상권 요약해줘"),
    ("comparison", "{name}이랑 홍대 비교해줘"),
    ("recommendation", "{name}에 창업하기 좋은 업종 추천해줘"),
]

# Korean number patterns
NUM_RE = re.compile(r"(?P<num>[\d,]+(?:\.\d+)?)\s*(?P<unit>억|만|천|조|%|원|명|곳|개|시간|회|위)")
PLAIN_NUM_RE = re.compile(r"\b(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?)\b")


def parse_korean_amount(num_str: str, unit: str) -> float | None:
    """Convert '53.2억' -> 5_320_000_000 (approx)."""
    try:
        n = float(num_str.replace(",", ""))
    except ValueError:
        return None
    multi = {"조": 1e12, "억": 1e8, "만": 1e4, "천": 1e3}
    if unit in multi:
        return n * multi[unit]
    return n


def extract_numbers(text: str) -> list[tuple[str, str, float]]:
    """Extract (raw, unit, numeric) tuples from text."""
    out = []
    for m in NUM_RE.finditer(text):
        num_str = m.group("num")
        unit = m.group("unit")
        val = parse_korean_amount(num_str, unit)
        if val is not None:
            out.append((f"{num_str}{unit}", unit, val))
    return out


def collect_ground_truth(card_data: dict) -> list[float]:
    """Walk card payload and collect all leaf numeric values."""
    vals: list[float] = []

    def walk(x):
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for item in x:
                walk(item)
        elif isinstance(x, (int, float)) and not isinstance(x, bool):
            vals.append(float(x))

    walk(card_data)
    return vals


def sse_chat(message: str, district_code: str | None = None) -> dict:
    """Send chat request, capture SSE events until 'done'."""
    body = {
        "message": message,
        "session_id": str(uuid.uuid4()),
        "district_code": district_code,
    }
    req = urllib.request.Request(
        f"{BACKEND}/api/chat",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
        method="POST",
    )

    events: list[dict] = []
    text_chunks: list[str] = []

    with urllib.request.urlopen(req, timeout=120) as resp:
        buf = b""
        for chunk in resp:
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.strip()
                if not line or not line.startswith(b"data:"):
                    continue
                try:
                    ev = json.loads(line[5:].strip().decode("utf-8"))
                except json.JSONDecodeError:
                    continue
                events.append(ev)
                if ev.get("type") == "text":
                    text_chunks.append(ev.get("content", ""))
                elif ev.get("type") == "done":
                    return {"events": events, "final_text": "".join(text_chunks)}

    return {"events": events, "final_text": "".join(text_chunks)}


def audit_session(message: str, district_code: str | None) -> dict:
    try:
        sess = sse_chat(message, district_code)
    except Exception as e:
        return {"error": str(e), "message": message}

    events = sess["events"]
    text = sess["final_text"]

    ground_truth: list[float] = []
    card_types = []
    tool_calls = []
    for ev in events:
        t = ev.get("type")
        if t == "card":
            card_types.append(ev.get("card_type"))
            ground_truth.extend(collect_ground_truth(ev.get("data", {})))
        elif t == "tool_end":
            tool_calls.append(ev.get("name"))
            result = ev.get("result")
            if result is not None:
                ground_truth.extend(collect_ground_truth(result))

    # Deduplicate
    ground_truth_set = set(ground_truth)

    # Extract numbers from text
    text_nums = extract_numbers(text)
    suspicious: list[dict] = []
    for raw, unit, val in text_nums:
        # Skip pure percentage values (often derived)
        if unit == "%":
            continue
        # Check if val matches any ground truth (±5% tolerance for rounding)
        best_ratio = None
        for gt in ground_truth_set:
            if gt == 0:
                continue
            ratio = abs(val - gt) / gt
            if best_ratio is None or ratio < best_ratio:
                best_ratio = ratio
        # Also check exact small-integer matches (e.g. "5곳", "3위")
        match_in_truth = val in ground_truth_set or any(abs(val - gt) < 1 for gt in ground_truth_set)

        is_hallucination = True
        if match_in_truth:
            is_hallucination = False
        elif best_ratio is not None and best_ratio < 0.10:  # within 10%
            is_hallucination = False

        if is_hallucination:
            suspicious.append({
                "raw": raw,
                "value": val,
                "closest_gt_ratio": best_ratio,
            })

    return {
        "message": message,
        "district_code": district_code,
        "card_types": card_types,
        "tool_calls": tool_calls,
        "ground_truth_count": len(ground_truth_set),
        "text_length": len(text),
        "text_numbers_found": len(text_nums),
        "suspicious_count": len(suspicious),
        "suspicious": suspicious[:10],
        "text_excerpt": text[:400],
    }


def main() -> None:
    out: dict = {"sessions": []}
    for code, name in SAMPLES:
        for intent_name, template in INTENTS:
            msg = template.format(name=name)
            print(f"[{intent_name}] {msg}", file=sys.stderr)
            sess = audit_session(msg, code)
            sess["intent"] = intent_name
            out["sessions"].append(sess)

    # Aggregate
    total = len(out["sessions"])
    failed = [s for s in out["sessions"] if "error" in s]
    clean = [s for s in out["sessions"] if s.get("suspicious_count", 0) == 0 and "error" not in s]
    halluc = [s for s in out["sessions"] if s.get("suspicious_count", 0) > 0]

    out["summary"] = {
        "total_sessions": total,
        "errored": len(failed),
        "clean": len(clean),
        "with_suspicious_numbers": len(halluc),
    }

    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    import os
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    main()
