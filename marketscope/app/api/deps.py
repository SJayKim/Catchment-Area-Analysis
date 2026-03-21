"""FastAPI 의존성 주입."""

from __future__ import annotations

from app.config import Settings, get_settings


def get_current_settings() -> Settings:
    return get_settings()
