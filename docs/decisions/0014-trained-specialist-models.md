# ADR-0014: One trained specialist model per runtime agent, advisory and evidence-gated

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-10-18 |
| Deciders | Adam (product owner request recorded in session); team ratification pending |
| Related | `specialists/`, `security-agents/security_agents/specialist_bridge.py`, docs/07, docs/08, docs/15 |

## Context
The seven runtime agents were Claude prompts with tools. The product owner asked for genuinely
trained ML components per agent, with Claude kept for higher-level reasoning, without weakening
budgets, permissions, approval gates or evidence requirements, and without claiming improvements
that are not measured.

## Decision
1. A new workspace package, `specialists/`, holds one small model per agent: dataset builder,
   NumPy training, held-out evaluation against deterministic baselines, and a versioned checkpoint
   (`manifest.json` + `weights.bin`, SHA-256 verified on load). Inference is pure Python, so the
   control-plane image gains no ML dependency.
2. Training data is synthetic (seeded generator) or pinned public MITRE catalogs. No customer code
   is ever used for training.
3. A model is used only when the paired-bootstrap 95% interval of its gain over the strongest
   baseline excludes zero on the held-out split. Otherwise the agent gets that baseline's answer,
   recorded in the manifest and labelled in the audit event.
4. Specialist output is advisory data in prompts (`provenance='trained_model'`), a bounded re-rank
   of Scout hypotheses, and a review note from Verify's evidence model. It has no authority:
   it cannot approve, verify, widen scope, change a severity, an executed outcome or a verdict.
   Every call is a `specialist.inference` audit event.
5. A missing or tampered checkpoint is a fallback, never a failure: the agent runs as before.

## Consequences
- Each agent has an identifiable, versioned trained component; three (Scout, Probe, Verify) beat
  their baselines with statistical support, four answer from their baseline.
- Results on synthetic data do not establish performance on real repositories, and nothing is
  compared against Claude-only behaviour yet (needs live provider runs).
- Retraining changes checkpoints; dataset hashes and published results are asserted by tests.
