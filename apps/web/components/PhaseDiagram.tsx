"use client";
/**
 * PhaseDiagram — visualises stable phases for a binary/ternary system.
 * Clicking a phase boundary triggers the Local AI popover.
 */
import dynamic from "next/dynamic";
import { useCanvasStore } from "@/lib/store";
import { CHART } from "@/lib/chartTheme";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

interface StablePhase {
  formula: string;
  formation_energy: number;
}

interface PhaseDiagramProps {
  elements: string[];
  stablePhases: StablePhase[];
}

export function PhaseDiagram({ elements, stablePhases }: PhaseDiagramProps) {
  const { selectElement } = useCanvasStore();

  const sorted = [...stablePhases].sort((a, b) => a.formation_energy - b.formation_energy);
  const labels = sorted.map((p) => p.formula);
  const energies = sorted.map((p) => p.formation_energy);

  const trace: Plotly.Data = {
    type: "bar",
    x: labels,
    y: energies,
    marker: {
      color: energies.map((e) => (e < -0.5 ? CHART.ok : e < 0 ? CHART.muted : CHART.warn)),
      line: { color: CHART.outline, width: 1 },
    },
    hovertemplate: "%{x}<br>ΔHf = %{y:.3f} eV/atom<extra></extra>",
  } as Plotly.Data;

  const layout: Partial<Plotly.Layout> = {
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    xaxis: { color: CHART.axis, gridcolor: CHART.grid, title: { text: "Phase" }, tickfont: { size: 11 } },
    yaxis: { color: CHART.axis, gridcolor: CHART.grid, title: { text: "Formation energy (eV/atom)" }, zeroline: true, zerolinecolor: CHART.zero, tickfont: { size: 11 } },
    font: { color: CHART.muted, size: 11, family: CHART.font },
    margin: { t: 10, b: 70, l: 65, r: 20 },
  };

  function handleClick(event: Readonly<Plotly.PlotMouseEvent>) {
    const pt = event.points[0];
    if (!pt) return;
    const formula = pt.x as string;
    const phase = sorted.find((p) => p.formula === formula);
    if (!phase) return;
    const mouseEvent = (event as unknown as { event?: MouseEvent }).event;
    const anchor = mouseEvent ? { x: mouseEvent.clientX, y: mouseEvent.clientY } : undefined;
    selectElement({
      type: "phase_boundary",
      data: {
        formula: phase.formula,
        formation_energy_eV_per_atom: phase.formation_energy,
        system_elements: elements,
      },
      canvas_summary: {
        n_stable_phases: stablePhases.length,
        most_stable: sorted[0]?.formula,
      },
      anchor,
    });
  }

  if (!stablePhases.length) {
    return (
      <div className="flex items-center justify-center h-full text-subtle text-sm">
        No phase data — select elements to load a diagram.
      </div>
    );
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
