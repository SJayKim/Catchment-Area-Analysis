"""MCP 도구 호출 클라이언트."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

import httpx

from app.config import Settings
from app.logging_config import get_logger

logger = get_logger("mcp_client")

_MAX_RETRIES = 3
_BACKOFF_BASE = 0.5  # seconds
_RETRYABLE_STATUS_CODES = {502, 503, 504}


class MCPClientError(Exception):
    """MCP 클라이언트에서 발생하는 기본 예외."""

    def __init__(self, message: str, *, original_error: Optional[Exception] = None) -> None:
        self.original_error = original_error
        super().__init__(message)


class MCPConnectionError(MCPClientError):
    """MCP 서버 연결 실패."""


class MCPResponseError(MCPClientError):
    """MCP 서버 응답 파싱 실패."""


class MCPClient:
    """MCP 프로토콜 기반 도구 호출 클라이언트."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = settings.mcp_server_url
        self.timeout = settings.mcp_timeout
        self._http_client: Optional[httpx.AsyncClient] = None

    # -- async context manager --------------------------------------------------

    async def __aenter__(self) -> MCPClient:
        await self._get_client()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    # -- internal ---------------------------------------------------------------

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
                limits=httpx.Limits(
                    max_connections=10,
                    max_keepalive_connections=5,
                ),
            )
        return self._http_client

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """HTTP 요청을 재시도 로직과 함께 실행한다."""
        client = await self._get_client()
        last_exc: Optional[Exception] = None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = await client.request(method, url, **kwargs)

                if response.status_code in _RETRYABLE_STATUS_CODES and attempt < _MAX_RETRIES:
                    delay = _BACKOFF_BASE * (2 ** (attempt - 1))
                    logger.warning(
                        "MCP 서버 일시 오류 %s, %s초 후 재시도 (%d/%d)",
                        response.status_code,
                        delay,
                        attempt,
                        _MAX_RETRIES,
                    )
                    await asyncio.sleep(delay)
                    continue

                response.raise_for_status()
                return response

            except httpx.TimeoutException as e:
                last_exc = e
                if attempt < _MAX_RETRIES:
                    delay = _BACKOFF_BASE * (2 ** (attempt - 1))
                    logger.warning(
                        "MCP 요청 타임아웃, %s초 후 재시도 (%d/%d)",
                        delay,
                        attempt,
                        _MAX_RETRIES,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise MCPConnectionError(
                    f"MCP 서버 타임아웃 ({_MAX_RETRIES}회 시도 실패)",
                    original_error=e,
                ) from e

            except httpx.HTTPStatusError as e:
                raise MCPConnectionError(
                    f"MCP 서버 HTTP {e.response.status_code} 오류",
                    original_error=e,
                ) from e

            except httpx.HTTPError as e:
                last_exc = e
                if attempt < _MAX_RETRIES:
                    delay = _BACKOFF_BASE * (2 ** (attempt - 1))
                    logger.warning(
                        "MCP 요청 실패, %s초 후 재시도 (%d/%d): %s",
                        delay,
                        attempt,
                        _MAX_RETRIES,
                        e,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise MCPConnectionError(
                    f"MCP 서버 연결 실패 ({_MAX_RETRIES}회 시도 실패)",
                    original_error=e,
                ) from e

        # Should not be reached, but guard against it.
        raise MCPConnectionError(
            "MCP 요청 재시도 초과",
            original_error=last_exc,
        )

    @staticmethod
    def _parse_json(response: httpx.Response) -> Any:
        """응답 본문을 JSON으로 파싱한다."""
        try:
            return response.json()
        except (ValueError, UnicodeDecodeError) as e:
            raise MCPResponseError(
                f"MCP 응답 JSON 파싱 실패: {response.text[:200]}",
                original_error=e,
            ) from e

    # -- public API -------------------------------------------------------------

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """MCP 도구를 호출하고 결과를 반환한다."""
        logger.info("MCP 도구 호출: %s", tool_name)

        response = await self._request_with_retry(
            "POST",
            "/tools/call",
            json={
                "name": tool_name,
                "arguments": arguments,
            },
        )
        return self._parse_json(response)

    async def list_tools(self) -> list[dict[str, Any]]:
        """사용 가능한 MCP 도구 목록을 조회한다."""
        response = await self._request_with_retry("GET", "/tools/list")
        return self._parse_json(response)

    async def health_check(self) -> bool:
        """MCP 서버 상태를 확인한다. 정상이면 True를 반환한다."""
        try:
            client = await self._get_client()
            response = await client.get("/health")
            return response.status_code == 200  # noqa: PLR2004
        except httpx.HTTPError:
            return False

    async def close(self) -> None:
        """HTTP 클라이언트를 정리한다."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None
