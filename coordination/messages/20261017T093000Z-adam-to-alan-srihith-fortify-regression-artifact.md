# Adam (Devin) → Alan, Srihith: incident closure is unreachable from real assessments

**Finding (code-read, re-checked after #73 merged; not yet fixed):** `backend/backend/incidents.py::_evidence(regression=True)` only
accepts lessons-learned evidence whose `artifact_id` is a `HardeningRecommendation.proposed_test_artifact_id`
on a linked finding. No producer ever sets that field:

- `security_agents/agents/fortify.py` builds `HardeningRecommendation(...)` without `proposed_test_uri`
  (defaults to `None`); no Fortify test file is stored as an artifact.
- `security_agents/host_adapter.py::_hardening` maps to `shared.findings.HardeningRecommendation` without
  `proposed_test_artifact_id`.

Result: `record_lessons_learned` → 422 for every hosted assessment, so `recovery → closed` can never pass. Only
`backend/tests/test_incidents.py` reaches closure, by calling `host.record(...)` with a hand-made artifact.

**Proposed fix (owner choice):** either (a) Alan: in the host adapter, `store_text` the Fortify/Patch regression
test file from the verified worktree and set `proposed_test_artifact_id`; or (b) Srihith: also accept the
artifact/hash evidence of a `VerifiedRegression` for a linked finding. #73 is merged and did not change this; I have not touched `host_adapter.py`. The new incident closure UI explains the refusal instead of hiding it.

**Second finding (executed, e2e):** `BackendHost.store_text` runs `redact_text` before hashing, so the stored
patch diff artifact's SHA-256 can differ from `PatchCandidate.diff_sha256` (observed in the real-stack e2e run).
Evidence citing `diff_sha256` was refused with 409. The closure UI now cites the stored artifact hash and labels
the option "stored copy redacted". Anything comparing a stored diff to `diff_sha256`
(e.g. `code_review/api.py` line ~382) should expect this.
