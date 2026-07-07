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
