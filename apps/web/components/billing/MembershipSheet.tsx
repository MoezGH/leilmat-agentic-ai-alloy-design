/**
 * MembershipSheet — in-app subscription & credit management for LeilMat.
 *
 * A modal that lets the signed-in user upgrade their plan, top up credits, or manage /
 * cancel their membership WITHOUT leaving LeilMat — it only bounces out to Stripe's
 * hosted pages and returns via ?billing=success|cancel (handled in LeilHeader).
 *
 * All logic stays central: this renders plan cards from LeilAI-5's public
 * tier-configurations API and calls the same checkout/portal/purchase endpoints the main
 * app uses. Nothing Stripe-sensitive lives here.
 */
"use client";

import { useEffect, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { usePathname } from "next/navigation";
import { Loader2, X, ExternalLink, Check, Zap } from "lucide-react";
import { toast } from "sonner";

import { useSession } from "@/components/providers/AuthProvider";
import {
  fetchTierConfigurations,
  createCheckoutSession,
  createPortalSession,
  purchaseCredits,
  goTo,
  type TierConfig,
} from "@/lib/billing/client";

const ACCENT_HSL = "38 96% 60%"; // LeilMat warm gold

// Quick top-up presets (dollars). Mirror a subset of LeilAI-5's credit packages.
const TOPUP_AMOUNTS = [10, 25, 50];

// Headline monthly USD price per tier — mirrors LeilAI-5's own pricing-config.ts
// (the same source leil.app/pricing renders). The sheet's checkout is monthly
// (no commitment_type), so these are exactly what the user is charged. Keep in
// sync with LeilAI-5 if prices change (rare); the tier LIST + credits still come
// live from the central tier-configurations API.
const MONTHLY_USD: Record<string, number> = {
  tier_2_20: 20,   // Basic
  tier_6_50: 50,   // Advanced
  tier_25_200: 200, // Ultra
};

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Current tier display name (from useCredits), e.g. "Basic". */
  currentTier: string | null;
  /** Current display balance (credits). */
  balance: number | null;
}

