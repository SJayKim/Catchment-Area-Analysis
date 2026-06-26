"""0-LLM router: TRIVIAL / SIMPLE / DEEP tier + greeting/out_of_scope short-circuit.

Reuses the legacy rule constants (intents.yaml patterns via load_intent_config) so
the agentic router stays in lock-step with the PAE planner's classification. The
greeting / out_of_scope reply text + suggestions are copied verbatim from the PAE
greeting/clarification nodes for byte-identical TRIVIAL responses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from server.agent.config.intent_loader import load_intent_config

# Greeting fast-path — mirrors chat.py _GREETING_PATTERN (trailing \s*$).
_GREETING = re.compile(
    r"^(안녕하세요|안녕|하이|헬로|hi|hello|반갑습니다|반갑|감사합니다|감사|고마워|ㅎㅇ|좋은\s*아침|좋은\s*저녁)[!?.ㅎㅋ요]*\s*$",
    re.IGNORECASE,
)

_GREETING_TEXT = (
    "안녕하세요! 서울 상권 분석 AI 마켓스코프입니다.\n지도에서 상권을 선택하시거나, 분석할 상권명을 알려주세요!"
)
_GREETING_SUGGESTIONS = ["강남역 상권 분석해줘", "홍대 어때?", "업종 추천해줘", "상권 비교하고 싶어"]

_OUT_OF_SCOPE_TEXT = (
    "현재 마켓스코프는 **서울시 1,650개 상권**만 지원합니다. 서울 외 지역(부산·인천·경기 등)의 "
    "상권 데이터는 아직 제공하지 않습니다. 서울 상권에 대해 알려드릴까요?"
)
_OUT_OF_SCOPE_SUGGESTIONS = ["강남역 상권 요약", "홍대 vs 성수 비교", "명동 창업 추천 업종"]

# Intent labels recognized by eventHandlers.ts for the `plan` event.
_INTENT_ORDER = ("comparison", "simulation", "risk", "recommendation", "category_analysis", "summary")


@dataclass
class RouteDecision:
    tier: str  # "TRIVIAL" | "SIMPLE" | "DEEP"
    intent: str  # plan-event intent label
    response_mode: str  # "greeting_direct" | "clarification_direct" | "tool_assisted"
    text: str = ""
    suggestions: list[str] = field(default_factory=list)


def classify(message: str, district_code: str | None) -> RouteDecision:
    """Pick a tier with zero LLM/tool calls. out_of_scope is checked first (PAE order)."""
    cfg = load_intent_config()
    msg = message.strip()

    if cfg.patterns["out_of_scope"].search(msg):
        return RouteDecision(
            "TRIVIAL",
            "out_of_scope",
            "clarification_direct",
            _OUT_OF_SCOPE_TEXT,
            list(_OUT_OF_SCOPE_SUGGESTIONS),
        )
    if _GREETING.match(msg) or cfg.patterns["greeting"].search(msg):
        return RouteDecision(
            "TRIVIAL",
            "general",
            "greeting_direct",
            _GREETING_TEXT,
            list(_GREETING_SUGGESTIONS),
        )

    intent = _guess_intent(cfg, msg)
    tier = "DEEP" if (intent == "comparison" or cfg.follow_up_markers.search(msg)) else "SIMPLE"
    return RouteDecision(tier, intent, "tool_assisted")


def _guess_intent(cfg, msg: str) -> str:
    for name in _INTENT_ORDER:
        pat = cfg.patterns.get(name)
        if pat and pat.search(msg):
            return name
    return "general"
