"use client";
import dynamic from "next/dynamic";
import { useCanvasStore } from "@/lib/store";
import { useState, useCallback, useEffect, useRef } from "react";
import { toast } from "sonner";

import { useAuthFetch } from "@/lib/api/client";
import { KWNPlayback, type KWNTrajectory } from "@/components/KWNPlayback";

// Mini-sim #2 — 1-D diffusion couple.  Defined in its own file because
// its surface (system catalogue + Crank-Nicolson backend) is independent
// of the property dashboard's composition prop.  Re-exported here so
// canvas/page.tsx can pull all process-simulation cards from one barrel.
export { DiffusionCard } from "@/components/DiffusionCard";


// ─────────────────────────────────────────────────────────────────────
// coerceNum — tolerant value→number for LLM "Apply" executables.
//
// The interpret LLMs emit ``executable.value`` inconsistently: sometimes
// a clean number (4, 1.5), sometimes a numeric string ("4", "1.5"),
// sometimes a string with units or words baked in ("16 h", "N=4",
// "four-fold", "1.5x").  The original handlers did ``Number(ex.value)``
// then ``Number.isFinite`` — which silently rejected every string form,
// so clicking Apply did nothing with no feedback.  This was the root
// cause of "the Apply buttons don't work."
//
// coerceNum handles all of those: word-numbers (one..eight, incl. the
// "-fold" suffix the crystal-symmetry recs use), then the first numeric
// token found anywhere in the string.  Returns null only when there's
// genuinely no number to extract.
// ─────────────────────────────────────────────────────────────────────
const _WORD_NUM: Record<string, number> = {
  one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8,
};

export function coerceNum(value: unknown): number | null {
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value !== "string") return null;
  const s = value.trim().toLowerCase();
  if (!s) return null;

  // Word-number (handles "four", "four-fold", "fourfold", "six fold").
  const wordKey = s.replace(/[-\s]?fold\b/, "").replace(/[-\s]+/g, "");
  if (wordKey in _WORD_NUM) return _WORD_NUM[wordKey];

  // First numeric token anywhere in the string: "16 h" → 16, "N=4" → 4,
  // "1.5x" → 1.5, "-0.3" → -0.3.
  const m = s.match(/-?\d+(?:\.\d+)?/);
  if (m) {
    const n = Number(m[0]);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

/**
 * Helper: cards read their previously-saved result from the store on
 * mount, and write back via setSimulationResult after a fresh fetch
 * lands.  useSessionPersistence packs the whole simulationResults
 * object into Supabase under the row's simulation_results JSONB.
 */
function useCardPersistence<T>(bucket:
  | "phase" | "scheil" | "ttt" | "microstructure" | "precipitation"
  | "grain_structure" | "grain_growth" | "stress_strain" | "aging" | "inverse"
) {
  const saved = useCanvasStore((s) => s.simulationResults[bucket]) ?? {};
  const set   = useCanvasStore((s) => s.setSimulationResult);
  return {
    savedResult:         saved.result as T | undefined,
    savedInterpretation: saved.interpretation,
    persistResult:         (result: T) => set(bucket, { result }),
    persistInterpretation: (interpretation: unknown) =>
                              set(bucket, { interpretation }),
  };
}

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

// Backend origin — must match the BASE in apps/web/lib/api.ts.  Without this,
// the sprint cards below would call /api/... on the Next.js dev server
// (port 4000) which 404s; we want them to hit FastAPI on port 8000.
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface PropertyDetail {
  value: number | null;
  uncertainty?: number;
  source?: string;
  error?: string;
  rating?: string;
  rate_range_text?: string;
  pren?: number;
  drivers_positive?: { element: string; contribution: number }[];
  drivers_negative?: { element: string; contribution: number }[];
  e_voigt_GPa?: number;
  e_reuss_GPa?: number;
  // ── Conformal prediction interval (Track C) ──
  ci_low?: number;
  ci_high?: number;
  coverage?: number | null;       // e.g. 0.9 for a 90% interval; null = no guarantee
  calibration?: string;           // "conformal" | "tree_std_heuristic" | "by_definition" | "configurational_only"
  n_calibration?: number;
  // ── Sprint 4: temper that was used for the prediction ──
  temper_used?: string;
  // ── Hall-Petch grain-size overlay on yield strength (literature-correlation) ──
  hall_petch?: {
    delta_MPa: number;
    grain_size_um: number;
    d_ref_um: number;
    k_y_MPa_sqrt_um: number;
    family: string;
    calibration: string;
    note: string;
  };
  // ── Orowan precipitation overlay on yield strength (literature-correlation) ──
  precipitation?: {
    delta_MPa: number;
    orowan_sim_MPa: number;
    orowan_baseline_MPa: number;
    vf: number;
    r_nm: number;
    family: string;
    temper: string | null;
    calibration: string;
    note: string;
  };
}

interface PhaseWarning {
  level: "critical" | "warning" | "info";
  code: string;
  message: string;
  element: string;
}

interface PhaseStability {
  warnings: PhaseWarning[];
  source: string;
  n_warnings: number;
}

interface HullDistance {
  e_above_hull: number | null;
  e_above_hull_meV?: number;
  stability: "stable" | "metastable" | "unstable" | "unknown";
  note: string;
  source?: string;
  error?: string;
}

interface PropertyDashboardProps {
  composition: Record<string, number>;
  properties: Record<string, number | null> & {
    _details?: Record<string, PropertyDetail>;
    phase_stability?: PhaseStability;
  };
  hullDistance?: HullDistance | null;
  /** Optional: live load state of M3GNet + its conformal calibrator. When
   *  not "ready", the formation-energy property card shows a small spinner
   *  instead of (silently) falling back to the Miedema heuristic. */
  m3gnetState?: "loading" | "fitting_calibrator" | "ready" | "failed" | null;
}

const DISPLAY_PROPS = [
  { key: "density_g_cm3",                 label: "Density",          unit: "g/cm³",   short: "Density",   scale: 1     },
  { key: "elastic_modulus_GPa",           label: "Young's Modulus",  unit: "GPa",     short: "E",         scale: 0.003 },
  { key: "melting_point_K",               label: "Melting Pt",       unit: "K",       short: "Melt Pt",   scale: 0.001 },
  { key: "yield_strength_MPa",            label: "Yield Strength",   unit: "MPa",     short: "YS",        scale: 0.001 },
  { key: "hardness_HV",                   label: "Hardness",         unit: "HV",      short: "HV",        scale: 0.01  },
  { key: "fatigue_endurance_MPa",         label: "Fatigue σₑ",       unit: "MPa",     short: "σₑ",        scale: 0.001 },
  { key: "formation_energy_eV_per_atom",  label: "Formation E",      unit: "eV/atom", short: "ΔHf",       scale: 1     },
  { key: "electronegativity_mean",        label: "Electroneg.",      unit: "",        short: "χ",         scale: 1     },
  { key: "valence_electrons_mean",        label: "Valence",          unit: "e⁻",      short: "Val e⁻",    scale: 0.1   },
];

const CORROSION_COLOR: Record<string, { bg: string; text: string; border: string }> = {
  "Excellent": { bg: "bg-emerald-500/15", text: "text-emerald-300", border: "border-emerald-500/30" },
  "Good":      { bg: "bg-lime-500/15",    text: "text-lime-300",    border: "border-lime-500/30" },
  "Fair":      { bg: "bg-amber-500/15",   text: "text-amber-300",   border: "border-amber-500/30" },
  "Poor":      { bg: "bg-rose-500/15",    text: "text-rose-300",    border: "border-rose-500/30" },
};

const HULL_COLOR: Record<string, { bg: string; text: string; border: string; dot: string }> = {
  stable:    { bg: "bg-emerald-500/15", text: "text-emerald-300", border: "border-emerald-500/30", dot: "bg-emerald-400" },
  metastable:{ bg: "bg-amber-500/15",   text: "text-amber-300",   border: "border-amber-500/30",   dot: "bg-amber-400"   },
  unstable:  { bg: "bg-rose-500/15",    text: "text-rose-300",    border: "border-rose-500/30",    dot: "bg-rose-400"    },
  unknown:   { bg: "bg-slate-500/15",   text: "text-slate-400",   border: "border-slate-500/30",   dot: "bg-slate-500"   },
};

const WARN_COLOR: Record<string, { bg: string; text: string; border: string; dot: string }> = {
  critical: { bg: "bg-rose-500/10",   text: "text-rose-300",   border: "border-rose-500/30",   dot: "bg-rose-400"   },
  warning:  { bg: "bg-amber-500/10",  text: "text-amber-300",  border: "border-amber-500/30",  dot: "bg-amber-400"  },
  info:     { bg: "bg-sky-500/10",    text: "text-sky-300",    border: "border-sky-500/30",    dot: "bg-sky-400"    },
};

const SOURCE_COLOR: Record<string, string> = {
  calphad_pycalphad:       "bg-teal-500/15 text-teal-300 border-teal-500/30",
  calphad_no_tdb:          "bg-slate-500/15 text-slate-400 border-slate-500/30",
  scheil_gulliver:         "bg-cyan-500/15 text-cyan-300 border-cyan-500/30",
  scheil_no_tdb:           "bg-slate-500/15 text-slate-400 border-slate-500/30",
  ttt_kirkaldy_venugopalan:"bg-violet-500/15 text-violet-300 border-violet-500/30",
  phase_field_kwc:         "bg-pink-500/15 text-pink-300 border-pink-500/30",
  kwn_robson_2004:         "bg-blue-500/15 text-blue-300 border-blue-500/30",
  kwn_undersaturated:      "bg-slate-500/15 text-slate-400 border-slate-500/30",
  kwn_no_phase:            "bg-slate-500/15 text-slate-400 border-slate-500/30",
  kwn_solute_missing:      "bg-slate-500/15 text-slate-400 border-slate-500/30",
  rule_of_mixtures:        "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  magpie_mean:             "bg-sky-500/15 text-sky-300 border-sky-500/30",
  rf_matbench_steels:      "bg-violet-500/15 text-violet-300 border-violet-500/30",
  rf_aluminum:             "bg-lime-500/15 text-lime-300 border-lime-500/30",
  rf_titanium:             "bg-indigo-500/15 text-indigo-300 border-indigo-500/30",
  rf_nickel:               "bg-orange-500/15 text-orange-300 border-orange-500/30",
  m3gnet_dft:              "bg-fuchsia-500/15 text-fuchsia-300 border-fuchsia-500/30",
  miedema_heuristic:       "bg-amber-500/15 text-amber-300 border-amber-500/30",
  by_definition:           "bg-cyan-500/15 text-cyan-300 border-cyan-500/30",
  rf_no_match:             "bg-slate-500/15 text-slate-400 border-slate-500/30",
  tabor_rule:              "bg-teal-500/15 text-teal-300 border-teal-500/30",
  empirical_ratio_UTS:     "bg-pink-500/15 text-pink-300 border-pink-500/30",
  electrochemistry_rules:  "bg-yellow-500/15 text-yellow-300 border-yellow-500/30",
  pren_steels:             "bg-cyan-500/15 text-cyan-300 border-cyan-500/30",
  passive_film_rules:      "bg-teal-500/15 text-teal-300 border-teal-500/30",
  voigt_reuss_hill:        "bg-blue-500/15 text-blue-300 border-blue-500/30",
};

const SOURCE_LABEL: Record<string, string> = {
  calphad_pycalphad:       "CALPHAD",
  calphad_no_tdb:          "no TDB",
  scheil_gulliver:         "Scheil",
  scheil_no_tdb:           "no TDB",
  ttt_kirkaldy_venugopalan:"TTT/KV",
  phase_field_kwc:         "PF/KWC",
  kwn_robson_2004:         "KWN",
  kwn_undersaturated:      "KWN",
  kwn_no_phase:            "KWN",
  kwn_solute_missing:      "KWN",
  rule_of_mixtures:        "ROM",
  magpie_mean:             "Magpie",
  rf_matbench_steels:      "RF/Steels",
  rf_aluminum:             "RF/Al",
  rf_titanium:             "RF/Ti",
  rf_nickel:               "RF/Ni",
  m3gnet_dft:              "M3GNet",
  miedema_heuristic:       "Miedema",
  by_definition:           "Defined",
  rf_no_match:             "n/a",
  tabor_rule:              "Tabor",
  empirical_ratio_UTS:     "σ_e/UTS",
  electrochemistry_rules:  "Electrochem",
  pren_steels:             "PREN",
  passive_film_rules:      "TiO₂ film",
  voigt_reuss_hill:        "VRH",
};

// ── CALPHAD phase-assemblage types ───────────────────────────────────────────
interface PhaseAssemblageResult {
  phases: Record<string, number>;
  phase_comps?: Record<string, Record<string, number>>;
  T_K: number;
  T_C: number;
  source: string;
  tdb: string | null;
  chemsys: string;
  error: string | null;
}

// ── CALPHAD phase-assemblage card ─────────────────────────────────────────────
export function PhaseAssemblageCard({ composition }: { composition: Record<string, number> }) {
  const authFetch = useAuthFetch();
  const persist = useCardPersistence<PhaseAssemblageResult>("phase");
  const logAction = useCanvasStore((s) => s.logAction);
  const [T_C, setT_C] = useState(500);
  const [result, setResult] = useState<PhaseAssemblageResult | null>(
    persist.savedResult ?? null,
  );
  const [loading, setLoading] = useState(false);
  const [queried, setQueried] = useState(!!persist.savedResult);
  const [interpretation, setInterpretation] = useState<InterpretationPayload | null>(
    (persist.savedInterpretation as InterpretationPayload | undefined) ?? null,
  );
  const [interpreting, setInterpreting] = useState(false);
  const [rateLimited, setRateLimited] = useState(false);

  const fetchPhases = useCallback(async (temp: number) => {
    setLoading(true);
    setInterpretation(null);
    setRateLimited(false);
    try {
      const compStr = Object.entries(composition)
        .filter(([, v]) => v > 0)
        .map(([el, v]) => `${el}:${v.toFixed(2)}`)
        .join(",");
      const res = await fetch(
        `${BASE}/api/phase/equilibrium?composition=${encodeURIComponent(compStr)}&T_C=${temp}`
      );
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json() as PhaseAssemblageResult;
      setResult(data);
      setQueried(true);
      persist.persistResult(data);

      // Fire interpretation if we actually got phases back.
      if (data && !data.error && data.phases && Object.keys(data.phases).length > 0) {
        setInterpreting(true);
        authFetch("/api/phase/interpret", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            composition,
            T_K:    data.T_K ?? (temp + 273.15),
            phases: data.phases,
            sim_metadata: { tdb: data.tdb, chemsys: data.chemsys },
          }),
        })
          .then(r => r.ok ? r.json() : Promise.reject(r.status))
          .then((p: InterpretationPayload) => {
            setInterpretation(p);
            persist.persistInterpretation(p);
          })
          .catch((err) => {
            if (err === 429) setRateLimited(true);
            setInterpretation(null);
          })
          .finally(() => setInterpreting(false));
      }
    } catch {
      setResult(null);
    } finally {
      setLoading(false);
    }
  }, [composition, authFetch, persist]);

  const applyRec = useCallback((ex?: { type: string; value: unknown }, label?: string) => {
    if (!ex) { toast.error("This suggestion has no action attached."); return; }
    switch (ex.type) {
      case "set_temperature_C": {
        const v = coerceNum(ex.value);
        if (v == null || v < -200 || v > 1600) {
          toast.error(`Couldn't apply temperature "${String(ex.value)}".`);
          return;
        }
        setT_C(Math.round(v));
        fetchPhases(Math.round(v));
        const msg = `Equilibrium temperature → ${Math.round(v)} °C`;
        toast.success(msg);
        logAction({ source: "interpret_card", label: msg, detail: label, op: ex.type });
        return;
      }
      case "scroll_to_card":
        scrollToCard(String(ex.value));
        return;
      case "info_only":
        return;   // informational — intentionally no action
      default:
        toast.message("Noted — this suggestion is informational.");
        return;
    }
  }, [fetchPhases, logAction]);

  // Phase-fraction colour scale (teal palette, darkens for small fractions)
  const phaseColour = (frac: number) => {
    if (frac > 0.8) return "bg-teal-500/30 text-teal-200";
    if (frac > 0.4) return "bg-teal-500/20 text-teal-300";
    return "bg-teal-500/10 text-teal-400";
  };

  return (
    <div className="rounded-lg border border-white/8 overflow-hidden">
      <div className="flex items-center justify-between px-3 py-1.5 bg-teal-500/8 border-b border-teal-500/20">
        <span className="text-[9.5px] font-semibold uppercase tracking-wider text-slate-400">
          Equilibrium Phases
        </span>
        <span className="text-[8.5px] px-1.5 py-0.5 rounded border font-mono font-semibold uppercase tracking-wider bg-teal-500/15 text-teal-300 border-teal-500/30">
          CALPHAD
        </span>
      </div>

      {/* Temperature slider */}
      <div className="px-3 py-2 border-b border-white/[0.04]">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-[9px] text-slate-500 font-mono w-10 shrink-0">T (°C)</span>
          <input
            type="range"
            min={-200}
            max={1600}
            step={10}
            value={T_C}
            onChange={(e) => setT_C(Number(e.target.value))}
            className="flex-1 accent-teal-400 h-1"
          />
          <span className="text-[9.5px] font-mono text-teal-300 w-10 text-right shrink-0">
            {T_C}°C
          </span>
        </div>
        <button
          onClick={() => fetchPhases(T_C)}
          disabled={loading}
          className="w-full text-[9px] py-1 rounded bg-teal-500/15 text-teal-300 border border-teal-500/30 hover:bg-teal-500/25 transition-colors font-semibold uppercase tracking-wider disabled:opacity-50"
        >
          {loading ? "Calculating…" : "Calculate"}
        </button>
      </div>

      {/* Results */}
      {queried && (
        <div className="px-3 py-2">
          {result?.error && result.source === "calphad_no_tdb" ? (
            <p className="text-[9px] text-slate-500 font-mono leading-snug">
              No TDB for {result.chemsys || "this system"}.
              <br />Drop a compatible .tdb into models/calphad_tdbs/.
            </p>
          ) : result?.error ? (
            <p className="text-[9px] text-rose-400 font-mono">{result.error}</p>
          ) : result && Object.keys(result.phases).length > 0 ? (
            <>
              <div className="space-y-1">
                {Object.entries(result.phases)
                  .sort(([, a], [, b]) => b - a)
                  .map(([ph, frac]) => (
                    <div key={ph} className="flex items-center gap-2">
                      <div
                        className={`text-[8.5px] font-mono px-1.5 py-0.5 rounded font-semibold flex-1 truncate ${phaseColour(frac)}`}
                      >
                        {ph}
                      </div>
                      <div className="text-[9px] font-mono text-slate-400 w-10 text-right shrink-0">
                        {(frac * 100).toFixed(1)}%
                      </div>
                      <div className="w-12 bg-slate-800 rounded-full h-1.5 shrink-0">
                        <div
                          className="bg-teal-500 h-1.5 rounded-full"
                          style={{ width: `${Math.round(frac * 100)}%` }}
                        />
                      </div>
                    </div>
                  ))}
              </div>
              <p className="text-[8px] text-slate-600 font-mono mt-1.5">
                {result.tdb ?? "—"} · {result.T_K?.toFixed(0)} K
              </p>
            </>
          ) : (
            <p className="text-[9px] text-slate-600 font-mono">No phases returned.</p>
          )}

          {/* Layer 2: AI interpretation of the phase assemblage */}
          <AIInsightsBlock
            interpretation={interpretation}
            interpreting={interpreting}
            rateLimited={rateLimited}
            onApply={applyRec}
          />
        </div>
      )}
    </div>
  );
}

