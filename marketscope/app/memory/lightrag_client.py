"""LightRAG 클라이언트 (Phase 2 스텁)."""

from __future__ import annotations

from typing import Any, Optional


class LightRAGClient:
    """Phase 2 스텁."""

    async def query(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        return []

    async def insert(self, content: str, metadata: Optional[dict[str, Any]] = None) -> None:
        pass
