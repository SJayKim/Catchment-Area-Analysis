"""Base collector with pagination, retry, and concurrency control."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from server.config import settings

logger = logging.getLogger(__name__)


class CollectorError(Exception):
    """Raised when data collection fails."""


class BaseCollector(ABC):
    """Abstract base for all API data collectors."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self._client: httpx.AsyncClient | None = None
        self._semaphore = asyncio.Semaphore(settings.etl_max_concurrency)

    async def __aenter__(self) -> BaseCollector:
        self._client = httpx.AsyncClient(timeout=settings.etl_request_timeout)
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._client:
            await self._client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("Collector must be used as async context manager")
        return self._client

    @retry(
        stop=stop_after_attempt(settings.etl_max_retries),
        wait=wait_exponential(multiplier=2, min=2, max=8),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
        reraise=True,
    )
    async def _fetch_page(self, url: str) -> dict:
        """Fetch a single page with retry."""
        async with self._semaphore:
            response = await self.client.get(url)
            response.raise_for_status()
            return response.json()

    @abstractmethod
    async def collect(self, quarter: str) -> list[dict]:
        """Collect raw data for a given quarter. Subclasses must implement."""
        ...

    @staticmethod
    def log_progress(service: str, fetched: int, total: int) -> None:
        logger.info(f"[{service}] {fetched}/{total} rows fetched")
