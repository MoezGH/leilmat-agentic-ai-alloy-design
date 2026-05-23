"use client";
import dynamic from "next/dynamic";
import { useCanvasStore } from "@/lib/store";
import { useState, useCallback } from "react";

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

        {/* ── CALPHAD phase assemblage card ────────────────────── */}
        <PhaseAssemblageCard composition={composition} />

      </div>
    </div>
  );
}
