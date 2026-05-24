/**
 * /auth/callback — Supabase OAuth code-exchange route.
 *
 * When the user signs in via Google, Supabase redirects back here with
 * `?code=<one-time>`.  We trade that code for a session (sets the
 * httpOnly session cookie) and then bounce the user to the post-login
 * destination (default: `/`).
 *
 * If the exchange fails (expired code, network blip, missing env), we
 * route to `/auth/error?reason=...` so the user sees a clear failure
 * rather than landing back on an empty page.
 *
 * Reference: landing_header_spec.md §5 + Supabase Next.js App Router docs.
 */
import { NextResponse, type NextRequest } from "next/server";

import { createSupabaseServerClient } from "@/lib/supabase/server";

export async function GET(request: NextRequest) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const next = url.searchParams.get("next") ?? "/";

  if (!code) {
    return NextResponse.redirect(new URL("/auth/error?reason=no_code", url.origin));
  }

  const supabase = await createSupabaseServerClient();
  const { error } = await supabase.auth.exchangeCodeForSession(code);

  if (error) {
    const reason = encodeURIComponent(error.message);
    return NextResponse.redirect(new URL(`/auth/error?reason=${reason}`, url.origin));
  }

  // The session cookie is now set on the response courtesy of the
  // server client's cookies.setAll handler.  Send the user home.
  return NextResponse.redirect(new URL(next, url.origin));
}
