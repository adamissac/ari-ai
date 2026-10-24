# Isolated integration log

Base: upstream main 35e8b32c (full SHA in evidence/UPSTREAM_MAIN.txt).
Review pins are recorded in evidence/pr-*-metadata.json. No original branch or PR
is modified, merged or closed. Integration merges preserve source ancestry.

A: merged 89a3debab24f27da8672a1f2b22239d916079b04 cleanly.
B: integrated 17c3ded021a48165bbdb03af014fb494133376c7 after A.
Conflicts in CHANGELOG and SESSION_HANDOFF preserve both sides' entries.
Worker conflict resolution preserves A's JobDeferred definition/exception path
and B's JobDeadlineExceeded/EffectNotApplied definitions and completion DB retries.
This is mechanical composition only; defer lifecycle compatibility and provider
external-effect guards still require independent tests and may be defects.

C: e187e9a20f5c9792da8d17371c0ef57c2573609b integrated cleanly after A/B;
only its E2E changes were applied, retaining the newer A security fixes.
D: b44b28aad69fb7775b6e9e0c5225b899a7446af1 conflicts resolved by retaining
both execution and investigation API routers, both changelog entries, 0.22 history
and final additive schema 0.23.0. Generated aggregate JSON/TS was regenerated from
combined canonical models; no original PR is rewritten. Shared examples check passed.

First combined run: 88 passed, 2 failed, 1 skipped (live provider disabled).
Failures: A asserts exactly schema 0.22 while combined canonical schema is 0.23;
C deadline compatibility test writes Python utcnow() inside a transaction whose
PostgreSQL now() is earlier. A separate DB-clock regression passes.
Independent regressions: 7 failing assertions, 1 passing clock control. These
remain deliberately failing evidence, not hidden behind xfail. See raw logs/XML.
