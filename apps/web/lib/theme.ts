/**
 * Design tokens (UI/UX audit Tier C — component kit).
 *
 * Single source of truth for the semantic "tone" colour-coding that was
 * previously duplicated inline across cards, badges and the glossary
 * (calibration labels, source chips, status pills…).  Values are FULL
 * literal Tailwind class strings so the JIT scanner detects them — never
 * build a class name by interpolating a tone fragment.
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

/** Soft chip styling — text + translucent fill + border, for badges/pills. */
export const TONE_SOFT: Record<Tone, string> = {
  emerald: "text-emerald-300 bg-emerald-500/10 border-emerald-500/30",
  sky:     "text-sky-300 bg-sky-500/10 border-sky-500/30",
  amber:   "text-amber-300 bg-amber-500/10 border-amber-500/30",
  slate:   "text-slate-400 bg-white/[0.04] border-white/[0.12]",
  rose:    "text-rose-300 bg-rose-500/10 border-rose-500/30",
  violet:  "text-violet-300 bg-violet-500/10 border-violet-500/30",
  indigo:  "text-indigo-300 bg-indigo-500/10 border-indigo-500/30",
  cyan:    "text-cyan-300 bg-cyan-500/10 border-cyan-500/30",
  pink:    "text-pink-300 bg-pink-500/10 border-pink-500/30",
  fuchsia: "text-fuchsia-300 bg-fuchsia-500/10 border-fuchsia-500/30",
};

/** Text colour only — for section labels / headings on a transparent bg. */
export const TONE_TEXT: Record<Tone, string> = {
  emerald: "text-emerald-300",
  sky:     "text-sky-300",
  amber:   "text-amber-300",
  slate:   "text-slate-400",
  rose:    "text-rose-300",
  violet:  "text-violet-300",
  indigo:  "text-indigo-300",
  cyan:    "text-cyan-300",
  pink:    "text-pink-300",
  fuchsia: "text-fuchsia-300",
};
