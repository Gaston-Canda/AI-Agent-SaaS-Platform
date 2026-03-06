"""Phase 3 test configuration with minimal runtime dependencies."""

from __future__ import annotations

import os
import pytest


os.environ.setdefault("DEBUG", "false")
os.environ.setdefault("DATABASE_URL", "sqlite:///phase3_tests.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")


class FakeRedis:
    """Small async Redis fake for memory components."""

    def __init__(self) -> None:
        self._hashes: dict[str, dict[str, str]] = {}
        self._lists: dict[str, list[str]] = {}

    async def hset(self, key: str, field: str, value: str) -> None:
        self._hashes.setdefault(key, {})[field] = value

    async def hgetall(self, key: str) -> dict[str, str]:
        return dict(self._hashes.get(key, {}))

    async def hlen(self, key: str) -> int:
        return len(self._hashes.get(key, {}))

    async def rpush(self, key: str, value: str) -> None:
        self._lists.setdefault(key, []).append(value)

    async def ltrim(self, key: str, start: int, end: int) -> None:
        items = self._lists.get(key, [])
        length = len(items)
        start_idx = max(length + start, 0) if start < 0 else start
        end_idx = (length + end + 1) if end < 0 else (end + 1)
        self._lists[key] = items[start_idx:end_idx]

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        items = self._lists.get(key, [])
        length = len(items)
        start_idx = max(length + start, 0) if start < 0 else start
        end_idx = (length + end + 1) if end < 0 else (end + 1)
        return list(items[start_idx:end_idx])

    async def llen(self, key: str) -> int:
        return len(self._lists.get(key, []))

    async def delete(self, key: str) -> None:
        self._hashes.pop(key, None)
        self._lists.pop(key, None)

    async def expire(self, key: str, seconds: int) -> None:
        _ = (key, seconds)


@pytest.fixture(autouse=True, scope="session")
def patch_redis():
    """Mock Redis client creation for all Phase 3 tests."""
    fake = FakeRedis()

    async def _fake_from_url(*args, **kwargs):
        _ = (args, kwargs)
        return fake

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("redis.asyncio.from_url", _fake_from_url)
    yield fake
    monkeypatch.undo()


@pytest.fixture(autouse=True)
def clear_tool_registry():
    """Keep ToolRegistry isolated between tests."""
    from app.tools.tool_registry import ToolRegistry

    ToolRegistry.clear()
    yield
    ToolRegistry.clear()
