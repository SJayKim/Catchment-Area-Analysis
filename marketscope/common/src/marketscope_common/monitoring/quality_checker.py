"""데이터 품질 모니터링 — Freshness / Completeness / Anomaly / 참조무결성 체크.

체크 기준:
- Freshness: population 100일, transit 35일, revenue 100일
- Completeness: NULL 비율 < 5%
- Anomaly: 300%+ 변동 플래그
- 참조 무결성: orphan district_code
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from marketscope_common.db.models import (
    CollectionLog,
    District,
    PopulationStat,
    RevenueStat,
    Store,
    TransitStat,
)
from marketscope_common.logging import get_logger

logger = get_logger("monitoring.quality")


@dataclass
class CheckResult:
    name: str
    status: str  # "ok" | "warning" | "critical"
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class QualityReport:
    timestamp: str
    checks: list[CheckResult] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "summary": self.summary,
            "total_checks": len(self.checks),
            "ok": sum(1 for c in self.checks if c.status == "ok"),
            "warnings": sum(1 for c in self.checks if c.status == "warning"),
            "critical": sum(1 for c in self.checks if c.status == "critical"),
            "checks": [
                {"name": c.name, "status": c.status, "message": c.message, "details": c.details}
                for c in self.checks
            ],
        }


# ---------------------------------------------------------------------------
# Freshness 체크
# ---------------------------------------------------------------------------

FRESHNESS_THRESHOLDS = {
    "population": timedelta(days=100),
    "transit": timedelta(days=35),
    "revenue": timedelta(days=100),
    "store": timedelta(days=100),
}

MODEL_MAP = {
    "population": PopulationStat,
    "transit": TransitStat,
    "revenue": RevenueStat,
    "store": Store,
}


async def check_freshness(session: AsyncSession) -> list[CheckResult]:
    """각 테이블의 최신 데이터 신선도 체크."""
    results = []
    now = datetime.now(timezone.utc)

    for table_name, threshold in FRESHNESS_THRESHOLDS.items():
        model = MODEL_MAP[table_name]
        stmt = select(func.max(model.created_at))
        row = await session.execute(stmt)
        latest = row.scalar()

        if latest is None:
            results.append(CheckResult(
                name=f"freshness_{table_name}",
                status="critical",
                message=f"{table_name}: 데이터 없음",
            ))
            continue

        age = now - latest.replace(tzinfo=timezone.utc) if latest.tzinfo is None else now - latest
        if age > threshold:
            results.append(CheckResult(
                name=f"freshness_{table_name}",
                status="warning",
                message=f"{table_name}: {age.days}일 경과 (기준: {threshold.days}일)",
                details={"latest": str(latest), "age_days": age.days},
            ))
        else:
            results.append(CheckResult(
                name=f"freshness_{table_name}",
                status="ok",
                message=f"{table_name}: {age.days}일 경과 (정상)",
                details={"latest": str(latest), "age_days": age.days},
            ))

    return results


# ---------------------------------------------------------------------------
# Completeness 체크
# ---------------------------------------------------------------------------

async def check_completeness(session: AsyncSession) -> list[CheckResult]:
    """주요 필드 NULL 비율 체크 (< 5% 정상)."""
    results = []
    checks = [
        ("population_stats", "total_population", PopulationStat),
        ("revenue_stats", "total_revenue", RevenueStat),
        ("transit_stats", "boarding_total", TransitStat),
    ]

    for label, column_name, model in checks:
        col = getattr(model, column_name, None)
        if col is None:
            continue

        total_stmt = select(func.count()).select_from(model)
        null_stmt = select(func.count()).select_from(model).where(col.is_(None))

        total_row = await session.execute(total_stmt)
        null_row = await session.execute(null_stmt)

        total = total_row.scalar() or 0
        nulls = null_row.scalar() or 0

        if total == 0:
            results.append(CheckResult(
                name=f"completeness_{label}",
                status="warning",
                message=f"{label}: 레코드 없음",
            ))
            continue

        null_pct = (nulls / total) * 100
        status = "ok" if null_pct < 5.0 else "warning" if null_pct < 20.0 else "critical"

        results.append(CheckResult(
            name=f"completeness_{label}",
            status=status,
            message=f"{label}.{column_name}: NULL {null_pct:.1f}% ({nulls}/{total})",
            details={"total": total, "nulls": nulls, "null_pct": round(null_pct, 2)},
        ))

    return results


# ---------------------------------------------------------------------------
# Anomaly 체크 (300%+ 변동)
# ---------------------------------------------------------------------------

async def check_anomaly(session: AsyncSession) -> list[CheckResult]:
    """최근 2개 기간 데이터 비교, 300% 이상 변동 감지."""
    results = []

    # population: 최근 2개 분기 총인구 비교
    stmt = (
        select(PopulationStat.year, PopulationStat.quarter, func.sum(PopulationStat.total_population))
        .group_by(PopulationStat.year, PopulationStat.quarter)
        .order_by(PopulationStat.year.desc(), PopulationStat.quarter.desc())
        .limit(2)
    )
    rows = (await session.execute(stmt)).all()

    if len(rows) == 2:
        latest_val = rows[0][2] or 0
        prev_val = rows[1][2] or 0
        if prev_val > 0:
            change_pct = abs(latest_val - prev_val) / prev_val * 100
            if change_pct > 300:
                results.append(CheckResult(
                    name="anomaly_population",
                    status="critical",
                    message=f"인구 변동 {change_pct:.0f}% ({rows[1][0]} → {rows[0][0]})",
                    details={"prev": prev_val, "latest": latest_val, "change_pct": round(change_pct, 1)},
                ))
            else:
                results.append(CheckResult(
                    name="anomaly_population",
                    status="ok",
                    message=f"인구 변동 {change_pct:.1f}% (정상)",
                ))
    else:
        results.append(CheckResult(
            name="anomaly_population",
            status="warning",
            message="비교할 기간 데이터 부족",
        ))

    return results


# ---------------------------------------------------------------------------
# 참조 무결성 체크
# ---------------------------------------------------------------------------

async def check_referential_integrity(session: AsyncSession) -> list[CheckResult]:
    """orphan district_code 감지."""
    results = []

    # PopulationStat.district_id가 districts 테이블에 존재하는지
    stmt = text("""
        SELECT COUNT(*) FROM population_stats ps
        WHERE NOT EXISTS (
            SELECT 1 FROM districts d WHERE d.id = ps.district_id
        )
    """)
    try:
        row = await session.execute(stmt)
        orphan_count = row.scalar() or 0

        if orphan_count > 0:
            results.append(CheckResult(
                name="integrity_population_district",
                status="warning",
                message=f"population_stats에 orphan district_id {orphan_count}건",
                details={"orphan_count": orphan_count},
            ))
        else:
            results.append(CheckResult(
                name="integrity_population_district",
                status="ok",
                message="참조 무결성 정상",
            ))
    except Exception as e:
        results.append(CheckResult(
            name="integrity_population_district",
            status="warning",
            message=f"참조 무결성 체크 실패: {e}",
        ))

    return results


# ---------------------------------------------------------------------------
# 수집 현황 요약
# ---------------------------------------------------------------------------

async def get_collection_summary(session: AsyncSession) -> dict:
    """collection_logs 기반 최근 수집 현황."""
    stmt = (
        select(
            CollectionLog.collector_name,
            func.count().label("total"),
            func.sum(CollectionLog.records_fetched).label("total_fetched"),
            func.max(CollectionLog.created_at).label("last_run"),
        )
        .group_by(CollectionLog.collector_name)
    )
    rows = (await session.execute(stmt)).all()

    return {
        "sources": [
            {
                "source": row.collector_name,
                "total_runs": row.total,
                "total_fetched": row.total_fetched or 0,
                "last_run": str(row.last_run) if row.last_run else None,
            }
            for row in rows
        ]
    }


# ---------------------------------------------------------------------------
# 통합 품질 체크 실행
# ---------------------------------------------------------------------------

async def run_quality_check() -> dict:
    """전체 품질 체크 실행 → QualityReport 반환."""
    from marketscope_common.db.session import get_session_factory

    report = QualityReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    try:
        factory = get_session_factory()
        async with factory() as session:
            freshness = await check_freshness(session)
            report.checks.extend(freshness)

            completeness = await check_completeness(session)
            report.checks.extend(completeness)

            anomaly = await check_anomaly(session)
            report.checks.extend(anomaly)

            integrity = await check_referential_integrity(session)
            report.checks.extend(integrity)
    except Exception as e:
        logger.exception("품질 체크 중 오류")
        report.checks.append(CheckResult(
            name="system_error",
            status="critical",
            message=f"품질 체크 시스템 오류: {e}",
        ))

    ok = sum(1 for c in report.checks if c.status == "ok")
    total = len(report.checks)
    report.summary = f"{ok}/{total} 정상"

    result = report.to_dict()
    logger.info("품질 체크 완료: %s", report.summary)
    return result
