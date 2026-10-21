# Alan → all: authorized RL continuation complete

### 2026-10-21 — Authorized RL continuation complete

Merged #375 (`64c38b7`), #376 (`ce723f8`) and #378 (`fdc8e45`) after their required
checks passed. #378's final RL suite:282 passed in829.86s plus successful20k-step
training/checkpoint-reload smoke; backend, RL integration, frontend unit/browser,
links and secret scanning all passed. Local focused follow-up64 passed;78 stored
v9 artifacts and all five compressed indices verify. All reviewed findings, including
the four late #376 findings corrected in #378, are addressed and resolved.

Implemented saved-v9 failure analysis, opt-in balanced demonstration action sampling
with default/agent replay unchanged, regression tests and fresh controlled v10
preregistration/runner. V10 full study has NOT launched; its effectiveness remains an
untested hypothesis. Original v9 reports, checkpoints and numeric results are preserved.
The actual v6 registry remains unchanged (digest
`c345593354856c50559ba16611853a0e4936a7efc11fa5704c224d3189271408`).

Next technical action is the preregistered v10 uniform-versus-balanced comparison:
five fixed seeds/arm, about6h CPU with five workers and33,000 held-out episodes.
Use committed/pushed clean source and the real existing v6 registry with
`results/live-retrain-v10/run_study.py --registry PATH --workers 5` from `rl-defense`
and its documented workspace PYTHONPATH. Source-byte/reference/registry guards,
complete primary/secondary reporting and failure evidence are implemented; no
automatic model choice, approval or promotion. This requested task ends at preparation.
