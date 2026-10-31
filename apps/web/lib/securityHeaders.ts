/**
 * Security headers for every page the web app serves (wired in next.config.ts).
 *
 * The Content-Security-Policy is built from the SAME NEXT_PUBLIC_* values the bundle is built with, so it allows exactly
 * the origins this deployment talks to — its own API, and Supabase / the billing API only if configured — and nothing a
 * self-hoster did not choose. It is not nonce-based: Next's inline hydration scripts need 'unsafe-inline' unless every
 * page is rendered per request, so script injection is not fully closed. What it does close: framing (clickjacking),
 * plugins, <base> and form hijacking, and any request or image/font load to a host that is not listed.
 *
 * Headers that only matter over HTTPS (HSTS) are harmless over plain http, which browsers ignore them on.
 */
export type HeaderEntry = { key: string; value: string };

type Env = Record<string, string | undefined>;

function originOf(url: string | undefined): string | null {
  if (!url) return null;
  try {
    return new URL(url).origin;
  } catch {
    return null;
  }
}

/** The origins the browser may open connections to: this site, its API, and the optional integrations. */
export function connectSources(env: Env = process.env): string[] {
  const sources = new Set<string>(["'self'"]);
  for (const value of [env.NEXT_PUBLIC_API_URL, env.NEXT_PUBLIC_SUPABASE_URL, env.NEXT_PUBLIC_LEIL_API_URL]) {
    const origin = originOf(value);
    if (!origin) continue;
    sources.add(origin);
    if (origin.startsWith("https://")) sources.add(origin.replace("https://", "wss://"));   // Supabase realtime
  }
  return [...sources];
}

export function contentSecurityPolicy(env: Env = process.env, dev = false): string {
  const directives: Record<string, string[]> = {
    "default-src": ["'self'"],
    // Inline scripts: Next's hydration payload. 'unsafe-eval' only for the dev server's hot reloading.
    "script-src": ["'self'", "'unsafe-inline'", ...(dev ? ["'unsafe-eval'"] : [])],
    "style-src": ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com"],
    "font-src": ["'self'", "https://fonts.gstatic.com", "data:"],
    // https: because signed-in users' avatars come from their identity provider.
    "img-src": ["'self'", "data:", "blob:", "https:"],
    "connect-src": connectSources(env),
    "worker-src": ["'self'", "blob:"],
    "object-src": ["'none'"],
    "base-uri": ["'self'"],
    "form-action": ["'self'"],
    "frame-ancestors": ["'none'"],
  };
  return Object.entries(directives).map(([name, values]) => `${name} ${values.join(" ")}`).join("; ");
}

export function securityHeaders(env: Env = process.env, dev = false): HeaderEntry[] {
  return [
    { key: "Content-Security-Policy", value: contentSecurityPolicy(env, dev) },
    { key: "X-Content-Type-Options", value: "nosniff" },
    { key: "X-Frame-Options", value: "DENY" },                                   // older browsers; frame-ancestors covers the rest
    { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
    { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
    { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
  ];
}
