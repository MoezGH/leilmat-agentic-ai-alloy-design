"use client";

import { useState, useEffect, useRef } from "react";
import { Bot, X, Zap, Atom, FlaskConical, Target, Sparkles, Loader2, Bookmark, LayoutGrid, HelpCircle, Lock, Check } from "lucide-react";
import { toast } from "sonner";
import { useCanvasStore } from "@/lib/store";
import { GlobalAIPanel } from "@/components/GlobalAIPanel";
import { LocalAISuggestion } from "@/components/LocalAISuggestion";
import {
  PropertyDashboard,
  PhaseAssemblageCard,
  SolidificationCard,
  TTTCard,
  MicrostructureCard,
  PrecipitationCard,
  DiffusionCard,
  GrainStructureCard,
  GrainGrowthCard,
  CPFEMStressStrainCard,
  AgingOptimizerCard,
} from "@/components/PropertyDashboard";
import { PhaseDiagram } from "@/components/PhaseDiagram";
import { JobsIndicator } from "@/components/JobsIndicator";
import { ParetoExplorer } from "@/components/ParetoExplorer";
import { ExplorationTrajectory } from "@/components/ExplorationTrajectory";
import { TernaryExplorer } from "@/components/TernaryExplorer";
import { PeriodicTable } from "@/components/PeriodicTable";
import { Bloom } from "@/components/brand/Bloom";
import { authConfigured } from "@/lib/features";
import { LeilBrand } from "@/components/brand/LeilBrand";
import { GlossaryModal } from "@/components/GlossaryModal";
import { ManufacturabilityPanel } from "@/components/ManufacturabilityPanel";
import { predictProperties, getPhaseDiagram, runInverseDesign, getHullDistance } from "@/lib/api";
import { useSession, useSignInWithGoogle } from "@/components/providers/AuthProvider";
import { useSessionPersistence } from "@/lib/hooks/useSessionPersistence";
import { SaveIndicator } from "@/components/SaveIndicator";
import { ExportReportButton } from "@/components/ExportReportButton";
import { LeilUserCluster } from "@/components/LeilHeader";
import { SessionsSidebar } from "@/components/SessionsSidebar";
import { Folder } from "lucide-react";
import { useModelHealth } from "@/lib/useModelHealth";

