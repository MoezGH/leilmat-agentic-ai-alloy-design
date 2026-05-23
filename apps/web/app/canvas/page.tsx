"use client";

import { useState } from "react";
import { Bot, X, Zap, Atom, FlaskConical, Target, Sparkles, Loader2, Bookmark, LayoutGrid } from "lucide-react";
import { toast } from "sonner";
import { useCanvasStore } from "@/lib/store";
import { GlobalAIPanel } from "@/components/GlobalAIPanel";
import { LocalAISuggestion } from "@/components/LocalAISuggestion";
import { PropertyDashboard } from "@/components/PropertyDashboard";
import { PhaseDiagram } from "@/components/PhaseDiagram";
import { ParetoExplorer } from "@/components/ParetoExplorer";
import { ExplorationTrajectory } from "@/components/ExplorationTrajectory";
import { TernaryExplorer } from "@/components/TernaryExplorer";
import { PeriodicTable } from "@/components/PeriodicTable";
import { ManufacturabilityPanel } from "@/components/ManufacturabilityPanel";
import { predictProperties, getPhaseDiagram, runInverseDesign, getHullDistance } from "@/lib/api";
import { useModelHealth } from "@/lib/useModelHealth";

export default function CanvasPage() {
  const {
    session, globalAIPanelOpen, setGlobalAIPanelOpen, addComposition,
    composition, setComposition, properties, setProperties,
    targetDensityMax, setTargetDensityMax, targetMeltMin, setTargetMeltMin,
    sweepResult, sweepInProgress,
  } = useCanvasStore();

  const [predicting, setPredicting] = useState(false);
  const [periodicOpen, setPeriodicOpen] = useState(false);
  const [hullDistance, setHullDistance] = useState<{
    e_above_hull: number | null;
    e_above_hull_meV?: number;
    stability: "stable" | "metastable" | "unstable" | "unknown";
    note: string;
    source?: string;
    error?: string;
  } | null>(null);

  const [phaseElements, setPhaseElements] = useState("Al,Mg,Si");
  const [stablePhases, setStablePhases] = useState<{ formula: string; formation_energy: number }[]>([]);
  const [loadingPhase, setLoadingPhase] = useState(false);

  const [candidates, setCandidates] = useState<{
    composition: Record<string, number>;
    properties: Record<string, number | null>;
    pareto_rank: number;
    score: number;
  }[]>([]);
  const [runningInverse, setRunningInverse] = useState(false);

  // Poll model health so the formation-energy card shows a loading indicator
  // during M3GNet cold-start instead of silently falling back to Miedema.
  const modelHealth = useModelHealth(true);
  const m3gnetState: "loading" | "fitting_calibrator" | "ready" | "failed" | null =
    !modelHealth ? null
    : modelHealth.m3gnet.status === "failed" ? "failed"
    : modelHealth.m3gnet.status !== "loaded" ? "loading"
    : modelHealth.calibrator.status === "fitted" ? "ready"
    : modelHealth.calibrator.status === "failed" ? "failed"
    : "fitting_calibrator";

  async function handlePredict() {
    setPredicting(true);
    setHullDistance(null);
    try {
      const res = await predictProperties(composition);
      setProperties(res.properties);
      addComposition({ composition, properties: res.properties, bookmarked: false, rejected: false });
      toast.success("Properties predicted");

      // Fire hull distance asynchronously — doesn't block the UI update
      const fe = res.properties._details?.formation_energy_eV_per_atom?.value;
      if (fe != null && Object.keys(composition).length >= 2) {
        getHullDistance(composition, fe).then((hull) => {
          if (hull) setHullDistance(hull);
        });
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Prediction failed");
    } finally {
      setPredicting(false);
    }
  }

  async function handleLoadPhase() {
    setLoadingPhase(true);
    try {
      const elements = phaseElements.split(",").map((s) => s.trim()).filter(Boolean);
      const res = await getPhaseDiagram(elements);
      setStablePhases(res.stable_phases ?? []);
      if (!res.stable_phases?.length) toast.warning("No phase data returned");
      else toast.success(`${res.stable_phases.length} stable phases loaded`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Phase diagram failed");
    } finally {
      setLoadingPhase(false);
    }
  }

  async function handleInverseDesign() {
    setRunningInverse(true);
    try {
      const result = await runInverseDesign({
        elements: Object.keys(composition),
        targets: [
          { name: "density_g_cm3", max_val: targetDensityMax, optimize: "minimize" },
          { name: "melting_point_K", min_val: targetMeltMin, optimize: "maximize" },
        ],
        n_candidates: 10,
        n_iterations: 30,
      });
      setCandidates(result);
      toast.success(`${result.length} candidates found`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Inverse design failed");
    } finally {
      setRunningInverse(false);
    }
  }

  function toggleElement(symbol: string) {
    const defaultPct = 5;
    if (composition[symbol] != null) {
      // Remove and rescale others back to 100%
      const next: Record<string, number> = {};
      const others = Object.entries(composition).filter(([el]) => el !== symbol);
      const otherSum = others.reduce((s, [, v]) => s + v, 0);
      if (otherSum > 0) {
        for (const [el, v] of others) {
          next[el] = Math.round((v / otherSum) * 100 * 10) / 10;
        }
      }
      setComposition(next);
      return;
    }
    // Add at 5%, scale existing entries to fit remaining 95%
    const otherSum = Object.values(composition).reduce((a, b) => a + b, 0);
    const scale = otherSum > 0 ? (100 - defaultPct) / otherSum : 0;
    const next: Record<string, number> = { [symbol]: defaultPct };
    for (const [el, v] of Object.entries(composition)) {
      next[el] = Math.round(v * scale * 10) / 10;
    }
    setComposition(next);
  }

  const totalFrac = Object.values(composition).reduce((a, b) => a + b, 0);
  const hasProperties = Object.keys(properties).length > 0;
  const bookmarkedCount = session.compositions.filter(c => c.bookmarked).length;

  // Top-3 elements by atomic % for the ternary explorer
  const ternaryElements = (Object.entries(composition)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([el]) => el)) as [string, string, string];
  const canRenderTernary = ternaryElements.length === 3;

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-[#0a0b0f]">
      <div className="fixed inset-0 pointer-events-none opacity-30" style={{
        background: "radial-gradient(ellipse 80% 50% at 50% -20%, rgba(56,189,248,0.15), transparent 70%), radial-gradient(ellipse 60% 50% at 80% 80%, rgba(139,92,246,0.08), transparent 60%)"
      }} />

      {/* ── Topbar ── */}
      <header className="relative z-10 flex items-center justify-between px-6 h-14 border-b border-white/[0.06] shrink-0 bg-[#0a0b0f]/80 backdrop-blur-xl">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-sky-400 to-blue-600 flex items-center justify-center shadow-lg shadow-sky-500/20">
            <Atom size={15} className="text-white" />
          </div>
          <div className="flex items-baseline gap-2.5">
            <span className="font-semibold text-[15px] tracking-tight text-white">
              Leil<span className="text-sky-400">Mat</span>
            </span>
            <span className="text-[11px] text-slate-500 font-medium uppercase tracking-wider">Design Canvas</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-white/[0.04] border border-white/[0.06]">
            <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-[11px] text-slate-400 font-medium">DeepSeek V4 Pro</span>
          </div>

          <button
            onClick={() => setGlobalAIPanelOpen(!globalAIPanelOpen)}
            className={`flex items-center gap-2 text-[12px] px-3 py-1.5 rounded-md font-medium transition-all ${
              globalAIPanelOpen
                ? "bg-sky-500/15 text-sky-300 border border-sky-500/30 shadow-lg shadow-sky-500/10"
                : "bg-white/[0.04] hover:bg-white/[0.08] text-slate-300 border border-white/[0.06] hover:border-white/[0.12]"
            }`}
          >
            <Sparkles size={13} />
            Global AI
            {session.messages.length > 0 && (
              <span className="bg-sky-500 text-white text-[10px] rounded-full px-1.5 leading-none py-0.5 font-semibold">
                {session.messages.length}
              </span>
            )}
          </button>
        </div>
      </header>

      {/* ── Body ── */}
      <div className="relative z-10 flex flex-1 overflow-hidden">

        {/* ── Left Sidebar ── */}
        <aside className="w-[300px] shrink-0 border-r border-white/[0.06] flex flex-col overflow-y-auto bg-[#0c0e13]/60">

          <section className="p-5 border-b border-white/[0.06]">
            <SectionHeader icon={<Atom size={11} />} label="Composition" trailing={`${Object.keys(composition).length}`} />

            <div className="space-y-3 mt-3.5">
              {Object.entries(composition).map(([el, frac]) => (
                <div key={el} className="group flex items-center gap-2.5">
                  <span className="text-[11px] font-mono font-semibold text-sky-400 w-6 tabular-nums">{el}</span>
                  <input
                    type="range" min={0} max={100} step={0.5} value={frac}
                    onChange={(e) => setComposition({ ...composition, [el]: parseFloat(e.target.value) })}
                    className="flex-1 cursor-pointer"
                  />
                  <span className="text-[11px] font-mono text-slate-300 w-10 text-right tabular-nums">{frac.toFixed(1)}</span>
                  <button
                    onClick={() => { const n = { ...composition }; delete n[el]; setComposition(n); }}
                    className="text-slate-700 hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100"
                  >
                    <X size={11} />
                  </button>
                </div>
              ))}
            </div>

            <button
              onClick={() => setPeriodicOpen(true)}
              className="w-full mt-4 flex items-center justify-center gap-2 py-2 bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] hover:border-sky-500/30 rounded-lg text-[12px] font-medium text-slate-300 hover:text-white transition-all group"
            >
              <LayoutGrid size={12} className="text-slate-500 group-hover:text-sky-400 transition-colors" />
              Periodic Table
            </button>

            <div className="flex items-center justify-between mt-3 text-[10px] text-slate-600 font-medium uppercase tracking-wider">
              <span>Total</span>
              <span className={`tabular-nums ${totalFrac > 101 ? "text-red-400" : totalFrac < 99 ? "text-amber-400" : "text-emerald-400"}`}>
                {totalFrac.toFixed(1)}%
              </span>
            </div>

            <button
              onClick={handlePredict}
              disabled={predicting || !Object.keys(composition).length}
              className="w-full mt-4 flex items-center justify-center gap-2 py-2.5 bg-sky-500 hover:bg-sky-400 disabled:bg-white/[0.05] disabled:text-slate-600 disabled:cursor-not-allowed rounded-lg text-[13px] font-semibold text-white shadow-lg shadow-sky-500/20 hover:shadow-sky-500/30 transition-all"
            >
              {predicting ? <Loader2 size={14} className="animate-spin" /> : <Zap size={13} fill="currentColor" />}
              {predicting ? "Predicting…" : "Predict Properties"}
            </button>
          </section>

          <section className="p-5 border-b border-white/[0.06]">
            <SectionHeader icon={<FlaskConical size={11} />} label="Phase System" />
            <div className="flex gap-1.5 mt-3">
              <input
                value={phaseElements}
                onChange={(e) => setPhaseElements(e.target.value)}
                placeholder="Al,Mg,Si"
                className="flex-1 bg-white/[0.03] border border-white/[0.06] rounded-md px-2.5 py-1.5 text-[11px] font-mono text-slate-200 placeholder:text-slate-600 outline-none focus:border-sky-500/40 focus:bg-white/[0.05] transition-all"
              />
              <button
                onClick={handleLoadPhase}
                disabled={loadingPhase}
                className="px-3 py-1.5 bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.06] rounded-md text-[11px] font-medium text-slate-300 hover:text-white transition-all disabled:opacity-40"
              >
                {loadingPhase ? <Loader2 size={11} className="animate-spin" /> : "Load"}
              </button>
            </div>
            <p className="text-[10px] text-slate-600 mt-2 leading-relaxed">
              Fetches stable phases from Materials Project
            </p>
          </section>

          <section className="p-5 border-b border-white/[0.06]">
            <SectionHeader icon={<Target size={11} />} label="Inverse Design" />
            <div className="space-y-2.5 mt-3.5">
              <NumberRow label="Density max" value={targetDensityMax} step={0.1} unit="g/cm³" onChange={setTargetDensityMax} />
              <NumberRow label="Melt point min" value={targetMeltMin} step={50} unit="K" onChange={setTargetMeltMin} />
            </div>
            <button
              onClick={handleInverseDesign}
              disabled={runningInverse || !Object.keys(composition).length}
              className="w-full mt-4 flex items-center justify-center gap-2 py-2 bg-violet-500/15 hover:bg-violet-500/25 border border-violet-500/30 hover:border-violet-500/50 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg text-[12px] font-semibold text-violet-300 transition-all"
            >
              {runningInverse ? <Loader2 size={12} className="animate-spin" /> : <Target size={12} />}
              {runningInverse ? "Optimizing…" : "Run Optimization"}
            </button>
          </section>

          <section className="p-5 mt-auto">
            <SectionHeader icon={<Bookmark size={11} />} label="Session" />
            <div className="space-y-2 mt-3">
              <StatRow label="Explored" value={session.compositions.length} />
              <StatRow label="Bookmarked" value={bookmarkedCount} accent="sky" />
              <StatRow label="Rejected" value={session.compositions.filter(c => c.rejected).length} />
              {sweepResult && (
                <StatRow label={`Sweep ${sweepResult.vary}`} value={sweepResult.points.length} accent="emerald" />
              )}
            </div>
          </section>
        </aside>

        {/* ── Main Content ── */}
        <main className="flex-1 overflow-y-auto">
          <div className="max-w-[1100px] mx-auto px-8 py-8 space-y-6">

            <Panel
              title="Properties"
              subtitle="Predicted from composition — click any property for AI insights"
              badge={hasProperties ? "Live" : undefined}
              empty={!hasProperties}
              emptyTitle="No prediction yet"
              emptyText="Run Predict Properties in the sidebar to see the radar chart"
              emptyIcon={<Zap size={18} className="text-slate-700" />}
            >
              {hasProperties && (
                <div className="h-72">
                  <PropertyDashboard composition={composition} properties={properties} hullDistance={hullDistance} m3gnetState={m3gnetState} />
                </div>
              )}
            </Panel>

            {/* Manufacturability — only show when we have a manufacturability block in the prediction */}
            {hasProperties && (properties as Record<string, unknown>).manufacturability != null && (
              <Panel
                title="Manufacturability"
                subtitle="Castability · weldability · cost — click any score for AI suggestions"
                badge={(properties as Record<string, unknown>).manufacturability_score != null
                  ? `${Math.round((properties as Record<string, number>).manufacturability_score)} / 100`
                  : undefined}
                empty={false}
                emptyTitle=""
                emptyText=""
                emptyIcon={null}
              >
                <div className="h-44">
                  <ManufacturabilityPanel
                    composition={composition}
                    data={(properties as Record<string, unknown>).manufacturability as Parameters<typeof ManufacturabilityPanel>[0]["data"]}
                  />
                </div>
              </Panel>
            )}

            {/* Ternary Composition Explorer */}
            <Panel
              title="Ternary Composition Explorer"
              subtitle={canRenderTernary
                ? `Heatmap across ${ternaryElements.join("–")} simplex — click any point to design from there`
                : "Add at least 3 elements to enable simplex sampling"}
              empty={!canRenderTernary}
              emptyTitle="Need 3+ elements"
              emptyText="The ternary explorer needs at least 3 elements in the composition"
              emptyIcon={<Atom size={18} className="text-slate-700" />}
            >
              {canRenderTernary && (
                <div className="h-[420px]">
                  <TernaryExplorer elements={ternaryElements} />
                </div>
              )}
            </Panel>

            {/* Exploration trajectory — appears after a sweep action */}
            {(sweepResult || sweepInProgress) && (
              <Panel
                title="Exploration Trajectory"
                subtitle={sweepResult ? `Sweeping ${sweepResult.vary} from ${sweepResult.from}% to ${sweepResult.to}%` : "Running sweep…"}
                badge={sweepInProgress ? "Live" : sweepResult ? `${sweepResult.points.length} points` : undefined}
                empty={!sweepResult}
                emptyTitle="Sweep running…"
                emptyText="Generating compositions and predicting properties"
                emptyIcon={<Loader2 size={18} className="text-slate-700 animate-spin" />}
              >
                {sweepResult && (
                  <div className="h-72">
                    <ExplorationTrajectory result={sweepResult} />
                  </div>
                )}
              </Panel>
            )}

            <Panel
              title="Phase Diagram"
              subtitle="Stable phases from Materials Project"
              badge={stablePhases.length > 0 ? `${stablePhases.length} phases` : undefined}
              empty={stablePhases.length === 0}
              emptyTitle="No phase data"
              emptyText="Enter elements and click Load in the sidebar"
              emptyIcon={<FlaskConical size={18} className="text-slate-700" />}
            >
              {stablePhases.length > 0 && (
                <div className="h-72">
                  <PhaseDiagram
                    elements={phaseElements.split(",").map(s => s.trim())}
                    stablePhases={stablePhases}
                  />
                </div>
              )}
            </Panel>

            <Panel
              title="Pareto Candidates"
              subtitle="Inverse design results — click any point for AI insights"
              badge={candidates.length > 0 ? `${candidates.length} candidates` : undefined}
              empty={candidates.length === 0}
              emptyTitle="No optimization run"
              emptyText="Set target properties and click Run Optimization"
              emptyIcon={<Target size={18} className="text-slate-700" />}
            >
              {candidates.length > 0 && (
                <div className="h-[520px]">
                  <ParetoExplorer candidates={candidates} />
                </div>
              )}
            </Panel>

          </div>
        </main>

        <GlobalAIPanel />
      </div>

      <LocalAISuggestion />

      <PeriodicTable
        open={periodicOpen}
        onClose={() => setPeriodicOpen(false)}
        composition={composition}
        onToggleElement={toggleElement}
      />
    </div>
  );
}

function SectionHeader({ icon, label, trailing }: { icon: React.ReactNode; label: string; trailing?: string }) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-1.5 text-slate-500">
        {icon}
        <span className="text-[10px] font-semibold uppercase tracking-[0.12em]">{label}</span>
      </div>
      {trailing && (
        <span className="text-[10px] font-mono text-slate-600 bg-white/[0.03] px-1.5 py-0.5 rounded">{trailing}</span>
      )}
    </div>
  );
}

