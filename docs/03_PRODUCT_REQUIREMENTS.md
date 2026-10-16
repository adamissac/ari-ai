# 03 — Product requirements

Status: **specified**. Requirement IDs are stable; reference them from tasks and
tests. Priority: **M** = MVP (HackATL), **S** = should for MVP if time permits,
**L** = later.

## Functional requirements

### Platform (FR-P)
| ID | Requirement | Pri |
|---|---|---|
| FR-P-01 | Users authenticate with GitHub OAuth. | M |
| FR-P-02 | A user can create a Project and connect one or more Repositories. | M |
| FR-P-03 | A user can register an AuthorizedScope that names sandbox targets; it is inactive until a human approver approves it. | M |
| FR-P-04 | All consequential actions are recorded in an append-only audit log. | M |
| FR-P-05 | Every assessment has a token and USD budget; exceeding it stops the run cleanly. | M |
| FR-P-06 | Organizations with role-based access (owner, member, viewer). | L |

### Pillar 1 — intelligence, review, repair (FR-1)
| ID | Requirement | Pri |
|---|---|---|
| FR-1-01 | Index a repository at a given commit SHA (Python). | M |
| FR-1-02 | Extract symbols, imports, call edges and HTTP entry points. | M |
| FR-1-03 | Extract BehavioralExpectations with provenance and confidence. | M |
| FR-1-04 | Users can confirm, edit, or reject expectations. | S |
| FR-1-05 | Review changed or selected code against expectations and report functional findings with evidence. | M |
| FR-1-06 | Generate behavioral tests that encode an expectation and run them in a sandbox. | M |
| FR-1-07 | Produce candidate repairs in an isolated worktree with test evidence. | M |
| FR-1-08 | JavaScript/TypeScript indexing. | S |
| FR-1-09 | Incremental re-index on a diff. | S |

### Pillar 2 — security agents (FR-2)
| ID | Requirement | Pri |
|---|---|---|
| FR-2-01 | Scout produces evidence-backed hypotheses from the context pack and static tools. | M |
| FR-2-02 | Probe validates hypotheses with non-destructive checks only inside an approved scope's sandbox. | M |
| FR-2-03 | Trace builds an attack path, labeling unverified steps. | M |
| FR-2-04 | Diagnose produces root cause and remediation plan linked to expectations. | M |
| FR-2-05 | Patch produces a candidate diff in an isolated worktree after human approval. | M |
| FR-2-06 | Verify independently re-runs the validation check and functional tests in a fresh sandbox and accepts or rejects. | M |
| FR-2-07 | Fortify recommends hardening and regression tests. | S |
| FR-2-08 | The user can open a GitHub PR from a verified patch (human action). | S |

### Pillar 3 — monitoring & RL (FR-3)
| ID | Requirement | Pri |
|---|---|---|
| FR-3-01 | Receive GitHub push/PR webhooks, verify signatures, and record events. | M |
| FR-3-02 | Map changed files to affected symbols, expectations and prior findings. | M |
| FR-3-03 | Request a targeted re-assessment when affected items exist (policy-driven). | M |
| FR-3-04 | Ingest runtime logs from the sandboxed demo target and compute simple anomaly signals. | S |
| FR-3-05 | Train and evaluate a Double DQN defense policy in a simulated environment, with baselines. | M |
| FR-3-06 | Show RL recommendations labeled as simulation-derived recommendations. | S |

## Non-functional requirements (NFR)

| ID | Requirement | Target |
|---|---|---|
| NFR-01 | No untrusted code executes outside a sandbox container. | Absolute |
| NFR-02 | Sandboxes default to no network; target-only network requires an approved scope. | Absolute |
| NFR-03 | Every finding/claim shown in UI links to ≥ 1 EvidenceRef. | Absolute |
| NFR-04 | Schema-invalid LLM output is a failed step, never partially used. | Absolute |
| NFR-05 | Full demo-target assessment completes. | < 10 min (MVP target, unmeasured) |
| NFR-06 | Indexing of a 50k-LOC Python repo. | < 2 min (target, unmeasured) |
| NFR-07 | Per-assessment LLM cost cap. | Default USD 10 (`LLM_MAX_USD_PER_ASSESSMENT`) |
| NFR-08 | Secrets never logged; logs redact known secret patterns. | Absolute |
| NFR-09 | Free-tier or local infrastructure only until paid infra is approved. | Absolute |
| NFR-10 | Accessibility: WCAG 2.1 AA for core screens. | S |

## Traceability

Each task in [planning/HACKATL_TASKS](planning/HACKATL_TASKS.md) lists the
requirement IDs it satisfies. Each requirement marked M must be covered by at
least one test listed in [16](16_TESTING_AND_VERIFICATION.md).
