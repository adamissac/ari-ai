/**
 * Demo-only deployments (for example the hosted Vercel site) run without the control-plane
 * backend. There the console cannot work, so the landing page renders without a session and
 * the console routes send visitors to the labelled simulated demo (ADR-0013) instead of an
 * "API unreachable" error. Off unless NEXT_PUBLIC_DEMO_ONLY=1 is set at build time.
 */
export const DEMO_ONLY = process.env.NEXT_PUBLIC_DEMO_ONLY === '1';

export interface Redirect { source: string; destination: string; permanent: false }

/** Console routes that need the backend, redirected to the demo in a demo-only build. */
export function demoOnlyRedirects(enabled: boolean): Redirect[] {
  if (!enabled) return [];
  return ['/projects', '/projects/:path*'].map(source => ({ source, destination: '/demo', permanent: false }));
}
