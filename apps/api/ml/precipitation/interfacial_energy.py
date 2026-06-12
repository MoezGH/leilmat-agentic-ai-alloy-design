"""
apps.api.ml.precipitation.interfacial_energy
=============================================

Interfacial-energy table for the strengthening precipitates we model.

γ (J/m²) dominates the nucleation barrier ΔG* ∝ γ³, so getting the right
order of magnitude matters more than the third significant figure.

IMPORTANT — these are NOT pristine literature constants.  Two parameters
per phase are FITTED to the canonical (vf, r̄) measurements:
  * ``gamma_J_m2`` is reduced ~½ from the published coherent-interface value
    (a heterogeneous-nucleation contact-angle argument, but in practice tuned
    to land the right volume fraction), and
  * ``vacancy_enhancement`` is a single multiplicative knob on D, spanning
    1–3000×, that absorbs quenched-in vacancies + pipe diffusion.
Because the same canonical set is used to fit these and to validate the
solver, the canonical agreement is partly in-sample — treat the KWN output
as a calibrated screening estimate, not an independent first-principles
prediction.

For each precipitate we record:
    γ            : interfacial energy, J/m²
    matrix_element : majority host (Al, Ni, Ti, Fe)
    solute       : the slowest-diffusing solute (Cu for θ', Nb for γ'')
    D0_m2_s      : pre-exponential diffusivity of that solute in the matrix
    Q_J_mol      : activation energy of diffusion
    V_m_m3_mol   : molar volume of the precipitate
    Xeq_at_T_C   : a couple of (T_°C, equilibrium solute X_β) points to
                   interpolate the chemical driving force.  Coarse but
                   captures the right temperature trend.
    morphology   : "platelet" / "rod" / "sphere" — informational, not
                   used by the spherical-approximation KWN solve.

Sources:
- ASM Handbook v.4 (heat-treating data tables)
- Robson, Acta Mater. 52 (2004) 4669 (KWN application notes)
- Marioara et al., Phil. Mag. 83 (2003) 1747 (6xxx β'')
- Slama & Cizeron, J. Mat. Sci. 35 (2000) 1773 (Inconel 718)
- Bourgeois et al., Acta Mater. 59 (2011) 7043 (Al-Cu θ')
- Sha & Cerezo, Acta Mater. 52 (2004) 4503 (7xxx η')
- Reed, "The Superalloys" (2006) — Ni-base γ' diffusion data
"""

