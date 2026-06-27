"""Function-calling tool surface for the v2 loop.

Wraps the existing @register_tool domain tools as OpenAI-function-shaped
schemas the model can call, and adds three meta-tools that make the loop
both general and trustworthy:

  resolve_district(name)  — name → code, so open-ended queries work without a
                            pre-selected district (generality)
  compute(expression)     — arithmetic via a safe evaluator, NOT model mental
                            math; result becomes a bound fact (trust)
  abstain(reason)         — first-class "I don't have the data / out of scope"
                            so the model never has to guess (trust)
"""

from __future__ import annotations

import ast
import logging
import operator

from server.agent.tools.data_sources import get_sources_for_tool
from server.agent.tools.registry import get_tool_registry

logger = logging.getLogger(__name__)

# Meta-tool names handled locally (not in the domain registry).
RESOLVE_DISTRICT = "resolve_district"
COMPUTE = "compute"
ABSTAIN = "abstain"


def _str(desc: str) -> dict:
    return {"type": "string", "description": desc}


def tool_schemas() -> list[dict]:
    """OpenAI-function-shaped schemas for bind_tools (works on Anthropic+Gemini)."""
    code = _str("상권 코드 (예: 3120103). 모르면 먼저 resolve_district 로 찾으세요.")
    return [
        {
            "name": RESOLVE_DISTRICT,
            "description": "상권 이름(예: '성수동 카페거리', '홍대')을 상권 코드로 변환. "
            "사용자가 코드 없이 상권명만 말했을 때 가장 먼저 호출하세요.",
            "parameters": {
                "type": "object",
                "properties": {"name": _str("상권 이름")},
                "required": ["name"],
            },
        },
        {
            "name": "get_district_summary",
            "description": "한 상권의 종합 요약(유동인구·매출·점포·Top업종). 단일 상권 개요에 사용.",
            "parameters": {
                "type": "object",
                "properties": {"district_code": code},
                "required": ["district_code"],
            },
        },
        {
            "name": "get_floating_population",
            "description": "유동인구 상세(시간대/성별/연령). 비교 질문에서 각 상권별로 호출하세요.",
            "parameters": {
                "type": "object",
                "properties": {
                    "district_code": code,
                    "quarter": _str("분기(예: 2025Q4). 생략 시 최신."),
                },
                "required": ["district_code"],
            },
        },
        {
            "name": "get_estimated_sales",
            "description": "추정 매출(월 환산). category_code 지정 시 해당 업종.",
            "parameters": {
                "type": "object",
                "properties": {
                    "district_code": code,
                    "category_code": _str("업종 코드(선택)"),
                },
                "required": ["district_code"],
            },
        },
        {
            "name": "get_store_info",
            "description": "점포 현황(점포수/개폐업/프랜차이즈 비율).",
            "parameters": {
                "type": "object",
                "properties": {
                    "district_code": code,
                    "category_code": _str("업종 코드(선택)"),
                },
                "required": ["district_code"],
            },
        },
        {
            "name": "get_store_history",
            "description": "점포 이력 기반 안정성 스코어·생존기간(리스크 분석).",
            "parameters": {
                "type": "object",
                "properties": {"district_code": code},
                "required": ["district_code"],
            },
        },
        {
            "name": "get_population_info",
            "description": "상주/직장 인구.",
            "parameters": {
                "type": "object",
                "properties": {"district_code": code},
                "required": ["district_code"],
            },
        },
        {
            "name": "compare_districts",
            "description": "2~3개 상권 핵심 지표 비교. district_codes 에 코드 배열을 넘기세요.",
            "parameters": {
                "type": "object",
                "properties": {
                    "district_codes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "상권 코드 2~3개",
                    }
                },
                "required": ["district_codes"],
            },
        },
        {
            "name": "recommend_business",
            "description": "상권에 적합한 업종 Top 추천. budget(만원) 선택.",
            "parameters": {
                "type": "object",
                "properties": {
                    "district_code": code,
                    "budget": {"type": "integer", "description": "예산(만원, 선택)"},
                    "preference": _str("선호(선택)"),
                },
                "required": ["district_code"],
            },
        },
        {
            "name": "simulate_revenue",
            "description": "업종 매출 시뮬레이션(p25/평균/p75).",
            "parameters": {
                "type": "object",
                "properties": {
                    "district_code": code,
                    "category_code": _str("업종 코드(선택)"),
                    "unit_price": {"type": "integer", "description": "객단가(원, 선택)"},
                },
                "required": ["district_code"],
            },
        },
        {
            "name": COMPUTE,
            "description": "산술 계산(비율·합·차·증감률 등). 숫자 계산은 암산하지 말고 반드시 "
            "이 도구를 쓰세요. 예: '4106209 / 1412369', '(532-221)/221*100'.",
            "parameters": {
                "type": "object",
                "properties": {"expression": _str("산술식. +,-,*,/,**,괄호만 허용")},
                "required": ["expression"],
            },
        },
        {
            "name": ABSTAIN,
            "description": "데이터가 없거나 서울 외 지역 등 답할 수 없을 때 호출. 추측하지 마세요.",
            "parameters": {
                "type": "object",
                "properties": {"reason": _str("답할 수 없는 이유")},
                "required": ["reason"],
            },
        },
    ]


