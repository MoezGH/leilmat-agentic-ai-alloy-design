"use client";
/**
 * TernaryPlot — interactive ternary composition space explorer.
 * Renders a Plotly ternary scatter chart. Clicking a point selects it
 * and triggers the Local AI popover.
 */
import dynamic from "next/dynamic";
import { useCanvasStore, CompositionEntry } from "@/lib/store";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

interface TernaryPlotProps {
  elementA: string;
  elementB: string;
  elementC: string;
  compositions: CompositionEntry[];
  propertyKey?: string;
}

export function TernaryPlot({ elementA, elementB, elementC, compositions, propertyKey }: TernaryPlotProps) {
  const { selectElement } = useCanvasStore();

  const points = compositions.filter(
    (c) => c.composition[elementA] !== undefined || c.composition[elementB] !== undefined || c.composition[elementC] !== undefined
  );

  const a = points.map((p) => (p.composition[elementA] ?? 0) / 100);
  const b = points.map((p) => (p.composition[elementB] ?? 0) / 100);
  const c = points.map((p) => (p.composition[elementC] ?? 0) / 100);
  const vals = propertyKey ? points.map((p) => p.properties[propertyKey] ?? null) : null;
  const labels = points.map((p) =>
    Object.entries(p.composition).map(([el, v]) => `${el}: ${v.toFixed(1)}%`).join("<br>")
  );

  const trace: Plotly.Data = {
    type: "scatterternary",
    mode: "markers",
    a,
    b,
    c,
    text: labels,
    hovertemplate: "%{text}<extra></extra>",
    marker: {
      size: 10,
      color: vals ?? "#0ea5e9",
      colorscale: vals ? "Viridis" : undefined,
      showscale: vals !== null,
      colorbar: vals ? { title: { text: propertyKey ?? "" } } : undefined,
      line: { color: "rgba(255,255,255,0.3)", width: 1 },
    },
  } as Plotly.Data;

  const layout: Partial<Plotly.Layout> = {
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    ternary: {
      sum: 1,
      aaxis: { title: { text: elementA }, color: "#94a3b8", gridcolor: "#1e293b" },
      baxis: { title: { text: elementB }, color: "#94a3b8", gridcolor: "#1e293b" },
      caxis: { title: { text: elementC }, color: "#94a3b8", gridcolor: "#1e293b" },
      bgcolor: "rgba(15,17,23,0.5)",
    },
    font: { color: "#94a3b8", size: 12 },
    margin: { t: 20, b: 20, l: 20, r: 20 },
  };

  function handleClick(event: Readonly<Plotly.PlotMouseEvent>) {
    const pt = event.points[0];
    if (!pt) return;
    const idx = pt.pointIndex;
    const entry = points[idx];
    if (!entry) return;
    const mouseEvent = (event as unknown as { event?: MouseEvent }).event;
    const anchor = mouseEvent ? { x: mouseEvent.clientX, y: mouseEvent.clientY } : undefined;
    selectElement({
      type: "composition_point",
      data: {
        composition: entry.composition,
        properties: entry.properties,
        label: entry.label,
      },
      canvas_summary: {
        total_points: points.length,
        elements: [elementA, elementB, elementC],
        property_displayed: propertyKey ?? null,
      },
      anchor,
    });
  }

  return (
    <Plot
      data={[trace]}
      layout={layout}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: "100%", height: "100%" }}
      onClick={handleClick}
    />
  );
}
