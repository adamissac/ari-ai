## Task

Task ID(s): <!-- e.g. INTEL-003 -->
Pillar / subsystem: <!-- P1 intel | P1 review | P2 sec | P3 mon | P3 rl | ui | api | shared | infra | docs -->

## What changed and why

<!-- What does this PR do? Link the spec section it implements. -->

## Evidence it works

<!-- Commands you ran and their actual results. Do not claim tests you did not run. -->

```
$ <command>
<output summary>
```

## Checklist

- [ ] Scope matches the task; no unrelated changes
- [ ] Tests added/updated and passing locally (list above)
- [ ] Uses `shared/` contracts; no locally redefined shared models
- [ ] Contract change? → labelled `contract-change`, generated types regenerated, migration noted
- [ ] Executes code / sends network traffic / changes state? → goes through authorization + sandbox layers ([15](../docs/15_SECURITY_BOUNDARIES.md))
- [ ] No secrets, customer code, or third-party exploit details
- [ ] Docs updated: subsystem README "What exists", specs if diverged, task status, `SESSION_HANDOFF.md`, `CHANGELOG.md`
- [ ] UI/docs claims do not exceed what the code actually does
- [ ] No attribution trailers in commits

## Risks / follow-ups

<!-- Known limitations, regression risks, follow-up task IDs. -->
