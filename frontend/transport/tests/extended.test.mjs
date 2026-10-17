import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { ApiClient, ApiError, ProtocolError } from '../dist/frontend/transport/src/index.js';

const json = (body, status = 200) => Response.json(body, { status });
const me = { user: { id: 'usr_12345678', github_login: 'test', display_name: null, created_at: '2026-10-17T03:00:00Z' }, memberships: [], csrf_token: 'test-csrf' };
const evidence = { kind: 'source_span', path: 'app.py', commit_sha: 'a'.repeat(40), span: { start_line: 1, end_line: 2, start_col: null, end_col: null }, symbol: null, artifact_id: null, sha256: null, provenance: 'agent:scout', note: null };
const finding = {
  id: 'fnd_12345678', assessment_id: 'asm_12345678', snapshot_id: null, commit_sha: 'a'.repeat(40), kind: 'security',
  title: 'Cross-tenant invoice read', status: 'hypothesis', severity: null, subject_refs: [], expectation_ids: [],
  evidence: [evidence], confidence: 0.6, produced_by_run_id: null, history: [], standards: null, created_at: '2026-10-17T03:00:00Z', updated_at: '2026-10-17T03:00:00Z',
};
const hypothesis = { id: 'hyp_12345678', finding_id: 'fnd_12345678', weakness_class: 'CWE-639', rationale: 'Tenant check removed', cited_spans: [evidence], expectation_ids: [], confidence: 0.6, suggested_check_category: 'ownership' };
const client = (handler) => new ApiClient({ baseUrl: 'http://localhost/api/v1', fetch: async (url, init) => handler(String(url), init) });

test('finding detail validates the finding and each typed evidence record', async () => {
  const ok = client(() => json({ finding, records: [{ type: 'hypothesis', record: hypothesis }] }));
  const detail = await ok.finding('fnd_12345678');
  assert.equal(detail.records[0].type, 'hypothesis');
  assert.equal(detail.records[0].record.weakness_class, 'CWE-639');
  for (const body of [
    { finding, records: [{ type: 'mystery', record: hypothesis }] },
    { finding, records: [{ type: 'hypothesis', record: { ...hypothesis, extra: 1 } }] },
    { finding: { ...finding, status: 'definitely_fine' }, records: [] },
    { finding, records: [], extra: true },
  ]) {
    await assert.rejects(client(() => json(body)).finding('fnd_12345678'), ProtocolError);
  }
});

test('recommendation list keeps the backend simulation label and rejects other envelopes', async () => {
  const page = await client(() => json({ items: [], next_cursor: null, label: 'simulation-derived' })).defenseRecommendations('prj_12345678');
  assert.equal(page.label, 'simulation-derived');
  await assert.rejects(client(() => json({ items: [], next_cursor: null })).defenseRecommendations('prj_12345678'), ProtocolError);
  // A real cursor is accepted and passed back as ?cursor= (the list used to truncate at 50).
  let seen = '';
  const more = await client((url) => { seen = url; return json({ items: [], next_cursor: '2026-10-17T03:00:00+00:00|rec_1', label: 'x' }); })
    .defenseRecommendations('prj_12345678', { cursor: '2026-10-17T04:00:00+00:00|rec_9' });
  assert.equal(more.next_cursor, '2026-10-17T03:00:00+00:00|rec_1');
  assert.ok(seen.endsWith('/defense-recommendations?cursor=2026-10-17T04%3A00%3A00%2B00%3A00%7Crec_9'), seen);
  await assert.rejects(client(() => json({ items: [], next_cursor: 7, label: 'x' })).defenseRecommendations('prj_12345678'), ProtocolError);
});

test('artifact text is bounded and its declared SHA-256 must match the bytes', async () => {
  const diff = '--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-x\n+y\n';
  const sha = createHash('sha256').update(diff).digest('hex');
  const good = await client(() => new Response(diff, { headers: { 'content-type': 'text/x-diff', 'x-artifact-sha256': sha } })).artifactText('art_12345678');
  assert.equal(good.text, diff);
  assert.equal(good.hashVerified, true);
  await assert.rejects(client(() => new Response(diff, { headers: { 'x-artifact-sha256': '0'.repeat(64) } })).artifactText('art_12345678'), /hash mismatch/);
  await assert.rejects(client(() => new Response(diff)).artifactText('art_12345678', { maxBytes: 4 }), /size limit/);
  await assert.rejects(client(() => json({ error: { code: 'NOT_FOUND', message: 'gone', details: {}, request_id: null } }, 404)).artifactText('art_12345678'), ApiError);
});

test('cancel requires a session and validates the acknowledgement', async () => {
  const calls = [];
  const api = client((url, init) => {
    calls.push(init);
    return url.endsWith('/me') ? json(me) : json({ assessment_id: 'asm_12345678', cancelled: false, cancel_requested: true });
  });
  await assert.rejects(api.cancelAssessment('asm_12345678'), ProtocolError);
  await api.session();
  assert.deepEqual(await api.cancelAssessment('asm_12345678'), { assessment_id: 'asm_12345678', cancelled: false, cancel_requested: true });
  assert.equal(calls.at(-1).headers.get('X-CSRF-Token'), 'test-csrf');
  const wrong = client((url) => url.endsWith('/me') ? json(me) : json({ assessment_id: 'asm_other999', cancelled: true, cancel_requested: true }));
  await wrong.session();
  await assert.rejects(wrong.cancelAssessment('asm_12345678'), ProtocolError);
});

test('event log cursor is validated before any request', async () => {
  let called = false;
  const api = client(() => { called = true; return json({ items: [], next_cursor: null }); });
  assert.throws(() => api.eventsLog('asm_12345678', -1), ProtocolError);
  assert.equal(called, false);
  assert.deepEqual(await api.eventsLog('asm_12345678', 3), { items: [], next_cursor: null });
});

test('snapshot list builds its query and validates each Snapshot', async () => {
  const snap = { id: 'snp_12345678', repo_id: 'rep_12345678', commit_sha: 'a'.repeat(40), status: 'ready', index_version: 'python-ast-ts/0.2.0', base_snapshot_id: null, stats: { files: 3, symbols: 9, call_edges: 4, entry_points: 2, expectations: 5 }, error_message: null, created_at: '2026-10-17T03:00:00Z', completed_at: '2026-10-17T03:00:05Z' };
  let seen = '';
  const api = client((url) => { seen = url; return json({ items: [snap], next_cursor: null }); });
  const page = await api.snapshots('rep_12345678', { status: 'ready', limit: 5, cursor: 'snp_99999999' });
  assert.equal(page.items[0].status, 'ready');
  assert.equal(seen, 'http://localhost/api/v1/repositories/rep_12345678/snapshots?status=ready&limit=5&cursor=snp_99999999');
  await api.snapshots('rep_12345678');
  assert.equal(seen, 'http://localhost/api/v1/repositories/rep_12345678/snapshots');
  await assert.rejects(client(() => json({ items: [{ ...snap, status: 'bogus' }], next_cursor: null })).snapshots('rep_12345678'), ProtocolError);
});

test('assessment report is decoded as the shared AssessmentReport', async () => {
  const bad = { assessment: {}, agent_runs: [], findings: [], generated_at: '2026-10-17T03:00:00Z', source: 'persisted records', standards: { classification_only: true, findings: [], hardening: [], unscored_reason: 'x' } };
  await assert.rejects(client(() => json(bad)).report('asm_12345678'), ProtocolError);
  await assert.rejects(client(() => json({ ...bad, source: 'generated prose' })).report('asm_12345678'), ProtocolError);
});