export default function CanvasPage() {
  const {
    session, globalAIPanelOpen, setGlobalAIPanelOpen, addComposition,
    composition, setComposition, properties, setProperties,
    targetDensityMax, setTargetDensityMax, targetMeltMin, setTargetMeltMin,
    sweepResult, sweepInProgress,
  } = useCanvasStore();
  // Supabase auth session — distinct from the LeilMat design `session`
  // above (Zustand store).  Used to attach the Bearer token on calls
  // to gated /api/design/inverse etc.
  const { session: authSession } = useSession();
  const authToken = authSession?.access_token ?? null;

  // Auto-save the design session to Supabase (Phase E).  Runs on
  // every persistable store mutation, 3-second debounce.  Bootstraps
  // by loading the last-opened session on sign-in.
  const persistence = useSessionPersistence();
  const [sessionsSidebarOpen, setSessionsSidebarOpen] = useState(false);

  const [predicting, setPredicting] = useState(false);
  const [periodicOpen, setPeriodicOpen] = useState(false);
  const [glossaryOpen, setGlossaryOpen] = useState(false);
  // Sprint 4 — temper selector state (null = use family default)
  const [temper, setTemper] = useState<string | null>(null);
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

  // Sync the Phase System "Load" text input with the composition's
  // element-set.  Without this, the AI's ``set_phase_system`` action (or
  // any other code path that swaps which elements live in the
  // composition) would update the sliders but leave the sidebar input
  // showing the stale element list, which is confusing.
  //
  // We track ``prevPhaseKeysRef`` so the effect only fires when the
  // composition's *key set* (not values) actually changes — a user
  // typing in the input shouldn't be clobbered by their own slider
  // movements, and slider-only edits shouldn't disturb the field at all.
  const prevPhaseKeysRef = useRef("");
  useEffect(() => {
    const keys = Object.keys(composition).join(",");
    if (keys === prevPhaseKeysRef.current) return;
    prevPhaseKeysRef.current = keys;
    if (keys) setPhaseElements(keys);
  }, [composition]);

  // Inverse-design Pareto candidates — restored from store
  // (simulationResults.inverse) on page reload so closing the tab
  // doesn't lose a 30-iteration BoTorch run.
  type Candidate = {
    composition: Record<string, number>;
    properties: Record<string, number | null>;
    pareto_rank: number;
    score: number;
  };
  const savedInverse = useCanvasStore((s) => s.simulationResults.inverse?.result);
  const setSimResult = useCanvasStore((s) => s.setSimulationResult);
  // Physical mean grain size (µm) from a grain sim, if one was run with a
  // domain_um. Prefer the deterministic-geometry Neper result over the
  // qualitative Potts one. Feeds the Hall-Petch overlay in Predict.
  const grainStructResult = useCanvasStore(
    (s) => s.simulationResults.grain_structure?.result) as { mean_grain_size_um?: number } | undefined;
  const grainGrowthResult = useCanvasStore(
    (s) => s.simulationResults.grain_growth?.result) as { mean_grain_size_um?: number } | undefined;
  // KWN precipitate state (volume fraction + mean radius) → Orowan overlay on YS.
  const precipResult = useCanvasStore(
    (s) => s.simulationResults.precipitation?.result) as
      { value?: { volume_fraction?: number; mean_radius_nm?: number } } | undefined;
  const [candidates, setCandidates] = useState<Candidate[]>(
    (savedInverse as Candidate[] | undefined) ?? [],
  );
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
      const grainUm =
        grainStructResult?.mean_grain_size_um ??
        grainGrowthResult?.mean_grain_size_um ?? null;
      const pv = precipResult?.value;
      const precip =
        pv && typeof pv.volume_fraction === "number" && pv.volume_fraction > 0 &&
        typeof pv.mean_radius_nm === "number" && pv.mean_radius_nm > 0
          ? { vf: pv.volume_fraction, r_nm: pv.mean_radius_nm }
          : null;
      const res = await predictProperties(composition, temper, grainUm, precip);
      setProperties(res.properties);
      addComposition({ composition, properties: res.properties, bookmarked: false, rejected: false });
      const ys = res.properties?._details?.yield_strength_MPa ?? {};
      const notes = [
        ys.hall_petch ? `grain ${ys.hall_petch.grain_size_um} µm ${ys.hall_petch.delta_MPa >= 0 ? "+" : ""}${ys.hall_petch.delta_MPa} MPa` : null,
        ys.precipitation ? `precip ${ys.precipitation.delta_MPa >= 0 ? "+" : ""}${ys.precipitation.delta_MPa} MPa` : null,
      ].filter(Boolean);
      toast.success(
        notes.length ? `Properties predicted (${notes.join(", ")})` : "Properties predicted",
      );

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
      }, authToken);
      setCandidates(result);
      setSimResult("inverse", { result });
      toast.success(`${result.length} candidates found`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Inverse design failed");
    } finally {
      setRunningInverse(false);
    }
  }

  // ── AI command bus ─────────────────────────────────────────────────
  // Global AI's agentic pills (`run_predict`, `run_optimization`) dispatch
  // a ``leilmat:ai_command`` CustomEvent on the window.  We listen here
  // and route to the existing handlers so the AI can trigger the same
  // buttons the user can click.  No-op if the canvas isn't mounted (the
  // event simply has no listener).
  useEffect(() => {
    const onAICommand = (e: Event) => {
      const detail = (e as CustomEvent<{ kind?: string }>).detail;
      if (!detail) return;
      if (detail.kind === "predict")  void handlePredict();
      if (detail.kind === "optimize") void handleInverseDesign();
    };
    window.addEventListener("leilmat:ai_command", onAICommand);
    return () => window.removeEventListener("leilmat:ai_command", onAICommand);
    // handlePredict / handleInverseDesign are defined in this same
    // component scope; they close over `composition`, `predicting`, etc.
    // Re-binding the listener every render is fine — both functions are
    // cheap to recreate and we never have more than one listener at a
    // time thanks to the cleanup return.
  });

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
      // Surface the silent renormalization so the user understands why
      // the other sliders just moved.
      if (others.length > 0) {
        toast(`Removed ${symbol} — remaining elements rescaled to 100%`);
      }
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
    if (otherSum > 0) {
      toast(`Added ${symbol} at ${defaultPct}% — other elements rescaled to fit`);
    }
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
    <>
    <MobileInterstitial />
    <div className="hidden lg:flex flex-col h-screen overflow-hidden bg-bg">

      {/* ── Topbar ── */}
      <header className="relative z-20 flex items-center justify-between px-6 h-14 border-b border-line shrink-0 bg-bg/80 backdrop-blur-xl">
        <div className="flex items-center gap-3 min-w-0">
          <LeilBrand subtitle="Materials cockpit" />

          {/* Active session name — sits beside the logo so the user
              always knows which design they're in.  Click opens the
              Sessions drawer.  Hidden until the session has a real name
              (the auto-namer / manual rename replaces the default). */}
          {session.name && session.name !== "Untitled session" && (
            <>
              <span className="hidden md:inline w-px h-4 bg-fg/[0.12] shrink-0" />
              <button
                onClick={() => setSessionsSidebarOpen(true)}
                title="Switch or rename session"
                className="hidden md:flex items-center gap-1.5 min-w-0 max-w-[280px] px-1.5 py-0.5 rounded-md hover:bg-fg/[0.05] transition-colors group"
              >
                <span className="truncate text-[13px] text-muted group-hover:text-fg transition-colors">
                  {session.name}
                </span>
              </button>
            </>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Sessions drawer toggle */}
          <button
            onClick={() => setSessionsSidebarOpen(true)}
            aria-label="Design sessions"
            disabled={!authSession}
            title={authSession ? "Open design sessions" : "Sign in to save sessions"}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-fg/[0.04] border border-line hover:bg-fg/[0.07] hover:border-fg/30 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Folder size={12} className="text-muted" />
            <span className="hidden md:inline text-[11px] text-muted font-medium">Sessions</span>
          </button>

          {/* Auto-save state */}
          <SaveIndicator
            saveState={persistence.saveState}
            lastSavedAt={persistence.lastSavedAt}
            signedIn={!!authSession}
          />

          {/* divider · Document → Status group */}
          <div className="hidden md:block w-px h-5 bg-fg/[0.08] mx-0.5" />

          <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-fg/[0.04] border border-line">
            <div className="w-1.5 h-1.5 rounded-full bg-ok animate-pulse" />
            <span className="text-[10px] text-muted font-medium">AI online</span>
          </div>

          {/* Daily LLM-budget pill — hidden when cap_usd=0 or cap_usd=null */}
          <BudgetPill />

          {/* Cloud-compute jobs (running + recent) — hidden when none */}
          <JobsIndicator />

          {/* Audit-grade PDF report export — uses warm-gold accent so it
              reads as a "deliverable" action, distinct from the cooler
              info chips and the sky-blue Global AI toggle. */}
          <ExportReportButton />

          {/* divider · Status → Actions group */}
          <div className="hidden md:block w-px h-5 bg-fg/[0.08] mx-0.5" />

          {/* Glossary — in-canvas quick reference for the jargon (CPFEM,
              KWN, Scheil, calibration labels…), with a link out to the
              full /docs explainer.  Replaces the earlier new-tab stopgap. */}
          <button
            onClick={() => setGlossaryOpen(true)}
            aria-label="Open the glossary"
            title="Glossary — CPFEM, KWN, Scheil, calibration labels…"
            className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-fg/[0.04] border border-line hover:bg-fg/[0.07] hover:border-fg/30 text-muted hover:text-fg transition-colors"
          >
            <HelpCircle size={12} />
            <span className="text-[11px] font-medium">Glossary</span>
          </button>

          <button
            onClick={() => setGlobalAIPanelOpen(!globalAIPanelOpen)}
            className={`flex items-center gap-2 text-[12px] px-3 py-1.5 rounded-md font-medium transition-all ${
              globalAIPanelOpen
                ? "bg-fg/10 text-fg border border-line shadow-lg shadow-black/30"
                : "bg-fg/[0.04] hover:bg-fg/[0.08] text-muted border border-line hover:border-fg/30"
            }`}
          >
            <Sparkles size={13} />
            Global AI
            {session.messages.length > 0 && (
              <span className="bg-fg text-bg text-[10px] rounded-full px-1.5 leading-none py-0.5 font-semibold">
                {session.messages.length}
              </span>
            )}
          </button>

          {/* Divider before the global user cluster (credit chip + avatar).
              Absorbing LeilHeader's right cluster here means /canvas only
              renders ONE banner instead of two stacked headers.
              ``LeilHeader`` itself returns null on this route — see
              ``components/LeilHeader.tsx``. */}
          <div className="hidden md:block w-px h-5 bg-fg/[0.08] mx-1" />
          <div className="flex items-center gap-3">
            <LeilUserCluster />
          </div>
        </div>
      </header>

      {/* ── Body ── */}
      <div className="relative z-10 flex flex-1 overflow-hidden">

        {/* ── Left Sidebar ── */}
        <aside className="w-[300px] shrink-0 border-r border-line flex flex-col overflow-y-auto bg-surface/60">

          <section className="p-5 border-b border-line">
            <SectionHeader icon={<Atom size={11} />} label="Composition" trailing={`${Object.keys(composition).length}`} />

            <div className="space-y-3 mt-3.5">
              {Object.entries(composition).map(([el, frac]) => (
                <div key={el} className="group flex items-center gap-2.5">
                  <span className="text-[11px] font-mono font-semibold text-fg w-6 tabular-nums">{el}</span>
                  <input
                    type="range" min={0} max={100} step={0.5} value={frac}
                    onChange={(e) => setComposition({ ...composition, [el]: parseFloat(e.target.value) })}
                    className="flex-1 cursor-pointer"
                  />
                  <span className="text-[11px] font-mono text-muted w-10 text-right tabular-nums">{frac.toFixed(1)}</span>
                  <button
                    aria-label={`Remove ${el} from composition`}
                    title={`Remove ${el}`}
                    onClick={() => {
                      const prev = { ...composition };
                      const n = { ...composition }; delete n[el]; setComposition(n);
                      toast(`Removed ${el}`, {
                        action: { label: "Undo", onClick: () => setComposition(prev) },
                      });
                    }}
                    className="text-subtle hover:text-bad transition-colors opacity-0 group-hover:opacity-100 rounded"
                  >
                    <X size={11} />
                  </button>
                </div>
              ))}
            </div>

            <button
              onClick={() => setPeriodicOpen(true)}
              className="w-full mt-4 flex items-center justify-center gap-2 py-2 bg-fg/[0.04] hover:bg-fg/[0.08] border border-line hover:border-fg/40 rounded-lg text-[12px] font-medium text-muted hover:text-fg transition-all group"
            >
              <LayoutGrid size={12} className="text-subtle group-hover:text-fg transition-colors" />
              Periodic Table
            </button>

            <div className="flex items-center justify-between mt-3 text-[10px] text-subtle font-medium uppercase tracking-wider">
              <span>Total</span>
              <span className={`tabular-nums ${totalFrac > 101 ? "text-bad" : totalFrac < 99 ? "text-warn" : "text-ok"}`}>
                {totalFrac.toFixed(1)}% · {totalFrac > 101 ? "over" : totalFrac < 99 ? "under" : "ok"}
              </span>
            </div>

            {/* Sprint 4 — temper selector */}
            <TemperSelector composition={composition} temper={temper} onChange={setTemper} />

            <button
              onClick={handlePredict}
              disabled={predicting || !Object.keys(composition).length}
              title="Predicts mechanical, physical & manufacturability properties — and unlocks the 10 process simulations (Scheil, KWN, grain structure, CPFEM, aging…)"
              className="w-full mt-3 flex items-center justify-center gap-2 py-2.5 bg-brand hover:bg-brand/90 disabled:bg-fg/[0.05] disabled:text-subtle disabled:cursor-not-allowed rounded-lg text-[13px] font-semibold text-white transition-colors"
            >
              {predicting ? <Loader2 size={14} className="animate-spin" /> : <Zap size={13} fill="currentColor" />}
              {predicting ? "Predicting…" : "Predict Properties"}
            </button>
          </section>

          <section className="p-5 border-b border-line">
            <SectionHeader icon={<FlaskConical size={11} />} label="Phase System" />
            <div className="flex gap-1.5 mt-3">
              <input
                value={phaseElements}
                onChange={(e) => setPhaseElements(e.target.value)}
                placeholder="Al,Mg,Si"
                className="flex-1 bg-fg/[0.03] border border-line rounded-md px-2.5 py-1.5 text-[11px] font-mono text-fg placeholder:text-subtle outline-none focus:border-fg/40 focus:bg-fg/[0.05] transition-all"
              />
              <button
                onClick={handleLoadPhase}
                disabled={loadingPhase}
                className="px-3 py-1.5 bg-fg/[0.04] hover:bg-fg/[0.08] border border-line rounded-md text-[11px] font-medium text-muted hover:text-fg transition-all disabled:opacity-40"
              >
                {loadingPhase ? <Loader2 size={11} className="animate-spin" /> : "Load"}
              </button>
            </div>
            <p className="text-[10px] text-subtle mt-2 leading-relaxed">
              Fetches stable phases from Materials Project
            </p>
          </section>

          <section className="p-5 border-b border-line">
            <SectionHeader icon={<Target size={11} />} label="Inverse Design" />
            <div className="space-y-2.5 mt-3.5">
              <NumberRow label="Density max" value={targetDensityMax} step={0.1} unit="g/cm³" onChange={setTargetDensityMax} />
              <NumberRow label="Melt point min" value={targetMeltMin} step={50} unit="K" onChange={setTargetMeltMin} />
            </div>
            <button
              onClick={handleInverseDesign}
              disabled={runningInverse || !Object.keys(composition).length}
              className="w-full mt-4 flex items-center justify-center gap-2 py-2.5 border border-fg/40 bg-fg/[0.04] hover:bg-fg/[0.10] disabled:border-line disabled:bg-fg/[0.05] disabled:text-subtle disabled:cursor-not-allowed rounded-lg text-[13px] font-semibold text-fg transition-colors"
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

            {/* Guest banner — signed-out visitors otherwise hit silent 401s
                on cost-bearing actions.  Soft, dismissible sign-in nudge. */}
            {!authSession && <GuestBanner />}

            {/* First-run workflow scaffold — makes the compose → Predict →
                explore dependency explicit.  Dismissible (persisted). */}
            <WorkflowBanner
              hasComposition={Object.keys(composition).length > 0}
              hasProperties={hasProperties}
            />

            {/* Persistent honesty disclaimer — every result carries a
                calibration label; this points users at what the labels
                mean (the glossary) and sets the screening-tool expectation. */}
            <p className="text-[10.5px] text-subtle leading-snug px-1">
              Screening tools — each result carries a{" "}
              <button
                onClick={() => setGlossaryOpen(true)}
                className="text-muted hover:text-fg underline underline-offset-2 decoration-line transition-colors"
              >
                calibration label
              </button>{" "}
              showing how far to trust its absolute numbers. Validate against experiment before production.
            </p>

            <Panel
              title="Properties"
              subtitle="Predicted from composition — click any property for AI insights"
              badge={hasProperties ? "Live" : undefined}
              empty={!hasProperties}
              emptyTitle="No prediction yet"
              emptyText="Run Predict Properties in the sidebar to see the radar chart"
              emptyIcon={<Zap size={18} className="text-subtle" />}
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
                <div className="min-h-44">
                  <ManufacturabilityPanel
                    composition={composition}
                    data={(properties as Record<string, unknown>).manufacturability as Parameters<typeof ManufacturabilityPanel>[0]["data"]}
                  />
                </div>
              </Panel>
            )}

            {/* ── Process simulation — CALPHAD, solidification, TTT,
                  microstructure, precipitation kinetics.  Each card has
                  its own composition-driven empty state and "run" button.
                  Always rendered: before the first prediction we show the
                  modules as LOCKED placeholders so the depth of the tool
                  is visible, rather than hiding everything behind the
                  Predict gate (the audit's #1 finding). */}
            <Panel
              title="Process Simulation"
              subtitle="CALPHAD equilibrium · Scheil · TTT · microstructure · KWN precipitation · Fick diffusion · grain structure · grain growth · CPFEM stress–strain · aging optimizer"
              badge={hasProperties ? "10 modules" : "🔒 Predict to unlock"}
              empty={false}
              emptyTitle=""
              emptyText=""
              emptyIcon={null}
            >
              {hasProperties ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <PhaseAssemblageCard composition={composition} />
                  <SolidificationCard  composition={composition} />
                  <TTTCard             composition={composition} />
                  <MicrostructureCard  composition={composition} />
                  <PrecipitationCard   composition={composition} />
                  <DiffusionCard />
                  <GrainStructureCard  composition={composition} />
                  <GrainGrowthCard     composition={composition} />
                  <CPFEMStressStrainCard composition={composition} />
                  <AgingOptimizerCard  composition={composition} />
                </div>
              ) : (
                <LockedSimulationGrid />
              )}
            </Panel>

            {/* Ternary Composition Explorer */}
            <Panel
              title="Ternary Composition Explorer"
              subtitle={canRenderTernary
                ? `Heatmap across ${ternaryElements.join("–")} simplex — click any point to design from there`
                : "Add at least 3 elements to enable simplex sampling"}
              empty={!canRenderTernary}
              emptyTitle="Need 3+ elements"
              emptyText="The ternary explorer needs at least 3 elements in the composition"
              emptyIcon={<Atom size={18} className="text-subtle" />}
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
                emptyIcon={<Loader2 size={18} className="text-subtle animate-spin" />}
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
              emptyIcon={<FlaskConical size={18} className="text-subtle" />}
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
              emptyIcon={<Target size={18} className="text-subtle" />}
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

      <GlossaryModal open={glossaryOpen} onClose={() => setGlossaryOpen(false)} />

      <SessionsSidebar
        open={sessionsSidebarOpen}
        onClose={() => setSessionsSidebarOpen(false)}
        persistence={persistence}
      />
    </div>
    </>
  );
}

