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

- **No JavaScript execution.** Fixed since (#830–#832, JavaScript section below). Functional Verify still cannot replay JS tests, so JS fixes are not delivered.
- **"Refactor must not change behavior" never confirms on its own.** For `py-null-dest`, the test fails on head and passes on base, but the only rule is the commit message, so the finding stays a hypothesis with `needs_clarification`. This is deliberate: auto-repairing on an untrusted message could revert intended behavior.
- **Haiku only.** Production forces `claude-haiku-5-5` for every agent (`Settings.model_for`). Every number here is Haiku's. A stronger reviewer model is an owner cost decision and was not changed.
- **Classification noise.** Keyword rules sometimes file a functional bug as a security hand-off (gt3 `js-async`). Duplicate findings for one root cause appear on JS contract breaks.
- **Delivery target.** A fix for a commit on a feature branch is delivered as a PR against the default branch. It should target the pushed branch (`backend/delivery.py`).
- **Scout false positives.** Scout, not the reviewer, raised `inconclusive` security hypotheses on clean commits (for example 2 on gt1 `py-clean-helper`). These are out of the reviewer's scope.
- **Small set.** 9 bugs and 4 clean commits per round, in 2 repositories. These are point estimates, not intervals.

## Second ground-truth set (gtB, gtC), 2026-11-03

The first set reached 9/9, so I built a harder one. Every label was again proven by an evaluator-only oracle before the push. Some JS labels are static source checks, because Firestore is not stubbed.

| Case | Repo | Planted change | Class |
|---|---|---|---|
| py-async-audit | pilot-rehearsal-target | new audit trail; `async def log_transfer` called without `await` (README documents `GET /audit`) | broken async |
| py-paging | pilot-rehearsal-target | new `GET /transfers`; slice `offset:offset+limit+1`, docstring says "at most `limit`" | off-by-one |
| py-rename | pilot-rehearsal-target | `Customer.id` → `customer_id` in `store.py`; `app.py` still reads `customer.id` (every authenticated request returns 500) | cross-file contract |
| py-float | pilot-rehearsal-target | `amount: Decimal` → `float` ("accept plain JSON numbers"); `Decimal -= float` raises | type contract |
| py-clean-getattr | pilot-rehearsal-target | `account is None or account.customer_id != …` → `getattr(account, "customer_id", None) != …` | clean (looks like a removed guard) |
| py-clean-asynchealth | pilot-rehearsal-target | `async def healthz` | clean |
| js-foreach-async | mypypath | `for…of await createAssignment` → `.forEach(async …)`; `rolloverClass` returns before the copies finish | broken async |
| js-purge-order | mypypath | roster row deleted before its records, against "the roster row goes last" | documented intent |
| js-batch-obo | mypypath | `snap.size < 400` → `<= 400` in the purge pager (records left behind) | off-by-one |
| js-arg-swap | mypypath | `noteEvents(classId, uid, …)` → `(uid, classId, …)`; the caller in `event-sink.js` is unchanged (silent) | cross-file contract |
| js-lessonkey | mypypath | swapped `replace` order; `lessonKey` is no longer injective (`a/b` = `a__b`) | documented intent |
| js-clean-forof | mypypath | `forEach` → `for…of` with no `await` | clean |
| js-clean-demorgan | mypypath | `!a \|\| b \|\| c` rewritten positively | clean |
| py-test-weakened (gtC) | pilot-rehearsal-target | `>` → `>=` **and** a new test asserting the full-balance transfer is rejected; README still says "not exceeding" | intent vs. a test changed to match |
| py-clean-docs (gtC) | pilot-rehearsal-target | docstrings on every endpoint | clean |
| js-buried (gtC) | mypypath | 15-site rename `counted` → `countReads`, plus a retention cutoff of `365*24*60*1000` (≈6 days, not 365) in a 9.7k-char diff | needle in a large diff |
| js-clean-rename (gtC) | mypypath | the same rename without the cutoff change | labelled clean; see below |

**Label correction.** `js-clean-rename` is not clean. `tests/read-counter.test.js` counts `counted(` calls in `classroom-store.js`, so the rename breaks an existing test. The reviewer found this and I had not. It is scored as a true positive, and the same breakage counts within js-buried.

### Results (reviewer's own findings)

| Case | gtB1 (`eac412ad`) | gtB2 (+#805) | gtB3 (+#807) | gtB4 (+#809, #810) | gtB5 (+#811) |
|---|---|---|---|---|---|
| py-async-audit | fixed | fixed | hyp (model kept the rule `inferred`: the README line came in the same commit) | fixed | fixed |
| py-paging | fixed | fixed | fixed | fixed | fixed |
| py-rename | routed to security | routed to security | **fixed** | routed to security (claim was an access rule; #811) | hyp (stayed functional; tied to the `inferred` refactor claim) |
| py-float | fixed | hyp (test citation rejected) | fixed | fixed (+1 related finding: the change also dropped `max_digits`/`decimal_places`) | fixed |
| js-foreach-async | hyp | hyp | **dropped** (citations failed; #809) | hyp | hyp (+1 true: the change also breaks a static test that pins `continue`) |
| js-purge-order | hyp | hyp | hyp | hyp | **dropped** (the finding named claim `c1`, but no claims were submitted; #812) |
| js-batch-obo | hyp | hyp | **dropped** (#809) | hyp | hyp |
| js-arg-swap | hyp | hyp | hyp | hyp (+ a CWE-639 hand-off: summaries written under the wrong user) | hyp |
| js-lessonkey | hyp | **lost** (review failed on a 530-char summary; #807) | "validated" on a Python copy of the JS function (#810) | hyp | hyp (+1 consequence: `eventsFromSummary`) |
| 4 clean | 0 | 0 | 0 | 0 | 0 |

| Case (gtC) | gtC1 (+#805) | gtC2 (+#807) | gtC3 (+#809, #810) | gtC4 (+#811) |
|---|---|---|---|---|
| py-test-weakened | validated; the repair cannot pass the changed test, so it is left to a human (correct) | **dropped** (#809) | validated; left to a human | validated; left to a human |
| js-buried | hyp ("cutoff shortened from 365 days to about 6") | hyp | hyp | hyp |
| js-clean-rename (relabelled defect) | hyp (found the broken guard test) | hyp | missed | hyp |
| py-clean-docs | 0 | 0 | 0 | 0 |

### Metrics

| | gtB1 | gtB2 | gtB3 | gtB4 | gtB5 |
|---|---|---|---|---|---|
| Recall, planted bugs flagged (9) | 9/9 | 8/9 | 7/9 | **9/9** | 8/9 |
| Python bugs fixed and Verify-accepted (4) | 3/4 | 2/4 | 3/4 | 3/4 | 3/4 |
| False positives on clean commits (4) | 0 | 0 | 0 | 0 | 0 |
| Reviewer run, median / max | 23.7 / 50.3 s | 24.0 / 49.4 s | 20.1 / 40.7 s | 21.2 / 34.2 s | 19.6 / 33.7 s |
| Reviewer cost per review, mean | $0.0060 | $0.0055 | $0.0047 | $0.0046 | $0.0046 |
| Whole assessment per commit, mean | $0.0105 | $0.0111 | $0.0117 | $0.0098 | $0.0091 |

gtC (the defects among the 4 commits are test-weakened, buried and rename): flagged 3/3, 2/3, 2/3 and 3/3; clean-docs had 0 false positives in every round. Push-to-completed median was 100–145 s.

**Reading these numbers.** Each round re-runs the same changes with new SHAs, and Haiku's choices vary between runs: which claim a finding is tied to, how it quotes, whether it marks a rule `confirmed`. Most of what this round of PRs fixed is deterministic code that was dropping or misrouting findings the model had already made correctly. In every round, the model's own report named every planted bug.

### What the gtB/gtC rounds changed
- **#805:** a rule is routed to security only when it restricts access. "Authenticated" alone sent gtB1 py-rename to Scout.
- **#807:**
  - "must not" counts only when it is about who may act;
  - a paraphrased citation naming an existing test resolves to that test;
  - overlong model text is clipped instead of failing the review.
- **#809:** findings are no longer dropped over quote formatting:
  - comment markers are ignored when matching wrapped quotes;
  - a JS `it('title')` in a quote resolves to its block;
  - a finding whose claim lost every citation, but whose spans are in the change, keeps an `inferred` claim. It can only be a hypothesis.
- **#810:** a generated test must import a module of the project. A Python re-implementation of the JS function had "validated" js-lessonkey. The repair report's `rationale`/`root_cause` are now optional, after a schema failure.
- **#811:** a finding that describes a crash stays functional even under an access rule (gtB4 py-rename). In gtB5 it stayed functional.
- **#812:** a finding that names a claim the model never submitted keeps an `inferred` claim built from the finding, when its spans are in the change (gtB5 js-purge-order).

### Still short (in addition to the list above)
- **JavaScript tests.** Superseded: see the JavaScript section below. The remaining JS gap is functional Verify, which replays generated tests with pytest only.
- **Model variance.** With Haiku, the same change can land as fixed in one round and as a hypothesis in the next (py-async-audit, py-float, py-rename).

## JavaScript tests in production (gtB6–gtB8, gtC5–gtC7), 2026-11-05

The JS half of the second set was re-run after the reviewer gained JavaScript test execution. It used the same 9 mypypath commits per round: 6 planted bugs (including js-buried), 2 clean commits, and js-clean-rename, which is a true positive (see the label correction above). mypypath main did not change between rounds, so the earlier oracle labels still hold.

**What changed:**
- **#830:** `write_test(language="javascript")` writes `tests/generated/cr_<name>.test.js`. A static policy forbids `fs`, network, `child_process`, `process.env`, `eval` and computed imports, and the test must import a real source module by a relative path. It runs through the security_agents sandbox `nodetest` mode, using the target's lockfile-installed `node_modules` with no network. Railway sets `CODE_REVIEW_NODE_ON_VERCEL=1`. The first run built the Node base snapshot and the deps snapshot in about 1 minute each.
- **#831:** in gtB6, running the whole jsdom suite was killed with exit 137 after 131 s. The suite is now limited to tests that mention a changed file (at most 12), with two workers. The prompt asks for `vi.mock` fakes of backend modules (never the module under test).
- **#832:** in gtB7, three generated tests failed on head and passed on base, but their claims never confirmed. A JS comment cited as `code` now counts as a docstring, and the prompt asks findings to name the claim that their sources confirm (`reviewer@6`).

| Case | gtB6 (#830) | gtB7 (#831) | gtB8 (#832) |
|---|---|---|---|
| js-lessonkey | validated, repaired | validated, repaired | validated, repaired |
| js-purge-order | validated, repaired | hyp (5 tests, none failed) | validated, repaired |
| js-buried (gtC) | validated, repaired | validated, repaired | validated, repaired |
| js-batch-obo | hyp | hyp (test fails on head; claim inferred) | validated, repaired |
| js-foreach-async | hyp (whole suite killed, no test) | hyp (test fails; code-only claim) | validated, repaired |
| js-arg-swap | hyp | hyp (test fails; caller code only) | hyp (test fails; caller code only) |
| js-clean-rename (TP) | hyp | hyp | hyp |
| 2 clean | 0 findings | 0 findings | 0 findings |

| | gtB6 | gtB7 | gtB8 |
|---|---|---|---|
| JS bugs flagged (6) | 6/6 | 6/6 | 6/6 |
| Proven by a reproducible failing vitest test (6) | 3/6 | 2/6 | 5/6 |
| Reviewer fix accepted on fresh replay | 3 | 2 | 5 |
| False positives on clean commits (2) | 0 | 0 | 0 |
| Reviewer run, median / max | 183 s / 406 s | 64 s / 175 s | 67 s / 151 s |
| Reviewer cost per review, mean | $0.0061 (7 of 9 recorded) | $0.0102 | $0.0117 |

Every validated finding has the same evidence chain. The generated test failed twice on head in the Vercel microVM (about 15 s per run) and passed on the base commit. For example, gtB6 js-lessonkey failed with `AssertionError: expected 'unit_5F1_5F_5Flesson' to be 'unit_5F1__lesson'`.

js-arg-swap stays a hypothesis by design. Its generated test fails, but its only evidence for the rule is the unchanged caller's code, and code never confirms a rule.

**Not delivered.** Functional Verify in the security agents rejected every one of these fixes (`patch_rejected`). It replays generated tests with pytest only, so it cannot run a `.test.js`. Making Verify run them through the same `nodetest` mode is security-agents work and was not done here. Until then, JS fixes stop at "accepted on fresh replay by the reviewer". The demo branches (27) are deleted, and no delivery PRs were opened.
