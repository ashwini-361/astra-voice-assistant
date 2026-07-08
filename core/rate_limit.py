"""Per-user rate limiting, built on core/cache.py's generic Redis wrapper.

Enforced locally per-service via the shared JWT-derived user_id, not
centralized in the gateway (ADR-007's "gateway is auth-only, not a
proxy" decision). Replaces core.auth.get_current_user_id as the auth
dependency on every route -- it calls get_current_user_id itself, so
callers still get the same user_id return value, with rate limiting
layered on top rather than duplicated as a second dependency.

Fails open on Redis errors: ADR-007 deliberately kept JWT auth I/O-free
(in-process decode only) specifically so whisper/llm/tts/intent don't
gain a shared stateful dependency between the loops. A Redis outage
must not take down the entire authenticated surface for a throttling
feature that is inherently allowed to degrade -- unlimited-rate is a
safe fallback, a hard 500 on every route is not.
"""
import logging
import time

from fastapi import HTTPException, Request
from redis.exceptions import RedisError

from core.auth import get_current_user_id
from core.cache import incr_with_ttl
from core.config import get_settings

logger = logging.getLogger(__name__)


def rate_limited_user_id(request: Request) -> str:
    user_id = get_current_user_id(request)
    settings = get_settings()
    window = int(time.time() // 60)
    key = f"ratelimit:{user_id}:{window}"
    try:
        count = incr_with_ttl(key, ttl_seconds=60)
    except RedisError:
        logger.warning("[rate-limit] Redis unavailable, failing open for user_id=%s", user_id)
        return user_id
    if count > settings.rate_limit_requests_per_minute:
        raise HTTPException(status_code=429, detail="Rate limit exceeded, try again shortly")
    return user_id
