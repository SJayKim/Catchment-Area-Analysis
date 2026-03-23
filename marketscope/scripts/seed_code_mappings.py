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

from marketscope_common.config import get_settings
from marketscope_common.db.models import CodeMapping, District, UnitPrice, StartupCost
from marketscope_common.db.session import get_session_factory

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
# 업종 소분류 (SEMAS 기준)
# ---------------------------------------------------------------------------
INDUSTRY_SMALL = [
    # (code, name, parent_code, level)
    # 카페/커피
    ("Q05A01", "커피전문점/카페", "Q05", 3),
    ("Q05A02", "제과점", "Q05", 3),
    ("Q05A03", "아이스크림/빙수", "Q05", 3),
    # 한식
    ("Q01A01", "백반/한정식", "Q01", 3),
    ("Q01A02", "육류/고기", "Q01", 3),
    ("Q01A03", "해물/생선", "Q01", 3),
    ("Q01A04", "국밥/해장국", "Q01", 3),
    # 기타 외식
    ("Q06A01", "햄버거", "Q06", 3),
    ("Q07A01", "치킨전문점", "Q07", 3),
    ("Q08A01", "김밥/분식", "Q08", 3),
    ("Q09A01", "피자전문점", "Q09", 3),
    ("Q12A01", "호프/맥주", "Q12", 3),
    # 소매
    ("D01A01", "편의점", "D01", 3),
    ("D14A01", "화장품전문점", "D14", 3),
    # 서비스
    ("R01A01", "미용실", "R01", 3),
    ("N01A01", "네일아트", "N01", 3),
    ("N05A01", "반려동물용품", "N05", 3),
    # 여가
    ("L01A01", "PC방", "L01", 3),
    ("L05A01", "헬스클럽", "L05", 3),
    # 학원
    ("F01A01", "입시/보습학원", "F01", 3),
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

    # 소분류
    for code, name, parent_code, level in INDUSTRY_SMALL:
        parent = next((n for c, n, pc, _ in INDUSTRY_COMMON if c == parent_code), None)
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
        # (district_code, name, type, gu, dong, lat, lng, admin_dong_code)
        ("3110001", "강남역", "D", "강남구", "역삼1동", 37.4979, 127.0276, "1168010100"),
        ("3110002", "신논현역", "D", "강남구", "역삼1동", 37.5046, 127.0250, "1168010100"),
        ("3110003", "삼성역", "D", "강남구", "삼성1동", 37.5089, 127.0630, "1168010500"),
        ("3120001", "홍대입구역", "D", "마포구", "서교동", 37.5571, 126.9244, "1144012700"),
        ("3120002", "합정역", "D", "마포구", "합정동", 37.5496, 126.9139, "1144011500"),
        ("3130001", "이태원역", "G", "용산구", "이태원1동", 37.5345, 126.9946, "1117011100"),
        ("3140001", "건대입구역", "D", "광진구", "화양동", 37.5404, 127.0695, "1121510500"),
        ("3150001", "신촌역", "D", "서대문구", "창천동", 37.5554, 126.9367, "1141010700"),
        ("3160001", "종로3가", "D", "종로구", "종로3가동", 37.5710, 126.9920, "1111015000"),
        ("3170001", "명동역", "G", "중구", "명동", 37.5609, 126.9862, "1114015000"),
        ("3180001", "여의도역", "D", "영등포구", "여의도동", 37.5216, 126.9242, "1156010300"),
        ("3190001", "성수역", "D", "성동구", "성수1가1동", 37.5445, 127.0558, "1120011100"),
        ("3200001", "잠실역", "D", "송파구", "잠실6동", 37.5133, 127.1001, "1171011500"),
    ]
    count = 0
    for code, name, dtype, gu, dong, lat, lng, adm_dong in samples:
        values = dict(
            district_code=code,
            district_name=name,
            district_type=dtype,
            city_name="서울특별시",
            gu_name=gu,
            dong_name=dong,
            center_lat=lat,
            center_lng=lng,
            admin_dong_code=adm_dong,
            is_active=True,
        )
        stmt = pg_insert(District).values(**values).on_conflict_do_update(
            index_elements=["district_code"],
            set_={k: v for k, v in values.items() if k != "district_code"},
        )
        await session.execute(stmt)
        count += 1
    return count


