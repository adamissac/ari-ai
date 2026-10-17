import { type NextRequest, NextResponse } from 'next/server';
import { cookieGrantsAccess, DEMO_COOKIE } from '@/lib/demo/access';

/** The demo account (/demo) is only reachable with a valid access-code cookie. */
export function proxy(request: NextRequest) {
  if (cookieGrantsAccess(request.cookies.get(DEMO_COOKIE)?.value)) return NextResponse.next();
  const url = request.nextUrl.clone();
  url.pathname = '/access';
  url.search = '';
  url.searchParams.set('next', request.nextUrl.pathname);
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ['/demo', '/demo/:path*'],
};
