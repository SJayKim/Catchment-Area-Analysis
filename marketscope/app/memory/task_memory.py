"""TaskMemory - Redis 기반 세션 컨텍스트 메모리."""

from __future__ import annotations

import json
from typing import Any, Optional

from app.logging_config import get_logger

logger = get_logger("memory.task")

_DEFAULT_TTL = 3600  # 1시간


class TaskMemory:
    """현재 분석 세션의 컨텍스트를 Redis에 저장한다.

    세션 종료 시 자동 만료(TTL).
    """

    def __init__(self, redis_client: Any = None, ttl: int = _DEFAULT_TTL) -> None:
        self._redis = redis_client
        self._ttl = ttl
        # Redis 없을 때 인메모리 폴백
        self._fallback: dict[str, list[dict[str, Any]]] = {}

    def _key(self, session_id: str, agent_name: str) -> str:
        return f"task_memory:{session_id}:{agent_name}"

    async def store(
        self,
        session_id: str,
        agent_name: str,
        content: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """세션 컨텍스트를 저장한다."""
        entry = {"content": content, "metadata": metadata or {}}

        if self._redis:
            key = self._key(session_id, agent_name)
            existing = await self._redis.get(key)
            items = json.loads(existing) if existing else []
            items.append(entry)
            await self._redis.set(key, json.dumps(items, ensure_ascii=False), ex=self._ttl)
        else:
            fk = f"{session_id}:{agent_name}"
            self._fallback.setdefault(fk, []).append(entry)

    async def recall(
        self,
        session_id: str,
        agent_name: str,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """세션 컨텍스트를 조회한다."""
        if self._redis:
            key = self._key(session_id, agent_name)
            raw = await self._redis.get(key)
            if raw:
                items = json.loads(raw)
                return items[-top_k:]
            return []

        fk = f"{session_id}:{agent_name}"
        return self._fallback.get(fk, [])[-top_k:]

    async def clear(self, session_id: str) -> None:
        """세션의 모든 메모리를 삭제한다."""
        if self._redis:
            pattern = f"task_memory:{session_id}:*"
            async for key in self._redis.scan_iter(match=pattern):
                await self._redis.delete(key)
        else:
            keys_to_delete = [k for k in self._fallback if k.startswith(f"{session_id}:")]
            for k in keys_to_delete:
                del self._fallback[k]
