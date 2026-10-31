"use client";

/**
 * The INFINITE "endless bloom" (brand guidelines, 13 · Motion): new seeds are born at the centre and drift outward
 * for ever, with no cut — a secondary brand motion for loading states and ambient screens, never in place of the logo.
 *
 * Drawn from the symbol's own construction (guidelines, 04): seed i at i × 137.508°, at distance c·√i with
 * c = R / √n, its radius c·(0.28 + 0.50·t) growing toward the rim (t = distance / R); the origin seed, radius 0.62·c
 * in Infinite Red, stays at the centre. A seed born at time j keeps its angle j × 137.508° and moves straight out as
 * its age grows (distance c·√age), as in a real flower: the pattern never spins, it grows. Seeds fade in under the
 * origin and fade out at the rim. With reduced motion asked for, it is the settled flower, still.
 */
import { useEffect, useRef } from "react";


const GOLDEN = (137.508 * Math.PI) / 180;
const N = 55;                       // seeds in the flower at any time (the primary drawing has 55)
const RATE = 3;                     // seeds born per second: a calm, ambient pace

export function Bloom({ size = 64, seed, origin = "#E30613", className, label = "Working", decorative = false }: {
  /** px, the flower's diameter. Below 32 px the seeds blur together: use it larger than that. */
  size?: number;
  /** Default: paper seeds on the dark theme, ink on the light (the brand's primary and reversed versions). */
  seed?: string;
  origin?: string;
  className?: string;
  /** What is happening, for screen readers. */
  label?: string;
  /** Pure decoration (behind a logo, say): hidden from screen readers. */
  decorative?: boolean;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  // Paper seeds on the dark theme, ink on the light (the brand's reversed and primary versions). The app is dark by default.
  const light = typeof document !== "undefined" && document.documentElement.dataset.theme === "light";
  const seedColour = seed ?? (light ? "#141414" : "#F4F1EA");

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const dpr = typeof window !== "undefined" ? Math.min(window.devicePixelRatio || 1, 3) : 1;
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const still = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    const R = (size / 2) * (58 / 60);                 // the symbol's outer edge: 58 of 60 units
    const c = R / Math.sqrt(N);

    const draw = (u: number) => {
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, size, size);
      const cx = size / 2, cy = size / 2;
      ctx.fillStyle = seedColour;
      // Every seed alive at "time" u (in births): born at j, age u − j in (0, N].
      for (let j = Math.ceil(u - N); j < u; j++) {
        const age = u - j;
        const d = c * Math.sqrt(age);
        const t = d / R;
        const fadeIn = Math.min(1, age / 1.5);                  // grows out from under the origin
        const fadeOut = Math.min(1, (N - age) / 6);             // and leaves at the rim
        const r = c * (0.28 + 0.5 * t) * fadeIn;
        if (r <= 0) continue;
        ctx.globalAlpha = Math.max(0, fadeOut);
        const a = j * GOLDEN;
        ctx.beginPath();
        ctx.arc(cx + d * Math.cos(a), cy + d * Math.sin(a), r, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalAlpha = 1;
      ctx.fillStyle = origin;
      ctx.beginPath();
      ctx.arc(cx, cy, c * 0.62, 0, Math.PI * 2);
      ctx.fill();
    };

    if (still) {
      draw(N + 0.5);
      return;
    }
    let raf = 0;
    const t0 = performance.now();
    const tick = (now: number) => {
      draw(N + ((now - t0) / 1000) * RATE);                   // start full-grown: no empty first seconds
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [size, seedColour, origin]);

  return decorative
    ? <canvas ref={ref} aria-hidden="true" className={className} style={{ width: size, height: size }} />
    : <canvas ref={ref} role="img" aria-label={label} className={className} style={{ width: size, height: size }} />;
}
