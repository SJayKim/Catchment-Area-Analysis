"""MCPClientRouter 단위 테스트."""

import pytest

from app.tools.mcp_client import MCPClientRouter


class TestResolveServer:
    def test_maps_prefix(self, mock_settings):
        router = MCPClientRouter(mock_settings)
        prefix, name = router._resolve_server("maps.geocode")
        assert prefix == "maps"
        assert name == "geocode"

    def test_public_data_prefix(self, mock_settings):
        router = MCPClientRouter(mock_settings)
        prefix, name = router._resolve_server("public_data.get_floating_population")
        assert prefix == "public_data"
        assert name == "get_floating_population"

    def test_finance_prefix(self, mock_settings):
        router = MCPClientRouter(mock_settings)
        prefix, name = router._resolve_server("finance.search_startup_loans")
        assert prefix == "finance"
        assert name == "search_startup_loans"

    def test_database_prefix(self, mock_settings):
        router = MCPClientRouter(mock_settings)
        prefix, name = router._resolve_server("database.query_nearby_stores")
        assert prefix == "database"
        assert name == "query_nearby_stores"

    def test_google_maps_prefix(self, mock_settings):
        router = MCPClientRouter(mock_settings)
        prefix, name = router._resolve_server("google_maps.google_geocode")
        assert prefix == "google_maps"
        assert name == "google_geocode"

    def test_naver_maps_prefix(self, mock_settings):
        router = MCPClientRouter(mock_settings)
        prefix, name = router._resolve_server("naver_maps.naver_geocode")
        assert prefix == "naver_maps"
        assert name == "naver_geocode"

    def test_no_prefix_defaults_to_public_data(self, mock_settings):
        router = MCPClientRouter(mock_settings)
        prefix, name = router._resolve_server("get_some_data")
        assert prefix == "public_data"
        assert name == "get_some_data"

    def test_unknown_prefix_defaults_to_public_data(self, mock_settings):
        router = MCPClientRouter(mock_settings)
        prefix, name = router._resolve_server("unknown_server.some_tool")
        assert prefix == "public_data"
        assert name == "unknown_server.some_tool"

    def test_all_nine_servers_resolvable(self, mock_settings):
        router = MCPClientRouter(mock_settings)
        servers = [
            "public_data", "maps", "real_estate", "news", "regulatory",
            "finance", "database", "google_maps", "naver_maps",
        ]
        for server in servers:
            prefix, name = router._resolve_server(f"{server}.test_tool")
            assert prefix == server, f"{server} routing failed"
            assert name == "test_tool"


class TestGetClient:
    def test_creates_client_for_known_server(self, mock_settings):
        router = MCPClientRouter(mock_settings)
        client = router._get_client("maps")
        assert client.base_url == "http://localhost:5101"

    def test_lazy_creates_once(self, mock_settings):
        router = MCPClientRouter(mock_settings)
        c1 = router._get_client("maps")
        c2 = router._get_client("maps")
        assert c1 is c2  # 같은 인스턴스

    def test_different_servers_different_clients(self, mock_settings):
        router = MCPClientRouter(mock_settings)
        c_maps = router._get_client("maps")
        c_finance = router._get_client("finance")
        assert c_maps is not c_finance
        assert c_maps.base_url == "http://localhost:5101"
        assert c_finance.base_url == "http://localhost:5105"

    def test_unknown_server_raises(self, mock_settings):
        router = MCPClientRouter(mock_settings)
        from app.tools.mcp_client import MCPClientError
        with pytest.raises(MCPClientError):
            router._get_client("nonexistent_server")
