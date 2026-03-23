"""APScheduler 배치 수집 작업 — 10개 수집 스케줄.

스케줄:
- semas_population_quarterly: 분기 15일 06:00
- semas_revenue_quarterly: 분기 1일 07:00
- semas_stores_quarterly: 분기 20일 08:00
- seoul_population_monthly: 매월 15일 12:00
- seoul_subway_monthly: 매월 15일 11:00
- seoul_card_sales_monthly: 매월 15일 13:00
- kosis_resident_population_yearly: 매년 3월 1일 09:00
- kosis_worker_population_yearly: 매년 3월 1일 10:00
- refresh_mv_monthly: 매월 25일 02:00
- data_quality_daily: 매일 03:00
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger("scheduler.jobs")


def _current_quarter() -> tuple[int, int]:
    """현재 연도와 분기 반환."""
    now = datetime.now(timezone.utc)
    quarter = (now.month - 1) // 3 + 1
    return now.year, quarter


def _prev_month() -> tuple[int, int]:
    """직전 월 (year, month) 반환."""
    now = datetime.now(timezone.utc)
    if now.month == 1:
        return now.year - 1, 12
    return now.year, now.month - 1


async def _get_districts() -> list[dict]:
    """DB에서 district 목록 조회. 실패 시 빈 리스트 반환."""
    try:
        from sqlalchemy import text
        from marketscope_common.db.session import get_session_factory
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                text("SELECT id, district_code, district_name, gu_name, admin_dong_code FROM districts WHERE is_active = true LIMIT 100")
            )
            return [dict(row._mapping) for row in result]
    except Exception:
        logger.warning("district 목록 조회 실패 — 빈 리스트로 진행")
        return []

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    """스케줄러 싱글턴."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="Asia/Seoul")
    return _scheduler


# ---------------------------------------------------------------------------
# 개별 작업 함수
# ---------------------------------------------------------------------------

async def job_semas_population_quarterly():
    """SEMAS 유동인구 분기 수집."""
    logger.info("[스케줄] SEMAS 유동인구 수집 시작")
    try:
        from marketscope_pipeline.collectors.semas import SemasCollector
        from marketscope_common.config import get_settings
        from marketscope_common.db.session import get_session_factory

        settings = get_settings()
        api_key = settings.data_api_public_data_key
        if not api_key:
            logger.warning("[스케줄] SEMAS API 키 미설정 — 스킵")
            return

        year, quarter = _current_quarter()
        districts = await _get_districts()
        factory = get_session_factory()

        for dist in districts:
            try:
                async with factory() as session:
                    collector = SemasCollector(session, api_key)
                    await collector.collect_floating_population(
                        district_code=dist["district_code"],
                        year=year,
                        quarter=quarter,
                        district_id=dist["id"],
                    )
                    await session.commit()
            except Exception:
                logger.exception("[스케줄] SEMAS 유동인구 수집 실패: %s", dist.get("district_name"))

        logger.info("[스케줄] SEMAS 유동인구 수집 완료 (%d개 상권)", len(districts))
    except Exception:
        logger.exception("[스케줄] SEMAS 유동인구 수집 전체 실패")


async def job_semas_revenue_quarterly():
    """SEMAS 추정매출 분기 수집."""
    logger.info("[스케줄] SEMAS 추정매출 수집 시작")
    try:
        from marketscope_pipeline.collectors.semas import SemasCollector
        from marketscope_common.config import get_settings
        from marketscope_common.db.session import get_session_factory

        settings = get_settings()
        api_key = settings.data_api_public_data_key
        if not api_key:
            logger.warning("[스케줄] SEMAS API 키 미설정 — 스킵")
            return

        year, quarter = _current_quarter()
        districts = await _get_districts()
        factory = get_session_factory()

        for dist in districts:
            try:
                async with factory() as session:
                    collector = SemasCollector(session, api_key)
                    await collector.collect_estimated_revenue(
                        district_code=dist["district_code"],
                        industry_code="",  # 전체 업종
                        year=year,
                        quarter=quarter,
                        district_id=dist["id"],
                    )
                    await session.commit()
            except Exception:
                logger.exception("[스케줄] SEMAS 추정매출 수집 실패: %s", dist.get("district_name"))

        logger.info("[스케줄] SEMAS 추정매출 수집 완료 (%d개 상권)", len(districts))
    except Exception:
        logger.exception("[스케줄] SEMAS 추정매출 수집 전체 실패")


