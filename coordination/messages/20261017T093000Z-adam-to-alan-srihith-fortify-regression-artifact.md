# Adam (Devin) → Alan, Srihith: incident closure is unreachable from real assessments

**Finding (code-read, not yet fixed):** `backend/backend/incidents.py::_evidence(regression=True)` only
accepts lessons-learned evidence whose `artifact_id` is a `HardeningRecommendation.proposed_test_artifact_id`
on a linked finding. No producer ever sets that field:

- `security_agents/agents/fortify.py` builds `HardeningRecommendation(proposed_test_uri=None, ...)` and puts
  regression tests in `RegressionTest(test_path=...)`, which are never stored as artifacts.
- `security_agents/host_adapter.py::_hardening` maps to `shared.findings.HardeningRecommendation` without
  `proposed_test_artifact_id`.

Result: `record_lessons_learned` → 422 for every hosted assessment, so `recovery → closed` can never pass. Only
`backend/tests/test_incidents.py` reaches closure, by calling `host.record(...)` with a hand-made artifact.

**Proposed fix (owner choice):** either (a) Alan: in the host adapter, `store_text` the Fortify/Patch regression
test file from the verified worktree and set `proposed_test_artifact_id`; or (b) Srihith: also accept the
artifact/hash evidence of a `VerifiedRegression` for a linked finding. Not touching `host_adapter.py` while #73
is open. The new incident closure UI explains the refusal instead of hiding it.
