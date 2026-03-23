"""API analysis 라우트 단위 테스트 — RedisBroker를 Mock으로 대체."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from marketscope_api.routes.analysis import _broker, init_broker, close_broker


@pytest.fixture
def mock_broker():
    """Mock RedisBroker."""
    broker = AsyncMock()
    broker.publish_request = AsyncMock(return_value="stream-id-001")
    broker.get_status = AsyncMock(return_value=None)
    broker.get_result = AsyncMock(return_value=None)
    broker.subscribe_progress = AsyncMock()
    broker.connect = AsyncMock()
    broker.close = AsyncMock()
    return broker


@pytest.fixture
def app_with_broker(mock_broker):
    """RedisBroker를 주입한 FastAPI app."""
    import marketscope_api.routes.analysis as analysis_module
    # broker를 직접 주입
    original = analysis_module._broker
    analysis_module._broker = mock_broker

    from marketscope_api.main import create_app
    test_app = create_app()

    yield test_app

    analysis_module._broker = original


class TestCreateAnalysis:
    @pytest.mark.asyncio
    async def test_create_returns_202(self, app_with_broker, mock_broker):
        transport = ASGITransport(app=app_with_broker)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/analysis",
                json={"query": "강남역 카페 창업 분석"},
            )
        assert resp.status_code == 202
        data = resp.json()
        assert "request_id" in data
        assert data["status"] == "queued"
        assert data["estimated_duration_sec"] == 180  # standard
        assert "/stream" in data["stream_url"]

    @pytest.mark.asyncio
    async def test_create_calls_publish_request(self, app_with_broker, mock_broker):
        transport = ASGITransport(app=app_with_broker)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                "/api/v1/analysis",
                json={
                    "query": "홍대 음식점 분석",
                    "depth": "deep",
                    "location": "홍대",
                    "industry": "음식점",
                },
            )
        mock_broker.publish_request.assert_awaited_once()
        call_kwargs = mock_broker.publish_request.call_args[1]
        assert call_kwargs["query"] == "홍대 음식점 분석"
        assert call_kwargs["depth"] == "deep"
        assert call_kwargs["location"] == "홍대"

    @pytest.mark.asyncio
    async def test_create_short_query_rejected(self, app_with_broker, mock_broker):
        transport = ASGITransport(app=app_with_broker)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/analysis",
                json={"query": "a"},  # min_length=2
            )
        assert resp.status_code == 422


class TestGetAnalysis:
    @pytest.mark.asyncio
    async def test_get_not_found(self, app_with_broker, mock_broker):
        mock_broker.get_status.return_value = None
        transport = ASGITransport(app=app_with_broker)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/analysis/nonexistent-id")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "ANALYSIS_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_get_in_progress(self, app_with_broker, mock_broker):
        mock_broker.get_status.return_value = {
            "status": "processing",
            "updated_at": "2026-03-22T12:00:00",
        }
        transport = ASGITransport(app=app_with_broker)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/analysis/req-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "processing"
        assert data["request_id"] == "req-001"

    @pytest.mark.asyncio
    async def test_get_completed_includes_result(self, app_with_broker, mock_broker):
        mock_broker.get_status.return_value = {"status": "completed"}
        mock_broker.get_result.return_value = {"score": 85, "grade": "A"}
        transport = ASGITransport(app=app_with_broker)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/analysis/req-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["score"] == 85


class TestStreamAnalysis:
    @pytest.mark.asyncio
    async def test_stream_not_found(self, app_with_broker, mock_broker):
        mock_broker.get_status.return_value = None
        transport = ASGITransport(app=app_with_broker)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/analysis/nonexistent/stream")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_stream_already_completed(self, app_with_broker, mock_broker):
        mock_broker.get_status.return_value = {"status": "completed"}
        transport = ASGITransport(app=app_with_broker)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/analysis/req-done/stream")
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        # 완료 이벤트가 포함되어 있어야 함
        assert "done" in resp.text
