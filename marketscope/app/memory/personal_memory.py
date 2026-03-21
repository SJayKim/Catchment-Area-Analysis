"""PersonalMemory - PostgreSQL 기반 사용자 이력 메모리."""

from __future__ import annotations

from typing import Any, Optional

from app.logging_config import get_logger

logger = get_logger("memory.personal")


class PersonalMemory:
    """사용자별 분석 이력과 선호도를 저장한다.

    Phase 2에서는 인메모리로 동작하며,
    PostgreSQL 연동 시 AnalysisSession 테이블과 통합된다.
    """

    def __init__(self, db_session: Any = None) -> None:
        self._db = db_session
        self._fallback: dict[str, list[dict[str, Any]]] = {}

    async def store_analysis_history(
        self,
        user_id: str,
        session_id: str,
        location: str,
        industry: str,
        overall_score: float,
        overall_grade: str,
        summary: str,
    ) -> None:
        """분석 이력을 저장한다."""
        entry = {
            "session_id": session_id,
            "location": location,
            "industry": industry,
            "overall_score": overall_score,
            "overall_grade": overall_grade,
            "summary": summary,
        }

        if self._db:
            # PostgreSQL AnalysisSession 테이블에 저장
            logger.info("분석 이력 DB 저장: user=%s, session=%s", user_id, session_id)
            # TODO: SQLAlchemy ORM 연동
        else:
            self._fallback.setdefault(user_id, []).append(entry)

    async def get_history(
        self,
        user_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """사용자의 분석 이력을 조회한다."""
        if self._db:
            # TODO: SQLAlchemy ORM 조회
            return []

        return self._fallback.get(user_id, [])[-limit:]

    async def get_preferences(
        self,
        user_id: str,
    ) -> dict[str, Any]:
        """사용자 선호도를 반환한다 (자주 분석하는 지역/업종)."""
        history = await self.get_history(user_id, limit=50)
        if not history:
            return {}

        locations: dict[str, int] = {}
        industries: dict[str, int] = {}
        for h in history:
            loc = h.get("location", "")
            ind = h.get("industry", "")
            if loc:
                locations[loc] = locations.get(loc, 0) + 1
            if ind:
                industries[ind] = industries.get(ind, 0) + 1

        return {
            "frequent_locations": sorted(locations.items(), key=lambda x: -x[1])[:5],
            "frequent_industries": sorted(industries.items(), key=lambda x: -x[1])[:5],
            "total_analyses": len(history),
        }
