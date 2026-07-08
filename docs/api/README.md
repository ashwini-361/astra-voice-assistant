# API contracts

Endpoint documentation for Phase C (multi-user foundation), written
before implementation per ADR-007 — see
[`../adr/ADR-007-multiuser-pivot.md`](../adr/ADR-007-multiuser-pivot.md).

- [`auth.md`](auth.md) — JWT model and the shared `core/auth.py`
  in-process validation dependency used by every service.
- [`gateway.md`](gateway.md) — the new auth-only gateway service
  (OAuth login/callback, refresh, logout, `/me`). Not a data-plane proxy.
- [`voice.md`](voice.md) — whisper/tts/intent's `/api/v1/voice/*` routes.
- [`memory.md`](memory.md) — llm_service's `/api/v1/chat/*` and
  `/api/v1/agent/*` routes, and the per-user memory isolation design
  (Postgres source-of-truth, Qdrant as a derived index).

## Naming conventions (frozen now, before any route exists)

Every path is grouped by **resource domain**, not by physical service —
noun-based, no verbs in the path itself (the HTTP method is the verb):

- `/api/v1/auth/*` — gateway (login, callback, refresh, logout, me).
- `/api/v1/voice/*` — whisper (`transcriptions`), tts (`speech`,
  `playback`), intent (`intents`). Three physically separate services
  each implement their own slice of this one logical namespace — that's
  fine, they don't share a process, just a naming convention.
- `/api/v1/chat/*` — llm_service's core generation (`completions`,
  `providers`, `models`, `settings`, `stop`, `metrics`).
- `/api/v1/agent/*` — llm_service's tool-use loop (`loop`) — kept as its
  own resource domain, not nested under `chat`, since it's a distinct
  capability (multi-step tool use vs. single-turn generation) and is
  explicitly excluded from ADR-006's freeze (still consolidating) — not
  worth over-designing a name for a surface that may get reshaped in the
  agent roadmap anyway.
- `/api/v1/memory/*` — **reserved, not implemented in Phase C.** Memory
  stays an internal concern (`MemoryManager`, reached only via `chat`/
  `agent` routes) for now; reserved for a future direct history-retrieval
  endpoint (e.g. `GET /api/v1/memory/conversations`).
- `/api/v1/admin/*` — **reserved, not implemented in Phase C** (admin
  dashboard is explicitly deferred, per the user's own scope call).
- `/api/v1/health` — every service keeps its own, unprefixed by resource
  domain and unauthenticated. Health is an operational check, not a
  business resource — it doesn't fit the domain-grouping scheme above by
  design.
