"""Trust regression — 5 상권 응답 수치 vs DB ground truth 교차검증.

사용법:
    python scripts/eval/trust_scenarios.py

출력:
    docs/qa/runs/trust-eval-<YYYY-MM-DD>/
      summary.md
      per-district.md
      raw/<district>.sse
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path

BACKEND = "http://localhost:8000"
# REQUIRE_TRACE=1 (default) aborts the run if Langfuse tracing is inactive.
# See docs/plan/infra/langfuse-cost-coverage-fix-2026-04-24.md
REQUIRE_TRACE = os.environ.get("REQUIRE_TRACE", "1") == "1"
DB_CONTAINER = "catchment-area-analysis-db-1"
DB_USER = "marketscope"
DB_NAME = "marketscope"
QUARTER = "2025Q4"

TARGETS = [
    ("종로3가역", "3120009", "발달상권"),
    ("남대문시장(자유상가)", "3130024", "전통시장"),
    ("강남역", "3120189", "발달상권"),
    ("망원시장", "3130186", "전통시장"),
    (
        "명동 남대문 북창동 다동 무교동 관광특구",
        "3001492",
        "관광특구",
    ),
]


@dataclass
class Ground:
    district_code: str
    district_name: str
    district_type: str
    monthly_sales_won: int  # /3 환산된 월 매출
    store_count: int
    close_rate_pct: float | None
    floating_pop_daily_avg: int | None


@dataclass
class Verdict:
    district: str
    sent_message: str
    ground: Ground
    sse_raw_path: Path
    response_text: str
    extracted_numbers: list[tuple[str, int]] = field(default_factory=list)
    checks: list[dict] = field(default_factory=list)
    pass_count: int = 0
    fail_count: int = 0
    done_payload: dict = field(default_factory=dict)

    @property
    def verdict(self) -> str:
        return "PASS" if self.fail_count == 0 and self.pass_count > 0 else "FAIL"


def psql(sql: str) -> str:
    cmd = [
        "docker",
        "exec",
        DB_CONTAINER,
        "psql",
        "-U",
        DB_USER,
        "-d",
        DB_NAME,
        "-t",
        "-A",
        "-F",
        "|",
        "-c",
        sql,
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding="utf-8")
    return out.stdout.strip()


def fetch_ground(code: str, name: str, dtype: str) -> Ground:
    sales_row = psql(
        f"SELECT COALESCE(SUM(monthly_sales),0) FROM estimated_sales WHERE district_code='{code}' AND quarter='{QUARTER}';"
    )
    quarterly = int(sales_row or 0)
    monthly = quarterly // 3

    store_row = psql(
        f"SELECT COALESCE(SUM(store_count),0) FROM stores WHERE district_code='{code}' AND quarter='{QUARTER}';"
    )
    store_count = int(store_row or 0)

    close_row = psql(
        f"""SELECT ROUND(100.0 * SUM(close_count)::numeric / NULLIF(SUM(store_count),0), 2)
            FROM stores WHERE district_code='{code}' AND quarter='{QUARTER}';"""
    )
    close_rate = float(close_row) if close_row else None

    pop_row = psql(
        f"""SELECT COALESCE(SUM(total_pop),0)
            FROM floating_population WHERE district_code='{code}' AND quarter='{QUARTER}';"""
    )
    pop = int(pop_row or 0)

    return Ground(
        district_code=code,
        district_name=name,
        district_type=dtype,
        monthly_sales_won=monthly,
        store_count=store_count,
        close_rate_pct=close_rate,
        floating_pop_daily_avg=pop,
    )


KOREAN_NUM_PATTERN = re.compile(r"(\d{1,3}(?:,\d{3})*|\d+)(?:\.(\d+))?\s*(조|억|만|천)?\s*(원|명|개)?")
UNIT_TO_SCALE = {"조": 10**12, "억": 10**8, "만": 10**4, "천": 10**3, None: 1}


def extract_numbers(text: str) -> list[tuple[str, int]]:
    """Parse Korean number expressions like '1,104억', '590만 6천명', '2,679만원'.

    Returns list of (raw_snippet, scalar_value).
    """
    found: list[tuple[str, int]] = []
    # compound: '590만 6천명' -> 5,906,000
    compound_re = re.compile(r"(\d+(?:,\d{3})*)\s*(조|억|만)\s*(\d+(?:,\d{3})*)\s*(천|백|십)?\s*(원|명|개)?")
    for m in compound_re.finditer(text):
        hi = int(m.group(1).replace(",", ""))
        hi_unit = UNIT_TO_SCALE[m.group(2)]
        lo = int(m.group(3).replace(",", ""))
        lo_unit = UNIT_TO_SCALE.get(m.group(4))
        value = hi * hi_unit + lo * lo_unit
        found.append((m.group(0), value))

    consumed = {m.start() for m in compound_re.finditer(text)}

    for m in KOREAN_NUM_PATTERN.finditer(text):
        if m.start() in consumed:
            continue
        base = int(m.group(1).replace(",", ""))
        frac_str = m.group(2)
        unit = UNIT_TO_SCALE[m.group(3)]
        value = base * unit
        if frac_str:
            frac_value = int(frac_str) * unit // (10 ** len(frac_str))
            value += frac_value
        found.append((m.group(0), value))
    return found


def send_chat(message: str, session_id: str, raw_path: Path) -> tuple[str, dict]:
    """Return (assembled_text, done_payload). done_payload may include quality_flags."""
    data = json.dumps({"message": message, "session_id": session_id}).encode("utf-8")
    req = urllib.request.Request(
        f"{BACKEND}/api/chat",
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        body = r.read().decode("utf-8", "replace")
    raw_path.write_text(body, encoding="utf-8")
    text_chunks: list[str] = []
    done_payload: dict = {}
    for line in body.splitlines():
        if line.startswith("data:"):
            try:
                payload = json.loads(line[5:].strip())
            except json.JSONDecodeError:
                continue
            if payload.get("type") == "text":
                text_chunks.append(payload.get("content", ""))
            elif payload.get("type") == "done":
                done_payload = payload
    return "".join(text_chunks), done_payload


def within_pct(actual: float, expected: float, tol: float = 0.05) -> bool:
    if expected == 0:
        return actual == 0
    return abs(actual - expected) / expected <= tol


def check_district(name: str, code: str, dtype: str, out_dir: Path) -> Verdict:
    ground = fetch_ground(code, name, dtype)
    raw_path = out_dir / "raw" / f"{code}.sse"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    message = f"{name.split('(')[0].strip()} 상권 자세히 분석해줘"
    response, done_payload = send_chat(message, f"trust-{code}", raw_path)
    numbers = extract_numbers(response)

    v = Verdict(
        district=name,
        sent_message=message,
        ground=ground,
        sse_raw_path=raw_path,
        response_text=response,
        extracted_numbers=numbers[:50],
    )
    # Attach L3 evaluator output from the SSE done event.
    v.done_payload = done_payload

    # Check 1: monthly sales appears within ±5%
    monthly = ground.monthly_sales_won
    sales_hits = [raw for raw, v_ in numbers if within_pct(v_, monthly, 0.05)]
    v.checks.append(
        {
            "rule": "monthly_sales ±5%",
            "expected": monthly,
            "hits": sales_hits,
            "pass": bool(sales_hits),
        }
    )

    # Check 2: store_count exact or ±2
    store_hits = [raw for raw, v_ in numbers if abs(v_ - ground.store_count) <= 5]
    v.checks.append(
        {
            "rule": f"store_count ≈ {ground.store_count}",
            "expected": ground.store_count,
            "hits": store_hits,
            "pass": bool(store_hits),
        }
    )

    # Check 3: benchmark context mentioned
    ctx_keywords = ["p95", "상위 5", "상위 10", "상위 25", "평균", "중앙값", "분위", "p50", "p75"]
    has_ctx = any(k in response for k in ctx_keywords)
    v.checks.append(
        {
            "rule": "벤치마크 컨텍스트 언급",
            "expected": "p95/상위 N% 표현",
            "hits": [k for k in ctx_keywords if k in response],
            "pass": has_ctx,
        }
    )

    # Check 4: attribution tag `(tool_name)` present for sales number
    has_attr = bool(re.search(r"\(get_district_summary\)|\(get_estimated_sales\)", response))
    v.checks.append(
        {
            "rule": "sales attribution tag",
            "expected": "(get_*_sales) or (get_district_summary)",
            "hits": re.findall(r"\((get_[a-z_]+)\)", response)[:5],
            "pass": has_attr,
        }
    )

    # Check 5: per-store sales (점포당 / 점포 평균) mentioned
    has_per_store = any(k in response for k in ["점포당", "1개 점포", "점포 평균"])
    v.checks.append(
        {
            "rule": "점포당 매출 제시",
            "expected": "점포당 월 매출 N만원",
            "hits": [k for k in ["점포당", "1개 점포", "점포 평균"] if k in response],
            "pass": has_per_store,
        }
    )

    # Check 6: L3 numeric_sanity evaluator — done.quality_flags 에 warning 없어야 PASS
    warn_flags = [
        f
        for f in (done_payload.get("quality_flags") or [])
        if f.get("severity") == "warning"
    ]
    v.checks.append(
        {
            "rule": "numeric_sanity warning 부재",
            "expected": "severity=warning 0건",
            "hits": [f.get("rule") for f in warn_flags],
            "pass": not warn_flags,
        }
    )

    v.pass_count = sum(1 for c in v.checks if c["pass"])
    v.fail_count = sum(1 for c in v.checks if not c["pass"])
    return v


def write_reports(verdicts: list[Verdict], out_dir: Path) -> None:
    summary = ["# Trust Eval — 2026-04-24", ""]
    summary.append("| 상권 | 유형 | DB 월매출 | 검증 통과 | 판정 |")
    summary.append("|---|---|---:|---:|:---:|")
    for v in verdicts:
        monthly_억 = v.ground.monthly_sales_won / 1e8
        summary.append(
            f"| {v.district} | {v.ground.district_type} | {monthly_억:,.0f}억 | "
            f"{v.pass_count}/{v.pass_count + v.fail_count} | {v.verdict} |"
        )
    summary.append("")
    total = sum(v.pass_count for v in verdicts)
    total_max = sum(v.pass_count + v.fail_count for v in verdicts)
    summary.append(f"**Overall**: {total}/{total_max} checks passed")

    (out_dir / "summary.md").write_text("\n".join(summary), encoding="utf-8")

    per_lines = ["# Per-district details", ""]
    for v in verdicts:
        per_lines.append(f"## {v.district} ({v.ground.district_code}) — {v.verdict}")
        per_lines.append("")
        per_lines.append(f"- district_type: {v.ground.district_type}")
        per_lines.append(f"- DB 월매출: {v.ground.monthly_sales_won:,} 원")
        per_lines.append(f"- DB 점포 수: {v.ground.store_count}")
        per_lines.append(f"- DB 폐업률: {v.ground.close_rate_pct}")
        per_lines.append(f"- DB 일평균 유동인구: {v.ground.floating_pop_daily_avg:,}")
        per_lines.append(f"- sent: `{v.sent_message}`")
        per_lines.append("")
        per_lines.append("| 규칙 | 기대 | 실측 | 판정 |")
        per_lines.append("|---|---|---|:---:|")
        for c in v.checks:
            hits = ", ".join(str(h) for h in c.get("hits", []))[:120]
            per_lines.append(
                f"| {c['rule']} | {c['expected']} | {hits or '(미탐)'} | {'✅' if c['pass'] else '❌'} |"
            )
        per_lines.append("")
        per_lines.append(f"**응답 본문** (truncated 1200자):")
        per_lines.append("")
        per_lines.append("```")
        per_lines.append(v.response_text[:1200].replace("\n", " "))
        per_lines.append("```")
        per_lines.append("")
        per_lines.append(f"**추출 수치 (top 15)**: {v.extracted_numbers[:15]}")
        per_lines.append("")
    (out_dir / "per-district.md").write_text("\n".join(per_lines), encoding="utf-8")


def preflight_trace() -> None:
    """Abort the trust eval if Langfuse tracing is inactive (done.trace_id missing)."""
    if not REQUIRE_TRACE:
        print("[trust-eval] preflight skipped (REQUIRE_TRACE=0)", file=sys.stderr)
        return
    session_id = f"trust-preflight-{uuid.uuid4().hex[:8]}"
    probe_raw = Path("/tmp") / f"{session_id}.sse"
    try:
        _, done = send_chat("강남역 요약", session_id, probe_raw)
    except Exception as e:
        print(f"[trust-eval] preflight FAIL — /api/chat unreachable: {e}", file=sys.stderr)
        sys.exit(2)
    finally:
        try:
            probe_raw.unlink(missing_ok=True)
        except Exception:
            pass
    if not done.get("trace_id"):
        print(
            "[trust-eval] preflight FAIL — done event missing trace_id.\n"
            "  Langfuse tracing inactive. Abort to avoid untracked LLM cost.\n"
            "  See docs/plan/infra/langfuse-cost-coverage-fix-2026-04-24.md\n"
            "  Override: REQUIRE_TRACE=0",
            file=sys.stderr,
        )
        sys.exit(3)
    print(f"[trust-eval] preflight OK — trace_id={done['trace_id'][:16]}…", file=sys.stderr)


def verify_target_codes() -> None:
    """Drift guard — fail fast if hardcoded ground-truth codes no longer match
    the live districts table. See memory/feedback_eval_district_code_hardcode.md
    """
    if os.environ.get("SKIP_CODE_VERIFY") == "1":
        return
    pairs = [(name, code) for name, code, _ in TARGETS]
    try:
        from scripts.eval.verify_district_codes import verify_codes
    except ImportError:
        # Allow trust eval to run when called from a layout without the
        # `scripts` package on sys.path. Falls back to skip-with-warning.
        print("[trust-eval] verify_district_codes import skipped", file=sys.stderr)
        return
    verify_codes(pairs)


def main() -> int:
    preflight_trace()
    verify_target_codes()
    date = dt.date.today().isoformat()
    out_dir = Path("docs/qa/runs") / f"trust-eval-{date}"
    out_dir.mkdir(parents=True, exist_ok=True)

    verdicts: list[Verdict] = []
    for name, code, dtype in TARGETS:
        print(f"[trust-eval] {name} ({code}) ...", file=sys.stderr)
        v = check_district(name, code, dtype, out_dir)
        verdicts.append(v)
        print(f"  {v.verdict} ({v.pass_count}/{v.pass_count + v.fail_count})", file=sys.stderr)

    write_reports(verdicts, out_dir)
    print(f"reports → {out_dir}", file=sys.stderr)
    return 0 if all(v.verdict == "PASS" for v in verdicts) else 1


if __name__ == "__main__":
    sys.exit(main())
