# API contracts

Endpoint documentation for Phase C (multi-user foundation), written
before implementation per ADR-007 — see
[`../adr/ADR-007-multiuser-pivot.md`](../adr/ADR-007-multiuser-pivot.md).

- [`auth.md`](auth.md) — JWT model and the shared `core/auth.py`
  in-process validation dependency used by every service.
- [`gateway.md`](gateway.md) — the new auth-only gateway service
  (OAuth login/callback, refresh, logout, `/me`). Not a data-plane proxy.
- [`voice.md`](voice.md) — whisper/tts/intent's `/api/v1/` routes
  (unchanged shapes, new prefix + auth requirement).
- [`memory.md`](memory.md) — llm_service's core-generation routes and the
  per-user memory isolation design (Postgres source-of-truth, Qdrant as a
  derived index).
