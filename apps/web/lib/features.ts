/**
 * Which optional integrations this BUILD has. LeilMat runs with neither: no accounts, no credits, no calls to any
 * service the operator did not configure. (NEXT_PUBLIC_* are inlined at build time, so these are decided when the image
 * or bundle is built; they are functions only so a test can set the environment.)
 *
 *   auth     — Supabase sign-in. Needs NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY.
 *   billing  — credits and plans, served by a separate billing API the operator runs. Needs auth AND
 *              NEXT_PUBLIC_LEIL_API_URL. There is NO default: a default pointing at someone else's host would send
 *              every signed-in user's access token there.
 *   account  — a link out to the operator's account app (profile, password, usage). Needs auth AND
 *              NEXT_PUBLIC_ACCOUNT_URL. No default, for the same reason as billing: this is where we send a
 *              signed-in user to manage their identity, and it must never be a host the operator did not name.
 */
export function authConfigured(): boolean {
  return Boolean(process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY);
}

/** Base URL of the billing API, without a trailing slash; "" when billing is not configured. */
export function billingBase(): string {
  return (process.env.NEXT_PUBLIC_LEIL_API_URL ?? "").trim().replace(/\/+$/, "");
}

export function billingConfigured(): boolean {
  return authConfigured() && billingBase() !== "";
}

/**
 * The account app's origin, without a trailing slash; "" when not configured.
 *
 * LeilMat deliberately has no profile editor of its own — name, avatar and
 * password live in one place for every Leil app, so there is one account and
 * no chance of two apps disagreeing about it. This is the way there.
 */
export function accountAppUrl(): string {
  return (process.env.NEXT_PUBLIC_ACCOUNT_URL ?? "").trim().replace(/\/+$/, "");
}

export function accountConfigured(): boolean {
  return authConfigured() && accountAppUrl() !== "";
}
