# LeilMat — 12-Week Deep-on-Metals Plan

## Strategic context

**Decision (May 14, 2026):** Stay focused on **metallic alloys** for the next 12 months. Go deeper, not wider. Don't generalize to polymers/composites/biomaterials until LeilMat has a clear moat in metals.

**One-sentence positioning:** *"The AI-native design canvas for metallic alloys."*
Covers: steels, Al, Ti, Ni-superalloys, Cu, Mg, refractories, high-entropy alloys (HEAs), metallic glasses.

**Why this beats going generic:**
- Our science stack (Magpie, Materials Project, pymatgen, BoTorch, IIW Carbon Equivalent) is *inorganic-crystalline-metal* tooling. Generalizing means a 6-month rebuild per material class.
- Specialization signals expertise. Generic "materials AI" reads as "knows nothing well."
- The competitive landscape is most exploitable in metals: Citrine is broad/shallow, Granta is a database, Materials Project has no inverse design UI, academic tools aren't productized.
- Hot growth markets are metallic: aerospace alloys, EV battery casings, aviation engines, defense refractories, additive manufacturing.
- We expand to **ceramics** in months 13-18 (reuses 80% of our stack), and only consider polymers in year 2+.

---

## 12-week execution plan

### Phase A — DFT-grade formation energy (Weeks 1-2) ⚙️ *in progress*

**Goal:** Replace the Miedema heuristic with M3GNet (universal interatomic potential pretrained on Materials Project DFT data). Turn the `Miedema` amber chip into a `M3GNet (DFT)` violet chip with ~5 meV/atom accuracy.

**Deliverables:**
- `apps/api/ml/m3gnet_predictor.py` — lazy-loaded MatGL model, structure builder from composition, elemental reference cache
- Modified `formation_energy_eV_per_atom()` in `featurizers.py` → calls M3GNet with Miedema fallback on timeout/error
- New source label `m3gnet_dft` rendered as violet chip in property dashboard
- Verification scorecard: Mg₂Si ≈ -0.13 eV/atom (MP truth: -0.129), Al₃Mg₂ ≈ -0.02, etc.

**Risks & mitigations:**
- Model is 600MB, first load ~30s → preload at startup in a background thread
- Per-prediction latency ~1-2s → could slow the UI; mitigate with timeout (3s) + Miedema fallback
- Structure-building from arbitrary composition is approximate (random FCC/BCC supercell)

**Success criteria:** Mg₂Si and 3 other Materials-Project-known intermetallics predict within ±30 meV/atom of the database value.

---

### Phase B — Non-ferrous yield strength models (Weeks 3-4)

**Goal:** Remove the "Fe ≥ 50% gate" from yield strength prediction. Train separate RF models for:
- **Aluminum alloys** (target: any Al ≥ 80%)
- **Titanium alloys** (target: any Ti ≥ 70%)
- **Nickel-base superalloys** (target: any Ni ≥ 50%)

**Datasets:**
- Al: hand-curate from NIMS MatNavi + MatWeb published values for 2xxx/5xxx/6xxx/7xxx series (~150-200 alloys)
- Ti: NIST Atom Probe data + literature scrapes (~80-100 alloys)
- Ni: superalloy databases (Inconel/Hastelloy series, ~60-80 alloys)
- Where curated data is sparse, augment with empirical solid-solution strengthening + precipitation hardening formulas

**Deliverables:**
- `apps/api/ml/training.py` — new functions: `train_aluminum_ys()`, `train_titanium_ys()`, `train_nickel_ys()`
- `models/aluminum_ys_rf.pkl`, `models/titanium_ys_rf.pkl`, `models/nickel_ys_rf.pkl`
- Routing in `yield_strength_MPa()` to pick the right model based on majority element
- Source chip per material family: `RF/Al`, `RF/Ti`, `RF/Ni`, `RF/Steels`

**Risks:** Public datasets are smaller and noisier than `matbench_steels`. Mitigate with conservative uncertainty bands + explicit "limited training data" warnings in the UI.

**Success criteria:** CV MAE < 50 MPa on each subset; can predict 6061-T6, Ti-6-4 annealed, Inconel 718 within ±15% of nominal data sheet values.

---

### Phase C — Hardness, fatigue, corrosion proxies (Weeks 5-6)

**Goal:** Add three new property panels that engineers care about: hardness, fatigue limit, corrosion rate (qualitative).

**Approach:**
- **Hardness (HV)**: empirical YS/HV ratio per family (HV ≈ YS/2.9 for steels, HV ≈ YS/2.5 for Al, etc.) + curated data RF where available
- **Fatigue endurance limit (σ_e)**: empirical σ_e ≈ 0.5 × UTS for steels, 0.4 × UTS for Al, gated; long-term replace with ML once data is collected
- **Corrosion rate** (qualitative): rules based on free corrosion potential vs SHE, passivating elements (Cr, Ni, Mo, Al, Ti), and pH-Eh diagram zones; output: "Excellent / Good / Fair / Poor" + `mm/year` order of magnitude

