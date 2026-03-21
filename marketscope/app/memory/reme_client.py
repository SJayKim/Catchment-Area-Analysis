"""ReMe 메모리 클라이언트 (Phase 1 스텁)."""

from __future__ import annotations

from typing import Any, Optional

from app.logging_config import get_logger

logger = get_logger("memory.reme")


class ReMeClient:
    """Phase 1 스텁: 인메모리 저장소 사용."""

    def __init__(self, settings: Optional[Any] = None) -> None:
        self._store: dict[str, list[dict[str, Any]]] = {}

    async def recall(
        self,
        agent_name: str,
        query: str,
        memory_type: str = "long_term",
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        key = f"{agent_name}:{memory_type}"
        return self._store.get(key, [])[:top_k]

    async def store(
        self,
        agent_name: str,
        content: str,
        memory_type: str = "short_term",
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        key = f"{agent_name}:{memory_type}"
        if key not in self._store:
            self._store[key] = []
        self._store[key].append({
            "content": content,
            "metadata": metadata or {},
        })
