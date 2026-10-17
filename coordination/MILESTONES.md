# Integration milestones and evidence requirements

- [ ] **M0** shared schemas, importable packages, reproducible local run commands, PR/branch conventions agreed. Gate: 6 owners acknowledge types; CI contract tests pass.
- [x] **M1** intelligence indexes the owned Python example by SHA, structured graphs, expectations and citeable context packs. Gate: tests and provenance inspection.
- [ ] **M2** reviewer with real Claude agent loop can interpret commit intention, call retrieval/tests, generate candidate in safe worktree, inspect results. Gate: live optional smoke and deterministic fixture tests; functional defect reproduced.
- [ ] **M3** 7 *different* agent runners with actual bounded tool-use and distinct permissions and typed handoffs. Gate: observed real model/tool trace per required role (opt-in), fake-provider integration tests; separated Verify actual tests.
- [ ] **M4** FastAPI, DB migrations, durable queue, signed idempotent GitHub webhook, scope/approval, persisted audit and SSE. Gate: signed event -> durable queued analysis -> event stream in test.
- [ ] **M5** Double DQN trains from scratch; replay, target/online networks, masks, held-out evaluation and baselines run. Gate: checked env, deterministic seed, checkpoint reload, nonzero learning updates, honest metrics.
- [ ] **M6** frontend displays real backend assessments, actual finding provenance, agent steps, approval controls, RL evaluation and monitoring. Gate: browser e2e on live local service; mocks are test-only.
- [ ] **M7** unified owned-sandbox demonstration from commit -> index -> review -> seven security agents -> candidate patch -> independent security + functional verify -> regressions -> monitoring event -> dashboard, with errors handled honestly. Gate: automated e2e plus human-inspectable traces.
- [ ] **M8** deployment and continuous live event operations after human approval, safe scope and uptime validation. Gate: independently verified URL, webhook delivery and persistence; no blanket production claims.

For each gate, record exact command, git SHA, environment, pass/fail counts, artifact/PR, and unresolved limitations. Do not mark complete on the basis of screenshots alone.


### M1 producer evidence — Sarosh

PR #6 merged at `bcc2e23`; final head `d608af5` passed both CI test jobs, links and
secret scanning. Focused producer/PostgreSQL/webhook: 24 passed, 1 opt-in skip; broader
suite: 115 passed, 4 skips. Actual target/index evidence and canonical ContextPack fixture
are in code-intelligence/evidence/ and code-intelligence/fixtures/. Index version 0.2.0
includes route-attached ownership intent and two-commit convention invalidation proof.
No full reviewer/seven-agent runtime or live-provider claim is made by this M1 check.
