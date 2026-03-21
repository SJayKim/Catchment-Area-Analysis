"""APScheduler 배치 수집 작업 — 8개 수집 스케줄.

스케줄:
- semas_population_quarterly: 분기 15일 06:00
- semas_revenue_quarterly: 분기 1일 07:00
- semas_stores_quarterly: 분기 20일 08:00
- seoul_population_monthly: 매월 15일 12:00
- seoul_subway_monthly: 매월 15일 11:00
- seoul_card_sales_monthly: 매월 15일 13:00
- refresh_mv_monthly: 매월 25일 02:00
- data_quality_daily: 매일 03:00
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger("scheduler.jobs")

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
        from app.collectors.semas import SemasCollector
        from app.db.session import get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            collector = SemasCollector(session)
            await collector.collect_floating_population()
            await session.commit()
        logger.info("[스케줄] SEMAS 유동인구 수집 완료")
    except Exception:
        logger.exception("[스케줄] SEMAS 유동인구 수집 실패")


async def job_semas_revenue_quarterly():
    """SEMAS 추정매출 분기 수집."""
    logger.info("[스케줄] SEMAS 추정매출 수집 시작")
    try:
        from app.collectors.semas import SemasCollector
        from app.db.session import get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            collector = SemasCollector(session)
            await collector.collect_estimated_revenue()
            await session.commit()
        logger.info("[스케줄] SEMAS 추정매출 수집 완료")
    except Exception:
        logger.exception("[스케줄] SEMAS 추정매출 수집 실패")


async def job_semas_stores_quarterly():
    """SEMAS 점포 목록 분기 수집."""
    logger.info("[스케줄] SEMAS 점포 수집 시작")
    try:
        from app.collectors.semas import SemasCollector
        from app.db.session import get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            collector = SemasCollector(session)
            await collector.collect_store_list()
            await session.commit()
        logger.info("[스케줄] SEMAS 점포 수집 완료")
    except Exception:
        logger.exception("[스케줄] SEMAS 점포 수집 실패")


async def job_seoul_population_monthly():
    """서울 생활인구 월간 수집."""
    logger.info("[스케줄] 서울 생활인구 수집 시작")
    try:
        from app.collectors.seoul import SeoulCollector
        from app.db.session import get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            collector = SeoulCollector(session)
            await collector.collect_living_population()
            await session.commit()
        logger.info("[스케줄] 서울 생활인구 수집 완료")
    except Exception:
        logger.exception("[스케줄] 서울 생활인구 수집 실패")


async def job_seoul_subway_monthly():
    """서울 지하철 승하차 월간 수집."""
    logger.info("[스케줄] 서울 지하철 수집 시작")
    try:
        from app.collectors.seoul import SeoulCollector
        from app.db.session import get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            collector = SeoulCollector(session)
            await collector.collect_subway_stats()
            await session.commit()
        logger.info("[스케줄] 서울 지하철 수집 완료")
    except Exception:
        logger.exception("[스케줄] 서울 지하철 수집 실패")


async def job_seoul_card_sales_monthly():
    """서울 카드매출 월간 수집."""
    logger.info("[스케줄] 서울 카드매출 수집 시작")
    try:
        from app.collectors.seoul import SeoulCollector
        from app.db.session import get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            collector = SeoulCollector(session)
            await collector.collect_card_sales()
            await session.commit()
        logger.info("[스케줄] 서울 카드매출 수집 완료")
    except Exception:
        logger.exception("[스케줄] 서울 카드매출 수집 실패")


async def job_refresh_mv_monthly():
    """Materialized View 갱신."""
    logger.info("[스케줄] MV 갱신 시작")
    try:
        from sqlalchemy import text
        from app.db.session import get_session_factory

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
        from app.monitoring.quality_checker import run_quality_check
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