// ── Sprint 4: temper selector ─────────────────────────────────────────────
function detectAlloyFamily(composition: Record<string, number>): string | null {
  const total = Object.values(composition).reduce((a, b) => a + b, 0);
  if (total <= 0) return null;
  const fracs = Object.fromEntries(
    Object.entries(composition).map(([el, v]) => [el, v / total])
  );
  if ((fracs.Fe ?? 0) >= 0.5) return "general_steel";
  if ((fracs.Al ?? 0) >= 0.8) return "aluminum";
  if ((fracs.Ti ?? 0) >= 0.5) return "titanium";
  if ((fracs.Ni ?? 0) >= 0.4) return "nickel";
  return null;
}

const TEMPER_OPTIONS: Record<string, string[]> = {
  aluminum: ["O", "F", "T3", "T351", "T4", "T5", "T6", "T651", "T7", "T73",
             "T7351", "T7451", "T7651", "T7751", "T8", "T81", "T84", "T851",
             "T87", "T6511", "T8E74", "T8771",
             "H12", "H14", "H18", "H19", "H22", "H32", "H38", "H111", "H116", "H321"],
  titanium: ["Annealed", "Mill-annealed", "Duplex anneal", "β-anneal", "STA", "HIP+Aged"],
  nickel: ["Annealed", "Solution", "Aged", "SX-Aged"],
  general_steel: ["Annealed", "Hot-rolled", "As-rolled", "Normalised", "TMCP",
                  "Cold-drawn", "Cold-rolled",
                  "Q&T", "Q&T 300", "Q&T 400", "Q&T 425", "Q&T 450", "Q&T 650",
                  "Carburised", "Carburised + Q&T",
                  "H900", "H950", "H1000", "H1025", "H1050", "H1150",
                  "Weathering", "HSLA"],
};

