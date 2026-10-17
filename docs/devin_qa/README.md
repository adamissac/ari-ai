# QA Test Suite for HackATL Demo Reliability

This directory contains independent QA infrastructure for validating the hackatl-agentic-security platform for HackATL demonstration readiness.

## Important Note on Test Status

**Previous Phase 2 Status:** Tests were created but not executed. Module imports and file existence checks were reported as PASS, but this did not prove end-to-end functionality.

**Current Phase 3 Status:** Tests now use a shared result schema with proper PASS/FAIL/SKIP outcomes. Tests are executed and provide genuine evidence. A SKIP status never counts as PASS.

## Test Scripts

### Phase 2 Scripts (Superficial - Refactored for Accuracy)

These scripts check structure and imports but do not prove end-to-end functionality:

- `preflight_check.py` - Environment readiness (refactored to use shared schema)
- `test_security_workflow.py` - Security assessment workflow (module imports)
- `test_rl_workflow.py` - RL defense simulation (module imports)
- `test_frontend_integration.py` - Frontend/backend integration (file structure)
- `run_all_qa_tests.py` - Master runner for Phase 2 scripts

### Phase 3 Scripts (Genuine End-to-End Verification)

These scripts execute real processes and provide genuine evidence:

- `shared_test_schema.py` - Shared result schema (TestResult, TestSuite, TestStatus)
- `verify_demo.py` - Genuine end-to-end demo verification with local stack
- `test_failure_scenarios.py` - Failure injection and resilience testing

### Demo Toolkit

- `demo_preflight.py` - One-command demo preflight checker (distinguishes essential vs optional)
- `demo_diagnostics.py` - Post-failure diagnostic collection (redacted)
- `DEMO_RECOVERY_RUNBOOK.md` - Operator instructions for demo failures

## Running Tests

### Run All Phase 2 Tests (Superficial)

```bash
python3 scripts/devin_qa/run_all_qa_tests.py
```

### Run Genuine End-to-End Verification

```bash
python3 scripts/devin_qa/verify_demo.py
```

This will:
- Start embedded PostgreSQL
- Run migrations
- Attempt to start API server and worker
- Report genuine executed evidence
- Save JSON report to `devin_qa_report.json`

### Run Demo Preflight

```bash
python3 scripts/devin_qa/demo_preflight.py
```

### Collect Diagnostics

```bash
python3 scripts/devin_qa/demo_diagnostics.py > diagnostics.txt
```

## Test Result Schema

All tests use the shared schema from `shared_test_schema.py`:

- **PASS**: Required functional behavior was executed and verified
- **FAIL**: Required behavior was executed and produced incorrect result
- **SKIP/BLOCKED**: Behavior was not executed because a prerequisite was missing

The schema provides:
- Check name
- Expected result
- Actual result
- Elapsed time
- Status
- Prerequisites
- Evidence
- Error message
- File location and line number

## Current Verification Status

As of 2026-10-17 (Phase 3):

### Verified (PASS)
- Python and UV runtime availability
- Embedded PostgreSQL startup
- Database migrations
- Module imports for all subsystems
- File structure and dependency files
- Shared contracts import
- Standards catalog validation

### Blocked (SKIP)
- API server startup (process hangs during uvicorn startup)
- Worker startup (process hangs during startup)
- Full assessment workflow (requires API and worker)

### Not Verified
- End-to-end assessment lifecycle (blocked by API/worker)
- Frontend/browser integration (requires running services)
- Real failure injection (requires running services)

## Demo Readiness Conclusion

**Status:** NOT FULLY VERIFIED

The system can demonstrate readiness at the structural level (all modules import, database starts, migrations run), but genuine end-to-end assessment workflow cannot be verified because:

1. API server process hangs during startup (uvicorn blocking issue)
2. Worker process hangs during startup
3. These blockers prevent executing the full assessment workflow

**Recommendation:** The backend owner (Srihith) should investigate the uvicorn and worker startup blocking issues before genuine end-to-end verification can proceed.

**Mitigation:** For HackATL demo preparation, use the structural checks (all PASS) and manual testing of the API/worker startup with `make dev` command from the repository root.

## Reproducible Bugs

1. **API Server Startup Block**
   - Location: `uvicorn backend.main:app --reload --port 8000`
   - Symptoms: Process hangs, no output, blocks indefinitely
   - Owner: Srihith (backend)
   - Evidence: `verify_demo.py` attempts to start API and times out

2. **Worker Startup Block**
   - Location: `hackatl-worker` or `backend.worker.main()`
   - Symptoms: Process hangs, no output, blocks indefinitely
   - Owner: Srihith (backend)
   - Evidence: `verify_demo.py` attempts to start worker and times out

## Blocking Prerequisites

- None for structural checks (all PASS)
- API/worker startup blocking end-to-end verification (requires investigation)

## References

- Main README report: `docs/devin_qa/READINESS_REPORT.md`
- Recovery runbook: `docs/devin_qa/DEMO_RECOVERY_RUNBOOK.md`
- Repository: https://github.com/adamissac/hackatl-agentic-security
- Branch: `devin/demo-reliability`
- PR: #94
