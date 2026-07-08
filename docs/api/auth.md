# Auth model (JWT validation, shared across all services)

Written before Phase C PR1 implementation per ADR-007. This documents the
`core/auth.py` shared dependency every service (gateway, whisper, llm,
tts, intent) imports — not a separate HTTP endpoint (see
`docs/api/gateway.md` for the actual auth *endpoints*).

## Token model

- **Access JWT**: short-lived (`AI_ASSISTANT_JWT_ACCESS_EXPIRY_MINUTES`,
  default 30 min), signed with `AI_ASSISTANT_JWT_SECRET` (HS256). Claims:
  `sub` (user id, UUID string), `email`, `iat`, `exp`. Sent as
  `Authorization: Bearer <token>` on every request to whisper/llm/tts/
  intent/gateway (except `/health` routes).
- **Refresh JWT**: longer-lived (`AI_ASSISTANT_JWT_REFRESH_EXPIRY_DAYS`,
  default 30 days), same signing secret, distinguished by a claim (e.g.
  `type: "refresh"`) so an access token can't be replayed as a refresh
  token or vice versa. Only ever sent to the gateway's
  `POST /api/v1/auth/refresh`.
- **No server-side session/revocation state** (per ADR-007) — validation
  is signature+expiry check only, no DB or Redis lookup. A stolen access
  token is valid until it naturally expires (≤30 min by default); this is
  an accepted tradeoff for Phase C, revisit if a concrete need for
  revocation appears (ADR-007's review-date clause).

## `core/auth.py` — shared dependency

```python
def get_current_user_id(request: Request) -> str:
    """FastAPI dependency: decode/verify the Authorization header's JWT,
    return the user_id (sub claim). Raises HTTPException(401) if missing,
    malformed, expired, or wrong-type (e.g. a refresh token used here)."""
```

Imported identically by `services/whisper_service.py`,
`services/llm_service.py`, `services/tts_service.py`,
`services/intent_service.py`, and `services/gateway/routes.py`'s
`/api/v1/auth/me`. Pure in-process JWT decode (`pyjwt`) — no I/O, so it
adds negligible latency to the hot voice-loop path.

## Native/no-login dev path

`start_stack.ps1` (native, no OAuth flow wired in for that path) and
`docker/seed.py`/`docker/smoke_test.py` need a way to call authenticated
routes without going through a real OAuth login. Resolution (finalized in
PR2 alongside the reserved default user, referenced here for completeness
since it affects how `get_current_user_id` is exercised in tests/scripts):
a fixed, reserved user id (`00000000-0000-0000-0000-000000000000`,
`email='local@astra.local'`, `provider='local'`) is seeded into `users`,
and dev scripts mint a short-lived access JWT for that user directly
(e.g. via a small `scripts/`-only helper that signs a token with
`AI_ASSISTANT_JWT_SECRET` locally) rather than performing a real OAuth
round-trip. This is explicit and documented, not a silent fallback baked
into `get_current_user_id` itself — the dependency always requires a
valid JWT; scripts are responsible for obtaining one.

## Error responses

- Missing/malformed/expired JWT → `401 {"detail": "..."}`.
- Refresh token presented where an access token is expected (or vice
  versa) → `401`.
- No `403`s at the auth layer in Phase C — there's no per-route
  authorization/permission model yet (that's the roadmap's later Phase
  W5 "Permission Filter" concept, explicitly out of scope here).
