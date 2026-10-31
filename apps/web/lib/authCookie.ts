/**
 * Where the Supabase session cookie lives — the one thing that makes a single
 * sign-in work across every Leil app.
 *
 * KEPT IDENTICAL IN EVERY LEIL APP (LeilAuth apps/web/lib/authCookie.ts is the
 * original). These are separate repositories, so this is a deliberate copy: if
 * one app computes different cookie options from another, they write two
 * cookies of the same name and the session breaks in ways that are painful to
 * trace. Change it in all of them or in none.
 *
 * THE PROBLEM THIS SOLVES
 *   @supabase/ssr defaults to a HOST-ONLY cookie, so a session created on
 *   app.example.org is invisible to account.leil.app and the user is asked to
 *   sign in again on every app. (The analytics and Stripe cookies already
 *   cross between the subdomains, because those are set with Domain=.leil.app
 *   — that is exactly the attribute the auth cookie was missing.)
 *
 * THE TRADE-OFF, STATED PLAINLY
 *   A cookie scoped to .leil.app is readable by JavaScript on EVERY
 *   *.leil.app host. It cannot be HttpOnly, because the browser-side Supabase
 *   client has to read it. So an XSS or a subdomain takeover anywhere under
 *   leil.app yields a live session.
 *
 *   What this does NOT change: every Leil app already shares one Supabase
 *   project, so a session stolen from any single app already authenticates
 *   against all of them. The real widening is narrower — an app the user has
 *   NEVER signed into would now still hand out a session. Accepted
 *   deliberately on 2026-11-01 in exchange for one sign-in across the family.
 *
 * NO DEFAULT DOMAIN. Empty means host-only, which is what local development
 * and any single-app self-hosted build must get: a hard-coded ".leil.app"
 * would try to set a cookie for a domain the deployment does not own, and the
 * browser would silently drop it.
 */

export type AuthCookieOptions = {
  domain: string;
  path: string;
  sameSite: "lax";
  secure: boolean;
};

/** The configured parent domain (e.g. ".leil.app"), or "" for host-only. */
export function authCookieDomain(): string {
  return (process.env.NEXT_PUBLIC_AUTH_COOKIE_DOMAIN ?? "").trim();
}

/**
 * cookieOptions for createBrowserClient / createServerClient, or undefined to
 * keep @supabase/ssr's host-only default.
 *
 * EVERY client in the app must pass this — browser, server and middleware. If
 * they disagree, one writes the shared cookie and another writes a host-only
 * one of the SAME NAME, and which of the two wins a read is not well defined.
 */
export function authCookieOptions(): AuthCookieOptions | undefined {
  const domain = authCookieDomain();
  if (!domain) return undefined;
  // `secure` is safe to hard-code alongside a domain: a cross-subdomain
  // session is a production arrangement and production is HTTPS. Local dev
  // sets no domain and so never reaches this branch (a Secure cookie on
  // http://localhost would simply be dropped).
  return { domain, path: "/", sameSite: "lax", secure: true };
}

/**
 * Remove a pre-existing HOST-ONLY session cookie, once per browser.
 *
 * Switching to Domain=.leil.app does not replace the old cookie — it ADDS a
 * second one with the same name. `document.cookie` then returns both, and
 * which one a parser keeps depends on browser ordering rules that are not
 * specified for the host-only vs domain case. The two stay in step only until
 * the first token refresh writes one of them; after that the stale twin can
 * shadow the live session and sign-in appears to fail at random.
 *
 * So clear the host-only one deliberately rather than leave it to chance. The
 * cost is one forced re-sign-in per browser, which is both unavoidable here
 * and much kinder than an intermittent auth bug.
 *
 * Deleting a cookie requires matching its domain: omitting the attribute
 * targets the host-only cookie and leaves the shared one alone.
 *
 * Guarded by a localStorage marker so it runs exactly once. Wrapped in
 * try/catch because localStorage throws in some privacy modes, and a cleanup
 * that cannot record itself must not take the app down with it.
 */
const MIGRATION_KEY = "leil.authCookie.hostOnlyCleared.v1";

export function clearHostOnlyAuthCookies(): void {
  if (typeof document === "undefined") return;
  if (!authCookieDomain()) return;            // host-only by design: nothing to migrate

  try {
    if (localStorage.getItem(MIGRATION_KEY)) return;
  } catch {
    return;   // cannot track it — better to skip than to clear on every load
  }

  for (const entry of document.cookie.split("; ")) {
    const name = entry.split("=")[0];
    // Supabase chunks a large session across `…auth-token.0`, `.1`, and keeps
    // PKCE verifiers under the same prefix. Match the prefix, not a fixed name.
    if (!name.startsWith("sb-")) continue;
    document.cookie = `${name}=; Max-Age=0; path=/`;
  }

  try {
    localStorage.setItem(MIGRATION_KEY, String(Date.now()));
  } catch {
    /* ignore: the clear already happened, and re-running it is harmless */
  }
}
