# Functional reviewer: live ground-truth evaluation, 2026-11-03

This evaluation pushed planted functional bugs and clean commits to the connected repositories. The production pipeline (Railway, `provider_mode=live`) reviewed every push, and the outcomes were read back through the production API. Every number below comes from an executed run. The production model is `claude-haiku-5-5`, which `Settings.model_for` forces in production.

## Ground truth

There are 13 commits per round. Each commit sits on its own `ari-demo/<round>/<case>` branch, cut from the repository's `main`. Every label was proven before the push by an evaluator-only oracle that was never pushed. Each oracle passes on `main` and on the clean commits, and fails on the planted commit. Exception: the `js-async` label is a static check, because there is no Firestore stub.

| Case | Repo | Planted change (commit message the reviewer saw) | Class | Existing suite catches it? |
|---|---|---|---|---|
| py-boundary | pilot-rehearsal-target | `amount > balance` → `>=` ("fix: tighten insufficient-funds check") | off-by-one / boundary | no |
| py-null-dest | pilot-rehearsal-target | removed `if dest is not None` guard ("refactor: simplify make_transfer bookkeeping") | null handling | no |
| py-contract | pilot-rehearsal-target | `make_transfer(amount, from, to)`; caller in `app.py` not updated ("refactor(store): amount-first signature") | cross-file contract | yes (1 test) |
| py-intent | pilot-rehearsal-target | `Field(gt=0)` → `ge=0`; README says amounts are positive ("feat: accept zero-amount transfers") | regression of documented intent | no |
| py-clean-helper | pilot-rehearsal-target | extract `_bearer_token` helper, same behavior | clean | — |
| py-clean-sorted | pilot-rehearsal-target | list accounts in id order | clean | — |
| js-offbyone | mypypath | `n > TOTAL_UNITS` → `>=` (unit 10 dropped) | off-by-one | n/a |
| js-wrong-cond | mypypath | `if (!ON \|\| fromCache)` → `!fromCache` in `read-counter.js` | inverted condition | n/a |
| js-null | mypypath | removed `isPlainObject(entry)` guard in `summarizeUnitTests` | null/undefined | n/a |
| js-async | mypypath | dropped `await` on the roster transaction in `joinClass` | broken async/await | n/a |
| js-contract | mypypath | return key `testsPassed` → `passedUnits`; `sync.js` still reads `testsPassed` | cross-file contract | n/a |
| js-clean-rows | mypypath | name a local in `scoreRows` | clean | — |
| js-clean-report | mypypath | named sort comparator | clean | — |

The reviewer cannot execute JavaScript, because the production sandbox has no Node runtime. So for JS, "flagged" (a hypothesis on the right file) is the best result available.

## Rounds

