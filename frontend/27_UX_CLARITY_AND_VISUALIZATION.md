# UX Clarity, Product Story & Visualization

**Project:** Ari AI — autonomous software engineering and security platform  
**Status:** Product design direction and implementation acceptance criteria  
**Audience:** Frontend developers, product designers, backend/API developers, all coding agents  
**Suggested repository path:** `docs/27_UX_CLARITY_AND_VISUALIZATION.md`  
**Related references:** `docs/14_FRONTEND_UX_DESIGN.md`, `docs/01_MASTER_PRODUCT_SPEC.md`, `docs/08_AGENT_ORCHESTRATION.md`, `docs/09_RL_DEFENSE_SYSTEM.md`, `docs/12_DATA_MODELS_AND_CONTRACTS.md`

## 1. Goal

Ari AI is complex internally, but **the product must feel simple to use**. A person who has never heard of AI agents, penetration testing, Git commits, or reinforcement learning should understand the big picture within seconds. Developers must be able to inspect all the underlying technical evidence without forcing everyone else to confront it first.

The entire experience should communicate one story:

> **We understand your app, check that it works, look for ways it could be exploited, help fix confirmed problems, and keep watching for new risks.**

Do **not** build three unrelated mini-products for code review, the seven-agent security team, and defense. They are three connected stages of one continuous software-assurance loop. The user should see the connection everywhere.

### The five-second test

Every important page must answer, without scrolling or reading jargon:

1. **What's happening?** What system or change is being checked, and is anything running?
2. **Why does it matter?** What does the result mean for the user's app or customers?
3. **What happened or what should I do next?** Was an issue found, fixed, verified, blocked, or left unresolved? What action is available?

**A beautiful technical dashboard that fails this test is not a successful design.**

## 2. Overall design principles

- **Outcome first, internals second.** Lead with understandable outcomes, not run IDs, SHA hashes, token counts, provider labels, or low-level API metadata. Those remain available in expandable technical views.
- **Plain language first.** Say “A user may be able to see another user's payment” before “broken object-level authorization.” Show the precise classification in an advanced details panel.
- **One visible journey.** Connect code understanding, functional review, security assessment, patching, independent verification, and monitoring in a recognizable sequence.
- **Make the invisible visible.** Show where the agents are working, what they know, what evidence they produced, and what changed. Do not imply work occurred when it did not.
- **No fabricated AI activity.** Progress, metrics, findings, agent thought/action summaries, tests, and defense outcomes must come from real persisted backend events or explicitly labeled recorded runs. Never invent success animations or fake logs.
- **Evidence on demand.** Every important claim should open source snippets, tests, diffs, audit records, or an explanation. Keep those out of the default reading path unless essential.
- **Never overstate security.** “This test now passes” is not “your entire app is secure.” Distinguish *suspected*, *confirmed*, *fixed in a candidate patch*, *independently verified*, *awaiting approval*, *inconclusive*, and *deployed*.
- **No dark-pattern approval.** Clear confirmation for consequential actions. Candidate code patches do not silently merge or deploy. Scope limitations and simulation labels cannot be hidden.
- **Preserve brand direction.** Retain the current Ari AI identity and its established red-and-white visual system unless product ownership explicitly changes it. Prioritize information design over cosmetic redesign.

## 3. Priority 1: A project overview anybody can understand

### Current problem to avoid

A homepage that immediately displays tables of assessment IDs, commit SHAs, model costs, hypotheses, repository setup, and approval records tells a developer *what the database contains* but not *what the software did for them*.

### Proposed overview hierarchy

**A. Human-readable summary / hero**

Example copy:

> **Here's what's happening with your app.**  
> We checked your latest change for bugs and security risks. Review the results and decide whether to approve proposed fixes.

This sentence must be derived from the real current state; handle new projects, running assessments, and failures differently. Never display the example as a fabricated claim.

**B. Three connected health summaries**

Present three clear sections/cards with simple explanations and accurate statuses:

1. **Code Health — “Does your app work as intended?”** Functional review status; confirmed issues; proposed changes; verified behavior tests.
2. **Security — “Could someone exploit it?”** Security investigation status; verified vulnerabilities; candidate fixes; independent test outcomes.
3. **Continuous Defense — “What changed or needs attention?”** Monitored repository events, relevant reassessments, and a separate clearly labeled RL simulation entry point.

Do not invent one overall 0–100 “security score” without a valid, documented methodology. Prefer meaningful counts with definitions and links to evidence.

**C. A single connected journey**

Show a compact horizontal or wrapping sequence:

`Understand → Review → Security test → Repair → Verify → Monitor → repeat`

