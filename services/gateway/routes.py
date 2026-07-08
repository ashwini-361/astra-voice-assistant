"""Auth routes: OAuth login/callback, JWT refresh/logout, /me.
See docs/api/gateway.md. Not a data-plane proxy -- these are the only
routes this service exposes.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import create_access_token, create_refresh_token, decode_token, get_current_user_id
from core.config import get_settings
from db.models import User
from db.session import get_db
from services.gateway.oauth import fetch_profile, oauth

router = APIRouter(prefix="/api/v1/auth")


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessToken(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserProfile(BaseModel):
    id: str
    email: str
    provider: str
    display_name: str | None
    avatar_url: str | None


@router.get("/login/{provider}")
async def login(provider: str, request: Request):
    if provider not in ("google", "github"):
        raise HTTPException(status_code=404, detail="Unsupported provider")
    client = oauth.create_client(provider)
    settings = get_settings()
    redirect_uri = f"{settings.oauth_redirect_base_url}/api/v1/auth/callback/{provider}"
    return await client.authorize_redirect(request, redirect_uri)


@router.get("/callback/{provider}")
async def callback(provider: str, request: Request, db: AsyncSession = Depends(get_db)):
    if provider not in ("google", "github"):
        raise HTTPException(status_code=404, detail="Unsupported provider")
    client = oauth.create_client(provider)
    token = await client.authorize_access_token(request)
    profile = await fetch_profile(provider, token)

    if not profile.get("email"):
        raise HTTPException(status_code=400, detail="Provider did not return an email address")

    result = await db.execute(
        select(User).where(User.provider == provider, User.provider_sub == profile["provider_sub"])
    )
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            email=profile["email"],
            provider=provider,
            provider_sub=profile["provider_sub"],
            display_name=profile.get("display_name"),
            avatar_url=profile.get("avatar_url"),
            last_login_at=datetime.now(timezone.utc),
        )
        db.add(user)
    else:
        user.display_name = profile.get("display_name")
        user.avatar_url = profile.get("avatar_url")
        user.last_login_at = datetime.now(timezone.utc)
    try:
        await db.commit()
    except IntegrityError as exc:
        # email is UNIQUE across all providers; this fires when the same
        # email address logs in via a *different* provider than it first
        # registered with (e.g. Google first, GitHub later, same email).
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists under a different sign-in provider",
        ) from exc
    await db.refresh(user)

    return TokenPair(
        access_token=create_access_token(str(user.id), user.email),
        refresh_token=create_refresh_token(str(user.id), user.email),
    )


@router.post("/refresh")
async def refresh(body: RefreshRequest):
    payload = decode_token(body.refresh_token, expected_type="refresh")
    return AccessToken(access_token=create_access_token(payload["sub"], payload["email"]))


@router.post("/logout")
async def logout():
    """Client-side token discard -- no server-side state to clear (no
    sessions/revocation table, per ADR-007)."""
    return {"status": "logged_out"}


@router.get("/me", response_model=UserProfile)
async def me(user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserProfile(
        id=str(user.id),
        email=user.email,
        provider=user.provider,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
    )
