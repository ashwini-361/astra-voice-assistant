<!-- current-status-anchor -->
## Current Status / Next Up

**Update this section at the end of each work session** so the next
session (or a fresh context window) can pick up without re-deriving
where things stand.

**Last completed (2026-07-09):** Phase C — Multi-user Foundation (Local),
per `docs/adr/ADR-007-multiuser-pivot.md` and the "Phase C" entry in
`docs/roadmap/ASTRA_WEB_SERVICE_PLAN.md`. Delivered as ADR-007 docs +
4 sequenced PRs (1A infra, 1B auth, 2 memory isolation, 3 quotas/rate
limiting/logging), each with its own `/code-review` pass and live
Docker Compose verification. **All merged into `dev-init`** — confirmed
via `git merge-base --is-ancestor` for each branch tip, and a full
`pytest tests -q` run directly on merged `dev-init` (91 passed, 8
skipped when Postgres/Qdrant/Redis aren't running locally, 4 xfailed).

**Next up:** Phase D (AWS deployment) is the next phase per the
roadmap doc, but has **not been planned yet** — no ADR, no design pass.
Before starting it: re-read `docs/roadmap/ASTRA_WEB_SERVICE_PLAN.md`'s
Phase W0-W2 sections (the original AWS plan, written before the Phase C
pivot — GPU strategy, deploy target, monitoring) and treat them as a
starting draft, not a finished plan, since they predate Phase C's
actual multi-user implementation details. Also check `docs/backlog.md`
for deferred items from PR1B/PR2/PR3 that may be worth picking up
first (e.g. frontend OAuth wiring — the frontend has no login UI or
JWT attachment yet, so the multi-user backend isn't reachable from a
browser until that lands).

**Before touching AWS**, confirm with the user whether frontend OAuth
wiring (the biggest known gap — see `docs/backlog.md`'s "Deferred from
PR1B" entry) should land first, since Phase D assumes a reachable
multi-user product.

---

<!-- code-review-graph MCP tools -->
## MCP Tools: code-review-graph

**IMPORTANT: This project has a knowledge graph. ALWAYS use the
code-review-graph MCP tools BEFORE using Grep/Glob/Read to explore
the codebase.** The graph is faster, cheaper (fewer tokens), and gives
you structural context (callers, dependents, test coverage) that file
scanning cannot.

### When to use graph tools FIRST

- **Exploring code**: `semantic_search_nodes` or `query_graph` instead of Grep
- **Understanding impact**: `get_impact_radius` instead of manually tracing imports
- **Code review**: `detect_changes` + `get_review_context` instead of reading entire files
- **Finding relationships**: `query_graph` with callers_of/callees_of/imports_of/tests_for
- **Architecture questions**: `get_architecture_overview` + `list_communities`

Fall back to Grep/Glob/Read **only** when the graph doesn't cover what you need.

### Key Tools

| Tool | Use when |
|------|----------|
| `detect_changes` | Reviewing code changes � gives risk-scored analysis |
| `get_review_context` | Need source snippets for review � token-efficient |
| `get_impact_radius` | Understanding blast radius of a change |
| `get_affected_flows` | Finding which execution paths are impacted |
| `query_graph` | Tracing callers, callees, imports, tests, dependencies |
| `semantic_search_nodes` | Finding functions/classes by name or keyword |
| `get_architecture_overview` | Understanding high-level codebase structure |
| `refactor_tool` | Planning renames, finding dead code |

### Workflow

1. The graph auto-updates on file changes (via hooks).
2. Use `detect_changes` for code review.
3. Use `get_affected_flows` to understand impact.
4. Use `query_graph` pattern="tests_for" to check coverage.

---

## Commit conventions

- Do **not** add a `Co-Authored-By: Claude ... <noreply@anthropic.com>` (or
  any Claude/Anthropic) trailer to commit messages in this repo.
- When a change adds or changes architectural decisions, update
  `docs/adr/` (ADRs) and/or the relevant plan doc in `docs/` in
  the same change — don't let project-structure docs drift from the code.

---

## Project Snapshot (YC style)

- Build the fastest local voice assistant loop on Windows.
- Optimize for first-audio latency + natural speech quality.
- Recent upgrades: adaptive TTS chunking, runtime TTS settings API, stronger stream interrupt behavior.
- Primary tuning knobs: `edge_base_rate_pct`, `chunk_initial_words`, `chunk_steady_words`, `chunk_max_chars`.
