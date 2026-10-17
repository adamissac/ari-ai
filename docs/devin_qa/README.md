# Devin QA Integration Tests

This directory contains isolated QA integration tests and demo reliability tools for the hackatl-agentic-security project.

## Purpose

These tests are designed to:
- Verify the security assessment workflow end-to-end
- Verify the simulated RL defense environment
- Verify frontend/backend integration
- Provide a demo preflight checker
- Report on overall readiness for HackATL demonstration

## Test Scripts

### 1. `preflight_check.py`
Checks whether the demonstration environment is ready. Performs read-only checks against the system.

**Usage:**
```bash
python scripts/devin_qa/preflight_check.py
```

**Checks:**
- Environment (Python, UV, Node.js, Docker)
- Dependencies (required files, uv.lock)
- Backend (import, API health)
- Frontend (build, server)
- Database (.env configuration)
- Configuration (API keys, secrets)

### 2. `test_security_workflow.py`
Tests the security assessment workflow against the authorized payments-lite lab target.

**Usage:**
```bash
python scripts/devin_qa/test_security_workflow.py
```

**Tests:**
- Backend startup
- Shared contracts validity
- Backend test suite
- Security agents test suite
- payments-lite target structure
- Code intelligence tests
- Code review tests
- Standards catalog validity

### 3. `test_rl_workflow.py`
Tests the simulated Double DQN cybersecurity defense environment.

**Usage:**
```bash
python scripts/devin_qa/test_rl_workflow.py
```

**Tests:**
- RL environment structure
- RL imports
- RL test suite
- RL contract types
- RL backend integration
- RL honesty labeling

### 4. `test_frontend_integration.py`
Tests the integration between the frontend and backend API.

**Usage:**
```bash
python scripts/devin_qa/test_frontend_integration.py
```

**Tests:**
- Frontend structure
- Frontend dependencies
- TypeScript compilation
- Frontend linting
- Frontend unit tests
- Transport type generation

### 5. `run_all_qa_tests.py`
Master runner that executes all QA test suites in sequence.

**Usage:**
```bash
python scripts/devin_qa/run_all_qa_tests.py
```

## Running the Preflight Checker

Before a demonstration, run the preflight checker to verify the environment:

```bash
python scripts/devin_qa/preflight_check.py
```

This will report:
- **PASS**: Check succeeded
- **FAIL**: Check failed (must fix before demo)
- **WARN**: Check succeeded with limitations (review before demo)

## Scope and Boundaries

These tests:
- Are **non-invasive** and do not modify application functionality
- Run in isolated directories (`scripts/devin_qa/`)
- Use only repository-approved targets (payments-lite)
- Do not modify `frontend/src/**`, `backend/app/**`, `rl/**`, `lab/**`, `shared/**`, or existing test files
- Do not change authentication, security logic, or RL models
- Respect the ownership boundaries defined in `coordination/OWNERSHIP.md`

## Ownership

These QA tests are owned by the Devin QA engineer and are separate from the six developer implementation lanes:
- Adam (RL)
- Alan (Security agents)
- Sarosh (Code intelligence)
- Sai (Code review)
- Vihaan (Frontend)
- Srihith (Backend and monitoring)

## Reporting

Test results and readiness reports are documented in `docs/devin_qa/READINESS_REPORT.md`.
