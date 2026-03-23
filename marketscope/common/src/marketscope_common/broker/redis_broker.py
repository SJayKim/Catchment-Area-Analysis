"""Redis 기반 서비스 간 통신 브로커.

API ↔ Engine 간 통신을 Redis Stream, Pub/Sub, Hash로 처리.

사용 패턴:
- API → Engine: Redis Stream (analysis:requests)
- Engine → API: Redis Pub/Sub (analysis:progress:{request_id})
- 결과 저장: Redis Hash (analysis:result:{request_id})
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import redis.asyncio as aioredis

logger = logging.getLogger("engine.redis_broker")

# Redis 키 접두사
STREAM_KEY = "analysis:requests"
CONSUMER_GROUP = "engine-workers"
PROGRESS_CHANNEL_PREFIX = "analysis:progress:"
RESULT_KEY_PREFIX = "analysis:result:"
STATUS_KEY_PREFIX = "analysis:status:"

# 결과 TTL (1시간)
RESULT_TTL_SECONDS = 3600


class RedisBroker:
    """Redis 기반 메시지 브로커."""

    def __init__(self, redis_url: str = "redis://localhost:6379/0") -> None:
        self._redis_url = redis_url
        self._pool: aioredis.Redis | None = None

    async def connect(self) -> None:
        """Redis 연결 및 Consumer Group 초기화."""
        self._pool = aioredis.from_url(
            self._redis_url,
            decode_responses=True,
            max_connections=20,
        )
        # Consumer Group 생성 (이미 있으면 무시)
        try:
            await self._pool.xgroup_create(
                STREAM_KEY, CONSUMER_GROUP, id="0", mkstream=True,
            )
            logger.info("Redis Stream Consumer Group 생성: %s", CONSUMER_GROUP)
        except aioredis.ResponseError as e:
            if "BUSYGROUP" in str(e):
                logger.debug("Consumer Group 이미 존재: %s", CONSUMER_GROUP)
            else:
                raise

    async def close(self) -> None:
        """Redis 연결 종료."""
        if self._pool:
            await self._pool.aclose()
            self._pool = None

    @property
    def redis(self) -> aioredis.Redis:
        if self._pool is None:
            raise RuntimeError("RedisBroker not connected. Call connect() first.")
        return self._pool

    # -----------------------------------------------------------------------
    # API → Engine: 분석 요청 발행
    # -----------------------------------------------------------------------

    async def publish_request(
        self,
        request_id: str,
        query: str,
        depth: str = "standard",
        location: str = "",
        industry: str = "",
    ) -> str:
        """분석 요청을 Redis Stream에 발행."""
        message = {
            "request_id": request_id,
            "query": query,
            "depth": depth,
            "location": location,
            "industry": industry,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        stream_id = await self.redis.xadd(STREAM_KEY, message)
        await self.update_status(request_id, "queued", query=query, depth=depth)
        logger.info("분석 요청 발행: %s (stream_id=%s)", request_id, stream_id)
        return stream_id

    # -----------------------------------------------------------------------
    # Engine: 분석 요청 수신 (blocking)
    # -----------------------------------------------------------------------

    async def consume_requests(
        self,
        consumer_name: str = "worker-1",
        block_ms: int = 5000,
    ) -> AsyncIterator[dict[str, Any]]:
        """Redis Stream에서 분석 요청을 블로킹 수신."""
        while True:
            try:
                results = await self.redis.xreadgroup(
                    CONSUMER_GROUP,
                    consumer_name,
                    {STREAM_KEY: ">"},
                    count=1,
                    block=block_ms,
                )
                if not results:
                    continue

                for _stream_name, messages in results:
                    for msg_id, data in messages:
                        data["_stream_id"] = msg_id
                        yield data
                        # ACK 처리
                        await self.redis.xack(STREAM_KEY, CONSUMER_GROUP, msg_id)

            except aioredis.ConnectionError:
                logger.warning("Redis 연결 끊김, 재시도...")
                import asyncio
                await asyncio.sleep(1)
            except Exception:
                logger.exception("Stream 수신 오류")
                import asyncio
                await asyncio.sleep(1)

    # -----------------------------------------------------------------------
    # Engine → API: 진행률 발행
    # -----------------------------------------------------------------------

    async def publish_progress(
        self,
        request_id: str,
        event: dict[str, Any],
    ) -> None:
        """진행률 이벤트를 Pub/Sub으로 발행."""
        channel = f"{PROGRESS_CHANNEL_PREFIX}{request_id}"
        await self.redis.publish(channel, json.dumps(event, ensure_ascii=False))

    # -----------------------------------------------------------------------
    # API: 진행률 구독 (SSE용)
    # -----------------------------------------------------------------------

    async def subscribe_progress(
        self,
        request_id: str,
    ) -> AsyncIterator[dict[str, Any]]:
        """Pub/Sub에서 진행률 이벤트를 수신."""
        channel = f"{PROGRESS_CHANNEL_PREFIX}{request_id}"
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(channel)

        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])
                    yield data
                    # "done" 또는 "error" 이벤트면 종료
                    if data.get("type") in ("done", "error"):
                        break
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    # -----------------------------------------------------------------------
    # 결과 저장/조회
    # -----------------------------------------------------------------------

    async def store_result(
        self,
        request_id: str,
        result: dict[str, Any],
    ) -> None:
        """분석 결과를 Redis Hash에 저장."""
        key = f"{RESULT_KEY_PREFIX}{request_id}"
        await self.redis.set(
            key,
            json.dumps(result, ensure_ascii=False, default=str),
            ex=RESULT_TTL_SECONDS,
        )
        await self.update_status(request_id, "completed")
        logger.info("분석 결과 저장: %s", request_id)

    async def get_result(self, request_id: str) -> dict[str, Any] | None:
        """Redis에서 분석 결과 조회."""
        key = f"{RESULT_KEY_PREFIX}{request_id}"
        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return None

    # -----------------------------------------------------------------------
    # 상태 관리
    # -----------------------------------------------------------------------

    async def update_status(
        self,
        request_id: str,
        status: str,
        **extra: Any,
    ) -> None:
        """분석 상태 업데이트."""
        key = f"{STATUS_KEY_PREFIX}{request_id}"
        fields = {
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            **{k: str(v) for k, v in extra.items()},
        }
        await self.redis.hset(key, mapping=fields)
        await self.redis.expire(key, RESULT_TTL_SECONDS)

    async def get_status(self, request_id: str) -> dict[str, str] | None:
        """분석 상태 조회."""
        key = f"{STATUS_KEY_PREFIX}{request_id}"
        data = await self.redis.hgetall(key)
        return data if data else None