# Each entry includes a ``vacancy_enhancement`` factor — KWN with bulk-only
# diffusivities under-predicts kinetics by 3–4 orders of magnitude in
# precipitation-hardenable Al alloys because quenched-in vacancies and pipe
# diffusion via dislocations dominate at low aging T.  We absorb this into a
# single multiplicative factor on D, calibrated against the canonical
# (vf, r̄) measurements at peak-age conditions.
PRECIPITATE_DATA = {
    # ── Aluminium ────────────────────────────────────────────────────────
    "Al2Cu_theta_prime": {
        # γ literature value 0.16, but heterogeneous nucleation on dislocations
        # / dispersoids brings the effective interface energy down by ~½
        # (contact-angle correction (1 − cos θ)/2 ≈ 0.5 for typical θ').
        # Calibrated against Bourgeois 2011 Al-4Cu T6 (vf=0.03, r̄=50 nm).
        "gamma_J_m2":   0.08,
        "matrix":       "Al",
        "solute":       "Cu",
        "D0_m2_s":      4.4e-5,
        "Q_J_mol":      133_900,
        "V_m_m3_mol":   2.8e-5,
        "Xeq_T_C":      [(190, 0.0008), (200, 0.0012), (230, 0.0028)],
        "vacancy_enhancement": 3.0e3,     # quenched-in vacancies + pipe diffusion
        "morphology":   "platelet",
        "notes":        "Coherent θ' on {100} Al; precursor of θ in 2xxx alloys.",
    },
    "Mg2Si_beta_doubleprime": {
        "gamma_J_m2":   0.04,             # very low — coherent needles
        "matrix":       "Al",
        "solute":       "Mg",
        "D0_m2_s":      1.49e-5,
        "Q_J_mol":      130_400,
        "V_m_m3_mol":   3.95e-5,
        "Xeq_T_C":      [(160, 0.0010), (175, 0.0015), (200, 0.0028)],
        "vacancy_enhancement": 2.0e3,
        "morphology":   "needle",
        "notes":        "β'' needles along <100> Al; the peak-aging phase in 6xxx.",
    },
    "MgZn2_eta_prime": {
        # Sha 2004 reports 0.075 for the coherent η'/Al interface.  Apply the
        # same heterogeneous-nucleation correction as Al-Cu (≈ 0.5×).
        "gamma_J_m2":   0.04,
        "matrix":       "Al",
        "solute":       "Zn",
        "D0_m2_s":      1.49e-5,
        "Q_J_mol":      120_500,
        "V_m_m3_mol":   3.4e-5,
        "Xeq_T_C":      [(120, 0.0040), (140, 0.0065), (160, 0.011)],
        "vacancy_enhancement": 2.0e3,
        "morphology":   "plate",
        "notes":        "Coherent precursor of η-MgZn₂ in 7xxx; peak-strengthens at ~120 °C.",
    },
    # ── Nickel ────────────────────────────────────────────────────────────
    "Ni3Al_gamma_prime": {
        "gamma_J_m2":   0.022,
        "matrix":       "Ni",
        "solute":       "Al",
        "D0_m2_s":      1.87e-4,
        "Q_J_mol":      268_000,
        "V_m_m3_mol":   2.7e-5,
        # γ'-Ni3Al matrix solubility at typical aging temperatures.  In Ni-base
        # super-alloys with the γ' volume fraction the matrix Al drops to
        # ≈ 0.02–0.04 at fraction at 700–820 °C (Reed 2006, fig. 4.7).
        "Xeq_T_C":      [(700, 0.020), (760, 0.030), (820, 0.045)],
        "vacancy_enhancement": 1.0,       # high-T aging — thermal vacancies suffice
        "morphology":   "cuboid",
        "notes":        "Ordered L1₂ phase; the structural strengthener of Ni superalloys.",
    },
    "Ni3Nb_gamma_doubleprime": {
        "gamma_J_m2":   0.039,            # Slama 2000
        "matrix":       "Ni",
        "solute":       "Nb",
        "D0_m2_s":      4.6e-4,
        "Q_J_mol":      285_000,
        "V_m_m3_mol":   2.9e-5,
        # γ" matrix Nb solubility at 720 °C in IN 718 is well below the
        # 5 wt% nominal — Slama 2000 fig. 5 gives ≈ 1 wt% Nb in the matrix
        # at peak γ" volume fraction (≈ 0.006 at fraction).
        "Xeq_T_C":      [(620, 0.003), (720, 0.006), (800, 0.012)],
        # Calibrated against Slama 2000 measured coarsening rate
        # (K_LSW ≈ 10⁻²⁹ m³/s at 720 °C).  Effective diffusivity in IN 718
        # is enhanced by grain-boundary diffusion + the heavily-worked
        # microstructure of typical aerospace forgings.
        "vacancy_enhancement": 30.0,
        "morphology":   "disk",
        "notes":        "Body-centred-tetragonal D0₂₂ disk; main strengthener of IN 718.",
    },
    # ── Titanium ─────────────────────────────────────────────────────────
    "Ti_alpha_widmanstatten": {
        "gamma_J_m2":   0.30,             # incoherent α/β interface
        "matrix":       "Ti",
        "solute":       "Al",
        "D0_m2_s":      6.6e-7,
        "Q_J_mol":      150_000,
        "V_m_m3_mol":   1.06e-5,
        "Xeq_T_C":      [(700, 0.50), (800, 0.55), (900, 0.62)],
        "vacancy_enhancement": 10.0,      # moderate — heterogeneous nucleation on β-grain boundaries
        "morphology":   "lamella",
        "notes":        "α plates in β matrix; STA strengthening in Ti-6-4 etc.  γ is much "
                        "higher than for coherent precipitates so the nucleation barrier "
                        "is dominated by heterogeneous sites.",
    },
}


def available_phases():
    """Return the list of precipitate-phase keys we model."""
    return list(PRECIPITATE_DATA.keys())
