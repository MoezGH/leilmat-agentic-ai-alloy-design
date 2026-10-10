/**
 * Thin client for LeilAI-5's central billing API.
 *
 * The billing *engine* (Stripe, checkout sessions, the credit ledger, webhooks,
 * subscription state, pricing/tier config) lives entirely in LeilAI-5. This module is
 * just the buttons' plumbing: it calls the same endpoints the main app exposes, forwards
 * the caller's Supabase JWT for per-user attribution, and passes return URLs that bounce
 * the user back into LeilMat after Stripe. All checkout/portal endpoints return Stripe
 * *hosted* URLs, so we finish with a plain same-tab redirect — no embedded Stripe.js.
 *
 * Base URL matches lib/hooks/useCredits.ts (NEXT_PUBLIC_LEIL_API_URL, e.g.
 * https://www.leil.app/api/v1).
 */

const API_BASE =
  process.env.NEXT_PUBLIC_LEIL_API_URL ?? "https://www.leil.app/api/v1";

// ── Tier config (public — no auth) ──────────────────────────────────────────

export interface TierConfig {
  tier_key: string;
  name: string;
  display_name: string;
  monthly_credits: number;
  can_purchase_credits: boolean;
  price_ids?: string[];
}

export async function fetchTierConfigurations(): Promise<TierConfig[]> {
  const r = await fetch(`${API_BASE}/billing/tier-configurations`, {
    cache: "no-store",
  });
  if (!r.ok) throw new Error(`tier-configurations HTTP ${r.status}`);
  const data = await r.json();
  return (data?.tiers ?? []) as TierConfig[];
}

// ── Authenticated actions ───────────────────────────────────────────────────

function authHeaders(token: string): HeadersInit {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };
}

/** Only reached without a `window` (SSR); both callers are browser click handlers, so this is a
 *  safety net. Set NEXT_PUBLIC_APP_URL to your deployment origin. */
const APP_ORIGIN_FALLBACK = process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:4000";

/** Absolute return URL back into LeilMat, tagged so the header can toast + refresh. */
function returnUrl(returnPath: string, status: "success" | "cancel"): string {
  const origin =
    typeof window !== "undefined" ? window.location.origin : APP_ORIGIN_FALLBACK;
  const sep = returnPath.includes("?") ? "&" : "?";
  return `${origin}${returnPath}${sep}billing=${status}`;
}

/** Subscribe to / upgrade to a tier. Returns a Stripe hosted checkout URL. */
export async function createCheckoutSession(
  token: string,
  opts: { tierKey: string; commitmentType?: string; returnPath?: string },
): Promise<string> {
  const path = opts.returnPath ?? "/";
  const r = await fetch(`${API_BASE}/billing/create-checkout-session`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({
      tier_key: opts.tierKey,
      success_url: returnUrl(path, "success"),
      cancel_url: returnUrl(path, "cancel"),
      commitment_type: opts.commitmentType ?? null,
    }),
  });
  if (!r.ok) throw new Error(`create-checkout-session HTTP ${r.status}`);
  const data = await r.json();
  if (!data?.checkout_url) throw new Error("No checkout_url in response");
  return data.checkout_url as string;
}

/** Manage/cancel an existing subscription via Stripe's customer portal. */
export async function createPortalSession(
  token: string,
  opts: { returnPath?: string } = {},
): Promise<string> {
  const path = opts.returnPath ?? "/";
  const origin =
    typeof window !== "undefined" ? window.location.origin : APP_ORIGIN_FALLBACK;
  const r = await fetch(`${API_BASE}/billing/create-portal-session`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ return_url: `${origin}${path}` }),
  });
  if (!r.ok) throw new Error(`create-portal-session HTTP ${r.status}`);
  const data = await r.json();
  if (!data?.portal_url) throw new Error("No portal_url in response");
  return data.portal_url as string;
}

/** Buy a one-off credit top-up (dollar amount). Returns a Stripe hosted checkout URL. */
export async function purchaseCredits(
  token: string,
  opts: { amount: number; returnPath?: string },
): Promise<string> {
  const path = opts.returnPath ?? "/";
  const r = await fetch(`${API_BASE}/billing/purchase-credits`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({
      amount: opts.amount,
      success_url: returnUrl(path, "success"),
      cancel_url: returnUrl(path, "cancel"),
    }),
  });
  if (!r.ok) throw new Error(`purchase-credits HTTP ${r.status}`);
  const data = await r.json();
  if (!data?.checkout_url) throw new Error("No checkout_url in response");
  return data.checkout_url as string;
}

/** Same-tab navigation so Stripe's return URL lands back in this tab. */
export function goTo(url: string): void {
  window.location.assign(url);
}
