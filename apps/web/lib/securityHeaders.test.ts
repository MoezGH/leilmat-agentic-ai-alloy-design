import { describe, expect, it } from "vitest";

import { connectSources, contentSecurityPolicy, securityHeaders } from "./securityHeaders";

const HOSTED = {
  NEXT_PUBLIC_API_URL: "https://app.example.org",
  NEXT_PUBLIC_SUPABASE_URL: "https://abc.supabase.co",
  NEXT_PUBLIC_LEIL_API_URL: "https://billing.example.org/api/v1",
};

describe("connect-src follows the build's own configuration", () => {
  it("a bare build talks to itself and nothing else", () => {
    expect(connectSources({})).toEqual(["'self'"]);
  });

  it("lists the API, Supabase and billing origins (not their paths), with websockets for https", () => {
    const s = connectSources(HOSTED);
    expect(s).toContain("https://app.example.org");
    expect(s).toContain("https://abc.supabase.co");
    expect(s).toContain("wss://abc.supabase.co");
    expect(s).toContain("https://billing.example.org");
    expect(s.some((x) => x.includes("/api/v1"))).toBe(false);
  });

  it("ignores a value that is not a URL instead of throwing", () => {
    expect(connectSources({ NEXT_PUBLIC_API_URL: "not a url" })).toEqual(["'self'"]);
  });

  it("does not add websockets for plain http (local development)", () => {
    expect(connectSources({ NEXT_PUBLIC_API_URL: "http://localhost:8000" })).toEqual(["'self'", "http://localhost:8000"]);
  });
});

describe("the policy", () => {
  const csp = contentSecurityPolicy(HOSTED);

  it("forbids framing, plugins, <base> and foreign form targets", () => {
    expect(csp).toContain("frame-ancestors 'none'");
    expect(csp).toContain("object-src 'none'");
    expect(csp).toContain("base-uri 'self'");
    expect(csp).toContain("form-action 'self'");
  });

  it("allows eval only for the development server", () => {
    expect(contentSecurityPolicy(HOSTED, false)).not.toContain("'unsafe-eval'");
    expect(contentSecurityPolicy(HOSTED, true)).toContain("'unsafe-eval'");
  });

  it("does not allow arbitrary hosts to receive requests", () => {
    const sources = csp.split("; ").find((d) => d.startsWith("connect-src "))!.split(" ").slice(1);
    for (const bare of ["*", "https:", "http:", "wss:", "ws:", "data:", "blob:"]) expect(sources).not.toContain(bare);
  });
});

describe("the header set", () => {
  const names = securityHeaders(HOSTED).map((h) => h.key);

  it("carries the standard hardening headers", () => {
    for (const h of ["Content-Security-Policy", "X-Content-Type-Options", "X-Frame-Options", "Referrer-Policy",
                     "Permissions-Policy", "Strict-Transport-Security"]) expect(names).toContain(h);
  });
});
