"""LLM 비용 계산 스텁.

실제 구현은 agent 서비스의 llm.pricing 모듈에서 제공.
common에서는 기본 폴백만 제공한다.
"""

from __future__ import annotations

from typing import Any

# 기본 가격표 (USD per 1K tokens)
_PRICING: dict[str, dict[str, float]] = {
    "anthropic/claude-sonnet-4-6-20250514": {"prompt": 0.003, "completion": 0.015},
    "anthropic/claude-opus-4-6-20250514": {"prompt": 0.015, "completion": 0.075},
    "gemini/gemini-2.5-flash": {"prompt": 0.00015, "completion": 0.0006},
    "gemini/gemini-2.5-pro": {"prompt": 0.00125, "completion": 0.01},
}

_DEFAULT = {"prompt": 0.002, "completion": 0.01}


def calculate_cost(
    model: str, prompt_tokens: int, completion_tokens: int
) -> dict[str, Any]:
    """LLM 비용을 계산한다."""
    pricing = _PRICING.get(model, _DEFAULT)
    prompt_cost = (prompt_tokens / 1000) * pricing["prompt"]
    completion_cost = (completion_tokens / 1000) * pricing["completion"]
    return {
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "prompt_cost_usd": round(prompt_cost, 6),
        "completion_cost_usd": round(completion_cost, 6),
        "total_cost_usd": round(prompt_cost + completion_cost, 6),
    }