const TEMPER_DEFAULTS: Record<string, string> = {
  aluminum: "T6",
  titanium: "STA",
  nickel: "Aged",
  general_steel: "Annealed",
};

function TemperSelector({
  composition, temper, onChange,
}: {
  composition: Record<string, number>;
  temper: string | null;
  onChange: (t: string | null) => void;
}) {
  const family = detectAlloyFamily(composition);
  if (!family) {
    return null;   // no alloy family detected → no temper choice meaningful
  }
  const options = TEMPER_OPTIONS[family] ?? [];
  const defaultTemper = TEMPER_DEFAULTS[family] ?? "—";
  return (
    <div className="mt-3 rounded-lg border border-line bg-fg/[0.02] px-3 py-2">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[9.5px] font-semibold uppercase tracking-wider text-subtle">
          Temper / Heat-treat
        </span>
        <span className="text-[8.5px] px-1.5 py-0.5 rounded bg-fg/10 text-fg border border-line font-mono font-semibold uppercase">
          {family.replace("_", " ")}
        </span>
      </div>
      <select
        value={temper ?? ""}
        onChange={(e) => onChange(e.target.value || null)}
        className="w-full bg-fg/[0.04] border border-line rounded px-2 py-1.5 text-[11px] text-fg outline-none focus:border-fg/40 focus:bg-fg/[0.06] transition-all"
      >
        <option value="">Default for {family} ({defaultTemper})</option>
        {options.map((t) => (
          <option key={t} value={t}>{t}</option>
        ))}
      </select>
      <p className="text-[8.5px] text-subtle mt-1 leading-snug">
        Same composition, different tempers can give 3–5× different yield strength
        (6061-O = 55 MPa, 6061-T6 = 276 MPa).
      </p>
    </div>
  );
}


