"""Collector 추상 클래스 — 외부 API → DB 수집 공통 기반."""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CollectionLog

logger = logging.getLogger(__name__)


class CollectionError(Exception):
    """수집 중 발생하는 에러."""
    pass


class BaseCollector(ABC):
    """모든 Collector의 기본 클래스.

    공통 기능:
    - HTTP 재시도 (3회, 지수 백오프)
    - 429 Rate Limit 처리
    - collection_logs 기록
    - 응답 구조 검증
    """

    COLLECTOR_NAME: str = "base"
    MAX_RETRIES: int = 3
    TIMEOUT: int = 30
    MAX_CONNECTIONS: int = 5

    def __init__(self, session: AsyncSession, api_key: Optional[str] = None) -> None:
        self.session = session
        self.api_key = api_key
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.TIMEOUT),
                limits=httpx.Limits(
                    max_connections=self.MAX_CONNECTIONS,
                    max_keepalive_connections=self.MAX_CONNECTIONS,
                ),
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _call_api_with_retry(
        self,
        method: str,
        url: str,
        *,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
        json_body: Optional[dict] = None,
    ) -> dict[str, Any]:
        """HTTP 호출 + 3회 재시도 + 지수 백오프."""
        client = await self._get_client()
        last_error: Optional[Exception] = None

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                response = await client.request(
                    method, url, params=params, headers=headers, json=json_body,
                )

                if response.status_code == 429:
                    wait = self._handle_rate_limit(response, attempt)
                    logger.warning(
                        "%s rate limited (429), waiting %.1fs (attempt %d/%d)",
                        self.COLLECTOR_NAME, wait, attempt, self.MAX_RETRIES,
                    )
                    await asyncio.sleep(wait)
                    continue

                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code in (500, 502, 503, 504):
                    wait = 2 ** attempt
                    logger.warning(
                        "%s server error %d, retrying in %ds (attempt %d/%d)",
                        self.COLLECTOR_NAME, e.response.status_code,
                        wait, attempt, self.MAX_RETRIES,
                    )
                    await asyncio.sleep(wait)
                    continue
                raise CollectionError(
                    f"{self.COLLECTOR_NAME} HTTP {e.response.status_code}: {e}"
                ) from e

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = e
                wait = 2 ** attempt
                logger.warning(
                    "%s connection error, retrying in %ds (attempt %d/%d): %s",
                    self.COLLECTOR_NAME, wait, attempt, self.MAX_RETRIES, e,
                )
                await asyncio.sleep(wait)

        raise CollectionError(
            f"{self.COLLECTOR_NAME} failed after {self.MAX_RETRIES} attempts: {last_error}"
        )

    def _handle_rate_limit(self, response: httpx.Response, attempt: int) -> float:
        """429 응답에서 Retry-After 헤더를 파싱하거나 기본 대기."""
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass
        return min(2 ** attempt * 5, 60)

    def _validate_response(self, data: Any, *, required_keys: Optional[list[str]] = None) -> bool:
        """응답 구조 기본 검증."""
        if data is None:
            return False
        if required_keys:
            if isinstance(data, dict):
                return all(k in data for k in required_keys)
        return True

    async def _log_collection(
        self,
        endpoint: str,
        params: Optional[dict],
        *,
        status: str = "success",
        records_fetched: int = 0,
        records_inserted: int = 0,
        records_updated: int = 0,
        error_message: Optional[str] = None,
        duration_ms: Optional[int] = None,
    ) -> None:
        """수집 이력을 collection_logs 테이블에 기록."""
        log = CollectionLog(
            collector_name=self.COLLECTOR_NAME,
            endpoint=endpoint,
            params=params,
            status=status,
            records_fetched=records_fetched,
            records_inserted=records_inserted,
            records_updated=records_updated,
            error_message=error_message,
            duration_ms=duration_ms,
        )
        self.session.add(log)
        await self.session.flush()

    @abstractmethod
    async def collect(self, **kwargs) -> dict[str, Any]:
        """데이터 수집 실행. 하위 클래스에서 구현."""
        ...
