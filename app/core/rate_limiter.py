"""Redis-backed rate limiter with memory fallback and endpoint profiles."""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

import redis
from jose import jwt

from app.core.config import settings


@dataclass(frozen=True)
class RateLimitProfile:
    """Rate limit profile for a route group."""

    limit_per_minute: int
    burst: int


class SecurityRateLimiter:
    """Token-bucket limiter with Redis primary storage and memory fallback."""

    def __init__(self) -> None:
        try:
            self.redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        except Exception:
            self.redis_client = None

        self._memory_buckets: dict[str, dict[str, float]] = defaultdict(
            lambda: {"tokens": 0.0, "updated_at": time.time()}
        )

    def get_profile(self, path: str) -> RateLimitProfile | None:
        lowered = path.lower()
        if lowered.startswith("/api/auth"):
            return RateLimitProfile(limit_per_minute=settings.RATE_LIMIT_AUTH_PER_MINUTE, burst=5)
        if lowered.startswith("/api/agents/") and ("/execute" in lowered):
            return RateLimitProfile(
                limit_per_minute=settings.RATE_LIMIT_EXECUTE_PER_MINUTE,
                burst=settings.RATE_LIMIT_EXECUTE_BURST,
            )
        if lowered.startswith("/api/agents"):
            return RateLimitProfile(limit_per_minute=settings.RATE_LIMIT_AGENTS_PER_MINUTE, burst=20)
        return None

    def build_subjects(self, auth_header: str | None, path: str, remote_addr: str) -> list[str]:
        claims = self._decode_claims_without_validation(auth_header)
        tenant_id = claims.get("tenant_id")
        user_id = claims.get("sub")

        subjects = []
        if tenant_id:
            subjects.append(f"tenant:{tenant_id}:{path}")
        if user_id:
            subjects.append(f"user:{user_id}:{path}")
        if not subjects:
            subjects.append(f"ip:{remote_addr}:{path}")
        return subjects

    def is_allowed(self, key: str, profile: RateLimitProfile) -> tuple[bool, int]:
        if self.redis_client:
            try:
                return self._check_redis(key, profile)
            except Exception:
                pass
        return self._check_memory(key, profile)

    def _check_redis(self, key: str, profile: RateLimitProfile) -> tuple[bool, int]:
        redis_key = f"ratelimit:v2:{key}"
        now = time.time()
        refill_rate = profile.limit_per_minute / 60.0

        script = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local capacity = tonumber(ARGV[2])
local refill_rate = tonumber(ARGV[3])

local data = redis.call('HMGET', key, 'tokens', 'updated_at')
local tokens = tonumber(data[1])
local updated_at = tonumber(data[2])

if tokens == nil then
  tokens = capacity
end
if updated_at == nil then
  updated_at = now
end

local elapsed = now - updated_at
if elapsed < 0 then
  elapsed = 0
end

tokens = math.min(capacity, tokens + (elapsed * refill_rate))
local allowed = 0
if tokens >= 1 then
  tokens = tokens - 1
  allowed = 1
end

redis.call('HMSET', key, 'tokens', tokens, 'updated_at', now)
redis.call('EXPIRE', key, 120)
return {allowed, math.floor(tokens)}
"""
        allowed, remaining = self.redis_client.eval(  # type: ignore[union-attr]
            script,
            1,
            redis_key,
            now,
            float(profile.burst),
            refill_rate,
        )
        return bool(int(allowed)), int(remaining)

    def _check_memory(self, key: str, profile: RateLimitProfile) -> tuple[bool, int]:
        bucket = self._memory_buckets[key]
        now = time.time()
        refill_rate = profile.limit_per_minute / 60.0

        tokens = bucket["tokens"]
        updated_at = bucket["updated_at"]
        elapsed = max(0.0, now - updated_at)

        tokens = min(float(profile.burst), tokens + elapsed * refill_rate)
        allowed = tokens >= 1.0
        if allowed:
            tokens -= 1.0

        bucket["tokens"] = tokens
        bucket["updated_at"] = now
        return allowed, int(tokens)

    def _decode_claims_without_validation(self, auth_header: str | None) -> dict[str, Any]:
        if not auth_header:
            return {}
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return {}
        token = parts[1]
        try:
            return jwt.get_unverified_claims(token)
        except Exception:
            return {}
