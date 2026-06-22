"use client";
/**
 * CalibrationBadge — tone-coded calibration label shown on every
 * simulation result (UI/UX audit Tier B3).
 *
 * Promotes the honesty contract from 8px gray text to a glanceable,
 * color-coded badge whose hover tooltip explains exactly how far to
 * trust the number.  Tone + meaning come from the single glossary
 * source of truth so the badge and the glossary modal never drift.
 */
import { CALIBRATION_LABELS } from "@/lib/glossary";
import { type Tone } from "@/lib/theme";
import { Badge } from "@/components/ui/Badge";

export function CalibrationBadge({
  source,
  calibration,
}: {
  source?: string;
  calibration?: string;
}) {
  const entry = CALIBRATION_LABELS.find((c) => c.label === calibration);
  const tone = (entry?.tone ?? "slate") as Tone;
  const title = entry
    ? entry.meaning
    : "Calibration level for this result — how far to trust the absolute numbers.";

  return (
    <span className="inline-flex items-center gap-1 align-middle" title={title}>
      {source && <span className="text-[8px] font-mono text-slate-600">{source}</span>}
      {calibration && (
        <Badge tone={tone} title={title} className="cursor-help">
          {calibration}
        </Badge>
      )}
    </span>
  );
}
