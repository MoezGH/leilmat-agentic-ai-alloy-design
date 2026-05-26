"use client";

/**
 * KWNPlayback — interactive scrubber over the KWN trajectory.
 *
 * The backend's ``/api/precipitation/simulate`` already returns a
 * time-resolved trajectory:
 *
 *   trajectory = {
 *     times_s:   [t0, t1, …, t_N],            log-spaced 0 → aging_time_s
 *     vf:        [vf0, vf1, …, vf_N],         volume fraction
 *     r_bar_nm:  [r0, r1, …, r_N],            mean radius (nm)
 *     X_alpha:   [X0, X1, …, X_N],            matrix solute frac.
 *   }
 *
 * Today only the final values render in the card.  This component
 * scrubs through the whole curve so the user can watch nucleation →
 * growth → Ostwald-ripening unfold and build intuition for "why aging
 * curves look like aging curves."
 *
 * Visual layout — three stacked mini-curves with a shared vertical
 * marker that tracks the scrubber position:
 *
 *   ┌───────────────────────────────────────┐
 *   │ Volume fraction          ●  0.0123    │   ← current-time marker
 *   │ ──────────────────╱─────────────────  │
 *   │ Mean radius              ●  12.3 nm   │
 *   │ ─────────────╱──────────────────────  │
 *   │ Matrix solute            ●  0.42 %    │
 *   │ ──────╲─────────────────────────────  │
 *   │ [├──────●─────────────]               │   ← scrubber
 *   │ ▶ 1×   t = 2.3 h                      │
 *   └───────────────────────────────────────┘
 *
 * Implementation: pure SVG mini-charts.  Plotly is loaded elsewhere on
 * the page but at ~1.5 MB it's overkill for three 180×56 inline plots.
 * Hand-rolled SVG keeps the playback responsive and reactive — no
 * canvas redraws, no chart-library re-mounts on each scrub tick.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { Pause, Play, RotateCcw } from "lucide-react";


export interface KWNTrajectory {
  times_s:   number[];
  vf:        number[];
  r_bar_nm:  number[];
  X_alpha:   number[];
}


// Scrubber-tick interval in ms.  Each tick advances the index by
// ``stepFor(speed)``; default 1× = 1 frame ≈ 16 ms × 1 = ~62 fps.
const PLAYBACK_TICK_MS = 80;


export function KWNPlayback({ trajectory }: { trajectory: KWNTrajectory }) {
  const N = trajectory.times_s.length;

  // Resilience: a 0-or-1-point trajectory has nothing to scrub.  Bail
  // out early so the card still renders the rest of its content.
  if (N < 2) return null;

  const [idx, setIdx]       = useState<number>(N - 1);   // start at final
  const [playing, setPlaying] = useState<boolean>(false);
  const [speed, setSpeed]   = useState<1 | 2 | 5>(1);
  const playRef             = useRef<number | null>(null);

  // Auto-advance loop.  We use ``setInterval`` + a ref so the effect
  // tears down cleanly when the user pauses or unmounts; capping at
  // the final index instead of looping keeps the pedagogy clear
  // ("the run ended; here's the final state").
  useEffect(() => {
    if (!playing) {
      if (playRef.current !== null) window.clearInterval(playRef.current);
      playRef.current = null;
      return;
    }
    playRef.current = window.setInterval(() => {
      setIdx((i) => {
        const next = i + speed;
        if (next >= N - 1) {
          setPlaying(false);
          return N - 1;
        }
        return next;
      });
    }, PLAYBACK_TICK_MS);
    return () => {
      if (playRef.current !== null) window.clearInterval(playRef.current);
      playRef.current = null;
    };
  }, [playing, speed, N]);

  // Current-time spot values (memoised on idx so we don't recompute
  // every render of the SVG).
  const { tNow, vfNow, rNow, xNow } = useMemo(() => ({
    tNow:  trajectory.times_s[idx],
    vfNow: trajectory.vf[idx],
    rNow:  trajectory.r_bar_nm[idx],
    xNow:  trajectory.X_alpha[idx],
  }), [trajectory, idx]);

  return (
    <div className="mt-2 pt-2 border-t border-white/[0.04] space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-[8.5px] font-semibold uppercase tracking-[0.12em] text-slate-500">
          Aging playback
        </span>
        <span className="text-[8.5px] font-mono text-slate-400">
          t = {formatTime(tNow)}
        </span>
      </div>

      <MiniSeries
        label="Volume fraction"
        unit="%"
        values={trajectory.vf}
        spotValue={vfNow}
        displayValue={(v) => (v * 100).toFixed(3) + "%"}
        currentIdx={idx}
      />
      <MiniSeries
        label="Mean radius"
        unit="nm"
        values={trajectory.r_bar_nm}
        spotValue={rNow}
        displayValue={(v) => v.toFixed(1) + " nm"}
        currentIdx={idx}
      />
      <MiniSeries
        label="Matrix solute"
        unit="(X_α)"
        values={trajectory.X_alpha}
        spotValue={xNow}
        displayValue={(v) => (v * 100).toFixed(3) + "%"}
        currentIdx={idx}
      />

      {/* Scrubber */}
      <div className="flex items-center gap-2 pt-1">
        <button
          type="button"
          onClick={() => {
            if (idx >= N - 1) setIdx(0);  // restart from t=0 if at end
            setPlaying((p) => !p);
          }}
          aria-label={playing ? "Pause" : "Play"}
          className="shrink-0 w-5 h-5 grid place-items-center rounded bg-blue-500/15 border border-blue-500/30 hover:bg-blue-500/25 text-blue-300 transition-colors"
        >
          {playing
            ? <Pause size={9} />
            : (idx >= N - 1
                ? <RotateCcw size={9} />
                : <Play size={9} />)}
        </button>

        <input
          type="range"
          min={0}
          max={N - 1}
          step={1}
          value={idx}
          onChange={(e) => {
            setIdx(Number(e.target.value));
            if (playing) setPlaying(false);
          }}
          className="flex-1 accent-blue-400"
          aria-label="Aging-time scrubber"
        />

        {/* Speed selector */}
        <div className="shrink-0 flex items-center gap-0.5 text-[8.5px] font-mono">
          {([1, 2, 5] as const).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setSpeed(s)}
              className={`px-1 py-0.5 rounded transition-colors ${
                speed === s
                  ? "bg-blue-500/25 text-blue-200"
                  : "text-slate-500 hover:text-slate-300"
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


// ─────────────────────────────────────────────────────────────────────
// Mini-series — one row of the playback panel.
// Renders the label + spot value + a tiny SVG sparkline with a
// vertical marker at ``currentIdx``.
// ─────────────────────────────────────────────────────────────────────

interface MiniSeriesProps {
  label:        string;
  unit:         string;
  values:       number[];
  spotValue:    number;
  displayValue: (v: number) => string;
  currentIdx:   number;
}

function MiniSeries({
  label, unit, values, spotValue, displayValue, currentIdx,
}: MiniSeriesProps) {
  const W = 240;
  const H = 40;
  const PAD = 2;

  // Domain.  Guard against degenerate ranges (e.g. X_α never changes
  // when the alloy is under-saturated) so the SVG path stays visible
  // instead of collapsing to a flat zero line.
  const vMin = Math.min(...values);
  const vMax = Math.max(...values);
  const span = vMax - vMin || vMax || 1;

  const path = useMemo(() => {
    const pts: string[] = [];
    for (let i = 0; i < values.length; i++) {
      const x = PAD + (i / (values.length - 1)) * (W - 2 * PAD);
      const y = H - PAD - ((values[i] - vMin) / span) * (H - 2 * PAD);
      pts.push(`${i === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`);
    }
    return pts.join(" ");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [values]);

  const markerX = PAD + (currentIdx / (values.length - 1)) * (W - 2 * PAD);
  const markerY = H - PAD - ((spotValue - vMin) / span) * (H - 2 * PAD);

  // Subtle hint about the unit for screen-readers / users who want it.
  void unit;

  return (
    <div className="space-y-0.5">
      <div className="flex items-center justify-between text-[9px]">
        <span className="text-slate-400">{label}</span>
        <span className="font-mono text-blue-300">{displayValue(spotValue)}</span>
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        className="w-full h-9"
        role="img"
        aria-label={`${label} trajectory; current value ${displayValue(spotValue)}`}
      >
        {/* Curve */}
        <path
          d={path}
          fill="none"
          stroke="rgb(96 165 250)"          /* tailwind blue-400 */
          strokeWidth={1.1}
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        {/* Vertical marker line at the current scrubber position */}
        <line
          x1={markerX} x2={markerX}
          y1={PAD}     y2={H - PAD}
          stroke="rgb(147 197 253)"          /* blue-300 */
          strokeWidth={0.8}
          strokeDasharray="2 2"
          opacity={0.7}
        />
        {/* Spot dot */}
        <circle
          cx={markerX} cy={markerY} r={2.5}
          fill="rgb(147 197 253)"
          stroke="rgb(15 23 42)"             /* slate-900 ring for contrast */
          strokeWidth={1}
        />
      </svg>
    </div>
  );
}


/** Format seconds in a smart unit ladder (s → min → h → d). */
function formatTime(s: number): string {
  if (s < 60)       return `${s.toFixed(1)} s`;
  if (s < 3600)     return `${(s / 60).toFixed(1)} min`;
  if (s < 86400)    return `${(s / 3600).toFixed(2)} h`;
  return `${(s / 86400).toFixed(2)} d`;
}
