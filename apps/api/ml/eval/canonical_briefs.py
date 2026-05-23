"""
Canonical inverse-design briefs (Sprint 7 validation fixtures).

Each brief is a self-contained engineering scenario with:

* A composition search space (which elements are allowed).
* A list of weighted objectives (what to optimise for).
* Hard constraints (OOD-validity, CI tolerance, phase rules).
* An optional temper to evaluate at.
* The list of alloys an experienced metallurgist would *expect* to see
  in the top-3 candidates.

These briefs serve as both regression tests AND documentation of "what
the tool should be good at".
"""
from __future__ import annotations

from apps.api.ml.inverse_briefs import (
    DesignBrief, EngineeringObjective,
    OODConstraint, CIWidthConstraint, PhaseConstraint,
)


CANONICAL_BRIEFS = [
    # ─────────────────────────────────────────────────────────────────────
    # 1. Aerospace Al wing skin: lightweight, strong, in-domain.
    # ─────────────────────────────────────────────────────────────────────
    DesignBrief(
        name="Aerospace Al wing skin",
        elements=["Al", "Cu", "Mg", "Zn", "Si", "Mn"],
        objectives=[
            EngineeringObjective("density_g_cm3",      "minimize", max_val=3.0, weight=0.2),
            EngineeringObjective("yield_strength_MPa", "maximize", min_val=350, weight=0.6),
            EngineeringObjective("elastic_modulus_GPa","maximize", min_val=70,  weight=0.2),
        ],
        constraints=[
            OODConstraint(),
            CIWidthConstraint(property="yield_strength_MPa", max_half_width=200),
        ],
        temper="T651",
        n_candidates=8, n_iterations=2, n_init=10, batch_size=3,
        element_bounds={"Al": (5.0, 10.0)},      # majority Al
    ),

    # ─────────────────────────────────────────────────────────────────────
    # 2. Ti orthopaedic implant: biocompatible, modest strength, low Young's
    #    modulus (close to bone), no V/Al cytotoxicity.
    # ─────────────────────────────────────────────────────────────────────
    DesignBrief(
        name="Ti orthopaedic implant",
        elements=["Ti", "Nb", "Zr", "Ta", "Mo", "Sn"],   # all biocompatible
        objectives=[
            EngineeringObjective("yield_strength_MPa", "maximize", min_val=600, weight=0.5),
            EngineeringObjective("elastic_modulus_GPa","minimize", max_val=120, weight=0.5),
        ],
        constraints=[
            OODConstraint(),
            CIWidthConstraint(property="yield_strength_MPa", max_half_width=200),
        ],
        temper="STA",
        n_candidates=8, n_iterations=2, n_init=10, batch_size=3,
        element_bounds={"Ti": (4.0, 10.0)},
    ),

    # ─────────────────────────────────────────────────────────────────────
    # 3. Ni-base turbine disc: high-T strength, dense γ', no σ-phase.
    # ─────────────────────────────────────────────────────────────────────
    DesignBrief(
        name="Ni-base turbine disc",
        elements=["Ni", "Cr", "Co", "Mo", "Al", "Ti"],
        objectives=[
            EngineeringObjective("yield_strength_MPa", "maximize", min_val=900, weight=0.7),
            EngineeringObjective("density_g_cm3",      "minimize", max_val=9.0, weight=0.3),
        ],
        constraints=[
            OODConstraint(),
            CIWidthConstraint(property="yield_strength_MPa", max_half_width=300),
        ],
        temper="Aged",
        n_candidates=8, n_iterations=2, n_init=10, batch_size=3,
        element_bounds={"Ni": (5.0, 10.0)},
    ),

    # ─────────────────────────────────────────────────────────────────────
    # 4. Low-cost structural Fe alloy: cheap, strong enough, ductile.
    # ─────────────────────────────────────────────────────────────────────
    DesignBrief(
        name="Low-cost structural steel",
        elements=["Fe", "C", "Mn", "Si", "Cr", "Ni"],
        objectives=[
            EngineeringObjective("yield_strength_MPa", "maximize", min_val=400, weight=0.5),
            EngineeringObjective("density_g_cm3",      "target",    min_val=7.7, max_val=8.1, weight=0.2),
            EngineeringObjective("elastic_modulus_GPa","maximize", min_val=180, weight=0.3),
        ],
        constraints=[
            OODConstraint(),
            CIWidthConstraint(property="yield_strength_MPa", max_half_width=250),
        ],
        temper="Q&T",
        n_candidates=8, n_iterations=2, n_init=10, batch_size=3,
        element_bounds={"Fe": (5.0, 10.0)},
    ),

    # ─────────────────────────────────────────────────────────────────────
    # 5. Marine 5xxx Al: lightweight, modest strength, annealed-only.
    #    (Corrosion is captured indirectly by maximising Mg / Mn while
    #    excluding Cu and Zn from the search space.)
    # ─────────────────────────────────────────────────────────────────────
    DesignBrief(
        name="Marine Al 5xxx",
        elements=["Al", "Mg", "Mn", "Cr", "Si"],
        objectives=[
            EngineeringObjective("yield_strength_MPa", "maximize", min_val=160, weight=0.5),
            EngineeringObjective("density_g_cm3",      "minimize", max_val=3.0, weight=0.3),
            EngineeringObjective("elastic_modulus_GPa","maximize", min_val=65,  weight=0.2),
        ],
        constraints=[
            OODConstraint(),
        ],
        temper="O",
        n_candidates=8, n_iterations=2, n_init=10, batch_size=3,
        element_bounds={"Al": (12.0, 20.0)},   # high bias keeps Al > 85 % in random init
    ),
]


# Per-brief: ranked list of family/temper names the metallurgist expects to see
# near the top.  We don't insist on exact composition matches (BoTorch may
# propose novel chemistries) — only that the *family* and *temper class* are
# right.
EXPECTED_RESULT_FAMILIES = {
    "Aerospace Al wing skin": {
        "family": "aluminum",
        "temper_class": ["T6", "T651", "T8", "T87"],   # heat-treatable peak-aged
        "expected_ys_min": 300,
        "expected_density_max": 3.0,
    },
    "Ti orthopaedic implant": {
        "family": "titanium",
        "temper_class": ["STA", "Annealed"],
        "expected_ys_min": 400,
        "expected_modulus_max": 120,
    },
    "Ni-base turbine disc": {
        "family": "nickel",
        "temper_class": ["Aged"],
        "expected_ys_min": 700,
    },
    "Low-cost structural steel": {
        "family": "general_steel",
        "temper_class": ["Q&T", "Normalised", "Annealed"],
        "expected_ys_min": 250,
        "expected_density_range": (7.5, 8.2),
    },
    "Marine Al 5xxx": {
        "family": "aluminum",
        "temper_class": ["O", "H32", "H116", "H321"],
        "expected_density_max": 3.0,
    },
}
