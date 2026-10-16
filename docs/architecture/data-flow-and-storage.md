# Data flow and storage

Status: **specified**. Decision: [ADR-0005](../decisions/0005-postgres-primary-store-and-queue.md).

## Stores

| Store | Contents | Trust of contents |
|---|---|---|
| PostgreSQL | Tenancy, scopes, approvals, assessments, runs, intelligence facts, findings, events, queue, audit | Mixed: fields derived from repos/LLMs are untrusted *data* |
| Artifact store (`ARTIFACT_STORE_URI`) | Diffs, sandbox logs, transcripts, reports, raw webhook payloads, RL checkpoints | Untrusted data; served with `Content-Type: text/plain` / download only |
| Worker workspaces | Clones, worktrees | Untrusted; ephemeral; deleted after job |

## Table groups (planned)

| Group | Tables |
|---|---|
| tenancy | `organizations`, `users`, `memberships`, `projects`, `repositories` |
| authz | `authorized_scopes`, `scope_targets`, `approvals` |
| intel | `snapshots`, `files`, `symbols`, `import_edges`, `call_edges`, `entry_points`, `expectations` |
| assurance | `assessments`, `agent_runs`, `findings`, `finding_status_changes`, `hypotheses`, `validation_results`, `attack_paths`, `root_causes`, `remediation_plans`, `patch_candidates`, `verification_results`, `hardening_recommendations`, `regression_tests`, `test_runs` |
| ops | `monitoring_events`, `reassessment_requests`, `defense_recommendations`, `rl_checkpoints` |
| infra | `jobs`, `audit_events`, `llm_usage` |

All tenant tables carry `org_id` and `project_id`; every query goes through a
repository layer that requires them.

## Artifact addressing

`artifact_uri = <store>/<org_id>/<project_id>/<kind>/<id>` plus `sha256` stored in
the referencing row; readers verify the hash.

## Retention (MVP defaults)

| Data | Retention |
|---|---|
| Sandbox logs, transcripts, raw webhooks | 30 days |
| Findings, verification results, audit | Project lifetime |
| Workspaces / worktrees | Deleted at job end |
| RL checkpoints | Until superseded + 1 |

Project deletion cascades DB rows and artifact prefixes; audit events are kept
(with subject IDs only) for 1 year (policy to confirm, RQ-013).