Each stage has one of: `Not started`, `Running`, `Completed`, `Needs attention`, `Blocked`, `Failed`, `Not applicable`. Status comes from the backend, not hardcoded animation. Clicking a stage opens its underlying detail.

**D. “Latest activity” in normal language**

Use event cards such as:

- “New code change detected. Reviewing affected payment functions.”
- “A functional problem was confirmed by a failing test.”
- “A security check found that another user could view private data.”
- “A candidate fix passed the original security test and regression checks.”
- “A proposed patch is waiting for approval.”

These are **copy examples**, not data to ship as a fake activity feed. Render only messages supported by actual events. Each card should link to a project/assessment/finding.

**E. Clear primary action**

For a new project: “Connect a repository.” For a connected repo missing approval: “Approve a safe test environment.” For an idle configured project: “Run a review.” For a completed run: “View results.” For pending fixes: “Review proposed fix.” Never show multiple equally prominent competing primary calls to action.

### Overview acceptance criteria

- A first-time viewer can identify the app/repository, current status, biggest actionable issue, and next action in five seconds.
- No raw SHA, UUID, token budget, or model provider is necessary to understand the main content.
- Every metric and status is backed by a real API response, with accurate empty/loading/error/stale states.
- The screen works when there is no repo, no completed assessment, many findings, or a failed assessment.

## 4. Priority 2: Show the three pillars as *one connected system*

Make the relationship apparent in both project overview and assessment detail.

### Recommended mental model

**First: Understand & Review.** The platform maps the repository, identifies intended behavior from code/tests/docs/user intent, and checks functional correctness.

**Then: Investigate & Secure.** The seven cybersecurity agents use the same codebase understanding to identify and safely validate vulnerabilities, diagnose, patch, and independently verify them.

**Then: Watch & Reassess.** Authorized changes and security signals can lead to new reviews. The RL Defense Lab is a separate simulation demonstrating trained defensive decision-making, not proof of live production defense.

### UX pattern: one assessment storyline

Group technical actions by human-recognizable phases rather than exposing eight equally weighted agent panels before the user understands the workflow:

**Understanding your code** → **Checking intended behavior** → **Testing security** → **Proposing a fix** → **Verifying the result** → **Continuing to monitor**.

A user can expand a phase to reveal specific agents, model interactions, tools, and raw evidence. Use meaningful transitions: a reviewer finding should lead naturally to its related security implications; a verified security patch should link back to the functional expectations/regression tests it preserved.

Use relationships grounded in shared snapshot IDs, findings, evidence references, and backend contracts. Never connect unrelated artifacts solely to create a prettier diagram.

### Acceptance criteria

- A viewer can explain why code understanding matters to cybersecurity testing.
- A viewer can follow one issue from discovery to verification and see how future changes would be reassessed.
- Product capabilities are not confused with current deployment capabilities. No suggestion that simulation-only or planned integrations monitor live customer production.

## 5. Priority 3: Make the code-review agent and seven security agents understandable

There are **eight tool-using runtime AI roles overall**: the functional **Reviewer** plus **seven specialized security agents**. The interface must not reduce them to one generic chatbot pretending to have multiple personalities.

### Clear role descriptions

| Agent | On-screen plain-English description |
|---|---|
| Reviewer (code) | “Checks whether this change does what the developer intended, then tests suggested repairs.” |
| Scout (red) | “Looks for places where the code could be vulnerable.” |
| Probe (red) | “Safely tests suspected weaknesses in an approved sandbox.” |
| Trace (red) | “Maps what could be affected if a weakness were exploited.” |
| Diagnose (blue) | “Works out the root cause and what needs changing.” |
| Patch (blue) | “Creates a candidate fix without changing production.” |
| Fortify (blue) | “Suggests ways to prevent this kind of issue from recurring.” |
| Verify (independent) | “Retests the original problem and normal behavior to check the proposed fix.” |

### Visualization guidance

- Show **one prominent current phase** at a time, with completed phases compressed into a readable progress trail.
- Show an **agent handoff path**: Who investigated? Who tested? Who proposed the fix? Who independently verified it?
- Use small role cards with **role, current action, real execution status, and outcome**. Show what an agent accomplished, not merely that it was “active.”
- Provide a simple switch or expandable section: **Overview** (plain-English results) / **Technical details** (agent runs, tool traces, model version, costs, budgets, exact evidence).
- Distinguish `not invoked`, `queued`, `running`, `succeeded`, `failed`, and `skipped`. A successful agent step does not imply a successful vulnerability fix.
- Make **Verify** visually independent from Patch; users should understand that fixes are independently checked.
- Make real LLM/tool provenance accessible: agent name, model/provider mode (`live`, replay/test, or deterministic), called tool, and trace/evidence link. Do not show raw chain-of-thought; show action summaries and evidence.

