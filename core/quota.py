"""Per-user, per-month quota enforcement (docs/adr/ADR-007-multiuser-pivot.md).

Applied only to the LLM's generation-heavy routes (/api/v1/chat/completions,
/api/v1/agent/loop) -- not every route, since token/request quotas are
specifically about LLM usage, unlike rate limiting (core/rate_limit.py)
which applies uniformly everywhere. Enforced locally in llm_service.py via
the shared JWT-derived user_id, not centralized in the gateway.

llm_tokens_used is a length-based approximation (chars / 4), not an exact
tokenizer count -- adequate for a local-only, non-billing-critical quota
in this phase; providers don't uniformly return token usage today.
"""
from datetime import datetime, timezone

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import get_settings
from core.rate_limit import rate_limited_user_id
from db.models import UsageCounter
from db.session import get_sync_engine


def _current_period() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _get_or_create_counter(session: Session, user_id: str, period: str) -> UsageCounter:
    counter = session.execute(
        select(UsageCounter).where(UsageCounter.user_id == user_id, UsageCounter.period == period)
    ).scalar_one_or_none()
    if counter is None:
        counter = UsageCounter(user_id=user_id, period=period, llm_tokens_used=0, requests_used=0)
        session.add(counter)
        session.flush()
    return counter


def check_and_increment_quota(user_id: str = Depends(rate_limited_user_id)) -> str:
    """FastAPI dependency: raises 429 if the caller's monthly request or
    token quota is already exhausted, otherwise increments requests_used
    and returns user_id. Token usage is added separately, after
    generation, via record_token_usage() (actual response size isn't
    known until the LLM call completes)."""
    settings = get_settings()
    period = _current_period()
    with Session(get_sync_engine()) as session:
        counter = _get_or_create_counter(session, user_id, period)
        if counter.requests_used >= settings.quota_max_requests_per_month:
            raise HTTPException(status_code=429, detail="Monthly request quota exceeded")
        if counter.llm_tokens_used >= settings.quota_max_tokens_per_month:
            raise HTTPException(status_code=429, detail="Monthly token quota exceeded")
        counter.requests_used += 1
        session.commit()
    return user_id


def record_token_usage(user_id: str, token_count: int) -> None:
    """Best-effort: add token_count to this month's usage after a
    generation completes. Non-fatal if it fails -- quota tracking must
    not break the response path."""
    try:
        period = _current_period()
        with Session(get_sync_engine()) as session:
            counter = _get_or_create_counter(session, user_id, period)
            counter.llm_tokens_used += token_count
            session.commit()
    except Exception:  # pylint: disable=broad-except
        pass
