# Executed Phase 1 verification

Working checkout `/private/tmp/rl-cmdp-phase1`; Python3.12.14 from the existing RL
runtime. Run commands from repository root with:

```sh
RL_PY=/Users/alanmozhoor/Documents/hackatl-agentic-security/.claude/worktrees/live-retrain-v8-4c5c2e/rl-defense/.venv/bin/python
RL_RUFF=/Users/alanmozhoor/Documents/hackatl-agentic-security/.claude/worktrees/live-retrain-v8-4c5c2e/rl-defense/.venv/bin/ruff
export PYTHONPATH="$PWD/rl-defense:$PWD/shared:$PWD/standards:$PWD/examples/payments-lite/target"
export RUN_LIVE_LLM_EVAL=0
```

Executed results, in order of scope:

- `"$RL_PY" -m pytest -q rl-defense/tests/test_constrained_research.py`:
  original20passed in9.53s; scanner correction21passed in9.65s; review fixes
  **26passed in10.31s**, then **27passed in9.91s** with the historical-verifier drift regression. Includes measured cost/grants/collateral damage, unknowns,
  quiet/no-finding behavior, capabilities, provenance/splits/chains, deterministic
  episodes/bootstrap, policy-label checks, commit/tree/schema rejection and registry
  immutability with an always-present controlled fixture on every platform.
- `"$RL_PY" -m pytest -q rl-defense/tests`: **347passed in256.62s** before the seven
  additional scanner/review regressions. An earlier relative-PYTHONPATH run had346passes
  and one subprocess import failure; absolute paths resolve that environment issue.
  No existing test was removed/weakened. Later complete current-head CI is linked in PR.
- `"$RL_PY" -m pytest -q shared/tests`:60passed,1skipped in.39s (tsc unavailable onPATH).
  `TSC=/Users/alanmozhoor/Documents/hackatl-agentic-security/frontend/node_modules/.bin/tsc "$RL_PY" -m pytest -q shared/tests/test_contracts.py::test_generated_typescript_compiles`:
  **1passed in.64s**, resolving that skipped check. Shared schemas/generated files unchanged.
- `"$RL_RUFF" check rl-defense/rl_defense rl-defense/tests` and
  `"$RL_RUFF" format --check rl-defense/rl_defense rl-defense/tests`:pass.
- `python3 scripts/check_links.py`:518Markdown files,0problems before this new receipt;
  rerun at final publication. `git diff --check`:pass.
- `/private/tmp/hackatl-gitleaks-8.30.1/gitleaks git --no-banner --redact --config .gitleaks.toml .`:
  1,466local-history commits scanned, no leaks. CI initially flagged three **actual
  source SHA256s** on api.py paths; exact-path+exact-line+exact-hash AND exception only.
  A temporary Git fixture containing the same manifest passes, while adding a generated
  synthetic credential-shaped `api_key` in that same file fails with exactly one
  generic-api-key finding. Full-file/history scanning remains enabled.
- `"$RL_PY" -m rl_defense.research.evaluate verify --output rl-defense/results/constrained-phase1`:
  **140episodes /4,200transitions verified**, including after all review corrections.
  This is read-only verification and Q-network inference on saved observations, not a new
  HTTP episode, training run or holdout evaluation. Every fixed-policy action reproduces
  with its actual pinned weights/rules/budget and recorded decision mask.
- `"$RL_PY" rl-defense/results/constrained-phase1/read_legacy.py`:
  five historical training sources,280episodes /8,400transitions adapted with verified
  hashes, aggregate costs known,280initial masks and all propensities/delegated costs
  explicitly unknown. No historical artifact changed and no OPE claim made.

## Review corrections and preservation

PR388 automated review raised four P2s, addressed in this branch:

1. Published source declarations must resolve via Git and own the local execution tree,
   before output creation. New bundles preserve the exact Git commit object so its SHA
   and tree relationship can also be verified offline. Historical source9d64604's exact
   raw object was retrieved from GitHub Git-data API, reconstructed byte-for-byte and
   SHA1-verified (tree22c2f7f); it is preserved as `frozen/source.commit.txt`.
2. Registry safety test always snapshots an actual controlled champion fixture and the
   canonical checkout registry (including nonexistence), and rejects Registry.save.
   The external real v6 registry was independently hashed before/after unchanged.
3. Verifier loads the hash-pinned v6 checkpoint/manifest and saved fixed-rule source,
   then replays every named policy's decision on saved observations/current masks,
   resetting the budget per episode. Mislabeled noop-as-v6 data now fails.
4. Unknown index/config schema discriminators fail before semantic loading.

The original execution config, four original artifacts and EVIDENCE.json are preserved
byte-identically. Original evaluator is archived as `frozen/evaluate.py.txt` (SHA256
8c0002a79444f367a3b34967c198d4b3b1a292d5573fc134553168d385452b2e).
Only provenance/verification orchestration changed; its collection and raw-adaptation
function ASTs must match the frozen source, and all original environment, schema,
reward/cost, policy and metric source hashes still must match. Review evidence has its
own index; new verifier code is not falsely attributed to the original run. Future
incompatible product source requires the recorded checkout, not silent reinterpretation.

The original REPORT_EVIDENCE.json also remains unchanged; post-review files are pinned
separately in REVIEW_EVIDENCE.json. No source or measurement was recollected to pass review.
Existing routine regression fixtures/CI gradient smoke are software checks, not a new
research training study or a Phase2 candidate.

## Handoff boundary

PR388 stays on `feat/alan/constrained-rl-phase1`, deliberately unmerged. Root vercel.json
is main-deployment-enabled; the latest owner request forbids production deployment.
Primary dirty UI checkout is untouched. No actual registry write, model promotion,
customer recommendation change, new control/action index, paid provider call or new
research experiment occurred. V6 hash and registry guard are retained with the evidence.
No Phase2 work. See DECISION.md for explicit no-go and conditional future gates.
