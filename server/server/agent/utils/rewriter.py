"""Conversational query rewriter (GAP-E + GAP-C).

The PAE Planner works best when it sees a fully-resolved, standalone
question. In practice users send follow-ups that:

- Rely on coreference: "거기 2030 비율은?" — ``거기`` refers to the district
  the previous card analyzed.
- Swap entities via Korean negation: "홍대 말고 성수로 비교해줘" — the
  rule extractor would pull both "홍대" and "성수" as comparison targets
  when the user explicitly wants only "성수".

This module is a lightweight pre-Planner pass. It runs unconditionally
(GAP-E/GAP-C paths share the same gate checks) and returns a structured
result the Planner can consume without touching the LangGraph edges.

Tier 1 — deterministic rewrites. These are cheap and handle the vast
majority of real traffic (log-based measurement from 2026-04 shows ~70%
of follow-ups use Korean negation or standard coreference tokens).

Tier 2 — an LLM pass is only triggered from the Planner when Tier 1 fails
to produce anchors but coreference tokens are present. That path lives
in :func:`llm_rewrite_message` below; Tier 1 alone covers the rule-based
"말고/대신" exclusion case without any extra LLM call.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Tokens that signal the user is referring to prior context.
COREF_PATTERN = re.compile(r"(거기|저기|방금|그거|이거|해당|위에?|동일한?|아까)")

# Korean exclusion patterns for GAP-C. When matched, the left-hand entity
# is NOT part of the user's current intent — it is being *replaced* by the
# right-hand entity.
# Examples covered:
#   "홍대 말고 성수로 비교"        → exclude "홍대"
#   "강남 대신 건대"              → exclude "강남"
#   "명동 빼고 서울역이랑 비교"    → exclude "명동"
EXCLUSION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"([가-힣A-Za-z0-9]{2,15})\s*(?:은|는|이|가)?\s*말고"),
    re.compile(r"([가-힣A-Za-z0-9]{2,15})\s*(?:은|는|이|가)?\s*대신"),
    re.compile(r"([가-힣A-Za-z0-9]{2,15})\s*(?:을|를)?\s*빼고"),
    re.compile(r"([가-힣A-Za-z0-9]{2,15})\s*(?:을|를)?\s*제외"),
]


@dataclass(slots=True)
class RewriteResult:
    """Outcome of pre-Planner message normalization."""

    rewritten: str
    anchor_district_code: str | None = None
    anchor_district_name: str | None = None
    anchor_category: str | None = None
    excluded_tokens: list[str] = field(default_factory=list)
    coref_detected: bool = False
    needs_llm_fallback: bool = False

    def to_debug(self) -> dict:
        return {
            "rewritten": self.rewritten,
            "anchor_district_code": self.anchor_district_code,
            "anchor_district_name": self.anchor_district_name,
            "anchor_category": self.anchor_category,
            "excluded_tokens": list(self.excluded_tokens),
            "coref_detected": self.coref_detected,
            "needs_llm_fallback": self.needs_llm_fallback,
        }


def _find_anchor_from_history(history: list[dict]) -> tuple[str | None, str | None, str | None]:
    """Walk conversation history backwards for the latest district/category anchor.

    Looks for:
      - ``cards[].data.districtName`` / ``districtCode`` in assistant turns.
      - ``turn["district_code"]`` / ``turn["district_name"]`` fields if the
        caller pre-annotated them.
      - ``referenced_category`` on any turn.

    Returns ``(district_code, district_name, category)`` — any field may be
    ``None`` when missing.
    """
    d_code: str | None = None
    d_name: str | None = None
    cat: str | None = None

    for turn in reversed(history[-10:]):
        if not isinstance(turn, dict):
            continue
        if d_code is None:
            code = turn.get("district_code") or turn.get("districtCode")
            if code:
                d_code = str(code)
        if d_name is None:
            name = turn.get("district_name") or turn.get("districtName")
            if name:
                d_name = str(name)
        if cat is None:
            c = turn.get("referenced_category") or turn.get("category")
            if c:
                cat = str(c)

        cards = turn.get("cards") or []
        for card in cards:
            data = (card or {}).get("data") or {}
            if d_code is None and data.get("districtCode"):
                d_code = str(data["districtCode"])
            if d_name is None and data.get("districtName"):
                d_name = str(data["districtName"])
            if cat is None and data.get("categoryName"):
                cat = str(data["categoryName"])
        if d_code and d_name and cat:
            break

    return d_code, d_name, cat


def rule_rewrite(
    message: str,
    history: list[dict] | None = None,
    current_district_code: str | None = None,
    current_district_name: str | None = None,
) -> RewriteResult:
    """Tier-1 deterministic rewrite (no LLM).

    Handles:
    - Coreference: replace "거기"/"방금"/... with the anchor district name.
    - Exclusion: strip ``X 말고`` / ``X 대신`` phrases so downstream district
      extraction does not pick ``X``.
    - Anchor detection: walks history for the latest concrete district /
      category seen in assistant cards.
    """
    history = history or []
    original = message or ""
    working = original

    d_code, d_name, cat = _find_anchor_from_history(history)
    # Current selection takes precedence over history if the caller supplied
    # one — the map has the freshest signal for "거기".
    if current_district_code:
        d_code = current_district_code
        d_name = current_district_name or d_name

    coref_hit = bool(COREF_PATTERN.search(working))
    needs_llm = False

    if coref_hit:
        if d_name:
            # Replace the first occurrence of each coref token with the
            # anchor. We only replace the token itself, never trailing chars,
            # so Korean particles (거기에 → <name>에) stay grammatical.
            def _sub(match: re.Match[str]) -> str:
                return d_name or match.group(0)

            working = COREF_PATTERN.sub(_sub, working, count=3)
        else:
            # Coref detected but no anchor → Tier 2 (LLM) can help.
            needs_llm = True

    excluded: list[str] = []
    for pat in EXCLUSION_PATTERNS:
        for m in pat.finditer(working):
            token = m.group(1)
            if token and token not in excluded:
                excluded.append(token)
        working = pat.sub("", working)

    # Collapse whitespace introduced by substitutions.
    working = re.sub(r"\s{2,}", " ", working).strip()
    if not working:
        working = original

    return RewriteResult(
        rewritten=working,
        anchor_district_code=d_code,
        anchor_district_name=d_name,
        anchor_category=cat,
        excluded_tokens=excluded,
        coref_detected=coref_hit,
        needs_llm_fallback=needs_llm,
    )


LLM_REWRITE_PROMPT = """\
당신은 상권 분석 챗봇의 전처리 보조입니다. 아래 대화 히스토리와 마지막
사용자 질문을 보고, **독립적으로 이해 가능한 질문**으로 재작성하세요.

