"""도구 레지스트리."""

from __future__ import annotations

from typing import Any, Callable, Optional


class ToolRegistry:
    """MCP 도구 레지스트리 - 에이전트별 사용 가능 도구 관리."""

    def __init__(self) -> None:
        self._tools: dict[str, dict[str, Any]] = {}

    def register(
        self,
        name: str,
        description: str,
        server: str,
        parameters: Optional[dict[str, Any]] = None,
    ) -> None:
        self._tools[name] = {
            "name": name,
            "description": description,
            "server": server,
            "parameters": parameters or {},
        }

    def get_tools_for_agent(self, agent_name: str) -> list[dict[str, Any]]:
        agent_tool_map = {
            "population": [
                "public_data.get_seoul_living_population",
                "public_data.get_floating_population",
                "public_data.get_resident_population",
                "public_data.get_worker_population",
                "maps.geocode",
            ],
            "revenue": [
                "public_data.get_commercial_revenue",
                "public_data.get_industry_revenue",
                "maps.geocode",
            ],
            "competition": [
                "public_data.get_store_count",
                "public_data.get_store_openclose",
                "maps.geocode",
                "maps.search_nearby",
            ],
            "location": [
                "maps.geocode",
                "maps.search_nearby",
                "maps.get_transit_info",
            ],
        }
        tool_names = agent_tool_map.get(agent_name, [])
        return [self._tools[n] for n in tool_names if n in self._tools]

    def list_all(self) -> list[str]:
        return list(self._tools.keys())


# 싱글톤 인스턴스
tool_registry = ToolRegistry()
