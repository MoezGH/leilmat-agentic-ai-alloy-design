"use client";
/**
 * ParetoExplorer — renders BoTorch qEHVI results.
 * - Pareto-optimal candidates: large hexagons, colored by score, connected by a line
 * - Dominated candidates: small dim dots
 * - Clicking any point: composition + properties → Local AI popover
 */
import { useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { Bookmark, ThumbsDown, Sparkles } from "lucide-react";
import { useCanvasStore } from "@/lib/store";
import { CHART } from "@/lib/chartTheme";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

interface Candidate {
  composition: Record<string, number>;
  properties: Record<string, number | null>;
  pareto_rank: number;
  score: number;
  is_pareto?: boolean;
  method?: string;
}

interface ParetoExplorerProps {
  candidates: Candidate[];
  xProp?: string;
  yProp?: string;
}

const AXIS_OPTIONS = [
  { key: "density_g_cm3", label: "Density (g/cm³)" },
  { key: "melting_point_K", label: "Melting point (K)" },
  { key: "yield_strength_MPa", label: "Yield strength (MPa)" },
  { key: "formation_energy_eV_per_atom", label: "Formation E (eV/atom)" },
];

export function ParetoExplorer({ candidates, xProp = "density_g_cm3", yProp = "melting_point_K" }: ParetoExplorerProps) {
  const { selectElement, addComposition, toggleBookmark, toggleReject, session } = useCanvasStore();
  const [xAxis, setXAxis] = useState(xProp);
  const [yAxis, setYAxis] = useState(yProp);
  const [showDominated, setShowDominated] = useState(true);

  const xLabel = AXIS_OPTIONS.find((o) => o.key === xAxis)?.label ?? xAxis;
  const yLabel = AXIS_OPTIONS.find((o) => o.key === yAxis)?.label ?? yAxis;

  const { pareto, dominated, paretoLineX, paretoLineY } = useMemo(() => {
    const pareto = candidates.filter((c) => c.is_pareto);
    const dominated = candidates.filter((c) => !c.is_pareto);
    // Sort Pareto front by X for a clean line
    const sortedPareto = [...pareto].sort((a, b) => (a.properties[xAxis] ?? 0) - (b.properties[xAxis] ?? 0));
    return {
      pareto,
      dominated,
      paretoLineX: sortedPareto.map((c) => c.properties[xAxis] ?? null),
      paretoLineY: sortedPareto.map((c) => c.properties[yAxis] ?? null),
    };
  }, [candidates, xAxis, yAxis]);

  const labelFor = (c: Candidate) =>
    Object.entries(c.composition).map(([el, v]) => `${el}: ${v.toFixed(1)}%`).join("<br>") +
    `<br>Rank #${c.pareto_rank} • Score ${c.score.toFixed(2)}`;

  const paretoTrace: Plotly.Data = {
    type: "scatter",
    mode: "lines+markers",
    name: "Pareto frontier",
    x: paretoLineX,
    y: paretoLineY,
    line: { color: CHART.fgSoft, width: 1.5, dash: "dot" },
    marker: { size: 0.1, opacity: 0 },
    hoverinfo: "skip",
    showlegend: false,
  } as Plotly.Data;

  const paretoMarkers: Plotly.Data = {
    type: "scatter",
    mode: "markers+text",
    name: "Pareto",
    x: pareto.map((c) => c.properties[xAxis] ?? null),
    y: pareto.map((c) => c.properties[yAxis] ?? null),
    text: pareto.map((c) => `#${c.pareto_rank}`),
    textposition: "top center",
    textfont: { color: CHART.muted, size: 9 },
    hovertext: pareto.map(labelFor),
    hovertemplate: "%{hovertext}<extra>Pareto</extra>",
    marker: {
      size: 14,
      symbol: "hexagon",
      color: pareto.map((c) => c.score),
      colorscale: "Viridis",
      showscale: true,
      colorbar: { title: { text: "Score" }, len: 0.6, thickness: 10, x: 1.08 },
      line: { color: CHART.fg, width: 1.5 },
    },
  } as Plotly.Data;

  const dominatedTrace: Plotly.Data = {
    type: "scatter",
    mode: "markers",
    name: "Dominated",
    x: dominated.map((c) => c.properties[xAxis] ?? null),
    y: dominated.map((c) => c.properties[yAxis] ?? null),
    hovertext: dominated.map(labelFor),
    hovertemplate: "%{hovertext}<extra>Dominated</extra>",
    visible: showDominated ? true : "legendonly",
    marker: {
      size: 7,
      color: CHART.faint,
      line: { color: CHART.outline, width: 0.5 },
    },
  } as Plotly.Data;

  const layout: Partial<Plotly.Layout> = {
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    xaxis: { color: CHART.axis, gridcolor: CHART.grid, title: { text: xLabel }, tickfont: { size: 11 } },
    yaxis: { color: CHART.axis, gridcolor: CHART.grid, title: { text: yLabel }, tickfont: { size: 11 } },
    font: { color: CHART.muted, size: 11, family: CHART.font },
    margin: { t: 10, b: 50, l: 60, r: 100 },
    showlegend: false,
  };

  function handleClick(event: Readonly<Plotly.PlotMouseEvent>) {
    const pt = event.points[0];
    if (!pt) return;
    const isPareto = pt.curveNumber === 1;
    const arr = isPareto ? pareto : dominated;
    const c = arr[pt.pointIndex];
    if (!c) return;
    const mouseEvent = (event as unknown as { event?: MouseEvent }).event;
    const anchor = mouseEvent ? { x: mouseEvent.clientX, y: mouseEvent.clientY } : undefined;
    selectElement({
      type: "candidate_card",
      data: { composition: c.composition, properties: c.properties, pareto_rank: c.pareto_rank, score: c.score, is_pareto: c.is_pareto },
      canvas_summary: { n_candidates: candidates.length, x_prop: xAxis, y_prop: yAxis, n_pareto: pareto.length },
      anchor,
    });
  }

  function saveCandidate(c: Candidate, e: React.MouseEvent) {
    e.stopPropagation();
    addComposition({
      composition: c.composition,
      properties: c.properties as Record<string, number>,
      bookmarked: true,
      rejected: false,
    });
  }

  return (
    <div className="flex flex-col gap-3 h-full">
      {/* Controls */}
      <div className="flex items-center gap-2 flex-wrap shrink-0">
        <div className="flex items-center gap-1.5 text-[11px] text-subtle">
          <Sparkles size={11} className="text-fg" />
          <span className="font-medium text-fg">{pareto.length}</span>
          <span>Pareto · </span>
          <span className="font-medium text-muted">{dominated.length}</span>
          <span>dominated</span>
          {candidates[0]?.method && (
            <span className="ml-2 px-1.5 py-0.5 rounded bg-fg/10 text-fg border border-line font-mono text-[9px] uppercase tracking-wider">
              {candidates[0].method === "bo_qehvi" ? "BoTorch qEHVI" : "random"}
            </span>
          )}
        </div>

        <div className="flex items-center gap-1.5 ml-auto text-[11px] text-subtle">
          <span>X</span>
          <select value={xAxis} onChange={(e) => setXAxis(e.target.value)}
            className="bg-fg/[0.04] border border-line rounded-md px-2 py-1 text-fg outline-none focus:border-fg/40 cursor-pointer">
            {AXIS_OPTIONS.map((o) => <option key={o.key} value={o.key} className="bg-raised">{o.label}</option>)}
          </select>
          <span>Y</span>
          <select value={yAxis} onChange={(e) => setYAxis(e.target.value)}
            className="bg-fg/[0.04] border border-line rounded-md px-2 py-1 text-fg outline-none focus:border-fg/40 cursor-pointer">
            {AXIS_OPTIONS.map((o) => <option key={o.key} value={o.key} className="bg-raised">{o.label}</option>)}
          </select>
          <label className="flex items-center gap-1 cursor-pointer ml-1">
            <input type="checkbox" checked={showDominated} onChange={(e) => setShowDominated(e.target.checked)}
              className="accent-fg cursor-pointer" />
            <span>Show dominated</span>
          </label>
        </div>
      </div>

      <div className="h-64 shrink-0">
        <Plot
          data={[paretoTrace, paretoMarkers, dominatedTrace]}
          layout={layout}
          config={{ displayModeBar: false, responsive: true }}
          style={{ width: "100%", height: "100%" }}
          onClick={handleClick}
        />
      </div>

      <div className="flex-1 overflow-y-auto space-y-1.5 pr-1">
        {pareto.map((c) => {
          const saved = session.compositions.find(
            (x) => JSON.stringify(x.composition) === JSON.stringify(c.composition)
          );
          return (
            <div
              key={c.pareto_rank}
              className="rounded-lg bg-fg/[0.04] hover:bg-fg/[0.07] border border-line hover:border-fg/40 px-3 py-2 flex items-start justify-between gap-2 cursor-pointer transition-all"
              onClick={(e) =>
                selectElement({
                  type: "candidate_card",
                  data: { composition: c.composition, properties: c.properties, pareto_rank: c.pareto_rank, score: c.score, is_pareto: true },
                  canvas_summary: { n_candidates: candidates.length, n_pareto: pareto.length },
                  anchor: { x: e.clientX, y: e.clientY },
                })
              }
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5 mb-0.5">
                  <span className="text-[10px] font-bold text-fg bg-fg/10 border border-line rounded px-1.5 py-0.5 uppercase tracking-wider">
                    #{c.pareto_rank}
                  </span>
                  <span className="text-[11px] text-muted truncate font-mono">
                    {Object.entries(c.composition).filter(([, v]) => v > 0.5).map(([el, v]) => `${el}${v.toFixed(0)}`).join("-")}
                  </span>
                </div>
                <div className="text-[10px] text-subtle font-mono">
                  Score {c.score.toFixed(2)} · {xLabel}: {c.properties[xAxis]?.toFixed(2) ?? "—"} · {yLabel}: {c.properties[yAxis]?.toFixed(0) ?? "—"}
                </div>
              </div>
              {!saved ? (
                <button
                  className="shrink-0 text-subtle hover:text-fg transition-colors"
                  onClick={(e) => saveCandidate(c, e)}
                  title="Bookmark"
                >
                  <Bookmark size={13} />
                </button>
              ) : (
                <button
                  className="shrink-0 text-subtle hover:text-bad transition-colors"
                  onClick={(e) => { e.stopPropagation(); toggleReject(saved.id); }}
                  title="Reject"
                >
                  <ThumbsDown size={13} />
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
