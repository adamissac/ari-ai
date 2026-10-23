# ADR-0020: Per-project fix delivery mode (auto, pull request, manual)

- Status: Accepted
- Date: 2026-10-23
- Decision: Requested by the repository owner: teams should not have to accept Ari's work; it commits for them by default, with a setting to wait for human review as a pull request.

## Context

Until now every remediation needed a human approval and nothing Ari produced reached a customer repository (the GitHub App asked only for `contents: read`; Patch could not push).

## Decision

`ProjectSettings.delivery_mode` (shared 0.19.0):

- **auto** (default): remediation approvals are approved in the name of the authorizing owner and each patch with an `accepted` independent Verify verdict is committed onto the default branch, authored by `Ari`. The push only happens if the branch still points at the commit that was assessed and verified, so exactly the tested tree ships. If the branch moved, or the push is refused (branch protection), Ari opens a pull request instead.
- **pull_request**: same pre-approval, but the fix always goes to a branch `ari/fix-<patch id>` and a PR. The team reviews and merges.
- **manual**: today's behaviour. A human approves each remediation; nothing is pushed.

`delivery_authorized_by` is written only by the server: the owner creating the project, or saving settings with a changed mode (kept while the mode is unchanged). It is checked on every use: if that user is no longer an owner of the organization, delivery behaves as manual. Projects created before this change have no authorizer and stay manual until an owner saves settings. Switching on delivery also approves runs already waiting for approval.

Unchanged and deterministic: scope approval (still explicit), sandbox limits, Verify independence and its five checks, the security agents' requirement of an identified human approver (the stamped owner), budgets. Rejected, inconclusive or unverified patches never leave the sandbox. Nothing is force-pushed. The mode is re-checked when the delivery job runs, so switching to manual stops queued deliveries. Every switch, auto-approval and outcome is a hash-chained audit event (`delivery.<mode>`, `approval.auto_approved`, `delivery.pushed|pr_opened|failed|skipped`).

## Consequences

- Operators must grant the GitHub App **Contents** and **Pull requests: Read & write** and each installation must accept it. Write tokens are minted only for delivery; all other token requests stay read-only. Until granted, delivery fails with a recorded reason.
- The web UI asks for confirmation before enabling auto-commit.
- The git token is passed to git through the environment, not the command line.
- Auto approvals are system decisions on the owner's standing authorization; the manual decision endpoint keeps its approver-differs-from-requester rule.

## Verification

`backend/tests/test_auto_delivery.py`: default and server-side stamping, manual keeps the gate, authority ends when the authorizer loses ownership, owner-name approval and queued delivery, switching on unblocks waiting runs, auto push, fallback to PR when the branch moved, PR mode never touches the default branch, missing App permission recorded, switching to manual skips queued work, and real-git push tests (tip check, new branch, patch that does not apply, branch validation). Frontend tests cover the switch PATCH and the confirmation.
