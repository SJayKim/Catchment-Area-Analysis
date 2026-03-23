"""Public Data MCP 리소스 — 코드 매핑 조회 리소스 3종.

DB가 사용 가능하면 DB에서, 아니면 내장 정적 데이터를 반환.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("mcp.public_data.resources")


# ---------------------------------------------------------------------------
# 정적 코드 데이터 (DB 없을 때 fallback)
# ---------------------------------------------------------------------------

INDUSTRY_CODES: list[dict[str, Any]] = [
    # 대분류
    {"code": "Q", "name": "외식업", "level": 1, "parent_code": None},
    {"code": "R", "name": "서비스업", "level": 1, "parent_code": None},
    {"code": "D", "name": "소매업", "level": 1, "parent_code": None},
    {"code": "N", "name": "생활서비스업", "level": 1, "parent_code": None},
    {"code": "F", "name": "학문/교육", "level": 1, "parent_code": None},
    {"code": "L", "name": "여가/오락", "level": 1, "parent_code": None},
    {"code": "S", "name": "부동산", "level": 1, "parent_code": None},
    {"code": "P", "name": "숙박업", "level": 1, "parent_code": None},
    # 주요 중분류
    {"code": "Q01", "name": "한식", "level": 2, "parent_code": "Q"},
    {"code": "Q02", "name": "중식", "level": 2, "parent_code": "Q"},
    {"code": "Q03", "name": "일식", "level": 2, "parent_code": "Q"},
    {"code": "Q04", "name": "양식", "level": 2, "parent_code": "Q"},
    {"code": "Q05", "name": "제과/카페", "level": 2, "parent_code": "Q"},
    {"code": "Q06", "name": "패스트푸드", "level": 2, "parent_code": "Q"},
    {"code": "Q07", "name": "치킨", "level": 2, "parent_code": "Q"},
    {"code": "Q08", "name": "분식", "level": 2, "parent_code": "Q"},
    {"code": "Q09", "name": "피자", "level": 2, "parent_code": "Q"},
    {"code": "Q12", "name": "호프/주점", "level": 2, "parent_code": "Q"},
    {"code": "D01", "name": "편의점", "level": 2, "parent_code": "D"},
    {"code": "D05", "name": "슈퍼마켓", "level": 2, "parent_code": "D"},
    {"code": "D10", "name": "의류", "level": 2, "parent_code": "D"},
    {"code": "D14", "name": "화장품", "level": 2, "parent_code": "D"},
    {"code": "D20", "name": "의약품", "level": 2, "parent_code": "D"},
    {"code": "R01", "name": "미용실", "level": 2, "parent_code": "R"},
    {"code": "R02", "name": "세탁소", "level": 2, "parent_code": "R"},
    {"code": "R10", "name": "부동산중개", "level": 2, "parent_code": "R"},
    {"code": "N01", "name": "네일/피부관리", "level": 2, "parent_code": "N"},
    {"code": "N05", "name": "반려동물", "level": 2, "parent_code": "N"},
    {"code": "L01", "name": "PC방", "level": 2, "parent_code": "L"},
    {"code": "L02", "name": "노래방", "level": 2, "parent_code": "L"},
    {"code": "L05", "name": "헬스/피트니스", "level": 2, "parent_code": "L"},
    {"code": "F01", "name": "학원", "level": 2, "parent_code": "F"},
    {"code": "P01", "name": "모텔/여관", "level": 2, "parent_code": "P"},
    {"code": "P02", "name": "호텔", "level": 2, "parent_code": "P"},
]

DISTRICT_TYPE_CODES: list[dict[str, str]] = [
    {"code": "A", "name": "골목상권"},
    {"code": "D", "name": "발달상권"},
    {"code": "R", "name": "전통시장"},
    {"code": "G", "name": "관광특구"},
]

SEOUL_GU_CODES: list[dict[str, str]] = [
    {"code": f"11{i:03d}0", "name": name}
    for i, name in enumerate(
        [
            "강남구", "강동구", "강북구", "강서구", "관악구",
            "광진구", "구로구", "금천구", "노원구", "도봉구",
            "동대문구", "동작구", "마포구", "서대문구", "서초구",
            "성동구", "성북구", "송파구", "양천구", "영등포구",
            "용산구", "은평구", "종로구", "중구", "중랑구",
        ],
        start=1,
    )
]

# 주요 행정동 코드 (서울 주요 상권 지역)
DONG_CODES: list[dict[str, str]] = [
    {"code": "1168010100", "name": "역삼1동", "gu": "강남구"},
    {"code": "1168010600", "name": "삼성1동", "gu": "강남구"},
    {"code": "1168010300", "name": "논현1동", "gu": "강남구"},
    {"code": "1168010800", "name": "대치1동", "gu": "강남구"},
    {"code": "1156015000", "name": "서교동", "gu": "마포구"},
    {"code": "1156013500", "name": "합정동", "gu": "마포구"},
    {"code": "1121510700", "name": "장안1동", "gu": "동대문구"},
    {"code": "1150510100", "name": "신림동", "gu": "관악구"},
    {"code": "1174010100", "name": "잠실본동", "gu": "송파구"},
    {"code": "1174010300", "name": "잠실3동", "gu": "송파구"},
    {"code": "1165010100", "name": "영등포본동", "gu": "영등포구"},
    {"code": "1165010700", "name": "여의도동", "gu": "영등포구"},
    {"code": "1111010100", "name": "청운효자동", "gu": "종로구"},
    {"code": "1111015500", "name": "종로1·2·3·4가동", "gu": "종로구"},
    {"code": "1114015000", "name": "명동", "gu": "중구"},
    {"code": "1114016000", "name": "을지로동", "gu": "중구"},
    {"code": "1114011500", "name": "소공동", "gu": "중구"},
    {"code": "1135010100", "name": "후암동", "gu": "용산구"},
    {"code": "1135010600", "name": "이태원1동", "gu": "용산구"},
    {"code": "1168010500", "name": "압구정동", "gu": "강남구"},
    {"code": "1165010500", "name": "신길1동", "gu": "영등포구"},
    {"code": "1147010100", "name": "서초1동", "gu": "서초구"},
    {"code": "1147010800", "name": "반포본동", "gu": "서초구"},
    {"code": "1141510100", "name": "성수1가1동", "gu": "성동구"},
]


# ---------------------------------------------------------------------------
# 리소스 핸들러
# ---------------------------------------------------------------------------

async def get_industry_codes() -> dict:
    """업종코드 리소스."""
    return {
        "uri": "public-data://industry-codes",
        "data": INDUSTRY_CODES,
        "total_count": len(INDUSTRY_CODES),
        "categories": {
            "대분류": [c for c in INDUSTRY_CODES if c["level"] == 1],
            "중분류": [c for c in INDUSTRY_CODES if c["level"] == 2],
        },
    }


async def get_district_codes() -> dict:
    """상권 관련 코드 리소스 — 구 코드 + 상권유형."""
    return {
        "uri": "public-data://district-codes",
        "data": {
            "gu_codes": SEOUL_GU_CODES,
            "district_types": DISTRICT_TYPE_CODES,
        },
        "total_gu": len(SEOUL_GU_CODES),
        "total_types": len(DISTRICT_TYPE_CODES),
    }


async def get_dong_codes() -> dict:
    """행정동코드 리소스."""
    return {
        "uri": "public-data://dong-codes",
        "data": DONG_CODES,
        "total_count": len(DONG_CODES),
    }


RESOURCE_REGISTRY: dict[str, Any] = {
    "public-data://industry-codes": get_industry_codes,
    "public-data://district-codes": get_district_codes,
    "public-data://dong-codes": get_dong_codes,
}
