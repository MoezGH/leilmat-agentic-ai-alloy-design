/**
 * Design tokens (UI/UX audit Tier C — component kit).
 *
 * Single source of truth for the semantic "tone" colour-coding of cards,
 * badges and the glossary (calibration labels, source chips, status pills…).
 * Values are FULL literal Tailwind class strings so the JIT scanner detects
 * them — never build a class name by interpolating a tone fragment.
 *
 * The INFINITE cockpit rule: colour means status.  Three tones carry it —
 * `emerald` (ok), `amber` (check this), `rose` (failed) — and everything else
 * is neutral, so a chip that says "RF/AL" or "KWN" reads as a label, not as an
 * alarm.  The tone NAMES are kept (callers pass them); only what they look
 * like changed.  The brand red is never a tone: it is the one primary action.
 */

export type Tone =
  | "emerald"
  | "sky"
  | "amber"
  | "slate"
  | "rose"
  | "violet"
  | "indigo"
  | "cyan"
  | "pink"
  | "fuchsia";

const NEUTRAL_SOFT = "text-fg bg-fg/10 border-line";

/** Soft chip styling — text + translucent fill + border, for badges/pills. */
export const TONE_SOFT: Record<Tone, string> = {
  emerald: "text-ok bg-ok/10 border-ok/30",
  amber:   "text-warn bg-warn/10 border-warn/30",
  rose:    "text-bad bg-bad/10 border-bad/30",
  slate:   "text-muted bg-fg/[0.04] border-line",
  sky:     NEUTRAL_SOFT,
  violet:  NEUTRAL_SOFT,
  indigo:  NEUTRAL_SOFT,
  cyan:    NEUTRAL_SOFT,
  pink:    NEUTRAL_SOFT,
  fuchsia: NEUTRAL_SOFT,
};

/** Text colour only — for section labels / headings on a transparent bg. */
export const TONE_TEXT: Record<Tone, string> = {
  emerald: "text-ok",
  amber:   "text-warn",
  rose:    "text-bad",
  slate:   "text-muted",
  sky:     "text-fg",
  violet:  "text-fg",
  indigo:  "text-fg",
  cyan:    "text-fg",
  pink:    "text-fg",
  fuchsia: "text-fg",
};
