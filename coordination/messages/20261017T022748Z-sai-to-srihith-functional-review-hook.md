# MSG: Call the reviewer in FUNCTIONAL_REVIEW — one-line hook, shared repo registry
- ID: `20261017T022748Z-sai-to-srihith-functional-review-hook`
- From: sai
- To: srihith (cc: alan)
- Kind: `integration`
- Timestamp (UTC): 2026-10-17T02:27:48Z
- Branch / commit / PR or issue link: `feat/sai/reviewer-repair-agent` @ `5fa801a`, PR https://github.com/adamissac/hackatl-agentic-security/pull/22
- Related subsystem(s): backend adapter / pipeline ↔ code-review
- Summary (facts, not assumptions):
  - `backend/adapters/security_agents.py` passes through FUNCTIONAL_REVIEW without running the reviewer, so no functional findings appear in the hosted flow today.
  - `code_review.api.review_assessment(host, change_intent=None, focus_paths=None)` builds the `ReviewRequest` from `host.assessment`: the exact commit, the snapshot row recorded for (repo, sha) (`SNAPSHOT_NOT_READY` if there is none; no invented ref), and the assessment budget. It runs the reviewer loop through `host.llm()` and records findings, runs and artifacts through the host. Tested on real PostgreSQL (`code-review/tests/test_host_integration.py::test_review_assessment_entry_uses_recorded_snapshot`).
  - `resolve_repo` now reads your `REPOSITORY_BINDINGS_FILE` (same `{repo_id, local_path, subdir}` JSON) and honors `build_recipe.json` `target_dir` read via `git show <sha>:...`. There is one registry for both pillars.
- Interface requested/proposed (field-level types/example payload): in the adapter, while in FUNCTIONAL_REVIEW:
  ```python
  try:
      from code_review.api import review_assessment
  except ImportError:
      review_assessment = None  # degrade, and say so in a progress event
  if review_assessment:
      outcome = review_assessment(host, change_intent=<ChangeIntent from the push/PR event, if known>)
      # outcome.security_handoffs -> seed Scout (kind=security, status=hypothesis, cited spans)
  ```
  For monitoring triggers, please pass `ChangeIntent(source=push|pull_request, title, body, base_sha, head_sha)` from the delivery. That lets the reviewer review the diff against its intent rather than the whole snapshot.
- Breaking change? migration/test impact: none (additive call). A reviewer failure raises `ReviewError`/`LLMError` with a shared `ErrorCode`.
- Action required by recipient: add the hook (it's your file) or tell me to send a PR touching only those lines.
- Response-by milestone (not invented clock time): M2/M7.
- Evidence: `uv run pytest -q` (repo, merged with origin/main) → 132 passed, 7 skipped.
- In-Reply-To (optional): `coordination/messages/20261017T021618Z-srihith-to-alan-host-mode-findings.md`
