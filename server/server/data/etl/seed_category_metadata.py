"""Seed category_metadata from existing stores data."""

import json
import logging
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

# Major-category → 기본 객단가 (원). alembic 002 백필과 동일 값. major 미매핑 카테고리는
# _DEFAULT_UNIT_PRICE 로 채워 default_unit_price 가 NULL 로 남지 않도록 한다 (F09 시뮬레이션).
_UNIT_PRICES: dict[str, int] = {"외식": 12000, "서비스": 25000, "소매": 15000}
_DEFAULT_UNIT_PRICE = 15000

# code → [별칭, ...]. 핵심 ~30종만 정적 큐레이션. 나머지는 카테고리명 + learned_aliases + LLM 위임.
_ALIASES_PATH = Path(__file__).parent / "category_aliases.json"


def _load_aliases() -> dict[str, list[str]]:
    """Load curated category_code → aliases map. Missing/invalid file → no aliases (non-fatal)."""
    try:
        return json.loads(_ALIASES_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.warning("category_aliases.json missing/invalid at %s — seeding without aliases", _ALIASES_PATH)
        return {}


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

    aliases_map = _load_aliases()

    async with session_factory() as session:
        rows = (await session.execute(select(Store.category_code, Store.category_name).distinct())).all()

        count = 0
        for row in rows:
            major = None
            for kw, cat in _MAJOR_MAP.items():
                if kw in row.category_name:
                    major = cat
                    break
            unit_price = _UNIT_PRICES.get(major, _DEFAULT_UNIT_PRICE)
            alias_list = aliases_map.get(row.category_code)
            aliases = ",".join(alias_list) if alias_list else None
            await session.execute(
                text("""
                INSERT INTO category_metadata
                    (category_code, category_name, major_category, default_unit_price, aliases)
                VALUES (:code, :name, :major, :unit_price, :aliases)
                ON CONFLICT (category_code) DO UPDATE SET
                    category_name = EXCLUDED.category_name,
                    major_category = COALESCE(EXCLUDED.major_category, category_metadata.major_category),
                    default_unit_price = EXCLUDED.default_unit_price,
                    aliases = COALESCE(EXCLUDED.aliases, category_metadata.aliases)
            """),
                {
                    "code": row.category_code,
                    "name": row.category_name,
                    "major": major,
                    "unit_price": unit_price,
                    "aliases": aliases,
                },
            )
            count += 1
        await session.commit()
        logger.info("Seeded %d categories into category_metadata", count)
        return count
