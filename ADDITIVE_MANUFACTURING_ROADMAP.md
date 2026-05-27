# Additive Manufacturing Roadmap — LeilMat

**Status:** strategic planning document.  Not yet a sprint.
**Authored:** 2026-05-27 (conversation between Moez + the AI session).
**Trigger:** discussion of which growth industries LeilMat should
target next.  Conclusion was that AM / 3D-printing / sintering is
the right anchor — well-funded customers (aerospace, medical,
defence), unsolved materials problems, and certification overhead
that favours tools producing defensible documentation.

This document captures the thinking so we can pick up the work
when the time is right.

---

## Why AM is the right anchor

**Three structural advantages over chasing the wrought-alloy market:**

1. **Open materials problems.** AM doesn't have 50 years of property
   tables behind it.  Every alloy + machine + parameter combination
   needs fresh characterisation.  Tools that *compute* what experiment
   would tell us are worth real money to AM teams.

2. **Well-funded customer base.** Aerospace (Boeing, Airbus, GE,
   Pratt & Whitney, Safran), medical (Stryker, Zimmer, J&J), defence
   primes, and the dedicated AM service bureaus (Materialise, Sintavia,
   Carpenter Additive) all have R&D budgets where a $10-30k/year
   software seat is a rounding error if it shortens parameter
   qualification by 2 weeks.

3. **Certification overhead favours us.** Every AM part for an
   aerospace or medical application ships with a certification packet
   (AMS, Mil-Std, FDA 510k, ASTM F3001-F3413).  Provenance-everywhere
   audit-grade PDFs are the killer feature — LeilMat already produces
   them.

**Three competitive openings:**

The AM software market splits cleanly into two camps and LeilMat
sits in the gap:

| Camp | Tools | What they solve | What they ignore |
|---|---|---|---|
| **FE process simulators** | ANSYS Additive Print, Autodesk Netfabb Simulation, Atlas3D Sunata, Siemens Simcenter | Thermal problem — melt pool, residual stress, warp, distortion | Materials science.  They tell you the temperature history; they can't tell you what alloy to use or what YS the part will have |
| **Materials databases** | ANSYS GRANTA, JMatPro, Thermo-Calc | Properties + thermodynamics for wrought alloys | AM.  Wrought-alloy data often doesn't apply to as-built LPBF (anisotropy, dendrite refinement, residual stress, defects) |

**LeilMat = CALPHAD + ML + phase-field + agentic AI + audit-grade PDFs.**
That combination is unique.  Neither the FE camp nor the materials
camp can pivot to it without rebuilding from scratch.

---

## What LeilMat already serves on the AM side

We're ~60 % of the way to an AM platform without realising it.  The
existing modules map directly onto AM workflows:

| Module | AM relevance | Coverage |
|---|---|---|
| Scheil-Gulliver solidification | LPBF/EBM is solidification with extreme cooling rates.  Hot-tearing risk lives in the Scheil curve | ✅ Shipped (qualitative hot-tear flag — needs Kou CSC quantification) |
| Anisotropic phase-field dendrite (Taichi KWC) | LPBF microstructure = columnar / cellular dendrites driven by G/R anisotropy | ✅ Shipped — currently under-used; needs an AM use-case framing |
| KWN precipitation kinetics + aging playback | Post-build heat treatment (T6, HIP+aged) | ✅ Shipped |
| 1-D Fick diffusion (Crank-Nicolson) | Homogenisation cycles, HIP densification, multi-material AM interfaces | ✅ Shipped |
| Conformal-CI property prediction (RF + temper one-hot) | Every AM part needs certified property numbers with uncertainty | ✅ Shipped |
| Audit-grade PDF report with brand polish | AMS / Mil-Std certification packets | ✅ Shipped |
| Agentic AI copilot with click-to-apply pills | Walking a junior engineer through "design an AM alloy" | ✅ Shipped |
| Scalmalloy reference design | Canonical LPBF Al-Mg-Sc-Zr | ✅ In the starter prompts |

What's missing is **AM-specific framing in the UI** and a handful of
purpose-built modules.  We don't need to rebuild the engine; we need
to install AM-shaped seats on top of it.

---

## What's missing

The AM-engineer workflow has eight things LeilMat doesn't do yet:

