"""FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.config import settings

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
            settings.database_url, echo=False,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
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
    logger.info("MarketScope AI shutdown complete")


app = FastAPI(
    title="MarketScope AI",
    description="상권분석 AI 서비스 API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
from server.api.routes.chat import router as chat_router
from server.api.routes.districts import router as districts_router
from server.api.routes.map_data import router as map_data_router

app.include_router(districts_router)
app.include_router(map_data_router)
app.include_router(chat_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
