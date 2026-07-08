# ADR-007: Multi-user architecture pivot (Phase C, local-only)

**Status:** Accepted — supersedes ADR-001's timing anchor, amends ADR-006

## Context

`docs/roadmap/ASTRA_WEB_SERVICE_PLAN.md` originally sequenced auth/
multi-user work at Phase W3, *after* a single-user AWS deployment (W1)
and monitoring (W2) — rationale: deploy and instrument before adding
users, because you'll redesign after seeing real traffic. ADR-001
inherited that timing ("Session handling (Phase W3) issues a signed
session token...").

The user is deliberately pivoting this: build the full multi-user
architecture now — OAuth, JWT, Postgres, per-user memory isolation,
quotas, rate limiting, structured logging — validated entirely locally
via Docker Compose, *before* any AWS work. Rationale: application-
architecture changes and cloud/infra changes are two orthogonal concerns;
building and debugging both at once (as the original W1→W3 sequencing
would have, once AWS entered the picture) makes it hard to tell whether a
break is an auth bug, a Redis/session bug, a Docker networking issue, or
an AWS networking issue. Separating them fully — prove multi-user works
locally first, deploy to AWS only once it's already validated — removes
that ambiguity. AWS deployment becomes a separate, later phase ("Phase D",
not covered by this ADR).

This work is called **"Phase C: Multi-user Foundation (Local)"** in
project shorthand (not a phase defined in the original roadmap document —
see the roadmap update accompanying this ADR).

## Decision

1. **Supersede ADR-001's timing anchor.** OAuth (Google/GitHub, per
   ADR-001's original choice — unchanged) and JWT-based session handling
   move from "before Phase W3" to now (Phase C). ADR-001's *choice* of
   OAuth + JWT stands; only the *timing* changes.
2. **Amend ADR-006's frozen surface** to add:
   - A new **`gateway`** service (auth-only — see design note below) and
     a new **`postgres`** service join the frozen Docker Compose surface.
   - All core service routes (whisper/llm/tts/intent/gateway) move to an
     **`/api/v1/`** prefix — a declared, deliberate breaking change to the
     endpoint paths ADR-006 froze, done now while the surface is already
     being amended rather than as a second breaking change later.
   - The new `AI_ASSISTANT_*` env vars introduced across Phase C's PRs
     (Postgres DSN, JWT secret/expiry, OAuth client credentials, gateway
     host/port, and later Redis/quota/rate-limit vars) extend the frozen
     34-field env-var surface.
   - `docs/` gains `docs/api/` (endpoint contract docs, see below) as part
     of the frozen `docs/` layout.
3. **Design constraints for the auth/multi-user build** (binding on the
   implementation, detailed further in `docs/api/*.md`):
   - **The gateway is auth-only, not a data-plane proxy.** It owns OAuth
     login/callback, JWT issuance, and refresh/logout. It does not sit in
     front of whisper/llm/tts/intent traffic — streaming voice must not
     gain an extra FastAPI hop's latency/CPU/memory-copy cost. Each of
     whisper/llm/tts/intent validates the JWT itself via a shared,
     in-process dependency (no network call to the gateway per request).
     This preserves ADR-004's loop-separation invariant: auth becomes a
     shared library call, not a service hop coupling the loops.
   - **Stateless JWT, no revocation table.** Short-lived access JWT +
     longer-lived refresh JWT, both signed/stateless. No `sessions` table,
     no server-side logout-everywhere for Phase C — a deliberate scope
     cut (not an oversight), revisit only if a concrete need for
     cross-device revocation appears later.
   - **Postgres is the source of truth for conversations; Qdrant is a
     derived semantic index**, not a co-equal store. Every turn writes to
     Postgres first; Qdrant is populated from that write. Recoverable:
     Qdrant can be rebuilt from Postgres if ever lost.
   - **Per-user Qdrant isolation** via a required `user_id` payload field
     + `query_filter` (payload filtering, not per-user collections) —
     matches the original roadmap W3 design.
   - **Redis (introduced in a later Phase C PR) is designed as a generic
     cache**, not rate-limit-specific, so it's extensible later without
     re-architecting — but no caching/presence/WebSocket-state features
     are built now (no WS transport exists yet in this phase).
4. **Scope stays local-only.** No AWS provisioning, no production secrets
   management, no TLS/DNS work in Phase C. That's Phase D.

## Consequences

- ADR-001 remains the record of *what* auth mechanism was chosen (OAuth,
  Google/GitHub); this ADR records *when* and the surrounding session/
  gateway architecture. Read them together.
- ADR-006's "frozen" env-var/Compose/API-path surface is no longer
  exactly as declared in that ADR — this ADR is the sanctioned amendment
  its own "Consequences" section required for structural changes.
- Every existing frontend call site and `docker/seed.py`/
  `docker/smoke_test.py` need updating for the `/api/v1/` prefix and
  `Authorization` header — a real, one-time breaking change across the
  whole core-service surface, done deliberately now rather than
  incrementally later.
- Existing unattributed Qdrant `conversations` data has no principled way
  to be attributed to a real user; it will be wiped and reseeded under a
  reserved default/local user id as part of the PR that introduces
  per-user isolation (not migrated) — acceptable since it's local
  developer/demo data, not production data, and since Postgres becomes
  authoritative going forward.
- The MCP/agent-tool exclusion from ADR-006 stands unchanged — `/mcp/*`
  and `/agent/loop`'s *behavior* stays out of scope here; only its route
  gains the `/api/v1/` prefix and an auth dependency, consistent with
  every other core-service route.

## Alternatives considered

- **Keep the original W3 timing (defer multi-user until after a
  single-user AWS deploy)** — rejected: this is the user's explicit
  reason for this ADR; building the two orthogonal concerns (application
  architecture, cloud infra) simultaneously later was judged harder to
  debug than doing them in strict sequence now.
- **Route all traffic through the gateway (initial design)** — considered
  and rejected after review: proxying voice/LLM/TTS traffic through an
  extra hop was judged an unacceptable latency/resource cost for a
  latency-sensitive local voice loop, especially given ADR-004's loop-
  separation invariant. Local, in-process JWT validation per service
  achieves the same security property without the hop.
- **JWT + Redis-backed session table for revocation (initial design)** —
  considered and rejected after review: adds a second stateful dependency
  and an extra DB hit on every request's revocation check, for a
  capability (server-side logout-everywhere) not currently needed at
  solo-maintainer/local scale. Stateless JWT is simpler and sufficient;
  revisit if concrete need appears.

## Review date

Revisit when Phase D (AWS deployment) begins, to confirm whether any
Phase C design constraint (e.g. no revocation table, gateway auth-only)
needs to change for a multi-instance/production deployment. Also revisit
if a concrete requirement for cross-device logout/revocation appears.

## Source

User-directed pivot (2026-07-08); `docs/roadmap/ASTRA_WEB_SERVICE_PLAN.md`
Phase W3's original design (OAuth, users table, per-user Qdrant payload
filtering, conversation isolation test); ADR-001 (auth mechanism);
ADR-004 (loop-separation invariant); ADR-006 (frozen surface + its own
amendment clause); user architecture review of the initial gateway-as-proxy
design.
