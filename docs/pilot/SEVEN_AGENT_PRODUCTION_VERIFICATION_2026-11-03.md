# Seven-agent pipeline: production verification, 2026-11-03

Real GitHub pushes to a connected repository, observed through the production API
(`https://ari-ai-lake.vercel.app/api/v1`, owner session). Nothing here is replayed or
scripted: every agent run reports `provider_mode: live`.

## Target and ground truth

`adamissac/pilot-rehearsal-target` (ledgerlite, FastAPI), short-lived branch
`demo/sec-verify-20261102`. Eight weaknesses, each reproduced locally against the
pushed code before the push (script in the session scratchpad; outputs quoted).

| ID | Weakness | CWE | Where | Local reproduction |
|---|---|---|---|---|
| V1 | BOLA: any customer reads any transfer | CWE-639 | `GET /transfers/{transfer_id}` | bob reads alice's `txn_seed_a1`: 200 |
| V2 | Missing authentication, PII | CWE-306 | `GET /customers/{customer_id}` | anonymous: 200 with name + email |
| V3 | SQL injection | CWE-89 | `GET /notes/search?q=` (f-string SQL) | `' OR '1'='1' --` returns bob's private note to alice |
| V4 | Path traversal | CWE-22 | `GET /statements?file=` | `file=/etc/hosts` returns the host file |
| V5 | SSRF | CWE-918 | `POST /webhooks/test` (`urlopen(body.url)`) | not executed (no outbound call made); code-evident |
| V6 | Hard-coded credential | CWE-798 | `ledgerlite/config.py` (AWS documented example key pair) | present on added lines |
| V7 | Race: lost update on balance | CWE-362 | `Store.make_transfer` (read, 50 ms scorer call, write) | 4 concurrent 400.00 transfers from 500.00: all 201, bob credited 1,600.00 |
| V8 | Transfer to a nonexistent destination burns funds (pre-existing on `main`) | CWE-1284 | `POST /transfers` | 201, alice debited 100.00, nobody credited |

## Runs before the fixes

Push to assessment creation took 2-3 s in both runs (webhook, queue, scope check).

### Run A: code only (`23a5b2c`), build recipe not updated

`asm_01M6FEA1XEYP62YWMS90WCGB1E`: 56 s, $0.018, 13 LLM calls.

Scout raised 3 hypotheses (V1, V3, V4); the reviewer raised 6 (V1-V5, V7, the last with a
failing generated test). Probe validated only 2 (`validate_count=2`), both
**inconclusive**: the new routes were not in `build_recipe.json`, so no template could
name them. Correct behaviour, and the expected outcome when a customer adds routes without
updating the recipe.

### Run B: recipe declares the new routes (`c524f28`)

`asm_01M6FED6PT8MRRD4A6EAJHEHJJ`: 2 min 27 s push to COMPLETED, $0.057, 52 LLM calls,
55 s sandbox.

| Stage (UTC 00:54:xx-00:57:xx) | Start | End | Duration |
|---|---|---|---|
| push -> assessment created | 54:32 | 54:35 | 3 s |
| Reviewer (parallel to Scout) | 54:36 | 55:09 | 33 s |
| Scout | 54:36 | 54:56 | 20 s |
| Probe x2 (sequential) | 54:56 | 55:13 | 17 s |
| Trace x2 (sequential) / Diagnose x2 (parallel) | 55:13 | 55:49 | 36 s |
| Patch + Verify, finding 1 | 55:50 | 56:23 | 33 s |
| Patch + Verify, finding 2 | 56:26 | 56:59 | 33 s |
| Fortify x2 (parallel to Patch) | 55:50 | 56:15 | 25 s |
| COMPLETED | | 57:02 | |
| fix PRs opened (#7, #8) | | 57:06 / 57:09 | |

V1 and V2 went **validated -> patched -> verified -> hardened**, each with CVSS 3.1 base
metrics cited to sandbox runs and source spans, CWE 4.20 tags, and a fix PR with a
regression test. Both patches were minimal and correct (ownership check reusing the
`get_account` pattern; `current_customer` dependency plus self-only read).

## Scorecard before the fixes (best of run A/B)

| ID | Found | Validated in sandbox | Patched | Verified | Hardened |
|---|---|---|---|---|---|
| V1 BOLA | yes (Scout + reviewer) | yes | yes | yes | yes |
| V2 no auth | yes (Scout + reviewer) | yes | yes | yes | yes |
| V3 SQLi | yes (Scout + reviewer) | no template | - | - | - |
| V4 traversal | yes (Scout + reviewer) | never probed / no template | - | - | - |
| V5 SSRF | yes (reviewer) | no template | - | - | - |
| V6 secret | **no** | - | - | - | - |
| V7 race | reviewer only (run A, failing generated test) | no template | - | - | - |
| V8 destination | **no** | no template | - | - | - |

False positives: none. Every reported weakness is real. Duplicates: the reviewer's
security concerns repeat Scout's (V1 appears as a hardened Scout finding *and* an open
reviewer hypothesis).

