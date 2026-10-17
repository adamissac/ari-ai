import { test } from 'node:test';
import assert from 'node:assert/strict';
import { ApiClient, ApiError, ProtocolError } from '../dist/frontend/transport/src/index.js';

const me = { user: { id: 'usr_12345678', github_login: 'test', display_name: null, created_at: '2026-10-17T03:00:00Z' }, memberships: [], csrf_token: 'test-csrf' };
const json = (body, status = 200) => Response.json(body, { status });
const expectation = {
  id: 'exp_12345678', snapshot_id: 'snp_12345678', subject_ref: 'GET /payments/{payment_id}', kind: 'authorization',
  statement: 'A customer can only read their own payments.', origin: 'extracted', confidence: 0.55, status: 'inferred',
  data_sensitivity: null,
  sources: [{ kind: 'code_span', ref: 'src/app.py', path: 'src/app.py', start_line: 10, end_line: 12, sha256: null, note: null }],
};
const decision = {
  status: 'confirmed', reason: 'Product owner confirmed', expected_revision: 0, snapshot_ref: null,
  expectation_id: 'exp_12345678', revision: 1, decided_by: 'usr_12345678', decided_at: '2026-10-17T03:00:00Z',
};

function client(handler) {
  const calls = [];
  const c = new ApiClient({ baseUrl: 'http://localhost/api/v1', fetch: async (url, init) => {
    calls.push({ url, init });
    if (url.endsWith('/me')) return json(me);
    return handler(url, init);
  }});
  return { c, calls };
}

test('expectations list maps cursor to offset and validates page shape', async () => {
  const { c, calls } = client(() => json({ items: [], next_cursor: null }));
  await c.expectations('snp_12345678', { limit: 50, cursor: '100', subject: 'GET /x' });
  const url = new URL(calls[0].url);
  assert.equal(url.pathname, '/api/v1/snapshots/snp_12345678/expectations');
  assert.equal(url.searchParams.get('offset'), '100');
  assert.equal(url.searchParams.get('limit'), '50');
  assert.equal(url.searchParams.get('subject'), 'GET /x');
  assert.throws(() => c.expectations('snp_12345678', { cursor: 'abc' }), ProtocolError);
  assert.throws(() => c.expectations('snp_12345678', { limit: 0 }), ProtocolError);
  assert.throws(() => c.expectations('../x'), ProtocolError);
});

test('decideExpectation is a CSRF-protected PATCH and surfaces 409 conflicts', async () => {
  const { c, calls } = client(() => json({ error: { code: 'CONFLICT_STATE', message: 'stale revision', details: {}, request_id: null } }, 409));
  const body = { status: 'confirmed', reason: 'Product owner confirmed', expected_revision: 0 };
  await assert.rejects(c.decideExpectation('snp_12345678', 'exp_12345678', body), ProtocolError);
  assert.equal(calls.length, 0);
  await c.session();
  await assert.rejects(c.decideExpectation('snp_12345678', 'exp_12345678', body), e => e instanceof ApiError && e.status === 409);
  const last = calls.at(-1);
  assert.equal(last.init.method, 'PATCH');
  assert.equal(last.init.headers.get('X-CSRF-Token'), 'test-csrf');
  assert.deepEqual(JSON.parse(last.init.body), body);
});

test('updateProject uses PATCH; non-mutating reads stay GET', async () => {
  const { c, calls } = client((url, init) => json({ error: { code: 'FORBIDDEN', message: 'owner only', details: {}, request_id: null } }, 403));
  await c.session();
  await assert.rejects(c.updateProject('prj_12345678', { name: 'x', settings: null }), e => e instanceof ApiError && e.status === 403);
  assert.equal(calls.at(-1).init.method, 'PATCH');
  await assert.rejects(c.expectationDecisions('snp_12345678', 'exp_12345678'), ApiError);
  assert.equal(calls.at(-1).init.method, 'GET');
});

test('BehavioralExpectation responses are schema-validated', async () => {
  const { c } = client(() => json({ items: [{ ...expectation, extra: 1 }], next_cursor: null }));
  await assert.rejects(c.expectations('snp_12345678'), ProtocolError);
  void decision;
});
