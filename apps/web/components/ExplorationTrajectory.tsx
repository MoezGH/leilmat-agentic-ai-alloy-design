"use client";
/**
 * ExplorationTrajectory — line chart of property values along a swept variable.
 * Renders whenever the store has sweepResult populated by an AI-triggered sweep.
 */
import dynamic from "next/dynamic";
import { useState } from "react";
import type { SweepResult } from "@/lib/store";
import { useCanvasStore } from "@/lib/store";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

const PROPERTY_OPTIONS = [
  { key: "density_g_cm3", label: "Density (g/cm³)" },
  { key: "melting_point_K", label: "Melting point (K)" },
  { key: "electronegativity_mean", label: "Electronegativity" },
  { key: "valence_electrons_mean", label: "Valence e⁻" },
  { key: "formation_energy_eV_per_atom", label: "Formation E (eV/atom)" },
];

interface ExplorationTrajectoryProps {
  result: SweepResult;
}

export function ExplorationTrajectory({ result }: ExplorationTrajectoryProps) {
  const { selectElement } = useCanvasStore();
  const [propKey, setPropKey] = useState("density_g_cm3");
  const propLabel = PROPERTY_OPTIONS.find((p) => p.key === propKey)?.label ?? propKey;

  const xs = result.points.map((p) => p.variedValue);
  const ys = result.points.map((p) => p.properties[propKey] ?? null);
  const text = result.points.map((p) =>
    Object.entries(p.composition).map(([el, v]) => `${el}: ${v.toFixed(1)}%`).join("<br>")
  );

  const trace: Plotly.Data = {
    type: "scatter",
    mode: "lines+markers",
    x: xs,
    y: ys,
    text,
    hovertemplate: "%{text}<br>%{yaxis.title.text}: %{y:.3f}<extra></extra>",
    line: { color: "#10b981", width: 2.5, shape: "spline" },
    marker: { size: 9, color: "#10b981", line: { color: "rgba(255,255,255,0.25)", width: 1 } },
  } as Plotly.Data;

  const layout: Partial<Plotly.Layout> = {
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    xaxis: { color: "#64748b", gridcolor: "#1e293b", title: { text: `${result.vary} (%)` }, tickfont: { size: 11 } },
    yaxis: { color: "#64748b", gridcolor: "#1e293b", title: { text: propLabel }, tickfont: { size: 11 } },
    font: { color: "#94a3b8", size: 11, family: "Inter, system-ui, sans-serif" },
    margin: { t: 10, b: 50, l: 65, r: 20 },
  };

  function handleClick(event: Readonly<Plotly.PlotMouseEvent>) {
    const pt = event.points[0];
    if (!pt) return;
    const sp = result.points[pt.pointIndex];
    if (!sp) return;
    const mouseEvent = (event as unknown as { event?: MouseEvent }).event;
    const anchor = mouseEvent ? { x: mouseEvent.clientX, y: mouseEvent.clientY } : undefined;
    selectElement({
      type: "composition_point",
      data: { composition: sp.composition, properties: sp.properties, variedValue: sp.variedValue },
      canvas_summary: { sweep_axis: result.vary, n_points: result.points.length },
      anchor,
    });
  }

  return (
    <div className="flex flex-col h-full gap-3">
      <div className="flex items-center gap-2 shrink-0">
        <span className="text-[11px] text-slate-500">Property:</span>
        <select
          value={propKey}
          onChange={(e) => setPropKey(e.target.value)}
          className="bg-white/[0.04] border border-white/[0.08] rounded-md px-2 py-1 text-[11px] text-slate-200 outline-none focus:border-sky-500/40 cursor-pointer"
        >
          {PROPERTY_OPTIONS.map((p) => (
            <option key={p.key} value={p.key} className="bg-[#15171d]">{p.label}</option>
          ))}
        </select>
        <span className="text-[11px] text-slate-600 ml-auto">{result.points.length} points</span>
      </div>
      <div className="flex-1 min-h-0">
        <Plot
          data={[trace]}
          layout={layout}
          config={{ displayModeBar: false, responsive: true }}
          style={{ width: "100%", height: "100%" }}
          onClick={handleClick}
        />
      </div>
    </div>
  );
}
