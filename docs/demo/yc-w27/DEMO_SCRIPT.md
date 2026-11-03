# YC demo script (≈105 s spoken)

Pair with the click path in [DEMO_RUNBOOK.md](DEMO_RUNBOOK.md). Only say what is on screen.

**0:00 — Problem (landing page)**
"Teams ship code faster than anyone can security-review it. Scanners flag hundreds of
maybes, and nobody proves whether a fix actually closes the hole. Ari is a team of AI
agents that finds a real vulnerability, proves it with an executed test, and proves the fix."

**0:12 — Connect (Organizations)**
"You install our GitHub App and pick a repository. Ari tells you exactly what it can read
and write, and connecting doesn't run anything. Nothing is tested until you approve a
30-day sandbox scope."

**0:25 — The repository (Commits)**
"This is our own staging repository, a small payments API we seeded with a real
access-control bug. Ari assessed this commit."

**0:35 — The result (assessment)**
"Here's what the run did, in plain terms: what it found, which fixes a person approved,
what it wrote, and what an independent re-test accepted. It never merges or deploys."
*(If the banner says "Not a live-provider run": "For this recording the model replies are
scripted; the tests, sandbox and verification are real.")*

**0:50 — The agents (relay)**
"One reviewer and seven security agents, each with one job. Scout suspects, Probe proves it
in a sealed-off copy, Diagnose plans the fix, and nothing gets built until a human approves."

**1:00 — The finding (finding page)**
"Any logged-in customer could read someone else's payment. Probe reproduced it with a real
request. Patch wrote a fix and a regression test, and Verify re-ran the attack and
the existing tests. Red before, green after, all in an isolated copy."

**1:25 — Evidence chain**
"Every claim links to its evidence: the expectation, the test that proved it, the diff,
and the verdict."

**1:35 — Ongoing workflow (Settings)**
"Automatic reviews are off until you turn them on per repository; then Ari re-checks eligible pushes, rate-limited. Verified fixes arrive the way
you choose: you approve each one, or a pull request your team merges."

**1:50 — Close**
"Find the flaw, prove the fix. That's Ari."

## Words to avoid

- "customers", "in production at…", or any count of scans or users
- "secure", "clean" or "no vulnerabilities" as a verdict on the whole application
- "autonomously merges" or "deploys" (it does neither)
- "live" for any run whose page says **Not a live-provider run**

## If asked (answers must stay inside what ships)

| Question | Answer |
|---|---|
| Who buys it? | The engineering lead or CTO of a 2–30-developer startup with no dedicated security engineer. |
| Who uses it? | The developer who owns the service: connects the repo, approves the sandbox and the fix, merges the PR. |
| First useful outcome? | One confirmed vulnerability with an executed reproduction, and a fix the independent re-test accepted, delivered as a PR the team merges. |
| Finding vs verified finding? | A finding starts as a hypothesis. It is **confirmed** only when an approved test reproduced it in the sandbox; otherwise it is shown as ruled out or unconfirmed. |
| Proposed patch vs verified repair? | Patch writes a proposed fix after a human approves. It is a **verified repair** only when Verify, a separate agent, re-ran the attack and the existing tests on a fresh copy and both passed. Ari never merges or deploys. |
| What doesn't it do yet? | Validated security findings for Python HTTP services only (JS/TS get a functional review); one person per organization (no invites yet); no billing; no hosted live run recorded yet. |
| What's next? | One live hosted assessment on our staging repo, then 3–5 paid design partners on Python services, team invites, then JS/TS validation. |
| Is this live? | Say exactly what the assessment page says: **Live provider run** or **Not a live-provider run**. |
