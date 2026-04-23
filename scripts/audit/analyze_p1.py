"""Analyze p1_result.json → concise verdict table."""

from __future__ import annotations

import json
import sys


def main() -> None:
    with open("scripts/audit/p1_result.json", "r", encoding="utf-8") as f:
        d = json.load(f)

    print("=" * 72)
    print("PHASE 1 — Seoul API ↔ DB 일치성 verdict")
    print("=" * 72)

    for section_name, section in [
        ("sales_compare", d.get("sales_compare", [])),
        ("stores_compare", d.get("stores_compare", [])),
    ]:
        print(f"\n--- {section_name} ---")
        for r in section:
            code = r.get("district_code")
            common = r.get("common_categories", 0)
            all_match = r.get("all_match")
            sample_diffs = r.get("sample_diffs", [])
            total_checks = sum(len(c["checks"]) for c in sample_diffs)
            failed = [
                (d["category"], c)
                for d in sample_diffs
                for c in d["checks"]
                if not c["match"]
            ]
            sym = "PASS" if all_match else "FAIL"
            print(f"  [{sym}] {code} — common_cats={common} checks={total_checks} "
                  f"failed={len(failed)}")
            for cat, c in failed[:3]:
                print(f"     mismatch in cat={cat} field={c['field']}: "
                      f"api={c['api']} vs db={c['db']}")

    print(f"\n--- stores_service_used: {d.get('stores_service_used', '?')} ---")

    print("\n--- flpop_compare ---")
    for r in d.get("flpop_compare", []):
        code = r.get("district_code")
        if "error" in r:
            print(f"  [ERR] {code} — {r['error']}")
            continue
        checks = r.get("time_slot_checks", [])
        failed = [c for c in checks if not c["match"]]
        sym = "PASS" if r.get("all_slots_match") else "FAIL"
        print(f"  [{sym}] {code} — 6 slots checked, {len(failed)} mismatches")
        for c in failed[:3]:
            print(f"     slot={c['slot']} key={c['api_key']}: api={c['api']} vs db={c['db']}")
        g = r.get("gender_check", {})
        print(f"     gender API m={g.get('api_male_total')} f={g.get('api_female_total')} "
              f"| DB sum m={g.get('db_male_sum_across_slots')} f={g.get('db_female_sum_across_slots')}")


if __name__ == "__main__":
    import os
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    main()
