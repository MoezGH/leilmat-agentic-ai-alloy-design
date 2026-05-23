"""
End-to-end LeilMat walkthrough on a single composition (6061-T6).

This script is the "credibility artifact" — it takes one composition through
every shipped sprint's module-level API in sequence and prints a narrated
trace.  No HTTP, no FastAPI; the modules are called directly so the script
doubles as a smoke test (CI runs it and asserts no step errors out).

Run:
    python scripts/demo_6061_t6.py                  # fast path (~5-10 s)
    python scripts/demo_6061_t6.py --include-slow   # adds Scheil + Taichi (~5-15 min)
    python scripts/demo_6061_t6.py --json           # machine-readable output

Composition reference: 6061 nominal — Al 97.9 / Mg 1.0 / Si 0.6 /
Cu 0.28 / Cr 0.2 (wt %).  Temper: T6 (solutionise @ 530 °C, water-quench,
artificial-age @ 175 °C for 8 h).  Literature YS ≈ 276 MPa (MIL-HDBK-5J).
"""
from __future__ import annotations

import argparse
import json as json_module
import sys
import time
import traceback
from pathlib import Path
from typing import Any

# Add the repo root to sys.path so the `apps` package imports work whether
# this script is run with `python scripts/demo_6061_t6.py` (relative to
# repo root) or `python /abs/path/scripts/demo_6061_t6.py`.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# ─────────────────────────────────────────────────────────────────────
# 6061-T6 nominal composition + processing conditions
# ─────────────────────────────────────────────────────────────────────

COMPOSITION_WT = {
    "Al": 97.9,
    "Mg": 1.0,
    "Si": 0.6,
    "Cu": 0.28,
    "Cr": 0.2,
}
TEMPER = "T6"

SOLUTIONISING_K = 803.0   # 530 °C
AGING_K         = 448.0   # 175 °C
AGING_TIME_S    = 8 * 3600

# Reference values from MIL-HDBK-5J / ASM Handbook v.2 — used only for
# the "vs literature" narration; not enforced.
LIT_YS_MPA       = 276
LIT_DENSITY      = 2.70
LIT_COST_AMS     = 9.50     # USD/kg, AMS 4027 plate
LIT_BETA_VF      = 0.012    # Marioara 2003 (TEM)
LIT_BETA_R_NM    = 5.0


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _comp_str(comp: dict) -> str:
    return " · ".join(f"{el} {v:.2f}" for el, v in comp.items())


class Step:
    """One step of the walkthrough.  Captures timing + outcome."""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.elapsed_s: float | None = None
        self.outcome: str = "pending"   # pending | ok | skipped | error
        self.payload: dict[str, Any] = {}
        self.error: str | None = None
        self._t0: float = 0.0

    def __enter__(self) -> "Step":
        print(f"\n[{self.name}]  {self.description}")
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.elapsed_s = round(time.perf_counter() - self._t0, 3)
        if exc is None and self.outcome == "pending":
            self.outcome = "ok"
        if exc is not None:
            self.outcome = "error"
            self.error = f"{exc_type.__name__}: {exc}"
            print(f"    ⚠ ERROR after {self.elapsed_s}s: {self.error}")
            traceback.print_exception(exc_type, exc, tb)
            return True   # swallow; we still want subsequent steps to run
        marker = {"ok": "✓", "skipped": "—", "error": "⚠"}[self.outcome]
        print(f"    {marker} {self.elapsed_s}s")
        return False

    def line(self, s: str) -> None:
        print(f"    {s}")

    def skip(self, reason: str) -> None:
        self.outcome = "skipped"
        print(f"    — skipped: {reason}")


# ─────────────────────────────────────────────────────────────────────
# Steps
# ─────────────────────────────────────────────────────────────────────

def step_calphad_equilibrium(steps: list[Step]) -> None:
    from apps.api.ml.calphad.equilibrium import phase_assemblage_sync

    s = Step("1/8  CALPHAD equilibrium",
             f"phase assemblage @ {SOLUTIONISING_K:.0f} K (solutionising) "
             f"and {AGING_K:.0f} K (T6 aging)")
    steps.append(s)
    with s:
        last_source = None
        for label, T_K in [("solutionising 530 °C", SOLUTIONISING_K),
                           ("T6 aging 175 °C",      AGING_K)]:
            out = phase_assemblage_sync(COMPOSITION_WT, T_K)
            phases = out.get("phases") or {}
            top3 = sorted(phases.items(), key=lambda kv: -kv[1])[:3]
            phases_s = ", ".join(f"{p} {f:.3f}" for p, f in top3) or "—"
            s.line(f"@ {label:<22s} → {phases_s}")
            s.line(f"    source: {out.get('source')}  tdb: {out.get('tdb')}")
            last_source = out.get("source")
        s.payload = {"source": last_source}


