"""Generic Redis wrapper (ADR-007) -- rate limiting (core/rate_limit.py)
is one consumer of this, not the only one. Keep this file free of
rate-limit-specific naming/logic so future consumers (caching,
presence, websocket state) can reuse the same client/helpers.
"""
from functools import lru_cache

import redis

from core.config import get_settings


@lru_cache(maxsize=1)
def get_redis_client() -> redis.Redis:
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def incr_with_ttl(key: str, ttl_seconds: int) -> int:
    """Atomically increment `key`, setting its TTL only the first time it's
    created (Redis 7's `EXPIRE ... NX`) so an existing counter's window
    isn't reset by every increment. Returns the new count."""
    client = get_redis_client()
    count = client.incr(key)
    if count == 1:
        client.expire(key, ttl_seconds)
    return count
