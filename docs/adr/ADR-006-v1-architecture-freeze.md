# ADR-006: v1.0 architecture freeze

**Status:** Accepted

## Context

Phase A (`docs/backlog.md`, ADR-001..005) hardened the repo for
reproducibility: `.env` bootstrap, config/URL cleanup, test stabilization,
docs reorg. `docs/roadmap/ASTRA_WEB_SERVICE_PLAN.md` puts AWS setup next
(Phase W0). Deploying against a still-shifting local architecture means
debugging cloud issues and application issues at the same time. Before
Phase W0, this ADR declares which parts of the architecture are frozen —
stable enough to build AWS infrastructure against without expecting the
shape to change underneath it.

A 2-agent audit (2026-07-08) checked every part of this freeze definition
against the current repo state: environment variables, core HTTP APIs,
Docker/Compose/Dockerfile, and the startup process.

## Decision

Freeze the following surface as of this ADR:

- **Environment variables** — the full `AI_ASSISTANT_*` surface defined by
  `core/config.py`'s `Settings` class (34 fields), confirmed 1:1 against
  `.env.example` with zero drift. Two documented, intentional exceptions
  are part of the frozen surface too: `AI_ASSISTANT_WHISPER_MODEL_NAME`
  (read via `os.getenv`, not a `Settings` field) and
  `VITE_DEV_MANAGER_API_BASE` (frontend-only Vite var).
- **Core voice-loop HTTP APIs** — request/response shape of:
  - `services/whisper_service.py`: `/transcribe`, `/health`
  - `services/tts_service.py`: `/speak`, `/synthesize`, `/stop`,
    `/settings`, `/settings/reset`, `/streaming-config`, `/health`
  - `services/intent_service.py`: `/classify`, `/health`
  - `services/llm_service.py` (core-generation subset only —
    see exclusion below): `/generate`, `/providers`, `/models`,
    `/settings`, `/settings/reset`, `/stop`, `/metrics`, `/health`
- **Docker/Compose/Dockerfile structure** — `docker-compose.yml`,
  `docker-compose.gpu.yml`, `Dockerfile`, `Makefile` targets.
- **`docs/` layout** — `docs/{adr,architecture,development,deployment,
  roadmap,archive}/` as reorganized in Phase A.
- **Canonical startup path**: **Docker Compose** (`make up` /
  `docker compose up`) is the frozen, AWS-bound startup process.
  `start_stack.ps1` (native, with or without `-UseDevManager` +
  `services/dev_manager.py`) remains a Windows dev-convenience tool,
  explicitly **outside** the frozen deployment surface. All three paths
  independently encode env-var/port assumptions today with no observed
  divergence, but only the Compose path is guaranteed to stay in sync
  going forward.

## Explicitly excluded from this freeze

**`services/llm_service.py`'s `/mcp/*` and `/agent/loop` endpoints** are
not frozen. The audit found this surface still actively consolidating:

- A duplicate endpoint alias (`/mcp/docker/call` vs.
  `/mcp/docker/tools/call`, same handler).
- Three overlapping tool-registry mechanisms in flight: the in-memory
  `TOOLS` dict, `list_servers()`/`upsert_server()`, and `mcp_bridge` for
  Docker-hosted MCP servers.
- Three confirmed logic bugs already tracked as `xfail` in
  `docs/backlog.md` (`route_intent` URL-prioritization, `infer_category`
  naming, `get_allowed_categories` category tracking), plus a
  non-strict-xfail test-isolation gap in the agent-loop error path.

This matches `docs/roadmap/ASTRA_WEB_SERVICE_PLAN.md`'s own stated
philosophy — "web service" and "agent capability" are separable tracks —
which defers agent-tool work to Phase W5/W6. Changes to `/mcp/*` or
`/agent/loop` do **not** violate this freeze; fixing or reshaping that
surface is future agent-roadmap work, not scope creep against ADR-006.

## Known empirical risk points (freeze with caveat, not blocked)

These are documented, validate-on-new-machine concerns inherited from
Phase A, not active redesign — freezing the surface doesn't require
resolving them first, but they should be checked against the actual AWS
GPU instance before relying on them:

- GPU reservation syntax in `docker-compose.gpu.yml` varies by Docker
  Compose version (`deploy.resources.reservations.devices` vs.
  `runtime: nvidia` + `NVIDIA_VISIBLE_DEVICES`).
- CPU `onnxruntime` (containers) vs. native `onnxruntime-directml`
  behavioral parity — intent service reports `fallback_mode: true`
  under CPU-only.
- The Qdrant healthcheck's `bash`-specific `/dev/tcp` construct, verified
  empirically against the pinned `qdrant/qdrant:v1.12.1` image only.
- The `libctranslate2` ELF-patch workaround in `Dockerfile` (clears the
  executable-stack flag) — tied to the current base image/ctranslate2
  version.

## Consequences

- Structural changes to the frozen surface (new required env var without
  a default, breaking change to a core-loop endpoint shape, Docker/Compose
  restructuring, moving `docs/` again) require a new ADR that amends or
  supersedes this one before landing — a deliberate-acknowledgment gate,
  not a literal lock (this is a solo-maintainer repo, not a process with
  reviewers to block).
- Work on `/mcp/*`/`/agent/loop` can proceed freely under the agent
  roadmap without touching this ADR.
- AWS setup (roadmap Phase W0) can now proceed against a surface that
  isn't expected to shift underneath it, modulo the empirical risk points
  above (validate on the actual instance, don't assume).

## Alternatives considered

- **Freeze everything including `/mcp/*`/`/agent/loop`** — rejected: would
  either block AWS setup on fixing agent-track bugs (scope creep) or
  freeze a surface everyone already knows is going to change, making the
  freeze meaningless there.
- **Leave the dual startup paths (Compose vs. native) unresolved** —
  rejected: naming Docker Compose as canonical costs nothing (no code
  change) and removes ambiguity about which path AWS deployment should be
  validated against.

## Review date

Revisit when Phase W5/W6 (agent roadmap resumption) is ready to fold the
MCP/agent-tool surface into a future frozen-surface ADR, or if AWS setup
(Phase W0/W1) surfaces a reason to amend the frozen surface.

## Source

User-defined Phase B criteria (no major directory restructuring, stable
APIs, stable environment variables, stable Docker images, stable Compose,
stable startup process); `docs/roadmap/ASTRA_WEB_SERVICE_PLAN.md` (Phase
W0, and the web-service/agent-capability separable-tracks principle);
`docs/backlog.md` (MCP/agent-tool known issues); 2-agent audit,
2026-07-08.
