"""DB drift guard for eval ground-truth district codes.

매 실행마다 (name, code) 쌍이 DB 와 여전히 일치하는지 확인. seed 덤프 변경
또는 ETL 재적재 시 district_code 재할당 가능성에 대한 가드.

사용법:
    from scripts.eval.verify_district_codes import verify_codes
    verify_codes([
        ("강남역", "3120189"),
        ("서울역", "3120043"),
    ])  # raises SystemExit on mismatch

Memory: feedback_eval_district_code_hardcode.md
"""

from __future__ import annotations

import subprocess
import sys

DB_CONTAINER = "catchment-area-analysis-db-1"
DB_USER = "marketscope"
DB_NAME = "marketscope"


def _psql(sql: str) -> str:
    cmd = [
        "docker", "exec", DB_CONTAINER, "psql", "-U", DB_USER, "-d", DB_NAME,
        "-t", "-A", "-F", "|", "-c", sql,
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding="utf-8")
    return out.stdout.strip()


def verify_codes(pairs: list[tuple[str, str]]) -> None:
    """Verify each (name, expected_code) pair against the live districts table.

    상권 이름이 prefix-unique 한 경우만 검증 가능 (e.g. "강남역" → 다수 매칭).
    여러 row 가 매칭되는 경우엔 expected_code 가 그 중 하나에 포함되는지만 본다.
    """
    failures: list[str] = []
    for name, expected in pairs:
        # name 의 첫 토큰(괄호/공백 분리) 으로 prefix 검색
        prefix = name.split("(")[0].split()[0]
        rows = _psql(
            f"SELECT district_code, district_name, district_type FROM districts "
            f"WHERE district_name LIKE '{prefix}%' "
            f"ORDER BY district_type, district_code"
        )
        codes = []
        for line in rows.splitlines():
            parts = line.split("|")
            if len(parts) >= 1:
                codes.append(parts[0])
        if expected not in codes:
            failures.append(
                f"  - {name!r} expected={expected!r} but DB rows for prefix {prefix!r} = {codes[:5]}"
            )

    if failures:
        sys.stderr.write("[verify_district_codes] DRIFT detected:\n")
        for f in failures:
            sys.stderr.write(f + "\n")
        sys.stderr.write(
            "Update the eval ground-truth or re-seed the DB. "
            "See memory/feedback_eval_district_code_hardcode.md\n"
        )
        raise SystemExit(2)


if __name__ == "__main__":
    pairs = [
        ("강남역", "3120189"),
        ("서울역", "3120043"),
        ("홍대입구역(홍대)", "3120103"),
        ("성수역", "3120052"),
        ("건대입구역(건대)", "3120053"),
        ("명동(명동거리)", "3120028"),
    ]
    verify_codes(pairs)
    print("OK — all ground-truth codes still match.")
