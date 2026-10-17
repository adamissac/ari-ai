import { test } from 'node:test';
import assert from 'node:assert/strict';
import { ApiClient, ApiError, ProtocolError, watchAssessment } from '../dist/frontend/transport/src/index.js';
import { frames } from '../dist/frontend/transport/src/sse.js';
const asm = 'asm_12345678';
const event = (seq, extra = {}) => ({ seq, assessment_id: asm, type: 'assessment.progress', state: null, agent: null, agent_run_id: null, finding_id: null, approval_id: null, message: 'working', data: {}, at: '2026-10-17T03:00:00Z', ...extra });
const wire = e => `id: ${e.seq}\nevent: ${e.type}\ndata: ${JSON.stringify(e)}\n\n`;
const bytes = text => new TextEncoder().encode(text);
const stream = (...chunks) => new ReadableStream({ start(c) { for (const chunk of chunks) c.enqueue(typeof chunk === 'string' ? bytes(chunk) : chunk); c.close(); } });
const response = text => new Response(stream(text), { headers: { 'Content-Type': 'text/event-stream' } });
const collect = async gen => { const out = []; for await (const v of gen) out.push(v); return out; };
const fast = { retryMs: 0, maxRetryMs: 0 };

test('SSE frames handle chunked Unicode, BOM, CRLF, comments, retry and multiline data', async () => {
  const encoded = bytes('\uFEFF: heartbeat\r\nretry: 10\r\n\r\nid: 1\revent: example\rdata: café\rdata: second\r\rdata: incomplete');
  const out = await collect(frames(stream(...Array.from(encoded, b => Uint8Array.of(b)))));
  assert.deepEqual(out, [{ id: '', event: '', data: '', retry: 10 }, { id: '1', event: 'example', data: 'café\nsecond' }]);
});

test('bounded records and malformed UTF-8 close the reader', async () => {
  await assert.rejects(collect(frames(stream('data: abcdefgh\n\n'), 4)), ProtocolError);
  await assert.rejects(collect(frames(stream(Uint8Array.of(0xff)))), ProtocolError);
});

test('reconnect sends last yielded cursor, suppresses replay, stops on terminal', async () => {
  const calls = [], states = [];
  let connections = 0;
  const api = new ApiClient({ baseUrl: 'http://localhost/api/v1', fetch: async (url, init) => {
    calls.push([url, init]);
    if (url.includes('/events?')) {
      if (++connections === 1) return new Response(new ReadableStream({ start(c) { c.enqueue(bytes(wire(event(1)))); }, pull(c) { c.error(new TypeError('Disconnected')); } }), { headers: { 'content-type': 'text/event-stream' } });
      return response(wire(event(1)) + wire(event(2, { type: 'assessment.completed', state: 'COMPLETED' })));
    }
    throw new Error('Unexpected request');
  }});
  const out = await collect(watchAssessment(api, asm, { ...fast, onConnection: s => states.push(s) }));
  assert.deepEqual(out.map(e => e.seq), [1, 2]);
  assert.equal(calls[1][1].headers['Last-Event-ID'], '1');
  assert.match(calls[1][0], /after=1$/);
  assert.equal(states.at(-1), 'completed');
});

test('invalid JSON, canonical enums and mismatched envelopes are fatal without reconnect', async () => {
  const good = event(1);
  for (const text of [wire({ ...good, state: 'SUCCESS' }), wire(good).replace('id: 1', 'id: 2'), wire({ ...good, assessment_id: 'asm_abcdefgh' }), 'id: 1\nevent: assessment.progress\ndata: {bad}\n\n', wire(good).replace('event: assessment.progress', 'event: forged')]) {
    let calls = 0;
    const api = new ApiClient({ baseUrl: 'http://localhost', fetch: async () => { calls++; return response(text); } });
    await assert.rejects(collect(watchAssessment(api, asm, fast)), ProtocolError);
    assert.equal(calls, 1);
  }
});

test('permission denial does not reconnect; transient network errors have a finite retry budget', async () => {
  let calls = 0;
  const denied = new ApiClient({ baseUrl: 'http://localhost', fetch: async () => { calls++; return Response.json({ error: { code: 'FORBIDDEN', message: 'Denied', details: {}, request_id: null } }, { status: 403 }); } });
  await assert.rejects(collect(watchAssessment(denied, asm, fast)), ApiError);
  assert.equal(calls, 1);
  calls = 0;
  const offline = new ApiClient({ baseUrl: 'http://localhost', fetch: async () => { calls++; throw new TypeError('Offline'); } });
  await assert.rejects(collect(watchAssessment(offline, asm, { ...fast, maxReconnects: 2 })), /Offline/);
  assert.equal(calls, 3);
});

test('abort interrupts reconnect delay; early consumer return cancels body', async () => {
  const controller = new AbortController();
  const states = [];
  const api = new ApiClient({ baseUrl: 'http://localhost', fetch: async () => { throw new TypeError('Offline'); } });
  const promise = collect(watchAssessment(api, asm, { signal: controller.signal, retryMs: 60000, maxRetryMs: 60000, onConnection(s) { states.push(s); if (s === 'reconnecting') queueMicrotask(() => controller.abort()); } }));
  await assert.rejects(promise, e => e.name === 'AbortError');
  assert.equal(states.at(-1), 'aborted');
  let cancelled = false;
  const live = new ApiClient({ baseUrl: 'http://localhost', fetch: async () => new Response(new ReadableStream({ start(c) { c.enqueue(bytes(wire(event(1)))); }, cancel() { cancelled = true; } }), { headers: { 'content-type': 'text/event-stream' } }) });
  for await (const e of watchAssessment(live, asm)) { assert.equal(e.seq, 1); break; }
  assert.equal(cancelled, true);
});

test('EOF alone is not completion; checks persisted terminal state or fails', async () => {
  let calls = 0;
  const api = new ApiClient({ baseUrl: 'http://localhost', fetch: async () => { calls++; return response(''); } });
  await assert.rejects(collect(watchAssessment(api, asm, { ...fast, maxReconnects: 0 })), ProtocolError);
  assert.equal(calls, 2); // second response is not a valid AssessmentDetail
});
