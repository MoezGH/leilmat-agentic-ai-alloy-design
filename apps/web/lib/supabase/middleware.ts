/**
 * Supabase session-refresh helper used by Next.js root middleware.ts.
 *
 * Runs on every request to keep the session cookie fresh — without
 * this, the session expires silently after the access-token TTL even
 * when the refresh-token is still valid.
 *
 * Pattern from Supabase's official @supabase/ssr Next.js App Router
 * docs verbatim.  The NextResponse the middleware returns MUST carry
 * the same cookies we updated here, or the rotation is lost.
 */
import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

export async function updateSession(request: NextRequest) {
  let supabaseResponse = NextResponse.next({ request });

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) {
    // Env not configured — let the request through so the canvas
    // still renders during local development before /env is wired.
    return supabaseResponse;
  }

  const supabase = createServerClient(url, key, {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet) {
        cookiesToSet.forEach(({ name, value }) =>
          request.cookies.set(name, value),
        );
        supabaseResponse = NextResponse.next({ request });
        cookiesToSet.forEach(({ name, value, options }) =>
          supabaseResponse.cookies.set(name, value, options),
        );
      },
    },
  });

  // Touching getUser() forces the refresh-token rotation if the
  // access-token is near expiry.  Discard the result; the rotation
  // is the side effect we want.
  await supabase.auth.getUser();

  return supabaseResponse;
}