async def job_semas_stores_quarterly():
    """SEMAS 점포 목록 분기 수집."""
    logger.info("[스케줄] SEMAS 점포 수집 시작")
    try:
        from marketscope_pipeline.collectors.semas import SemasCollector
        from marketscope_common.config import get_settings
        from marketscope_common.db.session import get_session_factory

        settings = get_settings()
        api_key = settings.data_api_public_data_key
        if not api_key:
            logger.warning("[스케줄] SEMAS API 키 미설정 — 스킵")
            return

        districts = await _get_districts()
        factory = get_session_factory()

        for dist in districts:
            try:
                async with factory() as session:
                    collector = SemasCollector(session, api_key)
                    await collector.collect_store_list(
                        district_code=dist["district_code"],
                        district_id=dist["id"],
                    )
                    await session.commit()
            except Exception:
                logger.exception("[스케줄] SEMAS 점포 수집 실패: %s", dist.get("district_name"))

        logger.info("[스케줄] SEMAS 점포 수집 완료 (%d개 상권)", len(districts))
    except Exception:
        logger.exception("[스케줄] SEMAS 점포 수집 전체 실패")


async def job_seoul_population_monthly():
    """서울 생활인구 월간 수집."""
    logger.info("[스케줄] 서울 생활인구 수집 시작")
    try:
        from marketscope_pipeline.collectors.seoul import SeoulCollector
        from marketscope_common.config import get_settings
        from marketscope_common.db.session import get_session_factory

        settings = get_settings()
        api_key = settings.data_api_seoul_open_data_key
        if not api_key:
            logger.warning("[스케줄] 서울 열린데이터 API 키 미설정 — 스킵")
            return

        year, month = _prev_month()
        date_str = f"{year}{month:02d}01"
        districts = await _get_districts()
        factory = get_session_factory()

        for dist in districts:
            try:
                dong_code = dist.get("district_code", "")
                async with factory() as session:
                    collector = SeoulCollector(session, api_key)
                    await collector.collect_living_population(
                        dong_code=dong_code,
                        date_str=date_str,
                        district_id=dist["id"],
                    )
                    await session.commit()
            except Exception:
                logger.exception("[스케줄] 서울 생활인구 수집 실패: %s", dist.get("district_name"))

        logger.info("[스케줄] 서울 생활인구 수집 완료 (%d개 상권)", len(districts))
    except Exception:
        logger.exception("[스케줄] 서울 생활인구 수집 전체 실패")


async def job_seoul_subway_monthly():
    """서울 지하철 승하차 월간 수집."""
    logger.info("[스케줄] 서울 지하철 수집 시작")
    try:
        from marketscope_pipeline.collectors.seoul import SeoulCollector
        from marketscope_common.config import get_settings
        from marketscope_common.db.session import get_session_factory

        settings = get_settings()
        api_key = settings.data_api_seoul_open_data_key
        if not api_key:
            logger.warning("[스케줄] 서울 열린데이터 API 키 미설정 — 스킵")
            return

        year, month = _prev_month()
        year_month = f"{year}{month:02d}01"
        factory = get_session_factory()

        async with factory() as session:
            collector = SeoulCollector(session, api_key)
            await collector.collect_subway_stats(year_month=year_month)
            await session.commit()

        logger.info("[스케줄] 서울 지하철 수집 완료")
    except Exception:
        logger.exception("[스케줄] 서울 지하철 수집 실패")


