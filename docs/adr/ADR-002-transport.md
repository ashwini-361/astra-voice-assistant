# ADR-002: Transport via WebSocket (not WebRTC)

**Status:** Accepted — v1 only, revisit after public beta

## Context

Phase W1 of `docs/roadmap/ASTRA_WEB_SERVICE_PLAN.md` requires streaming mic audio
from browser clients to the server and streaming synthesized audio back,
with low-latency interruption handling. WebRTC would offer lower-latency
peer-to-peer media transport but adds substantial complexity (ICE/STUN/TURN,
SDP negotiation, media server infrastructure) that isn't justified by the
current architecture.

## Decision

Use WebSocket for audio streaming in both directions for v1. Interruption
handling fires on a socket message instead of a local event, but the
transport mechanism itself does not change.

## Consequences

- Simpler implementation and operational surface — no TURN/STUN
  infrastructure, no SDP negotiation.
- WebSocket carries higher per-frame overhead than WebRTC's media transport;
  acceptable for v1's single-GPU, moderate-concurrency target.
- If latency or scale requirements outgrow WebSocket (e.g. many concurrent
  streams, stricter jitter requirements), WebRTC becomes worth the added
  complexity.

## Alternatives considered

- **WebRTC** — rejected for v1: no reason to take on its complexity given
  the current architecture and scale.

## Review date

Revisit after public beta, once real concurrency and latency data (Phase
W2 metrics) show whether WebSocket is a bottleneck.

## Source

`docs/roadmap/ASTRA_WEB_SERVICE_PLAN.md` §1 (Confirmed decisions).
