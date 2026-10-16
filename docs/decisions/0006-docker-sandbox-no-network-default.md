# ADR-0006: Hardened Docker sandboxes, no network by default

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-10-16 |
| Deciders | UNASSIGNED (ratify in DOCS-002) |
| Related | [15](../15_SECURITY_BOUNDARIES.md), [architecture/sandbox-and-authorization](../architecture/sandbox-and-authorization.md), SEC-003 |

## Context
The platform runs untrusted repository code (tests) and validation checks. It must work on team laptops for the hackathon.

## Decision
Every untrusted execution runs in an ephemeral Docker container: non-root, all capabilities dropped, no-new-privileges, read-only rootfs, tmpfs /tmp, resource and time limits, no host mounts, no Docker socket, network `none` by default. `target-only` mode uses a per-step internal network containing only the scoped target, created after `scope_guard` approval.

## Options considered
| Option | Pros | Cons |
|---|---|---|
| Hardened Docker | Available everywhere; fast | Shared kernel; weaker isolation |
| gVisor (runsc) | Stronger syscall isolation | Linux-only; setup on laptops |
| Firecracker microVMs | Strong isolation | Linux/KVM only; heavier |
| Hosted sandbox service | No local setup | Paid; data leaves our boundary |

## Consequences
- Isolation is adequate only for repos we own (MVP); third-party repos require SEC-102 first.
- The worker needs Docker API access, a known risk (R-03).

## Revisit when
Before onboarding any repository we do not own.
