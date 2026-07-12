/**
 * middleware.ts  (project root — alongside next.config.ts)
 *
 * Protects all routes except /login.
 * Because the token lives in memory, we use an httpOnly cookie
 * named `svs_auth` as the middleware-visible signal:
 *   - On login: set cookie (done in AuthProvider below)
 *   - On logout: clear cookie
 *   - Middleware reads cookie and redirects if absent
 *
 * NOTE: The actual JWT is still kept in memory in lib/auth.ts.
 * The cookie only signals "has ever authenticated this browser session"
 * and is cleared on logout. This keeps the real token out of persistent storage.
 */

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_PATHS = ["/login"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Allow public paths
  if (PUBLIC_PATHS.some((p) => pathname.startsWith(p))) {
    return NextResponse.next();
  }

  // Allow Next.js internals and static assets
  if (
    pathname.startsWith("/_next") ||
    pathname.startsWith("/favicon") ||
    pathname.startsWith("/api/") ||       // API routes pass through
    pathname.includes(".")                // static files
  ) {
    return NextResponse.next();
  }

  // Check for auth signal cookie
  const authCookie = request.cookies.get("svs_auth");
  if (!authCookie?.value) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("from", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