function SectionHeader({ icon, label, trailing }: { icon: React.ReactNode; label: string; trailing?: string }) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-1.5 text-subtle">
        {icon}
        <span className="text-[10px] font-semibold uppercase tracking-[0.12em]">{label}</span>
      </div>
      {trailing && (
        <span className="text-[10px] font-mono text-subtle bg-fg/[0.03] px-1.5 py-0.5 rounded">{trailing}</span>
      )}
    </div>
  );
}

function NumberRow({ label, value, step, unit, onChange }: { label: string; value: number; step: number; unit: string; onChange: (v: number) => void }) {
  return (
    <label className="flex items-center gap-2">
      <span className="text-[11px] text-subtle flex-1">{label}</span>
      <input
        type="number" step={step} value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-20 bg-fg/[0.03] border border-line rounded-md px-2 py-1 text-[11px] font-mono text-fg outline-none focus:border-fg/40 focus:bg-fg/[0.05] transition-all text-right tabular-nums"
      />
      <span className="text-[10px] text-subtle w-10 font-medium">{unit}</span>
    </label>
  );
}

function StatRow({ label, value, accent }: { label: string; value: number; accent?: "sky" | "amber" | "emerald" }) {
  const accentClass = accent === "sky" ? "text-fg"
    : accent === "amber" ? "text-warn"
    : accent === "emerald" ? "text-ok"
    : "text-muted";
  return (
    <div className="flex items-center justify-between text-[11px]">
      <span className="text-subtle">{label}</span>
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
      <div className="flex items-center justify-between px-6 py-4 border-b border-line">
        <div>
          <h2 className="text-[15px] font-semibold text-fg tracking-tight">{title}</h2>
          {subtitle && <p className="text-[11px] text-subtle mt-0.5">{subtitle}</p>}
        </div>
        {badge && (
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-fg/10 text-fg border border-line font-semibold uppercase tracking-wider">
            {badge}
          </span>
        )}
      </div>
      {empty ? (
        <div className="flex flex-col items-center justify-center py-14 px-6 text-center">
          <div className="w-10 h-10 rounded-full bg-fg/[0.03] border border-line flex items-center justify-center mb-3">
            {emptyIcon}
          </div>
          <p className="text-[13px] font-medium text-muted">{emptyTitle}</p>
          <p className="text-[11px] text-subtle mt-1 max-w-xs">{emptyText}</p>
        </div>
      ) : (
        <div className="p-6">{children}</div>
      )}
    </div>
  );
}


