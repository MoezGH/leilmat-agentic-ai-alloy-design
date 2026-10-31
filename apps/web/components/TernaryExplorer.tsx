"use client";
/**
 * TernaryExplorer — heatmap of a chosen property across the full A-B-C simplex.
 *
 *  Workflow:
 *  1. Pick 3 elements from current composition (auto, top 3 by atomic %)
 *  2. Click "Sample" → generates 66 compositions on a 10-step simplex
 *  3. Backend batch-predicts properties for all 66
 *  4. Renders scatterternary colored by chosen property
 *  5. Click any point → composition fills sliders + Local AI fires
 */
import { useState, useMemo } from "react";
import dynamic from "next/dynamic";
import { Loader2, Grid3x3, Atom } from "lucide-react";
import { toast } from "sonner";
import { useCanvasStore } from "@/lib/store";
import { predictBatch, predictProperties } from "@/lib/api";
import { CHART } from "@/lib/chartTheme";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

const STEPS = 10;   // 11 grid lines per axis → C(11,2)+11 = 66 compositions

interface SimplexPoint {
  composition: Record<string, number>;
  properties: Record<string, number | null>;
  a: number;
  b: number;
  c: number;
}

interface TernaryExplorerProps {
  elements: [string, string, string];
}

const HEATMAP_PROPS = [
  { key: "density_g_cm3", label: "Density (g/cm³)" },
  { key: "melting_point_K", label: "Melting Pt (K)" },
  { key: "yield_strength_MPa", label: "Yield Strength (MPa)" },
  { key: "formation_energy_eV_per_atom", label: "Formation E (eV/atom)" },
  { key: "electronegativity_mean", label: "Electronegativity" },
];

function generateSimplex(elements: [string, string, string], steps: number): Record<string, number>[] {
  const out: Record<string, number>[] = [];
  for (let i = 0; i <= steps; i++) {
    for (let j = 0; j <= steps - i; j++) {
      const k = steps - i - j;
      out.push({
        [elements[0]]: Math.round((i / steps) * 1000) / 10,
        [elements[1]]: Math.round((j / steps) * 1000) / 10,
        [elements[2]]: Math.round((k / steps) * 1000) / 10,
      });
    }
  }
  return out;
}

