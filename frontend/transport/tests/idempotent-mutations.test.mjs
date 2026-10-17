import { test } from 'node:test';
import assert from 'node:assert/strict';
import { ApiClient } from '../dist/frontend/transport/src/index.js';

const me = { user: { id: 'usr_12345678', github_login: 'test', display_name: null, created_at: '2026-10-17T03:00:00Z' }, memberships: [], csrf_token: 'csrf' };
const err = { error: { code: 'NOT_FOUND', message: 'x', details: {}, request_id: null } };

test('create/decide calls forward an optional Idempotency-Key and omit it when absent', async () => {
  const seen = [];
  const api = new ApiClient({ baseUrl: 'http://localhost/api/v1', fetch: async (url, init) => {
    if (String(url).endsWith('/me')) return Response.json(me);
    seen.push({ url: String(url), key: init.headers.get('Idempotency-Key') });
    return Response.json(err, { status: 404 });
  } });
  await api.session();
  const calls = [
    () => api.createProject({ name: 'p', org_id: null, settings: null }, { idempotencyKey: 'k-project' }),
    () => api.createScope('prj_12345678', {}, { idempotencyKey: 'k-scope' }),
    () => api.createIncident('prj_12345678', {}, { idempotencyKey: 'k-incident' }),
    () => api.actOnIncident('inc_12345678', {}, { idempotencyKey: 'k-action' }),
    () => api.decideApproval('apr_12345678', { decision: 'approved', reason: null }, { idempotencyKey: 'k-decision' }),
    () => api.createProject({ name: 'p', org_id: null, settings: null }),
  ];
  for (const call of calls) await assert.rejects(call());
  assert.deepEqual(seen.map(s => s.key), ['k-project', 'k-scope', 'k-incident', 'k-action', 'k-decision', null]);
});
