"""FastAPI 앱 엔트리포인트."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.logging_config import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.app_log_level.value)
    yield


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

    # Routes
    from app.api.routes.analysis import router as analysis_router
    from app.api.routes.health import router as health_router

    app.include_router(health_router, prefix="/api/v1", tags=["헬스체크"])
    app.include_router(analysis_router, prefix="/api/v1/analysis", tags=["분석"])

    return app


app = create_app()
