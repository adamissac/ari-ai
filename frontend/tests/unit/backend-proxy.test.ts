import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('server-only', () => ({}));
const { backendOrigin, proxy } = await import('@/lib/backend-proxy');

afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

describe('backend proxy', () => {
  it('tolerates one trailing slash and rejects paths or credentials', () => {
    expect(backendOrigin('http://api:8000/')).toBe('http://api:8000');
    expect(() => backendOrigin('http://api:8000/v1')).toThrow();
    expect(() => backendOrigin('http://user:pw@api:8000')).toThrow();
  });
  it('a misconfigured origin is a 500 INTERNAL, not an outage', async () => {
    vi.stubEnv('BACKEND_ORIGIN', 'ftp://api');
    const res = await proxy(new Request('http://web/api/v1/me'));
    expect(res.status).toBe(500);
    expect((await res.json()).error.code).toBe('INTERNAL');
  });
  it('a network failure is a 502 SUBSYSTEM_UNAVAILABLE', async () => {
    vi.stubEnv('BACKEND_ORIGIN', 'http://api:8000');
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('connect ECONNREFUSED')));
    const res = await proxy(new Request('http://web/api/v1/me'));
    expect(res.status).toBe(502);
    expect((await res.json()).error.code).toBe('SUBSYSTEM_UNAVAILABLE');
  });
  it('forwards only allow-listed headers and every Set-Cookie', async () => {
    vi.stubEnv('BACKEND_ORIGIN', 'http://api:8000/');
    const upstream = new Response('{}', { headers: [['content-type', 'application/json'], ['set-cookie', 'a=1'], ['set-cookie', 'b=2'], ['x-internal', 'secret']] });
    const fetchMock = vi.fn().mockResolvedValue(upstream);
    vi.stubGlobal('fetch', fetchMock);
    const res = await proxy(new Request('http://web/api/v1/me?x=1', { headers: { 'x-csrf-token': 't', 'x-evil': 'no', cookie: 's=1' } }));
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('http://api:8000/api/v1/me?x=1');
    const sent = init.headers as Headers;
    expect(sent.get('x-csrf-token')).toBe('t');
    expect(sent.get('cookie')).toBe('s=1');
    expect(sent.get('x-evil')).toBeNull();
    expect(sent.get('x-forwarded-host')).toBe('web');
    expect(res.headers.getSetCookie()).toEqual(['a=1', 'b=2']);
    expect(res.headers.get('x-internal')).toBeNull();
  });
  it('refuses paths outside /api/v1/', async () => {
    const res = await proxy(new Request('http://web/api/v2/me'));
    expect(res.status).toBe(404);
  });
});
