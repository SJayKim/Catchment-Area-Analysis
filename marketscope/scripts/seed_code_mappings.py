"""코드 매핑 및 기초 데이터 시드 스크립트.

사용법:
    # DB 컨테이너가 실행 중인 상태에서
    cd marketscope
    python -m scripts.seed_code_mappings
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import get_settings
from app.db.models import CodeMapping, District
from app.db.session import get_session_factory

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ---------------------------------------------------------------------------
# 서울 25개 구 목록
# ---------------------------------------------------------------------------
SEOUL_GU_LIST = [
    "강남구", "강동구", "강북구", "강서구", "관악구",
    "광진구", "구로구", "금천구", "노원구", "도봉구",
    "동대문구", "동작구", "마포구", "서대문구", "서초구",
    "성동구", "성북구", "송파구", "양천구", "영등포구",
    "용산구", "은평구", "종로구", "중구", "중랑구",
]

# ---------------------------------------------------------------------------
# 업종 대분류 (SEMAS 기준 8개)
# ---------------------------------------------------------------------------
INDUSTRY_LARGE = [
    ("Q", "외식업", 1),
    ("R", "서비스업", 1),
    ("D", "소매업", 1),
    ("N", "생활서비스업", 1),
    ("F", "학문/교육", 1),
    ("L", "여가/오락", 1),
    ("S", "부동산", 1),
    ("P", "숙박업", 1),
]

# ---------------------------------------------------------------------------
# 주요 업종 중분류 / 소분류 일부 (자주 사용되는 업종)
# ---------------------------------------------------------------------------
INDUSTRY_COMMON = [
    # (code, name, parent_code, level)
    ("Q01", "한식", "Q", 2),
    ("Q02", "중식", "Q", 2),
    ("Q03", "일식", "Q", 2),
    ("Q04", "양식", "Q", 2),
    ("Q05", "제과/카페", "Q", 2),
    ("Q06", "패스트푸드", "Q", 2),
    ("Q07", "치킨", "Q", 2),
    ("Q08", "분식", "Q", 2),
    ("Q09", "피자", "Q", 2),
    ("Q12", "호프/주점", "Q", 2),
    ("D01", "편의점", "D", 2),
    ("D05", "슈퍼마켓", "D", 2),
    ("D10", "의류", "D", 2),
    ("D14", "화장품", "D", 2),
    ("D20", "의약품", "D", 2),
    ("R01", "미용실", "R", 2),
    ("R02", "세탁소", "R", 2),
    ("R10", "부동산중개", "R", 2),
    ("N01", "네일/피부관리", "N", 2),
    ("N05", "반려동물", "N", 2),
    ("L01", "PC방", "L", 2),
    ("L02", "노래방", "L", 2),
    ("L05", "헬스/피트니스", "L", 2),
    ("F01", "학원", "F", 2),
    ("P01", "모텔/여관", "P", 2),
    ("P02", "호텔", "P", 2),
]

# ---------------------------------------------------------------------------
# 상권 유형 코드
# ---------------------------------------------------------------------------
DISTRICT_TYPES = [
    ("district_type", "A", "골목상권"),
    ("district_type", "D", "발달상권"),
    ("district_type", "R", "전통시장"),
    ("district_type", "G", "관광특구"),
]


async def seed_industry_codes(session) -> int:
    """업종코드 시드 데이터 적재."""
    count = 0

    # 대분류
    for code, name, level in INDUSTRY_LARGE:
        stmt = pg_insert(CodeMapping).values(
            mapping_type="industry",
            code=code,
            name=name,
            level=level,
            is_active=True,
        ).on_conflict_do_nothing(constraint="uq_code_mapping")
        await session.execute(stmt)
        count += 1

    # 중분류
    for code, name, parent_code, level in INDUSTRY_COMMON:
        parent = next((n for c, n, _ in INDUSTRY_LARGE if c == parent_code), None)
        stmt = pg_insert(CodeMapping).values(
            mapping_type="industry",
            code=code,
            name=name,
            parent_code=parent_code,
            parent_name=parent,
            level=level,
            is_active=True,
        ).on_conflict_do_nothing(constraint="uq_code_mapping")
        await session.execute(stmt)
        count += 1

    # 구별 코드 (admin_dong 기반 매핑)
    for idx, gu in enumerate(SEOUL_GU_LIST, start=1):
        gu_code = f"11{idx:03d}0"  # 서울 구 코드 형식
        stmt = pg_insert(CodeMapping).values(
            mapping_type="admin_dong",
            code=gu_code,
            name=gu,
            parent_code="11",
            parent_name="서울특별시",
            level=1,
            is_active=True,
        ).on_conflict_do_nothing(constraint="uq_code_mapping")
        await session.execute(stmt)
        count += 1

    # 상권 유형 코드
    for mapping_type, code, name in DISTRICT_TYPES:
        stmt = pg_insert(CodeMapping).values(
            mapping_type=mapping_type,
            code=code,
            name=name,
            is_active=True,
        ).on_conflict_do_nothing(constraint="uq_code_mapping")
        await session.execute(stmt)
        count += 1

    return count


async def seed_sample_districts(session) -> int:
    """Phase 1 허용 상권 샘플 데이터 적재 (테스트용)."""
    samples = [
        # (district_code, name, type, gu, dong, lat, lng)
        ("3110001", "강남역", "D", "강남구", "역삼1동", 37.4979, 127.0276),
        ("3110002", "신논현역", "D", "강남구", "역삼1동", 37.5046, 127.0250),
        ("3110003", "삼성역", "D", "강남구", "삼성1동", 37.5089, 127.0630),
        ("3120001", "홍대입구역", "D", "마포구", "서교동", 37.5571, 126.9244),
        ("3120002", "합정역", "D", "마포구", "합정동", 37.5496, 126.9139),
        ("3130001", "이태원역", "G", "용산구", "이태원1동", 37.5345, 126.9946),
        ("3140001", "건대입구역", "D", "광진구", "화양동", 37.5404, 127.0695),
        ("3150001", "신촌역", "D", "서대문구", "창천동", 37.5554, 126.9367),
        ("3160001", "종로3가", "D", "종로구", "종로3가동", 37.5710, 126.9920),
        ("3170001", "명동역", "G", "중구", "명동", 37.5609, 126.9862),
        ("3180001", "여의도역", "D", "영등포구", "여의도동", 37.5216, 126.9242),
        ("3190001", "성수역", "D", "성동구", "성수1가1동", 37.5445, 127.0558),
        ("3200001", "잠실역", "D", "송파구", "잠실6동", 37.5133, 127.1001),
    ]
    count = 0
    for code, name, dtype, gu, dong, lat, lng in samples:
        stmt = pg_insert(District).values(
            district_code=code,
            district_name=name,
            district_type=dtype,
            city_name="서울특별시",
            gu_name=gu,
            dong_name=dong,
            center_lat=lat,
            center_lng=lng,
            is_active=True,
        ).on_conflict_do_nothing(index_elements=["district_code"])
        await session.execute(stmt)
        count += 1
    return count


async def main():
    logger.info("=== MarketScope 코드 매핑 시드 시작 ===")

    factory = get_session_factory()
    async with factory() as session:
        try:
            n_codes = await seed_industry_codes(session)
            logger.info(f"코드 매핑 {n_codes}건 적재 완료")

            n_districts = await seed_sample_districts(session)
            logger.info(f"샘플 상권 {n_districts}건 적재 완료")

            await session.commit()
            logger.info("=== 시드 완료 ===")
        except Exception:
            await session.rollback()
            logger.exception("시드 실패")
            raise


if __name__ == "__main__":
    asyncio.run(main())
