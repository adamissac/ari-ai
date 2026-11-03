import { type NextRequest, NextResponse } from 'next/server';
import { cookieGrantsAccess, DEMO_COOKIE, DEMO_GITHUB_STEP, DEMO_HOME } from '@/lib/demo/access';
import { DEMO_ONLY } from '@/lib/deployment';

/**
 * The demo account (/demo) is only reachable with a valid access-code cookie. With that
 * cookie the console routes (/connect, /projects) open the demo account in place, so the
 * access code is the only login needed; the access-code page opens the account instead.
 * The simulated GitHub authorization step needs the cookie too.
 */
export function proxy(request: NextRequest) {
  const access = cookieGrantsAccess(request.cookies.get(DEMO_COOKIE)?.value);
  const { pathname } = request.nextUrl;
  const url = request.nextUrl.clone();
  if (pathname === '/demo' || pathname.startsWith('/demo/')) {
    if (access) {
      url.pathname = DEMO_HOME;
      url.search = '';
      return NextResponse.redirect(url);
    }
    url.pathname = '/access';
    url.search = '';
    return NextResponse.redirect(url);
  }
  if (pathname === '/access' && access) {
    url.pathname = DEMO_HOME;
    url.search = '';
    return NextResponse.redirect(url);
  }
  if (pathname === DEMO_GITHUB_STEP && !access) {
    url.pathname = '/access';
    url.search = '';
    return NextResponse.redirect(url);
  }
  if (DEMO_ONLY && (pathname.startsWith('/projects') || pathname.startsWith('/connect')) && !access) {
    url.pathname = '/access';
    url.search = '';
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ['/demo', '/demo/:path*', '/access', '/access/github', '/projects', '/projects/:path*', '/connect', '/connect/:path*'],
};