// ── Guest sign-in banner (Tier C onboarding) ──────────────────────────────
// Signed-out visitors can browse the canvas but hit 401s on cost-bearing
// actions (inverse design, cloud sims) with no explanation.  This soft,
// dismissible strip sets the expectation and offers one-click sign-in.
function GuestBanner() {
  return authConfigured() ? <GuestBannerInner /> : null;     // no accounts on this build: nothing to sign in to
}

function GuestBannerInner() {
  const signIn = useSignInWithGoogle();
  const [busy, setBusy] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  useEffect(() => {
    try {
      if (localStorage.getItem("leilmat:guest-banner") === "dismissed") setDismissed(true);
    } catch { /* localStorage unavailable — show it */ }
  }, []);

  if (dismissed) return null;

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-fg/[0.03] px-4 py-2.5">
      <p className="text-[11.5px] text-muted leading-snug">
        <span className="text-fg font-medium">Exploring as a guest.</span>{" "}
        Sign in to save sessions, run cloud simulations, and keep your credit balance.
      </p>
      <div className="flex items-center gap-2 shrink-0">
        <button
          onClick={async () => { setBusy(true); try { await signIn(); } finally { setBusy(false); } }}
          disabled={busy}
          className="inline-flex items-center gap-1.5 px-3 py-1 rounded-md bg-fg/10 text-fg border border-line hover:bg-fg/15 text-[11px] font-semibold transition-colors disabled:opacity-50"
        >
          {busy && <Loader2 size={12} className="animate-spin" />}
          Sign in with Google
        </button>
        <button
          onClick={() => {
            setDismissed(true);
            try { localStorage.setItem("leilmat:guest-banner", "dismissed"); } catch { /* noop */ }
          }}
          aria-label="Dismiss the guest banner"
          title="Dismiss"
          className="p-1 rounded text-subtle hover:text-muted hover:bg-fg/[0.05] transition-colors"
        >
          <X size={12} />
        </button>
      </div>
    </div>
  );
}


