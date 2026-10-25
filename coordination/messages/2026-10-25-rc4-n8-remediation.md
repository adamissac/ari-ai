# RC4 NO-GO remediation — 2026-10-25

Independent RC4 review: https://github.com/adamissac/ari-ai/pull/632
(`codex/rc4-independent-audit`, `docs/reviews/rc4-independent/REPORT.md`)
Verdict there: **NO-GO** on `6a72949efa7c0a2d3233eb6884bb7a23dfe71ced` — new P2
finding N8 only; F1–F10 and N1–N7 all PASS.

## Candidate after remediation

Integration tip: **`2f2f4bc38e87ade6c2ba0f4e86f466d3ced18e93`** on
`integration/2026-11-02-release` (PR https://github.com/m-alan08/ari-ai/pull/8,
base `ci/upstream-e41c9dc2` = canonical main
`e41c9dc22e6536463cdab9be6a2a4cd76302c866`).

Prior candidate `6a72949e` and frozen RC1 `bc490484` preserved.

## N8 — P2 artifact disclosure (owner fix `5628af35`)

`_CODE_KV_PATTERN` missed two code forms, so quoted secrets survived in diff
artifacts labelled `redacted=true` and were served to project viewers:

- quoted mapping keys / subscripts: `{"password": "lit"}`, `d["k"] = "lit"`
- annotated assignments: `password: str = "lit"`

Owner: execution-reliability session (also owns `redaction.py`).
Fix (their commit `5628af35` on `feat/devin-execution-reliability`, merged here
as `76ee39f5`): `_CODE_KV_PATTERN` gained literal-terminating prefixes for
annotated assignments and quoted mapping keys/subscripts (single + double
quotes). Only the quoted literal is rewritten; unquoted non-secret expressions
(`api_key=os.environ["API_KEY"]`, `password: str = os.getenv(...)`) remain
byte-identical — N7 is not reopened. Sealed-diff path untouched; unrelated-user
404 preserved; `redacted=true` labelling unchanged.

Codex's verbatim probes (copied as
`backend/tests/live_defense_e2e/test_rc4_n8_artifact_disclosure.py` @ `4cd32dfb`)
— **4/4 pass**: ArtifactStore.put_text/get roundtrip redacts the literal while
keeping `redacted` semantics; the real viewer API returns 200 without the
secret; the unrelated user still gets 404. N7 probes (test_redact_code /
test_redact_text_gaps, vendored + suite) re-run green.

## Upstream reconciliation — canonical main `e41c9dc2`

Canonical main moved `eea084bc` → `e41c9dc2` (~25 PRs). Merged into the
integration branch at `463210f8`. Preserved upstream semantics, verified by
probe adaptation rather than weakened assertions:

- #607 split user rate limits: `rate_limit_read_per_minute=600` for GET/HEAD,
  `rate_limit_per_minute` for writes — `require_user` applies both; adapted
  `test_customer_security_hardening.py` to the split contract.
- #607 manual-only quota counting: `check_project_quota(manual=True)` filters
  `trigger == manual`; adapted `test_rc2_latest_quota.py` (manual-only seeds,
  429 `RATE_LIMITED` + `resets_at`).
- #593 `ReviewerSettings` + reviewer author source `pull_request.user.login`;
  PR probe payload carries `user.login`.
- #598 `GET /api/v1/github/commit`; #616 stale-base delivery; #621
  retention/destructive-pruning guards; #601/#618/#626 verify protections
  (`VerifyEvidence(candidate_id=…)` seam resolves in the merged tree — upstream
  `verify.py` defines the field, `orchestrator.py` passes it).
- Frontend #619–#624 land via the merge.

## Transfer stack — rebuilt on `e41c9dc2`, N8 cascaded

| Step | Branch | SHA | Schema |
|---|---|---|---|
| 1 | `transfer/01-pr412` | `8a945e04b9cecb3d9f10912f78d160f2673594e0` | 0.22 |
| 2 | `transfer/02-pr458` | `93b4fe82b8f12df50486b2f452d9d0d339e93bee` | 0.23 |
| 3 | `transfer/execution-reliability` | `5e130915d30aad375adc9750f2232e2d29c085cb` | 0.23 |
| 4 | `transfer/investigation-observability` | `660a3575d9eaf0a2df67a50002b2ec924f182f23` | 0.24 |
| 5 | `transfer/pilot-security-hardening` | `89a29d170d4cf1f589975713ee7c8ada778f1ab6` | 0.25 |
| 6 | `transfer/customer-onboarding` | `10e923d1ffda75b19b848a7154f8ba867a0a8589` | 0.26 |
| 7 | `transfer/pilot-deployment-ops` | `c1959b4be4dbaa2b25d26e858a5219802f320d0c` | 0.26 |
| 8 | `transfer/release-validation` | `b2a10667b6757e67fb32323919ef2d3cf843160a` | 0.26 |

All merges forward-only (no force-push). Cascade: N8 fix merged at S3, then
S4→S8 re-merged in order; `test_rc2_transfer_manifest.py` repinned (`7c78f3a4`)
and green.

**Merge equivalence:** `git merge-tree --write-tree` synthetic composition of
the eight steps equals the actual stack trees on `e41c9dc2`; S8's tree diff vs
the candidate is documentation/test-results/coordination files only — zero
production, test, or contract differences. Migrations single head `0019`
(upstream 0016/0017, 0018 execution_reliability, 0019 repository_disconnect).
S8 generated contracts byte-identical to the candidate's regenerated files.
Schema progression 0.22→0.26 monotonic (Codex N6 assertion unchanged, passing).

## Strict matrix on `2f2f4bc3`

- backend: see "Local matrix" line in the PR comment (full suite re-run on the
  final tree after the N8 merge)
- live_defense_e2e + N1–N8 + F1–F10 + R2–R5 + manifest/independent-review:
  **58 passed, 1 skipped** (opt-in live provider eval)
- security-agents: **795 passed, 24 skipped**
- shared: 13 passed, 3 skipped · migrations 2/2, head `0019`
- frontend: **403 passed** + lint + typecheck + build clean
- transport: 36/36
- `make check` + `mypy`: clean (41 source files, 0 issues)
- zero xfails; no assertion weakened (regressions fixed by adapting probe
  payloads/settings to real upstream contract changes)

## GitHub CI

PR #8 base retargeted to `ci/upstream-e41c9dc2` so `pull_request` workflows run
on the actual upstream merge commit (ci/upstream-main is protected; a new
mirror branch was created instead of a merge). Latest CI runs execute against
the real candidate head. See the PR checks section for same-SHA results.

## Outstanding blockers

1. Codex exact-SHA review of `2f2f4bc3` (or the next tip — docs commits only).
2. Adam's approval of the upstream landing order S1→S8.
3. `OPENAI_API_KEY` + `ARI_FIX_WEBHOOKS` fork secrets + 7 findings-router
   automation approvals (pipeline otherwise degrades to CI-only NO-GO).
4. `pilot-verify` manual dispatch; ops items (real secrets, backup schedule,
   staging deploy + `--remote` readiness).

## Verdict

**GO FOR INDEPENDENT REVIEW** — not customer GO. Nothing merged, deployed, or
enforcement-enabled.
