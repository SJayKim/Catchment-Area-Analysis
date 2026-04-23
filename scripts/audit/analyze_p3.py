"""Analyze p3_result.json → hallucination verdict."""

from __future__ import annotations

import json


def main() -> None:
    with open("scripts/audit/p3_result.json", "r", encoding="utf-8") as f:
        d = json.load(f)

    summary = d.get("summary", {})
    print("=" * 72)
    print("PHASE 3 — LLM response hallucination verdict")
    print("=" * 72)
    print(f"Total sessions: {summary.get('total_sessions')}")
    print(f"  clean:              {summary.get('clean')}")
    print(f"  with_suspicious:    {summary.get('with_suspicious_numbers')}")
    print(f"  errored:            {summary.get('errored')}")

    print()
    print("--- per-session breakdown ---")
    for s in d.get("sessions", []):
        if "error" in s:
            print(f"  [ERR]  {s.get('intent')} | {s.get('message')[:40]} → {s['error'][:80]}")
            continue
        intent = s.get("intent")
        msg = s.get("message", "")[:40]
        n_sus = s.get("suspicious_count", 0)
        n_nums = s.get("text_numbers_found", 0)
        n_gt = s.get("ground_truth_count", 0)
        sym = "CLEAN" if n_sus == 0 else f"SUS={n_sus}"
        print(f"  [{sym:8}] {intent:14} gt={n_gt:3} nums={n_nums:3} | {msg}")
        if n_sus > 0:
            for sus in s.get("suspicious", [])[:5]:
                print(f"     ? {sus['raw']} (value={sus['value']:.0f} "
                      f"closest_gt_ratio={sus.get('closest_gt_ratio')})")


if __name__ == "__main__":
    import os
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    main()
