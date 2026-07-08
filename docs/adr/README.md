# Architecture Decision Records

This directory records significant, locked architectural decisions for
Astra as individual ADRs — one decision per file, so each can be updated,
superseded, or referenced independently (e.g. in PRs) without editing a
single growing document.

Each ADR follows the same template: Status, Context, Decision,
Consequences, Alternatives considered, Review date, Source.

## Index

| ADR | Decision |
|-----|----------|
| [ADR-001](ADR-001-auth.md) | Authentication via OAuth (Google/GitHub) |
| [ADR-002](ADR-002-transport.md) | Transport via WebSocket (not WebRTC) |
| [ADR-003](ADR-003-companion-deferred.md) | Companion/Desktop app deferred |
| [ADR-004](ADR-004-loop-separation.md) | Keep the realtime voice loop and agent loop strictly isolated |
| [ADR-005](ADR-005-cloud-aws.md) | Target cloud platform is AWS |

New architectural decisions should be added here as `ADR-006`, etc., once
actually locked (not while still under discussion as options in a phase
plan).
