# ADR-0020: Per-project fix delivery mode (review or auto)

- Status: Accepted
- Date: 2026-10-23
- Decision: Explicitly requested by the repository owner ("toggle between reviewing all the changes, or having all of it committed and pushed to their repo by Ari automatically, no check").

## Context

Until now every remediation needed a human approval, and nothing Ari produced ever reached a customer repository: the GitHub App asked only for `contents: read`, and Patch could not push. The owner wants a per-project switch that keeps that behaviour as the default and offers a fully automatic alternative.

## Decision

`ProjectSettings.delivery_mode` (shared 0.19.0) is `review` (default) or `auto`.

- **review**: unchanged. A human approves each remediation; nothing is pushed.
- **auto**: when an assessment pauses in `AWAITING_APPROVAL`, its pending *remediation* approvals are approved with `decided_by` set to the owner who switched auto on (`auto_delivery_enabled_by`, written only by the server on the PATCH that enables it; a client value is ignored). The run resumes. Each patch whose independent Verify verdict is `accepted` (all five checks) enqueues `deliver_verified_patch`, which applies the diff onto the current tip of the repository's default branch and pushes a commit authored by `Ari`. Pushes are never forced; a patch that no longer applies is recorded as `delivery.failed` and not pushed.

What stays deterministic and unchanged: scope approval (still explicit), sandbox limits, Verify independence, the security agents' "identified human approver" check (the stamped approver is that owner), budgets. Rejected, inconclusive or unverified patches never leave the sandbox. The mode is re-checked when the push job runs, so switching back to review stops queued pushes. Every switch, auto-approval and delivery outcome is a hash-chained audit event (`delivery.auto|review`, `approval.auto_approved`, `delivery.pushed|failed|skipped`).

## Consequences

- Operators must grant the GitHub App **Contents: Read & write**, and each installation must accept it, before auto pushes succeed. Write tokens are minted only by `deliver_verified_patch`; every other token request stays read-only.
- Auto mode commits straight to the default branch with no human check. Branch protection on that branch will (correctly) reject the push and is reported as `delivery.failed`.
- Approver-must-differ-from-requester still applies to the manual decision endpoint; auto approvals are system decisions on the owner's standing authorization.

## Verification

`backend/tests/test_auto_delivery.py`: server-side stamping and clearing of the authorizer, review mode keeps the pending approval, auto mode approves in the owner's name, completes the run and queues delivery (and refuses to push for a repository not connected through the App), real-git push onto the branch tip, refusal of a patch that no longer applies, branch-name validation. Frontend unit tests cover the switch PATCH.
