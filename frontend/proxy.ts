import { type NextRequest, NextResponse } from 'next/server';
import { cookieGrantsAccess, DEMO_COOKIE, DEMO_HOME } from '@/lib/demo/access';
import { DEMO_ONLY } from '@/lib/deployment';

/**
 * The demo account (/demo) is only reachable with a valid access-code cookie. With that
 * cookie, the console routes that would otherwise ask for a GitHub sign-in (/projects,
 * /connect) and the access-code page itself open the demo account instead, so the access
 * code is the only login needed.
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
  if (pathname.startsWith('/connect') && access) {
    url.pathname = DEMO_HOME;
    url.search = '';
    return NextResponse.redirect(url);
  }
  if (DEMO_ONLY && pathname.startsWith('/projects') && !access) {
    url.pathname = '/access';
    url.search = '';
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ['/demo', '/demo/:path*', '/access', '/projects', '/projects/:path*', '/connect', '/connect/:path*'],
};