async def seed_unit_prices(session) -> int:
    """업종별 객단가 시드 데이터."""
    data = [
        # (industry_code, industry_name, avg, min, max, source, year)
        ("Q05A01", "커피전문점/카페", 5500, 3000, 8000, "시장조사", 2025),
        ("Q01A01", "백반/한정식", 9000, 7000, 13000, "시장조사", 2025),
        ("Q01A02", "육류/고기", 25000, 15000, 45000, "시장조사", 2025),
        ("Q07A01", "치킨전문점", 18000, 15000, 23000, "시장조사", 2025),
        ("Q09A01", "피자전문점", 22000, 15000, 35000, "시장조사", 2025),
        ("Q08A01", "김밥/분식", 6000, 4000, 9000, "시장조사", 2025),
        ("Q06A01", "햄버거", 8500, 5000, 13000, "시장조사", 2025),
        ("Q12A01", "호프/맥주", 15000, 8000, 25000, "시장조사", 2025),
        ("D01A01", "편의점", 5000, 2000, 10000, "시장조사", 2025),
        ("R01A01", "미용실", 25000, 10000, 50000, "시장조사", 2025),
        ("N01A01", "네일아트", 35000, 15000, 60000, "시장조사", 2025),
        ("L05A01", "헬스클럽", 80000, 50000, 150000, "시장조사/월회비", 2025),
    ]
    count = 0
    for code, name, avg_, min_, max_, src, yr in data:
        stmt = pg_insert(UnitPrice).values(
            industry_code=code,
            industry_name=name,
            avg_unit_price=avg_,
            min_unit_price=min_,
            max_unit_price=max_,
            source=src,
            reference_year=yr,
        ).on_conflict_do_nothing(constraint="uq_unit_price")
        await session.execute(stmt)
        count += 1
    return count


async def seed_startup_costs(session) -> int:
    """업종별 창업비용 시드 데이터."""
    data = [
        # (code, name, size_sqm, interior, equipment, deposit, rent, premium, etc, total_min, total_max, source, year)
        ("Q05A01", "커피전문점/카페", 33, 25000000, 20000000, 30000000, 2000000, 30000000, 5000000, 80000000, 150000000, "소상공인시장진흥공단", 2025),
        ("Q01A01", "백반/한정식", 50, 30000000, 25000000, 40000000, 2500000, 20000000, 5000000, 80000000, 160000000, "소상공인시장진흥공단", 2025),
        ("Q01A02", "육류/고기", 66, 50000000, 30000000, 50000000, 3000000, 50000000, 10000000, 150000000, 280000000, "소상공인시장진흥공단", 2025),
        ("Q07A01", "치킨전문점", 33, 15000000, 15000000, 20000000, 1500000, 15000000, 8000000, 50000000, 100000000, "프랜차이즈정보공개서", 2025),
        ("Q09A01", "피자전문점", 40, 20000000, 18000000, 25000000, 1800000, 20000000, 8000000, 60000000, 120000000, "프랜차이즈정보공개서", 2025),
        ("Q08A01", "김밥/분식", 26, 12000000, 10000000, 15000000, 1200000, 10000000, 5000000, 40000000, 80000000, "시장조사", 2025),
        ("D01A01", "편의점", 33, 5000000, 5000000, 30000000, 2000000, 20000000, 15000000, 50000000, 120000000, "프랜차이즈정보공개서", 2025),
        ("R01A01", "미용실", 33, 20000000, 8000000, 20000000, 1500000, 15000000, 5000000, 50000000, 100000000, "시장조사", 2025),
        ("N01A01", "네일아트", 20, 10000000, 5000000, 15000000, 1000000, 10000000, 3000000, 30000000, 60000000, "시장조사", 2025),
        ("L05A01", "헬스클럽", 165, 80000000, 50000000, 100000000, 5000000, 30000000, 20000000, 200000000, 400000000, "시장조사", 2025),
    ]
    count = 0
    for code, name, size, interior, equip, dep, rent, prem, etc_, tmin, tmax, src, yr in data:
        stmt = pg_insert(StartupCost).values(
            industry_code=code,
            industry_name=name,
            size_sqm=size,
            interior_cost=interior,
            equipment_cost=equip,
            deposit=dep,
            monthly_rent=rent,
            premium=prem,
            etc_cost=etc_,
            total_min=tmin,
            total_max=tmax,
            source=src,
            reference_year=yr,
        ).on_conflict_do_nothing(constraint="uq_startup_cost")
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

            n_prices = await seed_unit_prices(session)
            logger.info(f"객단가 {n_prices}건 적재 완료")

            n_costs = await seed_startup_costs(session)
            logger.info(f"창업비용 {n_costs}건 적재 완료")

            await session.commit()
            logger.info("=== 시드 완료 ===")
        except Exception:
            await session.rollback()
            logger.exception("시드 실패")
            raise


if __name__ == "__main__":
    asyncio.run(main())
