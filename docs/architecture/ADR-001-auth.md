# ADR-001: Authentication via OAuth (Google/GitHub)

**Status:** Accepted

## Context

The Astra web service (`docs/ASTRA_WEB_SERVICE_PLAN.md`) needs a login
mechanism before Phase W3 (auth + per-user isolation) can begin. Building
and maintaining a password-based auth system (hashing, reset flows, email
verification, breach handling) is significant surface area that doesn't
differentiate the product.

## Decision

Use OAuth via Google and GitHub as the sole login mechanism for v1. Skip
password-based authentication entirely.

## Consequences

- No password storage, reset flows, or credential-stuffing surface to
  build or defend.
- Users without a Google or GitHub account cannot sign up for v1 — accepted
  tradeoff, revisit if it blocks adoption.
- Session handling (Phase W3) issues a signed session token (opaque token
  in Redis or JWT) after the OAuth handshake completes.

## Alternatives considered

- **Password auth** — rejected: unnecessary implementation and security
  burden when OAuth fully covers v1's needs.

## Review date

Revisit if user feedback shows the Google/GitHub-only requirement is
blocking sign-ups.

## Source

`docs/ASTRA_WEB_SERVICE_PLAN.md` §1 (Confirmed decisions).