// ── Scheil-Gulliver solidification card (Sprint 2) ────────────────────────────
interface SolidificationResult {
  liquidus_K: number | null;
  solidus_K:  number | null;
  liquidus_C?: number;
  solidus_C?:  number;
  mushy_zone_K: number | null;
  active_phases: Record<string, number>;
  terminal_liquid: Record<string, number>;
  hot_tearing_index: number | null;
  source: string;
  tdb: string | null;
  error: string | null;
}

export function SolidificationCard({ composition }: { composition: Record<string, number> }) {
  const authFetch = useAuthFetch();
  const persist = useCardPersistence<SolidificationResult>("scheil");
  const [result, setResult] = useState<SolidificationResult | null>(
    persist.savedResult ?? null,
  );
  const [loading, setLoading] = useState(false);
  const [queried, setQueried] = useState(!!persist.savedResult);
  const [interpretation, setInterpretation] = useState<InterpretationPayload | null>(
    (persist.savedInterpretation as InterpretationPayload | undefined) ?? null,
  );
  const [interpreting, setInterpreting] = useState(false);
  const [rateLimited, setRateLimited] = useState(false);

  const fetchScheil = useCallback(async () => {
    setLoading(true);
    setInterpretation(null);
    setRateLimited(false);
    try {
      const compStr = Object.entries(composition)
        .filter(([, v]) => v > 0)
        .map(([el, v]) => `${el}:${v.toFixed(2)}`)
        .join(",");
      const res = await authFetch(`/api/phase/scheil?composition=${encodeURIComponent(compStr)}`);
      if (res.status === 429) {
        setRateLimited(true);
        setResult(null);
        return;
      }
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json() as SolidificationResult;
      setResult(data);
      setQueried(true);
      persist.persistResult(data);

      if (data && !data.error && data.liquidus_K != null) {
        setInterpreting(true);
        authFetch("/api/phase/interpret_scheil", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            composition,
            scheil_result: data,
            sim_metadata:  { tdb: data.tdb, source: data.source },
          }),
        })
          .then(r => r.ok ? r.json() : Promise.reject(r.status))
          .then((p: InterpretationPayload) => {
            setInterpretation(p);
            persist.persistInterpretation(p);
          })
          .catch((err) => {
            if (err === 429) setRateLimited(true);
            setInterpretation(null);
          })
          .finally(() => setInterpreting(false));
      }
    } catch {
      setResult(null);
    } finally {
      setLoading(false);
    }
  }, [composition]);

  const applyRec = useCallback((ex?: { type: string; value: unknown }) => {
    if (!ex) { toast.error("This suggestion has no action attached."); return; }
    if (ex.type === "scroll_to_card") { scrollToCard(String(ex.value)); return; }
    if (ex.type === "info_only") return;
    toast.message("Noted — this suggestion is informational.");
  }, []);

  // hot-tearing colour band
  const htBand = (idx: number | null) => {
    if (idx == null) return { text: "—", cls: "bg-slate-500/15 text-slate-400 border-slate-500/30" };
    if (idx <  30)   return { text: "low",    cls: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" };
    if (idx <  100)  return { text: "medium", cls: "bg-amber-500/15 text-amber-300 border-amber-500/30" };
    return                  { text: "high",   cls: "bg-rose-500/15 text-rose-300 border-rose-500/30" };
  };

  return (
    <div className="rounded-lg border border-white/8 overflow-hidden">
      <div className="flex items-center justify-between px-3 py-1.5 bg-cyan-500/8 border-b border-cyan-500/20">
        <span className="text-[9.5px] font-semibold uppercase tracking-wider text-slate-400">
          Solidification
        </span>
        <span className="text-[8.5px] px-1.5 py-0.5 rounded border font-mono font-semibold uppercase tracking-wider bg-cyan-500/15 text-cyan-300 border-cyan-500/30">
          Scheil
        </span>
      </div>

      <div className="px-3 py-2 border-b border-white/[0.04]">
        <button
          onClick={fetchScheil}
          disabled={loading}
          className="w-full text-[9px] py-1 rounded bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 hover:bg-cyan-500/25 transition-colors font-semibold uppercase tracking-wider disabled:opacity-50"
        >
          {loading ? "Simulating… (≈ 20 s)" : "Simulate freezing"}
        </button>
      </div>

      {queried && (
        <div className="px-3 py-2">
          {result?.error && result.source === "scheil_no_tdb" ? (
            <p className="text-[9px] text-slate-500 font-mono leading-snug">
              No TDB for this system.
            </p>
          ) : result?.error ? (
            <p className="text-[9px] text-rose-400 font-mono">{result.error}</p>
          ) : result?.liquidus_K != null ? (
            <>
              <div className="grid grid-cols-3 gap-2 mb-2">
                <div>
                  <p className="text-[8px] text-slate-500 uppercase tracking-wider">Liquidus</p>
                  <p className="text-[10.5px] font-mono text-cyan-300">{(result.liquidus_C ?? 0).toFixed(0)}°C</p>
                </div>
                <div>
                  <p className="text-[8px] text-slate-500 uppercase tracking-wider">Solidus</p>
                  <p className="text-[10.5px] font-mono text-cyan-300">{(result.solidus_C ?? 0).toFixed(0)}°C</p>
                </div>
                <div>
                  <p className="text-[8px] text-slate-500 uppercase tracking-wider">Mushy</p>
                  <p className="text-[10.5px] font-mono text-amber-300">{result.mushy_zone_K?.toFixed(0)} K</p>
                </div>
              </div>
              {/* Hot-tearing badge */}
              <div className="flex items-center gap-2 mb-1.5">
                <span className="text-[8.5px] text-slate-500 uppercase tracking-wider">Hot tearing</span>
                {(() => {
                  const b = htBand(result.hot_tearing_index);
                  return (
                    <span className={`text-[9px] px-1.5 py-0.5 rounded border font-mono font-semibold uppercase ${b.cls}`}>
                      {b.text} ({result.hot_tearing_index?.toFixed(0)})
                    </span>
                  );
                })()}
              </div>
              {/* Terminal phases */}
              {Object.keys(result.active_phases).length > 0 && (
                <div className="mt-1.5">
                  <p className="text-[8px] text-slate-500 uppercase tracking-wider mb-0.5">Active phases</p>
                  <div className="flex flex-wrap gap-1">
                    {Object.entries(result.active_phases)
                      .sort(([, a], [, b]) => b - a)
                      .slice(0, 6)
                      .map(([ph, frac]) => (
                        <span key={ph} className="text-[8.5px] font-mono px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
                          {ph} {(frac * 100).toFixed(1)}%
                        </span>
                      ))}
                  </div>
                </div>
              )}
              <p className="text-[8px] text-slate-600 font-mono mt-1.5">
                {result.tdb ?? "—"}
              </p>
            </>
          ) : (
            <p className="text-[9px] text-slate-600 font-mono">No solidification path returned.</p>
          )}

          {/* Layer 2: AI interpretation of the solidification path */}
          <AIInsightsBlock
            interpretation={interpretation}
            interpreting={interpreting}
            rateLimited={rateLimited}
            onApply={applyRec}
          />
        </div>
      )}
    </div>
  );
}


// ── Fe-C TTT card (Sprint 2) ──────────────────────────────────────────────────
interface TTTResult {
  value: object | null;
  noses_ttt?: {
    ferrite:  { T_nose_C: number; t_nose_s: number };
    pearlite: { T_nose_C: number; t_nose_s: number };
    bainite:  { T_nose_C: number; t_nose_s: number };
  };
  critical_T_C?: { Ae1: number; Ae3: number; Bs: number; Ms: number };
  astm_grain_number?: number;
  error: string | null;
}

export function TTTCard({ composition }: { composition: Record<string, number> }) {
  const persist = useCardPersistence<TTTResult>("ttt");
  const [result, setResult] = useState<TTTResult | null>(persist.savedResult ?? null);
  const [loading, setLoading] = useState(false);
  const [grainUm, setGrainUm] = useState(15);

  // Only render the card for Fe-rich compositions (it's a steel-only model)
  const fePct = composition["Fe"] ?? 0;
  if (fePct < 80) return null;

  const fetchTTT = useCallback(async () => {
    setLoading(true);
    try {
      const compStr = Object.entries(composition)
        .filter(([, v]) => v > 0)
        .map(([el, v]) => `${el}:${v.toFixed(2)}`)
        .join(",");
      const res = await fetch(
        `${BASE}/api/phase/ttt?composition=${encodeURIComponent(compStr)}&austenite_grain_um=${grainUm}`
      );
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json() as TTTResult;
      setResult(data);
      persist.persistResult(data);
    } catch {
      setResult(null);
    } finally {
      setLoading(false);
    }
  }, [composition, grainUm]);

  return (
    <div className="rounded-lg border border-white/8 overflow-hidden">
      <div className="flex items-center justify-between px-3 py-1.5 bg-violet-500/8 border-b border-violet-500/20">
        <span className="text-[9.5px] font-semibold uppercase tracking-wider text-slate-400">
          TTT diagram
        </span>
        <span className="text-[8.5px] px-1.5 py-0.5 rounded border font-mono font-semibold uppercase tracking-wider bg-violet-500/15 text-violet-300 border-violet-500/30">
          TTT/KV
        </span>
      </div>

      <div className="px-3 py-2 border-b border-white/[0.04]">
        <div className="flex items-center gap-2 mb-1.5">
          <span className="text-[9px] text-slate-500 font-mono w-14 shrink-0">grain (μm)</span>
          <input
            type="range" min={5} max={80} step={1}
            value={grainUm} onChange={(e) => setGrainUm(Number(e.target.value))}
            className="flex-1 accent-violet-400 h-1"
          />
          <span className="text-[9.5px] font-mono text-violet-300 w-8 text-right shrink-0">{grainUm}</span>
        </div>
        <button
          onClick={fetchTTT} disabled={loading}
          className="w-full text-[9px] py-1 rounded bg-violet-500/15 text-violet-300 border border-violet-500/30 hover:bg-violet-500/25 transition-colors font-semibold uppercase tracking-wider disabled:opacity-50"
        >
          {loading ? "Computing…" : "Compute TTT"}
        </button>
      </div>

      {result && (
        <div className="px-3 py-2">
          {result.error ? (
            <p className="text-[9px] text-slate-500 font-mono leading-snug">{result.error}</p>
          ) : result.noses_ttt && result.critical_T_C ? (
            <>
              <div className="grid grid-cols-4 gap-2 mb-1.5">
                <div><p className="text-[8px] text-slate-500 uppercase">Ae1</p><p className="text-[10px] font-mono text-violet-300">{result.critical_T_C.Ae1}°C</p></div>
                <div><p className="text-[8px] text-slate-500 uppercase">Ae3</p><p className="text-[10px] font-mono text-violet-300">{result.critical_T_C.Ae3}°C</p></div>
                <div><p className="text-[8px] text-slate-500 uppercase">Bs</p><p className="text-[10px] font-mono text-violet-300">{result.critical_T_C.Bs}°C</p></div>
                <div><p className="text-[8px] text-slate-500 uppercase">Ms</p><p className="text-[10px] font-mono text-amber-300">{result.critical_T_C.Ms}°C</p></div>
              </div>
              <div className="space-y-0.5 mt-1.5">
                <p className="text-[8px] text-slate-500 uppercase tracking-wider">TTT noses</p>
                {(["pearlite", "bainite"] as const).map((k) => {
                  const n = result.noses_ttt![k];
                  const tStr = n.t_nose_s < 1 ? `${(n.t_nose_s * 1000).toFixed(0)} ms` :
                               n.t_nose_s < 60 ? `${n.t_nose_s.toFixed(1)} s` :
                               n.t_nose_s < 3600 ? `${(n.t_nose_s/60).toFixed(1)} min` :
                               `${(n.t_nose_s/3600).toFixed(1)} h`;
                  return (
                    <div key={k} className="flex items-center justify-between text-[9.5px]">
                      <span className="text-slate-400 capitalize">{k}</span>
                      <span className="font-mono text-violet-300">{n.T_nose_C}°C / {tStr}</span>
                    </div>
                  );
                })}
              </div>
              <p className="text-[8px] text-slate-600 font-mono mt-1.5">
                ASTM G = {result.astm_grain_number}
              </p>
            </>
          ) : (
            <p className="text-[9px] text-slate-600 font-mono">No TTT data.</p>
          )}
        </div>
      )}
    </div>
  );
}

