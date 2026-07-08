# ASTRA_WEB_SERVICE_PLAN.md (v2)

**Goal:** Ship a hosted, multi-user web service for Astra on **AWS**, *early* — before the full agent roadmap (`ASTRA_AGENT_PLAN.md`) is complete.

**Scope of v1:** Voice + text chat, hosted, multi-user, with a small tool set behind a permission filter, plus a lightweight server-side admin page. **Not** in v1: multi-agent orchestration, computer use, the Docker MCP Gateway / Companion desktop app.

**Guiding principle:** "Web service" and "agent capability" are separable tracks sharing one foundation. Deploy and instrument *first*, then add users, then add agent capability — because you'll redesign against production data anyway, and you can't measure blind.

---

## 0. Core invariant — keep the two loops isolated

```
   Realtime Voice loop                Agent loop
   STT -> LLM -> TTS                  Planner -> Tools -> Memory -> Long reasoning
   (low latency,                      (throughput + correctness,
    orchestrator/pipeline.py)          agent/ package)
        \____________ MUST STAY SEPARATE ____________/
```

Voice latency and autonomous reasoning have different requirements. If they share a loop, every future agent feature slows down conversations. This is the highest-priority design constraint and survives every phase below.

---

## 1. Confirmed decisions (locked)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Auth | **OAuth (Google/GitHub)** | Skip password implementation entirely; OAuth is enough for v1. |
| Transport | **WebSocket** | No reason to take on WebRTC complexity for the current architecture yet. |
| Companion/Desktop | **Deferred** | Web service must prove demand first; Companion solves a different problem. |
| Loop separation | **Keep strict** | Per the invariant above. |
| Cloud | **AWS** | Target platform. |

---

## 2. Revised phase order

The key change from v1: **deploy and instrument before adding auth/users.** You cannot measure latency, GPU utilization, websocket stability, or memory usage without a deployed backend — and you'll redesign parts of it after seeing real traffic.

```
W-1  Developer Experience   (one command up)
  |
B    Architecture freeze   (ADR-006, new — not in original order)
  |
W0   Decisions + AWS setup
  |
W1   Deploy + streaming      (single-user, on AWS)
  |
W2   Monitoring + admission control  <- BEFORE multi-user
  |
W3   Auth + user isolation
  |
W4   Quotas + feature flags + admin page
  |
W5   Tools behind permission filter  (overlaps agent Phase 0/1)
  |
W6   Resume agent roadmap
```

---

### Phase W-1 — Developer Experience (2-3 days) *(new, do first)*

Before shipping anything, make the whole system start with one command. You'll thank yourself later.

- `docker compose up` starts **everything** (API, Postgres, Redis, Qdrant, monitoring).
- One `.env` (documented), one README.
- Health checks on every service.
- Seed script: seed database + a test user.
- Smoke test that hits the pipeline end to end.

**Exit:** a fresh clone runs in one command and passes a health check.

---

### Phase B — Architecture freeze *(new, before W0)*

Not in the original phase order above — inserted between repo hardening
(Phase W-1 / "Phase A" in project shorthand) and AWS setup, so cloud
issues and application issues aren't debugged simultaneously. Declared
in **`docs/adr/ADR-006-v1-architecture-freeze.md`**: env vars, core
voice-loop HTTP APIs, Docker/Compose/Dockerfile, and `docs/` layout are
frozen; the MCP/agent-tool surface (`/mcp/*`, `/agent/loop`) is
explicitly excluded (still consolidating, deferred to Phase W5/W6);
Docker Compose is declared the canonical, AWS-bound startup path over
the native `start_stack.ps1`/`dev_manager.py` paths.

**Exit:** ADR-006 accepted and merged into `dev-init`.

---

### Phase W0 — Decisions & AWS setup (2-3 days)

Record each choice + rationale in `DECISIONS.md`.

1. **GPU strategy on AWS** — choose one:
   - **(A)** GPU EC2 instance (e.g. `g5`/`g6` family) running Whisper + Ollama/Qwen + Piper as-is. Lowest code change, full control, higher fixed cost.
   - **(B)** Offload STT and/or TTS to hosted APIs, keep LLM on GPU EC2 or hosted. Lower GPU spend, adds per-request cost + external latency + vendor dependency.
   - **Recommendation for v1:** (A) — keep the validated pipeline intact. Move selectively to (B) only if GPU cost blocks launch.