| Round | Deployed main | Reviewer | What changed before this round |
|---|---|---|---|
| gt1 (baseline) | `079f7777` | `reviewer@1` | — |
| gt2 | `b0be0bc4` (#781) | `reviewer@2` | handoff race fix; change context; commit messages; JS comment docstrings; prompt checklist |
| gt3 | `353730af` (#785) | `reviewer@3` | keep findings that cite removed lines; commit messages are quotable |
| gt4 | `e64f1817` (#788) | `reviewer@3` | a test cited by name resolves to its `def` |
| gt5 | `ebb9c6fb` (#789) | `reviewer@4` | refuse "tests" that read JS source as text |

In gt1, `py-boundary` failed on infrastructure (`SNAPSHOT_NOT_READY`, a transient "Repository not found" from git). Its identical re-push `d624b6e8` ran on gt1 code and is counted in gt1.

## Results per case (reviewer's own findings only)

The `security` findings that Scout raised on the same runs are excluded. They carry no reviewer run id.

Legend: **fixed** means the finding was validated, then Ari's repair passed independent Verify. **validated** means a test failed reproducibly on head against a confirmed rule. **hyp** means the bug was flagged correctly but not proven. **miss** means no reviewer finding on the defect.

| Case | gt1 | gt2 | gt3 | gt4 | gt5 |
|---|---|---|---|---|---|
| py-boundary | fixed | fixed | fixed | fixed | fixed |
| py-null-dest | miss (Scout only) | miss (finding dropped: cited the removed guard) | hyp | hyp | hyp (+ same-root security hand-off) |
| py-contract | inconclusive (crash read as harness error) | hyp | hyp | **fixed** | **fixed** |
| py-intent | validated, **never repaired** (race) | fixed | fixed | fixed | fixed |
| js-offbyone | hyp | hyp | hyp | hyp | hyp |
| js-wrong-cond | hyp | hyp | hyp | "fixed" on non-behavioral evidence (see below) | hyp (honest) |
| js-null | hyp | hyp | hyp | hyp | hyp |
| js-async | **miss** | hyp | hyp (filed as security hand-off) | hyp | hyp |
| js-contract | hyp | hyp (+1 duplicate) | hyp | hyp (+1 duplicate) | hyp (+1 duplicate) |
| 4 clean commits | 0 findings | 0 | 0 | 0 | 0 |

## Summary metrics

The first column is gt1. The second is gt5, the final deployed state.

| Metric | Before (gt1) | After (gt5) |
|---|---|---|
| Recall: planted bugs flagged on the right file (9) | 7/9 (78%) | **9/9 (100%)** |
| Python bugs proven by an executed test (4) | 2/4 | **3/4** |
| Python bugs fixed and Verify-accepted (4) | 1/4 | **3/4** |
| False positives on clean commits (4 commits) | 0 | 0 |
| Precision of reviewer findings (excluding duplicates of a true positive) | 7/7 | 9/9 (2 extra findings were duplicates of a true positive) |
| Reviewer run, median / max | 23.4 s / 29.1 s | 21.0 s / 34.2 s |
| Reviewer cost per review, mean (Haiku) | $0.0054 | $0.0055 |
| Whole assessment cost per commit, mean (reviewer + 7 agents) | $0.0083 | $0.0082 |

The repair agent cost $0.0012–0.0017 per fix. Push-to-completed wall time was 30–200 s when the queue was free. In gt1 the queue was behind another session's 50+ `ari-ai` assessments, so wall time was not comparable.

Offline checks:
- `uv run python -m code_review.eval_corpus`: 10/10 labels proven, before and after.
- `uv run pytest -q code-review/tests`: 90 passed, 4 skipped before; 98 passed, 4 skipped after (the 4 skips are live/docker opt-ins).

## What was wrong, and what changed (PRs)

1. **A validated bug was never repaired (#781): a race in the reviewer → agents handoff.**
   - The reviewer runs beside Scout and Probe.
   - `_report_or_wait` asked `external_pending()` before the transition that joins the reviewer thread.
   - A reviewer that was still running filed its remediation approval after the run had already decided to complete, so the run ended COMPLETED with a pending approval. This happened in gt1 `py-intent`, even with `delivery_mode=auto`.
   - Fix: join the reviewer first. This is the only change in `security-agents/`.
2. **The reviewer saw only the diff (#781).**
   - The first turn now carries a deterministic `<change_context>` (`code_review/context.py`). It lists:
     - references to the changed symbols across the pinned head, including callers in files the diff never touched;
     - identifiers the change removed that other code still uses;
     - the tests and docs that mention the changed code.
   - The commit messages of `base..head` are passed as untrusted intent. Push events previously had an empty body.
   - In JS/TS, a citation wholly inside a comment block counts as a docstring.
   - The prompt gained a bug-class checklist: boundaries, inverted conditions, removed guards, a missing `await`, caller/callee contracts and documented intent. It also says a refactor must not change behavior, and that a crash must be asserted as a test failure, not left as a harness error.
   - Effect: the gt1 `js-async` miss is now caught, and `py-contract` moved from `inconclusive` to proven.
3. **Proven findings were thrown away (#785, #788).**
   - A finding whose spans quoted the guard the change removed had no span that verified at head, so it was dropped despite a failing test. It is now anchored to its changed hunk at head.
   - A claim that quoted the commit message was rejected, because the citation checker did not know commit messages. They are now quotable, and still only `inferred`.
   - A citation of the failing existing test by name with no line was rejected. It now resolves to the test's `def` line, so the rule is `confirmed` and the fix runs. Effect: `py-contract` was **fixed** in gt4.
4. **Unsound evidence closed (#789).**
   - Once JS comments could confirm a rule, the model "tested" `js-wrong-cond` (gt4) with a pytest module that regex-matched `read-counter.js`.
   - It failed on head, so the finding validated and was repaired, and Verify accepted it. The patch was the exact revert, but nothing behavioral had run.
   - `write_test` now refuses any generated test that names a JS/TS/HTML source file. JS findings stay hypotheses until a JS runner exists.

## Fixes Ari produced (all accepted by independent Verify: diff scope, no test tampering, original failure no longer reproduces, suite passes, generated tests pass)

- `py-boundary`: `- if body.amount >= source.balance:` → `+ if body.amount > source.balance:`. One line in `ledgerlite/app.py`.
- `py-intent`: `Field(ge=0, …)` → `Field(gt=0, …)`. One line.
- `py-contract` (gt4): the caller was changed to keyword arguments, `store.make_transfer(amount=…, from_account=…, to_account=…)`. This keeps the author's new signature instead of reverting it.

Delivery behaved correctly for the branch-only bugs: "main already contains this fix". The exception was `py-contract`. Its fix depends on the branch's own change, so delivery opened `pilot-rehearsal-target#9` against `main`, carrying the demo commit. That PR was closed in cleanup. See the shortfalls below.

## What still falls short

- **No JavaScript execution.** All five JS bugs are flagged with precise explanations, but none can be proven or fixed. The production sandbox has no Node runtime; that work is the security-agents JS stack (#762–#764). This is the largest remaining gap for `mypypath`.
- **"Refactor must not change behavior" never confirms on its own.** For `py-null-dest`, the test fails on head and passes on base, but the only rule is the commit message, so the finding stays a hypothesis with `needs_clarification`. This is deliberate: auto-repairing on an untrusted message could revert intended behavior.
- **Haiku only.** Production forces `claude-haiku-5-5` for every agent (`Settings.model_for`). Every number here is Haiku's. A stronger reviewer model is an owner cost decision and was not changed.
- **Classification noise.** Keyword rules sometimes file a functional bug as a security hand-off (gt3 `js-async`). Duplicate findings for one root cause appear on JS contract breaks.
- **Delivery target.** A fix for a commit on a feature branch is delivered as a PR against the default branch. It should target the pushed branch (`backend/delivery.py`).
- **Scout false positives.** Scout, not the reviewer, raised `inconclusive` security hypotheses on clean commits (for example 2 on gt1 `py-clean-helper`). These are out of the reviewer's scope.
- **Small set.** 9 bugs and 4 clean commits per round, in 2 repositories. These are point estimates, not intervals.
