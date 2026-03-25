"""Dependency injection for FastAPI routes."""

from typing import AsyncGenerator

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from server.config import settings
from server.models.base import async_session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session."""
    async with async_session() as session:
        yield session


async def get_redis() -> AsyncGenerator[Redis, None]:
    """Provide an async Redis client."""
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        yield redis
    finally:
        await redis.aclose()