export function MembershipSheet({ open, onOpenChange, currentTier, balance }: Props) {
  const { session } = useSession();
  const token = session?.access_token ?? null;
  const pathname = usePathname();
  const returnPath = pathname || "/";

  const [tiers, setTiers] = useState<TierConfig[] | null>(null);
  const [loadErr, setLoadErr] = useState(false);
  // Which action is mid-redirect (disables buttons + shows spinner).
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    if (!open || tiers) return;
    let cancelled = false;
    fetchTierConfigurations()
      .then((t) => {
        if (cancelled) return;
        // Show only purchasable, non-legacy plans, cheapest → priciest.
        const visible = t
          .filter(
            (x) =>
              x.tier_key !== "none" &&
              !/legacy/i.test(x.display_name ?? "") &&
              (x.tier_key === "free" || (x.price_ids?.length ?? 0) > 0),
          )
          .sort((a, b) => (a.monthly_credits ?? 0) - (b.monthly_credits ?? 0));
        setTiers(visible);
      })
      .catch(() => !cancelled && setLoadErr(true));
    return () => {
      cancelled = true;
    };
  }, [open, tiers]);

  async function run(key: string, fn: () => Promise<string>) {
    if (!token) {
      toast.error("Please sign in first.");
      return;
    }
    setBusy(key);
    try {
      goTo(await fn()); // full-page redirect to Stripe; component unmounts
    } catch (e) {
      setBusy(null);
      toast.error(e instanceof Error ? e.message : "Couldn't reach billing. Try again.");
    }
  }

  const onUpgrade = (tierKey: string) =>
    run(`tier:${tierKey}`, () => createCheckoutSession(token!, { tierKey, returnPath }));
  const onTopUp = (amount: number) =>
    run(`topup:${amount}`, () => purchaseCredits(token!, { amount, returnPath }));
  const onManage = () =>
    run("portal", () => createPortalSession(token!, { returnPath }));

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-[100] bg-black/70 backdrop-blur-sm motion-safe:animate-in fade-in-0" />
        <Dialog.Content
          style={{ ["--accent" as string]: ACCENT_HSL } as React.CSSProperties}
          className="fixed left-1/2 top-1/2 z-[101] w-[min(92vw,560px)] max-h-[88vh] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-2xl border border-white/10 bg-[hsl(0_0%_6%)] p-6 shadow-2xl shadow-black/60 motion-safe:animate-in fade-in-0 zoom-in-95"
        >
          <div className="mb-5 flex items-start justify-between gap-4">
            <div>
              <Dialog.Title className="text-[15px] font-semibold text-slate-100">
                Membership & credits
              </Dialog.Title>
              <Dialog.Description className="mt-1 text-[12px] text-slate-400">
                {currentTier ? (
                  <>
                    Current plan{" "}
                    <span style={{ color: "hsl(var(--accent))" }}>{currentTier}</span>
                    {balance != null && (
                      <>
                        {" · "}
                        <span className="font-mono text-slate-300">
                          {balance.toLocaleString()} credits
                        </span>
                      </>
                    )}
                  </>
                ) : (
                  "Choose a plan or top up credits."
                )}
              </Dialog.Description>
            </div>
            <Dialog.Close
              className="rounded-md p-1 text-slate-500 hover:bg-white/5 hover:text-slate-200"
              aria-label="Close"
            >
              <X size={16} />
            </Dialog.Close>
          </div>

          {/* Plans */}
          <section className="mb-6">
            <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              Plans
            </h3>
            {loadErr && (
              <p className="text-[12px] text-slate-500">
                Couldn&apos;t load plans.{" "}
                <a
                  href="https://www.leil.app"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline"
                >
                  Open leil.app
                </a>
              </p>
            )}
            {!loadErr && !tiers && (
              <div className="flex items-center gap-2 py-4 text-[12px] text-slate-500">
                <Loader2 size={13} className="animate-spin" /> Loading plans…
              </div>
            )}
            <div className="grid gap-2">
              {tiers?.map((t) => {
                const isCurrent =
                  !!currentTier &&
                  t.display_name?.toLowerCase() === currentTier.toLowerCase();
                const key = `tier:${t.tier_key}`;
                return (
                  <div
                    key={t.tier_key}
                    className="flex items-center justify-between gap-3 rounded-lg border border-white/[0.07] bg-white/[0.02] px-4 py-3"
                  >
                    <div>
                      <p className="text-[13px] font-medium text-slate-100">
                        {t.display_name}
                        {MONTHLY_USD[t.tier_key] != null && (
                          <span className="ml-1.5 text-[11px] font-normal text-slate-400">
                            ${MONTHLY_USD[t.tier_key]}/mo
                          </span>
                        )}
                      </p>
                      <p className="text-[11px] text-slate-500">
                        {t.monthly_credits > 0
                          ? `${(t.monthly_credits * 100).toLocaleString()} credits / mo`
                          : "Pay as you go"}
                      </p>
                    </div>
                    {isCurrent ? (
                      <span className="flex items-center gap-1 text-[11px] font-medium text-slate-400">
                        <Check size={12} /> Current
                      </span>
                    ) : t.tier_key === "free" ? null : (
                      <button
                        onClick={() => onUpgrade(t.tier_key)}
                        disabled={busy !== null}
                        className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[12px] font-semibold transition-all disabled:opacity-50"
                        style={{
                          background: "hsl(var(--accent) / 0.18)",
                          color: "hsl(var(--accent))",
                          border: "1px solid hsl(var(--accent) / 0.4)",
                        }}
                      >
                        {busy === key ? (
                          <Loader2 size={12} className="animate-spin" />
                        ) : (
                          <Zap size={12} />
                        )}
                        Choose
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          </section>

          {/* Top up */}
          <section className="mb-6">
            <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              Top up credits
            </h3>
            <div className="flex flex-wrap gap-2">
              {TOPUP_AMOUNTS.map((amount) => {
                const key = `topup:${amount}`;
                return (
                  <button
                    key={amount}
                    onClick={() => onTopUp(amount)}
                    disabled={busy !== null}
                    className="flex items-center gap-1.5 rounded-md border border-white/[0.08] bg-white/[0.03] px-3 py-1.5 text-[12px] font-medium text-slate-200 transition-colors hover:bg-white/[0.06] disabled:opacity-50"
                  >
                    {busy === key && <Loader2 size={12} className="animate-spin" />}
                    ${amount}
                    <span className="text-slate-500">
                      · {(amount * 100).toLocaleString()} cr
                    </span>
                  </button>
                );
              })}
            </div>
          </section>

          {/* Manage */}
          <section className="border-t border-white/[0.06] pt-4">
            <button
              onClick={onManage}
              disabled={busy !== null}
              className="flex w-full items-center justify-between gap-2 rounded-md px-1 py-1 text-[12px] text-slate-300 transition-colors hover:text-white disabled:opacity-50"
            >
              <span>Manage / cancel subscription, update payment method</span>
              {busy === "portal" ? (
                <Loader2 size={13} className="animate-spin text-slate-500" />
              ) : (
                <ExternalLink size={12} className="text-slate-500" />
              )}
            </button>
          </section>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
