# MSG: Ingestion profile fix merged; remaining owner gates

- From: sarosh
- To: all; consumer heads-up sai, alan, srihith; milestone reconciliation adam
- Timestamp (UTC): 2026-10-17T13:45:00Z
- PR: https://github.com/adamissac/hackatl-agentic-security/pull/150
- Product commit: `5015d67`; tested head: `91cea8c`; merge: `1129434`
- Issue #148: closed

Read recovered handoff #145 and confirmed #39/#38 complete. Reproduced and
fixed the separate same-SHA cache bug: normalized ingestion coverage and limits
now determine immutable profile identity. Historical refs remain readable;
reindex active commits for current refs. Never copy human confirmations across
profiles. No shared DTO change. Sai typography work (#149/#151) was integrated
before the final checks; active Vihaan work was left alone.

All executable PR checks passed on `91cea8c`: backend 417 passed/8 skipped;
intelligence 33 passed/1 skipped; reviewer 60 passed/3 skipped; security 455
passed/18 skipped; Docker security 6 passed and reviewer 2 passed; frontend
Vitest 67 passed and real-stack browser 12 passed. Image/Compose, lint/types,
links and gitleaks passed. CodeRabbit skipped automatic review; it is not a
review sign-off. Model suites use scripted transports; live checks stay opt-in.
Post-merge-local combined checks before pushing: producer/PostgreSQL/QA 10
passed, Markdown links 470 files/0 problems. Full commands are in PR #150.

Remaining owner gates: key holder must execute M3's live seven-role run (#10);
a human security owner must sign off the two Probe templates (SEC-005);
release owners must select an authorized registry and publish immutable sandbox
image digests (INFRA-005); deployment/GitHub account setup and live delivery
validation require the owner (M8). This checkout has no Anthropic environment
key or local .env. No new live-provider or deployment proof is claimed.

Adam: M5 is still unchecked while your status records trained/evaluated artifacts
and passing RL work. Please reconcile the milestone against the exact current
artifact/CI evidence. I have not changed another owner's milestone status.
