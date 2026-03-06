"""Memory service for short-term and long-term agent memory."""

from __future__ import annotations

import json
from math import sqrt
from typing import Any

import redis.asyncio as redis
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.extended import AgentMemory
from app.llm.openai_client import generate_embedding
from app.monitoring.logging import StructuredLogger


logger = StructuredLogger(__name__)


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity with safe zero guards."""
    if not vec_a or not vec_b:
        return 0.0
    size = min(len(vec_a), len(vec_b))
    a = vec_a[:size]
    b = vec_b[:size]
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = sqrt(sum(x * x for x in a))
    mag_b = sqrt(sum(y * y for y in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


class MemoryService:
    """Service layer for conversation memory and semantic retrieval."""

    def __init__(self) -> None:
        self._redis_client: redis.Redis | None = None

    async def _get_redis(self) -> redis.Redis:
        if self._redis_client is None:
            self._redis_client = await redis.from_url(settings.REDIS_URL, decode_responses=True)
        return self._redis_client

    async def store_memory(
        self,
        db: Session,
        tenant_id: str,
        agent_id: str,
        execution_id: str,
        role: str,
        content: str,
        store_long_term: bool = True,
    ) -> None:
        """Store short-term memory in Redis and optionally long-term in DB."""
        key = f"memory:execution:{execution_id}"
        payload = {"role": role, "content": content}

        try:
            redis_client = await self._get_redis()
            await redis_client.rpush(key, json.dumps(payload))
            await redis_client.ltrim(key, -100, -1)
            await redis_client.expire(key, 7 * 24 * 60 * 60)
        except Exception as exc:
            logger.log_error("Short-term memory store failed", {"error": str(exc), "execution_id": execution_id})

        if not store_long_term:
            return

        try:
            embedding = generate_embedding(content, model=settings.OPENAI_EMBEDDING_MODEL)
            row = AgentMemory(
                tenant_id=tenant_id,
                agent_id=agent_id,
                content=content,
                embedding=embedding,
            )
            db.add(row)
            db.flush()
        except Exception as exc:
            logger.log_error(
                "Long-term memory store failed",
                {"error": str(exc), "agent_id": agent_id, "tenant_id": tenant_id},
            )

    async def retrieve_memory(self, execution_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Retrieve short-term conversation memory by execution id."""
        key = f"memory:execution:{execution_id}"
        try:
            redis_client = await self._get_redis()
            items = await redis_client.lrange(key, -limit, -1)
            return [json.loads(item) for item in items]
        except Exception as exc:
            logger.log_error("Short-term memory retrieval failed", {"error": str(exc), "execution_id": execution_id})
            return []

    def retrieve_similar_memories(
        self,
        db: Session,
        tenant_id: str,
        agent_id: str,
        query: str,
        limit: int = 5,
    ) -> list[AgentMemory]:
        """Retrieve most similar long-term memories for prompt augmentation."""
        try:
            query_embedding = generate_embedding(query, model=settings.OPENAI_EMBEDDING_MODEL)
        except Exception as exc:
            logger.log_error("Embedding generation for retrieval failed", {"error": str(exc)})
            return []

        candidates = (
            db.query(AgentMemory)
            .filter(AgentMemory.tenant_id == tenant_id, AgentMemory.agent_id == agent_id)
            .order_by(AgentMemory.created_at.desc())
            .limit(100)
            .all()
        )

        scored: list[tuple[float, AgentMemory]] = []
        for memory in candidates:
            embedding = memory.embedding if isinstance(memory.embedding, list) else []
            score = _cosine_similarity(query_embedding, embedding)
            scored.append((score, memory))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in scored[:limit] if item[0] > 0]
