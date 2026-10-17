# M7 Demo Rehearsal Guide

This document provides the exact commands and UI actions needed to reproduce the working M7 demo.

## Prerequisites

Ensure the following are available:
- Python 3.12+
- UV package manager
- Node.js (for frontend)
- Access to `examples/payments-lite` target

## Commands to Run M7 Backend Validation

### 1. Run the Automated M7 Test

```bash
python3 scripts/devin_qa/verify_m7_demo.py
```

This executes the full M7 chain automatically:
- Starts embedded PostgreSQL
- Runs migrations
- Executes signed push workflow
- Validates all seven agents
- Verifies independent verification
- Records regressions
- Validates audit trail

### 2. Manual M7 Test (If Automated Fails)

```bash
# Start embedded database
cd backend
uv run python -m backend.devdb

# Run M7 test with proper PYTHONPATH
cd ..
PYTHONPATH=backend:shared:security-agents:code-review:code-intelligence:monitoring:standards \
TEST_DATABASE_URL=$(cd backend && uv run python -m backend.devdb) \
uv run pytest -q backend/tests/test_m7_push_to_regression.py -s

# Stop database
cd backend
uv run python -m backend.devdb --stop
```

## Manual Full-Stack Demo

To demonstrate the complete system including frontend:

### 1. Start the Full Local Stack

```bash
# Start embedded database
make dev-db

# Run migrations
make migrate

# Start API and worker
make dev
```

This starts:
- PostgreSQL (embedded)
- FastAPI backend on http://localhost:8000
- Worker process
- SSE streaming

### 2. Run Browser E2E Test

In a separate terminal:

```bash
cd frontend
../.venv/bin/python tests/e2e/stack.py
```

This runs the Playwright browser journey through:
- Scope request and approval
- Assessment creation
- SSE timeline observation
- Remediation approval
- Seven-agent runs
- Evidence chain inspection
- Hash-checked diff verification
- Verify acceptance
- Monitoring event display

### 3. Manual UI Demo

1. Open browser to http://localhost:3000
2. Authenticate with dev mode (AUTH_DEV_LOGIN_ENABLED=true)
3. Create a project or select existing
4. Create a scope
5. Start an assessment
6. Observe SSE timeline
7. Review findings and evidence
8. Approve remediation
9. Observe verification results
10. Check monitoring events
11. Navigate to RL Defense Lab

## Clean Up

```bash
# Stop API and worker (Ctrl+C in terminal where make dev ran)

# Stop database
make stop-db
```

## Verification Checklist

Before presenting the demo, verify:

- [ ] Backend responds to health checks: `curl http://localhost:8000/healthz`
- [ ] Frontend loads: `curl http://localhost:3000`
- [ ] Database is running: `make dev-db` should start embedded PostgreSQL
- [ ] M7 test passes: `python3 scripts/devin_qa/verify_m7_demo.py`
- [ ] Payments-lite target is accessible
- [ ] MODEL_MODE is set to fake (no real API charges)

## Known Limitations

- Model turns use TEST-ONLY scripted transports (provider_mode=fake)
- No live-provider M7 run has been executed
- Default monitoring budget (150k tokens) is too small for full chain
- Browser E2E requires full local stack running
- GitHub App credentials not configured (manual trigger only)

## Success Indicators

The demo is successful when:
- ✅ M7 backend test passes (full chain executes)
- ✅ Browser E2E test passes (12 scenarios)
- ✅ Findings are generated with evidence
- ✅ Remediation produces candidate patches
- ✅ Independent verification accepts patches
- ✅ Regressions are recorded
- ✅ Audit trail is intact
- ✅ Frontend displays actual results
- ✅ RL simulation runs with honest labeling
