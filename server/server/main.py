"""FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.config import settings
from server.logging_config import setup_logging

# Initialize structured logging before anything else
setup_logging(json_output=(settings.log_format == "json"))

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DataAccess, CacheService, and Agent singleton at startup."""

    from server.repositories import set_data_access
    from server.services.cache import (
        MemoryCacheService,
        RedisCacheService,
        set_cache_service,
    )
    from server.services.category_resolver import (
        CategoryResolver,
        set_category_resolver,
    )

    # --- Cache ---
    if settings.use_mock:
        cache = MemoryCacheService()
    else:
        cache = RedisCacheService(settings.redis_url)
    set_cache_service(cache)

    # --- DataAccess ---
    engine = None
    if settings.use_mock:
        from server.repositories.mock.factory import build_mock_data_access

        da = build_mock_data_access()
    else:
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

        engine = create_async_engine(
            settings.database_url,
            echo=False,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_pre_ping=settings.db_pool_pre_ping,
            pool_recycle=settings.db_pool_recycle,
            pool_timeout=settings.db_pool_timeout,
            connect_args={
                "server_settings": {
                    "statement_timeout": str(settings.db_statement_timeout_ms),
                },
            },
        )
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        from server.repositories.real.factory import build_real_data_access

        da = build_real_data_access(session_factory)
    set_data_access(da)

    # --- CategoryResolver ---
    resolver = CategoryResolver()
    if settings.use_mock:
        resolver.load_defaults()
    else:
        await resolver.load_from_db(session_factory)
    set_category_resolver(resolver)

    # Store engine reference for health/detail metrics
    app.state.db_engine = engine

    mode = "Mock" if settings.use_mock else "Real"
    logger.info(f"MarketScope AI started in {mode} mode")

    yield

    # --- Shutdown ---
    await cache.close()
    if engine is not None:
        await engine.dispose()
    # Langfuse best-effort flush — pending trace 가 SIGTERM 직후 드랍되지 않도록.
    try:
        from server.services.langfuse_tracer import shutdown as lf_shutdown

        lf_shutdown()
    except Exception:
        logger.debug("langfuse shutdown hook failed", exc_info=True)
    logger.info("MarketScope AI shutdown complete")


app = FastAPI(
    title="MarketScope AI",
    description="상권분석 AI 서비스 API",
    version="0.1.0",
    lifespan=lifespan,
)

# --- Middleware (order matters: last added = first executed) ---

# 1. CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Security headers
from server.api.middleware import (
    RequestIdMiddleware,
    SecurityHeadersMiddleware,
    register_global_exception_handler,
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIdMiddleware)

# 3. Global exception handler (non-SSE routes)
register_global_exception_handler(app)

# 4. Rate limiting
from server.api.rate_limiter import register_rate_limiter

register_rate_limiter(app)

# 5. Metrics (lightweight, no external dependency)
from server.middleware.metrics import MetricsMiddleware, metrics_router

app.add_middleware(MetricsMiddleware)

# Register routers
from server.api.routes.chat import router as chat_router
from server.api.routes.districts import router as districts_router
from server.api.routes.feedback import router as feedback_router
from server.api.routes.map_data import router as map_data_router

app.include_router(districts_router)
app.include_router(map_data_router)
app.include_router(chat_router)
app.include_router(feedback_router)
app.include_router(metrics_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
