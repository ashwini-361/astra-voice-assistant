"""Verifies core/quota.py's monthly request/token quota enforcement
against a live Postgres (docs roadmap's PR3 verification goal:
simulated usage crossing the monthly quota rejects the next call for
that user while a different user's quota is unaffected).

Requires a live Postgres -- skips with a clear reason if unreachable,
so `pytest tests -q` still passes on a machine without the stack
running.
"""
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from core.quota import _current_period, check_and_increment_quota
from db.models import Conversation, User, UsageCounter
from db.session import get_sync_engine


def _postgres_available() -> bool:
    try:
        with get_sync_engine().connect():
            pass
    except Exception:  # pylint: disable=broad-except
        return False
    return True


pytestmark = pytest.mark.skipif(not _postgres_available(), reason="requires a live Postgres (docker compose up postgres)")


@pytest.fixture
def two_users():
    engine = get_sync_engine()
    user_a_id = uuid.uuid4()
    user_b_id = uuid.uuid4()
    with Session(engine) as session:
        session.add(User(id=user_a_id, email=f"a-{user_a_id}@test.local", provider="local", provider_sub=str(user_a_id)))
        session.add(User(id=user_b_id, email=f"b-{user_b_id}@test.local", provider="local", provider_sub=str(user_b_id)))
        session.commit()

    yield str(user_a_id), str(user_b_id)

    with Session(engine) as session:
        session.query(Conversation).filter(Conversation.user_id.in_([user_a_id, user_b_id])).delete(synchronize_session=False)
        session.query(UsageCounter).filter(UsageCounter.user_id.in_([user_a_id, user_b_id])).delete(synchronize_session=False)
        session.query(User).filter(User.id.in_([user_a_id, user_b_id])).delete(synchronize_session=False)
        session.commit()


def test_quota_rejects_after_monthly_request_limit(two_users):
    user_a, _ = two_users
    engine = get_sync_engine()
    period = _current_period()

    with Session(engine) as session:
        session.add(UsageCounter(user_id=user_a, period=period, llm_tokens_used=0, requests_used=1999))
        session.commit()

    # 2000th request succeeds (at the default quota_max_requests_per_month=2000)
    assert check_and_increment_quota(user_id=user_a) == user_a

    # 2001st request is rejected
    with pytest.raises(HTTPException) as exc_info:
        check_and_increment_quota(user_id=user_a)
    assert exc_info.value.status_code == 429


def test_quota_is_independent_per_user(two_users):
    user_a, user_b = two_users
    engine = get_sync_engine()
    period = _current_period()

    with Session(engine) as session:
        session.add(UsageCounter(user_id=user_a, period=period, llm_tokens_used=0, requests_used=2000))
        session.commit()

    with pytest.raises(HTTPException):
        check_and_increment_quota(user_id=user_a)

    # user_b's quota is untouched by user_a's exhaustion
    assert check_and_increment_quota(user_id=user_b) == user_b


def test_quota_rejects_after_monthly_token_limit(two_users):
    user_a, _ = two_users
    engine = get_sync_engine()
    period = _current_period()

    with Session(engine) as session:
        session.add(UsageCounter(user_id=user_a, period=period, llm_tokens_used=200_000, requests_used=0))
        session.commit()

    with pytest.raises(HTTPException) as exc_info:
        check_and_increment_quota(user_id=user_a)
    assert exc_info.value.status_code == 429
