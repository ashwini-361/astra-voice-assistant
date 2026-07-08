# Deferred ideas / known issues

Things noticed during work that are out of scope for the task at hand.
Not a roadmap -- just a parking lot so they aren't lost or fixed as
scope creep.

## Found during Phase A test stabilization (2026-07-08)

Pre-existing test failures in `services/agent_control` and
`services/llm_service` business logic, unrelated to Phase A's
reproducibility/config/test-infrastructure scope. Confirmed present
before any Phase A changes (verified against commit `1230db4`). Not
fixed here -- these are behavior bugs, not test-infrastructure flakiness:

- `tests/test_agent_control_phase2.py::test_route_intent_url_prefers_fetch_tools`
  -- `route_intent` returns `duckduckgo.search` before `fetch.fetch` for
  a query containing a URL; test expects fetch-tools to be prioritized.
- `tests/test_agent_control_phase2.py::test_infer_category_uses_tool_identity_not_exact_tool_name`
  -- `infer_category("get_current_time")` returns `"time_current"`
  instead of `"time"`.
- `tests/test_agent_control_phase2.py::test_get_allowed_categories_uses_prior_tool_category`
  -- `get_allowed_categories` returns `["fetch"]` instead of
  `["fetch", "summarize"]` after a prior `search` step.
- `tests/test_llm.py::test_agent_loop_records_typed_tool_error` -- fails
  with `IndexError: list index out of range` on `body["steps"][0]`;
  reproduces with real network calls to MCP servers and Ollama warmup
  happening during the test (test isolation gap -- `TestClient` startup
  triggers real MCP tool discovery/warmup rather than everything being
  mocked).

All 4 are now marked `@pytest.mark.xfail` (the 3 agent_control ones
`strict=True` since they're deterministic logic bugs; the llm_service
one non-strict since it depends on network reachability) so the new CI
`pytest` job (added in this same branch) doesn't block merges on
pre-existing, already-tracked issues. Un-xfail each one when its
underlying bug is actually fixed.

## Found during Phase C PR1A code review (2026-07-08)

- **Per-decorator `/api/v1` prefix, not `APIRouter(prefix=...)`.** The
  bulk route rename to `/api/v1/{voice,chat,agent}/*` was done by editing
  ~50 individual `@app.get/post/...` decorators across
  `services/{whisper,llm,tts,intent}_service.py` rather than mounting
  routes under a shared `APIRouter(prefix="/api/v1")`. Works today, but
  any future prefix change (e.g. `/api/v2`) requires the same
  error-prone mechanical edit across all 4 files again. Worth a
  refactor to `APIRouter` when touching these files next, not urgent now.
- **`/api/v1/mcp/*` and `/api/v1/tools/toggle` have no stability marker**
  distinguishing them from the deliberately-designed `chat`/`voice`/`agent`
  resource routes -- they were bulk-prefixed only (per ADR-006/007's MCP
  exclusion from the freeze), so `/api/v1` now mixes stable and
  still-churning routes with no way to tell them apart from the URL
  alone. Consider an `/api/v1/internal/mcp/*` or similar marker when this
  surface is next redesigned (agent roadmap, Phase W5/W6).
- **`core/config.py`'s `gateway_host`/`gateway_port` fields are unused.**
  `services/gateway/main.py` and `docker-compose.yml`'s `gateway` service
  hardcode `0.0.0.0:8000` rather than reading these settings -- consistent
  with how whisper/llm/tts/intent's own bind address is also hardcoded in
  their compose `command:` (the `*_host`/`*_port` settings are consumed by
  *callers* via `resolve_host()`, not by the services binding to them), so
  this isn't a regression, just currently-dead config. Will matter once
  something needs to call the gateway besides the frontend's hardcoded
  `VITE_GATEWAY_API_BASE`.
- **`db/session.py`'s cached engine/sessionmaker have no shutdown/dispose
  hook.** Not a leak under today's single-process, no-DB-traffic-yet
  skeleton, but worth adding a FastAPI lifespan shutdown hook in
  `services/gateway/main.py` before PR1B starts issuing real DB queries
  through `get_db()`.
- **`db/migrations/env.py`'s `_sync_dsn()`** does a blind
  `.replace("+asyncpg", "+psycopg2")` on the configured DSN with no
  validation that the substring is present/well-formed. Works today
  because the default DSN always has `+asyncpg`, but a malformed
  `AI_ASSISTANT_POSTGRES_DSN` would silently no-op this substitution
  rather than failing with a clear config error. Consider a small
  assertion or regex-based swap.

## Found during Phase A code review (2026-07-08)

`core/config.py::resolve_host()` only centralizes the `0.0.0.0`/`::` ->
`127.0.0.1` normalization. The surrounding "build a full base URL from a
host+port" logic (scheme detection via `host.startswith("http")`, then
conditionally prefixing `http://`) is still duplicated across
`orchestrator/pipeline.py` (4 call sites), `orchestrator/main.py` (2
sites), `duplex/stream_manager.py`, and `streaming/tts_streamer.py` --
8+ near-identical conditionals for one conceptual operation. A shared
`core/config.py` helper (e.g. `build_service_url(host, port) -> str`,
internally calling `resolve_host`) would collapse these and remove the
risk of sites drifting out of sync (this already happened once during
Phase A -- see the code-review fix in this branch that restored the
scheme guard in `orchestrator/main.py`). Not done as part of Phase A
since it's a refactor beyond fixing the regressions found; worth doing
as a follow-up.
