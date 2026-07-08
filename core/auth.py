"""Shared JWT validation, used by every service (gateway, whisper, llm, tts,
intent). Pure in-process decode/verify -- no network call, no DB hit -- so
it adds negligible latency to the hot voice-loop path. See docs/api/auth.md.
"""
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, Request

from core.config import get_settings

JWT_ALGORITHM = "HS256"

# Reserved user id for the native, no-OAuth-login dev/CLI path (voice loop,
# manual scripts, seed/smoke-test) -- decided once here, not scattered
# across callers. The row itself is seeded in Postgres in a later Phase C
# PR; minting a token for this id doesn't require the row to exist yet,
# since only /api/v1/auth/me does a DB lookup -- every other service's
# get_current_user_id() only decodes the JWT.
LOCAL_USER_ID = "00000000-0000-0000-0000-000000000000"
LOCAL_USER_EMAIL = "local@astra.local"


def create_local_service_token() -> str:
    """Mint an access token for the reserved local/native user. Used by
    orchestrator/pipeline.py, duplex/, streaming/, and dev scripts
    (docker/seed.py, docker/smoke_test.py) so the native voice loop and
    tooling keep working without a real OAuth round-trip."""
    return create_access_token(LOCAL_USER_ID, LOCAL_USER_EMAIL)


def create_access_token(user_id: str, email: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_expiry_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str, email: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=settings.jwt_refresh_expiry_days),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_token(token: str, expected_type: str) -> dict:
    """Decode+verify a JWT, checking its `type` claim matches expected_type
    (prevents a refresh token being replayed as an access token or vice
    versa). Raises HTTPException(401) on any failure."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc
    if payload.get("type") != expected_type:
        raise HTTPException(status_code=401, detail="Wrong token type")
    return payload


def get_current_user_id(request: Request) -> str:
    """FastAPI dependency: decode/verify the Authorization header's access
    JWT, return the user_id (sub claim). Raises HTTPException(401) if
    missing, malformed, expired, or wrong-type."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")
    token = auth_header[len("Bearer "):]
    payload = decode_token(token, expected_type="access")
    return str(payload["sub"])
