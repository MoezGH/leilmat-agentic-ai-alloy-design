/**
 * RateLimitedNote — the "busy / rate-limited" notice shown in a cloud
 * card's result slot when the compute queue returns 429.  Extracted from
 * three byte-identical copies across the cloud cards (Tier C component kit).
 */
import { SectionLabel } from "@/components/ui/SectionLabel";

export function RateLimitedNote() {
  return (
    <div className="px-2 py-1.5 rounded bg-amber-500/[0.06] border border-amber-500/25">
      <SectionLabel tone="amber" size="sm">⚠ Busy / rate-limited</SectionLabel>
      <p className="text-[9px] text-slate-400 leading-snug mt-0.5">
        The cloud-compute queue is full or rate-limited. Try again shortly.
      </p>
    </div>
  );
}