// ── Phase-field microstructure card (Sprint 2.5) ──────────────────────────────
interface MicrostructureFrame {
  step: number;
  sim_time: number;
  solid_fraction: number;
  png: string;
}
interface MicrostructureAnalysis {
  n_arms_detected:        number;
  n_arms_expected:        number;
  regime:                 string;
  side_branch_amplitude:  string;
  side_branch_amp_score:  number;
  tip_velocity_dimless:   number | null;
  symmetry_score:         number;
  circularity:            number;
  boundary_touching:      boolean;
  solid_fraction_final:   number;
  growth_phase:           string;
  quality_warnings?:      string[];
  source?:                string;
}
interface InterpretationRecommendation {
  title:     string;
  rationale: string;
  executable?: { type: string; value: unknown };
}
interface InterpretationPayload {
  interpretation:      string;
  regime_call:         string;
  recommendations:     InterpretationRecommendation[];
  honest_limitations:  string[];
  source:              string;
  calibration:         string;
}

/**
 * Reusable cyan "AI Insights" block — same visual treatment across every
 * sprint card (microstructure, CALPHAD, Scheil, KWN).  Renders:
 *   * interpretation paragraph + regime label
 *   * recommendation chips with Apply buttons (handler is card-specific)
 *   * collapsible honest_limitations list
 *   * provenance footer (source)
 *
 * Cards own their own analysis chip (numeric Layer-1 summary) above this
 * block — the chip's content is too domain-specific to factor out.
 */
function AIInsightsBlock({
  interpretation, interpreting, onApply, rateLimited = false,
}: {
  interpretation: InterpretationPayload | null;
  interpreting:   boolean;
  onApply:        (executable?: { type: string; value: unknown }, label?: string) => void;
  rateLimited?:   boolean;
}) {
  if (rateLimited) {
    return (
      <div className="mt-2 px-2 py-1.5 rounded bg-amber-500/[0.06] border border-amber-500/25">
        <div className="flex items-center justify-between">
          <span className="text-[9px] font-semibold uppercase tracking-wider text-amber-300">
            ⚠ Rate-limited
          </span>
          <span className="text-[8.5px] text-amber-300/70 font-mono">429</span>
        </div>
        <p className="text-[9.5px] text-slate-400 leading-snug mt-0.5">
          Too many AI requests in the last minute.  The numeric layer above
          is still accurate; try again in ~60 s for the AI narrative.
        </p>
      </div>
    );
  }
  if (interpreting) {
    return (
      <div className="mt-2 px-2 py-1.5 rounded bg-white/[0.03] border border-white/8">
        <span className="text-[9px] font-mono text-slate-500">
          AI interpreting…
        </span>
      </div>
    );
  }
  if (!interpretation) return null;
  return (
    <div className="mt-2 px-2 py-2 rounded bg-cyan-500/[0.05] border border-cyan-500/20">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[8.5px] font-semibold uppercase tracking-wider text-cyan-300">
          AI Insights
        </span>
        <span className="text-[8px] font-mono text-slate-500">
          {interpretation.regime_call}
        </span>
      </div>
      <p className="text-[10px] text-slate-300 leading-snug mb-2">
        {interpretation.interpretation}
      </p>
      {interpretation.recommendations.length > 0 && (
        <div className="space-y-1 mb-2">
          {interpretation.recommendations.map((r, i) => (
            <div
              key={i}
              className="flex items-start justify-between gap-2 px-1.5 py-1 rounded bg-white/[0.03] border border-white/8"
            >
              <div className="flex-1 min-w-0">
                <p className="text-[9.5px] font-semibold text-cyan-200 truncate">
                  {r.title}
                </p>
                <p className="text-[8.5px] text-slate-400 leading-snug">
                  {r.rationale}
                </p>
              </div>
              {r.executable && (
                <button
                  type="button"
                  onClick={() => onApply(r.executable, r.title)}
                  className="shrink-0 text-[8.5px] px-1.5 py-0.5 rounded bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 hover:bg-cyan-500/25 font-semibold uppercase tracking-wider"
                >
                  Apply
                </button>
              )}
            </div>
          ))}
        </div>
      )}
      {interpretation.honest_limitations.length > 0 && (
        <details className="mt-1 group">
          <summary className="text-[8.5px] text-slate-500 cursor-pointer hover:text-slate-400 select-none">
            Honest limitations ({interpretation.honest_limitations.length})
          </summary>
          <ul className="mt-1 space-y-0.5 pl-3">
            {interpretation.honest_limitations.map((l, i) => (
              <li key={i} className="text-[8.5px] text-slate-500 leading-snug list-disc">
                {l}
              </li>
            ))}
          </ul>
        </details>
      )}
      <p className="text-[8px] text-slate-600 mt-1.5 font-mono">
        source: {interpretation.source}
      </p>
    </div>
  );
}

/**
 * Shared scroll-to-card helper — every card's Apply handler uses it for
 * the "scroll_to_card" executable type.  Matches against heading text in
 * the canvas; tolerant of LLM-supplied aliases.
 */
function scrollToCard(key: string) {
  const norm = key.toLowerCase();
  const aliases: Record<string, string> = {
    phase: "phase", calphad: "phase", equilibrium: "phase",
    precipitation: "precipitation", kwn: "precipitation", aging: "precipitation",
    solidification: "solidification", scheil: "solidification",
    ttt: "ttt",
    microstructure: "microstructure", dendrite: "microstructure",
    cost: "cost",
    grain_growth: "grain growth", graingrowth: "grain growth", potts: "grain growth",
    grain_structure: "grain structure", neper: "grain structure", polycrystal: "grain structure",
    predict: "predict", properties: "predict",
  };
  const target_key = aliases[norm] || norm;
  const target = Array.from(document.querySelectorAll("h2, h3, span"))
    .find((el) => (el.textContent || "").toLowerCase().includes(target_key));
  if (target) {
    target.scrollIntoView({ behavior: "smooth", block: "center" });
    toast.success(`Jumped to the ${target_key} card`);
  } else {
    // No heading matched — tell the user instead of silently doing nothing.
    toast.message(`Open the ${target_key} card to follow this suggestion.`);
  }
}
interface MicrostructureResult {
  frames: MicrostructureFrame[];
  metadata: { grid: number; final_solid_fraction: number; cache_hit?: boolean };
  analysis?: MicrostructureAnalysis;
  source: string;
  calibration: string;
  warnings: string[];
  error?: string;
}

export function MicrostructureCard({
  composition, T_C,
}: { composition: Record<string, number>; T_C?: number | null }) {
  const authFetch = useAuthFetch();
  const logAction = useCanvasStore((s) => s.logAction);
  const persist = useCardPersistence<MicrostructureResult>("microstructure");
  const [result, setResult] = useState<MicrostructureResult | null>(
    persist.savedResult ?? null,
  );
  const [loading, setLoading] = useState(false);
  const [frameIdx, setFrameIdx] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [symmetry, setSymmetry] = useState(6);
  const [undercooling, setUndercooling] = useState(1.0);
  // Fidelity preset — controls grid resolution + step count.  Taichi runs
  // identical physics at each level; "fast" is for quick preview, "publication"
  // matches docs/sprint_2_6/dendrite_morphology.png.
  const [fidelity, setFidelity] = useState<"fast" | "standard" | "publication">("standard");
  // Layer-2 AI interpretation state — auto-fired after a simulation completes.
  const [interpretation, setInterpretation] = useState<InterpretationPayload | null>(
    (persist.savedInterpretation as InterpretationPayload | undefined) ?? null,
  );
  const [interpreting, setInterpreting] = useState(false);
  const [rateLimited, setRateLimited] = useState(false);
  const intervalRef = useRef<number | null>(null);

  const FIDELITY = {
    fast:        { grid:  80, n_steps:  5000, eta: "~10 s",  label: "Fast" },
    standard:    { grid: 120, n_steps: 15000, eta: "~30 s",  label: "Standard" },
    publication: { grid: 220, n_steps: 22000, eta: "~2 min", label: "Publication" },
  } as const;

  const fetchSim = useCallback(async () => {
    setLoading(true);
    setPlaying(false);
    setInterpretation(null);
    setRateLimited(false);
    try {
      const { grid, n_steps } = FIDELITY[fidelity];
      const res = await authFetch("/api/microstructure/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          composition, T_C,
          crystal_symmetry: symmetry,
          undercooling_factor: undercooling,
          grid, n_steps, n_frames: 12,
        }),
      });
      if (res.status === 429) {
        setRateLimited(true);
        setResult(null);
        return;
      }
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json() as MicrostructureResult;
      setResult(data);
      setFrameIdx(0);
      if (data.frames.length > 1) setPlaying(true);
      persist.persistResult(data);

      // Layer 2: auto-fire AI interpretation with the analysis block.
      // Runs in the background — the simulation frames render immediately.
      if (data.analysis && !data.error) {
        setInterpreting(true);
        authFetch("/api/microstructure/interpret", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            composition, temper: null, T_C,
            analysis:     data.analysis,
            sim_metadata: data.metadata,
          }),
        })
          .then(r => r.ok ? r.json() : Promise.reject(r.status))
          .then((p: InterpretationPayload) => {
            setInterpretation(p);
            persist.persistInterpretation(p);
          })
          .catch((err) => {
            if (err === 429) setRateLimited(true);
            setInterpretation(null);
          })
          .finally(() => setInterpreting(false));
      }
    } catch {
      setResult(null);
    } finally {
      setLoading(false);
    }
  }, [composition, T_C, symmetry, undercooling, fidelity]);

  /**
   * Wire a recommendation's "Apply" button to the card's local state.
   * Tolerant: unknown action types or malformed values become no-ops so
   * the LLM hallucinating a key doesn't break the UI.
   */
  const applyRecommendation = useCallback((ex?: { type: string; value: unknown }, label?: string) => {
    if (!ex) { toast.error("This suggestion has no action attached."); return; }
    const log = (msg: string, op: string) =>
      logAction({ source: "interpret_card", label: msg, detail: label, op });
    switch (ex.type) {
      case "set_undercooling_factor": {
        const v = coerceNum(ex.value);
        if (v == null || v < 0.5 || v > 2.0) {
          toast.error(`Couldn't apply ΔT factor "${String(ex.value)}" (range 0.5–2.0).`);
          return;
        }
        setUndercooling(v);
        toast.success(`ΔT factor → ${v}`);
        log(`ΔT factor → ${v}`, ex.type);
        return;
      }
      case "set_crystal_symmetry": {
        const raw = coerceNum(ex.value);
        const v = raw == null ? null : Math.round(raw);
        if (v == null || v < 3 || v > 8) {
          toast.error(`Couldn't apply symmetry "${String(ex.value)}" (range 3–8 fold).`);
          return;
        }
        setSymmetry(v);
        toast.success(`Crystal symmetry → ${v}-fold`);
        log(`Crystal symmetry → ${v}-fold`, ex.type);
        return;
      }
      case "set_fidelity": {
        const v = String(ex.value).toLowerCase().trim();
        // Tolerate LLM aliases: "high"/"max" → publication, "low"/"quick" → fast.
        const map: Record<string, "fast" | "standard" | "publication"> = {
          fast: "fast", low: "fast", quick: "fast",
          standard: "standard", med: "standard", medium: "standard",
          publication: "publication", high: "publication", max: "publication",
        };
        if (!map[v]) {
          toast.error(`Couldn't map fidelity "${String(ex.value)}".`);
          return;
        }
        setFidelity(map[v]);
        toast.success(`Fidelity → ${map[v]}`);
        log(`Fidelity → ${map[v]}`, ex.type);
        return;
      }
      case "scroll_to_card":
        scrollToCard(String(ex.value));
        return;
      case "info_only":
        return;
      default:
        toast.message("Noted — this suggestion is informational.");
        return;
    }
  }, [logAction]);

  // Frame animation loop (browser-side)
  useEffect(() => {
    if (intervalRef.current != null) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (!playing || !result || result.frames.length < 2) return;
    intervalRef.current = window.setInterval(() => {
      setFrameIdx((i) => {
        const next = i + 1;
        if (next >= result.frames.length) {
          setPlaying(false);
          return result.frames.length - 1;
        }
        return next;
      });
    }, 280);
    return () => {
      if (intervalRef.current != null) clearInterval(intervalRef.current);
    };
  }, [playing, result]);

  const currentFrame = result?.frames[frameIdx];

  return (
    <div className="rounded-lg border border-white/8 overflow-hidden">
      <div className="flex items-center justify-between px-3 py-1.5 bg-pink-500/8 border-b border-pink-500/20">
        <span className="text-[9.5px] font-semibold uppercase tracking-wider text-slate-400">
          Microstructure
        </span>
        <span className="text-[8.5px] px-1.5 py-0.5 rounded border font-mono font-semibold uppercase tracking-wider bg-pink-500/15 text-pink-300 border-pink-500/30">
          PF/KWC
        </span>
      </div>

      {/* Controls */}
      <div className="px-3 py-2 border-b border-white/[0.04] space-y-1.5">
        <div className="flex items-center gap-2">
          <span className="text-[9px] text-slate-500 font-mono w-14 shrink-0">N-fold</span>
          <input type="range" min={3} max={8} step={1}
            value={symmetry} onChange={(e) => setSymmetry(Number(e.target.value))}
            className="flex-1 accent-pink-400 h-1" />
          <span className="text-[9.5px] font-mono text-pink-300 w-8 text-right shrink-0">{symmetry}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[9px] text-slate-500 font-mono w-14 shrink-0">ΔT factor</span>
          <input type="range" min={0.5} max={2.0} step={0.1}
            value={undercooling} onChange={(e) => setUndercooling(Number(e.target.value))}
            className="flex-1 accent-pink-400 h-1" />
          <span className="text-[9.5px] font-mono text-pink-300 w-8 text-right shrink-0">{undercooling.toFixed(1)}</span>
        </div>
        {/* Fidelity preset — grid resolution + step count.  Taichi runs the
            same physics at every level; higher = bigger grid + more steps. */}
        <div className="flex items-center gap-2">
          <span className="text-[9px] text-slate-500 font-mono w-14 shrink-0">Fidelity</span>
          <div className="flex-1 grid grid-cols-3 gap-1">
            {(["fast", "standard", "publication"] as const).map((k) => {
              const active = fidelity === k;
              return (
                <button
                  key={k}
                  type="button"
                  onClick={() => setFidelity(k)}
                  className={`text-[8.5px] py-0.5 rounded border font-semibold uppercase tracking-wider transition-colors
                    ${active
                      ? "bg-pink-500/25 text-pink-200 border-pink-500/50"
                      : "bg-white/[0.03] text-slate-400 border-white/8 hover:bg-white/[0.07]"}`}
                  title={`${FIDELITY[k].grid}² grid · ${FIDELITY[k].n_steps.toLocaleString()} steps · ${FIDELITY[k].eta}`}
                >
                  {FIDELITY[k].label}
                </button>
              );
            })}
          </div>
        </div>
        <button
          onClick={fetchSim} disabled={loading}
          className="w-full text-[9px] py-1 rounded bg-pink-500/15 text-pink-300 border border-pink-500/30 hover:bg-pink-500/25 transition-colors font-semibold uppercase tracking-wider disabled:opacity-50"
        >
          {loading
            ? `Simulating Taichi KWC… (${FIDELITY[fidelity].eta})`
            : `Simulate crystal · ${FIDELITY[fidelity].label.toLowerCase()} (${FIDELITY[fidelity].eta})`}
        </button>
      </div>

      {/* Frame viewer */}
      {result && (
        <div className="px-3 py-2">
          {result.error ? (
            <p className="text-[9px] text-rose-400 font-mono">{result.error}</p>
          ) : currentFrame ? (
            <>
              <div className="relative aspect-square rounded overflow-hidden bg-[#000713]">
                <img
                  src={`data:image/png;base64,${currentFrame.png}`}
                  alt="dendrite frame"
                  className="w-full h-full object-cover"
                />
                <div className="absolute bottom-1 left-1 px-1.5 py-0.5 rounded bg-black/60 backdrop-blur-sm">
                  <span className="text-[8.5px] font-mono text-pink-300">
                    fs = {(currentFrame.solid_fraction * 100).toFixed(1)}%
                  </span>
                </div>
                <div className="absolute top-1 right-1 px-1.5 py-0.5 rounded bg-black/60 backdrop-blur-sm">
                  <span className="text-[8.5px] font-mono text-pink-300">
                    {frameIdx + 1}/{result.frames.length}
                  </span>
                </div>
              </div>
              {/* Playback controls */}
              <div className="flex items-center gap-1.5 mt-1.5">
                <button
                  onClick={() => setPlaying((p) => !p)}
                  className="text-[9px] px-2 py-0.5 rounded bg-pink-500/15 text-pink-300 border border-pink-500/30 hover:bg-pink-500/25 font-semibold uppercase"
                >
                  {playing ? "⏸" : "▶"}
                </button>
                <input
                  type="range" min={0} max={result.frames.length - 1} step={1}
                  value={frameIdx} onChange={(e) => { setFrameIdx(Number(e.target.value)); setPlaying(false); }}
                  className="flex-1 accent-pink-400 h-1"
                />
              </div>
              <p className="text-[8px] text-slate-600 mt-1.5 leading-snug">
                {result.warnings[0]}
              </p>

              {/* ── Layer 1: quantitative analysis chip ────────────────── */}
              {result.analysis && !("error" in result.analysis) && (
                <div className="mt-2 px-2 py-1.5 rounded bg-pink-500/[0.06] border border-pink-500/15">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[8.5px] font-semibold uppercase tracking-wider text-pink-300">
                      Analysis
                    </span>
                    <span className="text-[8px] font-mono text-slate-500">
                      {result.analysis.source}
                    </span>
                  </div>
                  <div className="text-[9px] font-mono text-slate-300 leading-tight">
                    <span className="text-pink-200">{result.analysis.n_arms_detected} arms</span>
                    <span className="text-slate-600"> · </span>
                    <span className="text-pink-200">{result.analysis.regime}</span>
                    <span className="text-slate-600"> · </span>
                    sb <span className="text-pink-200">{result.analysis.side_branch_amplitude}</span>
                    <span className="text-slate-600"> · </span>
                    sym <span className="text-pink-200">{result.analysis.symmetry_score.toFixed(2)}</span>
                    <span className="text-slate-600"> · </span>
                    circ <span className="text-pink-200">{result.analysis.circularity.toFixed(2)}</span>
                    {result.analysis.tip_velocity_dimless != null && (
                      <>
                        <span className="text-slate-600"> · </span>
                        v<sub>tip</sub> <span className="text-pink-200">
                          {result.analysis.tip_velocity_dimless.toFixed(1)}
                        </span>
                      </>
                    )}
                  </div>
                  {result.analysis.boundary_touching && (
                    <p className="text-[8.5px] text-amber-300 mt-1 leading-snug">
                      ⚠ boundary impingement — rerun at higher fidelity for reliable late-stage morphology
                    </p>
                  )}
                </div>
              )}

              {/* ── Layer 2: LLM interpretation + recommendations ───────── */}
              <AIInsightsBlock
                interpretation={interpretation}
                interpreting={interpreting}
                rateLimited={rateLimited}
                onApply={applyRecommendation}
              />
            </>
          ) : (
            <p className="text-[9px] text-slate-600 font-mono">No frames returned.</p>
          )}
        </div>
      )}
    </div>
  );
}

