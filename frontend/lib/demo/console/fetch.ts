import type { Fetch } from '@hackatl/frontend-transport';
import fixtures from './fixtures.json';

type FixtureResponse = {
  status: number;
  content_type: string | null;
  headers?: Record<string, string>;
  body: unknown;
};

const capturedAt = Date.parse(fixtures.captured_at);
const responses = fixtures.responses as Record<string, FixtureResponse>;
const NOT_FOUND = {
  error: {
    code: 'NOT_FOUND',
    message: 'Not part of the demo account',
    details: {},
    request_id: null,
  },
};
const READ_ONLY = {
  error: {
    code: 'FORBIDDEN',
    message: 'This is the demo account: actions are turned off.',
    details: {},
    request_id: null,
  },
};

function shiftIsoDates(value: unknown, delta: number): unknown {
  if (Array.isArray(value)) return value.map(item => shiftIsoDates(item, delta));
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([key, child]) => [key, shiftIsoDates(child, delta)]));
  }
  if (typeof value !== 'string') return value;
  return value.replace(/\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})\b/g, timestamp => {
    const time = Date.parse(timestamp);
    return Number.isNaN(time) ? timestamp : new Date(time + delta).toISOString();
  });
}

function canonicalQuery(search: string): string {
  return [...new URLSearchParams(search).entries()]
    .sort(([aKey, aValue], [bKey, bValue]) => aKey.localeCompare(bKey) || aValue.localeCompare(bValue))
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
    .join('&');
}

function fixtureKey(pathname: string, search: string): string | undefined {
  const path = pathname.replace(/^\/api\/v1(?=\/|$)/, '').replace(/\/$/, '') || '/';
  const query = canonicalQuery(search);
  const exact = `GET ${path}${query ? `?${query}` : ''}`;
  if (responses[exact]) return exact;
  if (/\/assessments\/[^/]+\/events$/.test(path)) {
    const eventKey = Object.keys(responses).find(key => key.startsWith(`GET ${path}?`));
    if (eventKey) return eventKey;
  }
  return undefined;
}

async function sha256(text: string): Promise<string> {
  const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return [...new Uint8Array(bytes)].map(byte => byte.toString(16).padStart(2, '0')).join('');
}

export const demoFetch: Fetch = async (input, init) => {
  const request = input instanceof Request ? input : undefined;
  const url = new URL(request?.url ?? String(input), globalThis.location?.origin ?? 'http://localhost');
  const method = (init?.method ?? request?.method ?? 'GET').toUpperCase();
  const path = url.pathname.replace(/^\/api\/v1(?=\/|$)/, '').replace(/\/$/, '') || '/';

  if (method !== 'GET') {
    if (method === 'POST' && path === '/auth/logout') return new Response(null, { status: 204 });
    return new Response(JSON.stringify(READ_ONLY), {
      status: 403,
      headers: { 'content-type': 'application/json' },
    });
  }

  const key = fixtureKey(url.pathname, url.search);
  const fixture = key ? responses[key] : undefined;
  if (!fixture) {
    return new Response(JSON.stringify(NOT_FOUND), {
      status: 404,
      headers: { 'content-type': 'application/json' },
    });
  }

  const delta = Date.now() - capturedAt;
  const body = shiftIsoDates(fixture.body, delta);
  const headers = new Headers(fixture.headers);
  if (fixture.content_type) headers.set('content-type', fixture.content_type);

  if (key?.startsWith('GET /artifacts/') && fixture.status === 200 && typeof body === 'string') {
    headers.set('x-artifact-sha256', await sha256(body));
  }

  const payload = typeof body === 'string'
    ? body
    : body === null ? null : JSON.stringify(body);
  return new Response(payload, { status: fixture.status, headers });
};