export function TernaryExplorer({ elements }: TernaryExplorerProps) {
  const { selectElement, setComposition, setProperties, addComposition } = useCanvasStore();
  const [points, setPoints] = useState<SimplexPoint[]>([]);
  const [property, setProperty] = useState("density_g_cm3");
  const [loading, setLoading] = useState(false);

  async function sampleGrid() {
    setLoading(true);
    setPoints([]);
    try {
      const compositions = generateSimplex(elements, STEPS);
      const res = await predictBatch(compositions);
      const populated: SimplexPoint[] = res.results.map((r, i) => ({
        composition: r.composition,
        properties: r as unknown as Record<string, number | null>,
        a: (compositions[i][elements[0]] ?? 0) / 100,
        b: (compositions[i][elements[1]] ?? 0) / 100,
        c: (compositions[i][elements[2]] ?? 0) / 100,
      }));
      setPoints(populated);
      toast.success(`Sampled ${populated.length} compositions across the ${elements.join("-")} simplex`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Batch prediction failed");
    } finally {
      setLoading(false);
    }
  }

  const propLabel = HEATMAP_PROPS.find((p) => p.key === property)?.label ?? property;

  const { a, b, c, vals, text } = useMemo(() => {
    if (!points.length) return { a: [], b: [], c: [], vals: [], text: [] };
    return {
      a: points.map((p) => p.a),
      b: points.map((p) => p.b),
      c: points.map((p) => p.c),
      vals: points.map((p) => (p.properties[property] ?? null) as number | null),
      text: points.map((p) =>
        `${elements[0]}: ${(p.a * 100).toFixed(0)}%<br>` +
        `${elements[1]}: ${(p.b * 100).toFixed(0)}%<br>` +
        `${elements[2]}: ${(p.c * 100).toFixed(0)}%<br>` +
        `${propLabel}: ${p.properties[property]?.toFixed(2) ?? "—"}`
      ),
    };
  }, [points, property, elements, propLabel]);

  const trace: Plotly.Data = {
    type: "scatterternary",
    mode: "markers",
    a, b, c, text,
    hovertemplate: "%{text}<extra></extra>",
    marker: {
      size: 14,
      symbol: "hexagon",
      color: vals,
      colorscale: "Viridis",
      showscale: true,
      colorbar: { title: { text: propLabel }, len: 0.7, thickness: 12 },
      line: { color: CHART.outline, width: 0.5 },
    },
  } as Plotly.Data;

  const layout: Partial<Plotly.Layout> = {
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    ternary: {
      sum: 1,
      aaxis: { title: { text: elements[0] }, color: CHART.muted, gridcolor: CHART.grid, linecolor: CHART.zero, tickfont: { size: 10 } },
      baxis: { title: { text: elements[1] }, color: CHART.muted, gridcolor: CHART.grid, linecolor: CHART.zero, tickfont: { size: 10 } },
      caxis: { title: { text: elements[2] }, color: CHART.muted, gridcolor: CHART.grid, linecolor: CHART.zero, tickfont: { size: 10 } },
      bgcolor: "transparent",
    },
    font: { color: CHART.muted, size: 12, family: CHART.font },
    margin: { t: 10, b: 10, l: 30, r: 30 },
  };

  async function handleClick(event: Readonly<Plotly.PlotMouseEvent>) {
    const pt = event.points[0];
    if (!pt) return;
    const idx = pt.pointIndex;
    const entry = points[idx];
    if (!entry) return;

    const mouseEvent = (event as unknown as { event?: MouseEvent }).event;
    const anchor = mouseEvent ? { x: mouseEvent.clientX, y: mouseEvent.clientY } : undefined;

    // Fill main composition with the clicked point
    setComposition(entry.composition);
    // Auto-predict using the full predict endpoint (so we get all properties + details)
    try {
      const res = await predictProperties(entry.composition);
      setProperties(res.properties);
      addComposition({ composition: entry.composition, properties: res.properties, bookmarked: false, rejected: false });
    } catch {/* silent — user can re-predict */}

    selectElement({
      type: "composition_point",
      data: { composition: entry.composition, properties: entry.properties },
      canvas_summary: {
        sampled_property: property,
        n_grid_points: points.length,
        elements,
      },
      anchor,
    });
  }

  return (
    <div className="flex flex-col h-full gap-3">
      <div className="flex items-center gap-2 shrink-0 flex-wrap">
        <div className="flex items-center gap-1.5 text-[11px] text-subtle">
          <Atom size={11} />
          {elements.map((el, i) => (
            <span key={el}>
              <span className="font-mono text-fg font-semibold">{el}</span>
              {i < 2 && <span className="text-subtle mx-1">·</span>}
            </span>
          ))}
        </div>

        <div className="flex items-center gap-2 ml-auto">
          <select
            value={property}
            onChange={(e) => setProperty(e.target.value)}
            disabled={!points.length}
            className="bg-fg/[0.04] border border-line rounded-md px-2 py-1 text-[11px] text-fg outline-none focus:border-fg/40 cursor-pointer disabled:opacity-40"
          >
            {HEATMAP_PROPS.map((p) => (
              <option key={p.key} value={p.key} className="bg-raised">{p.label}</option>
            ))}
          </select>

          <button
            onClick={sampleGrid}
            disabled={loading}
            className="flex items-center gap-1.5 text-[11px] font-semibold px-2.5 py-1 rounded-md bg-fg hover:bg-fg/90 disabled:opacity-40 disabled:cursor-not-allowed text-bg transition-colors"
          >
            {loading ? <Loader2 size={11} className="animate-spin" /> : <Grid3x3 size={11} />}
            {loading ? "Sampling…" : points.length ? "Resample" : "Sample"}
          </button>
        </div>
      </div>

      <div className="flex-1 min-h-0">
        {points.length === 0 && !loading ? (
          <div className="flex flex-col items-center justify-center h-full text-center text-[12px] text-subtle gap-2">
            <div className="w-10 h-10 rounded-full bg-fg/[0.03] border border-line flex items-center justify-center">
              <Grid3x3 size={16} className="text-subtle" />
            </div>
            <div>
              <p>Click <span className="text-fg font-medium">Sample</span> to predict {(STEPS + 1) * (STEPS + 2) / 2} compositions</p>
              <p className="text-subtle text-[11px] mt-1">Across the {elements.join("-")} simplex</p>
            </div>
          </div>
        ) : loading ? (
          <div className="flex flex-col items-center justify-center h-full text-[12px] text-subtle gap-2">
            <Loader2 size={16} className="animate-spin text-fg" />
            <span>Predicting {(STEPS + 1) * (STEPS + 2) / 2} compositions…</span>
          </div>
        ) : (
          <Plot
            data={[trace]}
            layout={layout}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: "100%", height: "100%" }}
            onClick={handleClick}
          />
        )}
      </div>
    </div>
  );
}
