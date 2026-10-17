import { test } from 'node:test';
import assert from 'node:assert/strict';
import { ApiClient, ApiError, watchAssessment } from '../dist/frontend/transport/src/index.js';
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
    const cancelled = await alice.fetch(`${baseUrl}/assessments/${assessment.id}/cancel`, { method: 'POST', headers: { 'X-CSRF-Token': me.csrf_token } });
    assert.equal(cancelled.status, 200);
    assert.equal((await cancelled.json()).cancelled, true);
    assert.equal((await alice.api.assessment(assessment.id)).assessment.state, 'CANCELLED');
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
    console.log(JSON.stringify({ backend: 'real FastAPI + PostgreSQL', provider_calls: 0, assessment_state: 'CANCELLED', persisted_events: events.length, resumed_sequences: resumed.map(e => e.seq) }));
  });
});
