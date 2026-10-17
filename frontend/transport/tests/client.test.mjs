import { test } from 'node:test';
import assert from 'node:assert/strict';
import { ApiClient, ApiError, ProtocolError } from '../dist/frontend/transport/src/index.js';
import { readJson } from '../dist/frontend/transport/src/client.js';
const me = { user: { id: 'usr_12345678', github_login: 'test', display_name: null, created_at: '2026-10-17T03:00:00Z' }, memberships: [], csrf_token: 'test-csrf' };
const json = (body, status = 200) => Response.json(body, { status });

test('session cookie mode and CSRF; mutations are explicit and never retried', async () => {
  const calls = [];
  const client = new ApiClient({ baseUrl: 'http://localhost/api/v1', fetch: async (url, init) => {
    calls.push({ url, init });
    return calls.length === 1 ? json(me) : json({ error: { code: 'FORBIDDEN', message: 'Denied', details: {}, request_id: null } }, 403);
  }});
  await assert.rejects(client.approveScope('scp_12345678'), ProtocolError);
  assert.equal(calls.length, 0);
  assert.deepEqual(await client.session(), me);
  await assert.rejects(client.approveScope('scp_12345678'), e => e instanceof ApiError && e.status === 403);
  assert.equal(calls.length, 2);
  assert.equal(calls[1].init.credentials, 'include');
  assert.equal(calls[1].init.headers.get('X-CSRF-Token'), 'test-csrf');
  assert.equal(calls[1].init.method, 'POST');
});

test('canonical response schema rejects wrong IDs, unknown fields and absent fields', async () => {
  for (const invalid of [{ ...me, extra: true }, { ...me, csrf_token: undefined }, { ...me, user: { ...me.user, id: 'bad' } }]) {
    const client = new ApiClient({ baseUrl: 'http://localhost/api/v1', fetch: async () => json(invalid) });
    await assert.rejects(client.session(), ProtocolError);
    await assert.rejects(client.approveScope('scp_12345678'), ProtocolError);
  }
});

test('idempotency key required and forwarded exactly once; abort forwarded', async () => {
  let last;
  const client = new ApiClient({ baseUrl: 'http://localhost/api/v1', fetch: async (url, init) => {
    last = init;
    if (url.endsWith('/me')) return json(me);
    return json({ error: { code: 'CONFLICT_STATE', message: 'Not ready', details: {}, request_id: 'req1' } }, 409);
  }});
  await client.session();
  await assert.rejects(client.startAssessment('prj_12345678', {}, ''), ProtocolError);
  const signal = new AbortController().signal;
  await assert.rejects(client.startAssessment('prj_12345678', {}, 'unique-action-1', { signal }), ApiError);
  assert.equal(last.headers.get('Idempotency-Key'), 'unique-action-1');
  assert.equal(last.signal, signal);
  await assert.rejects(client.project('../escape'), ProtocolError);
});

test('401 clears CSRF, login is opt-in, invalid content and large responses fail', async () => {
  let count = 0;
  const client = new ApiClient({ baseUrl: 'http://localhost/api/v1', fetch: async () => ++count === 1 ? json(me) : json({ error: { code: 'UNAUTHENTICATED', message: 'Expired', details: {}, request_id: null } }, 401) });
  await client.devLogin({ github_login: 'test', display_name: null });
  await assert.rejects(client.session(), ApiError);
  await assert.rejects(client.approveScope('scp_12345678'), ProtocolError);
  await assert.rejects(readJson(new Response('<html>')), ProtocolError);
  await assert.rejects(readJson(json({ too: 'large' }), 2), ProtocolError);
  for (const baseUrl of ['file:///tmp/api', 'http://secret:password@localhost', 'http://localhost?token=x']) {
    assert.throws(() => new ApiClient({ baseUrl }), ProtocolError);
  }
});
