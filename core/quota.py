"""Per-user, per-month quota enforcement (docs/adr/ADR-007-multiuser-pivot.md).

Applied only to the LLM's generation-heavy routes (/api/v1/chat/completions,
/api/v1/agent/loop) -- not every route, since token/request quotas are
specifically about LLM usage, unlike rate limiting (core/rate_limit.py)
which applies uniformly everywhere. Enforced locally in llm_service.py via
the shared JWT-derived user_id, not centralized in the gateway.

llm_tokens_used is a length-based approximation (chars / 4), not an exact
tokenizer count -- adequate for a local-only, non-billing-critical quota
in this phase; providers don't uniformly return token usage today.

Row creation and increments are both done as single atomic SQL statements
(INSERT ... ON CONFLICT DO NOTHING, UPDATE ... WHERE ... RETURNING) rather
than a Python-level select-then-check-then-write -- the latter is exactly
the TOCTOU race PR2 already hit once with the reserved-user bootstrap
(see db/migrations/versions/76936a1ecf9d_seed_reserved_local_user.py):
concurrent requests from the same user could otherwise both pass a
Python-side quota check before either commits, or both try to INSERT
the first-ever row for a (user_id, period) and raise a duplicate-key error.
"""
from datetime import datetime, timezone

from fastapi import Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from core.config import get_settings
from core.rate_limit import rate_limited_user_id
from db.models import UsageCounter
from db.session import get_sync_engine
from services.llm_metrics import estimate_tokens

__all__ = ["check_and_increment_quota", "record_token_usage", "estimate_tokens"]


def _current_period() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _ensure_counter_row(session: Session, user_id: str, period: str) -> None:
    stmt = pg_insert(UsageCounter).values(user_id=user_id, period=period, llm_tokens_used=0, requests_used=0)
    stmt = stmt.on_conflict_do_nothing(index_elements=["user_id", "period"])
    session.execute(stmt)


def check_and_increment_quota(user_id: str = Depends(rate_limited_user_id)) -> str:
    """FastAPI dependency: raises 429 if the caller's monthly request or
    token quota is already exhausted, otherwise atomically increments
    requests_used and returns user_id. Token usage is added separately,
    after generation, via record_token_usage() (actual response size
    isn't known until the LLM call completes).

    Fails open on Postgres errors, same rationale as core/rate_limit.py:
    a DB blip must not take down chat/agent generation entirely."""
    settings = get_settings()
    period = _current_period()
    try:
        with Session(get_sync_engine()) as session:
            _ensure_counter_row(session, user_id, period)
            session.commit()

            result = session.execute(
                text(
                    "UPDATE usage_counters SET requests_used = requests_used + 1 "
                    "WHERE user_id = :user_id AND period = :period "
                    "AND requests_used < :max_requests AND llm_tokens_used < :max_tokens "
                    "RETURNING requests_used"
                ),
                {
                    "user_id": user_id,
                    "period": period,
                    "max_requests": settings.quota_max_requests_per_month,
                    "max_tokens": settings.quota_max_tokens_per_month,
                },
            )
            row = result.fetchone()
            session.commit()
    except Exception:  # pylint: disable=broad-except
        return user_id

    if row is None:
        raise HTTPException(status_code=429, detail="Monthly request or token quota exceeded")
    return user_id


def record_token_usage(user_id: str, token_count: int) -> None:
    """Best-effort: add token_count to this month's usage after a
    generation completes. Non-fatal if it fails -- quota tracking must
    not break the response path."""
    try:
        period = _current_period()
        with Session(get_sync_engine()) as session:
            _ensure_counter_row(session, user_id, period)
            session.commit()
            session.execute(
                text(
                    "UPDATE usage_counters SET llm_tokens_used = llm_tokens_used + :token_count "
                    "WHERE user_id = :user_id AND period = :period"
                ),
                {"token_count": token_count, "user_id": user_id, "period": period},
            )
            session.commit()
    except Exception:  # pylint: disable=broad-except
        pass
