"""Load intent configuration from intents.yaml."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_FLAGS_MAP = {
    "IGNORECASE": re.IGNORECASE,
    "DOTALL": re.DOTALL,
    "MULTILINE": re.MULTILINE,
}


@dataclass
class IntentConfig:
    """Compiled intent patterns and plans loaded from YAML."""

    patterns: dict[str, re.Pattern[str]] = field(default_factory=dict)
    plans: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    non_summary_overrides: re.Pattern[str] = field(default_factory=lambda: re.compile("$^"))
    follow_up_markers: re.Pattern[str] = field(default_factory=lambda: re.compile("$^"))


def _compile_pattern(raw: str, flags_str: str | None = None) -> re.Pattern[str]:
    flags = 0
    if flags_str:
        for f in flags_str.split("|"):
            flags |= _FLAGS_MAP.get(f.strip(), 0)
    return re.compile(raw, flags)


def _parse_plan(raw_plan: list[dict] | None) -> list[dict[str, Any]]:
    if not raw_plan:
        return []
    result = []
    for step in raw_plan:
        result.append(
            {
                "tool_name": step["tool"],
                "args_template": step.get("args", {}),
                "reason": step.get("reason", ""),
                "depends_on": step.get("depends_on", []),
            }
        )
    return result


@lru_cache(maxsize=1)
def load_intent_config() -> IntentConfig:
    """Load and compile intents.yaml. Cached after first call."""
    path = Path(__file__).parent / "intents.yaml"
    raw = yaml.safe_load(path.read_text("utf-8"))

    config = IntentConfig()

    for name, defn in raw.get("intents", {}).items():
        config.patterns[name] = _compile_pattern(defn["pattern"], defn.get("flags"))
        config.plans[name] = _parse_plan(defn.get("plan"))

    # Empty-plan intents (greeting, general, ambiguous)
    for empty_intent in ("general", "ambiguous"):
        if empty_intent not in config.plans:
            config.plans[empty_intent] = []

    if raw.get("non_summary_overrides"):
        config.non_summary_overrides = re.compile(raw["non_summary_overrides"])
    if raw.get("follow_up_markers"):
        config.follow_up_markers = re.compile(raw["follow_up_markers"])

    return config
