"""MCP 호출 모니터링 미들웨어 — 레이턴시·에러율 추적."""

from __future__ import annotations

import time
from typing import Any

from app.logging_config import get_logger

logger = get_logger("monitoring.mcp")


class MCPMonitoringMiddleware:
    """MCPClientRouter를 래핑하여 호출 모니터링을 수행한다."""

    def __init__(self, router: Any) -> None:
        self._router = router
        self._stats: dict[str, dict[str, Any]] = {}

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """도구를 호출하고 레이턴시·성공여부를 기록한다."""
        server_prefix = tool_name.split(".")[0] if "." in tool_name else "public_data"
        start = time.monotonic()

        try:
            result = await self._router.call_tool(tool_name, arguments)
            latency_ms = (time.monotonic() - start) * 1000
            self._record(server_prefix, tool_name, latency_ms, success=True)

            logger.info(
                "mcp.call.success",
                tool=tool_name,
                server=server_prefix,
                latency_ms=round(latency_ms, 1),
            )

            # Prometheus 메트릭
            from app.monitoring.metrics import observe_mcp_call
            observe_mcp_call(server_prefix, tool_name, latency_ms / 1000)

            return result

        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            error_type = type(e).__name__
            self._record(server_prefix, tool_name, latency_ms, success=False)

            logger.error(
                "mcp.call.error",
                tool=tool_name,
                server=server_prefix,
                error_type=error_type,
                error=str(e),
                latency_ms=round(latency_ms, 1),
            )

            # Prometheus 메트릭
            from app.monitoring.metrics import inc_mcp_error
            inc_mcp_error(server_prefix, error_type)

            # 연속 실패 경고
            stats = self._stats.get(server_prefix, {})
            consecutive = stats.get("consecutive_errors", 0)
            if consecutive >= 3:
                logger.warning(
                    "mcp.circuit_breaker_warning",
                    server=server_prefix,
                    consecutive_errors=consecutive,
                )

            raise

    def _record(
        self,
        server: str,
        tool: str,
        latency_ms: float,
        *,
        success: bool,
    ) -> None:
        if server not in self._stats:
            self._stats[server] = {
                "calls": 0,
                "errors": 0,
                "total_ms": 0.0,
                "consecutive_errors": 0,
            }

        s = self._stats[server]
        s["calls"] += 1
        s["total_ms"] += latency_ms

        if success:
            s["consecutive_errors"] = 0
        else:
            s["errors"] += 1
            s["consecutive_errors"] = s.get("consecutive_errors", 0) + 1

    def get_stats(self) -> dict[str, dict[str, Any]]:
        """서버별 통계를 반환한다."""
        result: dict[str, dict[str, Any]] = {}
        for server, s in self._stats.items():
            calls = s["calls"]
            result[server] = {
                "calls": calls,
                "errors": s["errors"],
                "avg_ms": round(s["total_ms"] / calls, 1) if calls else 0,
                "error_rate": round(s["errors"] / calls, 3) if calls else 0,
            }
        return result

    # 프록시 메서드 — MCPClientRouter 인터페이스 호환
    async def list_tools(self, server_prefix: str | None = None) -> list[dict[str, Any]]:
        return await self._router.list_tools(server_prefix)

    async def health_check(self) -> dict[str, bool]:
        results = await self._router.health_check()
        for server, healthy in results.items():
            logger.info("mcp.health", server=server, healthy=healthy)
        return results

    async def close(self) -> None:
        await self._router.close()
