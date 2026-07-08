# Multi-source fetch architecture

Consolidated from the (now archived) MULTI_SOURCE_ARCHITECTURE.md,
MULTI_SOURCE_RULES.md, VISUAL_ARCHITECTURE.md, and IMPLEMENTATION_SUMMARY.md
-- see `docs/archive/2026/` for the original point-in-time writeups.

## Problem solved

Before: agent would search -> fetch the first URL -> summarize. If that
URL failed or had poor content, the entire query failed.

After: agent searches -> ranks results -> fetches the top 3 sources (max 1
per domain) -> synthesizes an answer from all successful fetches, with
citations.

## Flow

```
User query
  -> Intent Router          (domain-aware routing)
  -> Search (DuckDuckGo)    (returns top 10 results)
  -> Rank + dedup           (enforce domain diversity)
  -> Multi-fetch            (top 3 sources, 10s timeout each)
  -> Synthesis (LLM)        (combine all successful sources)
  -> Final response         (with citations)
```

## Critical rules (enforced)

1. **Domain-aware search** -- route by query content before intent
   matching (`services/agent_control/intent_router.py`):
   ```python
   if ".md" in query or "obsidian" in query:
       route -> obsidian.search
   elif "file" in query:
       route -> file-search
   else:
       route -> web search (DuckDuckGo)
   ```
2. **Never let the LLM choose URLs** -- always pick URLs from search
   results, never from LLM generation (`control_plane.py`, forced fetch
   uses `session.last_search_results`).
3. **Limit fetch** -- `max_sources=3`, `max_per_domain=1`
   (`multi_fetch.py::_rank_and_deduplicate`).
4. **Timeout + fallback** -- each fetch gets a 10s timeout; on
   timeout/error, skip the source and continue.
5. **Source diversity** -- enforce `domain_counts[domain] < max_per_domain`
   so results don't cluster on one domain.

## Implementation

- **`services/agent_control/multi_fetch.py`**
  - `_extract_domain(url)` -- domain extraction for diversity checks.
  - `_rank_and_deduplicate(search_results, max_sources=3, max_per_domain=1)`
    -- ranks and enforces diversity.
  - `multi_fetch(search_results, fetch_fn, max_sources=3, ...)` -- fetches
    from multiple sources with per-source error handling.
  - `synthesize_multi_source(user_query, fetched_sources, llm_call)` --
    synthesizes one answer from all successful fetches.
- **`services/agent_control/control_plane.py`**
  - Triggers a multi-fetch action after a successful search step
    (`last_successful_category == "search"`).
  - Executes multi-fetch, synthesizes via `synthesize_multi_source`, and
    skips re-synthesis for the multi-fetch result path.

## Configuration

Tunable in `multi_fetch.py`: `MAX_SOURCES` (default 3), `MAX_PER_DOMAIN`
(default 1), `TIMEOUT_PER_FETCH` (default 10.0s). Tunable in
`control_plane.py`: `MAX_STEPS` (default 4).

## Error handling

- All fetches fail: user gets an explicit "unable to retrieve content"
  message, not a crash.
- Partial success: synthesis proceeds from whatever succeeded, with a note
  that some sources were unavailable.
- Per-source timeout: that source is skipped and logged; the rest proceed.
