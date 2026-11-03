import { describe, expect, it } from 'vitest';
import handler from '../api/notes/[id].js';

function response() {
  return {
    code: 0, body: null, headers: {},
    setHeader(k, v) { this.headers[k] = v; },
    status(c) { this.code = c; return this; },
    json(b) { this.body = b; return this; },
  };
}

describe('GET /api/notes/:id', () => {
  it('rejects other methods', async () => {
    const res = response();
    await handler({ method: 'POST', headers: {}, query: { id: 'x' } }, res);
    expect(res.code).toBe(405);
    expect(res.headers.Allow).toBe('GET');
  });

  it('requires a bearer token', async () => {
    const res = response();
    await handler({ method: 'GET', headers: {}, query: { id: 'x' } }, res);
    expect(res.code).toBe(401);
  });
});
