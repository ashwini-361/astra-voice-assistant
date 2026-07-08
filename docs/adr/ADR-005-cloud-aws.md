# ADR-005: Target cloud platform is AWS

**Status:** Accepted

## Context

The Astra web service (`docs/roadmap/ASTRA_WEB_SERVICE_PLAN.md`) needs to run
hosted, multi-user infrastructure: a GPU instance for the pipeline, a
Postgres database, Redis, and Qdrant. A cloud platform decision is needed
before Phase W0 (AWS setup) can proceed.

## Decision

Target AWS as the cloud platform for the hosted Astra web service.

## Consequences

- Phase W0 infrastructure choices (GPU EC2 instance family, RDS Postgres,
  ElastiCache Redis, ALB/HTTPS termination) are scoped to AWS-native
  services and are tracked separately as those choices are finalized, not
  in this ADR.
- Team tooling, IAM, and networking setup target AWS conventions.

## Alternatives considered

Not evaluated in depth — AWS was the given target platform for v1; no
other cloud provider was under serious consideration for this decision.

## Review date

No scheduled revisit; this is a fixed target platform for v1.

## Source

`docs/roadmap/ASTRA_WEB_SERVICE_PLAN.md` §1 (Confirmed decisions).
