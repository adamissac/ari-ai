# ADR-0016: Owner approval for sandbox-only scopes

- Status: Accepted
- Date: 2026-10-19
- Decision: Explicitly authorized by the repository owner in this session.

## Context

A personal GitHub organization maps to a project with one owner. Requiring a different owner to activate its sandbox scope makes real assessments impossible without adding another account. The commit panel also loaded scope status only once, leaving it stale after an external approval.

## Decision

A project owner may explicitly approve a scope they requested when its target list is nonempty and every target is `sandbox_build`. The API continues to enforce owner membership, project isolation, pending status, expiry, permitted target types and audit recording. Approval records the actual approving identity and whether approval was by the requester. No scope is auto-approved, and approval does not start an assessment or spend provider credits.

Other scope types do not gain this exception. The generic remediation/PR approval endpoint retains its independent approver rule. Sandbox networking, process isolation and deterministic scope checks are unchanged.

## User flow

The commit panel offers Approve sandbox authorization, then Run the 7 agents once fresh state confirms activation. The scopes page enables the same explicit action. Status refreshes every ten seconds and on window focus; expired pending scopes do not block a new request. A failed refresh is visible, never presented as current data.

## Verification

Backend API tests cover owner self-approval, independent owner approval, denial for ordinary members and outsiders, persisted approval state and repeat-decision rejection. Frontend tests cover explicit approval, refreshed run availability, focus/poll refresh and expired pending requests.