def step_scheil(steps: list[Step], include_slow: bool) -> None:
    s = Step("2/8  Scheil solidification",
             "non-equilibrium freezing range + mushy zone")
    steps.append(s)
    with s:
        if not include_slow:
            s.skip("slow (~3-5 min); pass --include-slow to run")
            return
        from apps.api.ml.calphad.scheil import scheil_solidification_sync
        out = scheil_solidification_sync(COMPOSITION_WT, T_start_K=1000.0)
        liq = out.get("liquidus_K"); sol = out.get("solidus_K")
        mushy = out.get("mushy_K")
        s.line(f"liquidus {liq} K  ·  solidus {sol} K  ·  mushy {mushy} K")
        terminal = (out.get("terminal_liquid") or {})
        if terminal:
            s.line(f"terminal liquid: {_comp_str(terminal)}")
        s.payload = {"liquidus_K": liq, "solidus_K": sol, "mushy_K": mushy}


def step_ttt(steps: list[Step]) -> None:
    s = Step("3/8  TTT diagram",
             "Fe-C austenite decomposition kinetics")
    steps.append(s)
    with s:
        s.skip("not applicable to Al alloys (TTT is Fe-C only)")


def step_microstructure(steps: list[Step], include_slow: bool) -> None:
    s = Step("4/8  Microstructure (Taichi KWC)",
             "full anisotropic dendrite morphology")
    steps.append(s)
    with s:
        if not include_slow:
            s.skip("slow (~5-30 min depending on grid); pass --include-slow to run")
            return
        try:
            from apps.api.ml.microstructure.taichi_kwc import simulate_dendrite_taichi
        except Exception as exc:
            s.skip(f"Taichi unavailable: {exc}")
            return
        out = simulate_dendrite_taichi(grid=200, steps=2000, n_fold=6)
        s.line(f"final solid fraction: {out.get('solid_fraction', '—')}")
        s.line(f"runtime: {out.get('elapsed_s', '—')} s on {out.get('backend', 'taichi')}")
        s.payload = {"sf": out.get("solid_fraction")}


def step_precipitation(steps: list[Step]) -> None:
    from apps.api.ml.precipitation.kwn import simulate_precipitation_sync

    s = Step("5/8  KWN precipitation",
             f"β″-Mg₂Si nucleation+growth+coarsening, 175 °C for "
             f"{AGING_TIME_S/3600:.0f} h")
    steps.append(s)
    with s:
        out = simulate_precipitation_sync(
            COMPOSITION_WT, phase="Mg2Si_beta_doubleprime",
            T_C=175.0, aging_time_s=AGING_TIME_S,
        )
        value = out.get("value") or {}
        vf = value.get("volume_fraction")
        r_nm = value.get("mean_radius_nm")
        N = value.get("number_density_per_m3")
        if vf is None:
            s.line(f"refused: {out.get('error') or out.get('note') or 'no value'}")
            s.payload = {"refused": True, "source": out.get("source")}
            return
        s.line(f"volume fraction: {vf:.4f}      (lit. ~{LIT_BETA_VF})")
        s.line(f"mean radius:     {float(r_nm):.1f} nm  (lit. ~{LIT_BETA_R_NM} nm)")
        s.line(f"number density:  {N:.2e} /m³")
        s.line(f"source: {out.get('source', 'kwn_robson_2004')}")
        s.payload = {"vf": vf, "r_nm": float(r_nm), "N_per_m3": float(N),
                     "source": out.get("source")}


def step_predict_properties(steps: list[Step]) -> None:
    from apps.api.ml.matgl_models import predict_properties

    s = Step("6/8  Yield strength + bulk properties",
             f"RF per-family + temper one-hot + physics features (temper={TEMPER})")
    steps.append(s)
    with s:
        out = predict_properties(COMPOSITION_WT, temper=TEMPER)
        # Flat shape carries the numeric values; _details carries the rich
        # per-property dicts with CI + source provenance.
        details = out.get("_details") or {}
        ys_det  = details.get("yield_strength_MPa") or {}
        ys_val  = ys_det.get("value")
        ci_lo   = ys_det.get("ci_low")
        ci_hi   = ys_det.get("ci_high")
        src     = ys_det.get("source")
        temper_used = (ys_det.get("_details") or {}).get("temper_used")

        if ys_val is not None:
            s.line(f"YS predicted: {ys_val:.0f} MPa  (lit. {LIT_YS_MPA} MPa)")
            if ci_lo is not None and ci_hi is not None:
                s.line(f"90% conformal interval: [{ci_lo:.0f}, {ci_hi:.0f}] MPa")
            s.line(f"source: {src}  ·  temper used: {temper_used or TEMPER}")
        else:
            s.line(f"YS prediction unavailable: {ys_det.get('error') or 'no value'}")

        rho = out.get("density_g_cm3")
        E   = out.get("elastic_modulus_GPa")
        if rho is not None:
            s.line(f"density:  {float(rho):.2f} g/cm³  (lit. {LIT_DENSITY})")
        if E is not None:
            s.line(f"E modulus: {float(E):.0f} GPa")
        s.payload = {"ys_MPa": ys_val, "ci_low": ci_lo, "ci_high": ci_hi,
                     "source": src}


