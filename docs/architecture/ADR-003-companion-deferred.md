# ADR-003: Companion/Desktop app deferred

**Status:** Accepted

## Context

`docs/ASTRA_WEB_SERVICE_PLAN.md` §3 describes a future Companion desktop
app (`Cloud -> Planner -> Gateway -> Desktop Companion -> Docker / Browser
/ Files / Git`) that would give a cloud-hosted agent access to a user's
local machine. This solves a fundamentally different problem than the
hosted web service (local file/browser/git access vs. hosted voice+text
chat), and building it now would delay proving demand for the web service
itself.

## Decision

Defer the Companion/Desktop app entirely for v1. Do not build the Docker
MCP Gateway or desktop companion until the web service has proven demand.

## Consequences

- v1 web service tools are limited to hosted-appropriate capabilities (web
  search, document summarization) — no local file/browser access from the
  user's own machine (Phase W5).
- The eventual Companion architecture direction is agreed upon and
  documented in §3 of the plan, so future work has a target shape without
  building it prematurely.

## Alternatives considered

- **Build Companion alongside the web service** — rejected: doubles scope
  before either track is validated; the web service must prove demand
  first.

## Review date

Revisit once the web service has real multi-user traffic and demand for
local-machine agent capability is established.

## Source

`docs/ASTRA_WEB_SERVICE_PLAN.md` §1 (Confirmed decisions), §3 (Future
Companion architecture), §4 (Explicitly deferred).
