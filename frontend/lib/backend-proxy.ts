import 'server-only';

/**
 * Forward /api/v1/* to BACKEND_ORIGIN at request time. Keeps the backend's
 * SameSite=Lax session cookie and CSRF flow same-origin, streams bodies without
 * buffering (SSE) and forwards only the headers the API contract uses.
 */
const REQUEST_HEADERS = [
  'accept', 'content-type', 'cookie', 'last-event-id', 'x-csrf-token', 'idempotency-key',
  'x-github-event', 'x-github-delivery', 'x-hub-signature-256', 'authorization', 'user-agent',
];
const RESPONSE_HEADERS = [
  'content-type', 'cache-control', 'location', 'retry-after', 'x-request-id', 'x-artifact-sha256',
  'x-content-type-options', 'content-disposition', 'x-accel-buffering',
];

export function backendOrigin(): string {
  const origin = process.env.BACKEND_ORIGIN ?? 'http://127.0.0.1:8000';
  if (!/^https?:\/\/[^/?#@]+$/.test(origin)) throw new Error('BACKEND_ORIGIN must be an http(s) origin without path or credentials');
  return origin;
}

export async function proxy(request: Request): Promise<Response> {
  const url = new URL(request.url);
  if (!url.pathname.startsWith('/api/v1/') || url.pathname.includes('..')) {
    return Response.json({ error: { code: 'NOT_FOUND', message: 'not found', details: {}, request_id: null } }, { status: 404 });
  }
  const headers = new Headers();
  for (const name of REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value !== null) headers.set(name, value);
  }
  const hasBody = request.method !== 'GET' && request.method !== 'HEAD';
  let upstream: Response;
  try {
    upstream = await fetch(`${backendOrigin()}${url.pathname}${url.search}`, {
      method: request.method,
      headers,
      redirect: 'manual',
      signal: request.signal,
      cache: 'no-store',
      ...(hasBody ? { body: request.body, duplex: 'half' } : {}),
    } as RequestInit);
  } catch (error) {
    if (request.signal.aborted) throw error;
    return Response.json(
      { error: { code: 'SUBSYSTEM_UNAVAILABLE', message: 'control-plane API unreachable', details: {}, request_id: null } },
      { status: 502 },
    );
  }
  const out = new Headers();
  for (const name of RESPONSE_HEADERS) {
    const value = upstream.headers.get(name);
    if (value !== null) out.set(name, value);
  }
  for (const cookie of upstream.headers.getSetCookie()) out.append('set-cookie', cookie);
  return new Response(upstream.body, { status: upstream.status, statusText: upstream.statusText, headers: out });
}
