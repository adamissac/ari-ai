# ADR-0009: GitHub App for repository access and webhooks

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-10-16 |
| Deciders | UNASSIGNED (ratify in DOCS-002) |
| Related | [25](../25_INTEGRATION_STRATEGY.md), MON-001, CORE-005 |

## Context
The platform clones repos, receives push/PR events, and (later) opens PRs. Personal access tokens are over-privileged and long-lived.

## Decision
Use a GitHub App with least-privilege permissions (contents read, metadata read, pull requests write only for PR creation; events push and pull_request). Use short-lived installation tokens per job. Sign-in uses a separate OAuth app with `read:user`.

## Options considered
| Option | Pros | Cons |
|---|---|---|
| GitHub App | Fine-grained, short-lived tokens, per-repo install | Setup complexity |
| OAuth app user tokens | Simple | Broad scopes; tied to a user |
| PATs | Simplest | Long-lived, over-privileged |

## Consequences
- Webhook secret and app private key are required secrets.
- Local development needs a tunnel or webhook replay.

## Revisit when
Support for GitLab/Bitbucket is required.