# --------------------------------------------------------------------------
# Safe arithmetic evaluator for the compute tool (no eval()).
# --------------------------------------------------------------------------

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        return _BIN_OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError("허용되지 않은 식")


def safe_compute(expression: str) -> dict:
    """Evaluate a pure-arithmetic expression. Returns {result} or {error}."""
    try:
        tree = ast.parse(expression, mode="eval")
        value = _eval_node(tree.body)
        return {"expression": expression, "result": value}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"계산 실패: {exc}"}


# --------------------------------------------------------------------------
# Executor
# --------------------------------------------------------------------------


async def execute_fc_tool(name: str, args: dict) -> tuple[dict | None, str | None]:
    """Execute one tool call. Returns (result_dict, error_str)."""
    clean = {k: v for k, v in (args or {}).items() if v is not None}

    if name == COMPUTE:
        result = safe_compute(str(clean.get("expression", "")))
        return (result, result.get("error"))

    if name == ABSTAIN:
        return ({"abstain": True, "reason": clean.get("reason", "")}, None)

    if name == RESOLVE_DISTRICT:
        from server.repositories import get_data_access

        da = get_data_access()
        match = await da.districts.detect_district_by_name(clean.get("name", ""))
        if not match:
            return ({"error": "해당 상권을 찾지 못했습니다."}, "not_found")
        return (
            {"code": match["code"], "name": match.get("name"), "score": match.get("score")},
            None,
        )

    reg = get_tool_registry()
    meta = reg.get(name)
    if not meta:
        return (None, f"Unknown tool: {name}")
    try:
        result = await meta.fn(**clean)
        if isinstance(result, dict) and "error" in result:
            return (result, result["error"])
        return (result if isinstance(result, dict) else {"result": result}, None)
    except Exception as exc:  # noqa: BLE001
        logger.warning("fc tool %s failed: %s", name, exc, exc_info=True)
        return (None, str(exc))


def card_for_tool(name: str, result: dict) -> dict | None:
    """Build a card payload if this tool maps to a card type (and succeeded)."""
    reg = get_tool_registry()
    meta = reg.get(name)
    if not meta or not meta.card_type or not isinstance(result, dict) or "error" in result:
        return None
    data = dict(result)
    sources = get_sources_for_tool(name)
    if sources:
        data["dataSources"] = sources
    return {"card_type": meta.card_type, "data": data}


def labels_for_tool(name: str) -> tuple[str, str]:
    """(progress_label, done_label) for SSE tool/tool_end events."""
    special = {
        RESOLVE_DISTRICT: ("상권 찾는 중...", "상권 확인"),
        COMPUTE: ("계산 중...", "계산 완료"),
        ABSTAIN: ("확인 중...", "확인"),
    }
    if name in special:
        return special[name]
    reg = get_tool_registry()
    meta = reg.get(name)
    if meta:
        return (meta.progress_label, meta.done_label)
    return (f"{name} 실행 중...", f"{name} 완료")
