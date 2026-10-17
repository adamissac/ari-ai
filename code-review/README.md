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
`CODE_REVIEW_SANDBOX_PYTHON` (interpreter that has the target's deps).

## Evidence status

* Executed: 33 tests pass (`uv run pytest -q code-review/tests`). They cover labeled
  scenarios (discount rounding, a fix that weakens tenant auth, the payments-lite refund
  bound), the review → approval → repair → fresh replay flow on the real `AssessmentHost`
  with PostgreSQL, Verify independence, and policy units.
* **Not executed:** the live Tier-3 run (`test_live_reviewer.py`). The development
  environment had no authorized API key. No live-model claim is made.
* **Unverified integrations:** `code_intelligence` (Sarosh) is used through
  `IntelligencePort` when importable; until then the tools report `UNAVAILABLE`. Alan's
  Docker sandbox and Verify agent are not wired in yet; the Verify used in the tests is a
  labeled test double.