async def job_seoul_card_sales_monthly():
    """서울 카드매출 월간 수집."""
    logger.info("[스케줄] 서울 카드매출 수집 시작")
    try:
        from marketscope_pipeline.collectors.seoul import SeoulCollector
        from marketscope_common.config import get_settings
        from marketscope_common.db.session import get_session_factory

        settings = get_settings()
        api_key = settings.data_api_seoul_open_data_key
        if not api_key:
            logger.warning("[스케줄] 서울 열린데이터 API 키 미설정 — 스킵")
            return

        year, month = _prev_month()
        districts = await _get_districts()
        factory = get_session_factory()

        for dist in districts:
            try:
                async with factory() as session:
                    collector = SeoulCollector(session, api_key)
                    await collector.collect_card_sales(
                        year=str(year),
                        month=str(month),
                        district_id=dist["id"],
                        dong_code=dist.get("district_code", ""),
                    )
                    await session.commit()
            except Exception:
                logger.exception("[스케줄] 서울 카드매출 수집 실패: %s", dist.get("district_name"))

        logger.info("[스케줄] 서울 카드매출 수집 완료 (%d개 상권)", len(districts))
    except Exception:
        logger.exception("[스케줄] 서울 카드매출 수집 전체 실패")


_KOSIS_GU_REGION_CODES = {
    "강남구": "1168000000", "마포구": "1144000000",
    "용산구": "1117000000", "광진구": "1121500000",
    "서대문구": "1141000000", "종로구": "1111000000",
    "중구": "1114000000", "영등포구": "1156000000",
    "성동구": "1120000000", "송파구": "1171000000",
}


async def job_kosis_resident_population_yearly():
    """KOSIS 주민등록인구 연간 수집."""
    logger.info("[스케줄] KOSIS 주민등록인구 수집 시작")
    try:
        from marketscope_pipeline.collectors.kosis import KosisCollector
        from marketscope_common.config import get_settings
        from marketscope_common.db.session import get_session_factory

        settings = get_settings()
        api_key = getattr(settings, "data_api_kosis_key", "")
        if not api_key:
            logger.warning("[스케줄] KOSIS API 키 미설정 — 스킵")
            return

        year = datetime.now(timezone.utc).year - 1
        districts = await _get_districts()
        factory = get_session_factory()

        seen_gu: set[str] = set()
        for dist in districts:
            gu_name = dist.get("gu_name", "")
            if not gu_name or gu_name in seen_gu or gu_name not in _KOSIS_GU_REGION_CODES:
                continue
            seen_gu.add(gu_name)

            try:
                async with factory() as session:
                    collector = KosisCollector(session, api_key)
                    await collector.collect_resident_population(
                        region_code=_KOSIS_GU_REGION_CODES[gu_name],
                        year=year,
                        district_id=dist["id"],
                    )
                    await session.commit()
            except Exception:
                logger.exception("[스케줄] KOSIS 주민인구 수집 실패: %s", gu_name)

        logger.info("[스케줄] KOSIS 주민등록인구 수집 완료 (%d개 구)", len(seen_gu))
    except Exception:
        logger.exception("[스케줄] KOSIS 주민등록인구 수집 전체 실패")


async def job_kosis_worker_population_yearly():
    """KOSIS 직장인구 연간 수집."""
    logger.info("[스케줄] KOSIS 직장인구 수집 시작")
    try:
        from marketscope_pipeline.collectors.kosis import KosisCollector
        from marketscope_common.config import get_settings
        from marketscope_common.db.session import get_session_factory

        settings = get_settings()
        api_key = getattr(settings, "data_api_kosis_key", "")
        if not api_key:
            logger.warning("[스케줄] KOSIS API 키 미설정 — 스킵")
            return

        year = datetime.now(timezone.utc).year - 1
        districts = await _get_districts()
        factory = get_session_factory()

        seen_gu: set[str] = set()
        for dist in districts:
            gu_name = dist.get("gu_name", "")
            if not gu_name or gu_name in seen_gu or gu_name not in _KOSIS_GU_REGION_CODES:
                continue
            seen_gu.add(gu_name)

            try:
                async with factory() as session:
                    collector = KosisCollector(session, api_key)
                    await collector.collect_worker_population(
                        region_code=_KOSIS_GU_REGION_CODES[gu_name],
                        year=year,
                        district_id=dist["id"],
                    )
                    await session.commit()
            except Exception:
                logger.exception("[스케줄] KOSIS 직장인구 수집 실패: %s", gu_name)

        logger.info("[스케줄] KOSIS 직장인구 수집 완료 (%d개 구)", len(seen_gu))
    except Exception:
        logger.exception("[스케줄] KOSIS 직장인구 수집 전체 실패")


