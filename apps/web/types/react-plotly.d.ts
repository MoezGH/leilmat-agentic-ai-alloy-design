// Minimal declaration so `dynamic(() => import("react-plotly.js"), { ssr: false })`
// passes TypeScript. The real Plot component is loaded at runtime only.
declare module "react-plotly.js" {
  import type { ComponentType } from "react";
  // Loose-typed props — the codebase passes data/layout/config dynamically.
  // If you want stricter typing later, install @types/react-plotly.js.
  const Plot: ComponentType<Record<string, unknown>>;
  export default Plot;
}
