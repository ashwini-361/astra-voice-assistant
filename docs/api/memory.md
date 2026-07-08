# Memory & LLM API contract (llm_service core routes + per-user isolation design)

Written before Phase C implementation per ADR-007. Covers
`services/llm_service.py`'s core-generation routes (the ADR-006 frozen
subset — `/mcp/*`/`/agent/loop`'s *behavior* stays excluded from the
freeze per ADR-006, but they still gain the `/api/v1/` prefix and auth
dependency like every other route) and the per-user memory design PR2
implements.

## LLM core routes (`services/llm_service.py`, port 8002)

All require `Authorization: Bearer <access_jwt>` except `/api/v1/health`.

### `POST /api/v1/generate`
Request (`GenerateRequest`):
```json
{"prompt": "string", "provider": "ollama|lmstudio|openai|custom|null", "model": "string|null", "stream": "bool|null", "temperature": "float|null", "max_tokens": "int|null", "top_p": "float|null", "stop": ["string"], "voice_mode": "bool|null"}
```
Response (`GenerateResponse`, non-stream): `{"provider": "string", "model": "string", "response": "string", "request_id": "string"}`.
Stream mode: NDJSON, unchanged from today.

**PR2/PR3 note:** `user_id` comes from `get_current_user_id`
(`docs/api/auth.md`), not a request field — never accept `user_id` as
client-supplied input, always derive it from the verified JWT server-side.

### `GET /api/v1/providers`, `GET /api/v1/models`, `GET/POST /api/v1/settings`, `POST /api/v1/settings/reset`, `POST /api/v1/stop`
Unchanged shape from today, gain the prefix + auth requirement.

### `POST /api/v1/agent/loop`
Request (`AgentLoopRequest`): `{"prompt": "string", "max_steps": int}`.
Response: `{"status": "string", "steps": [...], "response": "string"}`.
Behavior/known issues unchanged (still excluded from ADR-006's freeze,
per ADR-007 — this route just gains the path prefix and auth like
everything else). `user_id` from the JWT is threaded down through
`control_plane.py` → `agent_memory.py` (see below) — this is the one
`/mcp/*`-adjacent change that's actually required by Phase C, since the
agent loop touches per-user memory.

### `GET /api/v1/metrics`, `GET /api/v1/health`
`/health` unauthenticated (Compose healthchecks); `/metrics` requires
auth.

## Per-user memory design (`memory/vector_store.py`, `memory/memory_manager.py`)

Not HTTP endpoints — this is the internal contract PR2 implements,
documented here because `/api/v1/generate` and `/api/v1/agent/loop` are
its primary callers.

### Postgres is the source of truth; Qdrant is a derived index

```
MemoryManager.add_interaction(user_text, assistant_text, user_id: str)
  1. INSERT INTO conversations (user_id, role, content, created_at) -- both turns
  2. embed(assistant_text) -> vector
  3. VectorStore.upsert(doc_id, vector, text, user_id) -> qdrant_point_id
  4. UPDATE conversations SET qdrant_point_id = ... WHERE id = ...

MemoryManager.retrieve(query, top_k, user_id: str) -> str
  1. embed(query) -> vector
  2. VectorStore.search(vector, top_k, user_id) -- query_filter on user_id
  3. format results as context string (unchanged from today's shape)
```

`user_id` is a **required** parameter on both methods — no default, no
silent omission. A caller with no attributable user (shouldn't happen
post-PR1/PR2 since every route requires auth) fails loudly rather than
leaking across the (currently nonexistent) isolation boundary.

### Qdrant schema change

`conversations` collection payload: `{"text": "string", "user_id": "string"}`
(was `{"text": "string"}`). A payload index on `user_id` (keyword type) is
created at collection-init time so filtered search stays fast as data
grows.

### Postgres `conversations` table (new, Alembic-managed)

```
id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE
role            TEXT NOT NULL           -- 'user' | 'assistant'
content         TEXT NOT NULL
qdrant_point_id UUID                    -- nullable; set once embedded+upserted
created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
-- INDEX (user_id, created_at)
```

### Isolation guarantee (the privacy-critical test)

Two accounts, each with distinct content added via `add_interaction`:
`retrieve()` for account A must return zero of account B's content, and
vice versa — covering both the Qdrant-search path (`query_filter`) and
the Postgres `conversations` read path (`WHERE user_id = ...`). See the
Phase C plan's PR2 verification section for the concrete test
(`tests/test_memory_isolation.py`).

### Existing data

The current `conversations` Qdrant collection (payload `{"text": ...}`
only, no `user_id`) has no principled way to be attributed to a real
user after the fact. PR2 wipes and recreates it with the `user_id`
payload index, reseeding demo data under a reserved default/local user
(see `docs/api/auth.md`'s "Native/no-login dev path" section) — not a
migration, a deliberate reset, since this is local developer/demo data.
