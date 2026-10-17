# M7 Demo Execution Report

**Generated:** 2026-10-17
**Branch:** `devin/m7-demo-validation`
**Test:** `backend/tests/test_m7_push_to_regression.py`

## Executive Summary

The M7 unified demonstration workflow executed successfully. The full chain from signed GitHub push through independent verification and regression recording completed without errors.

**Status:** ✅ M7 BACKEND WORKFLOW VERIFIED

## Test Execution

### Command Executed

```bash
python3 scripts/devin_qa/verify_m7_demo.py
```

### Environment

- **Python:** 3.14.4
- **UV:** 0.13.0
- **Database:** Embedded PostgreSQL (pgserver)
- **Model Mode:** Fake (TEST-ONLY scripted transports)
- **Target:** Owned `examples/payments-lite` sandbox

### Stages Executed

#### Stage 1: Prerequisites ✅
- Python available: PASS
- UV available: PASS

#### Stage 2: M7 Backend Workflow ✅
- **Test:** `backend/tests/test_m7_push_to_regression.py`
- **Result:** PASS
- **Duration:** ~15 seconds (full chain execution)

**What was verified:**
1. Signed push of a real second commit on the owned payments-lite repo
2. Monitoring event ingestion and reassessment trigger
3. Assessment pinned to the pushed commit
4. Functional review execution
5. All seven security agents (Scout, Probe, Trace, Diagnose, Patch, Fortify, Verify)
6. Human approvals (security + functional)
7. Candidate patches (security fix + reviewer's functional repair)
8. Independent Verify for both security and functional patches
9. Findings transition to correct final states (hardened, verified)
10. Verified-regression candidates recorded on the snapshot
11. Durable event log ends with `assessment.completed`
12. Audit hash chain verified

**Evidence:** The test validates the complete M7 chain as specified in `coordination/MILESTONES.md`.

#### Stage 3: Browser Demo ⚠️ BLOCKED
- **Status:** BLOCKED
- **Reason:** Browser E2E requires running API/worker services
- **Manual Path:** Use `frontend/tests/e2e/stack.py` with `make dev`

**Note:** The Playwright browser journey is covered by Vihaan's M6 evidence (see coordination/MILESTONES.md). This validation focused on the backend API-level M7 chain.

## Detailed Results

### M7 Chain Details

**1. Monitoring Budget**
- Default 150k tokens too small for full chain
- Test raised to 400k tokens through PATCH /projects/{id}
- Settings API updated successfully

**2. Signed Push**
- Real second commit on payments-lite (behavior-neutral)
- HMAC-signed webhook delivered
- Monitoring event ingested
- Reassessment triggered

**3. Assessment Pinned**
- Assessment created and pinned to pushed commit SHA
- Trigger set to "monitoring"
- State transitioned to AWAITING_APPROVAL

**4. Human Approvals**
- Two pending approvals: security + functional
- Bob approved both via API
- Worker drained all jobs

**5. Agent Execution**
- All required agents executed: reviewer, scout, probe, trace, diagnose, patch, verify, fortify
- Each agent run produced valid output
- Agent steps persisted correctly

**6. Independent Verification**
- Security patch: Verify re-ran check, verdict "accepted"
- Functional patch: Verify ran generated tests, verdict "accepted"
- Verify run distinct from patch run
- Findings transitioned to "hardened" (security) and "verified" (functional)

**7. Regression Recording**
- Snapshot ID associated with assessment
- Verified-regression candidates recorded
- Regression IDs linked to finding IDs

**8. Audit Trail**
- Event log ends with `assessment.completed`
- Audit hash chain verified
- Chain events checked

## Conclusion

The M7 backend workflow is **fully verified**. The complete chain from signed push through independent verification and regression recording executes successfully with proper evidence persistence.

**Browser demo validation is blocked** because it requires running the full local stack (API + worker). This should be executed manually using `make dev` and `frontend/tests/e2e/stack.py` as documented in Vihaan's M6 evidence.

**Recommendation:** The backend M7 workflow is ready for HackATL demonstration. The browser demo should be rehearsed manually with the full local stack before the event.
