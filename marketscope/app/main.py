"""FastAPI 앱 엔트리포인트."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.logging_config import get_logger, setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.app_log_level.value, env=settings.app_env.value)
    logger = get_logger("lifespan")

    # ── Startup ──
    logger.info("app.startup", env=settings.app_env.value, version=settings.app_version)

    # Redis 연결
    try:
        from app.cache.redis_client import get_redis
        await get_redis(settings)
        logger.info("redis.connected")
    except Exception as e:
        logger.warning("redis.connection_failed", error=str(e))

    # MCP Router 초기화
    from app.graph.nodes import _get_mcp_router
    _get_mcp_router()
    logger.info("mcp_router.initialized", servers=list(settings.mcp_servers.keys()))

    # Langfuse 초기화
    from app.monitoring.langfuse_handler import setup_langfuse
    setup_langfuse(settings)

    yield

    # ── Shutdown ──
    logger.info("app.shutdown_start")

    from app.graph.nodes import shutdown_mcp_router
    await shutdown_mcp_router()

    from app.monitoring.langfuse_handler import shutdown_langfuse
    await shutdown_langfuse()

    try:
        from app.cache.redis_client import close_redis
        await close_redis()
        logger.info("redis.disconnected")
    except Exception as e:
        logger.warning("redis.cleanup_error", error=str(e))

    logger.info("app.shutdown_complete")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="MarketScope AI API",
        version=settings.app_version,
        description="AI 기반 상권 분석 플랫폼 API",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.app_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # HTTP 메트릭 미들웨어
    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next) -> Response:
        from app.monitoring.metrics import observe_http_request
        start = time.monotonic()
        response = await call_next(request)
        duration = time.monotonic() - start
        observe_http_request(
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration=duration,
        )
        return response

    # Routes
    from app.api.routes.analysis import router as analysis_router
    from app.api.routes.health import router as health_router

    app.include_router(health_router, prefix="/api/v1", tags=["헬스체크"])
    app.include_router(analysis_router, prefix="/api/v1/analysis", tags=["분석"])

    # Prometheus /metrics 엔드포인트
    from prometheus_client import make_asgi_app
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    return app


app = create_app()
