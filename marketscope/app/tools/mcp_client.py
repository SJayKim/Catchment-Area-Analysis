"""MCP 도구 호출 클라이언트."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

import httpx

from app.config import Settings
from app.logging_config import get_logger

logger = get_logger("tools.mcp")

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
                        "mcp.retry",
                        status_code=response.status_code,
                        delay_s=delay,
                        attempt=attempt,
                        max_retries=_MAX_RETRIES,
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
                        "mcp.timeout_retry",
                        delay_s=delay,
                        attempt=attempt,
                        max_retries=_MAX_RETRIES,
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
                        "mcp.request_retry",
                        delay_s=delay,
                        attempt=attempt,
                        max_retries=_MAX_RETRIES,
                        error=str(e),
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
        logger.info("mcp.call_tool", tool=tool_name)

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


class MCPClientRouter:
    """MCP 멀티서버 라우터.

    tool_name의 prefix(예: ``maps.geocode`` → ``maps``)로
    적절한 MCP 서버에 요청을 라우팅한다.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._clients: dict[str, MCPClient] = {}
        self._server_map: dict[str, str] = settings.mcp_servers

    def _resolve_server(self, tool_name: str) -> tuple[str, str]:
        """tool_name에서 서버 prefix와 실제 도구명을 분리한다.

        Returns:
            (server_prefix, actual_tool_name)
        """
        if "." in tool_name:
            prefix, actual_name = tool_name.split(".", 1)
            if prefix in self._server_map:
                return prefix, actual_name
        # prefix 없으면 기본 서버(public_data)로 라우팅
        return "public_data", tool_name

    def _get_client(self, server_prefix: str) -> MCPClient:
        """서버별 MCPClient를 lazy 생성한다."""
        if server_prefix not in self._clients:
            url = self._server_map.get(server_prefix)
            if not url:
                raise MCPClientError(
                    f"알 수 없는 MCP 서버: {server_prefix}. "
                    f"등록된 서버: {list(self._server_map.keys())}"
                )
            # 해당 서버 URL로 개별 Settings 생성 대신, base_url만 오버라이드
            client = MCPClient(self.settings)
            client.base_url = url
            self._clients[server_prefix] = client
        return self._clients[server_prefix]

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """tool_name prefix에 따라 적절한 MCP 서버로 라우팅하여 호출한다."""
        server_prefix, actual_name = self._resolve_server(tool_name)
        client = self._get_client(server_prefix)
        logger.info(
            "mcp.routing",
            tool=tool_name,
            server=server_prefix,
            actual_name=actual_name,
        )
        return await client.call_tool(actual_name, arguments)

    async def list_tools(self, server_prefix: Optional[str] = None) -> list[dict[str, Any]]:
        """특정 서버 또는 전체 서버의 도구 목록을 조회한다."""
        if server_prefix:
            client = self._get_client(server_prefix)
            return await client.list_tools()

        all_tools: list[dict[str, Any]] = []
        for prefix in self._server_map:
            try:
                client = self._get_client(prefix)
                tools = await client.list_tools()
                for tool in tools:
                    tool["_server"] = prefix
                all_tools.extend(tools)
            except Exception as e:
                logger.warning("mcp.list_tools_failed", server=prefix, error=str(e))
        return all_tools

    async def health_check(self) -> dict[str, bool]:
        """모든 MCP 서버의 상태를 확인한다."""
        results: dict[str, bool] = {}
        for prefix in self._server_map:
            try:
                client = self._get_client(prefix)
                results[prefix] = await client.health_check()
            except Exception:
                results[prefix] = False
        return results

    async def close(self) -> None:
        """모든 클라이언트를 정리한다."""
        for client in self._clients.values():
            await client.close()
        self._clients.clear()
