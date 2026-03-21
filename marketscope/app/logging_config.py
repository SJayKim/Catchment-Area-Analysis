"""구조화된 로깅 설정."""

from __future__ import annotations

import logging
import sys
from typing import Any


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = f"{record.asctime} [{record.levelname}] {record.name}: {record.getMessage()}"
        extra: dict[str, Any] = getattr(record, "extra", {})
        if extra:
            pairs = " ".join(f"{k}={v}" for k, v in extra.items())
            base = f"{base} | {pairs}"
        return base


def setup_logging(level: str = "DEBUG") -> None:
    root = logging.getLogger("marketscope")
    root.setLevel(getattr(logging, level.upper(), logging.DEBUG))

    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            StructuredFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
        root.addHandler(handler)


def get_agent_logger(agent_name: str) -> logging.Logger:
    return logging.getLogger(f"marketscope.agents.{agent_name}")


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"marketscope.{name}")
