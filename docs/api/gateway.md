# Gateway API contract (auth only — not a data-plane proxy)

Written before Phase C PR1 implementation per ADR-007. The gateway
(`services/gateway/` package, port 8000) owns OAuth login/callback, JWT
issuance, and refresh/logout. **It does not proxy or sit in front of
whisper/llm/tts/intent traffic** — those are called directly by the
frontend (see `docs/api/voice.md`, `docs/api/memory.md`'s LLM section).
This is the one deliberate design change from the first draft of this
architecture: proxying voice/LLM/TTS through an extra hop was rejected as
an unacceptable latency/CPU/memory-copy cost on the realtime voice loop,
and as coupling ADR-004's isolated loops through a shared service hop.

## `GET /api/v1/auth/login/{provider}`
`provider`: `google` | `github`. Redirects the browser to the OAuth
provider's consent screen (`authlib` handles the OAuth2 flow). No auth
required (this *is* the login entry point).

## `GET /api/v1/auth/callback/{provider}`
OAuth callback target. Exchanges the provider's auth code for profile
info, upserts a `users` row (`email`, `provider`, `provider_sub`,
`display_name`, `avatar_url`, `last_login_at`), issues an access+refresh
JWT pair, and returns them to the browser (redirect with tokens, or a
JSON response — exact transport TBD at implementation time, e.g. secure
cookie vs. URL fragment vs. JSON body; not architecturally load-bearing,
pick whichever is simplest to wire into the existing frontend's fetch
calls).

Response shape (JSON variant):
```json
{"access_token": "string", "refresh_token": "string", "token_type": "bearer", "expires_in": 1800}
```

## `POST /api/v1/auth/refresh`
Request: `{"refresh_token": "string"}`. Verifies the refresh JWT's
signature+expiry (stateless — no DB lookup, no revocation check per
ADR-007's "no sessions table" decision) and issues a new access JWT (and
optionally a rotated refresh JWT — implementation detail, not
architecturally required for Phase C).

Response: `{"access_token": "string", "token_type": "bearer", "expires_in": 1800}`

## `POST /api/v1/auth/logout`
Client-side token discard — this endpoint exists for symmetry/future use
(e.g. if a revocation mechanism is added later per ADR-007's review-date
clause) but performs **no server-side state change** in Phase C. Response:
`{"status": "logged_out"}`.

## `GET /api/v1/auth/me`
Request: `Authorization: Bearer <access_jwt>`. Validates the JWT via the
same `core/auth.py` dependency whisper/llm/tts/intent use, returns the
authenticated user's profile.

Response:
```json
{"id": "uuid", "email": "string", "provider": "string", "display_name": "string|null", "avatar_url": "string|null"}
```
Invalid/expired JWT → `401`.

## `GET /api/v1/health`
No auth required. Response: `{"status": "ok", "service": "gateway"}`.

## What the gateway explicitly does NOT do

- Does not forward/proxy `/api/v1/voice/*`, `/api/v1/chat/*`,
  `/api/v1/agent/loop`, or any other data-plane route — the frontend
  calls whisper/llm/tts/intent directly.
- Does not perform quota or rate-limit enforcement itself (PR3 puts that
  in each service, built on the shared JWT-derived `user_id` — see
  `docs/api/memory.md` and the Phase C plan's PR3 section).
- **Is not managed by the native dev tools.** `services/dev_manager.py`
  and `start_stack.ps1` still only supervise whisper/llm/tts/intent — the
  gateway (and Postgres) are Docker-Compose-only in Phase C, consistent
  with ADR-006's canonical-startup-path decision. Running native dev mode
  (`start_stack.ps1`, with or without `-UseDevManager`) will never bring
  up the gateway; `curl http://127.0.0.1:8000/api/v1/health` will always
  connection-refuse in that mode — this is expected, not a regression.
- Does not maintain server-side session state (no `sessions` table, no
  Redis session store) — JWTs are self-contained and stateless.
