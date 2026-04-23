"""Abstention + attribution helpers for GAP-D.

Goal: when tool results are thin or empty, the Respond node must stop
generating confident prose from LLM priors ("the Seoul F&B close rate is
around 25%...") and either abstain or explicitly flag the gap. This
module ships three pieces:

1. :func:`classify_tool_results` — triage level based on critical fields.
2. :const:`ABSTENTION_PROMPT_ADDENDUM` — extra prompt text injected when
   status is ``partial`` or ``empty``.
3. :func:`scan_unattributed_numbers` — post-hoc regex check that flags
   numeric claims without a tool-attribution tag. Used for structlog
   telemetry today; future iterations can gate on it.
"""

from __future__ import annotations

import re
from typing import Literal

ResultStatus = Literal["full", "partial", "empty"]

# Critical field per tool — when this key is missing/falsy the tool result
# counts as an empty row. Derived from ``_compute_hints`` behaviour in
# ``respond.py`` and the Repository return shapes.
CRITICAL_FIELDS: dict[str, str] = {
    "get_floating_population": "daily_avg",
    "get_estimated_sales": "total_monthly_sales",
    "get_store_info": "total_stores",
    "get_store_history": "benchmarks",
    "get_population_info": "total_population",
    "compare_districts": "districts",
    "recommend_business": "recommendations",
    "get_district_summary": "store_info",
    "estimate_revenue": "monthly_avg",
}


def classify_tool_results(
    tool_results: dict[str, dict],
    tool_errors: dict[str, str] | None = None,
) -> ResultStatus:
    """Triage the Respond node's evidence level.

    - ``empty``: no successful results, or every successful result lacks its
      critical field. LLM should abstain with a fixed template.
    - ``partial``: some critical fields missing or the plan had errors on
      non-critical tools. LLM should mark gaps explicitly.
    - ``full``: every tool that ran produced its critical field.
    """
    if not tool_results:
        return "empty"

    missing = 0
    total = 0
    for name, data in tool_results.items():
        if not isinstance(data, dict) or "error" in data:
            missing += 1
            total += 1
            continue
        critical = CRITICAL_FIELDS.get(name)
        total += 1
        if critical is None:
            continue
        value = data.get(critical)
        if not value and value != 0:
            missing += 1

    if total == 0:
        return "empty"
    if missing == total:
        return "empty"
    if missing > 0 or (tool_errors and any(tool_errors.values())):
        return "partial"
    return "full"


ABSTENTION_PROMPT_ADDENDUM_EMPTY = """\

## ⚠️ 데이터 조회 실패 (중요)
요청하신 분석에 필요한 공공데이터를 조회하지 못했습니다. 아래 문구를
**그대로** 사용하여 답변하고, 구체적 수치나 일반 지식으로 추정하지 마세요.

> "요청하신 상권의 공공데이터를 조회하지 못했습니다. 다른 상권을 선택하시거나 잠시 후 다시 시도해 주세요. 서울 열린데이터 API 일시 장애 가능성이 있습니다."

절대 금지:
- 외부 지식(업계 평균, 뉴스, 추측)을 끌어와 수치를 생성
- "일반적으로 ~% 정도" 같은 추정 표현
- 타 상권 사례로 대체
"""

ABSTENTION_PROMPT_ADDENDUM_PARTIAL = """\

## ⚠️ 일부 데이터 누락
[수집된 데이터] 섹션의 일부 도구 결과에서 핵심 필드가 비어 있습니다.
비어 있는 항목은 **"해당 데이터 없음"** 으로 명시하고, 확보된 지표만으로
분석을 진행하세요. 비어 있는 항목에 대해 임의 수치 추정 금지.
"""

# 각 수치성 주장 뒤에 ``(tool_name)`` 을 붙이도록 지시. 후처리 검증이 이
# 패턴을 기대함.
ATTRIBUTION_PROMPT_RULE = """\

## 수치 주장 출처 표기 (필수)
구체적 수치(원/명/%/억/만/건/개)를 언급할 때마다 바로 뒤에 괄호로 해당
수치가 나온 도구 이름을 붙이세요.

- 올바른 예: "월 추정 매출 5,320억원 `(get_estimated_sales)`"
- 올바른 예: "하루 유동인구 12만 4천명 `(get_floating_population)`"
- 잘못된 예: "업계 평균은 보통 25% 정도입니다" (출처 없음 → 금지)

도구 데이터에 없는 수치는 쓰지 않습니다. 없으면 "해당 데이터 없음" 으로
표기하거나 정성적 설명으로 전환하세요.
"""


# 숫자(콤마/소수 허용) + 단위 패턴. 뒤에 ``(tool_snake_case)`` 가 바로 이어지면
# attribution 적용으로 간주하고 flag 하지 않음.
_NUMERIC_PATTERN = re.compile(
    r"(?P<num>\d[\d,\.]*)\s*(?P<unit>원|명|%|퍼센트|억|만|천|건|개|회|배)"
    r"(?P<tail>[^(\n]{0,6})",
    re.UNICODE,
)
_ATTRIBUTION_TAIL = re.compile(r"^\s*(?:원|명)?\s*\(\s*[a-z_][a-z0-9_]+\s*\)")


def scan_unattributed_numbers(text: str) -> list[str]:
    """Return every unattributed numeric snippet found in ``text``.

    Heuristic: a numeric + unit is considered attributed when immediately
    followed by ``(tool_snake_case)``. The scanner skips trivial numbers in
    list headers ("1위", "3개") when they are inside a short structural
    phrase — those are enumerations, not factual claims.
    """
    violations: list[str] = []
    for match in _NUMERIC_PATTERN.finditer(text):
        tail = match.group("tail")
        if _ATTRIBUTION_TAIL.match(tail):
            continue
        num = match.group("num")
        unit = match.group("unit")
        if unit in ("위", "개") and num in {"1", "2", "3", "4", "5"} and len(num) == 1:
            # Rank suffix or tiny enumeration — ignore.
            continue
        violations.append(f"{num}{unit}")
        if len(violations) >= 25:
            break
    return violations
