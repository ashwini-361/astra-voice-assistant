# ADR-004: Keep the realtime voice loop and agent loop strictly isolated

**Status:** Accepted — highest-priority constraint, survives all phases

## Context

Astra has two loops with fundamentally different requirements:

- **Realtime voice loop** (STT -> LLM -> TTS, `orchestrator/pipeline.py`) —
  optimized for low latency.
- **Agent loop** (Planner -> Tools -> Memory -> long reasoning,
  `services/agent_control/` + `services/llm_service.py`) — optimized for
  throughput and correctness.

If these loops share a call path, every future agent feature (longer
planning, more tool calls, deeper reasoning) directly slows down live
voice conversations. As of this writing, `orchestrator/pipeline.py` has no
dependency on `services/agent_control`; the agent loop is only reached via
`services/llm_service.py`, which runs as its own process/service
(port 8002 in `services/dev_manager.py`) with its own `/agent_loop`
endpoint.

## Decision

Keep the two loops architecturally and operationally separate under all
future multi-user, web-service, and agent-roadmap changes. The realtime
voice pipeline must never import from or block on `services/agent_control`.

## Consequences

- Voice latency work and agent capability work can proceed independently
  without one regressing the other.
- Any future PR that adds an import from `orchestrator/pipeline.py` (or its
  direct dependencies) to `services/agent_control` should be treated as a
  regression against this decision, not a refactor to wave through.
- The agent loop remaining a separate service also enables independent
  scaling/deployment of the two loops later.

## Alternatives considered

- **Unify into a single loop** — rejected: conflates two workloads with
  incompatible latency/throughput requirements; every agent feature would
  then cost voice latency.

## Review date

This is a durable, highest-priority constraint — not scheduled for
revisit. Re-open only if a concrete design shows the loops can share
infrastructure without latency coupling.

## Source

`docs/roadmap/ASTRA_WEB_SERVICE_PLAN.md` §0 (Core invariant), §1 (Confirmed
decisions), §6 (Risk register — "Loop entanglement").
