# Backlog (post-MVP and stretch)

Owners UNASSIGNED. IDs use the `1xx` range per prefix. Stretch items may be
pulled into MVP only if MVP tasks they would compete with are `DONE`.

| ID | Title | Type | Rationale / trigger | Depends on |
|---|---|---|---|---|
| INTEL-101 | JavaScript/TypeScript extraction + Express adapter | stretch | FR-1-08; broadens demo | INTEL-003 |
| INTEL-102 | User confirm/edit expectations UI + API | stretch | FR-1-04 | INTEL-006, UI-001 |
| INTEL-103 | pgvector semantic retrieval | later | If lexical recall insufficient (ADR-0010 revisit) | INTEL-007 |
| SEC-101 | GitHub PR creation from verified patch | stretch | FR-2-08 | SEC-010, CORE-005 |
| SEC-102 | gVisor/Firecracker sandbox runtime | later | Before third-party repos (R-03) | SEC-003 |
| SEC-103 | Additional check-template categories | later | Coverage growth; each needs security review | SEC-005 |
| SEC-104 | Staging-URL scope targets with ownership verification | later | Requires new contract + legal review | CORE-007 |
| MON-101 | PR comments / commit statuses | stretch | Developer workflow | MON-003 |
| MON-102 | OpenTelemetry runtime ingestion | later | Real telemetry | MON-004 |
| MON-103 | Dependency advisory polling (OSV) | later | SCA coverage | MON-002 |
| RL-101 | Ablations (DQN vs DDQN, features, reward sensitivity) | later | Protocol 17 §Ablations | RL-004 |
| RL-102 | Replay real monitoring signals as eval observations | later | RQ-005 transfer question | RL-004, MON-004 |
| CORE-101 | Organizations RBAC (owner/member/viewer) | later | FR-P-06 | CORE-005 |
| CORE-102 | S3-compatible artifact store | later | Hosted deployment | CORE-009 |
| CORE-103 | Queue abstraction swap (Celery/Temporal) | later | R-09 trigger | CORE-006 |
| INFRA-101 | Hosted staging (Vercel + Railway free tiers) | later | Requires approval (NFR-09) | INFRA-004 |
| INFRA-102 | Dedicated sandbox host | later | Paid; requires approval + ADR | SEC-102 |
| DOCS-101 | Contributor License Agreement / DCO policy | later | Before outside contributions | DOCS-003 |
| TEST-101 | Labeled benchmark for finding precision | later | [research/EVALUATION_DATASETS](../research/EVALUATION_DATASETS.md) | TEST-005 |
| PROD-101 | Design-partner interviews (validate A-1…A-4) | later | [02](../02_PROBLEM_AND_USERS.md) | — |

- DONE (2026-10-17): Pricing navigation uses the same color, hover, and contrast handling as sibling links.


Completed: homepage invitation and evaluation selector alignment (feat/adam/home-next-step).


Completed: centered sign-in form and reduced-motion-aware background decoration.


Completed: evaluation terminology cleanup and explicit synthetic/illustrative provenance labels.


Completed: remove homepage closing invitation at owner request.


Completed: one-time homepage video wheel landing with bounded momentum absorption and explicit continuation.


Completed: slower, smoother walkthrough video zoom after large scroll input.


Completed: owner sandbox authorization flow, live approval-status refresh and expired pending scope recovery.


Completed: #359 review fixes for selected-prefix lineage, the promised online update count, self-contained evidence export, servability/evidence promotion guards and changelog. Historical v6 artifact bytes remain unavailable and are explicitly marked as such.

Completed: PR #360 review follow-up — standalone live-layout checkpoint loading, abstention-consistent explanations, Q-ranked confidence metadata and neutral CLI provenance. No checkpoint promotion.


Completed: align browser scope approval assertion with explicit sandbox-owner approval, retaining independent Bob approval and the full persisted Verify journey.


Completed: owner-requested landing design and readability update — Kairo visual study, editorial hero, persistent process controls, bounded wheel momentum and an original Ari horizon footer.

Owner correction: restore the original landing hero, scroll-driven story animations and original wheel easing; remove the reading-distance cap and manual controls. Keep the new Ari-colored footer. Branch `fix/adam/restore-landing`; validation in PR.

