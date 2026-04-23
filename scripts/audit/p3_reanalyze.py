"""Re-analyze P3 results with augmented ground truth.

The original p3_llm_hallucination.py only collected numbers from card.data.
Actor's tool_end does not carry result, so underlying tool numbers (like
total_stores = 5111) are missing from ground truth. Augment by looking up
authoritative DB numbers for each sampled district and injecting them.
"""

from __future__ import annotations

import json
import re
import subprocess


NUM_RE = re.compile(r"(?P<num>[\d,]+(?:\.\d+)?)\s*(?P<unit>억|만|천|조|%|원|명|곳|개|시간|회|위)")


def parse_korean_amount(num_str: str, unit: str) -> float | None:
    try:
        n = float(num_str.replace(",", ""))
    except ValueError:
        return None
    multi = {"조": 1e12, "억": 1e8, "만": 1e4, "천": 1e3}
    if unit in multi:
        return n * multi[unit]
    return n


def extract_numbers(text: str) -> list[tuple[str, str, float]]:
    out = []
    for m in NUM_RE.finditer(text):
        num_str = m.group("num")
        unit = m.group("unit")
        val = parse_korean_amount(num_str, unit)
        if val is not None:
            out.append((f"{num_str}{unit}", unit, val))
    return out


def collect_ground_truth(card_data: dict) -> list[float]:
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


def load_db_facts() -> dict[str, dict]:
    """Return authoritative per-district numbers from DB."""
    sql = """
    SELECT
      es.district_code,
      (SELECT COALESCE(SUM(store_count),0) FROM stores s WHERE s.district_code=es.district_code AND s.quarter='2025Q4') AS stores,
      (SELECT COALESCE(SUM(open_count),0) FROM stores s WHERE s.district_code=es.district_code AND s.quarter='2025Q4') AS opens,
      (SELECT COALESCE(SUM(close_count),0) FROM stores s WHERE s.district_code=es.district_code AND s.quarter='2025Q4') AS closes,
      (SELECT COALESCE(SUM(franchise_count),0) FROM stores s WHERE s.district_code=es.district_code AND s.quarter='2025Q4') AS franchises,
      (SELECT COALESCE(SUM(total_pop),0) FROM floating_population fp WHERE fp.district_code=es.district_code AND fp.quarter='2025Q4') AS fp_sum,
      (SELECT COALESCE(MAX(total_pop),0) FROM floating_population fp WHERE fp.district_code=es.district_code AND fp.quarter='2025Q4') AS fp_peak,
      (COALESCE(SUM(es.monthly_sales),0) / 3)::bigint AS monthly_sales,
      (COALESCE(SUM(es.male_sales),0) / 3)::bigint AS male,
      (COALESCE(SUM(es.female_sales),0) / 3)::bigint AS female
    FROM estimated_sales es
    WHERE es.district_code IN ('3120189','3120103','3120053','3120028','3120043')
      AND es.quarter='2025Q4'
    GROUP BY es.district_code
    """
    wrapped = f"SELECT json_agg(t) FROM ({sql}) t;"
    r = subprocess.run(
        [
            "docker", "exec", "catchment-area-analysis-db-1",
            "psql", "-U", "marketscope", "-d", "marketscope",
            "-At", "-c", wrapped,
        ],
        capture_output=True, text=True, encoding="utf-8",
    )
    rows = json.loads(r.stdout.strip())
    facts: dict[str, dict] = {}
    for row in rows:
        code = row["district_code"]
        # Derived: per-store sales, close_rate, fran ratio
        stores = int(row["stores"] or 0)
        closes = int(row["closes"] or 0)
        fran = int(row["franchises"] or 0)
        ms = int(row["monthly_sales"] or 0)

        vals = []
        for v in row.values():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                vals.append(float(v))

        # Derived
        if stores > 0:
            vals.append(float(ms / stores))
            vals.append(float(round(closes / stores * 100, 1)))
            vals.append(float(round(fran / stores * 100, 1)))

        facts[code] = {
            "base_values": [float(v) for v in vals if v],
            "stores": stores,
            "monthly_sales": ms,
            "fp_sum": int(row["fp_sum"] or 0),
        }
    return facts


def is_suspicious(val: float, gt_set: set[float], tolerance: float = 0.03) -> tuple[bool, float | None]:
    """Return (suspicious, closest_ratio)."""
    if val == 0:
        return False, 0
    if val in gt_set:
        return False, 0
    # 1-unit exact match
    if any(abs(val - g) < 1 for g in gt_set):
        return False, 0
    # Ratio match
    best = min((abs(val - g) / max(g, 1) for g in gt_set if g > 0), default=None)
    if best is None:
        return True, None
    return best > tolerance, best


def main() -> None:
    with open("scripts/audit/p3_result.json", "r", encoding="utf-8") as f:
        d = json.load(f)

    facts = load_db_facts()

    re_audit = {"sessions": []}
    total_sus = 0
    total_confirmed_hallucination = 0

    for s in d["sessions"]:
        if "error" in s:
            re_audit["sessions"].append({"error": s["error"], "intent": s.get("intent")})
            continue

        district_code = s.get("district_code")
        message = s.get("message", "")
        intent = s.get("intent")

        gt = set()
        if district_code in facts:
            for v in facts[district_code]["base_values"]:
                gt.add(v)
        # Additionally, for comparison queries ("X이랑 홍대") also inject 홍대 facts
        if "홍대" in message and district_code != "3120103" and "3120103" in facts:
            for v in facts["3120103"]["base_values"]:
                gt.add(v)

        # Re-extract from text
        text = s.get("text_excerpt", "")  # only 400 chars - limitation
        # Actually to re-analyze we need full text, which we didn't save. Use
        # the per-session list of suspicious we already have + fallback.
        suspicious_items = s.get("suspicious", [])
        confirmed = []
        for sus in suspicious_items:
            val = float(sus["value"])
            is_sus, best = is_suspicious(val, gt)
            if is_sus:
                confirmed.append({"raw": sus["raw"], "value": val, "closest_ratio": best})

        # Near-match explanation: if val is within ±3 of a ground truth, likely
        # rounding/minor mismatch — not a hallucination
        near_match = []
        for sus in suspicious_items:
            val = float(sus["value"])
            close = [g for g in gt if g > 0 and abs(val - g) <= max(3, g * 0.01)]
            if close:
                near_match.append({"raw": sus["raw"], "value": val, "near": min(close, key=lambda g: abs(g - val))})

        total_sus += len(suspicious_items)
        total_confirmed_hallucination += len(confirmed)

        re_audit["sessions"].append({
            "intent": intent,
            "district_code": district_code,
            "message": message,
            "raw_suspicious_count": len(suspicious_items),
            "confirmed_hallucination_count": len(confirmed),
            "near_match_count": len(near_match),
            "confirmed": confirmed[:5],
            "near_match": near_match[:5],
        })

    re_audit["summary"] = {
        "total_raw_suspicious": total_sus,
        "confirmed_hallucination": total_confirmed_hallucination,
        "near_match_rounding": total_sus - total_confirmed_hallucination - sum(
            1 for s in re_audit["sessions"] if s.get("raw_suspicious_count", 0) == 0
        ),
    }

    print(json.dumps(re_audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    import os
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    main()
