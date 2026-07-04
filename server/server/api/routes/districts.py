"""District search and detail API routes."""

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.exc import OperationalError

from server.api.errors import raise_db_unavailable, raise_not_found
from server.repositories import get_data_access
from server.services.cache import get_cache_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["districts"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class DistrictSummary(BaseModel):
    district_code: str
    district_name: str
    district_type: str
    gu_code: str | None = None
    dong_code: str | None = None
    data_quarter: str
    center_lng: float | None = None
    center_lat: float | None = None


class DistrictListResponse(BaseModel):
    total: int
    items: list[DistrictSummary]


class DistrictDetail(BaseModel):
    district_code: str
    district_name: str
    district_type: str
    gu_code: str | None = None
    dong_code: str | None = None
    data_quarter: str
    center_lng: float | None = None
    center_lat: float | None = None
    polygon: dict | None = None  # GeoJSON geometry


class PreviewTopCategory(BaseModel):
    category_code: str | None = None
    category_name: str
    store_count: int
    share_pct: float


class PreviewFloatingPopulation(BaseModel):
    quarter: str | None = None
    daily_total: int | None = None
    prev_quarter_total: int | None = None
    prev_quarter_delta_pct: float | None = None
    peak_hour: int | None = None


class DistrictPreview(BaseModel):
    district_code: str
    district_name: str
    district_type: str
    data_quarter: str
    center_lng: float | None = None
    center_lat: float | None = None
    top_categories: list[PreviewTopCategory]
    floating_population: PreviewFloatingPopulation
    suggested_questions: list[str]


# ---------------------------------------------------------------------------
# Preview — zero-LLM preview endpoint (2026-04-23 Plan: landing-onboarding-feedback)
# ---------------------------------------------------------------------------

# Role → suggested_questions 프리셋. intents.yaml 의 intent 매핑 기반.
# 무호출 안전값 — DB/캐시 실패 시에도 이 값은 정적으로 반환한다.
_SUGGESTED_QUESTIONS_BY_ROLE: dict[str, list[str]] = {
    "owner": [
        "이 상권 유동인구 시간대별로 보여줘",
        "주변 경쟁 점포는 몇 개야?",
        "비슷한 상권이랑 비교해줘",
        "이 상권 리스크는 뭐야?",
        "프랜차이즈 비중은 어때?",
    ],
    "investor": [
        "비슷한 상권 2~3곳이랑 비교해줘",
        "이 상권에서 가장 잘 될 업종은?",
        "시간대별 유동인구 히트맵 보여줘",
        "이 지역 안정성 점수는?",
        "월 매출 시뮬레이션 돌려줘",
    ],
    "founder": [
        "이 지역에서 유망한 업종 추천",
        "월 매출 시뮬레이션 해줘",
        "예산 대비 열기 좋은 업종",
        "신규 점포 생존율은 어때?",
        "비슷한 상권이랑 비교해줘",
    ],
}

_DEFAULT_SUGGESTED_QUESTIONS: list[str] = [
    "이 상권 요약해줘",
    "비슷한 상권이랑 비교해줘",
    "이 지역 유망 업종 추천",
    "매출 시뮬레이션 돌려줘",
    "이 상권의 리스크는?",
]

_VALID_ROLES = frozenset({"owner", "investor", "founder"})


def _suggestions_for(role: str | None) -> list[str]:
    if role and role in _VALID_ROLES:
        return list(_SUGGESTED_QUESTIONS_BY_ROLE[role])
    return list(_DEFAULT_SUGGESTED_QUESTIONS)


def _prev_quarter(quarter: str | None) -> str | None:
    # "2025Q4" → "2025Q3", "2025Q1" → "2024Q4"
    if not quarter or len(quarter) != 6 or quarter[4] != "Q":
        return None
    try:
        year = int(quarter[:4])
        q = int(quarter[5])
    except ValueError:
        return None
    if q <= 1:
        return f"{year - 1}Q4"
    return f"{year}Q{q - 1}"


def _build_top_categories(store_info: dict) -> list[PreviewTopCategory]:
    cats = store_info.get("top_categories") or []
    total = store_info.get("total_stores") or sum(int(c.get("store_count", 0)) for c in cats)
    total = total or 1
    out: list[PreviewTopCategory] = []
    for c in cats[:3]:
        sc = int(c.get("store_count", 0))
        out.append(
            PreviewTopCategory(
                category_code=c.get("category_code"),
                category_name=c.get("category_name", "기타"),
                store_count=sc,
                share_pct=round(sc / total * 100, 1),
            )
        )
    return out


def _build_floating(fp_current: dict, fp_prev: dict | None) -> PreviewFloatingPopulation:
    current_total = fp_current.get("quarter_total") if "error" not in fp_current else None
    quarter = fp_current.get("quarter") if "error" not in fp_current else None
    peak_hour = fp_current.get("peak_hour") if "error" not in fp_current else None

    prev_total: int | None = None
    delta_pct: float | None = None
    if fp_prev and "error" not in fp_prev:
        prev_total = fp_prev.get("quarter_total")
        if current_total and prev_total:
            delta_pct = round((current_total - prev_total) / prev_total * 100, 1)

    return PreviewFloatingPopulation(
        quarter=quarter,
        daily_total=int(current_total) if isinstance(current_total, (int, float)) else None,
        prev_quarter_total=int(prev_total) if isinstance(prev_total, (int, float)) else None,
        prev_quarter_delta_pct=delta_pct,
        peak_hour=int(peak_hour) if isinstance(peak_hour, (int, float)) else None,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/districts", response_model=DistrictListResponse)
async def list_districts(
    search: str | None = Query(None, description="상권명 검색 키워드"),
    type: str | None = Query(None, alias="type", description="상권 유형 필터"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> DistrictListResponse:
    """Search / list districts with optional keyword and type filter."""
    try:
        da = get_data_access()
        total, items = await da.districts.list_districts(search, type, limit, offset)
        return DistrictListResponse(
            total=total,
            items=[DistrictSummary(**item) for item in items],
        )
    except OperationalError:
        logger.exception("Database unavailable in list_districts")
        raise_db_unavailable()


@router.get("/districts/{code}", response_model=DistrictDetail)
async def get_district(code: str) -> DistrictDetail:
    """Get district detail including polygon GeoJSON."""
    try:
        da = get_data_access()
        detail = await da.districts.get_district_detail(code)
        if detail is None:
            raise_not_found("District", code)
        return DistrictDetail(**detail)
    except HTTPException:
        raise
    except OperationalError:
        logger.exception("Database unavailable in get_district")
        raise_db_unavailable()


@router.get("/districts/{code}/preview", response_model=DistrictPreview)
async def get_district_preview(
    code: str,
    role: str | None = Query(
        None,
        description="사용자 역할 (owner/investor/founder). 그 외 값은 기본 세트 반환.",
    ),
) -> DistrictPreview:
    """Zero-LLM district preview — 지도 클릭 직후 최소 정보를 반환.

    `/api/chat` SSE 풀파이프 대신 Repository 직접 호출로 LLM 비용 0 을 보장한다.
    (2026-04-23 Plan: landing-onboarding-feedback §4)
    """
    cache = get_cache_service()
    cache_role = role if role in _VALID_ROLES else "default"
    cache_key = f"preview:{code}:{cache_role}"

    cached = await cache.get(cache_key)
    if cached is not None:
        return DistrictPreview(**cached)

    try:
        da = get_data_access()

        # 1) 기본 메타 (name / type / quarter / center)
        detail = await da.districts.get_district_detail(code)
        if detail is None:
            raise_not_found("District", code)

        current_quarter = detail.get("data_quarter")
        prev_quarter = _prev_quarter(current_quarter)

        # 2) stores / floating pop 을 병렬 조회
        store_task = da.stores.get_store_info(code)
        fp_current_task = da.floating_pop.get_floating_population(code)
        fp_prev_task = (
            da.floating_pop.get_floating_population(code, prev_quarter)
            if prev_quarter
            else asyncio.sleep(0, result={"error": "no_prev_quarter"})  # type: ignore[arg-type]
        )
        store_info, fp_current, fp_prev = await asyncio.gather(
            store_task,
            fp_current_task,
            fp_prev_task,
            return_exceptions=False,
        )

        # 3) top categories — store_info 에 error 있어도 top 3 은 보통 있다
        top_categories = _build_top_categories(store_info) if isinstance(store_info, dict) else []

        # 4) 유동인구 추세
        floating = _build_floating(
            fp_current if isinstance(fp_current, dict) else {}, fp_prev if isinstance(fp_prev, dict) else None
        )

        preview = DistrictPreview(
            district_code=code,
            district_name=detail["district_name"],
            district_type=detail.get("district_type", "상권"),
            data_quarter=current_quarter or "",
            center_lng=detail.get("center_lng"),
            center_lat=detail.get("center_lat"),
            top_categories=top_categories,
            floating_population=floating,
            suggested_questions=_suggestions_for(role),
        )

        # 24h 캐시 — 분기 데이터는 변화 빈도가 낮음
        await cache.set(cache_key, preview.model_dump(), ttl=86400)
        return preview
    except HTTPException:
        raise
    except OperationalError:
        logger.exception("Database unavailable in get_district_preview code=%s", code)
        raise_db_unavailable()
    except Exception:  # pragma: no cover — defensive fallback
        logger.exception("Unexpected preview failure code=%s", code)
        # 데이터 실패 시에도 정적 suggested_questions 로 degrade
        return DistrictPreview(
            district_code=code,
            district_name=code,
            district_type="상권",
            data_quarter="",
            center_lng=None,
            center_lat=None,
            top_categories=[],
            floating_population=PreviewFloatingPopulation(),
            suggested_questions=_suggestions_for(role),
        )
