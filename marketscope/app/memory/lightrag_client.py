"""LightRAG 클라이언트 - 상권 지식 그래프 + RAG 통합."""

from __future__ import annotations

from typing import Any, Optional

from app.logging_config import get_logger

logger = get_logger("memory.lightrag")


class LightRAGClient:
    """상권 특성, 뉴스, 규제 등 도메인 지식을 저장하고 검색한다.

    Phase 2에서는 인메모리 키워드 매칭으로 동작하며,
    추후 LightRAG 라이브러리 + NetworkX 그래프 스토어로 교체된다.
    """

    def __init__(self, settings: Optional[Any] = None) -> None:
        self._store: list[dict[str, Any]] = []
        self._initialized = False

    async def initialize(self) -> None:
        """LightRAG 인덱스 초기화."""
        self._initialized = True
        logger.info("LightRAG 클라이언트 초기화 완료 (인메모리 모드)")

    async def query(
        self,
        query: str,
        mode: str = "hybrid",
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """지식 그래프에서 관련 정보를 검색한다.

        Args:
            query: 검색 쿼리
            mode: 검색 모드 (naive/local/global/hybrid)
            top_k: 반환할 최대 결과 수
        """
        if not self._store:
            return []

        # 인메모리 키워드 매칭
        query_tokens = set(query.lower().split())
        scored_results = []

        for entry in self._store:
            content = entry.get("content", "").lower()
            tags = set(entry.get("tags", []))
            # 키워드 매칭 점수
            content_tokens = set(content.split())
            overlap = len(query_tokens & content_tokens) + len(query_tokens & tags)
            if overlap > 0:
                scored_results.append((overlap, entry))

        scored_results.sort(key=lambda x: -x[0])
        return [entry for _, entry in scored_results[:top_k]]

    async def insert(
        self,
        content: str,
        entity_type: str = "general",
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """지식 그래프에 정보를 삽입한다."""
        entry = {
            "content": content,
            "entity_type": entity_type,
            "tags": [t.lower() for t in (tags or [])],
            "metadata": metadata or {},
        }
        self._store.append(entry)
        logger.debug("LightRAG 삽입: type=%s, tags=%s", entity_type, tags)

    async def insert_district_profile(
        self,
        district_name: str,
        characteristics: str,
        tags: Optional[list[str]] = None,
    ) -> None:
        """상권 프로필을 삽입한다."""
        await self.insert(
            content=f"상권: {district_name}. {characteristics}",
            entity_type="district_profile",
            tags=[district_name.lower()] + (tags or []),
        )

    async def insert_news(
        self,
        title: str,
        content: str,
        source: str,
        tags: Optional[list[str]] = None,
    ) -> None:
        """뉴스/트렌드 정보를 삽입한다."""
        await self.insert(
            content=f"[{source}] {title}: {content}",
            entity_type="news",
            tags=tags or [],
            metadata={"source": source},
        )

    async def insert_regulation(
        self,
        regulation_name: str,
        content: str,
        industry: str,
        tags: Optional[list[str]] = None,
    ) -> None:
        """규제 정보를 삽입한다."""
        await self.insert(
            content=f"규제: {regulation_name}. {content}",
            entity_type="regulation",
            tags=[industry.lower()] + (tags or []),
        )

    @property
    def size(self) -> int:
        return len(self._store)