### Acceptance criteria

- A nontechnical person can explain what each team contributes without reading developer logs.
- Agent progress corresponds to persisted orchestration events.
- A finding cannot appear “fixed” based only on Patch output; verification must have passed the appropriate executed checks.
- Tests cover phase ordering, agent statuses, skipped roles, failed agents, and verification rejection.

## 6. Priority 4: Every finding should tell a before-and-after story

The default finding detail should be a short narrative, not a wall of CWE numbers, log output, and JSON.

Use this top-to-bottom structure:

1. **The problem:** “A customer might be able to view another customer's payment.”
2. **Why it matters:** “This could expose private financial information.”
3. **How we know:** “An approved test reproduced the issue in the isolated test app.”
4. **What we changed:** “We created a candidate patch to check that the payment belongs to the signed-in user.”
5. **Did it work?** “The unauthorized request now fails; the legitimate request still works; regression tests passed.” Only say this when independent test evidence supports it.
6. **What happens next?** “Review the patch,” “Awaiting approval,” “Open pull request,” “Needs more investigation,” or the real available action.

### Suggested result card

**Issue:** Another user could read a payment  
**Impact:** Possible exposure of private payment details  
**Before:** Approved unauthorized-access test succeeded  
**Proposed fix:** Added the missing ownership check  
**After:** Unauthorized access rejected; owner access preserved  
**Verification:** Independently tested, with linked evidence  
**Next step:** Review candidate patch

This is illustrative wording for a verified lab scenario. Real copy must be derived from its actual finding, test results, patch, and approval state.

### Technical evidence, one click away

Expandable sections for source locations at the exact commit SHA, generated tests, sandbox execution records, vulnerability classification, attack-path assumptions, patch diffs, regression test results, and audit history.

### Acceptance criteria

- The issue can be understood without knowing the meaning of HTTP 200/403/404, CWE, or a Git diff.
- Technical users can access exact evidence without losing the simple explanation.
- Refuted, inconclusive, rejected, unapproved, and stale findings all have honest and visibly different narratives.
- Frontend state labels agree with persisted backend verification records. Fix any status synchronization bugs instead of papering over them in UI logic.

## 7. Priority 5: Explain the RL Defense Lab without requiring RL knowledge

People should first understand **what happened in the simulated network**. They should not have to interpret Double DQN, reward terms, or confidence intervals to understand the demo.

### First view: the incident story

Start with a clearly marked banner: **“Defense Lab — simulated environment. No actions were applied to a real company network.”**

Then display:

- A simple **network map** with service names and a legend explaining signal strength, isolation, and limitations.
- **What the defender noticed:** a human-readable alert summary from the *observations available to the model*, not the hidden attacker ground truth.
- **What the defender chose:** e.g. “Recommend isolating the payments service in this simulation.”
- **Why that action was available / selected:** provide explanatory features only where legitimately produced; do not invent model thought processes.
- **What happened next:** whether the simulated attacker progressed, service availability changed, and whether impact occurred.
- Simple replay controls: **Play / Pause / Step / Restart / Choose scenario**.

### Second view: evaluation and technical details

Expose a separate **“How was the model trained?” / “Model performance”** section for:

- Double DQN explanation in plain language (learns defensive choices through repeated simulated scenarios).
- Baseline comparisons (rule-based, random, no-op).
- Reward breakdown, observation/action spaces, confidence intervals, evaluation size, training seeds, failure cases, and checkpoint provenance.
- Explicit explanation that good simulation results do **not** demonstrate effectiveness on real customer systems.

### Critical separation

**Continuous Monitoring** and **Defense Lab** are related but distinct:

- Monitoring reports **real, authorized repository/webhook events and supported signals**, when those integrations are operational.
- Defense Lab shows **offline trained policies and replayable simulation results**.
- Never render replayed simulated attackers as detected real-life intrusions.
- Never use a “24/7 protecting your company” status unless there is actual deployed telemetry coverage and operational proof.

### Acceptance criteria

- A first-time viewer can narrate one simulated attack and one defender response in everyday language.
- Replay visuals update together and are tied to recorded episode data.
- Model metrics and uncertainty are accessible, but not the first or only way to understand the page.
- Simulation caveats remain visible and understandable in every relevant view.

## 8. Proposed navigation and progressive disclosure

Keep navigation focused on outcomes rather than internal implementation details. Suggested primary information architecture:

- **Overview:** Is my app okay? What happened? What should I do?
- **Code Review:** What functionality was checked? What bugs and fixes were proposed?
- **Security Team:** What weaknesses were investigated? What did seven agents conclude?
- **Monitoring:** What changed since the last check? What is awaiting reassessment?
- **Defense Lab:** How does the RL defender behave in simulation?
- **Activity & Evidence:** Full timeline, findings, tests, diffs, approvals, and audit.

