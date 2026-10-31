"use client";

/**
 * DiffusionCard — Mini-sim #2: 1-D Fick's-2nd-law diffusion couple.
 *
 * Sibling to PrecipitationCard / SolidificationCard etc. — fits in the
 * Process Simulation grid.  The user picks a canonical solute-matrix
 * pair (e.g. "Mg in Al"), a homogenisation temperature, the couple
 * length, and total time.  The backend's Crank-Nicolson solver returns
 * a full ``c(x, t)`` trajectory which this card animates as a sliding
 * diffusion front with a √(Dt) marker.
 *
 * Pedagogy
 * ────────
 *   * The curve flattens visibly as t grows — homogenisation in action.
 *   * The √(Dt) vertical marker on the chart shows the characteristic
 *     diffusion length growing with √t (Boltzmann-Matano scaling).
 *   * Ghost-curves of earlier snapshots fade behind the current one,
 *     so the user can see how the front sharpens, broadens, and
 *     finally vanishes.
 *
 * Implementation reuses the KWNPlayback patterns (range scrubber,
 * play/pause, speed selector, smart time formatter) but the chart
 * itself is different — KWN was three index-vs-value sparklines, this
 * is a single c(x) profile that morphs through time.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { Pause, Play, RotateCcw, Loader2 } from "lucide-react";

import { useAuthFetch } from "@/lib/api/client";


interface DiffusionSystem {
  key:   string;
  label: string;
  ref:   string;
}

interface DiffusionResult {
  value?: {
    D_m2_s:                    number;
    T_C:                       number;
    total_time_s:              number;
    L_um:                      number;
    diffusion_length_final_um: number;
  };
  system?:  string;
  label?:   string;
  source:   string;
  error?:   string;
  trajectory?: {
    x_um:        number[];
    times_s:     number[];
    c_profiles:  number[][];
    sqrt_Dt_um:  number[];
  };
  inputs?:  {
    c_left:   number;
    c_right:  number;
    ref:      string;
  };
  warnings?: string[];
}


const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const PLAYBACK_TICK_MS = 80;


export function DiffusionCard() {
  const authFetch = useAuthFetch();

  // ─── Catalogue of solute-matrix systems ───────────────────────────
  const [systems, setSystems] = useState<DiffusionSystem[]>([]);
  const [system,  setSystem]  = useState<string>("Mg_in_Al");
  const [T_C,     setTC]      = useState<number>(450);
  const [L_um,    setL_um]    = useState<number>(200);
  const [hours,   setHours]   = useState<number>(4);
  const [cLeft,   setCLeft]   = useState<number>(5.0);
  const [cRight,  setCRight]  = useState<number>(0.0);

  const [loading, setLoading] = useState(false);
  const [result,  setResult]  = useState<DiffusionResult | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${BASE}/api/diffusion/systems`, { cache: "force-cache" });
        if (!r.ok) return;
        const data = await r.json();
        setSystems(data.systems ?? []);
      } catch { /* silent — keep the default 'Mg_in_Al' */ }
    })();
  }, []);

  const runSim = async () => {
    setLoading(true);
    try {
      const res = await authFetch("/api/diffusion/simulate", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({
          system,
          T_C,
          L_um,
          c_left:       cLeft,
          c_right:      cRight,
          total_time_s: hours * 3600,
        }),
      });
      const data: DiffusionResult = await res.json();
      setResult(data);
    } catch (e) {
      setResult({ error: e instanceof Error ? e.message : "Failed", source: "fick_1d_crank_nicolson" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-lg border border-line overflow-hidden">
      <div className="flex items-center justify-between px-3 py-1.5 bg-fg/[0.04] border-b border-line">
        <span className="text-[9.5px] font-semibold uppercase tracking-wider text-muted">
          Diffusion (1D Fick)
        </span>
        <span className="text-[8.5px] px-1.5 py-0.5 rounded border font-mono font-semibold uppercase tracking-wider bg-fg/10 text-fg border-line">
          FICK
        </span>
      </div>

      {/* Inputs */}
      <div className="px-3 py-2 border-b border-line space-y-1.5">
        <select
          value={system}
          onChange={(e) => setSystem(e.target.value)}
          className="w-full bg-fg/[0.04] border border-line rounded px-2 py-1 text-[10px] text-fg outline-none focus:border-fg/40"
        >
          {systems.length === 0 && <option value="Mg_in_Al">Mg in Al (FCC)</option>}
          {systems.map((s) => (
            <option key={s.key} value={s.key}>{s.label}</option>
          ))}
        </select>
        <div className="grid grid-cols-2 gap-1.5">
          <LabeledInput label="T (°C)"    value={T_C}    onChange={setTC}    min={20} max={1500} step={10} />
          <LabeledInput label="t (h)"     value={hours}  onChange={setHours} min={0.01} max={500} step={0.5} />
          <LabeledInput label="L (μm)"    value={L_um}   onChange={setL_um}  min={10}  max={2000} step={10} />
          <LabeledInput label="c_L | c_R" value={cLeft}  onChange={setCLeft} min={0} max={100} step={0.5}
                        rightValue={cRight} onChangeRight={setCRight} />
        </div>
        <button
          onClick={runSim}
          disabled={loading}
          className="w-full text-[9px] py-1 rounded bg-fg/10 text-fg border border-line hover:bg-fg/15 transition-colors font-semibold uppercase tracking-wider disabled:opacity-50"
        >
          {loading ? "Simulating…" : "Run diffusion couple"}
        </button>
      </div>

      {/* Result */}
      {result && (
        <div className="px-3 py-2">
          {result.error || !result.value ? (
            <p className="text-[9px] text-subtle font-mono leading-snug">
              {result.error ?? "No result."}
            </p>
          ) : (
            <>
              <div className="grid grid-cols-3 gap-2 mb-1.5">
                <Spot label="D"            value={result.value.D_m2_s.toExponential(2)} unit="m²/s" />
                <Spot label="Diff. length" value={result.value.diffusion_length_final_um.toFixed(1)} unit="μm" />
                <Spot label="System"       value={(result.label ?? result.system ?? "—").split(" (")[0]} unit="" />
              </div>
              {result.warnings && result.warnings.length > 0 && (
                <p className="text-[8.5px] text-warn/80 leading-snug mb-1">
                  {result.warnings[0]}
                </p>
              )}
              {result.trajectory && (
                <DiffusionPlayback trajectory={result.trajectory} cLeft={cLeft} cRight={cRight} />
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}


// ─────────────────────────────────────────────────────────────────────
// Inputs + spot-readout helpers
// ─────────────────────────────────────────────────────────────────────

interface LabeledInputProps {
  label:           string;
  value:           number;
  onChange:        (v: number) => void;
  min:             number;
  max:             number;
  step:            number;
  // For the c_L | c_R compact 2-in-1 input.
  rightValue?:     number;
  onChangeRight?:  (v: number) => void;
}

function LabeledInput({ label, value, onChange, min, max, step, rightValue, onChangeRight }: LabeledInputProps) {
  return (
    <div className="flex items-center gap-1">
      <span className="text-[8.5px] text-subtle w-12 shrink-0 truncate">{label}</span>
      <input
        type="number" min={min} max={max} step={step}
        value={value} onChange={(e) => onChange(Number(e.target.value))}
        className="flex-1 min-w-0 bg-fg/[0.04] border border-line rounded px-1.5 py-0.5 text-[10px] font-mono text-fg outline-none focus:border-fg/40"
      />
      {rightValue !== undefined && onChangeRight && (
        <input
          type="number" min={min} max={max} step={step}
          value={rightValue} onChange={(e) => onChangeRight(Number(e.target.value))}
          className="flex-1 min-w-0 bg-fg/[0.04] border border-line rounded px-1.5 py-0.5 text-[10px] font-mono text-muted outline-none focus:border-fg/40"
        />
      )}
    </div>
  );
}


function Spot({ label, value, unit }: { label: string; value: string; unit: string }) {
  return (
    <div>
      <p className="text-[8px] text-subtle uppercase">{label}</p>
      <p className="text-[10.5px] font-mono text-fg leading-tight truncate">
        {value} <span className="text-subtle text-[8.5px]">{unit}</span>
      </p>
    </div>
  );
}


// ─────────────────────────────────────────────────────────────────────
// Playback chart — c(x) profile that morphs through time
// ─────────────────────────────────────────────────────────────────────

interface PlaybackProps {
  trajectory: {
    x_um:        number[];
    times_s:     number[];
    c_profiles:  number[][];
    sqrt_Dt_um:  number[];
  };
  cLeft:  number;
  cRight: number;
}

function DiffusionPlayback({ trajectory, cLeft, cRight }: PlaybackProps) {
  const N = trajectory.times_s.length;
  if (N < 2) return null;

  const [idx, setIdx]         = useState<number>(N - 1);
  const [playing, setPlaying] = useState<boolean>(false);
  const [speed, setSpeed]     = useState<1 | 2 | 5>(1);
  const playRef               = useRef<number | null>(null);

  useEffect(() => {
    if (!playing) {
      if (playRef.current !== null) window.clearInterval(playRef.current);
      playRef.current = null;
      return;
    }
    playRef.current = window.setInterval(() => {
      setIdx((i) => {
        const next = i + speed;
        if (next >= N - 1) { setPlaying(false); return N - 1; }
        return next;
      });
    }, PLAYBACK_TICK_MS);
    return () => {
      if (playRef.current !== null) window.clearInterval(playRef.current);
      playRef.current = null;
    };
  }, [playing, speed, N]);

  const tNow      = trajectory.times_s[idx];
  const cProfile  = trajectory.c_profiles[idx];
  const sqrtDtNow = trajectory.sqrt_Dt_um[idx];

  return (
    <div className="mt-2 pt-2 border-t border-line space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-[8.5px] font-semibold uppercase tracking-[0.12em] text-subtle">
          Homogenisation playback
        </span>
        <span className="text-[8.5px] font-mono text-muted">
          t = {formatTime(tNow)} · √(Dt) ≈ {sqrtDtNow.toFixed(1)} μm
        </span>
      </div>

      <ProfileChart
        xValues={trajectory.x_um}
        cValues={cProfile}
        ghosts={trajectory.c_profiles.filter((_, i) => i < idx && i % 4 === 0)}
        cLeft={cLeft}
        cRight={cRight}
        sqrtDt={sqrtDtNow}
      />

      <div className="flex items-center gap-2 pt-0.5">
        <button
          type="button"
          onClick={() => {
            if (idx >= N - 1) setIdx(0);
            setPlaying((p) => !p);
          }}
          aria-label={playing ? "Pause" : "Play"}
          className="shrink-0 w-5 h-5 grid place-items-center rounded bg-fg/10 border border-line hover:bg-fg/15 text-fg transition-colors"
        >
          {playing
            ? <Pause size={9} />
            : (idx >= N - 1 ? <RotateCcw size={9} /> : <Play size={9} />)}
        </button>

        <input
          type="range"
          min={0} max={N - 1} step={1}
          value={idx}
          onChange={(e) => {
            setIdx(Number(e.target.value));
            if (playing) setPlaying(false);
          }}
          className="flex-1 accent-ok"
          aria-label="Time scrubber"
        />

        <div className="shrink-0 flex items-center gap-0.5 text-[8.5px] font-mono">
          {([1, 2, 5] as const).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setSpeed(s)}
              className={`px-1 py-0.5 rounded transition-colors ${
                speed === s
                  ? "bg-fg/20 text-fg"
                  : "text-subtle hover:text-muted"
              }`}
            >
              {s}×
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}


// ─── The actual profile chart ─────────────────────────────────────────

interface ProfileChartProps {
  xValues: number[];
  cValues: number[];
  ghosts:  number[][];   // earlier snapshots, rendered at low opacity
  cLeft:   number;
  cRight:  number;
  sqrtDt:  number;
}

function ProfileChart({ xValues, cValues, ghosts, cLeft, cRight, sqrtDt }: ProfileChartProps) {
  const W = 260, H = 80, PAD_X = 4, PAD_Y = 4;

  const xMin = xValues[0];
  const xMax = xValues[xValues.length - 1];
  const xSpan = xMax - xMin || 1;
  // Concentration domain: fix to [min(c_L, c_R), max(c_L, c_R)] so the
  // y-axis doesn't bounce as the profile flattens.
  const yMin = Math.min(cLeft, cRight);
  const yMax = Math.max(cLeft, cRight);
  const ySpan = yMax - yMin || 1;

  const toPath = (cs: number[]): string => {
    const pts: string[] = [];
    for (let i = 0; i < cs.length; i++) {
      const x = PAD_X + ((xValues[i] - xMin) / xSpan) * (W - 2 * PAD_X);
      const y = H - PAD_Y - ((cs[i] - yMin) / ySpan) * (H - 2 * PAD_Y);
      pts.push(`${i === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`);
    }
    return pts.join(" ");
  };

  const currentPath = useMemo(() => toPath(cValues), [cValues]);
  const ghostPaths  = useMemo(() => ghosts.map(toPath), [ghosts]);

  // √(Dt) marker — measured from the centre of the bar in both directions
  // for a step-IC diffusion couple.  Show it as a horizontal arrow at
  // the y = (c_L + c_R)/2 level since that's where the diffusion front
  // sits in the symmetric case.
  const xMid    = (xMin + xMax) / 2;
  const xMidPx  = PAD_X + ((xMid - xMin) / xSpan) * (W - 2 * PAD_X);
  const halfPx  = (sqrtDt / xSpan) * (W - 2 * PAD_X);
  const yMidPx  = H - PAD_Y - 0.5 * (H - 2 * PAD_Y);

  return (
    <div className="space-y-0.5">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        className="w-full h-20"
        role="img"
        aria-label={`Concentration profile c(x) at the current time`}
      >
        {/* Ghost curves of earlier snapshots */}
        {ghostPaths.map((d, i) => (
          <path
            key={i} d={d} fill="none"
            stroke="rgb(var(--c-fg))"
            strokeOpacity={0.08 + 0.12 * (i / Math.max(1, ghostPaths.length - 1))}
            strokeWidth={0.7}
          />
        ))}

        {/* √(Dt) marker — translucent band around the midpoint */}
        <rect
          x={xMidPx - halfPx} width={Math.min(W - 2 * PAD_X, 2 * halfPx)}
          y={PAD_Y} height={H - 2 * PAD_Y}
          fill="rgb(var(--c-fg))" fillOpacity={0.06}
        />
        {/* √(Dt) endpoints — tiny ticks */}
        {[xMidPx - halfPx, xMidPx + halfPx].map((px, i) => (
          (px >= PAD_X && px <= W - PAD_X) && (
            <line
              key={i}
              x1={px} x2={px}
              y1={yMidPx - 3} y2={yMidPx + 3}
              stroke="rgb(var(--c-fg))" strokeOpacity={0.55} strokeWidth={0.8}
            />
          )
        ))}

        {/* Current concentration profile */}
        <path
          d={currentPath} fill="none"
          stroke="rgb(var(--c-fg))"         
          strokeWidth={1.4}
          strokeLinejoin="round"
          strokeLinecap="round"
        />
      </svg>

      <div className="flex items-center justify-between text-[8px] font-mono text-subtle px-0.5">
        <span>x = 0 μm</span>
        <span className="text-subtle">c (wt %)</span>
        <span>x = {xValues[xValues.length - 1].toFixed(0)} μm</span>
      </div>
    </div>
  );
}


function formatTime(s: number): string {
  if (s < 60)    return `${s.toFixed(1)} s`;
  if (s < 3600)  return `${(s / 60).toFixed(1)} min`;
  if (s < 86400) return `${(s / 3600).toFixed(2)} h`;
  return `${(s / 86400).toFixed(2)} d`;
}