| Gap | What AM users need | Effort |
|---|---|---|
| **Process window mapping (LPBF)** | Given (laser power P, scan speed v, hatch spacing h, layer thickness t), tell me whether I'll get porosity, keyhole, balling, or lack-of-fusion | 3-5 days |
| **Cooling-rate → microstructure chaining** | LPBF cooling rate ~10⁴-10⁶ K/s should feed *automatically* into the dendrite simulator | 2-3 days (mostly wiring) |
| **Hot tearing quantification** | Kou's CSC (Crack Susceptibility Coefficient) computed from the Scheil curve as a number, not just a flag | 1-2 days |
| **AM alloy library** | AlSi10Mg, Ti-6Al-4V, Inconel 718, 316L, 17-4PH, CoCrMo, Maraging 300, H13.  None well-covered in the current ~150-entry dataset | 1 week curation |
| **Build-direction anisotropy** | Z vs XY mechanical property delta from columnar grain texture | 1 week |
| **HIP densification kinetics** | Pore closure under pressure + temperature over time | 3-4 days (extends the diffusion solver) |
| **Sintering Master Sintering Curve** | For binder jet + traditional powder-met workflows | 1 week |
| **Residual stress estimator** | Simplified inherent-strain method for warp / distortion | 2 weeks |

---

## Phased roadmap

### Phase A — "AM-ready" badge (3-4 weeks)

Goal: any AM engineer landing on LeilMat sees themselves in the tool
within 30 seconds.

1. **AM alloy library expansion** — curate AlSi10Mg / Ti-6Al-4V /
   Inconel 718 / 316L / 17-4PH / CoCrMo / Maraging 300 / H13 with
   as-built + post-HIP + post-aged properties from MMPDS-08, AMS
   specs, and recent LPBF papers.  Tag each entry with process info
   (LPBF / EBM / DED) so they can be filtered.

2. **LPBF process-window calculator** — new card in Process
   Simulation.  Inputs: alloy + (P, v, h, t).  Outputs: 2-D colour-map
   of defect modes (porosity, keyhole, balling, LoF) based on
   normalised enthalpy + Rayleigh-number heuristics (Mostafaei et al.;
   King et al.).  Click any point on the map → reads back to the
   composition canvas.

3. **Hot tearing CSC** — replace the qualitative Scheil hot-tear flag
   with Kou's CSC number (vulnerability index from the solidification
   path's terminal slope, dT/d√fs).  Already have the Scheil curve;
   this is just post-processing.

4. **Cooling-rate piping** — when the user runs the LPBF process
   window, automatically feed the predicted cooling rate into the
   existing Taichi dendrite simulator.  One-click "see the
   microstructure you'd get."

**Deliverable:** a working **AM design canvas** that takes an alloy +
LPBF params → predicts microstructure + defects + properties →
exports a certification packet.

### Phase B — moat features (1-2 months)

The things competitors don't have:

5. **Build-direction anisotropy** — predict Z vs XY ultimate tensile
   strength + elongation delta from columnar grain texture (already
   surfaced by the dendrite simulator).  Critical for design
   engineers sizing parts.

6. **HIP cycle simulator** — extends the 1-D Fick code to a multi-
   process timeline: solution → quench → HIP → age.  Track porosity
   closure + precipitation evolution in one chained timeline.

7. **AM-specific inverse design** — BoTorch with AM-relevant objective
   (e.g. *maximise YS / minimise hot-tearing CSC / stay below density
   4.5 g/cm³ / keep process-window area > 200 J/mm³*).  Different
   acquisition function than the wrought-alloy inverse.

8. **As-built vs heat-treated property toggle** — the existing temper
   selector becomes an AM-state selector (`"as-built"`,
   `"stress-relieved"`, `"HIP'd"`, `"HIP+aged"`, `"T6"`) for AM
   alloys.  Training data feeds into the existing RF models.

### Phase C — closing the loop (3-6 months)

9. **Sintering / binder jet** — Master Sintering Curve, densification
   kinetics (Coble creep + lattice diffusion), grain coarsening.
   Opens the binder-jet customer segment (Desktop Metal, ExOne,
   HP Multi Jet Fusion adjacencies).

10. **Multi-material / functionally graded** — composition gradients
    through the build.  Reuses the existing diffusion solver across
    interfaces.

11. **Residual stress + warp** — inherent-strain method.  Skip full
    FEM; this is design-stage estimation, not validation.
    Differentiates from the ANSYS / Autodesk simulators (which need
    full part geometry; ours is composition-aware).