// ── Mobile interstitial (Tier C) ──────────────────────────────────────────
// The canvas is deliberately desktop-only (hard 300px sidebar, fixed-px
// charts, `hidden md:` topbar).  Below `lg` we replace it with a clean
// "open on desktop" screen rather than dropping users onto a broken,
// cramped layout.  Rendered as a sibling that is `lg:hidden`, while the
// canvas itself is `hidden lg:flex`.
function MobileInterstitial() {
  return (
    <div className="lg:hidden fixed inset-0 z-50 flex flex-col items-center justify-center gap-6 px-8 text-center bg-bg">
      <Bloom decorative size={64} className="relative" />
      <div className="relative space-y-2.5 max-w-sm">
        <h1 className="headline text-[34px] text-fg">
          Leil-Mat is built for desktop<span className="text-brand">.</span>
        </h1>
        <p className="text-[13px] text-muted leading-relaxed">
          The design canvas — composition sliders, simulation cards, phase
          diagrams and the AI copilot — needs a wider screen. Open this page on a laptop or desktop to start designing.
        </p>
      </div>
      <div className="relative flex items-center gap-2.5">
        <a
          href="/docs"
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-fg/10 text-fg border border-line hover:bg-fg/15 text-[12px] font-semibold transition-colors"
        >
          What LeilMat does
          <span aria-hidden>→</span>
        </a>
        <a
          href="/"
          className="inline-flex items-center px-4 py-2 rounded-lg bg-fg/[0.04] text-muted border border-line hover:bg-fg/[0.08] hover:text-fg text-[12px] font-medium transition-colors"
        >
          Home
        </a>
      </div>
    </div>
  );
}


// ── First-run workflow scaffold (B1) ──────────────────────────────────────
// The audit's #1 finding: the compose → Predict → explore dependency is
// invisible to anyone but the author.  These two pieces make it explicit —
// a progress-aware banner and locked placeholders for the gated sims.

const SIM_MODULES: { name: string; desc: string }[] = [
  { name: "Phase Assemblage", desc: "CALPHAD equilibrium" },
  { name: "Solidification", desc: "Scheil freezing path" },
  { name: "TTT Diagram", desc: "transformation kinetics" },
  { name: "Microstructure", desc: "equilibrium phase map" },
  { name: "Precipitation", desc: "KWN kinetics" },
  { name: "Diffusion", desc: "Fick concentration profiles" },
  { name: "Grain Structure", desc: "Neper tessellation · cloud" },
  { name: "Grain Growth", desc: "Potts Monte-Carlo · cloud" },
  { name: "Stress–Strain", desc: "CPFEM crystal plasticity · cloud" },
  { name: "Aging Optimizer", desc: "peak-age heat-treat schedule" },
];