**Deliverables:**
- `apps/api/ml/secondary_properties.py` — hardness, fatigue, corrosion functions
- New radar axes in `PropertyDashboard`
- Manufacturability panel updates: add "Hardness range" hint
- Source chip: `empirical_ratio`, `electrochemistry_rules`

**Success criteria:** 304SS Hv ≈ 200, 4140 Hv ≈ 285, 6061-T6 Hv ≈ 95, Ti-6-4 Hv ≈ 340 — all within ±15%.

---

### Phase D — Validation case studies (Weeks 7-8)

**Goal:** Three end-to-end published case studies that prove LeilMat works. These become sales material AND scientific credibility.

**Cases:**

1. **Aerospace Ti orthopaedic implant** — design a Ti-Al-V-Mo-Nb alloy targeting (YS > 800 MPa, density < 4.7, corrosion ≥ "Good"). Compare LeilMat's top Pareto candidates to Ti-6-4, Ti-6-4 ELI, Ti-6Al-7Nb published values.

2. **Automotive Al-Cu-Li for stringers** — design a 2xxx-Li alloy targeting (YS > 450, density < 2.7, weldability ≥ 70). Compare to 2099 and 2050 published data.

3. **Additive-manufactured Ni superalloy for turbine blade** — design a Ni-Cr-Co-Mo-Al-Ti alloy targeting (YS > 1000 at 25°C, manufacturability ≥ 50 for AM scoring). Compare to Inconel 718, Inconel 738, Mar-M-247.

**Deliverables:**
- `case_studies/` directory with three notebooks documenting each run
- Markdown writeup per case (problem → search → result → comparison to literature)
- PDF report export functionality (uses LLM to summarize the session)
- Optional: submit one case as a workshop paper

**Success criteria:** For each case, ≥ 1 of LeilMat's top-5 Pareto candidates lies within 10% of a published alloy's properties OR proposes a defensible variant.

---

### Phase E — Auth + persistence + share links (Weeks 9-10)

**Goal:** Make LeilMat shippable to real users. First paying customer-ready.

**Deliverables:**
- **Auth**: NextAuth.js with GitHub + Email magic link providers
- **Persistence**: wire the existing `DesignSession`/`SavedComposition`/`ChatMessage` ORM models in `apps/api/data/models.py`. Sessions auto-save on every action.
- **Share links**: `/share/<session-id>` — public read-only view of a session (composition + Pareto results + chat history, no editing). UTM tracking for marketing.
- **PDF report export**: generates a one-page summary of the session using DeepSeek (composition + properties + manufacturability + AI commentary) — uses ReportLab or WeasyPrint
- Rate limiting (slowapi) + basic error tracking (Sentry free tier)

**Success criteria:** A new user can sign up, run a session, share a link with a colleague, and the colleague can view the session without an account.

---

### Phase F — Domain expert pilots (Weeks 11-12)

**Goal:** Validate with real users in three target verticals.

**Targets:**
- 1 university materials lab (academic credibility)
- 1 aerospace or automotive R&D group (industrial credibility)
- 1 additive-manufacturing startup (modern target market)

**Pilot structure:**
- 30-min onboarding call → user runs 3-5 sessions over 2 weeks → 30-min debrief
- Structured feedback: what scientific predictions did they trust? what UX worked/didn't? what feature would they pay for?
- Track: time-to-first-meaningful-result, predictions accepted vs rejected, NPS

**Deliverables:**
- 3 pilot reports
- Feature backlog informed by real user feedback
- Decision point: continue solo / raise pre-seed / partner with a lab

**Success criteria:** At least 1 of 3 pilots says "I would pay $X/mo for this" with a concrete X.

---

## Out of scope for these 12 weeks

- Ceramics, polymers, composites (deferred to months 13-18+)
- Multi-user collaboration / real-time editing
- ML model retraining on user-uploaded data (regulatory complications)
- Mobile / tablet UI
- Crystallographic structure prediction
- Synthesis route recommendation

---

## How we'll know we won

By end of week 12, LeilMat should:
- Predict yield strength for **steels, Al, Ti, and Ni** alloys with published-data accuracy
- Show DFT-grade formation energy via M3GNet
- Render hardness, fatigue, corrosion alongside the existing properties
- Have **three published case studies** verifiable against real alloys
- Be **deployable** with auth + persistence + sharing
- Have **3 pilot users** willing to keep using it

That's a defensible Series A pitch: "We are the AI-native canvas for metallic alloy design, with validated predictions across the 4 dominant metal families, deployed with X pilot users."

---

## Sequencing & dependencies

```
A (M3GNet) ──┬──► B (Non-Fe YS) ──► C (Hardness/Fatigue/Corr) ──► D (Validation)
              │                                                       │
              └────────────────────────────────────────────────────────┴──► E (Productize) ──► F (Pilots)
```

A unblocks more honest predictions everywhere.
B and C broaden coverage.
D requires A+B+C done.
E is largely independent infrastructure work — can be parallelized with C/D.
F requires E.

We start with **A (M3GNet)** today.
