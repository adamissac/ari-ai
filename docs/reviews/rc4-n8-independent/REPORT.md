# Repeat independent review — N8-remediated RC4

**NO-GO pending one new P2 artifact-integrity defect, N9.** The previous N8 disclosure and latest-main composition blockers are resolved on this candidate. No new P0/P1 was established. No production code was modified, merged or deployed, and no GitHub approval or paid provider request was submitted.

## Exact reviewed state

- Production candidate: `4fdcf10cc2320b0eb499a177e3b8bea847de8e73`.
- PR #8 tip: `0098f1d5ffedd2b0a27f881fb5af15296693af93`; its only difference is a coordination audit-report file.
- Canonical main: `e41c9dc22e6536463cdab9be6a2a4cd76302c866`, fetched again at final capture; unchanged.
- Independent original regression source: `abf6b316b1de2fea9a8ac8c89a79a7368900145a`.

## Finding: N9 / P2 — annotation matcher corrupts a different statement

[backend/backend/redaction.py:52](https://github.com/m-alan08/ari-ai/blob/4fdcf10cc2320b0eb499a177e3b8bea847de8e73/backend/backend/redaction.py#L52)

The new annotated-assignment alternative uses `[^=\n]+?` for the type annotation. That span also accepts a semicolon and the next statement, so a declaration with no secret is treated as if it assigned the next variable's quoted value:

```python
# Input — valid Python; no credential value
password: str; notice = "public notice"
# Actual output
password: str; notice = "[REDACTED:kv]"
```

The reproduction checks that both input and output parse and requires byte equality for this non-secret source. It fails in the real `redact_code` implementation. A second independent check writes a real unified diff containing this source through `ArtifactStore.put_text(..., kind=ArtifactKind.diff)`, reads it back and requires unchanged bytes; that also fails. Thus this is an executed persisted-artifact defect, not just a theoretical regex concern.

`backend/backend/artifacts.py:102–109` routes diffs through the function. Patch/public diff consumers can receive content that changes an unrelated statement. The separately sealed original-diff path is unchanged and is not shown corrupted by this reproduction; no unauthorized execution or secret disclosure is claimed for N9. This is the same source/artifact integrity requirement as N7, newly broken by N8's broader annotation matcher (introduced in owner fix `5628af35`).

Required correction: restrict the annotation match to the actual assignment's syntactic/token boundaries; do not consume a semicolon or comment into another statement. Preserve the N8 dictionary/typed-secret controls, N7 nonliteral expressions, and original sealed-diff bytes. No fix was made by the reviewer.

## Former findings and upstream compatibility

- **F1–F10: PASS** on the original independent probes: provider replay, emergency capacity, lease fencing, deferral history, waiting OFF cancellation, observability, durable deadlines, final-submit cancellation, schema type/version and database-clock behavior.
- **N1–N6: PASS** on the original probes and production inspection: transactional disconnect/finalization, exact installation reconnect, provider-attempt claim/reconcile/operator retry, legacy history redaction, unique migration chain, monotonic schema progression.
- **N7 original three reproductions: PASS**; the broader non-secret source-integrity requirement now fails in the new N9 case. Do not interpret the old examples passing as universal artifact integrity.
- **N8: PASS** for all four original store/API cases: quoted mapping and typed literal credentials are scrubbed; real viewer reads no longer expose them; unrelated users stay denied. The original assertions were retained rather than weakened.
- **R2–R5: PASS** through the retained disconnect/provider-turn, target-installation, tenant-picker and crash/recovery probes.
- **Latest upstream VerifyEvidence/protected-test probe: PASS**. The previous `candidate_id` constructor mismatch is resolved.
- **Current upstream hourly/daily reset probes: PASS**. Production quota, delivery, retention, host/sealed-diff, pipeline, Verify, workspace, tool-services and orchestrator files are byte-identical to current main. Blob evidence: `evidence/upstream-security-preservation.json`.

Four independent audit files remain byte-identical to the original source; their SHA-256 provenance is retained. Queue, execution, finalizer, services and artifact production files are unchanged since the previously tested RC4; the new redaction implementation and the actual upstream merge were assessed rather than relying only on old results.

## Executed independent evidence

Final [GitHub run 40210138609](https://github.com/m-alan08/ari-ai/actions/runs/40210138609), controller `99bf3d6d`, product exactly as pinned above:

**187 passed, 3 failed, 0 skipped, 0 test errors**, 37.15 s.

- Two failures reproduce N9 (direct code redaction and stored diff).
- One retained old hardening test sets `rate_limit_per_minute=3`, then expects the fourth **GET** to return 429. Upstream #607 split read and write limits. The candidate correctly uses `rate_limit_read_per_minute` for GET. This legacy expectation is a contract mismatch, **not an established rate-limit bypass**.
- An additional independent positive/negative control sets read=3 and write=2, verifies three GET 200s then GET 429, and two POST 201s then POST 429. It **passes**. The old assertion was not removed or rewritten in the independent suite.

The candidate's one-line owner-test change switches the setting to `rate_limit_read_per_minute` while preserving every response assertion. This is a justified contract adaptation, not a weakened security check. Quota probes adapting manual-trigger seeds and PR-author payloads likewise reflect real #607/#593 semantics; no security assertion relaxation was found in the inspected changes.

Earlier [run 40209882486](https://github.com/m-alan08/ari-ai/actions/runs/40209882486) is retained: 186 passed / 2 failed / 0 skipped, before adding the positive split-limit and persisted-artifact controls. It is not substituted for the final failures.

Both executions used network-restricted, resource-limited Docker containers, read-only pinned candidate and independent fixtures, disposable real PostgreSQL and scripted providers. Candidate code received no GitHub/OpenAI/Devin credentials. No original assertions or skips were changed. The known collector cleanup error on container-owned result files is retained and fail-closed; these runs are not called green. It is a review-harness limitation, not a production defect. The one-off active workflow is removed after evidence capture; its YAML is archived for reproducibility.

Real migration upgrade/downgrade, populated 0017→0019→0017→0019, unique head, parallel branches and current-main-to-candidate upgrade probes pass. Final head is **0019**; no migration stamping fabricated compatibility.

## CI and actual landing composition

Exact-candidate check evidence: **24 successful, 1 failed, 2 skipped**. The failed `report` job explicitly says the optional paid Codex audit is unavailable; `codex-audit` and optional provider `live` are skipped. Missing OpenAI credentials are **not** a product vulnerability or a prerequisite for this manual audit. Product CI and strict-regressions checks succeeded.

Actual same-SHA owner CI logs include backend/workspace **1310 passed, 16 skipped**, security agents **806 passed, 23 skipped**, frontend **403 unit tests passed**, Playwright **46 passed**. Counts overlap and are not summed. Optional/skipped/live coverage is not claimed as executed independent proof.

The eight actual transfers were sequentially composed using `git merge-tree --write-tree` and synthetic two-parent commits. **All eight now compose cleanly on current main `e41c9dc2`**; direct current-main/candidate merge is also clean. The candidate contains current main as an ancestor. This closes the previous old-base-only composition blocker.

Pinned steps:

1. S1 `8a945e04b9cecb3d9f10912f78d160f2673594e0`
2. S2 `93b4fe82b8f12df50486b2f452d9d0d339e93bee`
3. Reliability `5e130915d30aad375adc9750f2232e2d29c085cb`
4. Observability `660a3575d9eaf0a2df67a50002b2ec924f182f23`
5. Hardening `89a29d170d4cf1f589975713ee7c8ada778f1ab6`
6. Onboarding `10e923d1ffda75b19b848a7154f8ba867a0a8589`
7. Ops `c1959b4be4dbaa2b25d26e858a5219802f320d0c`
8. Validation `b2a10667b6757e67fb32323919ef2d3cf843160a`

Schema progression: 0.22→0.23→0.23→0.24→0.25→0.26→0.26→0.26. Runtime/contract/deployment implementation matches the candidate. Full Git differences are documentation, stored test/deployment evidence, quota-test formatting and transfer-test SHA literals. The latter two test ASTs match after normalizing immutable SHA literals (evidence retained); the “no test differences” owner wording is literally too strong, but no differing assertion was found. Generated contracts are identical. The stale `transfer/sequential-manifest` branch is not used as proof.

The read-only composition is not a separately executed final deployment; CI evidence is attached to the reviewed candidate with equivalent application bytes. Any new production resolution or changed main requires fresh evidence. Open #629 Verify work is not treated as merged or as a new blocker on this pin.

## Release decision and remaining actions

- **Upstream merging: NO-GO pending N9**, not because of the former upstream conflict or N8.
- **Isolated staging:** fixture-only debugging is appropriate; security release signoff remains HOLD until N9 is corrected and the final build is verified.
- **Customer deployment: NO-GO**, pending corrected artifact integrity plus the final staging/provider/operational gates. No customer enforcement was enabled.

Existing release PRs remain HOLD for sequential landing; reliability and integrated release signoff are NO-GO while N9 is present. This review does not separately approve old standalone owner heads or submit a GitHub approval. Preserve the now-verified S1→S8 application union, fix N9 in its owner workstream, cascade it through the stack, then rerun the original N7/N8 and new N9 tests on the exact final SHA with same-SHA CI. Repair the collector cleanup before claiming an unattended green independent job. No paid API activation is necessary to complete manual independent review.
