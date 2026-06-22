/**
 * SectionLabel — the small uppercase tone-coded label that heads a card
 * sub-section ("Analysis", "Recommended schedule", "AI Insights"…).
 * Part of the Tier C component kit.
 *
 * Sizes are looked up as FULL literal classes (never interpolated) so the
 * Tailwind JIT scanner detects them and there's no class-conflict.
 */
import { type ReactNode } from "react";
import { TONE_TEXT, type Tone } from "@/lib/theme";

const SIZE: Record<"xs" | "sm", string> = {
  xs: "text-[8.5px]",
  sm: "text-[9px]",
};

export function SectionLabel({
  tone,
  size = "xs",
  className = "",
  children,
}: {
  tone: Tone;
  size?: "xs" | "sm";
  className?: string;
  children: ReactNode;
}) {
  return (
    <span className={`${SIZE[size]} font-semibold uppercase tracking-wider ${TONE_TEXT[tone]} ${className}`}>
      {children}
    </span>
  );
}
