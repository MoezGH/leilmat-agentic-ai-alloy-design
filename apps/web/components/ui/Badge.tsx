/**
 * Badge — the small tone-coded chip used across cards, the glossary and
 * status indicators (UI/UX audit Tier C component kit).
 *
 * Default styling matches the calibration badge (8px mono, uppercase,
 * rounded, bordered).  Pass `className` to tweak size/padding for a
 * specific site without forking the colour logic.
 */
import { type ReactNode } from "react";
import { TONE_SOFT, type Tone } from "@/lib/theme";

export function Badge({
  tone = "slate",
  title,
  className = "",
  children,
}: {
  tone?: Tone;
  title?: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <span
      title={title}
      className={`inline-flex items-center text-[8px] font-mono font-semibold uppercase tracking-wider px-1 py-0.5 rounded border ${TONE_SOFT[tone]} ${className}`}
    >
      {children}
    </span>
  );
}
