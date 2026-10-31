"use client";
/**
 * ManufacturabilityPanel — three sub-scores (castability/weldability/cost) plus overall.
 * Click any score to fire Local AI with context for that specific manufacturability axis.
 */
import { Factory, Flame, Zap, DollarSign } from "lucide-react";
import { useCanvasStore } from "@/lib/store";

interface SubScore {
  value: number | null;
  factors?: Record<string, unknown>;
  source?: string;
  cost_per_kg_USD?: number;
}

interface ManufacturabilityData {
  overall: number | null;
  castability: SubScore;
  weldability: SubScore;
  cost: SubScore & { cost_per_kg_USD?: number };
}

interface Props {
  composition: Record<string, number>;
  data: ManufacturabilityData;
}

function colorForScore(s: number | null): { bar: string; text: string; bg: string; ring: string } {
  if (s == null) return { bar: "bg-subtle", text: "text-subtle", bg: "bg-fg/10", ring: "ring-line" };
  if (s >= 75) return { bar: "bg-ok", text: "text-ok", bg: "bg-ok/10", ring: "ring-ok/25" };
  if (s >= 50) return { bar: "bg-warn",   text: "text-warn",   bg: "bg-warn/10",   ring: "ring-warn/25" };
  return { bar: "bg-bad", text: "text-bad", bg: "bg-bad/10", ring: "ring-bad/25" };
}

function castabilityHint(d: SubScore): string {
  const f = (d.factors ?? {}) as { Tm_K?: number; boosts?: Record<string, number>; penalties?: Record<string, number> };
  const parts: string[] = [];
  if (f.Tm_K) parts.push(`Tm ${f.Tm_K} K`);
  const boostList = Object.keys(f.boosts ?? {});
  const penList = Object.keys(f.penalties ?? {});
  if (boostList.length) parts.push("+ " + boostList[0]);
  if (penList.length) parts.push("− " + penList[0]);
  return parts.join(" · ");
}

function weldabilityHint(d: SubScore): string {
  const f = (d.factors ?? {}) as { method?: string; CE?: number };
  if (f.CE !== undefined) return `CE = ${f.CE} (IIW)`;
  return f.method ?? "";
}

function costHint(d: SubScore & { cost_per_kg_USD?: number }): string {
  const cost = d.cost_per_kg_USD;
  if (cost == null) return "";
  const drivers = ((d.factors ?? {}) as { top_drivers?: { element: string; USD_per_kg_of_alloy: number }[] }).top_drivers ?? [];
  const top = drivers[0]?.element;
  return cost < 1
    ? `$${cost}/kg`
    : top ? `$${cost.toLocaleString()}/kg · driven by ${top}` : `$${cost.toLocaleString()}/kg`;
}

export function ManufacturabilityPanel({ composition, data }: Props) {
  const { selectElement } = useCanvasStore();

  const rows = [
    {
      key: "castability_score",
      label: "Castability",
      icon: <Flame size={13} />,
      score: data.castability.value,
      hint: castabilityHint(data.castability),
      sub: data.castability,
    },
    {
      key: "weldability_score",
      label: "Weldability",
      icon: <Zap size={13} />,
      score: data.weldability.value,
      hint: weldabilityHint(data.weldability),
      sub: data.weldability,
    },
    {
      key: "cost_score",
      label: "Cost",
      icon: <DollarSign size={13} />,
      score: data.cost.value,
      hint: costHint(data.cost),
      sub: data.cost,
    },
  ];

  const overallColor = colorForScore(data.overall);

  return (
    <div className="flex gap-5 h-full">
      {/* Overall gauge */}
      <button
        onClick={(e) =>
          selectElement({
            type: "property_bar",
            data: {
              property_key: "manufacturability_score",
              property_label: "Overall manufacturability",
              value: data.overall,
              composition,
              detail: data,
            },
            canvas_summary: { all_manufacturability: data },
            anchor: { x: e.clientX, y: e.clientY },
          })
        }
        className={`shrink-0 w-44 rounded-xl border border-line ${overallColor.bg} hover:ring-2 ${overallColor.ring} transition-all p-5 flex flex-col items-center justify-center gap-1 group`}
      >
        <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-widest text-subtle font-semibold">
          <Factory size={11} />
          Overall
        </div>
        <div className={`text-5xl font-bold tracking-tight ${overallColor.text} group-hover:scale-105 transition-transform`}>
          {data.overall != null ? Math.round(data.overall) : "—"}
        </div>
        <div className="text-[10px] text-subtle font-mono">/ 100</div>
      </button>

      {/* Sub-scores */}
      <div className="flex-1 min-w-0 flex flex-col gap-2.5 justify-center">
        {rows.map((row) => {
          const c = colorForScore(row.score);
          const pct = row.score ?? 0;
          return (
            <button
              key={row.key}
              onClick={(e) =>
                selectElement({
                  type: "property_bar",
                  data: {
                    property_key: row.key,
                    property_label: row.label,
                    value: row.score,
                    composition,
                    detail: row.sub,
                  },
                  canvas_summary: { manufacturability_axis: row.label, all_manufacturability: data },
                  anchor: { x: e.clientX, y: e.clientY },
                })
              }
              className="text-left rounded-lg bg-fg/[0.03] hover:bg-fg/[0.06] border border-line hover:border-fg/30 px-3.5 py-2.5 transition-all group"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className={c.text}>{row.icon}</span>
                  <span className="text-[12px] font-semibold text-fg">{row.label}</span>
                </div>
                <div className="flex items-baseline gap-1">
                  <span className={`text-lg font-bold tabular-nums ${c.text}`}>
                    {row.score != null ? row.score.toFixed(0) : "—"}
                  </span>
                  <span className="text-[10px] text-subtle font-mono">/100</span>
                </div>
              </div>
              <div className="h-1.5 rounded-full bg-fg/[0.04] overflow-hidden">
                <div
                  className={`h-full ${c.bar} rounded-full transition-all`}
                  style={{ width: `${Math.max(0, Math.min(100, pct))}%` }}
                />
              </div>
              {row.hint && (
                <div className="text-[10px] text-subtle mt-1.5 font-mono truncate">{row.hint}</div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
