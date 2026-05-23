# LeilMat in the wild: three case studies in metallic alloy design

*A 12-week sprint produced an AI-native design canvas for metallic alloys. These three case studies ask the obvious next question: does it actually work?*

---

LeilMat is a design tool for metallic alloys. You compose chemistry on a canvas, the tool predicts properties from first principles plus trained ML models, and an inverse-design loop proposes Pareto-optimal candidates against your target constraints. It's modelled on the way Cursor sits inside code or Figma sits inside design — a workspace for the discipline, with AI as an integrated collaborator rather than a bolted-on chatbot.

After 12 weeks of build, we had something that ran end-to-end. Materials Project DFT phase diagrams, real ML-trained yield-strength models for steel, aluminium, titanium and nickel families, manufacturability scoring across castability/weldability/cost, BoTorch qEHVI inverse design, M3GNet for DFT-grade formation energies, an agentic Local-AI suggestion layer powered by DeepSeek V4 Pro.

A tool that runs end-to-end is not the same as a tool that works. We needed to know: when you point this at canonical engineering problems, does it produce defensible answers?

So we built three case studies. Each one takes a real-world alloy design brief, runs LeilMat against it, compares the predictions to the published values for the dominant reference alloys in that space, and writes up what we learned. Every figure, table and number regenerates by running a single Python script. We didn't tune anything to make the results look better.

These are the reports.

---

## The three cases

### [Case 1 — V-free titanium for an orthopaedic hip stem](01_titanium_orthopaedic/)

Ti-6Al-4V is implanted in millions of people. The 4% vanadium has had a cytotoxicity question mark over it for thirty years. The industry has been chasing V-free replacements that match Ti-6-4 on strength and density: Ti-6Al-7Nb, Ti-13Nb-13Zr, Ti-15Mo.

We asked LeilMat to design one from scratch. **It reproduced Ti-6Al-4V ELI's strength within 2.1% and density within 0.7%**, generated seven Pareto-optimal V-free candidates that all met the ASTM strength target, and identified its own most important weakness — it doesn't know about Ti₃Al embrittlement, which would render its top candidate unmakeable in practice.

**Takeaway:** strong reproduction of well-trodden chemistry, honest extrapolation failure on β-stabilised alloys, and a clear next-step product feature (phase-stability guardrails).

### [Case 2 — Third-generation Al-Cu-Li for an aerospace stringer](02_aluminum_li_aerospace/)

Each gram you remove from an aircraft saves $3,000 in fuel over its life. Modern Al-Cu-Li alloys (2050, 2099, 2196) make up the primary stringer material in the Airbus A350 fuselage, and they exist because of that arithmetic.

We asked LeilMat to design a fuselage stringer alloy with no knowledge of any specific commercial reference. **It rediscovered the 2099 chemistry envelope within ±8% on yield strength** across three modern Al-Li alloys, found 12 candidates on a clean Pareto front, and exposed a 6% systematic density bias from rule-of-mixtures that we can fix in ten lines of code.

**Takeaway:** essentially perfect reproduction of an established design space and one clearly diagnosable, easily-fixable bias. This is the case study that most directly demonstrates LeilMat doing its intended job.

### [Case 3 — When the AI gets it wrong: a Ni-superalloy cautionary tale](03_nickel_am_turbine/)

The hottest part of a jet engine is the turbine inlet, where Ni-base superalloys carry the load. 3D-printing these alloys is the bleeding edge of metal additive manufacturing.

We asked LeilMat to design a 3D-printable Ni superalloy. **It predicted CMSX-4, Inconel 738 and Inconel 625 within ±5%**. It also predicted **Inconel 718** — the most-used AM superalloy in the world — **−36% off**. The miss is honest, traceable to a single missing class of training data (Nb-bearing γ″ chemistries), and the case study uses it to map the highest-priority data-curation task for the next product iteration.

**Takeaway:** the failure is more useful than the wins. A model that fails visibly is auditable. A model that fails invisibly is a liability.

---

## The bigger picture: a 53% within-tolerance rate is what works

Across all three case studies, we compared LeilMat's predictions to literature values for 15 named alloys. The headline number:

> **8 out of 15 alloys predicted within ±15% — engineering-design tolerance.**

It would be more flattering to write "the model gets everything right." That wouldn't be true, and it wouldn't be useful. What's true is:

- **For mainstream alloy chemistry (Ti-6-4 class, modern Al-Li, γ′-strengthened Ni superalloys), LeilMat predicts within 5-8%** — well inside what an engineer would call useful for early screening.

- **For under-represented chemistries (β-stabilised Ti, γ″-Nb Ni, non-peak-aged Al tempers), the model misses badly but reports its uncertainty correctly.** A user reading the prediction alongside its uncertainty band would discount the failures appropriately.

- **The failures cluster around three specific patterns:** training-set bias toward peak-aged tempers, γ″-Nb strengthening absent from the Ni training data, and an Al-Li density bias from rule-of-mixtures linearity. All three are addressable with incremental data curation and minor code changes. None of them require redesigning the modelling stack.

This is the right shape of result for an early-stage AI design canvas. The tool's bones are sound. The gaps point at specific, tractable improvements.

## The product roadmap, written by the case studies

If we read the three case studies as a single body of evidence and ask "what should the next twelve weeks focus on?", the answer is unusually clear:

1. **Curate 5-10 more Nb-bearing Ni superalloys.** Closes the Inconel 718 gap. ~2 days.
2. **Add temper state as an input feature** to the Al and Ti models. Fixes the T3-vs-T6 confusion. ~3 days.
3. **Build a phase-stability guardrail layer** that flags compositions sitting in known embrittling regimes (Ti₃Al, σ-phase, Al₂MgLi). ~1 week.
4. **Add a partial-molar-volume correction** for Al-Li density. ~10 lines of code.

Three out of four are data tasks. None of them is an architecture change. **That's the most actionable kind of finding an early validation exercise can produce.**

## What these case studies are (and are not)

These case studies are:

- **Reproducibility evidence.** Every figure and every number regenerates from running three Python scripts. No private hooks. No cherry-picked seeds. No retroactive tuning.
- **Honest reports.** When LeilMat fails, the report says so and diagnoses why.
- **A product roadmap, written backwards from results.** Each documented "❌" is a specific data-collection or modelling task that would close the gap.

These case studies are not:

- **Industrial validation.** They compare predicted properties to published handbook values, not to laboratory experiments on novel-composition castings. Suitability for any specific aerospace, medical or automotive application would require experimental qualification.
- **Coverage proofs.** The three cases cover Ti, Al-Li and Ni — they don't say anything about Mg, Cu, refractory alloys, HEAs or metallic glasses. Those need separate validation.
- **Confidence intervals.** The 53% within-tolerance rate is over 15 alloys, not a statistically powerful sample. It's a directional signal.

## How to read these

Each case study is structured as a short report you can read top-to-bottom in 10-15 minutes:

1. **The brief and the stakes** — why the application matters in the real world
2. **What we asked LeilMat to do** — the inverse-design configuration in plain English
3. **What it returned** — the top candidates as a table, with a Pareto-front figure
4. **How well it knows the textbook** — predicted vs literature for the reference alloys
5. **The interesting bit** — what surprised us, what failed, what it means
6. **What we'd believe and what we wouldn't** — an honest score-card

You can also read just the [aggregate scorecard table](#the-bigger-picture-a-53-within-tolerance-rate-is-what-works) at the top of this page and skip to the case study whose chemistry you care about.

## Reproduce

```bash
# From repository root
source .venv/bin/activate
python case_studies/01_titanium_orthopaedic/run.py    # ~30 s
python case_studies/02_aluminum_li_aerospace/run.py   # ~30 s
python case_studies/03_nickel_am_turbine/run.py       # ~30 s
```

All three scripts use only the **public LeilMat APIs** that the design canvas itself calls. The full pipeline — RF training data, BoTorch configuration, property providers, manufacturability rules — is in the LeilMat repository at `apps/api/ml/`. Each prediction comes with a source label (`RF/Ti`, `ROM`, `Tabor`, `Electrochem`, `M3GNet`) that traces back to the exact rule or model file.

Seed = 42 throughout. If you change the seed, the numbers shift a few percent but the qualitative results — modern Al-Li on the Pareto front, Inconel 718 underprediction, Ti₃Al boundary violations — are robust.

---

*LeilMat is an AI-native design canvas for metallic alloys. These case studies were run as part of a broader 12-week sprint to take the tool from "great UX with placeholder science" to "great UX with defensible science." The case studies are the public-facing evidence that the sprint produced something real.*
