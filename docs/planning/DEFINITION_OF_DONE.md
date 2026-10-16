# Definition of Done

A task is `DONE` only when **all** apply. "It compiles" is not done.

## Every task
- [ ] Acceptance criteria in [HACKATL_TASKS](HACKATL_TASKS.md) met, with evidence
      (commands run + results) in the PR.
- [ ] Merged to `main` via reviewed PR (1 approval; 2 for `shared/`,
      authorization, sandboxing, agent tool permissions).
- [ ] Tests added/updated and passing in CI (or locally if CI not yet configured,
      stated explicitly).
- [ ] No secrets, customer code, or third-party exploit details.
- [ ] Docs: subsystem README "What exists" updated; specs updated or ADR added for
      divergence; CHANGELOG `Unreleased` for user-visible changes.
- [ ] Task status updated; [SESSION_HANDOFF](SESSION_HANDOFF.md) entry appended.
- [ ] Commits follow Conventional Commits with no attribution trailers.

## Additional, by type
| Type | Also required |
|---|---|
| Contract change | `contract-change` label; generated types regenerated; consumers updated or migration noted |
| Safety-critical | Security-owner review; SB suite extended/green; branch coverage target met |
| LLM-dependent | Schema validation tests; recorded-response tests; prompt version bumped |
| UI | Loading/empty/error/stale states; status badges; no fabricated data |
| RL result | Produced by protocol [17](../17_RL_EVALUATION_PROTOCOL.md) scripts; summary file referenced |
| Integration | Contract tests on both sides; checkpoint test added to CI |