Footer correction: use a conventional aligned footer with Ari branding/tagline on the left, two navigation columns on the right, and a separated copyright/back-to-top row. Stack branding above the link columns on mobile. Preserve Ari colors and restored hero/scroll animations. Validation recorded in PR.

Refine the landing headline with tighter two-line rhythm, a stronger cream first line and a lighter warm-ivory second line. Preserve wording, centered layout, pointer spotlight and scroll animations. Branch `fix/adam/hero-headline`; validation in PR.

Add staggered proof-card/footer entrances and subtle button, workflow-chip, process-evidence and footer-link motion. Reduce hero ants from 10–34 to 6–16. Honor reduced motion; preserve existing scroll traversal. Branch `feat/adam/landing-motion`; validation in PR.

Simplify project navigation to Code review and 7 agents. Move settings, scopes, approvals and other records into More; lead with run/replay and starting a check; disclose findings, repositories and progress on demand. Keep all routes and approval requirements. Branch `feat/adam/project-simplify`; validation in PR.

Keep organization/repository/commit navigation scoped to the selected repository and SHA. Real commit runs stay inline in a two-tab reviewer/seven-agent workspace with demo-style agent rail and recorded replay; no redirect to shared project history. Resolve the repository’s actual project, search older run pages, reject mismatched results and retain scoped remediation approvals. Optional narrated quick reads are explicitly requested and separate from executed records. Branch `fix/adam/commit-workspace`; validation in PR.


## Automatic commit assessments — 2026-10-21

IMPLEMENTED in [PR #377](https://github.com/adamissac/ari-ai/pull/377), pending merge/deployment verification: signed pushes fan out into durable per-commit jobs; GitHub API author allowlist, exact SHA, duplicate protection, no docs-only skip/coalescing loss, scope-approval resume. Railway defaults to `adamissac`; configurable for other accounts. Full runs use the normal project assessment budget (operator-capped), not the deliberately cheaper legacy monitoring budget. Shared contracts unchanged. Full-chain fixture tests use scripted model responses, not live provider evidence. Validation: 181 local backend/monitoring/security tests passed (7 optional/dependency skips); 12 final focused scheduling tests passed. Full-chain fixture covers reviewer and all seven roles with required repair approvals. All GitHub checks passed on cbc0782; checks rerun after integrating newer main documentation/RL changes. Production readiness is reachable; authenticated production worker/run verification remains outstanding.
### RL-REGISTRY-001 — v8 promotion review follow-up (Alan, 2026-10-20)

Merged in PR #375 on `feat/alan/rl-v8-continuation`. Bind reports to the current incumbent,
pin report bytes, reject missing/failed checks, add registry-backed experiment baseline,
and resolve reference-name ambiguity from PR #370. Historical v8 evidence is preserved.
Authenticated approvals and signed/schema-complete reports remain open in issue #317;
next training experiment needs preregistration and a fresh holdout.

RL-REGISTRY-001 validation: full RL suite 228 passed; Ruff lint/format and diff checks pass.

### RL-V9-001 — Quiet-validation five-seed lab experiment

Merged in PR #376 on `feat/alan/live-retrain-v9` (Alan).
Preregister val_v9/fresh holdout_v9; train seeds0–4; use actual incumbent v6; preserve
all trajectories and seed-level uncertainty. Completed all five seeds and 16,500 held-out
episodes. Hypothesis unsupported; all seeds reject, v6 unchanged. Evidence/figure in
`rl-defense/results/live-retrain-v9/`; no automatic promotion.

- [x] UI-POLISH: coherent Kairo-inspired visual system across ARI workspace and landing chapters, with responsive navigation coverage (user-authorized Adam frontend work; `feat/adam/ui-polish`).

### RL-V10-001 — Demonstration action balance (Alan, owner authorized)

MERGED in PR #378 (`fdc8e45`) on `feat/alan/v10-demo-balance`. Saved-data failure analysis, opt-in
balanced demo replay, regression tests and fresh two-arm preregistration implemented.
Five seeds per arm; no v10 training/evaluation results yet. V6 unchanged.

RL-V10-001 validation: all CI green,282 RL tests plus20k-step checkpoint smoke;
64 local focused tests;78 saved v9 artifacts verified. Full v10 execution remains
a future experiment (~6h CPU); no model promotion.
