import { createHmac, timingSafeEqual } from 'node:crypto';

/**
 * Server-only access gate for the demo account (/demo). The access code lives in the
 * DEMO_ACCESS_CODE environment variable (never in the repository or the browser bundle).
 * A correct code sets an httpOnly cookie holding an HMAC derived from the code, so the
 * cookie cannot be forged without the code and rotating the code signs everyone out.
 * Unset DEMO_ACCESS_CODE = the demo account is closed.
 */
export const DEMO_COOKIE = 'ari_demo_access';
export const DEMO_COOKIE_MAX_AGE_S = 12 * 60 * 60;
export const DEMO_HOME = '/demo/lumen-pay';

function secret(): string | null {
  const code = process.env.DEMO_ACCESS_CODE?.trim();
  return code ? code : null;
}

function same(a: string, b: string): boolean {
  const x = Buffer.from(a);
  const y = Buffer.from(b);
  return x.length === y.length && timingSafeEqual(x, y);
}

export function demoAccessConfigured(): boolean {
  return secret() !== null;
}

/** The cookie value for the current code, or null when the demo account is closed. */
export function demoAccessToken(): string | null {
  const code = secret();
  return code ? createHmac('sha256', code).update('ari-demo-access-v1').digest('hex') : null;
}

export function codeMatches(candidate: unknown): boolean {
  const code = secret();
  return code !== null && typeof candidate === 'string' && same(candidate.trim(), code);
}

export function cookieGrantsAccess(value: string | undefined): boolean {
  const token = demoAccessToken();
  return token !== null && typeof value === 'string' && same(value, token);
}

/** Only same-site paths under /demo may be a post-sign-in destination. */
export function safeNext(next: string | null | undefined): string {
  return next && /^\/demo(\/[A-Za-z0-9._~\-/]*)?$/.test(next) ? next : DEMO_HOME;
}
