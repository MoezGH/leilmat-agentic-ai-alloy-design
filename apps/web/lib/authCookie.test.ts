/**
 * @vitest-environment jsdom
 *
 * Per-file rather than global: the other suites are pure logic and run faster
 * in the default node environment.
 */
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { authCookieDomain, authCookieOptions, clearHostOnlyAuthCookies } from "./authCookie";

const KEY = "NEXT_PUBLIC_AUTH_COOKIE_DOMAIN";
const saved = process.env[KEY];

afterEach(() => {
  if (saved === undefined) delete process.env[KEY];
  else process.env[KEY] = saved;
});

describe("auth cookie scope", () => {
  it("is host-only when no domain is configured", () => {
    delete process.env[KEY];
    expect(authCookieDomain()).toBe("");
    // undefined, not {domain: ""} — @supabase/ssr must fall through to its own
    // default rather than be handed an empty domain to set.
    expect(authCookieOptions()).toBeUndefined();
  });

  it("shares across subdomains when a parent domain is configured", () => {
    process.env[KEY] = ".leil.app";
    expect(authCookieOptions()).toEqual({
      domain: ".leil.app",
      path: "/",
      sameSite: "lax",
      secure: true,
    });
  });

  it("trims whitespace, so a stray newline in .env is not a silent host-only fallback", () => {
    process.env[KEY] = "  .leil.app \n";
    expect(authCookieDomain()).toBe(".leil.app");
    expect(authCookieOptions()?.domain).toBe(".leil.app");
  });
});

describe("one-time host-only cookie cleanup", () => {
  const MARKER = "leil.authCookie.hostOnlyCleared.v1";
  let jar: string[];

  beforeEach(() => {
    jar = [];
    localStorage.clear();
    // jsdom's document.cookie does not model Domain, so stand in a jar that
    // records every write. What matters here is WHICH names are expired and
    // that the delete carries no domain attribute (that is what targets the
    // host-only cookie and spares the shared one).
    Object.defineProperty(document, "cookie", {
      configurable: true,
      get: () =>
        "sb-ref-auth-token.0=aaa; sb-ref-auth-token.1=bbb; " +
        "sb-ref-auth-token-code-verifier=ccc; _ga=GA1.2.3; __stripe_mid=xyz",
      set: (v: string) => jar.push(v),
    });
  });

  it("expires every sb-* cookie without a domain attribute, and nothing else", () => {
    process.env[KEY] = ".leil.app";
    clearHostOnlyAuthCookies();

    const cleared = jar.map((w) => w.split("=")[0]);
    expect(cleared).toEqual([
      "sb-ref-auth-token.0",
      "sb-ref-auth-token.1",
      "sb-ref-auth-token-code-verifier",
    ]);
    // Analytics and Stripe cookies are genuinely shared on .leil.app already:
    // touching them would log the user out of nothing and lose attribution.
    expect(cleared).not.toContain("_ga");
    expect(cleared).not.toContain("__stripe_mid");
    // No `domain=` — that is the whole point; with one, this would delete the
    // shared cookie it was meant to protect.
    for (const write of jar) {
      expect(write.toLowerCase()).not.toContain("domain=");
      expect(write).toContain("Max-Age=0");
    }
  });

  it("runs once per browser, not on every page load", () => {
    process.env[KEY] = ".leil.app";
    clearHostOnlyAuthCookies();
    const afterFirst = jar.length;
    expect(afterFirst).toBeGreaterThan(0);

    clearHostOnlyAuthCookies();
    clearHostOnlyAuthCookies();
    // Otherwise every load would delete the freshly-written shared session.
    expect(jar.length).toBe(afterFirst);
    expect(localStorage.getItem(MARKER)).toBeTruthy();
  });

  it("does nothing at all when the cookie is host-only by design", () => {
    delete process.env[KEY];
    clearHostOnlyAuthCookies();
    // Local dev and single-app self-hosted builds have no migration to run,
    // and clearing here would sign the user out on every reload.
    expect(jar).toEqual([]);
    expect(localStorage.getItem(MARKER)).toBeNull();
  });
});
