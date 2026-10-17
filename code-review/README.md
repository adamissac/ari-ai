# code-review/

Pillar 1's runtime agent: the **reviewer** (`AgentName.reviewer`). It works out what a
change is *supposed* to do, proves functional defects with executed behavioral tests,
and proposes minimal repairs in isolated workspaces. Spec: [docs/06](../docs/06_CODE_REVIEW_AND_REPAIR.md).

## What exists (implemented and tested)

| Module | What it does |
|---|---|
| `code_review/agent.py` | `ReviewerAgentRunner`: two bounded multi-turn Claude tool loops through the backend gateway (`host.llm().run_tool_loop`). **review** submits a `ReviewerReport`; **repair** (approval-gated) submits a `RepairReport`. Statuses are decided by code, not by the model. |
| `code_review/intent.py` | `IntentEvidence`: every citation is checked against the pinned files (path, line range, quoted text). `confirmed` needs a doc, docstring, existing test or confirmed index expectation; PR text or code alone gives `inferred`. Instruction-like PR text is flagged and treated as data. |
| `code_review/tools.py` | Permission-enforced tools: `list_files`, `read_file`, `search_code`, `get_change_diff`, `list_expectations`, `get_context_pack`, `write_test` (only new files under `tests/generated/`, AST policy: no subprocess/network/fs abuse, no new credential-shaped values), `run_tests`; repair mode adds `edit_file`, `apply_patch`, `show_diff`, `revert_file`. Tests, conftest, pytest/tox/setup config, `pyproject.toml` and lockfiles are never writable. Budgets cap tests written, runs and edits. |
| `code_review/workspace.py` | SHA-pinned exports via `git archive` into temp dirs: no `.git`, no link back to the customer repo. Unified diffs, `git apply` inside the workspace, docstring ranges. |
| `code_review/sandbox.py` | `LocalProcessSandbox` (`SandboxPort`): fixed pytest command, scrubbed env (no keys), rlimits, timeout, process-group kill, output cap; a pytest plugin records each test's exception type. Classifies runs as `passed`, `failed` (AssertionError / pytest.fail) or `error` (tooling, which is inconclusive). **No network isolation**; production should use Alan's Docker driver through the same port. |
| `code_review/shared_sandbox.py` | `SharedSandboxAdapter`: the same `SandboxPort` over Alan's `security_agents` drivers (fixed `pytest` mode, reporting plugin shipped via `extra_files`, results from `/out`). `CODE_REVIEW_SANDBOX=docker` uses `DockerSandboxDriver` (network none); `shared-local` uses the dev `LocalProcessDriver` (needs `SANDBOX_ALLOW_LOCAL_PROCESS=1`); the default `local` keeps `LocalProcessSandbox`. |
| `code_review/api.py` | `review(host, ReviewRequest) -> ReviewResult`, `review_full`, `generate_tests`, `propose_repair(host, finding_id, approval_id, repo_id=)`, `load_test_sources`. |
| `code_review/evaluation.py` | Scores an outcome against an answer key (`examples/payments-lite/labels.yaml`) after the run. Scripted runs are labeled "harness check only". |

### Decision rules (deterministic)

* Finding `validated` only if its generated test **fails with an assertion, twice**, on the
  head commit, **and** the violated claim is `confirmed`. If the rule is unconfirmed the
  finding stays `hypothesis` and the review status is `needs_clarification`. A passing
  test gives `refuted`. Errors or non-reproducible failures give `inconclusive`. A finding
  with no executed test is a `hypothesis`.
* The same test also runs on the base commit when one exists. "Passes on base, fails on
  head" is recorded as introduced by the change.
* Security concerns (auth, tenant isolation, injection) become `kind=security,
  status=hypothesis` findings with cited spans, "handoff to scout". The reviewer never
  claims they were exploited.
* Repair requires an **approved `remediation` approval for that finding**. A patch exists
  only after a **fresh export + diff + trusted tests** replay passes: the generated tests
  pass, and the existing suite has no new failures. The finding moves to `patch_proposed`,
  never `verified`. `VerificationResult` must come from the independent Verify run (the
  backend enforces this; tested).

