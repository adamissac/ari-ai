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

/** The configured API origin; one trailing slash is tolerated. Throws on anything else. */
export function backendOrigin(value: string | undefined = process.env.BACKEND_ORIGIN): string {
  const origin = (value ?? 'http://127.0.0.1:8000').replace(/\/$/, '');
  if (!/^https?:\/\/[^/?#@]+$/.test(origin)) throw new Error('BACKEND_ORIGIN must be an http(s) origin without path or credentials');
  return origin;
}

const envelope = (code: string, message: string, status: number): Response =>
  Response.json({ error: { code, message, details: {}, request_id: null } }, { status });

export async function proxy(request: Request): Promise<Response> {
  const url = new URL(request.url);
  if (!url.pathname.startsWith('/api/v1/') || url.pathname.includes('..')) {
    return envelope('NOT_FOUND', 'not found', 404);
  }
  const headers = new Headers();
  for (const name of REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value !== null) headers.set(name, value);
  }
  // The public host the browser used, so the backend can tell proxied requests from direct ones.
  headers.set('x-forwarded-host', url.host);
  const hasBody = request.method !== 'GET' && request.method !== 'HEAD';
  // A bad configuration is the frontend's fault, not an outage: report it as such.
  let origin: string;
  try { origin = backendOrigin(); } catch { return envelope('INTERNAL', 'frontend misconfigured: BACKEND_ORIGIN', 500); }
  let upstream: Response;
  try {
    upstream = await fetch(`${origin}${url.pathname}${url.search}`, {
      method: request.method,
      headers,
      redirect: 'manual',
      signal: request.signal,
      cache: 'no-store',
      ...(hasBody ? { body: request.body, duplex: 'half' } : {}),
    } as RequestInit);
  } catch (error) {
    if (request.signal.aborted) throw error;
    return envelope('SUBSYSTEM_UNAVAILABLE', 'control-plane API unreachable', 502);
  }
  // A 5xx that did not come from the API itself (Railway's "application failed to respond"
  // while a deploy rolls over, an HTML gateway page) is reported in the API's own error shape,
  // so the app shows "temporarily unavailable" instead of rejecting a malformed response.
  if (upstream.status >= 500 && !(await isApiError(upstream.clone()))) {
    await upstream.body?.cancel();
    return envelope('SUBSYSTEM_UNAVAILABLE', 'The API is restarting. Try again in a moment.', 503);
  }
  const out = new Headers();
  for (const name of RESPONSE_HEADERS) {
    const value = upstream.headers.get(name);
    if (value !== null) out.set(name, value);
  }
  for (const cookie of upstream.headers.getSetCookie()) out.append('set-cookie', cookie);
  return new Response(upstream.body, { status: upstream.status, statusText: upstream.statusText, headers: out });
}

/** True when the body is the API's error envelope (read from a clone, bounded). */
async function isApiError(response: Response): Promise<boolean> {
  if (!(response.headers.get('content-type') ?? '').includes('application/json')) return false;
  try {
    const text = await response.text();
    if (text.length > 64 * 1024) return false;
    const body = JSON.parse(text) as { error?: { code?: unknown; message?: unknown } };
    return typeof body?.error?.code === 'string' && typeof body.error.message === 'string';
  } catch {
    return false;
  }
}