## Gaps found and what was done

| # | Gap | Severity | Fix |
|---|---|---|---|
| G1 | Fix PRs targeted `main` though the assessed commit was on a feature branch; each PR (#7, #8) carried the whole vulnerable feature into `main` | high (merging the "fix" ships the vulnerabilities) | PR #780: delivery resolves the pushed branch from the push event and uses it for the tip check, auto push and PR base |
| G2 | Scout capped at 3 hypotheses and Probe at 2, run sequentially | high (most of a multi-bug commit never probed) | PR #783: 6 hypotheses, all validated, Probe steps concurrent |
| G3 | No template for races or destination references | high | PR #783: `input_validation.concurrent_bound@1`, `input_validation.destination@1` |
| G4 | Trace per finding ran sequentially | latency (+18 s per finding) | PR #783: Trace steps concurrent |
| G5 | Committed credentials never reported (models read redacted source) | high | PR #784: deterministic CWE-798 scan of added lines |
| G6 | Reviewer security concerns are labelled "handoff to scout" but never reach Scout or Probe (they run in parallel) | medium | not fixed; follow-up |
| G7 | No validation templates for SQLi, path traversal, SSRF | medium | not fixed; follow-up (needs new scope categories, so owner re-approval) |
| G8 | SARIF 2.1.0 is stored per run (final copy at REPORTING: `hardened`, verdict `accepted`), but holds only security-agent findings; reviewer CWE hypotheses (incl. the new CWE-798) are absent | low | not fixed |
| G9 | Patch -> Verify runs one finding at a time | latency (~33 s per finding) | not fixed: Patch shares the worktree host |

## Fixes landed

- #790 (combines #780, #783, #784): G1, G2, G3, G4, G5. Deployed 04:10 UTC.
- #797: one-segment routes never matched themselves when reconciling a check, so a failed (confirming) check on `POST /transfers` was recorded inconclusive. Deployed 07:34 UTC.
- #793: the registry scope-checked a run against the template *id* instead of its declared category, so `input_validation.concurrent_bound@1` was refused `CATEGORY_NOT_ALLOWED` live. Deployed 04:26 UTC.

## Run C after #790 (`555b66a`, recipe declares `{destination}` and `balance_field`)

`asm_01M6FSKFCDJVD99DDKREHN1XYW`: 4 min 22 s, $0.087.

| Stage | Before (run B) | After (run C) |
|---|---|---|
| push -> assessment | 3 s | 2 s |
| Scout | 20 s | 32 s (5 hypotheses, was 3) |
| Probe | 17 s for 2, sequential | 9 s for 4, concurrent |
| Trace | 36 s for 2, sequential | 23 s for 2, concurrent |
| Patch + Verify per finding | 33 s | 33-40 s per attempt |

Results: V2 validated -> patched -> verified -> hardened again, and **the fix PR (#11) now targets `demo/sec-verify-20261102` with one commit and only the fix files** (G1 confirmed live). V1 validated but ended `patch_rejected` after 4 Patch/Verify attempts: the demo fixture seeded bob's transfer *to alice*, Diagnose planned "caller must be a party to the transfer", and Verify correctly kept failing the check (alice is a party). That is a fixture ambiguity in the demo recipe, fixed locally (transfers seeded to a third customer) but not re-run. V7 race: Probe chose `input_validation.concurrent_bound@1` and was refused by the scope bug fixed in #793; not re-run after the fix. V4 inconclusive (no template). V8: no Scout hypothesis.

Locally (same target code, same recipe, real CheckRunner): `concurrent_bound` confirms V7, `destination` confirms V8, `ownership` confirms V1.

## Run D after #793 (`d0643c8`, transfers seeded to a third customer)

`asm_01M6G499QRS4JD9DTZ2F9EQETN`: 2 min 7 s, $0.046. V1 validated -> patched -> verified ->
hardened on the first attempt. Probe ran `input_validation.concurrent_bound@1` and the
executed check **failed in the microVM** (8 concurrent 300.00 transfers accepted against a
500.00 balance, 2,400.00 moved), yet the finding was recorded `inconclusive`:
`probe.same_route` never matched a one-segment route (`POST /transfers`) to itself, so the
run counted as outside the hypothesis subject. Fixed in #797 (deployed 07:34 UTC).

## Run E after #797 (`0175cb3`, adds a second AWS example key pair in `ledgerlite/archive.py`)

`asm_01M6G596S34CW7GY9M500J2ZQH`: push 07:34:19, created 07:34:21, COMPLETED 07:38:07
(3 min 48 s), $0.092.

| Stage | Start | End | Duration |
|---|---|---|---|
| Reviewer / Scout (parallel) | 34:24 | 34:46 / 34:50 | 22 s / 26 s |
| Probe x4 (concurrent) | 34:50 | 35:00 | 10 s |
| Trace x3 + Diagnose x3 (concurrent) | 35:00 | 35:27 | 27 s |
| Fortify x3 (concurrent with Patch) | 35:28 | 35:55 | 27 s |
| Patch + Verify V1 / V7 / V8 (sequential) | 35:28 | 38:04 | 37 s / 52 s / 48 s |
| fix PRs #13, #14, #15 (into the demo branch) | | 36:23 / 37:19 / 38:10 | |

V7's patch takes a `threading.Lock` around read-check-write in `make_transfer` and moves the
balance check inside it; Verify re-ran the concurrent check on the patched code and
accepted it. V8's patch rejects an unknown destination before any mutation.

## Final scorecard (best live result per weakness)

| ID | Found | Validated in sandbox | Patched | Verified | Hardened | Run |
|---|---|---|---|---|---|---|
| V1 BOLA | yes | yes | yes | yes | yes | B, D, E |
| V2 no auth | yes | yes | yes | yes | yes | B, C |
| V3 SQLi | yes | no template | - | - | - | A-E |
| V4 traversal | yes | no template | - | - | - | A-E |
| V5 SSRF | yes | no template | - | - | - | A, B, D |
| V6 secret | yes (CWE-798, deterministic scan) | n/a (static) | - | - | - | E |
| V7 race | yes | **yes** | yes | yes | yes | E |
| V8 destination | yes | **yes** | yes | yes | yes | E |

Before the fixes: 2 of 8 hardened, 6 of 8 found. After: 4 of 8 hardened, 8 of 8 found.
False positives on the planted code: none. Two noise findings: the reviewer flagged the
recipe's `{destination}` placeholder (run C, CWE-841) and an `[unclassified]` archive-key
concern (run E).

| Latency | Before (run B, 2 findings) | After (run E, 3 findings) |
|---|---|---|
| push -> assessment created | 3 s | 2 s |
| Probe | 8.5 s per hypothesis, sequential | 10 s for 4, concurrent |
| Trace | 18 s per finding, sequential | 27 s for 3, concurrent |
| Patch + Verify | 33 s per finding, sequential | 37-52 s per finding, sequential |
| push -> COMPLETED | 2 min 30 s | 3 min 48 s |

## Still open

- Each finding's fix PR is cut from the assessed commit, so PRs #13-#15 overlap in `app.py`/`store.py` and the second one merged will conflict.

- G10: Patch retried 4 times with a plan that contradicts the confirming check (~2.5 min, ~$0.03 wasted); a rejection that cites the check should go back to Diagnose, not repeat Patch.
- G6, G7, G9 above. The reviewer also raised a CWE-841 hypothesis about the recipe's `{destination}` placeholder itself (false positive on config).
- Other sessions pushed 12 commits to the same target repo during this run (PR #10 is theirs).