async def job_refresh_mv_monthly():
    """Materialized View 갱신."""
    logger.info("[스케줄] MV 갱신 시작")
    try:
        from sqlalchemy import text
        from marketscope_common.db.session import get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            await session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY IF EXISTS mv_district_summary"))
            await session.commit()
        logger.info("[스케줄] MV 갱신 완료")
    except Exception:
        logger.exception("[스케줄] MV 갱신 실패")


async def job_data_quality_daily():
    """일일 데이터 품질 체크."""
    logger.info("[스케줄] 데이터 품질 체크 시작")
    try:
        from marketscope_common.monitoring.quality_checker import run_quality_check
        report = await run_quality_check()
        logger.info("[스케줄] 데이터 품질 체크 완료: %s", report.get("summary", ""))
    except Exception:
        logger.exception("[스케줄] 데이터 품질 체크 실패")


# ---------------------------------------------------------------------------
# 스케줄 등록
# ---------------------------------------------------------------------------

# 분기 기준월: 1,4,7,10 (month="1,4,7,10")
_QUARTERLY_MONTHS = "1,4,7,10"


def register_all_jobs(scheduler: AsyncIOScheduler | None = None) -> AsyncIOScheduler:
    """모든 수집 스케줄 등록."""
    s = scheduler or get_scheduler()

    # SEMAS 분기별 (1,4,7,10월)
    s.add_job(
        job_semas_population_quarterly,
        CronTrigger(month=_QUARTERLY_MONTHS, day=15, hour=6),
        id="semas_population_quarterly",
        replace_existing=True,
    )
    s.add_job(
        job_semas_revenue_quarterly,
        CronTrigger(month=_QUARTERLY_MONTHS, day=1, hour=7),
        id="semas_revenue_quarterly",
        replace_existing=True,
    )
    s.add_job(
        job_semas_stores_quarterly,
        CronTrigger(month=_QUARTERLY_MONTHS, day=20, hour=8),
        id="semas_stores_quarterly",
        replace_existing=True,
    )

    # 서울 월별
    s.add_job(
        job_seoul_population_monthly,
        CronTrigger(day=15, hour=12),
        id="seoul_population_monthly",
        replace_existing=True,
    )
    s.add_job(
        job_seoul_subway_monthly,
        CronTrigger(day=15, hour=11),
        id="seoul_subway_monthly",
        replace_existing=True,
    )
    s.add_job(
        job_seoul_card_sales_monthly,
        CronTrigger(day=15, hour=13),
        id="seoul_card_sales_monthly",
        replace_existing=True,
    )

    # KOSIS 연간 (매년 3월)
    s.add_job(
        job_kosis_resident_population_yearly,
        CronTrigger(month=3, day=1, hour=9),
        id="kosis_resident_population_yearly",
        replace_existing=True,
    )
    s.add_job(
        job_kosis_worker_population_yearly,
        CronTrigger(month=3, day=1, hour=10),
        id="kosis_worker_population_yearly",
        replace_existing=True,
    )

    # MV 갱신 (월별)
    s.add_job(
        job_refresh_mv_monthly,
        CronTrigger(day=25, hour=2),
        id="refresh_mv_monthly",
        replace_existing=True,
    )

    # 데이터 품질 체크 (일별)
    s.add_job(
        job_data_quality_daily,
        CronTrigger(hour=3),
        id="data_quality_daily",
        replace_existing=True,
    )

    logger.info("스케줄 등록 완료: %d개 작업", len(s.get_jobs()))
    return s


async def start_scheduler() -> AsyncIOScheduler:
    """스케줄러 시작."""
    s = register_all_jobs()
    s.start()
    logger.info("스케줄러 시작됨")
    return s


async def shutdown_scheduler() -> None:
    """스케줄러 종료."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("스케줄러 종료됨")


def list_jobs() -> list[dict]:
    """등록된 작업 목록 반환 (dry-run 확인용)."""
    s = get_scheduler()
    return [
        {
            "id": job.id,
            "next_run": str(job.next_run_time) if job.next_run_time else None,
            "trigger": str(job.trigger),
        }
        for job in s.get_jobs()
    ]