// ── Grain-structure card (Neper, cloud compute) ──────────────────────────────
// The FIRST polling card: it submits a Daytona-backed Neper job, then polls
// /api/compute/jobs/{id} until done.  Ships calibration="deterministic-geometry"
// — exact geometry/statistics, but sizes are dimensionless unless a physical
// domain (µm) is supplied (then µm + ASTM appear).
interface GrainHistogram { bin_edges: number[]; counts: number[] }
interface GrainResult {
  grain_count: number;
  morpho: string;
  dimensionality: string;
  mean_grain_size_normalized: number | null;
  std_grain_size_normalized?: number | null;
  size_distribution_normalized: GrainHistogram | null;
  png_base64: string | null;
  source: string;
  calibration: string;
  warnings: string[];
  domain_um?: number;
  mean_grain_size_um?: number;
  astm_grain_number?: number;
  size_distribution_um?: GrainHistogram;
}
interface GrainJob {
  job_id: string;
  status: "queued" | "running" | "done" | "failed" | "timeout";
  result: GrainResult | null;
  error: string | null;
}

function GrainHistogramBars({ hist }: { hist: GrainHistogram }) {
  const max = Math.max(1, ...hist.counts);
  return (
    <div className="flex items-end gap-px h-10 mt-1" aria-label="grain size distribution">
      {hist.counts.map((c, i) => (
        <div
          key={i}
          title={`${c} grains`}
          style={{ height: `${Math.round((c / max) * 100)}%` }}
          className="flex-1 bg-indigo-400/60 rounded-sm min-h-[2px]"
        />
      ))}
    </div>
  );
}