function NumberRow({ label, value, step, unit, onChange }: { label: string; value: number; step: number; unit: string; onChange: (v: number) => void }) {
  return (
    <label className="flex items-center gap-2">
      <span className="text-[11px] text-slate-500 flex-1">{label}</span>
      <input
        type="number" step={step} value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-20 bg-white/[0.03] border border-white/[0.06] rounded-md px-2 py-1 text-[11px] font-mono text-slate-200 outline-none focus:border-sky-500/40 focus:bg-white/[0.05] transition-all text-right tabular-nums"
      />
      <span className="text-[10px] text-slate-600 w-10 font-medium">{unit}</span>
    </label>
  );
}

function StatRow({ label, value, accent }: { label: string; value: number; accent?: "sky" | "amber" | "emerald" }) {
  const accentClass = accent === "sky" ? "text-sky-400"
    : accent === "amber" ? "text-amber-400"
    : accent === "emerald" ? "text-emerald-400"
    : "text-slate-300";
  return (
    <div className="flex items-center justify-between text-[11px]">
      <span className="text-slate-500">{label}</span>
      <span className={`font-mono font-semibold tabular-nums ${accentClass}`}>{value}</span>
    </div>
  );
}

function Panel({ title, subtitle, badge, empty, emptyTitle, emptyText, emptyIcon, children }: {
  title: string;
  subtitle?: string;
  badge?: string;
  empty: boolean;
  emptyTitle: string;
  emptyText: string;
  emptyIcon: React.ReactNode;
  children?: React.ReactNode;
}) {
  return (
    <div className="panel overflow-hidden">
      <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06]">
        <div>
          <h2 className="text-[14px] font-semibold text-slate-100 tracking-tight">{title}</h2>
          {subtitle && <p className="text-[11px] text-slate-500 mt-0.5">{subtitle}</p>}
        </div>
        {badge && (
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-sky-500/10 text-sky-300 border border-sky-500/20 font-semibold uppercase tracking-wider">
            {badge}
          </span>
        )}
      </div>
      {empty ? (
        <div className="flex flex-col items-center justify-center py-14 px-6 text-center">
          <div className="w-10 h-10 rounded-full bg-white/[0.03] border border-white/[0.06] flex items-center justify-center mb-3">
            {emptyIcon}
          </div>
          <p className="text-[13px] font-medium text-slate-400">{emptyTitle}</p>
          <p className="text-[11px] text-slate-600 mt-1 max-w-xs">{emptyText}</p>
        </div>
      ) : (
        <div className="p-6">{children}</div>
      )}
    </div>
  );
}
