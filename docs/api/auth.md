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

## Native/no-login dev path (implemented in PR1B)

`orchestrator/pipeline.py`, `orchestrator/main.py`, `duplex/
stream_manager.py`, `streaming/tts_streamer.py` (the realtime voice loop),
and `docker/seed.py`/`docker/smoke_test.py`/manual scripts all need to
call authenticated routes without a real OAuth login. Resolution:
`core/auth.py` defines a fixed, reserved user id
(`LOCAL_USER_ID = "00000000-0000-0000-0000-000000000000"`,
`LOCAL_USER_EMAIL = "local@astra.local"`) and a
`create_local_service_token()` helper that mints an access token for it
directly (signs with `AI_ASSISTANT_JWT_SECRET` in-process — no OAuth
round-trip). Every native/CLI/script caller imports this one function
and attaches `Authorization: Bearer <token>` — explicit and centralized,
not a silent fallback baked into `get_current_user_id` itself (that
dependency always requires a valid JWT; callers are responsible for
obtaining one).

Note: minting this token does **not** require a `users` row to exist yet
-- only `/api/v1/auth/me` does a DB lookup by `id`; every other service's
`get_current_user_id` only decodes the JWT. The reserved user row itself
is seeded in PR2 alongside per-user memory isolation.

**Frontend gap (known, deferred):** the frontend's `core/api/*.ts` files
do not yet attach any `Authorization` header or have a login UI — full
OAuth browser wiring (login button, token storage, refresh-on-expiry,
`/api/v1/auth/callback/*` redirect handling) is out of PR1B's scope by
design (backend auth enforcement first) and is a follow-up. Until then,
calling the API from the frontend's `npm run dev` will 401. Exercising
the pipeline end-to-end is verified via `make smoke` (which uses
`create_local_service_token()`, same as the native voice loop).

## Error responses

- Missing/malformed/expired JWT → `401 {"detail": "..."}`.
- Refresh token presented where an access token is expected (or vice
  versa) → `401`.
- No `403`s at the auth layer in Phase C — there's no per-route
  authorization/permission model yet (that's the roadmap's later Phase
  W5 "Permission Filter" concept, explicitly out of scope here).
