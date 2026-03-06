"""
Rate limiting per tenant.
"""

import time
from typing import Dict, Tuple
from collections import defaultdict
import redis
from app.core.config import settings


class RateLimiter:
    """Token bucket rate limiter for tenants."""
    
    def __init__(self):
        try:
            self.redis_client = redis.from_url(settings.REDIS_URL)
        except Exception:
            self.redis_client = None
        
        # In-memory fallback
        self.memory_buckets: Dict[str, Dict[str, any]] = defaultdict(
            lambda: {"tokens": 100, "last_refill": time.time()}
        )
    
    def is_allowed(
        self,
        tenant_id: str,
        executions_per_minute: int = 10,
    ) -> Tuple[bool, int]:
        """
        Check if execution is allowed for tenant.
        
        Returns: (allowed, remaining_tokens)
        """
        if self.redis_client:
            return self._check_redis(tenant_id, executions_per_minute)
        else:
            return self._check_memory(tenant_id, executions_per_minute)
    
    def _check_redis(self, tenant_id: str, limit: int) -> Tuple[bool, int]:
        """Check rate limit using Redis."""
        key = f"ratelimit:{tenant_id}"
        
        try:
            current = self.redis_client.incr(key)
            
            if current == 1:
                # First request in window, set expiry
                self.redis_client.expire(key, 60)  # 1 minute window
            
            remaining = max(0, limit - current)
            allowed = current <= limit
            
            return allowed, remaining
            
        except Exception:
            # Fail open if Redis is unavailable
            return True, limit
    
    def _check_memory(self, tenant_id: str, limit: int) -> Tuple[bool, int]:
        """Check rate limit using in-memory storage."""
        bucket = self.memory_buckets[tenant_id]
        now = time.time()
        
        # Refill tokens based on time elapsed
        time_elapsed = now - bucket["last_refill"]
        refill_rate = limit / 60  # tokens per second
        
        bucket["tokens"] = min(
            limit,
            bucket["tokens"] + (time_elapsed * refill_rate),
        )
        bucket["last_refill"] = now
        
        # Check if we have tokens available
        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            return True, int(bucket["tokens"])
        
        return False, 0
