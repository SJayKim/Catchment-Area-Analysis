"""Seed category_metadata from existing stores data."""

import logging

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

# 업종명 키워드 → 대분류 매핑
_MAJOR_MAP = {
    "한식": "외식",
    "중식": "외식",
    "일식": "외식",
    "양식": "외식",
    "커피": "외식",
    "카페": "외식",
    "제과": "외식",
    "분식": "외식",
    "패스트": "외식",
    "치킨": "외식",
    "호프": "외식",
    "주점": "외식",
    "의류": "소매",
    "화장품": "소매",
    "편의점": "소매",
    "슈퍼": "소매",
    "약국": "소매",
    "서적": "소매",
    "문구": "소매",
    "미용": "서비스",
    "세탁": "서비스",
    "숙박": "서비스",
    "병원": "서비스",
    "학원": "서비스",
    "부동산": "서비스",
}


async def seed_category_metadata(session_factory: async_sessionmaker[AsyncSession]) -> int:
    """Seed category_metadata table from distinct categories in stores table."""
    from server.models.store import Store

    async with session_factory() as session:
        rows = (await session.execute(select(Store.category_code, Store.category_name).distinct())).all()

        count = 0
        for row in rows:
            major = None
            for kw, cat in _MAJOR_MAP.items():
                if kw in row.category_name:
                    major = cat
                    break
            await session.execute(
                text("""
                INSERT INTO category_metadata (category_code, category_name, major_category)
                VALUES (:code, :name, :major)
                ON CONFLICT (category_code) DO UPDATE SET
                    category_name = EXCLUDED.category_name,
                    major_category = COALESCE(EXCLUDED.major_category, category_metadata.major_category)
            """),
                {"code": row.category_code, "name": row.category_name, "major": major},
            )
            count += 1
        await session.commit()
        logger.info("Seeded %d categories into category_metadata", count)
        return count
