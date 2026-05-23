"use client";
import dynamic from "next/dynamic";
import { useCanvasStore } from "@/lib/store";
import { useState, useCallback, useEffect, useRef } from "react";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

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
function PhaseAssemblageCard({ composition }: { composition: Record<string, number> }) {
  const [T_C, setT_C] = useState(500);
  const [result, setResult] = useState<PhaseAssemblageResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [queried, setQueried] = useState(false);

  const fetchPhases = useCallback(async (temp: number) => {
    setLoading(true);
    try {
      const compStr = Object.entries(composition)
        .filter(([, v]) => v > 0)
        .map(([el, v]) => `${el}:${v.toFixed(2)}`)
        .join(",");
      const res = await fetch(
        `/api/phase/equilibrium?composition=${encodeURIComponent(compStr)}&T_C=${temp}`
      );
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json() as PhaseAssemblageResult;
      setResult(data);
      setQueried(true);
    } catch {
      setResult(null);
    } finally {
      setLoading(false);
    }
  }, [composition]);

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

function SolidificationCard({ composition }: { composition: Record<string, number> }) {
  const [result, setResult] = useState<SolidificationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [queried, setQueried] = useState(false);

  const fetchScheil = useCallback(async () => {
    setLoading(true);
    try {
      const compStr = Object.entries(composition)
        .filter(([, v]) => v > 0)
        .map(([el, v]) => `${el}:${v.toFixed(2)}`)
        .join(",");
      const res = await fetch(`/api/phase/scheil?composition=${encodeURIComponent(compStr)}`);
      if (!res.ok) throw new Error(await res.text());
      setResult(await res.json() as SolidificationResult);
      setQueried(true);
    } catch {
      setResult(null);
    } finally {
      setLoading(false);
    }
  }, [composition]);

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

function TTTCard({ composition }: { composition: Record<string, number> }) {
  const [result, setResult] = useState<TTTResult | null>(null);
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
        `/api/phase/ttt?composition=${encodeURIComponent(compStr)}&austenite_grain_um=${grainUm}`
      );
      if (!res.ok) throw new Error(await res.text());
      setResult(await res.json() as TTTResult);
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
interface MicrostructureResult {
  frames: MicrostructureFrame[];
  metadata: { grid: number; final_solid_fraction: number; cache_hit?: boolean };
  source: string;
  calibration: string;
  warnings: string[];
  error?: string;
}

function MicrostructureCard({
  composition, T_C,
}: { composition: Record<string, number>; T_C?: number | null }) {
  const [result, setResult] = useState<MicrostructureResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [frameIdx, setFrameIdx] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [symmetry, setSymmetry] = useState(6);
  const [undercooling, setUndercooling] = useState(1.0);
  const intervalRef = useRef<number | null>(null);

  const fetchSim = useCallback(async () => {
    setLoading(true);
    setPlaying(false);
    try {
      const res = await fetch("/api/microstructure/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          composition, T_C,
          crystal_symmetry: symmetry,
          undercooling_factor: undercooling,
          grid: 100, n_steps: 800, n_frames: 12,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json() as MicrostructureResult;
      setResult(data);
      setFrameIdx(0);
      if (data.frames.length > 1) setPlaying(true);
    } catch {
      setResult(null);
    } finally {
      setLoading(false);
    }
  }, [composition, T_C, symmetry, undercooling]);

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
        <button
          onClick={fetchSim} disabled={loading}
          className="w-full text-[9px] py-1 rounded bg-pink-500/15 text-pink-300 border border-pink-500/30 hover:bg-pink-500/25 transition-colors font-semibold uppercase tracking-wider disabled:opacity-50"
        >
          {loading ? "Simulating phase-field… (≈ 15 s)" : "Simulate crystal"}
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
            </>
          ) : (
            <p className="text-[9px] text-slate-600 font-mono">No frames returned.</p>
          )}
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

        {/* ── CALPHAD phase assemblage card (Sprint 1) ─────────── */}
        <PhaseAssemblageCard composition={composition} />

        {/* ── Scheil solidification card (Sprint 2) ────────────── */}
        <SolidificationCard composition={composition} />

        {/* ── Fe-C TTT card (Sprint 2, steel-only) ─────────────── */}
        <TTTCard composition={composition} />

        {/* ── Microstructure card (Sprint 2.5) ─────────────────── */}
        <MicrostructureCard composition={composition} />

      </div>
    </div>
  );
}
