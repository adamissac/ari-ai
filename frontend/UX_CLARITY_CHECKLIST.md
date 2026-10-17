# UX clarity — acceptance checklist (frontend working draft)

**Status of this file:** `docs/27_UX_CLARITY_AND_VISUALIZATION.md` was referenced by the
product owner but is not on any branch yet. Until it lands, this checklist is the
frontend's *assumed* reading of its five priorities, written from the owner's brief.
When docs/27 is published, reconcile this file against it and delete what disagrees.

Audience: someone who has never studied programming, security or reinforcement learning.
Every item must hold **without fabricating results**: numbers and statuses come only from
persisted backend records or the committed, schema-validated RL bundle; explanations that
are not results are visibly marked as explanations.

## 1. A clear overview

- [ ] The project page answers, in one sentence each: what was checked, what was found,
      what was fixed and proven, and what the person should do next.
- [ ] Each of the three pillars has a plain-language question, a status in words, and a
      count taken from records, with a link to the detail.
- [ ] Jargon (finding, hypothesis, scope, sandbox, patch, verification, commit, SHA,
      simulation, policy) has an inline, keyboard-accessible definition.
- [ ] Empty, loading, failed and "not live" states remain explicit and distinct.

## 2. The eight AI agents, understandable at a glance

- [ ] A single relay view shows all eight agents in run order, grouped by team
      (check the change → attack safely → fix → prove → prevent), with the human
      approval gate drawn where the orchestrator actually pauses.
- [ ] Each agent's tile shows its recorded status in words and icon (not colour alone)
      and what it handed to the next agent, using only recorded runs/findings.
- [ ] An agent that has not run says so; nothing is shown as done ahead of its record.
- [ ] The relay is keyboard-operable and selecting a tile opens that agent's detail.
- [ ] Runs whose model replies were scripted or replayed stay labelled as not live.

## 3. How the three pillars connect

- [ ] One diagram shows the loop: understand the code → review it (pillar 1) → test it
      like an attacker (pillar 2) → fix and prove → monitor for new changes (pillar 3)
      → a new change starts the loop again.
- [ ] Every node carries this project's real count (or an explicit "none yet").
- [ ] The RL Defense Lab is shown as connected research, visibly labelled simulation,
      never as production detection.

## 4. Before-and-after evidence of a fix

- [ ] A finding page shows, side by side, the code before and after the candidate fix,
      from the hash-checked diff artifact.
- [ ] It shows the check result before (Probe confirmed / reviewer reproduced) and after
      (Verify's "original check no longer reproduces" and test-suite checks), each with
      its recorded evidence, and says plainly when either side is missing.
- [ ] A rejected or unverified patch is never presented as a fix; nothing implies the
      change was merged or deployed.

## 5. An intuitive RL Defense Lab

- [ ] The lab opens with what it is in two sentences, and the simulation caveat.
- [ ] Policies have plain names (trained defender, rule-based, random, do nothing) and a
      scoreboard in plain words, still showing the bundle's mean, 95% CI and n.
- [ ] The replay explains each defender action in words and shows, over the episode,
      what the defender did against the attacker's hidden progress (labelled ground
      truth, never observed by the policy).
- [ ] No number appears that is not in the bundle.

## Verification

- [ ] ESLint, strict TypeScript, Vitest and `next build` pass.
- [ ] Real-stack Playwright (`tests/e2e/stack.py`) passes, with new assertions for each
      priority, and screenshots of the executed run are reviewed.
- [ ] Layout works at 375 px width and with keyboard only.
