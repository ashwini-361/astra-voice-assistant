"""OAuth2 client registration for Google/GitHub, via authlib. See
docs/api/gateway.md and docs/adr/ADR-001-auth.md (auth mechanism choice).
"""
from authlib.integrations.starlette_client import OAuth

from core.config import get_settings

_settings = get_settings()

oauth = OAuth()

oauth.register(
    name="google",
    client_id=_settings.oauth_google_client_id,
    client_secret=_settings.oauth_google_client_secret,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

oauth.register(
    name="github",
    client_id=_settings.oauth_github_client_id,
    client_secret=_settings.oauth_github_client_secret,
    access_token_url="https://github.com/login/oauth/access_token",
    authorize_url="https://github.com/login/oauth/authorize",
    api_base_url="https://api.github.com/",
    client_kwargs={"scope": "read:user user:email"},
)


async def fetch_profile(provider: str, token: dict) -> dict:
    """Normalize each provider's profile shape to
    {provider_sub, email, display_name, avatar_url}."""
    client = oauth.create_client(provider)
    if provider == "google":
        userinfo = token.get("userinfo")
        if userinfo is None:
            resp = await client.get("https://openidconnect.googleapis.com/v1/userinfo", token=token)
            userinfo = resp.json()
        return {
            "provider_sub": str(userinfo["sub"]),
            "email": userinfo["email"],
            "display_name": userinfo.get("name"),
            "avatar_url": userinfo.get("picture"),
        }
    if provider == "github":
        profile_resp = await client.get("user", token=token)
        profile = profile_resp.json()
        email = profile.get("email")
        if not email:
            emails_resp = await client.get("user/emails", token=token)
            emails = emails_resp.json()
            primary = next((e for e in emails if e.get("primary")), emails[0] if emails else None)
            email = primary["email"] if primary else None
        return {
            "provider_sub": str(profile["id"]),
            "email": email,
            "display_name": profile.get("name") or profile.get("login"),
            "avatar_url": profile.get("avatar_url"),
        }
    raise ValueError(f"Unsupported provider: {provider}")
