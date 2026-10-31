/**
 * Server-side Supabase client (for Server Components, Route Handlers,
 * and Server Actions).
 *
 * Reads/writes cookies through the Next.js `cookies()` helper so the
 * session cookie set by the OAuth callback round-trip persists across
 * SSR requests.
 *
 * Pattern from Supabase's official Next.js App Router docs verbatim
 * (`getAll` + `setAll` cookie methods).  Do not mutate cookies in a
 * try/catch'd `setAll` outside Server Actions / Route Handlers —
 * Next.js throws otherwise and Supabase swallows the error.
 */
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

import { authCookieOptions } from "@/lib/authCookie";

export async function createSupabaseServerClient() {
  const cookieStore = await cookies();
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) {
    throw new Error(
      "Supabase env vars missing on the server — set " +
      "NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY."
    );
  }
  return createServerClient(url, key, {
    // Same options as the browser client and the middleware — see
    // lib/authCookie.ts for why they must not diverge.
    cookieOptions: authCookieOptions(),
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet) {
        try {
          cookiesToSet.forEach(({ name, value, options }) =>
            cookieStore.set(name, value, options),
          );
        } catch {
          // The `setAll` method was called from a Server Component.
          // This can be ignored if you have middleware refreshing
          // user sessions — see apps/web/middleware.ts.
        }
      },
    },
  });
}