2. **Deploy target** — single GPU EC2 + Docker Compose behind an ALB (or Caddy/nginx) with HTTPS. Orchestration (ECS/EKS) deferred until load demands it.
3. **Data stores** — RDS Postgres, ElastiCache Redis, Qdrant (self-hosted on the box or managed). Keep it minimal.

**Exit:** `DECISIONS.md` written; AWS account + networking + a running GPU instance reachable.

---

### Phase W1 — Deploy + streaming, single user (1-2 weeks)

Get the *existing* pipeline running on AWS and reachable before any multi-user work.

- Containerize FastAPI; deploy to the GPU instance; HTTPS in front.
- **WebSocket audio streaming:** client streams mic audio -> server runs streaming STT->LLM->TTS -> streams audio back. Interruption handling transfers — it fires on a socket message instead of a local event.
- Verify GPU resource locking works on the server (it will soon guard a *shared* GPU).

**Exit:** one browser client on the internet holds a streaming voice conversation with Astra on AWS, interruptions working.

---

### Phase W2 — Monitoring + admission control (4-6 days) *(moved earlier)*

Instrument **before** the second user, or you debug blind. Observability, audit logging, and policy enforcement are first-class here, not add-ons.

**Metrics to expose from day one:**
- GPU queue length + GPU utilization
- Whisper (STT) latency
- LLM latency
- TTS latency
- WebSocket disconnect rate
- Active users / active streams
- Memory usage

Structured logging (reuse the agent Phase 0 logging design): request id, user id, per-stage latency, tool calls. Ship a minimal dashboard (Prometheus + Grafana, or CloudWatch). This also seeds the eval system (currently 2/10).

**Admission control — make it explicit, never let latency grow unbounded:**

```
Request arrives
  |
GPU busy? -- no --> serve
  | yes
  |
Queue, wait up to ~8s
  |
Still busy? -- yes --> reject with "retry later"
```

**Exit:** live per-stage latency + GPU + disconnect dashboards; requests are admitted or cleanly rejected, never queued indefinitely.

---

### Phase W3 — Auth + per-user isolation (1-2 weeks)

Now that you can measure, add users.

- **OAuth login** (Google/GitHub) -> signed session token (opaque token in Redis or JWT).
- **User model:** minimal `users` table in Postgres (`id`, `email`, `provider`, `created_at`).
- **Per-user memory isolation in Qdrant:** `user_id` payload on every vector; filter *all* retrieval by `user_id`. (Per-user collections are an alternative — simpler isolation, more collections; payload-filter is usually the v1 call.)
- **Conversation isolation:** history keyed by `user_id`.
- **Isolation test (privacy-critical, must pass):** two accounts, zero cross-contamination in retrieval or history.

**Exit:** two users log in, chat, and neither can see the other's memory or history.

---

### Phase W4 — Quotas, feature flags, admin page (1-2 weeks)

**Quotas, not just rate limiting.** Track the things pricing will eventually be based on:
- GPU seconds
- Audio minutes
- Tokens
- Tool calls
- Concurrent streams

(Keep the simple req/min limiter too, but these usage counters are the real unit of account.)

**Feature flags from day one.** Without them every deploy is all-or-nothing risk. Flag per-user / per-cohort:
- models
- prompts
- TTS engine
- tools
- memory behavior
- duplex

```
User A -> New TTS        User B -> Old TTS
```

**Admin page (server-side control) — yes, you need this.** Minimum viable admin, gated to admin accounts:
- **Users:** list, view usage/quotas, disable/enable, promote to admin.
- **Feature flags:** toggle flags per user/cohort without redeploying.
- **Tools / MCP:** enable/disable tools per user or globally, view which tools are registered, reconcile against `.mcp.json` (single registry of record — do not fork it).
- **Quotas:** set/adjust limits per user.
- **Observability:** surface the W2 metrics + audit log of tool calls and admin actions.
- **Admission/queue:** view current queue length, active streams.

