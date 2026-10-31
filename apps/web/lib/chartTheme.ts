/**
 * Chart colours — the INFINITE cockpit palette as literals, because Plotly and SVG attributes cannot read Tailwind roles.
 * Keep in step with the variables in app/globals.css (dark theme: the charts sit on `viewport` / `surface` Ink grounds).
 *
 * Colour in a chart is data, not decoration: series are Paper on Ink, and the three status colours are reserved for
 * values that mean ok / check / failed. Continuous heatmaps use Viridis (perceptually uniform, colour-blind-safe).
 */
export const CHART = {
  fg: "#F4F1EA",                       // series, markers: Paper
  fgSoft: "rgba(244,241,234,0.5)",     // secondary lines
  fill: "rgba(244,241,234,0.12)",      // area under a series
  faint: "rgba(244,241,234,0.4)",      // de-emphasised points
  outline: "rgba(244,241,234,0.25)",   // marker outlines
  muted: "#A8A49B",                    // axis titles, tick text, annotations
  axis: "#96928A",                     // axis lines and tick labels
  grid: "rgba(244,241,234,0.10)",      // gridlines
  zero: "rgba(244,241,234,0.25)",      // zero lines
  surface: "rgba(27,27,26,0.5)",       // plot-area ground
  ok: "#7FB896",
  warn: "#E5AA4A",
  bad: "#FF7A66",
  font: '"Barlow", system-ui, sans-serif',
} as const;
