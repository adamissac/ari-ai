# Demo Recovery Runbook

This document provides exact operator instructions for what to do when the demonstration fails during HackATL.

## Quick Reference

| Scenario | Recovery Action | Owner |
|----------|----------------|-------|
| Backend not responding | Check `make dev-db` and restart with `make dev` | Demo Operator |
| Frontend not loading | Check `npm install` in frontend/ and restart | Demo Operator |
| Assessment stuck | Cancel assessment, check logs, retry | Demo Operator |
| SSE events not streaming | Refresh page, check backend logs | Demo Operator |
| LLM errors | Check ANTHROPIC_API_KEY, check quota | Demo Operator |
| Database errors | Restart embedded DB with `make stop-db && make dev-db` | Demo Operator |

## Pre-Demo Checklist

Before starting the demo, run:
```bash
python3 scripts/devin_qa/demo_preflight.py
```

All essential checks must pass. Review warnings.

## Common Failure Scenarios

### 1. Backend Not Responding

**Symptoms:**
- Frontend shows "API connection error"
- `http://localhost:8000/healthz` returns connection refused
- Assessment creation fails

**Recovery Steps:**
1. Check if backend is running: `ps aux | grep uvicorn`
2. If not running, start it:
   ```bash
   make dev-db
   make dev
   ```
3. Wait for `/readyz` to return 200
4. Check logs for errors

**Alternative:** Use Docker Compose:
```bash
docker compose up --build
```

### 2. Frontend Not Loading

**Symptoms:**
- Browser shows blank page or error
- `http://localhost:3000` returns 404 or connection refused

**Recovery Steps:**
1. Check if node_modules exists: `ls frontend/node_modules`
2. If missing, install dependencies:
   ```bash
   cd frontend
   npm install
   cd ..
   ```
3. Start frontend:
   ```bash
   cd frontend
   npm run dev
   ```
4. Check browser console for errors

### 3. Assessment Stuck

**Symptoms:**
- Assessment status remains "RUNNING" for > 2 minutes
- No SSE events arriving
- No evidence being generated

**Recovery Steps:**
1. Check backend logs: look for worker errors
2. Check if DATABASE_URL is set or embedded DB is running
3. Cancel stuck assessment via API or UI
4. Check if security-agents can import: `uv run python -c "import sys; sys.path.insert(0, 'security-agents'); import security_agents"`
5. Retry assessment with fresh state

### 4. SSE Events Not Streaming

**Symptoms:**
- Assessment status updates not appearing
- Frontend shows "Connecting..." indefinitely

**Recovery Steps:**
1. Refresh the browser page
2. Check backend logs for SSE connection errors
3. Verify `/api/v1/stream` endpoint is accessible
4. Check Last-Event-ID header handling

### 5. LLM Errors

**Symptoms:**
- Agent steps fail with "LLM error"
- Anthropic API timeout or rate limit
- Invalid model output errors

**Recovery Steps:**
1. Check ANTHROPIC_API_KEY is set and valid
2. Check API quota: https://console.anthropic.com/settings/limits
3. Reduce model turns if quota low
4. If rate limited, wait and retry
5. Check model ID is correct (claude-opus-5-5 or configured value)

### 6. Database Errors

**Symptoms:**
- "Database connection failed" errors
- Migration errors
- Assessment creation fails with DB error

**Recovery Steps:**
1. Stop embedded DB: `make stop-db`
2. Restart embedded DB: `make dev-db`
3. Run migrations: `make migrate`
4. If using Docker Compose: `docker compose restart db migrate`
5. Check DATABASE_URL environment variable

### 7. Browser Refresh During Active Assessment

**Symptoms:**
- User refreshed page during assessment
- Assessment appears lost or status unclear

**Recovery Steps:**
1. Navigate to Assessments page
2. Find the assessment by ID or timestamp
3. Status should reflect actual backend state
4. If disconnected, SSE will reconnect automatically
5. Evidence should still be accessible

### 8. Artifact Store Errors

**Symptoms:**
- "Artifact not found" errors
- Patch diff not loading
- Evidence artifacts missing

**Recovery Steps:**
1. Check ARTIFACT_STORE_URI configuration
2. If using local FS, check `/data/artifacts` directory exists
3. If using Docker Compose, check volume mount
4. Verify artifact permissions
5. Check backend logs for artifact storage errors

## Manual Assessment Trigger (Fallback)

If GitHub webhooks are not configured, trigger assessments manually:

1. Create project via UI
2. Connect repository
3. Click "Start Assessment" button
4. Select commit SHA
5. Wait for completion

## Offline Demo Mode

If internet connectivity is unreliable:

1. Use embedded PostgreSQL (no Docker required)
2. Use FakeLLM mode for all agents (configured in backend)
3. Pre-generate transport types: `make contracts`
4. Have a backup assessment with evidence ready to show

## Post-Demo Diagnostics

If demo fails, collect diagnostics:

```bash
python3 scripts/devin_qa/demo_diagnostics.py > demo_diagnostics_$(date +%Y%m%d_%H%M%S).txt
```

This will collect:
- Runtime versions
- Backend/frontend health status
- Recent error logs (redacted)
- Configuration status
- Assessment IDs and states

**Do not share diagnostics with secrets.** Review before sharing.

## Emergency Stop

If something goes critically wrong:

1. Stop all services:
   ```bash
   make stop-db
   # Kill backend/frontend processes
   pkill -f uvicorn
   pkill -f "npm run dev"
   ```
2. Reset database (only if acceptable):
   ```bash
   make stop-db
   rm -rf .venv/pgdata
   make dev-db
   make migrate
   ```
3. Restart with `make dev`

## Contact Information

- **Platform Issues:** Backend/Monitoring (Srihith)
- **Security Agent Issues:** Security Agents (Alan)
- **Code Intelligence Issues:** Code Intelligence (Sarosh)
- **Code Review Issues:** Code Review (Sai)
- **Frontend Issues:** Frontend (Vihaan)
- **RL Defense Issues:** RL Defense (Adam)

## Escalation Path

1. First attempt: Follow recovery steps above
2. Second attempt: Contact relevant subsystem owner
3. Third attempt: Switch to offline/demo mode with pre-recorded evidence
4. Last resort: Explain technical issue honestly and show architecture docs

## Success Indicators

Demo is successful when:
- ✅ Backend responds to health checks
- ✅ Frontend loads and navigates
- ✅ Assessment can be created and progresses
- ✅ At least one finding is generated with evidence
- ✅ Patch candidate can be viewed
- ✅ Verification status is clear
- ✅ RL simulation can be accessed and shows honest labeling

**Honesty rule:** Never claim a feature works if it fails during the demo. Explain what failed and why.