Keep it a thin internal panel (protected route + simple UI) — not a product surface yet.

**Exit:** an admin can add/disable users, flip feature flags, toggle tools, and adjust quotas from a page; usage counters accrue per user.

---

### Phase W5 — Tools behind a permission filter (overlaps agent Phase 0/1)

Ship 2-3 tools sensible for a *hosted web* user (web search, PDF/document summarization). No local file/browser access — that's Companion territory, deferred.

**Security architecture — don't let the LLM see every tool.** Architectural filtering is far more reliable than prompt instructions for preventing unauthorized tool use:

```
User -> Gateway -> Permission Filter -> Visible Tools -> LLM
                                            |
                          (re-enforce permission at invocation)
```

- Build on the typed tool interface + registry from agent Phase 0, **multi-user-aware**: every call carries `user_id` and honors per-user quotas.
- **Filter visible tools per user** *before* they reach the model, **and re-check permission again at invocation** — defense in depth, not the confirmation gate alone.
- **Confirmation gate** still wraps anything destructive (carried from your top-4 risks). For v1's read-only tools it's light, but wire it now.
- **Single registry:** reconcile with `.mcp.json`; no duplicate registry.

**Exit:** a hosted user only sees tools they're authorized for; permission is enforced again at call time; destructive actions pass the gate; one registry of record.

---

### Phase W6 — Resume the agent roadmap

With real multi-user traffic, monitoring, quotas, flags, and a permission-filtered tool layer in place, resume `ASTRA_AGENT_PLAN.md` from Phase 0 onward — validated against actual concurrent usage and real latency data.

---

## 3. Future Companion architecture (deferred, agreed direction)

Postponed for v1, but the eventual shape:

```
Cloud -> Planner -> Gateway -> Desktop Companion -> Docker / Browser / Files / Git
```

This matches where MCP infrastructure is heading: a gateway centralizing server lifecycle, authentication, routing, credential management, and logging behind one control plane instead of every app managing MCP servers independently. Build toward it later; don't let it block the web service.

---

## 4. Explicitly deferred (do NOT build for v1)

| Deferred | Why it waits |
|----------|--------------|
| Docker MCP Gateway / Companion desktop app | Only matters for *local* file/browser/git access from the user's own machine. |
| Multi-agent orchestration (agent Phase 3) | Latency + complexity before the service is proven. |
| Computer use / autonomy (agent Phase 4) | Later differentiator, not a v1 blocker. |
| ECS/EKS orchestration, Celery, heavy infra | Single GPU EC2 + Compose + Redis + Postgres is enough for v1. |

---

## 5. Condensed sequence

1. **W-1** One-command dev environment (2-3 days)
2. **B** Architecture freeze (ADR-006 — done)
3. **W0** Decisions + AWS setup (2-3 days)
4. **W1** Deploy pipeline + WebSocket streaming, single-user (1-2 wks)
5. **W2** Monitoring + admission control — *before* multi-user (4-6 days)
6. **W3** OAuth + per-user isolation (1-2 wks)
7. **W4** Quotas + feature flags + admin page (1-2 wks)
8. **W5** Tools behind permission filter (overlaps agent Phase 0/1)
9. **W6** Resume agent roadmap against real traffic

**Rough total to v1:** ~6-9 weeks, with W5 doubling as agent-track progress.

---

## 6. Risk register (v1-specific)

- **Shared GPU contention** — biggest new failure mode. Bounded admission control (W2) + verified GPU locking (W1). Test 2+ simultaneous streams before launch.
- **Cross-user data leakage** — privacy-critical must-pass isolation test (W3).
- **Debugging blind** — mitigated by moving monitoring ahead of multi-user (W2).
- **Risky deploys** — mitigated by feature flags from day one (W4).
- **Unauthorized tool use** — mitigated by architectural permission filtering + invocation-time re-check (W5), not prompt instructions.
- **Registry duplication** — reconcile new tools with `.mcp.json`; admin page reads that single source.
- **Loop entanglement** — keep `orchestrator/pipeline.py` and `agent/` separate under all multi-user changes (the core invariant).