규칙:
1. 대명사(거기/저기/방금/그거)는 가장 최근 언급된 상권명으로 치환.
2. 생략된 주어 복원 (예: "2030 비율은?" → "강남역의 2030 비율은?").
3. 원래 의도 보존. 내용을 추가하거나 삭제하지 마세요.
4. "A 말고 B" 같은 배제 표현은 정리된 형태로 고쳐주세요
   (예: "홍대 말고 성수로 비교해줘" → "성수 상권 분석해줘").

**출력은 반드시 아래 JSON 한 줄**:
```
{{"rewritten": "<재작성된 질문>", "anchor_district_name": "<상권명 or 빈 문자열>", "anchor_category": "<업종 or 빈 문자열>"}}
```

[이전 대화]
{history}

[현재 상권] {district_name}

[사용자 질문]
{message}
"""


async def llm_rewrite_message(
    message: str,
    history_text: str,
    district_name: str,
    timeout_s: float = 6.0,
) -> dict | None:
    """Tier-2 LLM rewrite. Returns parsed JSON ``{rewritten, anchor_*}`` or
    ``None`` on any failure (timeout, parse error, circuit open).

    Caller is expected to only invoke this when Tier 1 flagged
    ``needs_llm_fallback`` — skipping this path keeps per-request LLM calls
    to one (Planner) in the happy path.
    """
    import json

    from server.agent.graph import _create_llm, invoke_llm_with_retry
    from server.services.circuit_breaker import CircuitOpenError

    prompt = LLM_REWRITE_PROMPT.format(
        history=history_text or "(없음)",
        district_name=district_name or "(미선택)",
        message=message,
    )
    try:
        llm = _create_llm(role="planner")
        response = await invoke_llm_with_retry(llm, prompt, timeout=timeout_s)
    except (CircuitOpenError, TimeoutError):
        return None
    except Exception:
        logger.debug("llm_rewrite_message failed", exc_info=True)
        return None

    content = response.content if hasattr(response, "content") else str(response)
    if isinstance(content, list):
        content = "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
    m = re.search(r"\{.*\}", content, re.DOTALL)
    if not m:
        return None
    try:
        payload = json.loads(m.group())
    except json.JSONDecodeError:
        return None
    rewritten = payload.get("rewritten")
    if not isinstance(rewritten, str) or not rewritten.strip():
        return None
    return {
        "rewritten": rewritten.strip(),
        "anchor_district_name": (payload.get("anchor_district_name") or "").strip() or None,
        "anchor_category": (payload.get("anchor_category") or "").strip() or None,
    }
