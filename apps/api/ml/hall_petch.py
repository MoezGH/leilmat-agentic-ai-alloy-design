"""
apps.api.ml.hall_petch
======================

First-order Hall-Petch overlay coupling a *physical* mean grain size into the
yield-strength prediction.

Why a DIFFERENTIAL overlay (not σ₀ + k·d^-½ from scratch)?
---------------------------------------------------------
The yield-strength RandomForest is trained on real alloys whose grain sizes
were not recorded — its prediction reflects each family's *typical, as-tested*
(usually wrought) microstructure.  We therefore cannot cleanly decompose it
into a Hall-Petch friction stress σ₀ plus a grain term.  What we CAN do
honestly is treat the ML value as corresponding to a reference grain size
``D_REF_UM`` and apply the *change* in the Hall-Petch term relative to it:

    Δσ_y = K · ( d^(-1/2) − d_ref^(-1/2) )          [MPa, d in µm]

So at d = d_ref the ML value is unchanged; finer grains add strength, coarser
grains subtract it.  This is a screening-grade ``literature-correlation``
estimate, never a calibrated/validated coupling — see ``calibration`` in the
returned block.

Only ever called with a PHYSICAL grain size (µm), i.e. when the upstream Neper
/ SPPARKS sim was given a ``domain_um``.  Dimensionless sims never reach here.

K coefficients (MPa·µm^½) are k_y·10³ from the usual literature k_y in
MPa·m^½.  Ballpark, family-level values — individual alloys/tempers vary.
"""
from __future__ import annotations

# Hall-Petch slope by base-metal family, MPa·µm^(1/2).
# (k_y in MPa·m^(1/2) × 1e3, since d_m^(-1/2) = d_µm^(-1/2)·1e3.)
HALL_PETCH_K: dict[str, float] = {
    "Fe": 550.0,   # ferritic / mild-low-alloy steel, k_y ≈ 0.55 MPa·m^½ (Petch)
    "Al": 70.0,    # aluminium, k_y ≈ 0.07 MPa·m^½
    "Ti": 350.0,   # titanium (CP / α), k_y ≈ 0.35 MPa·m^½
    "Ni": 160.0,   # nickel, k_y ≈ 0.16 MPa·m^½
}

# Reference grain size the ML baseline is taken to represent (≈ ASTM 7, a
# typical wrought grain size).  The overlay is zero at this size.
D_REF_UM = 30.0

# Hall-Petch is a coarse/medium-grain relation; below ~1 µm the slope rolls
# over (inverse Hall-Petch) and above ~1 cm grains are meaningless here.
# Clamp the size that enters the formula so the overlay can't run away.
_D_MIN_UM = 1.0
_D_MAX_UM = 1.0e4


def hall_petch_delta_MPa(
    family_element: str,
    grain_size_um: float,
    d_ref_um: float = D_REF_UM,
) -> dict | None:
    """Differential Hall-Petch yield-strength adjustment for a physical grain size.

    Returns ``None`` when no family coefficient is available or the grain size
    is non-physical; otherwise a self-describing block with the signed
    ``delta_MPa`` and full provenance (honest ``calibration`` tag).
    """
    K = HALL_PETCH_K.get(family_element)
    if K is None or not grain_size_um or grain_size_um <= 0:
        return None

    d = min(max(float(grain_size_um), _D_MIN_UM), _D_MAX_UM)
    delta = K * (d ** -0.5 - d_ref_um ** -0.5)
    clamped = d != float(grain_size_um)

    return {
        "delta_MPa": round(delta, 1),
        "grain_size_um": round(float(grain_size_um), 2),
        "d_ref_um": d_ref_um,
        "k_y_MPa_sqrt_um": K,
        "family": family_element,
        "calibration": "literature-correlation",
        "note": (
            f"Differential Hall-Petch overlay: σ_y adjusted by "
            f"K·(d^-1/2 − d_ref^-1/2) relative to a {d_ref_um:g} µm reference "
            f"(K={K:g} MPa·µm^½, {family_element}-base, literature value)."
            + (" Grain size clamped to the Hall-Petch validity window."
               if clamped else "")
        ),
    }
