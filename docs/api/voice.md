# Voice API contract (whisper / tts / intent)

Written before Phase C implementation per ADR-007. Documents the
`/api/v1/` shape these services move to, and their auth requirement.
Existing field shapes are unchanged from today — only the path prefix
and auth requirement are new (per ADR-006's amendment in ADR-007).

**Auth:** every route below requires `Authorization: Bearer <access_jwt>`,
validated in-process by each service via `core/auth.py`'s
`get_current_user_id` dependency (no network call to the gateway). No
route in this document is proxied through the gateway — these are called
directly by the frontend, same as today, just with the header attached
and the new path prefix.

## Whisper (`services/whisper_service.py`, port 8001)

### `POST /api/v1/transcribe`
Multipart form-data. Field: `audio_file` (audio file).

Response (`TranscriptionResponse`):
```json
{"text": "string", "language": "string|null", "duration": "float|null", "segments": [{"...": "float"}]}
```

### `GET /api/v1/health`
No auth required (health checks must work pre-login / from Docker
healthchecks). Response: `{"status": "ok", "service": "whisper"}`.

## TTS (`services/tts_service.py`, port 8003)

### `POST /api/v1/speak`
Server-side synth + enqueue for ordered playback (native dev path only).

Request (`SpeakRequest`):
```json
{"text": "string", "emotion": "string|null", "chunk_id": "int|null", "generation_id": "int|null"}
```
Response (`SpeakResponse`): `{"accepted": bool, "backend_status": int, "backend": "string"}`

### `POST /api/v1/synthesize`
Returns raw MP3 bytes (browser-side playback path — this is what a
hosted/Docker-Compose frontend actually uses).

### `POST /api/v1/stop`
Stop playback engine, bump generation counter. Body: none.

### `GET /api/v1/settings`, `POST /api/v1/settings`, `POST /api/v1/settings/reset`
Runtime TTS tuning (unchanged shape from today — see root `README.md`'s
"TTS runtime control API" section for the full field list).

### `GET /api/v1/streaming-config`
Expose chunking knobs (`chunk_initial_words`, `chunk_steady_words`,
`chunk_max_chars`).

### `GET /api/v1/health`
No auth required. Response: `{"status": "ok", "service": "tts", "backend": "string"}`.

*(`/debug/playback` stays unprefixed/undocumented-externally — internal
diagnostics only, per ADR-006's note that it should be excluded from any
frozen public API definition.)*

## Intent (`services/intent_service.py`, port 8004)

### `POST /api/v1/classify`
Request (`IntentRequest`): `{"text": "string"}`
Response (`IntentResponse`): `{"label": "string", "scores": {"...": float}, "provider": "string|null"}`

### `GET /api/v1/health`
No auth required. Response: `{"status": "ok", "service": "intent", "fallback_mode": bool}`.

## Notes for PR1 implementation

- `/health` endpoints on every service stay **unauthenticated** — Docker
  Compose healthchecks and CI's smoke test hit these directly and must
  keep working without a token.
- All other routes above gain `Depends(get_current_user_id)` even though
  whisper/tts/intent don't touch per-user memory themselves — this is for
  consistent quota/rate-limit accounting in PR3 (every request needs an
  attributable `user_id`), not because these services need per-user
  business logic today.
- `docker/seed.py` and `docker/smoke_test.py` need a token to call these
  routes post-PR1 — see `docs/api/auth.md` for how a script obtains one
  for the reserved default/local user.
