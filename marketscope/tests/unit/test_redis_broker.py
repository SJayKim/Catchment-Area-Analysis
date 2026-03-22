"""Redis Broker 단위 테스트 — redis.asyncio를 Mock으로 대체."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.engine.redis_broker import (
    CONSUMER_GROUP,
    PROGRESS_CHANNEL_PREFIX,
    RESULT_KEY_PREFIX,
    RESULT_TTL_SECONDS,
    STATUS_KEY_PREFIX,
    STREAM_KEY,
    RedisBroker,
)


@pytest.fixture
def broker():
    return RedisBroker(redis_url="redis://localhost:6379/0")


@pytest.fixture
def mock_redis():
    """AsyncMock Redis 클라이언트."""
    r = AsyncMock()
    r.xadd = AsyncMock(return_value="1234567890-0")
    r.xreadgroup = AsyncMock(return_value=[])
    r.xack = AsyncMock()
    r.xgroup_create = AsyncMock()
    r.publish = AsyncMock()
    r.set = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.hset = AsyncMock()
    r.hgetall = AsyncMock(return_value={})
    r.expire = AsyncMock()
    r.aclose = AsyncMock()
    r.pubsub = MagicMock()
    return r


@pytest.fixture
def connected_broker(broker, mock_redis):
    """연결된 상태의 broker (mock redis 주입)."""
    broker._pool = mock_redis
    return broker


class TestRedisBrokerConnection:
    def test_redis_property_raises_before_connect(self, broker):
        with pytest.raises(RuntimeError, match="not connected"):
            _ = broker.redis

    def test_redis_property_returns_pool(self, connected_broker, mock_redis):
        assert connected_broker.redis is mock_redis

    @pytest.mark.asyncio
    async def test_close(self, connected_broker, mock_redis):
        await connected_broker.close()
        mock_redis.aclose.assert_awaited_once()
        assert connected_broker._pool is None


class TestPublishRequest:
    @pytest.mark.asyncio
    async def test_publish_request_xadd(self, connected_broker, mock_redis):
        stream_id = await connected_broker.publish_request(
            request_id="req-001",
            query="강남역 카페 분석",
            depth="standard",
        )
        assert stream_id == "1234567890-0"

        # XADD 호출 검증
        mock_redis.xadd.assert_awaited_once()
        call_args = mock_redis.xadd.call_args
        assert call_args[0][0] == STREAM_KEY
        msg = call_args[0][1]
        assert msg["request_id"] == "req-001"
        assert msg["query"] == "강남역 카페 분석"
        assert msg["depth"] == "standard"

    @pytest.mark.asyncio
    async def test_publish_request_updates_status(self, connected_broker, mock_redis):
        await connected_broker.publish_request(
            request_id="req-002",
            query="홍대 음식점",
        )
        # update_status가 hset을 호출했는지 확인
        mock_redis.hset.assert_awaited()
        call_args = mock_redis.hset.call_args
        key = call_args[0][0]
        assert key == STATUS_KEY_PREFIX + "req-002"


class TestPublishProgress:
    @pytest.mark.asyncio
    async def test_publish_progress(self, connected_broker, mock_redis):
        event = {"type": "status", "message": "분석 중"}
        await connected_broker.publish_progress("req-001", event)

        mock_redis.publish.assert_awaited_once()
        channel = mock_redis.publish.call_args[0][0]
        data = mock_redis.publish.call_args[0][1]
        assert channel == f"{PROGRESS_CHANNEL_PREFIX}req-001"
        assert json.loads(data) == event


class TestStoreAndGetResult:
    @pytest.mark.asyncio
    async def test_store_result(self, connected_broker, mock_redis):
        result = {"score": 85, "grade": "A"}
        await connected_broker.store_result("req-001", result)

        mock_redis.set.assert_awaited_once()
        key = mock_redis.set.call_args[0][0]
        assert key == f"{RESULT_KEY_PREFIX}req-001"
        stored = json.loads(mock_redis.set.call_args[0][1])
        assert stored["score"] == 85

    @pytest.mark.asyncio
    async def test_get_result_found(self, connected_broker, mock_redis):
        mock_redis.get.return_value = json.dumps({"score": 85})
        result = await connected_broker.get_result("req-001")
        assert result == {"score": 85}

    @pytest.mark.asyncio
    async def test_get_result_not_found(self, connected_broker, mock_redis):
        mock_redis.get.return_value = None
        result = await connected_broker.get_result("req-999")
        assert result is None


class TestStatusManagement:
    @pytest.mark.asyncio
    async def test_update_status(self, connected_broker, mock_redis):
        await connected_broker.update_status("req-001", "processing")

        mock_redis.hset.assert_awaited_once()
        call_kwargs = mock_redis.hset.call_args
        key = call_kwargs[0][0]
        mapping = call_kwargs[1]["mapping"]
        assert key == f"{STATUS_KEY_PREFIX}req-001"
        assert mapping["status"] == "processing"

    @pytest.mark.asyncio
    async def test_get_status_found(self, connected_broker, mock_redis):
        mock_redis.hgetall.return_value = {"status": "completed", "updated_at": "2026-03-22T12:00:00"}
        status = await connected_broker.get_status("req-001")
        assert status["status"] == "completed"

    @pytest.mark.asyncio
    async def test_get_status_not_found(self, connected_broker, mock_redis):
        mock_redis.hgetall.return_value = {}
        status = await connected_broker.get_status("req-999")
        assert status is None


class TestSubscribeProgress:
    @pytest.mark.asyncio
    async def test_subscribe_progress_receives_and_stops_on_done(self, connected_broker, mock_redis):
        """done 이벤트 수신 시 구독 종료."""
        mock_pubsub = AsyncMock()
        mock_redis.pubsub.return_value = mock_pubsub

        # listen()이 3개 메시지를 반환하도록 설정
        messages = [
            {"type": "message", "data": json.dumps({"type": "status", "message": "시작"})},
            {"type": "message", "data": json.dumps({"type": "status", "message": "진행 중"})},
            {"type": "message", "data": json.dumps({"type": "done", "message": "완료"})},
        ]

        async def mock_listen():
            for msg in messages:
                yield msg

        mock_pubsub.listen = mock_listen
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.unsubscribe = AsyncMock()
        mock_pubsub.aclose = AsyncMock()

        events = []
        async for event in connected_broker.subscribe_progress("req-001"):
            events.append(event)

        assert len(events) == 3
        assert events[0]["type"] == "status"
        assert events[2]["type"] == "done"
        mock_pubsub.unsubscribe.assert_awaited()