def step_cost(steps: list[Step]) -> None:
    from apps.api.ml.cost.model import compute_cost

    s = Step("7/8  Hierarchical cost",
             f"plate · AMS 4027 · {TEMPER} · 100 kg lot")
    steps.append(s)
    with s:
        out = compute_cost(
            COMPOSITION_WT, form="plate", cert="AMS",
            ht=TEMPER, lot_kg=100,
        )
        usd = out.get("USD_per_kg")
        if usd is None:
            s.line(f"cost computation refused: {out.get('error', '—')}")
            return
        bd = out.get("breakdown", {})
        s.line(f"USD/kg: ${usd:.2f}  (commercial quote ≈ ${LIT_COST_AMS:.2f}/kg)")
        s.line(f"  family: {out.get('family')}")
        s.line(f"  spot:           ${bd.get('spot_price_USD_per_kg', 0):.2f}/kg")
        s.line(f"  × form (plate)  {bd.get('form_factor_multiplier', '—')}")
        s.line(f"  × cert (AMS)    {bd.get('certification_multiplier', '—')}")
        s.line(f"  × HT  ({bd.get('heat_treatment_class')})  {bd.get('heat_treatment_multiplier', '—')}")
        s.line(f"  + supplier min  ${bd.get('supplier_overhead_USD', 0):.0f} → "
               f"${bd.get('supplier_overhead_per_kg', 0):.2f}/kg over {bd.get('lot_kg')} kg lot")
        s.payload = {"USD_per_kg": usd, "family": out.get("family")}


def step_inverse_reference(steps: list[Step]) -> None:
    """Inverse design isn't a single-composition operation — it takes a
    DesignBrief and returns candidates.  Document the closest brief from the
    canonical set (Aerospace Al wing skin) rather than re-run BoTorch here."""
    s = Step("8/8  Inverse design (reference)",
             "Aerospace Al wing skin brief — see Sprint 7 canonical-brief runner")
    steps.append(s)
    with s:
        from apps.api.ml.eval.canonical_briefs import CANONICAL_BRIEFS
        brief = next((b for b in CANONICAL_BRIEFS
                      if "Al wing skin" in b.name), None)
        if brief is None:
            s.skip("brief not found")
            return
        s.line(f"brief: {brief.name}")
        objs = [o.property for o in brief.objectives]
        s.line(f"  objectives:  {len(brief.objectives)} ({objs})")
        s.line(f"  constraints: {len(brief.constraints)}")
        s.line(f"  temper:      {brief.temper}")
        s.line("(run `python -m apps.api.ml.eval.brief_runner` for live execution)")
        s.payload = {"brief": brief.name}


# ─────────────────────────────────────────────────────────────────────
# Orchestration
# ─────────────────────────────────────────────────────────────────────

def run(include_slow: bool, as_json: bool) -> int:
    print("=" * 72)
    print(f"LeilMat — end-to-end demo on 6061-{TEMPER}")
    print(f"  composition (wt%): {_comp_str(COMPOSITION_WT)}")
    print(f"  temper: {TEMPER}  ·  aging: 175 °C for {AGING_TIME_S/3600:.0f} h")
    print("=" * 72)

    steps: list[Step] = []
    t0 = time.perf_counter()

    step_calphad_equilibrium(steps)
    step_scheil(steps, include_slow)
    step_ttt(steps)
    step_microstructure(steps, include_slow)
    step_precipitation(steps)
    step_predict_properties(steps)
    step_cost(steps)
    step_inverse_reference(steps)

    total_s = round(time.perf_counter() - t0, 2)

    print("\n" + "=" * 72)
    n_ok      = sum(1 for s in steps if s.outcome == "ok")
    n_skipped = sum(1 for s in steps if s.outcome == "skipped")
    n_error   = sum(1 for s in steps if s.outcome == "error")
    print(f"summary: {n_ok} ok  ·  {n_skipped} skipped  ·  {n_error} errors  "
          f"·  total {total_s}s")

    sources = sorted({(s.payload or {}).get("source")
                      for s in steps if s.payload and (s.payload or {}).get("source")})
    if sources:
        print(f"sources used: {', '.join(filter(None, sources))}")

    if as_json:
        print("\n--- JSON ---")
        print(json_module.dumps({
            "composition_wt": COMPOSITION_WT,
            "temper": TEMPER,
            "steps": [
                {
                    "name":      s.name,
                    "outcome":   s.outcome,
                    "elapsed_s": s.elapsed_s,
                    "error":     s.error,
                    "payload":   s.payload,
                }
                for s in steps
            ],
            "total_elapsed_s": total_s,
        }, indent=2, default=str))

    # Exit code: 0 if no errors (skipped is fine); 1 if any error.
    return 1 if n_error else 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="End-to-end LeilMat demo on 6061-T6.")
    parser.add_argument(
        "--include-slow", action="store_true",
        help="also run Scheil + Taichi microstructure (multi-minute)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="emit a machine-readable JSON summary after the narrated trace",
    )
    args = parser.parse_args()
    raise SystemExit(run(include_slow=args.include_slow, as_json=args.json))


if __name__ == "__main__":
    main()
