"""코드 매퍼 — 행정동↔법정동↔상권코드 변환."""

from __future__ import annotations

import logging
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CodeMapping

logger = logging.getLogger(__name__)


class CodeMapper:
    """코드 매핑 변환기.

    DB의 code_mappings 테이블을 인메모리 캐시로 로드하여
    행정동 ↔ 법정동 ↔ 상권코드 ↔ 업종코드 변환을 수행.
    """

    def __init__(self) -> None:
        self._cache: dict[str, dict[str, CodeMapping]] = {}
        self._loaded = False

    async def load(self, session: AsyncSession) -> None:
        """DB에서 전체 코드 매핑을 인메모리 캐시로 로드."""
        stmt = select(CodeMapping).where(CodeMapping.is_active.is_(True))
        result = await session.execute(stmt)
        mappings = result.scalars().all()

        self._cache.clear()
        for m in mappings:
            if m.mapping_type not in self._cache:
                self._cache[m.mapping_type] = {}
            self._cache[m.mapping_type][m.code] = m

        self._loaded = True
        total = sum(len(v) for v in self._cache.values())
        logger.info(
            "코드 매핑 로드 완료: %d types, %d records",
            len(self._cache), total,
        )

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            raise RuntimeError("CodeMapper.load()를 먼저 호출하세요")

    def get_by_code(self, mapping_type: str, code: str) -> Optional[CodeMapping]:
        """특정 타입/코드 조회."""
        self._ensure_loaded()
        return self._cache.get(mapping_type, {}).get(code)

    def get_name(self, mapping_type: str, code: str) -> Optional[str]:
        """코드 → 이름 변환."""
        m = self.get_by_code(mapping_type, code)
        return m.name if m else None

    def get_all_by_type(self, mapping_type: str) -> list[CodeMapping]:
        """특정 타입의 전체 코드 목록."""
        self._ensure_loaded()
        return list(self._cache.get(mapping_type, {}).values())

    # --- 행정동 ↔ 법정동 ---

    def admin_dong_to_legal_dong(self, admin_dong_code: str) -> Optional[str]:
        """행정동코드 → 법정동코드."""
        m = self.get_by_code("admin_dong", admin_dong_code)
        return m.related_code if m else None

    def legal_dong_to_admin_dong(self, legal_dong_code: str) -> Optional[str]:
        """법정동코드 → 행정동코드."""
        m = self.get_by_code("legal_dong", legal_dong_code)
        return m.related_code if m else None

    # --- 행정동 → 상권코드 ---

    def dong_to_district(self, admin_dong_code: str) -> Optional[str]:
        """행정동코드 → 상권코드 (related_code 경유)."""
        m = self.get_by_code("admin_dong", admin_dong_code)
        return m.related_code if m else None

    def district_to_dong(self, district_code: str) -> Optional[str]:
        """상권코드 → 행정동코드."""
        m = self.get_by_code("district", district_code)
        return m.related_code if m else None

    # --- 업종 코드 ---

    def get_industry_name(self, industry_code: str) -> Optional[str]:
        """업종코드 → 업종명."""
        return self.get_name("industry", industry_code)

    def get_industry_parent(self, industry_code: str) -> Optional[str]:
        """업종 소분류 → 대분류 코드."""
        m = self.get_by_code("industry", industry_code)
        return m.parent_code if m else None

    def search_industry(self, keyword: str) -> list[CodeMapping]:
        """업종명 키워드 검색."""
        self._ensure_loaded()
        result = []
        for m in self._cache.get("industry", {}).values():
            if keyword in (m.name or ""):
                result.append(m)
        return result
