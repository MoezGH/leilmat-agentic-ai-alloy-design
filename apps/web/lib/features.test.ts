import { afterEach, describe, expect, it } from "vitest";

import { accountAppUrl, accountConfigured, authConfigured, billingBase, billingConfigured } from "./features";

const KEYS = ["NEXT_PUBLIC_SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_ANON_KEY", "NEXT_PUBLIC_LEIL_API_URL",
  "NEXT_PUBLIC_ACCOUNT_URL"] as const;
const saved = Object.fromEntries(KEYS.map((k) => [k, process.env[k]]));

function env(values: Partial<Record<(typeof KEYS)[number], string>>) {
  for (const k of KEYS) delete process.env[k];
  Object.assign(process.env, values);
}

afterEach(() => {
  for (const k of KEYS) {
    if (saved[k] === undefined) delete process.env[k];
    else process.env[k] = saved[k];
  }
});

describe("optional integrations", () => {
  it("a bare build has neither auth nor billing, and no billing host", () => {
    env({});
    expect(authConfigured()).toBe(false);
    expect(billingConfigured()).toBe(false);
    expect(billingBase()).toBe("");           // never a default host: it would receive users' access tokens
    expect(accountConfigured()).toBe(false);
    expect(accountAppUrl()).toBe("");         // same rule: never send a signed-in user to an unnamed host
  });

  it("auth needs both the URL and the anon key", () => {
    env({ NEXT_PUBLIC_SUPABASE_URL: "https://x.supabase.co" });
    expect(authConfigured()).toBe(false);
    env({ NEXT_PUBLIC_SUPABASE_URL: "https://x.supabase.co", NEXT_PUBLIC_SUPABASE_ANON_KEY: "anon" });
    expect(authConfigured()).toBe(true);
  });

  it("billing needs auth AND its own URL", () => {
    env({ NEXT_PUBLIC_LEIL_API_URL: "https://billing.example.org/api/v1/" });
    expect(billingConfigured()).toBe(false);  // a billing URL without accounts is meaningless
    env({ NEXT_PUBLIC_SUPABASE_URL: "u", NEXT_PUBLIC_SUPABASE_ANON_KEY: "k" });
    expect(billingConfigured()).toBe(false);  // accounts without a billing URL: sign-in only
    env({ NEXT_PUBLIC_SUPABASE_URL: "u", NEXT_PUBLIC_SUPABASE_ANON_KEY: "k", NEXT_PUBLIC_LEIL_API_URL: "https://billing.example.org/api/v1/" });
    expect(billingConfigured()).toBe(true);
    expect(billingBase()).toBe("https://billing.example.org/api/v1");   // trailing slash trimmed
  });

  it("the account link needs auth AND its own URL", () => {
    env({ NEXT_PUBLIC_ACCOUNT_URL: "https://account.example.org/" });
    expect(accountConfigured()).toBe(false);  // an account host without accounts is meaningless
    env({ NEXT_PUBLIC_SUPABASE_URL: "u", NEXT_PUBLIC_SUPABASE_ANON_KEY: "k" });
    expect(accountConfigured()).toBe(false);  // accounts without an account app: nowhere to send them
    env({ NEXT_PUBLIC_SUPABASE_URL: "u", NEXT_PUBLIC_SUPABASE_ANON_KEY: "k", NEXT_PUBLIC_ACCOUNT_URL: "https://account.example.org/" });
    expect(accountConfigured()).toBe(true);
    expect(accountAppUrl()).toBe("https://account.example.org");        // trailing slash trimmed
  });

  it("billing and the account link are independent", () => {
    env({ NEXT_PUBLIC_SUPABASE_URL: "u", NEXT_PUBLIC_SUPABASE_ANON_KEY: "k", NEXT_PUBLIC_ACCOUNT_URL: "https://account.example.org" });
    expect(accountConfigured()).toBe(true);
    expect(billingConfigured()).toBe(false);  // profile editing works even where nothing is for sale
  });
});
