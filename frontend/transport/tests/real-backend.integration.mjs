import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { ApiClient, ApiError, ProtocolError, watchAssessment } from '../dist/frontend/transport/src/index.js';
const baseUrl = process.env.TRANSPORT_TEST_API;
if (!baseUrl) throw new Error('Run through real_backend.py (isolated database required)');
// Node has no browser cookie store. This test-only jar models credentialed fetch.
function browserSession() {
  let cookie = '';
  const requests = [];
  const fetch = async (url, init = {}) => {
    const headers = new Headers(init.headers);
    if (cookie) headers.set('Cookie', cookie);
    requests.push({ url, headers: new Headers(headers) });
    const response = await globalThis.fetch(url, { ...init, headers });
    const set = response.headers.get('set-cookie');
    if (set) cookie = set.split(';')[0];
    return response;
  };
  return { api: new ApiClient({ baseUrl, fetch }), fetch, requests };
}
const collect = async gen => { const result = []; for await (const v of gen) result.push(v); return result; };

test('real FastAPI/PostgreSQL browser transport', async t => {
  const alice = browserSession(), bob = browserSession(), eve = browserSession();
  let me, project, repo, scope, assessment;
  await t.test('cookie sessions, persisted project, CSRF and tenant denial', async () => {
    me = await alice.api.devLogin({ github_login: 'transport-alice', display_name: null });
    await bob.api.devLogin({ github_login: 'transport-bob', display_name: null });
    await eve.api.devLogin({ github_login: 'transport-eve', display_name: null });
    assert.equal((await alice.api.session()).user.id, me.user.id);
    project = await alice.api.createProject({ name: 'Transport integration', org_id: null, settings: null });
    assert.equal((await bob.api.project(project.id)).id, project.id);
    assert.ok((await alice.api.projects()).items.some(p => p.id === project.id));
    await assert.rejects(eve.api.project(project.id), e => e instanceof ApiError && e.status === 404);
    const missingCsrf = await alice.fetch(`${baseUrl}/projects`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: 'Rejected' }) });
    assert.equal(missingCsrf.status, 403);
    assert.equal((await missingCsrf.json()).error.code, 'CSRF_FAILED');
  });
  await t.test('real scope approval, idempotent assessment creation and cancellation', async () => {
    repo = await alice.api.connectRepository(project.id, { full_name: 'owned/transport-fixture', default_branch: 'main', installation_id: null });
    scope = await alice.api.createScope(project.id, { name: 'Transport-only scope', targets: [{ kind: 'sandbox_build', repo_id: repo.id, build_recipe_ref: 'examples/payments-lite/sandbox.yaml', exposed_ports: [8080] }], allowed_check_categories: ['authorization.ownership'], expires_at: new Date(Date.now() + 3600000).toISOString(), notes: null });
    // Requesters cannot approve their own scope; the client surfaces backend denial.
    await assert.rejects(alice.api.approveScope(scope.id), e => e instanceof ApiError && e.status === 403);
    scope = await bob.api.approveScope(scope.id);
    const body = { scope_id: scope.id, repo_id: repo.id, commit_sha: 'b'.repeat(40), snapshot_id: null, budget: null };
    assessment = await alice.api.startAssessment(project.id, body, 'transport-action-1');
    assert.equal((await alice.api.startAssessment(project.id, body, 'transport-action-1')).id, assessment.id);
    await assert.rejects(alice.api.startAssessment(project.id, { ...body, commit_sha: 'c'.repeat(40) }, 'transport-action-1'), e => e instanceof ApiError && e.status === 409);
    const controller = new AbortController();
    const live = watchAssessment(alice.api, assessment.id, { signal: controller.signal });
    assert.equal((await live.next()).value.seq, 1);
    controller.abort();
    await assert.rejects(live.next(), e => e.name === 'AbortError');
    const cancelled = await alice.fetch(`${baseUrl}/assessments/${assessment.id}/cancel`, { method: 'POST', headers: { 'X-CSRF-Token': me.csrf_token } });
    assert.equal(cancelled.status, 200);
    assert.equal((await cancelled.json()).cancelled, true);
    assert.equal((await alice.api.assessment(assessment.id)).assessment.state, 'CANCELLED');
    assert.equal((await alice.api.assessments(project.id)).items[0].id, assessment.id);
    assert.equal((await alice.api.repositories(project.id)).items[0].id, repo.id);
    assert.equal((await alice.api.scopes(project.id)).items[0].id, scope.id);
    assert.deepEqual((await alice.api.agentRuns(assessment.id)).items, []);
    // Report and snapshot list decode as the shared contracts against the real API.
    const report = await alice.api.report(assessment.id);
    assert.equal(report.source, 'persisted records');
    assert.equal(report.assessment.id, assessment.id);
    const snap = await alice.api.createSnapshot(repo.id, { commit_sha: 'b'.repeat(40) }, 'transport-snapshot-1');
    const snaps = await alice.api.snapshots(repo.id, { limit: 5 });
    assert.equal(snaps.items[0].id, snap.id);
    assert.deepEqual((await alice.api.snapshots(repo.id, { status: 'ready' })).items, []);
    await assert.rejects(eve.api.snapshots(repo.id), e => e instanceof ApiError && e.status === 404);
    assert.deepEqual((await alice.api.findings(project.id)).items, []);
    assert.ok((await alice.api.approvals(project.id)).items.length >= 1);
  });
  await t.test('lost acceptance response retries one persisted assessment/job and new actions recover', async () => {
    const body = { scope_id: scope.id, repo_id: repo.id, commit_sha: 'd'.repeat(40), snapshot_id: null, budget: null };
    const accepted = [];
    let loseResponse = true;
    const lossy = new ApiClient({ baseUrl, fetch: async (url, init) => {
      const response = await alice.fetch(url, init);
      if (init?.method === 'POST' && url.endsWith('/assessments')) {
        accepted.push(await response.clone().json());
        if (loseResponse) {
          loseResponse = false;
          await response.body?.cancel();
          throw new DOMException('Acceptance response lost after server commit', 'AbortError');
        }
      }
      return response;
    } });
    await lossy.session();
    const count = (await alice.api.assessments(project.id)).items.length;
    await assert.rejects(lossy.startAssessment(project.id, body, 'lost-response-action'), e => e.name === 'AbortError');
    const retried = await lossy.startAssessment(project.id, body, 'lost-response-action');
    assert.equal(retried.id, accepted[0].assessment.id);
    assert.equal(accepted[1].job_id, accepted[0].job_id);
    assert.equal((await alice.api.assessments(project.id)).items.length, count + 1);
    const job = await alice.fetch(`${baseUrl}/jobs/${accepted[0].job_id}`);
    assert.equal(job.status, 200, await job.clone().text());
    const persisted = await job.json();
    assert.equal(persisted.id, accepted[0].job_id);
    assert.equal(persisted.kind, 'run_assessment');
    assert.equal(persisted.status, 'queued');
    assert.equal((await eve.fetch(`${baseUrl}/jobs/${persisted.id}`)).status, 404);
    await assert.rejects(alice.api.startAssessment(project.id, { ...body, commit_sha: 'e'.repeat(40) }, 'lost-response-action'), e => e instanceof ApiError && e.status === 409 && e.error.code === 'IDEMPOTENCY_CONFLICT');
    const other = await alice.api.createProject({ name: 'Retry URL isolation', org_id: null, settings: null });
    await assert.rejects(alice.api.startAssessment(other.id, body, 'lost-response-action'), e => e instanceof ApiError && e.status === 409 && e.error.code === 'IDEMPOTENCY_CONFLICT');
    assert.deepEqual((await alice.api.assessments(other.id)).items, []);
    const fresh = await alice.api.startAssessment(project.id, { ...body, commit_sha: 'e'.repeat(40) }, 'fresh-action');
    assert.notEqual(fresh.id, retried.id);
    assert.equal((await alice.api.assessments(project.id)).items.length, count + 2);
    for (const id of [retried.id, fresh.id]) {
      await alice.api.cancelAssessment(id);
      assert.equal((await alice.api.assessment(id)).assessment.state, 'CANCELLED');
    }
  });
  await t.test('stored artifact bytes verify over HTTP and corrupt downloads are rejected', async () => {
    const id = process.env.TRANSPORT_TEST_ARTIFACT;
    assert.ok(id, 'the isolated harness must create the owned artifact fixture');
    const raw = await alice.fetch(`${baseUrl}/artifacts/${id}`);
    assert.equal(raw.status, 200);
    const bytes = Buffer.from(await raw.arrayBuffer());
    assert.equal(createHash('sha256').update(bytes).digest('hex'), raw.headers.get('x-artifact-sha256'));
    const stored = await alice.api.artifactText(id);
    assert.equal(stored.hashVerified, true);
    assert.equal(stored.text, bytes.toString('utf8'));
    assert.ok(stored.text.includes('Δ regression'));
    assert.ok(!stored.text.includes('x'.repeat(40)), 'credential-shaped fixture must be redacted');
    await assert.rejects(eve.api.artifactText(id), e => e instanceof ApiError && e.status === 404);
    const corrupt = new ApiClient({ baseUrl, fetch: async (url, init) => {
      const response = await alice.fetch(url, init);
      return new Response((await response.text()) + 'changed in transit', { status: response.status, headers: response.headers });
    } });
    await assert.rejects(corrupt.artifactText(id), e => e instanceof ProtocolError && e.message === 'Artifact hash mismatch');
  });
  await t.test('persisted SSE, Last-Event-ID resume, terminal confirmation and scoped denial', async () => {
    const events = await collect(watchAssessment(alice.api, assessment.id, { maxReconnects: 0 }));
    assert.ok(events.length >= 2);
    assert.deepEqual(events.map(e => e.seq), Array.from({ length: events.length }, (_, i) => i + 1));
    assert.equal(events.at(-1).state, 'CANCELLED');
    const middle = events[0].seq;
    const resumed = await collect(watchAssessment(alice.api, assessment.id, { after: middle, maxReconnects: 0 }));
    assert.deepEqual(resumed.map(e => e.seq), events.filter(e => e.seq > middle).map(e => e.seq));
    const last = events.at(-1).seq;
    const states = [];
    assert.deepEqual(await collect(watchAssessment(alice.api, assessment.id, { after: last, maxReconnects: 0, onConnection: s => states.push(s) })), []);
    assert.equal(states.at(-1), 'completed'); // persisted CANCELLED, not success
    const request = alice.requests.find(r => r.url.includes(`/events?after=${last}`));
    assert.equal(request.headers.get('Last-Event-ID'), String(last));
    await assert.rejects(collect(watchAssessment(eve.api, assessment.id, { maxReconnects: 0 })), e => e instanceof ApiError && e.status === 404);
    await eve.api.logout();
    await assert.rejects(eve.api.session(), e => e instanceof ApiError && e.status === 401);
    console.log(JSON.stringify({ backend: 'real FastAPI + PostgreSQL', provider_calls: 0, assessment_state: 'CANCELLED', persisted_events: events.length, resumed_sequences: resumed.map(e => e.seq) }));
  });
});
