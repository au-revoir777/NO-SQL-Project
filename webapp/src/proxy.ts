/**
 * Optimistic route protection (Next.js 16 "proxy", formerly middleware): pages
 * without a session cookie go to /login. The real checks are server-side: the
 * app layout asks FastAPI who the user is, and every /api/v1 route enforces its
 * role. The current path is passed on so layouts can build ?next= links.
 */
import { type NextRequest, NextResponse } from "next/server";

const PUBLIC_PAGES = ["/login"];

export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const isPublic = PUBLIC_PAGES.some((p) => pathname === p || pathname.startsWith(`${p}/`));
  if (!isPublic && !request.cookies.has("fraudsim_access")) {
    const login = new URL("/login", request.url);
    login.searchParams.set("next", `${pathname}${search}`);
    return NextResponse.redirect(login);
  }
  const headers = new Headers(request.headers);
  headers.set("x-pathname", `${pathname}${search}`);
  return NextResponse.next({ request: { headers } });
}

export const config = {
  // Pages only: not the API proxy, Next internals or static files.
  matcher: ["/((?!api/|_next/|favicon\\.ico|.*\\.[a-zA-Z0-9]+$).*)"],
};
