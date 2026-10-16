# Team assignments

**All roles are UNASSIGNED.** Team size and members are unconfirmed (RQ-014).
When owners are agreed, fill this table and replace the placeholders in
[.github/CODEOWNERS](../../.github/CODEOWNERS).

| Role | Owns | Owner | Backup | CODEOWNERS placeholder |
|---|---|---|---|---|
| Lead / product | Scope, roadmap, demo story, phase gates | UNASSIGNED | UNASSIGNED | `@OWNER-LEAD` |
| Contracts owner | `shared/`, docs 12 & 13, contract-change reviews | UNASSIGNED | UNASSIGNED | `@OWNER-CONTRACTS` |
| Frontend | `frontend/` | UNASSIGNED | UNASSIGNED | `@OWNER-FRONTEND` |
| Backend / platform | `backend/`, queue, LLM gateway, infra | UNASSIGNED | UNASSIGNED | `@OWNER-BACKEND` |
| Code intelligence | `code-intelligence/` | UNASSIGNED | UNASSIGNED | `@OWNER-INTEL` |
| Review & repair | `code-review/` | UNASSIGNED | UNASSIGNED | `@OWNER-REVIEW` |
| Security agents & boundaries | `security-agents/`, doc 15, check library | UNASSIGNED | UNASSIGNED | `@OWNER-SECURITY` |
| RL | `rl-defense/`, protocol 17 | UNASSIGNED | UNASSIGNED | `@OWNER-RL` |
| Monitoring / integrations | `monitoring/`, GitHub App | UNASSIGNED | UNASSIGNED | `@OWNER-MONITORING` |
| Testing / evaluation | `tests/`, SB suite, e2e | UNASSIGNED | UNASSIGNED | `@OWNER-TESTING` |

## Suggested combinations for a small team (proposal)

| Team size | Combination |
|---|---|
| 3 | (Lead + Frontend), (Backend + Monitoring + Testing), (Intel + Review + Security + RL split as needed) |
| 4 | Lead/Frontend · Backend/Monitoring · Intel/Review · Security/RL |
| 5 | Lead/Frontend · Backend · Intel/Review · Security · RL/Monitoring/Testing |

The security-owner role must be held by someone other than the main author of
any safety-critical PR they review.
