/**
 * Which optional integrations this BUILD has. LeilMat runs with neither: no accounts, no credits, no calls to any
 * service the operator did not configure. (NEXT_PUBLIC_* are inlined at build time, so these are decided when the image
 * or bundle is built; they are functions only so a test can set the environment.)
 *
 *   auth     — Supabase sign-in. Needs NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY.
 *   billing  — credits and plans, served by a separate billing API the operator runs. Needs auth AND
 *              NEXT_PUBLIC_LEIL_API_URL. There is NO default: a default pointing at someone else's host would send
 *              every signed-in user's access token there.
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