export function GrainStructureCard({
  composition,
}: { composition?: Record<string, number> }) {
  // Neper geometry is composition-independent, but the post-sim AI analysis
  // uses composition for alloy context (Hall-Petch, processing).
  const authFetch = useAuthFetch();
  const logAction = useCanvasStore((s) => s.logAction);
  const persist = useCardPersistence<GrainResult>("grain_structure");
  const [result, setResult] = useState<GrainResult | null>(persist.savedResult ?? null);
  const [loading, setLoading] = useState(false);
  const [phase, setPhase] = useState<"idle" | "submitting" | "running">("idle");
  const [error, setError] = useState<string | null>(null);
  const [rateLimited, setRateLimited] = useState(false);
  const [cloudEnabled, setCloudEnabled] = useState<boolean | null>(null);
  const [nGrains, setNGrains] = useState(100);
  const [morpho, setMorpho] = useState<"voronoi" | "graingrowth">("voronoi");
  const [domainUm, setDomainUm] = useState<string>("");  // optional, blank = dimensionless
  const [interpretation, setInterpretation] = useState<InterpretationPayload | null>(
    (persist.savedInterpretation as InterpretationPayload | undefined) ?? null,
  );
  const [interpreting, setInterpreting] = useState(false);
  const [aiRateLimited, setAiRateLimited] = useState(false);
  const pollRef = useRef<{ active: boolean }>({ active: false });

  // Post-sim "local AI" analysis: narrate the result + suggest next moves.
  const runInterpret = useCallback((res: GrainResult) => {
    if (!res || (res as { error?: unknown }).error) return;
    setInterpreting(true); setAiRateLimited(false); setInterpretation(null);
    authFetch("/api/compute/grain/interpret", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind: "grain_tessellate", result: res, composition: composition ?? null }),
    })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((p: InterpretationPayload) => { setInterpretation(p); persist.persistInterpretation(p); })
      .catch((err) => { if (err === 429) setAiRateLimited(true); setInterpretation(null); })
      .finally(() => setInterpreting(false));
  }, [authFetch, composition, persist]);

  // Is the cloud tier enabled? (DAYTONA_API_KEY set on the backend)
  useEffect(() => {
    let alive = true;
    authFetch("/api/compute/health")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (alive && d) setCloudEnabled(!!d.cloud_enabled); })
      .catch(() => { if (alive) setCloudEnabled(false); });
    return () => { alive = false; };
  }, [authFetch]);

  // Stop polling if the card unmounts.
  useEffect(() => () => { pollRef.current.active = false; }, []);

  const startPolling = useCallback((jobId: string) => {
    pollRef.current.active = true;
    setPhase("running");
    const startedAt = Date.now();
    const tick = async () => {
      if (!pollRef.current.active) return;
      if (Date.now() - startedAt > 12 * 60 * 1000) {
        setError("Timed out waiting for the grain job (12 min).");
        setLoading(false); setPhase("idle"); pollRef.current.active = false;
        return;
      }
      try {
        const res = await authFetch(`/api/compute/jobs/${jobId}`);
        if (!res.ok) throw new Error(`poll ${res.status}: ${await res.text()}`);
        const job = await res.json() as GrainJob;
        if (job.status === "done" && job.result) {
          setResult(job.result);
          persist.persistResult(job.result);
          setLoading(false); setPhase("idle"); pollRef.current.active = false;
          runInterpret(job.result);   // auto-analyse the fresh result
          return;
        }
        if (job.status === "failed" || job.status === "timeout") {
          setError(job.error?.split("\n")[0] || job.status);
          setLoading(false); setPhase("idle"); pollRef.current.active = false;
          return;
        }
        setTimeout(tick, 2500);  // queued/running → keep polling
      } catch (e) {
        setError(String(e));
        setLoading(false); setPhase("idle"); pollRef.current.active = false;
      }
    };
    setTimeout(tick, 1500);
  }, [authFetch, persist, runInterpret]);

  const submit = useCallback(async (override?: { n_grains?: number; morpho?: string; domain_um?: number }) => {
    setError(null); setRateLimited(false); setResult(null);
    setInterpretation(null); setAiRateLimited(false);
    setLoading(true); setPhase("submitting");
    const dom = override?.domain_um ?? (domainUm.trim() ? Number(domainUm) : null);
    const body = {
      n_grains: override?.n_grains ?? nGrains,
      morpho: override?.morpho ?? morpho,
      domain_um: dom && Number.isFinite(dom) && dom > 0 ? dom : null,
    };
    try {
      const res = await authFetch("/api/compute/grain/tessellate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.status === 503) { setCloudEnabled(false); setLoading(false); setPhase("idle"); return; }
      if (res.status === 429) { setRateLimited(true); setLoading(false); setPhase("idle"); return; }
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json() as { job_id: string };
      logAction({
        source: "grain_card",
        label: `Grain structure: ${body.n_grains} grains (${body.morpho})`,
        op: "simulate_grain_structure",
      });
      startPolling(data.job_id);
    } catch (e) {
      setError(String(e)); setLoading(false); setPhase("idle");
    }
  }, [authFetch, nGrains, morpho, domainUm, startPolling, logAction]);

  // Apply a "next move" pill. Paid re-runs (set_tessellate_params) ask for
  // confirmation first — each is a real cloud job; free/cross-card moves fire
  // immediately.
  const applyRec = useCallback((ex?: { type: string; value: unknown }, label?: string) => {
    if (!ex) { toast.error("This suggestion has no action attached."); return; }
    switch (ex.type) {
      case "set_tessellate_params": {
        const v = (ex.value ?? {}) as Record<string, unknown>;
        const next: { n_grains?: number; morpho?: "voronoi" | "graingrowth"; domain_um?: number } = {};
        if (typeof v.n_grains === "number" && Number.isFinite(v.n_grains))
          next.n_grains = Math.max(8, Math.min(1000, Math.round(v.n_grains)));
        if (v.morpho === "voronoi" || v.morpho === "graingrowth") next.morpho = v.morpho;
        if (typeof v.domain_um === "number" && Number.isFinite(v.domain_um) && v.domain_um > 0)
          next.domain_um = v.domain_um;
        if (Object.keys(next).length === 0) { toast.error("No valid parameters to apply."); return; }
        if (next.n_grains != null) setNGrains(next.n_grains);
        if (next.morpho) setMorpho(next.morpho);
        if (next.domain_um != null) setDomainUm(String(next.domain_um));
        const desc = [
          next.n_grains != null ? `${next.n_grains} grains` : null,
          next.morpho ?? null,
          next.domain_um != null ? `domain ${next.domain_um} µm` : null,
        ].filter(Boolean).join(", ");
        toast(`Re-run polycrystal (${desc})? ~1–2 min cloud job.`, {
          action: {
            label: "Run",
            onClick: () => {
              submit(next);
              logAction({ source: "interpret_card", label: `Re-run grain structure: ${desc}`, detail: label, op: "simulate_grain_structure" });
            },
          },
          cancel: { label: "Cancel", onClick: () => {} },
          duration: 8000,
        });
        return;
      }
      case "scroll_to_card":
        scrollToCard(String(ex.value));
        return;
      case "run_predict":
        window.dispatchEvent(new CustomEvent("leilmat:ai_command", { detail: { kind: "predict" } }));
        toast.success("Running property prediction…");
        return;
      case "info_only":
        return;   // informational — intentionally no action
      default:
        toast.message("Noted — this suggestion is informational.");
        return;
    }
  }, [submit, logAction]);

  // Let the Global-AI command bus trigger a run.
  useEffect(() => {
    const handler = (e: Event) => {
      const d = (e as CustomEvent).detail;
      if (!d || d.kind !== "grain_structure") return;
      const p = (d.parameters ?? {}) as Record<string, unknown>;
      if (typeof p.n_grains === "number") setNGrains(p.n_grains);
      if (typeof p.morpho === "string" && (p.morpho === "voronoi" || p.morpho === "graingrowth")) setMorpho(p.morpho);
      if (typeof p.domain_um === "number") setDomainUm(String(p.domain_um));
      submit(p as { n_grains?: number; morpho?: string; domain_um?: number });
    };
    window.addEventListener("leilmat:ai_command", handler);
    return () => window.removeEventListener("leilmat:ai_command", handler);
  }, [submit]);

  const hist = result?.size_distribution_um ?? result?.size_distribution_normalized ?? null;

  return (
    <div className="rounded-lg border border-white/8 overflow-hidden">
      <div className="flex items-center justify-between px-3 py-1.5 bg-indigo-500/8 border-b border-indigo-500/20">
        <span className="text-[9.5px] font-semibold uppercase tracking-wider text-slate-400">
          Grain structure
        </span>
        <span className="text-[8.5px] px-1.5 py-0.5 rounded border font-mono font-semibold uppercase tracking-wider bg-indigo-500/15 text-indigo-300 border-indigo-500/30">
          Neper · cloud
        </span>
      </div>

      {cloudEnabled === false ? (
        <div className="px-3 py-3">
          <p className="text-[9.5px] text-slate-500 leading-snug">
            Grain-structure generation runs on cloud compute, which is currently
            disabled on this deployment. It activates once the cloud key is configured.
          </p>
        </div>
      ) : (
        <>
          {/* Controls */}
          <div className="px-3 py-2 border-b border-white/[0.04] space-y-1.5">
            <div className="flex items-center gap-2">
              <span className="text-[9px] text-slate-500 font-mono w-16 shrink-0">Grains</span>
              <input type="range" min={8} max={1000} step={1}
                value={nGrains} onChange={(e) => setNGrains(Number(e.target.value))}
                className="flex-1 accent-indigo-400 h-1" />
              <span className="text-[9.5px] font-mono text-indigo-300 w-10 text-right shrink-0">{nGrains}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[9px] text-slate-500 font-mono w-16 shrink-0">Morphology</span>
              <div className="flex-1 grid grid-cols-2 gap-1">
                {(["voronoi", "graingrowth"] as const).map((k) => {
                  const active = morpho === k;
                  return (
                    <button key={k} type="button" onClick={() => setMorpho(k)}
                      className={`text-[8.5px] py-0.5 rounded border font-semibold uppercase tracking-wider transition-colors
                        ${active
                          ? "bg-indigo-500/25 text-indigo-200 border-indigo-500/50"
                          : "bg-white/[0.03] text-slate-400 border-white/8 hover:bg-white/[0.07]"}`}
                      title={k === "voronoi" ? "Fast Voronoi tessellation" : "Realistic grain-growth morphology (slower)"}
                    >
                      {k === "voronoi" ? "Voronoi" : "Grain-growth"}
                    </button>
                  );
                })}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[9px] text-slate-500 font-mono w-16 shrink-0">Domain µm</span>
              <input type="number" min={0} placeholder="optional → dimensionless"
                value={domainUm} onChange={(e) => setDomainUm(e.target.value)}
                className="flex-1 bg-white/[0.03] border border-white/8 rounded px-1.5 py-0.5 text-[9px] font-mono text-indigo-200 placeholder:text-slate-600" />
            </div>
            <button onClick={() => submit()} disabled={loading}
              className="w-full text-[9px] py-1 rounded bg-indigo-500/15 text-indigo-300 border border-indigo-500/30 hover:bg-indigo-500/25 transition-colors font-semibold uppercase tracking-wider disabled:opacity-50">
              {loading
                ? (phase === "submitting" ? "Submitting to cloud…" : "Running in cloud…")
                : "Generate polycrystal"}
            </button>
            {loading && (
              <p className="text-[8px] text-slate-600 leading-snug">
                First run builds Neper in the sandbox (~1–2 min); later runs are faster.
              </p>
            )}
          </div>

          {/* Result */}
          {(result || error || rateLimited) && (
            <div className="px-3 py-2">
              {rateLimited ? (
                <div className="px-2 py-1.5 rounded bg-amber-500/[0.06] border border-amber-500/25">
                  <span className="text-[9px] font-semibold uppercase tracking-wider text-amber-300">⚠ Busy / rate-limited</span>
                  <p className="text-[9px] text-slate-400 leading-snug mt-0.5">
                    The cloud-compute queue is full or rate-limited. Try again shortly.
                  </p>
                </div>
              ) : error ? (
                <p className="text-[9px] text-rose-400 font-mono leading-snug">{error}</p>
              ) : result ? (
                <>
                  {result.png_base64 && (
                    <div className="relative aspect-square rounded overflow-hidden bg-[#05060d]">
                      <img src={`data:image/png;base64,${result.png_base64}`}
                        alt="synthetic polycrystal" className="w-full h-full object-contain" />
                    </div>
                  )}
                  <div className="mt-2 px-2 py-1.5 rounded bg-indigo-500/[0.06] border border-indigo-500/15">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[8.5px] font-semibold uppercase tracking-wider text-indigo-300">Analysis</span>
                      <span className="text-[8px] font-mono text-slate-500">{result.source} · {result.calibration}</span>
                    </div>
                    <div className="text-[9px] font-mono text-slate-300 leading-tight">
                      <span className="text-indigo-200">{result.grain_count} grains</span>
                      <span className="text-slate-600"> · </span>
                      <span className="text-indigo-200">{result.morpho}</span>
                      <span className="text-slate-600"> · </span>
                      <span className="text-indigo-200">{result.dimensionality}</span>
                      {result.mean_grain_size_um != null ? (
                        <>
                          <span className="text-slate-600"> · </span>
                          d̄ <span className="text-indigo-200">{result.mean_grain_size_um} µm</span>
                          {result.astm_grain_number != null && (
                            <>
                              <span className="text-slate-600"> · </span>
                              ASTM <span className="text-indigo-200">{result.astm_grain_number}</span>
                            </>
                          )}
                        </>
                      ) : result.mean_grain_size_normalized != null ? (
                        <>
                          <span className="text-slate-600"> · </span>
                          d̄ <span className="text-indigo-200">{result.mean_grain_size_normalized}</span>
                          <span className="text-slate-500"> (norm.)</span>
                        </>
                      ) : null}
                    </div>
                    {hist && <GrainHistogramBars hist={hist} />}
                  </div>
                  {result.warnings?.length > 0 && (
                    <p className="text-[8px] text-slate-500 mt-1.5 leading-snug">{result.warnings[0]}</p>
                  )}
                  <AIInsightsBlock
                    interpretation={interpretation}
                    interpreting={interpreting}
                    onApply={applyRec}
                    rateLimited={aiRateLimited}
                  />
                </>
              ) : null}
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── Stress–strain card (DAMASK crystal-plasticity FFT, cloud compute) ─────────
// Generates a synthetic Voronoi polycrystal RVE, pulls it in uniaxial tension
// with a phenopowerlaw crystal-plasticity phase (literature slip params), and
// returns the homogenized flow curve. calibration="literature-correlation":
// the curve SHAPE + hardening + modulus are physical; absolute stress is
// literature-parametrized. v1 supports FCC alloys (Al/Ni/Cu base).
const _FCC_ELEMENTS = new Set(["Al", "Ni", "Cu", "Ag", "Au", "Pt", "Pb"]);
function _dominantIsFcc(composition?: Record<string, number>): boolean {
  if (!composition) return false;
  let best = ""; let bestV = -1;
  for (const [el, v] of Object.entries(composition)) {
    if ((v ?? 0) > bestV) { best = el; bestV = v ?? 0; }
  }
  return _FCC_ELEMENTS.has(best);
}

interface CpfemResult {
  method: string;
  family: string;
  phase: string;
  cells: number;
  n_grains: number;
  max_strain_pct: number;
  rve_source?: string;
  stress_strain: { strain: number[]; stress_MPa: number[] } | null;
  youngs_modulus_GPa?: number | null;
  yield_strength_MPa?: number | null;
  flow_stress_MPa?: number | null;
  peak_stress_MPa?: number | null;
  png_base64: string | null;
  source: string;
  calibration: string;
  warnings: string[];
}
interface CpfemJob {
  job_id: string;
  status: "queued" | "running" | "done" | "failed" | "timeout";
  result: CpfemResult | null;
  error: string | null;
}

export function CPFEMStressStrainCard({
  composition,
}: { composition?: Record<string, number> }) {
  const authFetch = useAuthFetch();
  const logAction = useCanvasStore((s) => s.logAction);
  const persist = useCardPersistence<CpfemResult>("stress_strain");
  const [result, setResult] = useState<CpfemResult | null>(persist.savedResult ?? null);
  const [loading, setLoading] = useState(false);
  const [stage, setStage] = useState<"idle" | "submitting" | "running">("idle");
  const [error, setError] = useState<string | null>(null);
  const [rateLimited, setRateLimited] = useState(false);
  const [cloudEnabled, setCloudEnabled] = useState<boolean | null>(null);
  const [cells, setCells] = useState(16);
  const [nGrains, setNGrains] = useState(20);
  const [strainPct, setStrainPct] = useState(2);     // % engineering strain
  const [increments, setIncrements] = useState(30);
  const [interpretation, setInterpretation] = useState<InterpretationPayload | null>(
    (persist.savedInterpretation as InterpretationPayload | undefined) ?? null,
  );
  const [interpreting, setInterpreting] = useState(false);
  const [aiRateLimited, setAiRateLimited] = useState(false);
  const [useNeper, setUseNeper] = useState(true);
  const pollRef = useRef<{ active: boolean }>({ active: false });

  const fccOk = _dominantIsFcc(composition);

  // The user's Neper grain structure (if they ran one) — its Voronoi seeds let
  // CPFEM rebuild that EXACT microstructure as the RVE instead of a random one.
  const grainResult = useCanvasStore(
    (s) => s.simulationResults.grain_structure?.result) as
    { seeds?: number[][]; grain_count?: number } | undefined;
  const neperSeeds = grainResult?.seeds && grainResult.seeds.length >= 4
    ? grainResult.seeds : null;
  const usingNeper = useNeper && !!neperSeeds;

  const runInterpret = useCallback((res: CpfemResult) => {
    if (!res || (res as { error?: unknown }).error) return;
    setInterpreting(true); setAiRateLimited(false); setInterpretation(null);
    authFetch("/api/compute/grain/interpret", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind: "cpfem_stress_strain", result: res, composition: composition ?? null }),
    })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((p: InterpretationPayload) => { setInterpretation(p); persist.persistInterpretation(p); })
      .catch((err) => { if (err === 429) setAiRateLimited(true); setInterpretation(null); })
      .finally(() => setInterpreting(false));
  }, [authFetch, composition, persist]);

  useEffect(() => {
    let alive = true;
    authFetch("/api/compute/health")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (alive && d) setCloudEnabled(!!d.cloud_enabled); })
      .catch(() => { if (alive) setCloudEnabled(false); });
    return () => { alive = false; };
  }, [authFetch]);

  useEffect(() => () => { pollRef.current.active = false; }, []);

  const startPolling = useCallback((jobId: string) => {
    pollRef.current.active = true;
    setStage("running");
    const startedAt = Date.now();
    const tick = async () => {
      if (!pollRef.current.active) return;
      if (Date.now() - startedAt > 50 * 60 * 1000) {
        setError("Timed out waiting (50 min). It may still finish — watch the Jobs tray / your email.");
        setLoading(false); setStage("idle"); pollRef.current.active = false;
        return;
      }
      try {
        const res = await authFetch(`/api/compute/jobs/${jobId}`);
        if (!res.ok) throw new Error(`poll ${res.status}: ${await res.text()}`);
        const job = await res.json() as CpfemJob;
        if (job.status === "done" && job.result) {
          setResult(job.result); persist.persistResult(job.result);
          setLoading(false); setStage("idle"); pollRef.current.active = false;
          runInterpret(job.result);
          return;
        }
        if (job.status === "failed" || job.status === "timeout") {
          setError(job.error?.split("\n")[0] || job.status);
          setLoading(false); setStage("idle"); pollRef.current.active = false;
          return;
        }
        setTimeout(tick, 3000);
      } catch (e) {
        setError(String(e));
        setLoading(false); setStage("idle"); pollRef.current.active = false;
      }
    };
    setTimeout(tick, 2000);
  }, [authFetch, persist, runInterpret]);

  const submit = useCallback(async (override?: { cells?: number; n_grains?: number; max_strain?: number; n_increments?: number }) => {
    setError(null); setRateLimited(false); setResult(null);
    setInterpretation(null); setAiRateLimited(false);
    setLoading(true); setStage("submitting");
    const body = {
      composition: composition ?? {},
      cells: override?.cells ?? cells,
      n_grains: override?.n_grains ?? nGrains,
      max_strain: override?.max_strain ?? strainPct / 100,
      n_increments: override?.n_increments ?? increments,
      // Rebuild the user's actual Neper tessellation when the toggle is on.
      seeds: usingNeper ? neperSeeds : null,
    };
    try {
      const res = await authFetch("/api/compute/microstructure/stress_strain", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.status === 503) { setCloudEnabled(false); setLoading(false); setStage("idle"); return; }
      if (res.status === 429) { setRateLimited(true); setLoading(false); setStage("idle"); return; }
      if (res.status === 422) { setError((await res.json())?.detail || "Composition not supported"); setLoading(false); setStage("idle"); return; }
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json() as { job_id: string };
      logAction({
        source: "cpfem_card",
        label: `Stress–strain (CPFEM): ${body.cells}³, ${body.n_grains} grains, ${strainPct}% strain`,
        op: "simulate_stress_strain",
      });
      startPolling(data.job_id);
    } catch (e) {
      setError(String(e)); setLoading(false); setStage("idle");
    }
  }, [authFetch, composition, cells, nGrains, strainPct, increments, usingNeper, neperSeeds, startPolling, logAction]);

  const applyRec = useCallback((ex?: { type: string; value: unknown }, label?: string) => {
    if (!ex) { toast.error("This suggestion has no action attached."); return; }
    switch (ex.type) {
      case "set_cpfem_params": {
        const v = (ex.value ?? {}) as Record<string, unknown>;
        const next: { cells?: number; n_grains?: number; max_strain?: number; n_increments?: number } = {};
        if (typeof v.cells === "number") next.cells = Math.max(8, Math.min(32, Math.round(v.cells)));
        if (typeof v.n_grains === "number") next.n_grains = Math.max(4, Math.min(64, Math.round(v.n_grains)));
        if (typeof v.max_strain === "number" && v.max_strain > 0) next.max_strain = Math.max(0.005, Math.min(0.10, v.max_strain));
        if (typeof v.n_increments === "number") next.n_increments = Math.max(10, Math.min(60, Math.round(v.n_increments)));
        if (Object.keys(next).length === 0) { toast.error("No valid parameters to apply."); return; }
        if (next.cells != null) setCells(next.cells);
        if (next.n_grains != null) setNGrains(next.n_grains);
        if (next.max_strain != null) setStrainPct(Math.round(next.max_strain * 1000) / 10);
        if (next.n_increments != null) setIncrements(next.n_increments);
        const desc = [
          next.cells != null ? `${next.cells}³` : null,
          next.n_grains != null ? `${next.n_grains} grains` : null,
          next.max_strain != null ? `${(next.max_strain * 100).toFixed(1)}% strain` : null,
        ].filter(Boolean).join(", ");
        toast(`Re-run CPFEM (${desc})? Multi-minute cloud job.`, {
          action: {
            label: "Run",
            onClick: () => {
              submit(next);
              logAction({ source: "interpret_card", label: `Re-run CPFEM: ${desc}`, detail: label, op: "simulate_stress_strain" });
            },
          },
          cancel: { label: "Cancel", onClick: () => {} },
          duration: 8000,
        });
        return;
      }
      case "scroll_to_card":
        scrollToCard(String(ex.value));
        return;
      case "run_predict":
        window.dispatchEvent(new CustomEvent("leilmat:ai_command", { detail: { kind: "predict" } }));
        toast.success("Running property prediction…");
        return;
      case "info_only":
        return;
      default:
        toast.message("Noted — this suggestion is informational.");
        return;
    }
  }, [submit, logAction]);

  return (
    <div className="rounded-lg border border-white/8 overflow-hidden">
      <div className="flex items-center justify-between px-3 py-1.5 bg-sky-500/8 border-b border-sky-500/20">
        <span className="text-[9.5px] font-semibold uppercase tracking-wider text-slate-400">
          Stress–strain
        </span>
        <span className="text-[8.5px] px-1.5 py-0.5 rounded border font-mono font-semibold uppercase tracking-wider bg-sky-500/15 text-sky-300 border-sky-500/30">
          DAMASK · cloud
        </span>
      </div>

      {cloudEnabled === false ? (
        <div className="px-3 py-3">
          <p className="text-[9.5px] text-slate-500 leading-snug">
            Crystal-plasticity stress–strain runs on cloud compute, which is currently
            disabled on this deployment. It activates once the cloud key is configured.
          </p>
        </div>
      ) : !fccOk ? (
        <div className="px-3 py-3">
          <p className="text-[9.5px] text-slate-500 leading-snug">
            CPFEM stress–strain v1 supports <span className="text-sky-300">FCC alloys</span> (Al / Ni / Cu base).
            BCC (steel) and HCP (Ti) crystal-plasticity models are coming soon.
          </p>
        </div>
      ) : (
        <>
          <div className="px-3 py-2 border-b border-white/[0.04] space-y-1.5">
            {neperSeeds && (
              <button type="button" onClick={() => setUseNeper((v) => !v)}
                className={`w-full flex items-center justify-between gap-2 text-[9px] px-2 py-1 rounded border transition-colors
                  ${usingNeper
                    ? "bg-indigo-500/15 text-indigo-200 border-indigo-500/40"
                    : "bg-white/[0.03] text-slate-400 border-white/8 hover:bg-white/[0.06]"}`}
                title="Rebuild your Neper grain structure as the RVE instead of a random one">
                <span className="font-semibold uppercase tracking-wider">
                  {usingNeper ? "✓ " : ""}Use my Neper grains
                </span>
                <span className="font-mono">{grainResult?.grain_count ?? neperSeeds.length} grains</span>
              </button>
            )}
            <div className="flex items-center gap-2">
              <span className="text-[9px] text-slate-500 font-mono w-16 shrink-0">{usingNeper ? "Raster" : "RVE"}</span>
              <input type="range" min={8} max={32} step={4}
                value={cells} onChange={(e) => setCells(Number(e.target.value))}
                className="flex-1 accent-sky-400 h-1" />
              <span className="text-[9.5px] font-mono text-sky-300 w-12 text-right shrink-0">{cells}³</span>
            </div>
            <div className="flex items-center gap-2" style={usingNeper ? { display: "none" } : undefined}>
              <span className="text-[9px] text-slate-500 font-mono w-16 shrink-0">Grains</span>
              <input type="range" min={4} max={64} step={1}
                value={nGrains} onChange={(e) => setNGrains(Number(e.target.value))}
                className="flex-1 accent-sky-400 h-1" />
              <span className="text-[9.5px] font-mono text-sky-300 w-12 text-right shrink-0">{nGrains}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[9px] text-slate-500 font-mono w-16 shrink-0">Max strain</span>
              <input type="range" min={0.5} max={10} step={0.5}
                value={strainPct} onChange={(e) => setStrainPct(Number(e.target.value))}
                className="flex-1 accent-sky-400 h-1" />
              <span className="text-[9.5px] font-mono text-sky-300 w-12 text-right shrink-0">{strainPct}%</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[9px] text-slate-500 font-mono w-16 shrink-0">Increments</span>
              <input type="range" min={10} max={60} step={5}
                value={increments} onChange={(e) => setIncrements(Number(e.target.value))}
                className="flex-1 accent-sky-400 h-1" />
              <span className="text-[9.5px] font-mono text-sky-300 w-12 text-right shrink-0">{increments}</span>
            </div>
            <button onClick={() => submit()} disabled={loading}
              className="w-full text-[9px] py-1 rounded bg-sky-500/15 text-sky-300 border border-sky-500/30 hover:bg-sky-500/25 transition-colors font-semibold uppercase tracking-wider disabled:opacity-50">
              {loading
                ? (stage === "submitting" ? "Submitting to cloud…" : "Solving in cloud…")
                : "Run stress–strain"}
            </button>
            {loading && (
              <p className="text-[8px] text-slate-600 leading-snug">
                Crystal-plasticity FFT solve — a few to tens of minutes. Watch the Jobs tray / your email.
              </p>
            )}
          </div>

          {(result || error || rateLimited) && (
            <div className="px-3 py-2">
              {rateLimited ? (
                <div className="px-2 py-1.5 rounded bg-amber-500/[0.06] border border-amber-500/25">
                  <span className="text-[9px] font-semibold uppercase tracking-wider text-amber-300">⚠ Busy / rate-limited</span>
                  <p className="text-[9px] text-slate-400 leading-snug mt-0.5">
                    The cloud-compute queue is full or rate-limited. Try again shortly.
                  </p>
                </div>
              ) : error ? (
                <p className="text-[9px] text-rose-400 font-mono leading-snug">{error}</p>
              ) : result ? (
                <>
                  {result.png_base64 && (
                    <div className="rounded overflow-hidden bg-white">
                      <img src={`data:image/png;base64,${result.png_base64}`}
                        alt="stress-strain flow curve" className="w-full object-contain" />
                    </div>
                  )}
                  <div className="mt-2 px-2 py-1.5 rounded bg-sky-500/[0.06] border border-sky-500/15">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[8.5px] font-semibold uppercase tracking-wider text-sky-300">Analysis</span>
                      <span className="text-[8px] font-mono text-slate-500">{result.source} · {result.calibration}</span>
                    </div>
                    <div className="text-[9px] font-mono text-slate-300 leading-tight">
                      {result.yield_strength_MPa != null && (
                        <><span className="text-slate-500">YS </span><span className="text-sky-200">{result.yield_strength_MPa} MPa</span></>
                      )}
                      {result.youngs_modulus_GPa != null && (
                        <><span className="text-slate-600"> · </span><span className="text-slate-500">E </span><span className="text-sky-200">{result.youngs_modulus_GPa} GPa</span></>
                      )}
                      {result.flow_stress_MPa != null && (
                        <><span className="text-slate-600"> · </span><span className="text-slate-500">flow </span><span className="text-sky-200">{result.flow_stress_MPa} MPa</span></>
                      )}
                      <span className="text-slate-600"> · </span>
                      <span className="text-sky-200">{result.n_grains} grains</span>
                      {result.rve_source === "neper" && (
                        <>
                          <span className="text-slate-600"> · </span>
                          <span className="text-indigo-300">your Neper RVE</span>
                        </>
                      )}
                    </div>
                  </div>
                  {result.warnings?.length > 0 && (
                    <p className="text-[8px] text-slate-500 mt-1.5 leading-snug">{result.warnings[0]}</p>
                  )}
                  <AIInsightsBlock
                    interpretation={interpretation}
                    interpreting={interpreting}
                    onApply={applyRec}
                    rateLimited={aiRateLimited}
                  />
                </>
              ) : null}
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── Grain-growth card (SPPARKS Monte-Carlo Potts, cloud compute) ──────────────
// Sibling of GrainStructureCard, but simulates grains COARSENING over Monte-
// Carlo time (dynamic) rather than a static synthetic tessellation. Ships
// calibration="qualitative": MC sweeps are not physical time, the lattice is
// dimensionless, so it reports statistical morphology + grain count + size
// distribution, never a calibrated physical anneal.
interface GrainGrowthResult {
  grain_count: number;
  n_sweeps: number;
  grid: number[];
  dimensionality: string;
  method: string;
  mean_grain_size_voxels: number | null;
  size_distribution_voxels: GrainHistogram | null;
  png_base64: string | null;
  source: string;
  calibration: string;
  warnings: string[];
  domain_um?: number;
  voxel_um?: number;
  mean_grain_size_um?: number;
}
interface GrainGrowthJob {
  job_id: string;
  status: "queued" | "running" | "done" | "failed" | "timeout";
  result: GrainGrowthResult | null;
  error: string | null;
}

// ── Heat-treatment (aging) optimizer (KWN, local compute) ────────────────────
// Sweeps aging temperature × time through the KWN model → Orowan Δσ, finds the
// peak-age schedule. calibration="literature-correlation": ranks schedules +
// shows the peak-aging trend honestly; absolute Δσ is a screening estimate.
// v1 supports precipitation-hardened Al/Ni/Ti-base alloys.
const _AGING_ELEMENTS = new Set(["Al", "Ni", "Ti"]);
function _dominantEl(composition?: Record<string, number>): string {
  if (!composition) return "";
  let best = ""; let bestV = -1;
  for (const [el, v] of Object.entries(composition)) {
    if ((v ?? 0) > bestV) { best = el; bestV = v ?? 0; }
  }
  return best;
}

interface AgingPeak { T_C: number; t_h: number; delta_sigma_MPa: number; vf: number; r_nm: number; }
interface AgingResult {
  phase: string; family: string; temperatures_C: number[]; max_time_h: number;
  peak: AgingPeak; recommendation: string; png_base64: string | null;
  source: string; calibration: string; warnings: string[];
}

export function AgingOptimizerCard({ composition }: { composition?: Record<string, number> }) {
  const authFetch = useAuthFetch();
  const logAction = useCanvasStore((s) => s.logAction);
  const persist = useCardPersistence<AgingResult>("aging");
  const [result, setResult] = useState<AgingResult | null>(persist.savedResult ?? null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rateLimited, setRateLimited] = useState(false);
  const [phases, setPhases] = useState<Record<string, { matrix: string }>>({});
  const [phase, setPhase] = useState("");
  const [maxTimeH, setMaxTimeH] = useState(48);

  const dom = _dominantEl(composition);
  const supported = _AGING_ELEMENTS.has(dom);

  // Load the precipitate-phase list once; keep those whose matrix is the alloy's
  // dominant element, default to the first.
  useEffect(() => {
    if (!supported) return;
    let alive = true;
    fetch(`${BASE}/api/precipitation/phases`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!alive || !d?.phases) return;
        const matching: Record<string, { matrix: string }> = {};
        for (const [k, p] of Object.entries(d.phases as Record<string, { matrix: string }>)) {
          if (p.matrix === dom) matching[k] = p;
        }
        setPhases(matching);
        const keys = Object.keys(matching);
        if (keys.length && !keys.includes(phase)) setPhase(keys[0]);
      })
      .catch(() => {});
    return () => { alive = false; };
  }, [dom, supported]);   // eslint-disable-line react-hooks/exhaustive-deps

  const submit = useCallback(async () => {
    if (!phase) { setError("Pick a precipitate phase."); return; }
    setError(null); setRateLimited(false); setResult(null); setLoading(true);
    try {
      const res = await authFetch("/api/precipitation/optimize_aging", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ composition: composition ?? {}, phase, max_time_h: maxTimeH }),
      });
      if (res.status === 429) { setRateLimited(true); setLoading(false); return; }
      if (res.status === 422) { setError((await res.json())?.detail || "Composition not supported"); setLoading(false); return; }
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json() as AgingResult;
      if ((data as { error?: string }).error) { setError((data as { error?: string }).error!); setLoading(false); return; }
      setResult(data); persist.persistResult(data);
      logAction({ source: "interpret_card", label: `Aging optimizer: ${phase} → ${data.recommendation}`, op: "optimize_aging" });
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [authFetch, composition, phase, maxTimeH, persist, logAction]);

  return (
    <div className="rounded-lg border border-white/8 overflow-hidden">
      <div className="flex items-center justify-between px-3 py-1.5 bg-amber-500/8 border-b border-amber-500/20">
        <span className="text-[9.5px] font-semibold uppercase tracking-wider text-slate-400">
          Aging optimizer
        </span>
        <span className="text-[8.5px] px-1.5 py-0.5 rounded border font-mono font-semibold uppercase tracking-wider bg-amber-500/15 text-amber-300 border-amber-500/30">
          KWN · heat-treat
        </span>
      </div>

      {!supported ? (
        <div className="px-3 py-3">
          <p className="text-[9.5px] text-slate-500 leading-snug">
            The aging optimizer covers precipitation-hardened <span className="text-amber-300">Al / Ni / Ti</span>-base
            alloys. Set a composition with one of those as the majority element.
          </p>
        </div>
      ) : (
        <>
          <div className="px-3 py-2 border-b border-white/[0.04] space-y-1.5">
            <div className="flex items-center gap-2">
              <span className="text-[9px] text-slate-500 font-mono w-16 shrink-0">Phase</span>
              <select value={phase} onChange={(e) => setPhase(e.target.value)}
                className="flex-1 bg-white/[0.03] border border-white/8 rounded px-1.5 py-0.5 text-[9px] font-mono text-amber-200">
                {Object.keys(phases).length === 0 && <option value="">loading…</option>}
                {Object.keys(phases).map((k) => <option key={k} value={k}>{k}</option>)}
              </select>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[9px] text-slate-500 font-mono w-16 shrink-0">Max time</span>
              <input type="range" min={1} max={200} step={1}
                value={maxTimeH} onChange={(e) => setMaxTimeH(Number(e.target.value))}
                className="flex-1 accent-amber-400 h-1" />
              <span className="text-[9.5px] font-mono text-amber-300 w-12 text-right shrink-0">{maxTimeH} h</span>
            </div>
            <button onClick={submit} disabled={loading || !phase}
              className="w-full text-[9px] py-1 rounded bg-amber-500/15 text-amber-300 border border-amber-500/30 hover:bg-amber-500/25 transition-colors font-semibold uppercase tracking-wider disabled:opacity-50">
              {loading ? "Optimizing aging…" : "Optimize aging schedule"}
            </button>
          </div>

          {(result || error || rateLimited) && (
            <div className="px-3 py-2">
              {rateLimited ? (
                <p className="text-[9px] text-amber-300 leading-snug">Rate-limited — try again shortly.</p>
              ) : error ? (
                <p className="text-[9px] text-rose-400 font-mono leading-snug">{error}</p>
              ) : result ? (
                <>
                  {result.png_base64 && (
                    <div className="rounded overflow-hidden bg-white">
                      <img src={`data:image/png;base64,${result.png_base64}`}
                        alt="aging curves" className="w-full object-contain" />
                    </div>
                  )}
                  <div className="mt-2 px-2 py-1.5 rounded bg-amber-500/[0.06] border border-amber-500/15">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[8.5px] font-semibold uppercase tracking-wider text-amber-300">Recommended schedule</span>
                      <span className="text-[8px] font-mono text-slate-500">{result.source} · {result.calibration}</span>
                    </div>
                    <p className="text-[10px] text-amber-100 leading-snug font-medium">{result.recommendation}</p>
                    <div className="text-[9px] font-mono text-slate-400 leading-tight mt-1">
                      peak <span className="text-amber-200">{result.peak.delta_sigma_MPa} MPa</span>
                      <span className="text-slate-600"> · </span>
                      <span className="text-amber-200">{result.peak.T_C}°C</span>
                      <span className="text-slate-600"> · </span>
                      <span className="text-amber-200">{result.peak.t_h} h</span>
                      <span className="text-slate-600"> · </span>
                      vf <span className="text-amber-200">{result.peak.vf}</span>
                      <span className="text-slate-600"> · </span>
                      r̄ <span className="text-amber-200">{result.peak.r_nm} nm</span>
                    </div>
                  </div>
                  {result.warnings?.length > 0 && (
                    <p className="text-[8px] text-slate-500 mt-1.5 leading-snug">{result.warnings[0]}</p>
                  )}
                </>
              ) : null}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export function GrainGrowthCard({
  composition,
}: { composition?: Record<string, number> }) {
  // SPPARKS Potts microstructure is composition-independent, but the post-sim
  // AI analysis uses composition for alloy context (Hall-Petch, strength).
  const authFetch = useAuthFetch();
  const logAction = useCanvasStore((s) => s.logAction);
  const persist = useCardPersistence<GrainGrowthResult>("grain_growth");
  const [result, setResult] = useState<GrainGrowthResult | null>(persist.savedResult ?? null);
  const [loading, setLoading] = useState(false);
  const [stage, setStage] = useState<"idle" | "submitting" | "running">("idle");
  const [error, setError] = useState<string | null>(null);
  const [rateLimited, setRateLimited] = useState(false);
  const [cloudEnabled, setCloudEnabled] = useState<boolean | null>(null);
  const [grid, setGrid] = useState(32);
  const [sweeps, setSweeps] = useState(150);
  const [domainUm, setDomainUm] = useState<string>("");
  const [interpretation, setInterpretation] = useState<InterpretationPayload | null>(
    (persist.savedInterpretation as InterpretationPayload | undefined) ?? null,
  );
  const [interpreting, setInterpreting] = useState(false);
  const [aiRateLimited, setAiRateLimited] = useState(false);
  const pollRef = useRef<{ active: boolean }>({ active: false });

  // Post-sim "local AI" analysis: narrate the coarsening + suggest next moves.
  const runInterpret = useCallback((res: GrainGrowthResult) => {
    if (!res || (res as { error?: unknown }).error) return;
    setInterpreting(true); setAiRateLimited(false); setInterpretation(null);
    authFetch("/api/compute/grain/interpret", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind: "grain_grow", result: res, composition: composition ?? null }),
    })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((p: InterpretationPayload) => { setInterpretation(p); persist.persistInterpretation(p); })
      .catch((err) => { if (err === 429) setAiRateLimited(true); setInterpretation(null); })
      .finally(() => setInterpreting(false));
  }, [authFetch, composition, persist]);

  useEffect(() => {
    let alive = true;
    authFetch("/api/compute/health")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (alive && d) setCloudEnabled(!!d.cloud_enabled); })
      .catch(() => { if (alive) setCloudEnabled(false); });
    return () => { alive = false; };
  }, [authFetch]);

  useEffect(() => () => { pollRef.current.active = false; }, []);

  const startPolling = useCallback((jobId: string) => {
    pollRef.current.active = true;
    setStage("running");
    const startedAt = Date.now();
    const tick = async () => {
      if (!pollRef.current.active) return;
      if (Date.now() - startedAt > 50 * 60 * 1000) {
        setError("Timed out waiting (50 min). It may still finish — watch the Jobs tray / your email.");
        setLoading(false); setStage("idle"); pollRef.current.active = false;
        return;
      }
      try {
        const res = await authFetch(`/api/compute/jobs/${jobId}`);
        if (!res.ok) throw new Error(`poll ${res.status}: ${await res.text()}`);
        const job = await res.json() as GrainGrowthJob;
        if (job.status === "done" && job.result) {
          setResult(job.result); persist.persistResult(job.result);
          setLoading(false); setStage("idle"); pollRef.current.active = false;
          runInterpret(job.result);   // auto-analyse the fresh result
          return;
        }
        if (job.status === "failed" || job.status === "timeout") {
          setError(job.error?.split("\n")[0] || job.status);
          setLoading(false); setStage("idle"); pollRef.current.active = false;
          return;
        }
        setTimeout(tick, 3000);
      } catch (e) {
        setError(String(e));
        setLoading(false); setStage("idle"); pollRef.current.active = false;
      }
    };
    setTimeout(tick, 2000);
  }, [authFetch, persist, runInterpret]);

  const submit = useCallback(async (override?: { grid?: number; sweeps?: number; domain_um?: number }) => {
    setError(null); setRateLimited(false); setResult(null);
    setInterpretation(null); setAiRateLimited(false);
    setLoading(true); setStage("submitting");
    const g = override?.grid ?? grid;
    const sw = override?.sweeps ?? sweeps;
    const dom = override?.domain_um ?? (domainUm.trim() ? Number(domainUm) : null);
    const body = { grid: g, sweeps: sw, domain_um: dom && Number.isFinite(dom) && dom > 0 ? dom : null };
    try {
      const res = await authFetch("/api/compute/grain/grow", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.status === 503) { setCloudEnabled(false); setLoading(false); setStage("idle"); return; }
      if (res.status === 429) { setRateLimited(true); setLoading(false); setStage("idle"); return; }
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json() as { job_id: string };
      logAction({
        source: "grain_card",
        label: `Grain growth: ${g}³ lattice, ${sw} MC sweeps`,
        op: "simulate_grain_growth",
      });
      startPolling(data.job_id);
    } catch (e) {
      setError(String(e)); setLoading(false); setStage("idle");
    }
  }, [authFetch, grid, sweeps, domainUm, startPolling, logAction]);

  // Apply a "next move" pill. Paid re-runs (set_grow_params) confirm first;
  // free/cross-card moves fire immediately.
  const applyRec = useCallback((ex?: { type: string; value: unknown }, label?: string) => {
    if (!ex) { toast.error("This suggestion has no action attached."); return; }
    switch (ex.type) {
      case "set_grow_params": {
        const v = (ex.value ?? {}) as Record<string, unknown>;
        const next: { grid?: number; sweeps?: number; domain_um?: number } = {};
        if (typeof v.grid === "number" && Number.isFinite(v.grid))
          next.grid = Math.max(16, Math.min(64, Math.round(v.grid)));
        if (typeof v.sweeps === "number" && Number.isFinite(v.sweeps))
          next.sweeps = Math.max(50, Math.min(2000, Math.round(v.sweeps)));
        if (typeof v.domain_um === "number" && Number.isFinite(v.domain_um) && v.domain_um > 0)
          next.domain_um = v.domain_um;
        if (Object.keys(next).length === 0) { toast.error("No valid parameters to apply."); return; }
        if (next.grid != null) setGrid(next.grid);
        if (next.sweeps != null) setSweeps(next.sweeps);
        if (next.domain_um != null) setDomainUm(String(next.domain_um));
        const desc = [
          next.grid != null ? `${next.grid}³` : null,
          next.sweeps != null ? `${next.sweeps} sweeps` : null,
          next.domain_um != null ? `domain ${next.domain_um} µm` : null,
        ].filter(Boolean).join(", ");
        // Bigger grids run much longer — flag the heavier ones.
        const heavy = (next.grid ?? grid) >= 56 || (next.sweeps ?? sweeps) >= 1000;
        toast(`Re-run grain growth (${desc})? ${heavy ? "Long" : "~Few-min"} cloud job.`, {
          action: {
            label: "Run",
            onClick: () => {
              submit(next);
              logAction({ source: "interpret_card", label: `Re-run grain growth: ${desc}`, detail: label, op: "simulate_grain_growth" });
            },
          },
          cancel: { label: "Cancel", onClick: () => {} },
          duration: 8000,
        });
        return;
      }
      case "scroll_to_card":
        scrollToCard(String(ex.value));
        return;
      case "run_predict":
        window.dispatchEvent(new CustomEvent("leilmat:ai_command", { detail: { kind: "predict" } }));
        toast.success("Running property prediction…");
        return;
      case "info_only":
        return;
      default:
        toast.message("Noted — this suggestion is informational.");
        return;
    }
  }, [submit, grid, sweeps, logAction]);

  const hist = result?.size_distribution_voxels ?? null;

  return (
    <div className="rounded-lg border border-white/8 overflow-hidden">
      <div className="flex items-center justify-between px-3 py-1.5 bg-fuchsia-500/8 border-b border-fuchsia-500/20">
        <span className="text-[9.5px] font-semibold uppercase tracking-wider text-slate-400">
          Grain growth
        </span>
        <span className="text-[8.5px] px-1.5 py-0.5 rounded border font-mono font-semibold uppercase tracking-wider bg-fuchsia-500/15 text-fuchsia-300 border-fuchsia-500/30">
          Potts · cloud
        </span>
      </div>

      {cloudEnabled === false ? (
        <div className="px-3 py-3">
          <p className="text-[9.5px] text-slate-500 leading-snug">
            Grain-growth simulation runs on cloud compute, which is currently
            disabled on this deployment. It activates once the cloud key is configured.
          </p>
        </div>
      ) : (
        <>
          <div className="px-3 py-2 border-b border-white/[0.04] space-y-1.5">
            <div className="flex items-center gap-2">
              <span className="text-[9px] text-slate-500 font-mono w-16 shrink-0">Lattice</span>
              <input type="range" min={16} max={64} step={8}
                value={grid} onChange={(e) => setGrid(Number(e.target.value))}
                className="flex-1 accent-fuchsia-400 h-1" />
              <span className="text-[9.5px] font-mono text-fuchsia-300 w-12 text-right shrink-0">{grid}³</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[9px] text-slate-500 font-mono w-16 shrink-0">MC sweeps</span>
              <input type="range" min={50} max={2000} step={50}
                value={sweeps} onChange={(e) => setSweeps(Number(e.target.value))}
                className="flex-1 accent-fuchsia-400 h-1" />
              <span className="text-[9.5px] font-mono text-fuchsia-300 w-12 text-right shrink-0">{sweeps}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[9px] text-slate-500 font-mono w-16 shrink-0">Domain µm</span>
              <input type="number" min={0} placeholder="optional → dimensionless"
                value={domainUm} onChange={(e) => setDomainUm(e.target.value)}
                className="flex-1 bg-white/[0.03] border border-white/8 rounded px-1.5 py-0.5 text-[9px] font-mono text-fuchsia-200 placeholder:text-slate-600" />
            </div>
            <button onClick={() => submit()} disabled={loading}
              className="w-full text-[9px] py-1 rounded bg-fuchsia-500/15 text-fuchsia-300 border border-fuchsia-500/30 hover:bg-fuchsia-500/25 transition-colors font-semibold uppercase tracking-wider disabled:opacity-50">
              {loading
                ? (stage === "submitting" ? "Submitting to cloud…" : "Coarsening in cloud…")
                : "Grow grains"}
            </button>
            {loading && (
              <p className="text-[8px] text-slate-600 leading-snug">
                First run builds SPPARKS in the sandbox (~3–6 min); later runs are faster.
              </p>
            )}
          </div>

          {(result || error || rateLimited) && (
            <div className="px-3 py-2">
              {rateLimited ? (
                <div className="px-2 py-1.5 rounded bg-amber-500/[0.06] border border-amber-500/25">
                  <span className="text-[9px] font-semibold uppercase tracking-wider text-amber-300">⚠ Busy / rate-limited</span>
                  <p className="text-[9px] text-slate-400 leading-snug mt-0.5">
                    The cloud-compute queue is full or rate-limited. Try again shortly.
                  </p>
                </div>
              ) : error ? (
                <p className="text-[9px] text-rose-400 font-mono leading-snug">{error}</p>
              ) : result ? (
                <>
                  {result.png_base64 && (
                    <div className="relative aspect-square rounded overflow-hidden bg-[#05060d]">
                      <img src={`data:image/png;base64,${result.png_base64}`}
                        alt="grain-growth slice" className="w-full h-full object-contain" />
                      <div className="absolute bottom-1 left-1 px-1.5 py-0.5 rounded bg-black/60 backdrop-blur-sm">
                        <span className="text-[8.5px] font-mono text-fuchsia-300">{result.n_sweeps} sweeps · mid-slice</span>
                      </div>
                    </div>
                  )}
                  <div className="mt-2 px-2 py-1.5 rounded bg-fuchsia-500/[0.06] border border-fuchsia-500/15">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[8.5px] font-semibold uppercase tracking-wider text-fuchsia-300">Analysis</span>
                      <span className="text-[8px] font-mono text-slate-500">{result.source} · {result.calibration}</span>
                    </div>
                    <div className="text-[9px] font-mono text-slate-300 leading-tight">
                      <span className="text-fuchsia-200">{result.grain_count} grains</span>
                      <span className="text-slate-600"> · </span>
                      <span className="text-fuchsia-200">{result.grid?.join("×")}</span>
                      {result.mean_grain_size_um != null ? (
                        <>
                          <span className="text-slate-600"> · </span>
                          d̄ <span className="text-fuchsia-200">{result.mean_grain_size_um} µm</span>
                        </>
                      ) : result.mean_grain_size_voxels != null ? (
                        <>
                          <span className="text-slate-600"> · </span>
                          d̄ <span className="text-fuchsia-200">{result.mean_grain_size_voxels}</span>
                          <span className="text-slate-500"> vox</span>
                        </>
                      ) : null}
                    </div>
                    {hist && <GrainHistogramBars hist={hist} />}
                  </div>
                  {result.warnings?.length > 0 && (
                    <p className="text-[8px] text-slate-500 mt-1.5 leading-snug">{result.warnings[0]}</p>
                  )}
                  <AIInsightsBlock
                    interpretation={interpretation}
                    interpreting={interpreting}
                    onApply={applyRec}
                    rateLimited={aiRateLimited}
                  />
                </>
              ) : null}
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── KWN precipitation-kinetics card (Sprint 5) ───────────────────────────────
interface PrecipResult {
  value?: {
    volume_fraction: number;
    mean_radius_nm:  number;
    number_density_per_m3: number;
    aging_temperature_C: number;
    aging_time_s:    number;
  } | null;
  phase?:        string;
  morphology?:   string;
  source:        string;
  error?:        string;
  warnings?:     string[];
  // Time-resolved arrays from the KWN solver — see ``KWNPlayback`` for
  // the interactive scrubber that consumes them.  Optional because
  // "no precipitation" / "under-saturated" paths return a stub result
  // with no trajectory.
  trajectory?:   KWNTrajectory;
}

const PRECIP_PHASES_BY_FAMILY: Record<string, { key: string; label: string; default_T: number }[]> = {
  aluminum: [
    { key: "Al2Cu_theta_prime",       label: "θ' (Al₂Cu)",    default_T: 190 },
    { key: "Mg2Si_beta_doubleprime",  label: "β\" (Mg₂Si)",   default_T: 175 },
    { key: "MgZn2_eta_prime",         label: "η' (MgZn₂)",    default_T: 120 },
  ],
  nickel: [
    { key: "Ni3Al_gamma_prime",       label: "γ' (Ni₃Al)",    default_T: 760 },
    { key: "Ni3Nb_gamma_doubleprime", label: "γ\" (Ni₃Nb)",   default_T: 720 },
  ],
  titanium: [
    { key: "Ti_alpha_widmanstatten",  label: "α (Widmanstätten)", default_T: 950 },
  ],
};

function detectPrecipFamily(comp: Record<string, number>): string | null {
  const total = Object.values(comp).reduce((a, b) => a + b, 0);
  if (total <= 0) return null;
  const fracs = Object.fromEntries(Object.entries(comp).map(([el, v]) => [el, v / total]));
  if ((fracs.Al ?? 0) >= 0.8) return "aluminum";
  if ((fracs.Ni ?? 0) >= 0.4) return "nickel";
  if ((fracs.Ti ?? 0) >= 0.5) return "titanium";
  return null;
}

export function PrecipitationCard({ composition }: { composition: Record<string, number> }) {
  const authFetch = useAuthFetch();
  const logAction = useCanvasStore((s) => s.logAction);
  const persist = useCardPersistence<PrecipResult>("precipitation");
  const family = detectPrecipFamily(composition);
  const phases = family ? (PRECIP_PHASES_BY_FAMILY[family] ?? []) : [];
  const [phase, setPhase] = useState<string>(phases[0]?.key ?? "");
  const [agingT, setAgingT] = useState<number>(phases[0]?.default_T ?? 200);
  const [agingHours, setAgingHours] = useState<number>(8);
  const [result, setResult] = useState<PrecipResult | null>(
    persist.savedResult ?? null,
  );
  const [loading, setLoading] = useState(false);
  const [interpretation, setInterpretation] = useState<InterpretationPayload | null>(
    (persist.savedInterpretation as InterpretationPayload | undefined) ?? null,
  );
  const [interpreting, setInterpreting] = useState(false);
  const [rateLimited, setRateLimited] = useState(false);

  // Reset phase + T when family changes
  useEffect(() => {
    if (phases.length && !phases.find((p) => p.key === phase)) {
      setPhase(phases[0].key);
      setAgingT(phases[0].default_T);
      setResult(null);
      setInterpretation(null);
    }
  }, [family, phases, phase]);

  const runSim = useCallback(async () => {
    if (!phase) return;
    setLoading(true);
    setInterpretation(null);
    setRateLimited(false);
    try {
      const res = await authFetch("/api/precipitation/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          composition,
          phase,
          aging_T_C: agingT,
          aging_time_s: agingHours * 3600,
        }),
      });
      if (res.status === 429) {
        setRateLimited(true);
        setResult(null);
        return;
      }
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json() as PrecipResult;
      setResult(data);
      persist.persistResult(data);

      // Fire interpretation when KWN actually returned a (vf, r̄).
      if (data && !data.error && data.value && data.value.volume_fraction != null) {
        setInterpreting(true);
        authFetch("/api/precipitation/interpret", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            composition,
            kwn_result:   data,
            sim_metadata: { source: data.source },
          }),
        })
          .then(r => r.ok ? r.json() : Promise.reject(r.status))
          .then((p: InterpretationPayload) => {
            setInterpretation(p);
            persist.persistInterpretation(p);
          })
          .catch((err) => {
            if (err === 429) setRateLimited(true);
            setInterpretation(null);
          })
          .finally(() => setInterpreting(false));
      }
    } catch {
      setResult(null);
    } finally {
      setLoading(false);
    }
  }, [composition, phase, agingT, agingHours]);

  const applyRec = useCallback((ex?: { type: string; value: unknown }, label?: string) => {
    if (!ex) { toast.error("This suggestion has no action attached."); return; }
    const log = (msg: string, op: string) =>
      logAction({ source: "interpret_card", label: msg, detail: label, op });
    switch (ex.type) {
      case "set_temperature_C": {
        const v = coerceNum(ex.value);
        if (v == null || v < 50 || v > 1500) {
          toast.error(`Couldn't apply aging temperature "${String(ex.value)}".`);
          return;
        }
        setAgingT(Math.round(v));
        toast.success(`Aging temperature → ${Math.round(v)} °C`);
        log(`Aging temperature → ${Math.round(v)} °C`, ex.type);
        return;
      }
      case "set_aging_hours": {
        const v = coerceNum(ex.value);
        if (v == null || v <= 0 || v > 200) {
          toast.error(`Couldn't apply aging time "${String(ex.value)}" (range 0–200 h).`);
          return;
        }
        setAgingHours(v);
        toast.success(`Aging time → ${v} h`);
        log(`Aging time → ${v} h`, ex.type);
        return;
      }
      case "scroll_to_card":
        scrollToCard(String(ex.value));
        return;
      case "info_only":
        return;
      default:
        toast.message("Noted — this suggestion is informational.");
        return;
    }
  }, [logAction]);

  if (!family || phases.length === 0) return null;

  const v = result?.value;

  return (
    <div className="rounded-lg border border-white/8 overflow-hidden">
      <div className="flex items-center justify-between px-3 py-1.5 bg-blue-500/8 border-b border-blue-500/20">
        <span className="text-[9.5px] font-semibold uppercase tracking-wider text-slate-400">
          Precipitation (KWN)
        </span>
        <span className="text-[8.5px] px-1.5 py-0.5 rounded border font-mono font-semibold uppercase tracking-wider bg-blue-500/15 text-blue-300 border-blue-500/30">
          KWN
        </span>
      </div>

      <div className="px-3 py-2 border-b border-white/[0.04] space-y-1.5">
        <select
          value={phase}
          onChange={(e) => {
            setPhase(e.target.value);
            const p = phases.find((q) => q.key === e.target.value);
            if (p) setAgingT(p.default_T);
          }}
          className="w-full bg-white/[0.04] border border-white/[0.06] rounded px-2 py-1 text-[10px] text-slate-200 outline-none focus:border-blue-500/40"
        >
          {phases.map((p) => (
            <option key={p.key} value={p.key}>{p.label}</option>
          ))}
        </select>
        <div className="flex items-center gap-2">
          <span className="text-[9px] text-slate-500 w-12 shrink-0">T (°C)</span>
          <input
            type="number" min={50} max={1100} step={5}
            value={agingT} onChange={(e) => setAgingT(Number(e.target.value))}
            className="flex-1 bg-white/[0.04] border border-white/[0.06] rounded px-2 py-0.5 text-[10px] font-mono text-blue-300 outline-none focus:border-blue-500/40"
          />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[9px] text-slate-500 w-12 shrink-0">time (h)</span>
          <input
            type="number" min={0.1} max={1000} step={0.5}
            value={agingHours} onChange={(e) => setAgingHours(Number(e.target.value))}
            className="flex-1 bg-white/[0.04] border border-white/[0.06] rounded px-2 py-0.5 text-[10px] font-mono text-blue-300 outline-none focus:border-blue-500/40"
          />
        </div>
        <button
          onClick={runSim} disabled={loading}
          className="w-full text-[9px] py-1 rounded bg-blue-500/15 text-blue-300 border border-blue-500/30 hover:bg-blue-500/25 transition-colors font-semibold uppercase tracking-wider disabled:opacity-50"
        >
          {loading ? "Simulating…" : "Compute precipitation"}
        </button>
      </div>

      {result && (
        <div className="px-3 py-2">
          {result.error || !v ? (
            <p className="text-[9px] text-slate-500 font-mono leading-snug">
              {result.error ?? "No precipitation (under-saturated)."}
            </p>
          ) : (
            <>
              <div className="grid grid-cols-3 gap-2 mb-1.5">
                <div>
                  <p className="text-[8px] text-slate-500 uppercase">Volume frac</p>
                  <p className="text-[11px] font-mono text-blue-300">{(v.volume_fraction * 100).toFixed(2)}%</p>
                </div>
                <div>
                  <p className="text-[8px] text-slate-500 uppercase">Mean radius</p>
                  <p className="text-[11px] font-mono text-blue-300">{v.mean_radius_nm.toFixed(1)} nm</p>
                </div>
                <div>
                  <p className="text-[8px] text-slate-500 uppercase">N density</p>
                  <p className="text-[10px] font-mono text-blue-300">{v.number_density_per_m3.toExponential(2)}/m³</p>
                </div>
              </div>
              <p className="text-[8.5px] text-slate-600 leading-snug">
                {result.phase} ({result.morphology}) at {v.aging_temperature_C}°C / {(v.aging_time_s/3600).toFixed(1)} h
              </p>

              {/* Mini-sim #1 — KWN aging playback.  Renders only when the
                  backend returned a multi-point trajectory (real
                  precipitation; for the "under-saturated, nothing
                  nucleates" case the trajectory is single-point and
                  the component bails out). */}
              {result.trajectory && (
                <KWNPlayback trajectory={result.trajectory} />
              )}
            </>
          )}

          {/* Layer 2: AI interpretation of the KWN result */}
          <AIInsightsBlock
            interpretation={interpretation}
            interpreting={interpreting}
            rateLimited={rateLimited}
            onApply={applyRec}
          />
        </div>
      )}
    </div>
  );
}


export function PropertyDashboard({ composition, properties, hullDistance, m3gnetState }: PropertyDashboardProps) {
  const { selectElement } = useCanvasStore();
  const details = properties._details ?? {};
  const phaseStability = properties.phase_stability;

  const radarProps = DISPLAY_PROPS.filter((p) => properties[p.key] != null);
  const r = radarProps.map((p) => Math.abs((properties[p.key] as number) * p.scale));
  const theta = radarProps.map((p) => p.short);

  const trace: Plotly.Data = {
    type: "scatterpolar",
    r: [...r, r[0]],
    theta: [...theta, theta[0]],
    fill: "toself",
    fillcolor: "rgba(56,189,248,0.12)",
    line: { color: "#38bdf8", width: 2 },
    marker: { size: 7, color: "#38bdf8" },
    hovertemplate: "%{theta}: %{r:.3f}<extra></extra>",
  } as Plotly.Data;

  const layout: Partial<Plotly.Layout> = {
    paper_bgcolor: "transparent",
    polar: {
      bgcolor: "transparent",
      radialaxis: { visible: true, color: "#334155", gridcolor: "#1e293b", tickfont: { size: 9, color: "#475569" } },
      angularaxis: { color: "#64748b", tickfont: { size: 11 } },
    },
    font: { color: "#94a3b8", size: 11, family: "Inter, system-ui, sans-serif" },
    margin: { t: 20, b: 20, l: 50, r: 50 },
  };

  function handleClick(event: Readonly<Plotly.PlotMouseEvent>) {
    const pt = event.points[0];
    if (!pt) return;
    const short = (pt as { theta?: string }).theta;
    const prop = DISPLAY_PROPS.find((p) => p.short === short);
    if (!prop) return;
    const mouseEvent = (event as unknown as { event?: MouseEvent }).event;
    const anchor = mouseEvent ? { x: mouseEvent.clientX, y: mouseEvent.clientY } : undefined;
    selectElement({
      type: "property_bar",
      data: { property_key: prop.key, property_label: prop.label, value: properties[prop.key], composition, detail: details[prop.key] },
      canvas_summary: { all_properties: properties },
      anchor,
    });
  }

  const warnings = phaseStability?.warnings ?? [];
  const criticalCount = warnings.filter((w) => w.level === "critical").length;

  return (
    <div className="flex gap-6 h-full">
      {/* Radar */}
      <div className="flex-1 min-w-0">
        <Plot
          data={[trace]}
          layout={layout}
          config={{ displayModeBar: false, responsive: true }}
          style={{ width: "100%", height: "100%" }}
          onClick={handleClick}
        />
      </div>

      {/* Right column: property cards + stability panels */}
      <div className="w-72 shrink-0 flex flex-col gap-2 overflow-y-auto">

        {/* ── Phase stability warnings ─────────────────────────── */}
        {warnings.length > 0 && (
          <div className="rounded-lg border border-white/8 overflow-hidden">
            <div className={`flex items-center justify-between px-3 py-1.5 ${
              criticalCount > 0 ? "bg-rose-500/10 border-b border-rose-500/20" : "bg-amber-500/8 border-b border-amber-500/20"
            }`}>
              <span className="text-[9.5px] font-semibold uppercase tracking-wider text-slate-400">
                Phase Warnings
              </span>
              <span className={`text-[8.5px] px-1.5 py-0.5 rounded-full font-mono font-semibold ${
                criticalCount > 0 ? "bg-rose-500/20 text-rose-300" : "bg-amber-500/20 text-amber-300"
              }`}>
                {warnings.length}
              </span>
            </div>
            <div className="divide-y divide-white/[0.04]">
              {warnings.map((w, i) => {
                const wc = WARN_COLOR[w.level] ?? WARN_COLOR.warning;
                return (
                  <div key={i} className={`px-3 py-2 ${wc.bg}`}>
                    <div className="flex items-start gap-1.5">
                      <div className={`w-1.5 h-1.5 rounded-full mt-1 shrink-0 ${wc.dot}`} />
                      <p className={`text-[10px] leading-snug ${wc.text}`}>{w.message}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ── Hull distance (thermodynamic stability) ──────────── */}
        {hullDistance && (
          <div className={`rounded-lg border px-3 py-2 ${
            hullDistance.stability === "unknown"
              ? "bg-white/[0.03] border-white/8"
              : `${HULL_COLOR[hullDistance.stability].bg} border-${hullDistance.stability === "stable" ? "emerald" : hullDistance.stability === "metastable" ? "amber" : "rose"}-500/30`
          }`}>
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] text-slate-500 uppercase tracking-wider font-medium">
                Thermo. Stability
              </span>
              <span className="text-[8.5px] px-1.5 py-0.5 rounded border font-mono font-semibold uppercase tracking-wider bg-fuchsia-500/15 text-fuchsia-300 border-fuchsia-500/30">
                MP hull
              </span>
            </div>
            {hullDistance.error ? (
              <p className="text-[10px] text-slate-600 font-mono">{hullDistance.error}</p>
            ) : (
              <>
                <div className="flex items-baseline gap-2">
                  {(() => {
                    const hc = HULL_COLOR[hullDistance.stability] ?? HULL_COLOR.unknown;
                    return (
                      <span className={`text-[12px] font-semibold px-2 py-0.5 rounded border ${hc.bg} ${hc.text} ${hc.border} capitalize`}>
                        {hullDistance.stability}
                      </span>
                    );
                  })()}
                  {hullDistance.e_above_hull != null && (
                    <span className="text-[10px] text-slate-500 font-mono">
                      {hullDistance.e_above_hull_meV != null
                        ? `${hullDistance.e_above_hull_meV} meV/atom`
                        : `${(hullDistance.e_above_hull * 1000).toFixed(0)} meV/atom`}
                    </span>
                  )}
                </div>
                {hullDistance.note && (
                  <p className="text-[9.5px] text-slate-500 mt-1 leading-snug line-clamp-2">
                    {hullDistance.note}
                  </p>
                )}
              </>
            )}
          </div>
        )}

        {/* ── Property cards ───────────────────────────────────── */}
        {DISPLAY_PROPS.map((p) => {
          const val = properties[p.key];
          const detail = details[p.key] ?? {};
          const sourceKey = detail.source?.split(" ")[0] ?? "";
          const sourceClass = sourceKey ? SOURCE_COLOR[sourceKey] ?? "bg-slate-500/15 text-slate-400 border-slate-500/30" : "";
          const sourceLabel = sourceKey ? SOURCE_LABEL[sourceKey] ?? detail.source : null;
          const hasError = detail.error != null;

          return (
            <button
              key={p.key}
              onClick={(e) =>
                selectElement({
                  type: "property_bar",
                  data: { property_key: p.key, property_label: p.label, value: val, composition, detail },
                  canvas_summary: { all_properties: properties },
                  anchor: { x: e.clientX, y: e.clientY },
                })
              }
              title={hasError ? detail.error : undefined}
              className="w-full text-left px-3 py-2 rounded-lg bg-white/[0.03] hover:bg-white/[0.07] border border-white/8 hover:border-sky-500/30 transition-all group"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] text-slate-500 group-hover:text-slate-400 transition-colors uppercase tracking-wider font-medium">
                  {p.label} <span className="opacity-60">{p.unit && `(${p.unit})`}</span>
                </span>
                {p.key === "formation_energy_eV_per_atom" && m3gnetState && m3gnetState !== "ready" && m3gnetState !== "failed" ? (
                  <span className="text-[8.5px] px-1.5 py-0.5 rounded border font-mono font-semibold uppercase tracking-wider bg-fuchsia-500/15 text-fuchsia-300 border-fuchsia-500/30 inline-flex items-center gap-1">
                    <span className="w-1 h-1 rounded-full bg-fuchsia-400 animate-pulse" />
                    {m3gnetState === "loading" ? "M3GNet loading" : "calibrating"}
                  </span>
                ) : p.key === "formation_energy_eV_per_atom" && m3gnetState === "failed" ? (
                  <span className="text-[8.5px] px-1.5 py-0.5 rounded border font-mono font-semibold uppercase tracking-wider bg-amber-500/15 text-amber-300 border-amber-500/30" title="M3GNet failed — Miedema heuristic fallback active">
                    Miedema fallback
                  </span>
                ) : sourceLabel ? (
                  <span className={`text-[8.5px] px-1.5 py-0.5 rounded border font-mono font-semibold uppercase tracking-wider ${sourceClass}`}>
                    {sourceLabel}
                  </span>
                ) : null}
              </div>
              <div className="flex items-baseline gap-1.5">
                <span className={`font-mono text-sm font-semibold ${val == null ? "text-slate-600" : "text-slate-100"}`}>
                  {val == null ? "—" : (val as number).toFixed(p.key.includes("MPa") || p.key.includes("_K") || p.key === "elastic_modulus_GPa" ? 0 : 3)}
                </span>
                {detail.uncertainty != null && val != null && (
                  <span className="text-[10px] text-slate-500 font-mono">
                    ± {detail.uncertainty.toFixed(p.key.includes("MPa") || p.key.includes("_K") || p.key === "elastic_modulus_GPa" ? 0 : 2)}
                  </span>
                )}
              </div>
              {/* ── Conformal prediction interval (Track C) ── */}
              {val != null && detail.ci_low != null && detail.ci_high != null && detail.calibration === "conformal" && (
                <div className="flex items-center gap-1.5 text-[9px] mt-0.5">
                  <span className="px-1 py-px rounded text-[8px] font-mono uppercase tracking-wider bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
                    {Math.round((detail.coverage ?? 0.9) * 100)}% CI
                  </span>
                  <span className="text-slate-500 font-mono">
                    [{detail.ci_low.toFixed(p.key.includes("MPa") || p.key.includes("_K") || p.key === "elastic_modulus_GPa" ? 0 : 2)},{" "}
                    {detail.ci_high.toFixed(p.key.includes("MPa") || p.key.includes("_K") || p.key === "elastic_modulus_GPa" ? 0 : 2)}]
                  </span>
                </div>
              )}
              {/* Hall-Petch grain-size overlay (only when a sim grain size was applied) */}
              {p.key === "yield_strength_MPa" && detail.hall_petch && (
                <div className="flex items-center gap-1.5 text-[9px] mt-0.5" title={detail.hall_petch.note}>
                  <span className="px-1 py-px rounded text-[8px] font-mono uppercase tracking-wider bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                    grain {detail.hall_petch.grain_size_um} µm
                  </span>
                  <span className="text-slate-500 font-mono">
                    Hall-Petch {detail.hall_petch.delta_MPa >= 0 ? "+" : ""}{detail.hall_petch.delta_MPa} MPa
                  </span>
                </div>
              )}
              {p.key === "yield_strength_MPa" && detail.precipitation && (
                <div className="flex items-center gap-1.5 text-[9px] mt-0.5" title={detail.precipitation.note}>
                  <span className="px-1 py-px rounded text-[8px] font-mono uppercase tracking-wider bg-fuchsia-500/10 text-fuchsia-300 border border-fuchsia-500/20">
                    precip vf {detail.precipitation.vf} · r̄ {detail.precipitation.r_nm} nm
                  </span>
                  <span className="text-slate-500 font-mono">
                    Orowan {detail.precipitation.delta_MPa >= 0 ? "+" : ""}{detail.precipitation.delta_MPa} MPa
                  </span>
                </div>
              )}
              {/* VRH bounds tooltip */}
              {p.key === "elastic_modulus_GPa" && detail.e_voigt_GPa != null && (
                <div className="text-[9px] text-slate-600 font-mono mt-0.5">
                  Voigt {detail.e_voigt_GPa} · Reuss {detail.e_reuss_GPa} GPa
                </div>
              )}
              {hasError && (
                <div className="text-[9.5px] text-amber-400/80 mt-1 leading-tight line-clamp-2">
                  {detail.error}
                </div>
              )}
            </button>
          );
        })}

        {/* ── Corrosion resistance card ─────────────────────────── */}
        {(() => {
          const cor = (details["corrosion_resistance"] ?? {}) as PropertyDetail;
          const rating = cor.rating ?? null;
          if (!rating) return null;
          const rc = CORROSION_COLOR[rating] ?? CORROSION_COLOR["Fair"];
          const sourceKey = cor.source ?? "electrochemistry_rules";
          const sourceLabel = SOURCE_LABEL[sourceKey] ?? sourceKey;
          const sourceClass = SOURCE_COLOR[sourceKey] ?? SOURCE_COLOR.electrochemistry_rules;
          const topDriver = cor.drivers_positive?.[0]?.element;
          const prenValue = cor.pren;
          return (
            <button
              onClick={(e) =>
                selectElement({
                  type: "property_bar",
                  data: { property_key: "corrosion_resistance", property_label: "Corrosion resistance", value: rating, composition, detail: cor },
                  canvas_summary: { all_properties: properties },
                  anchor: { x: e.clientX, y: e.clientY },
                })
              }
              className="w-full text-left px-3 py-2 rounded-lg bg-white/[0.03] hover:bg-white/[0.07] border border-white/8 hover:border-yellow-500/30 transition-all group"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] text-slate-500 group-hover:text-slate-400 transition-colors uppercase tracking-wider font-medium">
                  Corrosion
                </span>
                <span className={`text-[8.5px] px-1.5 py-0.5 rounded border font-mono font-semibold uppercase tracking-wider ${sourceClass}`}>
                  {sourceLabel}
                </span>
              </div>
              <div className="flex items-baseline gap-2 mt-1">
                <span className={`text-[12px] font-semibold px-2 py-0.5 rounded border ${rc.bg} ${rc.text} ${rc.border}`}>
                  {rating}
                </span>
                {cor.rate_range_text && (
                  <span className="text-[10px] text-slate-500 font-mono">{cor.rate_range_text}</span>
                )}
              </div>
              {prenValue != null ? (
                <div className="text-[9.5px] text-slate-500 mt-1 font-mono">
                  PREN = {prenValue}
                </div>
              ) : topDriver ? (
                <div className="text-[9.5px] text-slate-500 mt-1 font-mono truncate">
                  driven by {topDriver}
                </div>
              ) : null}
            </button>
          );
        })()}

        {/* Sprint cards (PhaseAssemblage, Solidification, TTT,
            Microstructure, Precipitation) used to live here, but the
            w-72 × h-72 sub-column hid them — they now render as a
            dedicated "Process simulation" Panel in canvas/page.tsx. */}

      </div>
    </div>
  );
}