function LockedSimulationGrid() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      {SIM_MODULES.map((m) => (
        <div
          key={m.name}
          className="flex items-center gap-2.5 rounded-lg border border-line bg-fg/[0.015] px-3.5 py-3"
        >
          <div className="w-6 h-6 rounded-md bg-fg/[0.03] border border-line flex items-center justify-center shrink-0">
            <Lock size={11} className="text-subtle" />
          </div>
          <div className="min-w-0">
            <div className="text-[12px] font-medium text-muted truncate">{m.name}</div>
            <div className="text-[10px] text-subtle truncate">{m.desc}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * Dismissible "Getting started" stepper.  Reflects live progress
 * (composition set → properties predicted → exploring) and persists its
 * dismissal in localStorage so returning users don't see it again.
 */
function WorkflowBanner({
  hasComposition, hasProperties,
}: {
  hasComposition: boolean;
  hasProperties: boolean;
}) {
  const [dismissed, setDismissed] = useState(false);
  useEffect(() => {
    try {
      if (localStorage.getItem("leilmat:workflow-banner") === "dismissed") {
        setDismissed(true);
      }
    } catch {
      /* localStorage unavailable (private mode / SSR) — just show it */
    }
  }, []);

  if (dismissed) return null;

  const dismiss = () => {
    setDismissed(true);
    try { localStorage.setItem("leilmat:workflow-banner", "dismissed"); } catch { /* noop */ }
  };

  const steps = [
    { label: "Set composition", hint: "Add elements & ratios in the sidebar", done: hasComposition },
    { label: "Predict properties", hint: "Unlocks the 10 process simulations", done: hasProperties },
    { label: "Explore & optimize", hint: "Run sims, sweep & inverse-design", done: false },
  ];
  // The active step is the first one not yet complete.
  const activeIdx = steps.findIndex((s) => !s.done);

  return (
    <div className="panel relative px-5 py-4">
      <button
        onClick={dismiss}
        aria-label="Dismiss the getting-started guide"
        title="Dismiss"
        className="absolute top-2.5 right-2.5 p-1 rounded text-subtle hover:text-muted hover:bg-fg/[0.05] transition-colors"
      >
        <X size={12} />
      </button>

      <div className="flex items-center gap-1.5 mb-3 text-fg">
        <Sparkles size={12} />
        <span className="text-[10px] font-semibold uppercase tracking-[0.12em]">Getting started</span>
      </div>

      <div className="flex flex-col sm:flex-row sm:items-stretch gap-3 sm:gap-0">
        {steps.map((s, i) => {
          const isActive = i === activeIdx;
          return (
            <div key={s.label} className="flex items-start gap-3 flex-1 sm:pr-4">
              <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-semibold shrink-0 border ${
                s.done
                  ? "bg-ok/15 text-ok border-ok/40"
                  : isActive
                  ? "bg-fg text-bg border-fg"
                  : "bg-fg/[0.03] text-subtle border-line"
              }`}>
                {s.done ? <Check size={12} /> : i + 1}
              </div>
              <div className="min-w-0 pt-0.5">
                <div className={`text-[12px] font-medium ${isActive ? "text-fg" : s.done ? "text-muted" : "text-muted"}`}>
                  {s.label}
                </div>
                <div className="text-[10px] text-subtle leading-snug mt-0.5">{s.hint}</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}


/**
 * Daily LLM-budget visibility pill.
 *
 * Polls /api/health/budget every 30 s and renders a small status chip
 * showing today's USD spend against the cap.  Colour-coded:
 *   * < 60% used  → emerald  (everything fine)
 *   * 60-90% used → amber    (heads up)
 *   * ≥ 90% used  → rose     (live AI insights about to fall back to the
 *                              deterministic numeric path)
 *
 * Hidden entirely when cap_usd ≤ 0 (the operator disabled the budget cap
 * via the LLM_DAILY_BUDGET_USD env var).
 */
interface BudgetStatus {
  date_utc:        string;
  cap_usd:         number;
  spent_usd:       number;
  remaining_usd:   number | null;
  total_calls:     number;
  over_budget:     boolean;
  per_endpoint:    Record<string, { calls: number; cost: number }>;
}

function BudgetPill() {
  const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const [status, setStatus] = useState<BudgetStatus | null>(null);

  useEffect(() => {
    let active = true;
    const fetchStatus = async () => {
      try {
        const r = await fetch(`${BASE}/api/health/budget`, { cache: "no-store" });
        if (!r.ok) throw new Error(`${r.status}`);
        const data = (await r.json()) as BudgetStatus;
        if (active) setStatus(data);
      } catch {
        if (active) setStatus(null);
      }
    };
    fetchStatus();
    const t = window.setInterval(fetchStatus, 30_000);
    return () => { active = false; window.clearInterval(t); };
  }, [BASE]);

  // Don't render at all if the backend is unreachable or the cap is disabled
  if (!status || status.cap_usd <= 0) return null;

  const pct = status.cap_usd > 0 ? status.spent_usd / status.cap_usd : 0;
  // 3 colour bands
  const palette =
    status.over_budget || pct >= 0.90
      ? { bg: "bg-bad/15",    text: "text-bad",    border: "border-bad/30",    dot: "bg-bad"    }
      : pct >= 0.60
      ? { bg: "bg-warn/15",   text: "text-warn",   border: "border-warn/30",   dot: "bg-warn"   }
      : { bg: "bg-ok/10", text: "text-ok", border: "border-ok/25", dot: "bg-ok" };

  const perEndpointSummary = Object.entries(status.per_endpoint)
    .sort((a, b) => b[1].cost - a[1].cost)
    .slice(0, 5)
    .map(([ep, v]) => `${ep}: ${v.calls} calls · $${v.cost.toFixed(4)}`)
    .join("\n");

  const tooltip = [
    `Daily LLM budget (UTC ${status.date_utc})`,
    `Spent $${status.spent_usd.toFixed(4)} / $${status.cap_usd.toFixed(2)}`,
    `Calls today: ${status.total_calls}`,
    status.over_budget ? "⚠ Over budget — falling back to deterministic interpretations" : "",
    perEndpointSummary ? "" : "",
    perEndpointSummary,
  ].filter(Boolean).join("\n");

  return (
    <div
      className={`hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-md border ${palette.bg} ${palette.border}`}
      title={tooltip}
    >
      <div className={`w-1.5 h-1.5 rounded-full ${palette.dot}`} />
      <span className={`text-[11px] font-medium font-mono ${palette.text}`}>
        ${status.spent_usd.toFixed(2)} / ${status.cap_usd.toFixed(0)}
      </span>
      {status.over_budget && (
        <span className="text-[9.5px] uppercase tracking-wider text-bad/80">
          quota
        </span>
      )}
    </div>
  );
}
