# ADR-0020: Independent authorization gate is the final authority for live controls

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-23 |
| Deciders | Alan (interim `shared/` / live-defense owner) |
| Related | [ADR-0008](0008-offline-double-dqn.md), [ADR-0016](0016-owner-sandbox-approval.md), [ADR-0017](0017-runtime-principal-detection.md), [ADR-0019](0019-constrained-rl-foundation.md) (Codex; unrelated numbering), [LIVE_DEFENSE_PHASE4_PLAN](../planning/LIVE_DEFENSE_PHASE4_PLAN.md), docs/15 |

## Context

Phase 1–3 record shadow recommendations from deterministic rules and (when serving
assumptions hold) frozen v6. Those rows are explicitly `NOT_EXECUTED`. Phase 4
introduces **executable** actions against a registered owned-test application.
If a model, neural net, or typed `usr_*` string could approve those actions, the
authorization trust boundary would collapse.

ADR-0019 on `main` is Codex's constrained-RL foundation. This decision is numbered
**0020** so the two ADRs do not collide.

## Decision

1. `authorize.check` is a pure function. It is the final authority for whether a
   control may enter `authorized`. LLM output, v6 Q-values, and rule hit text
   are never inputs to the pass/fail decision beyond the already-typed action
   kind and target the analyst submitted.
2. Analyst **review** (accept/reject) remains a recorded opinion and never
   transitions a control to `executing`.
3. Approvals are bound to the exact tuple `(kind, target_type, target_value,
   duration_s, application_id)`. Changing any field is a different request.
4. The actor is the authenticated session. A body field matching `usr_*` is not
   identity. Extra actor fields are rejected (`extra="forbid"`).
5. Rules-originated and v6-originated proposals take the same gate. There is no
   fast path.
6. Fail closed: missing grant, missing channel, kill switch, unresolved failed
   control, or any raised exception is a denial.
7. The adapter talks only to a server-registered loopback URL. Browsers cannot
   supply the destination.

## Options considered

| Option | Pros | Cons |
|---|---|---|
| Reuse NIST incident two-person approve as execute | Fewer types | Mixes human IR lifecycle with machine enforcement; Phase 3 forbade this |
| Let v6 / rules execute when confidence is high | Faster | Model as authority; contradicts docs/15 §7 |
| Independent gate + distinct lifecycle (this) | Auditable, fail closed, reversible | More API surface |

## Consequences

- Executable actions exist, but only after the gate, only on an owned-test app,
  and only for the four allowlisted kinds.
- Customer production remains ungated because no production environment exists
  in `StagingEnvironment`.
- Phase 5 must not weaken this ADR. Autonomous execution would be a new ADR.

## Revisit when

A production environment class is proposed, or a second human approver is
required for owned-test controls.
