# Alan → all: diagnosis merged; no v11 experiment justified yet

### 2026-10-21 — RL-DIAG-001 complete; pause further training

Merged PR #383 at `79a21e8` (final source `d9ad43b`). Diagnosed exposed v10 data
without policy replay: all ten selected models already miss validation availability;
principal-wide long controls impose documented own/delegated-traffic costs during
rotation. Added opt-in validation screening, candidate/source/config provenance, empty
output preflight and atomic verified/restorable rejection export. All three automated
review findings are fixed and resolved. Existing trainer defaults, serving and v10
evidence are preserved.

Final CI: **310 RL tests passed in 389.33s**, plus successful 20k-step gradient/reload
smoke, full backend suite, backend-to-RL integration, frontend unit/build and browser
checks, link checks and secret scan. Local focused verification: **28 passed in 22.73s**.
No full research training, fresh/exposed holdout replay, registration or promotion.
Registry SHA-256 remains `c345593354856c50559ba16611853a0e4936a7efc11fa5704c224d3189271408`;
v6 remains deployed. The earlier v10 study monitor remains paused.

Owner requested at most one justified follow-up experiment. **No v11 launched**: the
process guard is proven, but no learned-policy improvement is established. Next research
requires a specific objective/control or validation-selection intervention with
train/validation proof, then at most one preregistered fresh-holdout experiment. If it
fails, reconsider the approach before spending more CPU. Diagnosis and preserved paired
traces: `rl-defense/results/v10-followup-diagnosis/README.md` and `diagnostics.json`.
