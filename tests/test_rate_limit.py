"""Verifies core/rate_limit.py's per-user rate limiting against a live
Redis (docs roadmap's PR3 verification goal: >N requests/minute from one
user gets a 429 on the (N+1)th, a different user is unaffected).

Requires a live Redis -- skips with a clear reason if unreachable, so
`pytest tests -q` still passes on a machine without the stack running.
Exercises the real dependency end-to-end with minted JWTs rather than
FastAPI's dependency_overrides, since rate_limited_user_id calls
get_current_user_id as a plain function (not a sub-Depends), which
dependency_overrides can't intercept.
"""
import uuid

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from core.auth import create_access_token
from core.cache import get_redis_client
from core.config import get_settings
from core.rate_limit import rate_limited_user_id


def _redis_available() -> bool:
    try:
        get_redis_client().ping()
    except Exception:  # pylint: disable=broad-except
        return False
    return True


pytestmark = pytest.mark.skipif(not _redis_available(), reason="requires a live Redis (docker compose up redis)")

app = FastAPI()


@app.get("/ping")
def ping(uid: str = Depends(rate_limited_user_id)):
    return {"user_id": uid}


def _auth_headers(user_id: str) -> dict:
    token = create_access_token(user_id, f"{user_id}@test.local")
    return {"Authorization": f"Bearer {token}"}


def test_rate_limit_blocks_after_threshold():
    user_id = str(uuid.uuid4())
    client = TestClient(app)
    settings = get_settings()
    headers = _auth_headers(user_id)

    statuses = [client.get("/ping", headers=headers).status_code for _ in range(settings.rate_limit_requests_per_minute + 1)]

    assert statuses[: settings.rate_limit_requests_per_minute] == [200] * settings.rate_limit_requests_per_minute
    assert statuses[-1] == 429


def test_rate_limit_is_per_user():
    settings = get_settings()
    client = TestClient(app)
    user_a = str(uuid.uuid4())
    user_b = str(uuid.uuid4())

    headers_a = _auth_headers(user_a)
    for _ in range(settings.rate_limit_requests_per_minute):
        assert client.get("/ping", headers=headers_a).status_code == 200
    assert client.get("/ping", headers=headers_a).status_code == 429

    headers_b = _auth_headers(user_b)
    assert client.get("/ping", headers=headers_b).status_code == 200
