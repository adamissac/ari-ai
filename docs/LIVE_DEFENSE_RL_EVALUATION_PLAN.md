# RL-gated pilot — evaluation plan

Status: **specified**. Thresholds are **unset** pending RL-owner approval.
This document does not authorize training, promotion, serving, or a customer
pilot.

Pass-by-total-reward is forbidden. Open PRs, unit tests, and research docs are
not evaluation evidence.

## 2026-11-14 update: thresholds approved, one run, candidate failed

The RL owner (Alan, with Adam) approved the criteria in `rl-defense/configs/live/promotion.yaml`
plus a 0.85 delegated-access floor, with the tuned rules as the incumbent. Frozen v6 was run
once on four new frozen scenarios and **failed the per-scenario check**
(`rl-defense/results/pilot-gate/REPORT.md`). The gate stays blocked. The tables below are the
plan as originally specified; the shared contract still carries `threshold: null` because
changing it is a contract change that was not made.

## Required dimensions

| Dimension | Required | Threshold |
|---|---|---|
| Frozen evaluation scenarios | yes | unset |
| Holdout unused in training | yes | unset |
| Independent seeds | yes | unset |
| Baselines: rules, fixed-block, frozen v6 | yes | unset |
| Per-scenario reporting | yes | n/a (total reward is not a pass rule) |
| Abstention | yes | unset |
| Uncertainty (Q is not probability) | yes | unset |
| Provenance (hash-pinned checkpoint + lineage) | yes | unset |

## Required metrics (thresholds unset)

| Metric | Meaning | Threshold |
|---|---|---|
| compromise | Unauthorized access remaining after the candidate acts | pending RL-owner approval |
| availability | Legitimate own-object requests that still succeed | pending RL-owner approval |
| delegated | Explicit valid delegates that still succeed on covered resources | pending RL-owner approval |
| false_disruption | Legitimate traffic disrupted by the candidate | pending RL-owner approval |
| cost | Measured intervention / collateral cost | pending RL-owner approval |

Do **not** invent numeric limits from Phase 1 research, v6–v10 historical
evals, or fixture audits. Formerly exposed holdout cannot be relabeled as
fresh.

## What this plan is not

- Not a claim that frozen v6 passed these criteria.
- Not a Codex research change. Do not edit datasets, holdout, v6 weights, or
  historical evals to “fill in” this table.
- Not authorization to start Phase 7.

Machine-readable copy: `RlEvaluationPlan` in `shared/shared/live_defense.py`,
served at `GET /api/v1/projects/{id}/rl-readiness`.
