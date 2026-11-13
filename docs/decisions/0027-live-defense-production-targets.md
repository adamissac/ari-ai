# ADR-0027: Live Defense may apply controls to a production application

- Status: accepted (owner decision, 2026-11-13)
- Date: 2026-11-13

## Context

Live Defense could only reach a loopback fixture on `127.0.0.1` in an `owned_test` or
`sandbox` application, so it could never defend a running customer system. The owner chose
to allow production targets. The design follows the existing spec: a human approves every
change to a real system (docs/01 §6.3), and the control model in
[LIVE_AUTONOMOUS_DEFENSE_PLAN](../LIVE_AUTONOMOUS_DEFENSE_PLAN.md) §4.

## Decision

- `StagingEnvironment.production` exists. An owner registers the application's own control
  endpoint: https, path `/live-defense/control`, and a hostname or address that is public.
- The gate (`live_defense/authorize.py`) still runs all fifteen checks. For production it
  requires an https channel to a public host, and `block_source` takes exactly one public
  unicast address. Unsafe kinds (isolate, principal blocks, firewall, deploy, …) stay denied.
- The adapter resolves DNS at each call, refuses the host if any answer is non-public, and
  connects to the checked address with TLS verified against the registered hostname. A DNS
  change cannot point a call at Ari's internal network.
- Verification asks the endpoint (signed `inspect`). Ari sends no test traffic to production.
  The record says the effect is self-reported by the application.
- `monitoring.controls.AriControls` is the reference endpoint an application installs. It
  checks the HMAC, refuses replays, and enforces each control's expiry itself.
- Ownership: after registering, the owner presses Check endpoint. Ari sends a fresh challenge
  and the endpoint must return `HMAC(secret, "prove." + challenge)`. The gate refuses every
  control on a production channel until this succeeds; a failed re-check clears it.
- Each grant carries `protected_sources` (addresses or CIDRs) that a source block may never hit.
- With `CONTROL_SECRET_KEY` set, channel secrets are stored Fernet-encrypted.

Unchanged: each control kind needs an owner grant (duration and hourly budget), each control
needs an owner's click, RL-gated pilot apps stay shadow-only, AUTO-EXECUTE is rejected, and
the RL policy only recommends.

## Consequences

- An owner can now rate-limit a route, block one address or raise logging on their live app.
  A wrong source block can lock out a real user behind that address until the control expires
  or is rolled back.
- Verification is weaker than on the fixture: it trusts the application's report.
- The loopback-only rule moved from database checks to the gate and adapter (migration 0022).
- Not done: non-Python control endpoints, key rotation for `CONTROL_SECRET_KEY`, and
  re-encrypting secrets written before the key was set.