Avoid duplicate navigation paths that lead to materially different versions of the same assessment state. A deep link to a finding should return to the correct project and assessment.

**Layer 1: Simple.** Meaning, outcome, next step.  
**Layer 2: Explain.** Which agent acted, what changed, and high-level proof.  
**Layer 3: Technical.** Precise files, tool calls, hashes, schemas, raw tests, budgets, metrics, incident records.

Don't hide required authorizations or important caveats in an advanced layer.

## 9. Example end-to-end user journey

1. **Connect a repository.** Explain access requested, scope restrictions, and why a safe test environment is needed.
2. **Understand the app.** Summarize discovered architecture and cite the tests/docs used to infer important expectations.
3. **Review a change.** Say what the developer intended and what the reviewer checked. If intent is uncertain, label it uncertain or request input.
4. **Investigate security.** Show Scout → Probe → Trace evidence in a condensed narrative. Explain whether the issue is confirmed, refuted, or inconclusive.
5. **Propose repair.** Show the intended fix in normal language, with a link to the diff.
6. **Verify independently.** Show tests of both original flaw and normal functionality. Report actual failures as failures.
7. **Approve deliberately.** Clearly differentiate candidate patch, verified patch, PR opened, and production deployment.
8. **Continue monitoring.** Show later authorized code events, their impact on previously reviewed code, and what was rechecked.
9. **Explore RL separately.** Show what the simulated defense policy learned through a recorded scenario and where the research currently stops.

## 10. Concrete implementation instructions for the frontend team

1. **Audit the existing Next.js frontend before redesigning.** Reuse actual backend endpoints, transport, generated types, components, and tests. Do not throw away working functionality or silently invent API fields.
2. **Build a single source of UI truth.** Render from typed persisted objects and genuine SSE/polling state. Define mapping between backend run/finding/verification status and user-facing summaries; test that mapping.
3. **Implement the project-overview summary first.** Use real data to determine what is known, unknown, unresolved, and actionable.
4. **Then connect the assessment storyline.** Build a human-readable phase timeline with expandable eight-agent details.
5. **Then improve issue cards.** Add verified before/after narratives based on actual test evidence and patch state.
6. **Then revise monitoring and RL displays.** Distinguish live source events, archived assessments, and simulated evaluation bundles.
7. **Preserve advanced inspection.** No feature regressions to code diffs, provenance, budgets, artifacts, approval gates, audit logs, error messages, or keyboard access.
8. **Coordinate contract changes.** Post interface requests to the Git coordination channel; do not fork backend models locally. Resolve documented finding-status inconsistencies at the source.
9. **Use a real end-to-end scenario.** Test the same issue as it flows through code understanding, review, security validation, patch proposal, independent verification, and later reassessment. Recorded runs must be labeled.
10. **Have a newcomer usability test.** Ask a person unfamiliar with the project to explain (a) what happened, (b) what is at risk, (c) what action is needed, and (d) what the system can actually prove. Iterate if the explanation fails.

## 11. Release acceptance checklist

- [ ] Project overview passes the five-second test for a new project, active run, completed run, and failure.
- [ ] Three pillars appear as one coherent product workflow.
- [ ] Code-review agent plus seven security agents are clearly differentiated and grounded in real execution records.
- [ ] Findings have understandable problem/impact/before/after/verification/next-step sections.
- [ ] “Fixed,” “verified,” and “deployed” are never conflated.
- [ ] Continuous Monitoring cannot be mistaken for the simulated RL Defense Lab.
- [ ] Defense Lab uses real recorded simulation data and a replay a beginner can follow.
- [ ] Technical evidence is accessible within one or two interactions from the summary.
- [ ] Empty, loading, stale, partial, failed, and inconclusive states are explicit.
- [ ] Backend finding-status synchronization bugs are corrected and integration tested.
- [ ] Existing approvals, security controls, source provenance, and audit detail remain available.
- [ ] Responsive layouts, keyboard navigation, accessible labels, and reduced-motion preferences are honored.
- [ ] A real-stack browser journey passes without fabricated results.
- [ ] At least one teammate outside frontend can successfully explain the complete product journey based only on the UI.

## 12. Final guiding instruction for every coding agent

**Do not optimize solely for looking impressive. Optimize for being immediately understandable, technically truthful, and genuinely useful.**

A first-time user should see a clear answer to:

**“What did your AI team discover about my software, what did it actually do, how do we know it worked, and what happens next?”**

If a screen cannot answer that simply, redesign the information hierarchy before adding more charts, badges, agent animations, or raw technical metrics.