12. **Powder feedstock characterisation** — given particle-size
    distribution, morphology, oxygen content → predict packing
    density + flowability.  Important for LPBF parameter
    qualification + AS9100 supplier audits.

---

## Strategic positioning

The pitch to an AM customer, written as the user would experience it:

> *"You picked AlSi10Mg + parameters X.  LeilMat predicts: 3.5 %
> porosity (process window plot here), columnar grain size 8 μm Z /
> 4 μm XY (dendrite simulator here), as-built YS 240 ± 20 MPa,
> post-T6 YS 310 ± 18 MPa, hot-tearing CSC 0.42 (acceptable), HIP
> closes pores to < 0.1 % in 4 h at 530 °C / 100 MPa.  Here's the
> full certification packet."*

Three clicks, one PDF, audit-grade.  No FE software needed.

**Why LeilMat wins this conversation:**

1. **Materials science integrated with process** — competitors solve
   thermal or materials, never both
2. **Browser-native, no install** — AM engineers move between sites;
   cloud-first wins over Windows desktop apps
3. **Agentic AI copilot** — junior engineers can lean on it; senior
   engineers can ignore it.  Both find value
4. **Audit-grade PDFs already shipped** — direct fit for AMS /
   Mil-Std / FDA documentation requirements
5. **Open-source stack** — inspectable by customer security review;
   no vendor lock-in story to worry about

**Target customer segments, by tier of expected fit:**

| Tier | Segment | Why a good fit |
|---|---|---|
| 1 | AM service bureaus (Materialise, Sintavia, Carpenter Additive, Velo3D, EOS application labs) | They qualify dozens of parameter combinations per quarter.  LeilMat shortcuts 80 % of that |
| 1 | Aerospace alloy R&D groups (GE, Pratt & Whitney, Safran, RR) | Custom-alloy development for engines; need full provenance + CALPHAD + property prediction |
| 2 | Medical-device alloy teams (Stryker, Zimmer, Bone Solutions) | Ti-6Al-4V + CoCrMo + Ta + Mg-alloy implants; conformal CIs + audit packets matter for 510k filings |
| 2 | Defence + space (Lockheed, NG, Anduril, Relativity Space) | Custom HEAs, refractory alloys, AlSi10Mg / Scalmalloy for lightweighting |
| 3 | Tooling + injection-mold makers (Mold Hotrunner, Hoffman Group) | Maraging steel, H13, conformal cooling channels.  Smaller market but well-funded |
| 3 | Academic AM research groups | Lower revenue but high credibility per seat |

---

## Suggested first move (when we come back)

**Phase A item 3 — Kou CSC quantification — is the cheapest highest-impact place to start.**

* The Scheil curve is already computed by the Sprint 2 module
* CSC is a 5-line post-processing step (terminal-slope ratio)
* Lets us put a *number* on hot-tearing risk that AM engineers
  already use as a screening metric
* Demonstrable in a single screenshot for marketing

Estimated effort: **half a day**.  After that ships, items 1, 2, 4
of Phase A in any order — they're independent.

Phase A as a whole (~3-4 weeks) gets us to the **"AM-ready" badge**
and unlocks the customer conversations.  Everything beyond that is
incremental moat-building.

---

## Out of scope for now

* Full FE thermal simulation (ANSYS / Autodesk territory) — LeilMat
  stays composition-aware, not part-geometry-aware
* Topology optimisation — would require a generative-design layer
  that's a different product, not LeilMat
* Machine-specific parameter recommendations (EOS M290 vs SLM 280
  vs Renishaw AM500) — defer until we have machine-database access
  via NIMS or a manufacturer partnership

---

## When to revive this document

Three trigger conditions, any one of which justifies opening Phase A:

1. **A real AM customer asks for it.**  Pilot conversation with an
   aerospace / medical R&D group where "show us your LPBF process
   window calculator" is the gating ask.
2. **The general LeilMat customer base hits ~20 paying seats.**  At
   that scale the next 10× is a vertical specialisation; AM is the
   best one.
3. **Internal capacity opens up.**  After the next major non-AM
   sprint (NIMS data ingest, stress-strain mini-sim, LeilAI-5
   credit-mapping fix), if no urgent customer item is pending, this
   is the highest-leverage initiative to take on.

Until then, this document stays put.  No half-built AM features —
either we go in seriously or we don't go in.

Authored: 2026-05-27.  Revisit before any sprint planning that
includes a vertical-specialisation discussion.