## Commands

```bash
uv sync                                    # from the repo root (workspace member)
uv run pytest -q code-review/tests         # Tier 1/2: FakeTransport + real tool execution
RUN_LIVE_LLM_EVAL=1 uv run pytest -q -m live_llm code-review/tests -s   # Tier 3, costs money; CODE_REVIEW_LIVE_MAX_USD (default 1.00)
```

Repositories must be registered by the operator:
`CODE_REVIEW_REPOSITORIES="rep_<id>=/abs/path/to/repo#optional/subdir"`. Optional:
`CODE_REVIEW_SANDBOX_PYTHON` (interpreter that has the target's deps), `CODE_REVIEW_SANDBOX` (`local` | `shared-local` | `docker`). Docker execution of the shared driver is UNVERIFIED here (no Docker engine); the adapter is tested with the shared local-process driver (`uv pip install -e security-agents --no-deps && uv run --no-sync pytest -q code-review/tests/test_shared_sandbox.py`).

## Evidence status

* Executed (FakeTransport, real tools): `uv run pytest -q code-review/tests` → 57 passed,
  1 skipped (the live test). Coverage: labeled scenarios (discount rounding, a fix that
  weakens tenant auth, the payments-lite refund bound and IDOR), the review → approval →
  repair → fresh replay flow on the real `AssessmentHost` with PostgreSQL, Verify
  independence, human expectation decisions from the real intelligence memory, tolerant
  span verification (with the exact spans from the first live run), CWE adjudication end
  to end, and policy units. CI: `.github/workflows/code-review.yml` (strict mypy + Postgres).
* **Live Tier 3, executed by Adam with the owner's key** (this agent spends nothing):
  * run 1 (main @ `0612cc5`): PASS, refund-bound TP, repair accepted ($0.276 + $0.082).
    It exposed a span-verifier bug that dropped all security hand-offs; fixed in #59.
  * run 2 (main @ `cdfc679`, after #59): PASS, refund-bound TP, FP 0, FN 0,
    `generated_tests_failing_on_head: 2`, **`security_handoffs_matched: [fnd_planted_authz]`**,
    0 rejected spans, repair accepted. Cost: review $0.374 + repair $0.115.
    (`coordination/messages/20261017T070325Z-adam-to-all-live-p1-p2-handoff-works.md`)
  * Srihith's live unified run reported the reviewer producing 2 validated findings ($0.37).
* **Integrations:** the real `code_intelligence` index is consumed and tested
  (`test_intel_integration.py`). Index expectations are `ambiguous` by design and cannot
  confirm a claim alone. Alan's shared sandbox driver is adopted (`test_shared_sandbox.py`;
  its Docker path is unverified because no engine is available). The backend runs the reviewer inside the hosted
  assessment (Srihith). The Verify in `test_host_integration.py` is still a labeled test double.

### Standards classifications

Producer standards fields resolve through the pinned offline `standards` catalog.
CWE proposals must identify real, nondeprecated weaknesses (categories such as
CWE-840 are not accepted as weakness classifications). CWE/CAPEC/ATT&CK catalog relationships are review candidates; they are not
automatically attached as ATT&CK mappings. These are
classifications, not evidence of production adversary activity.

Canonical `standards.mapping` validates classifications and reviewed rules.
CVSS is separate from the existing qualitative severity rubric. Trace can accept
a complete set of explicit CVSS v4 base metrics with executed validation artifact
references, then computes and validates the vector and score deterministically.
Missing metrics or unrelated artifacts leave the finding unscored. Evidence
provenance does not by itself prove an analyst's metric interpretation.

D3FEND mappings use the owner-reviewed rules keyed by Fortify category and
confirmed check category. Unsupported combinations remain unmapped. Reviewed RL actions have simulation-derived D3FEND
classifications, while unsupported actions stay unmapped. No rule
executes a defensive action against real systems.
