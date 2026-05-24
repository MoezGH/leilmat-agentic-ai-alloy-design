/**
 * Next.js root middleware — refreshes the Supabase session cookie on
 * every request that isn't a static asset.
 *
 * We intentionally don't gate routes here; route-level auth on this
 * frontend is unnecessary today because:
 *   * The cost-bearing API surface lives on the FastAPI backend behind
 *     the JWT middleware (apps/api/middleware/auth.py, Phase B).
 *   * The marketing landing (/) and canvas (/canvas) should render
 *     for signed-out users — they see the "Sign in" CTA in the header.
 *
 * Reference: Supabase Next.js App Router docs verbatim.
 */
import type { NextRequest } from "next/server";
import { updateSession } from "@/lib/supabase/middleware";

export async function middleware(request: NextRequest) {
  return await updateSession(request);
}

export const config = {
  matcher: [
    /**
     * Match all request paths except for the ones starting with:
     *   - _next/static  (static files)
     *   - _next/image   (image optimisation files)
     *   - favicon.ico   (favicon)
     *   - .*\..*        (any file with an extension, e.g. .svg, .png, .css)
     * Feel free to widen the exception list if needed.
     */
    "/((?!_next/static|_next/image|favicon.ico|.*\\..*).*)",
  ],
};
