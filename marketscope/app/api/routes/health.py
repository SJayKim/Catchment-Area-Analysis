"""헬스체크 엔드포인트 — live / ready / detailed."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter

from app.config import get_settings

router = APIRouter()

_app_start_time = time.monotonic()


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """기본 헬스체크."""
    settings = get_settings()
    return {
        "status": "healthy",
        "app_name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env.value,
    }


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    """프로세스 생존 확인 (Kubernetes liveness probe)."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness() -> dict[str, Any]:
    """컴포넌트 연결 상태 확인 (Kubernetes readiness probe)."""
    checks: dict[str, dict[str, Any]] = {}

    # Database
    checks["database"] = await _check_database()

    # Redis
    checks["redis"] = await _check_redis()

    # MCP 서버 5개
    checks["mcp_servers"] = await _check_mcp_servers()

    all_ok = all(
        c.get("status") == "ok"
        for c in checks.values()
        if isinstance(c, dict) and "status" in c
    )

    return {
        "status": "ok" if all_ok else "degraded",
        "checks": checks,
    }


@router.get("/health/detailed")
async def detailed_health() -> dict[str, Any]:
    """상세 헬스체크 — 컴포넌트 상태 + MCP 통계 + DAG 타이밍."""
    settings = get_settings()
    checks: dict[str, Any] = {}

    checks["database"] = await _check_database()
    checks["redis"] = await _check_redis()
    checks["mcp_servers"] = await _check_mcp_servers()

    # MCP 모니터링 통계
    mcp_stats = {}
    try:
        from app.graph.nodes import _mcp_monitor
        if _mcp_monitor is not None:
            mcp_stats = _mcp_monitor.get_stats()
    except Exception:
        pass

    # DAG 트레이서 타이밍
    dag_timings = {}
    try:
        from app.monitoring.dag_tracer import get_dag_tracer
        dag_timings = get_dag_tracer().get_timings()
    except Exception:
        pass

    uptime_seconds = time.monotonic() - _app_start_time

    return {
        "status": "ok" if all(
            c.get("status") == "ok"
            for c in checks.values()
            if isinstance(c, dict) and "status" in c
        ) else "degraded",
        "app": {
            "name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.app_env.value,
            "uptime_seconds": round(uptime_seconds, 1),
        },
        "checks": checks,
        "mcp_stats": mcp_stats,
        "dag_timings": dag_timings,
    }


# ── 내부 체크 함수 ──


async def _check_database() -> dict[str, Any]:
    """DB 연결 상태 확인."""
    try:
        from sqlalchemy import text
        from app.db.session import async_session_factory
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def _check_redis() -> dict[str, Any]:
    """Redis 연결 상태 확인."""
    try:
        from app.cache.redis_client import _redis_client
        if _redis_client is None:
            return {"status": "not_configured"}
        await _redis_client.ping()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def _check_mcp_servers() -> dict[str, Any]:
    """MCP 서버 상태 확인."""
    try:
        from app.graph.nodes import _mcp_monitor, _mcp_router
        client = _mcp_monitor or _mcp_router
        if client is None:
            return {"status": "not_initialized"}
        results = await client.health_check()
        all_healthy = all(results.values())
        return {
            "status": "ok" if all_healthy else "degraded",
            "servers": results,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
