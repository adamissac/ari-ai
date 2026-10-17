import { type NextRequest, NextResponse } from 'next/server';
import {
  codeMatches,
  cookieGrantsAccess,
  DEMO_COOKIE,
  DEMO_COOKIE_MAX_AGE_S,
  demoAccessConfigured,
  demoAccessToken,
} from '@/lib/demo/access';

// Failed attempts per client address, to slow down guessing. Per server instance.
const failures = new Map<string, number[]>();
const WINDOW_MS = 15 * 60 * 1000;
const MAX_FAILURES = 10;

function client(request: NextRequest): string {
  return request.headers.get('x-forwarded-for')?.split(',')[0]?.trim() || 'local';
}

function recentFailures(key: string, now: number): number[] {
  const kept = (failures.get(key) ?? []).filter(t => now - t < WINDOW_MS);
  failures.set(key, kept);
  return kept;
}

export function GET(request: NextRequest) {
  return NextResponse.json({ signedIn: cookieGrantsAccess(request.cookies.get(DEMO_COOKIE)?.value) });
}

export async function POST(request: NextRequest) {
  if (!demoAccessConfigured()) {
    return NextResponse.json({ error: 'Access codes are not enabled on this deployment.' }, { status: 503 });
  }
  const key = client(request);
  const now = Date.now();
  if (recentFailures(key, now).length >= MAX_FAILURES) {
    return NextResponse.json({ error: 'Too many attempts. Try again in a few minutes.' }, { status: 429 });
  }
  let body: unknown = null;
  try {
    body = await request.json();
  } catch {
    /* treated as a wrong code */
  }
  const code = body && typeof body === 'object' ? (body as { code?: unknown }).code : undefined;
  if (!codeMatches(code)) {
    failures.set(key, [...recentFailures(key, now), now]);
    return NextResponse.json({ error: 'That access code is not valid.' }, { status: 401 });
  }
  failures.delete(key);
  const response = NextResponse.json({ signedIn: true });
  response.cookies.set(DEMO_COOKIE, demoAccessToken() ?? '', {
    httpOnly: true,
    sameSite: 'lax',
    secure: process.env.NODE_ENV === 'production' && request.nextUrl.protocol === 'https:',
    path: '/',
    maxAge: DEMO_COOKIE_MAX_AGE_S,
  });
  return response;
}

export function DELETE() {
  const response = NextResponse.json({ signedIn: false });
  response.cookies.set(DEMO_COOKIE, '', { httpOnly: true, sameSite: 'lax', path: '/', maxAge: 0 });
  return response;
}
