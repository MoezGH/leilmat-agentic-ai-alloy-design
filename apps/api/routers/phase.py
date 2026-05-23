"""
GET /api/phase/equilibrium?composition=Al:97,Mg:2,Si:1&T_C=530
                                          — CALPHAD equilibrium phase assemblage
GET /api/phase/equilibrium/coverage       — list registered TDB databases
GET /api/phase/diagram?elements=Al,Mg,Si  — return phase diagram data
GET /api/phase/stability?formula=Al2Mg    — return phase stability for a formula
GET /api/phase/hull?composition=Al:50,Ti:50&formation_energy=-0.12
                                          — distance above convex hull (eV/atom)
"""
from fastapi import APIRouter, Query, HTTPException
from typing import Any

router = APIRouter()


# ── CALPHAD equilibrium endpoints (Sprint 1) ──────────────────────────────────

@router.get("/equilibrium")
async def phase_equilibrium(
    composition: str = Query(
        ...,
        description=(
            "Composition as 'Element:wt%' pairs, e.g. Al:97,Mg:2,Si:1. "
            "Values are weight percent (they will be normalised to sum=1)."
        ),
    ),
    T_C: float = Query(
        ...,
        description="Temperature in Celsius. Converted to Kelvin internally.",
        ge=-273.15,
    ),
):
    """Return the CALPHAD equilibrium phase assemblage at the given temperature.

    Uses pycalphad with the best available open-source TDB for the composition's
    chemical system.  Returns ``value: null`` (with ``source: calphad_no_tdb``)
    when no registered TDB covers the system.

    Response schema
    ---------------
    ```json
    {
      "phases":      {"FCC_A1": 0.99, "MG2SI": 0.01},
      "phase_comps": {"FCC_A1": {"Al": 0.985, "Mg": 0.012, "Si": 0.003}},
      "T_K":         803.15,
      "T_C":         530.0,
      "source":      "calphad_pycalphad",
      "tdb":         "cost507_al_alloys.tdb",
      "chemsys":     "Al-Mg-Si",
      "calibration": "deterministic",
      "value":       {"FCC_A1": 0.99, "MG2SI": 0.01},
      "error":       null
    }
    ```
    """
    # Parse composition string: "Al:97,Mg:2,Si:1"
    comp_dict: dict[str, float] = {}
    try:
        for pair in composition.split(","):
            pair = pair.strip()
            if not pair:
                continue
            el, wt = pair.split(":")
            comp_dict[el.strip()] = float(wt.strip())
    except Exception:
        raise HTTPException(
            400,
            "Invalid composition format. Use 'El:value,El:value', e.g. Al:97,Mg:2,Si:1",
        )

    if not comp_dict:
        raise HTTPException(400, "Empty composition")

    T_K = T_C + 273.15

    try:
        from apps.api.ml.calphad.equilibrium import phase_assemblage
        result = await phase_assemblage(comp_dict, T_K)
    except Exception as exc:
        raise HTTPException(500, f"CALPHAD calculation failed: {exc}")

    return {**result, "T_C": T_C}


@router.get("/equilibrium/coverage")
async def calphad_coverage():
    """List all registered CALPHAD TDB databases with their element coverage."""
    from apps.api.ml.calphad.databases import list_coverage
    return {"databases": list_coverage()}


# ── Sprint 2: Scheil + TTT endpoints ──────────────────────────────────────────

@router.get("/scheil")
async def scheil_endpoint(
    composition: str = Query(
        ...,
        description="Composition as 'El:wt%' pairs, e.g. Al:92.4,Si:7,Mg:0.3,Fe:0.2,Cu:0.1",
    ),
    T_start_C: float | None = Query(
        None, description="Starting temperature in Celsius. Defaults to ~150 K above liquidus.",
    ),
):
    """Run Scheil-Gulliver non-equilibrium solidification.

    Returns the freezing-range curve, mushy-zone width, terminal liquid
    composition and ad-hoc hot-tearing index.  Use this for casting work
    where solute back-diffusion is negligible (most engineering castings).

    Typical elapsed time: 10–60 s depending on the number of components.
    """
    comp_wt: dict[str, float] = {}
    try:
        for pair in composition.split(","):
            pair = pair.strip()
            if not pair:
                continue
            el, wt = pair.split(":")
            comp_wt[el.strip()] = float(wt.strip())
    except Exception:
        raise HTTPException(400, "Invalid composition format. Use 'El:wt%,El:wt%'.")
    if not comp_wt:
        raise HTTPException(400, "Empty composition")

    # Convert wt% to mole fractions for Scheil
    from apps.api.ml.calphad.eval.solidification_runner import _wt_to_mol
    comp_mol = _wt_to_mol(comp_wt)
    T_start_K = (T_start_C + 273.15) if T_start_C is not None else None

    from apps.api.ml.calphad.scheil import scheil_solidification
    result = await scheil_solidification(comp_mol, T_start_K)
    # Mirror the API contract: report both K and °C
    if result.get("liquidus_K"):
        result["liquidus_C"] = round(result["liquidus_K"] - 273.15, 2)
    if result.get("solidus_K"):
        result["solidus_C"] = round(result["solidus_K"] - 273.15, 2)
    return result


@router.get("/ttt")
async def ttt_endpoint(
    composition: str = Query(
        ...,
        description="Composition as 'El:wt%' pairs for a steel, e.g. Fe:96.7,C:0.4,Cr:1.0,Mo:0.2,Mn:0.85,Si:0.25",
    ),
    austenite_grain_um: float = Query(
        15.0, description="Prior-austenite grain size in micrometres.", gt=0,
    ),
):
    """Compute Fe-C TTT/CCT diagram (Kirkaldy-Venugopalan + Andrews Ms).

    Returns the pearlite/bainite/ferrite nose locations on both the
    isothermal TTT diagram and a CCT-shifted variant, plus equilibrium
    transformation temperatures (Ae1, Ae3, Bs, Ms).

    Refuses non-steels (Fe < 80 %), cast irons (C > 1 %) and highly-alloyed
    steels (total alloying > 12 %) — outside the Kirkaldy-Venugopalan
    domain.
    """
    comp_wt: dict[str, float] = {}
    try:
        for pair in composition.split(","):
            pair = pair.strip()
            if not pair:
                continue
            el, wt = pair.split(":")
            comp_wt[el.strip()] = float(wt.strip())
    except Exception:
        raise HTTPException(400, "Invalid composition format. Use 'El:wt%,El:wt%'.")
    if not comp_wt:
        raise HTTPException(400, "Empty composition")

    from apps.api.ml.calphad.ttt import ttt_diagram
    return ttt_diagram(comp_wt, austenite_grain_um=austenite_grain_um)


@router.get("/diagram")
async def phase_diagram(elements: str = Query(..., description="Comma-separated elements, e.g. Al,Mg,Si")):
    """
    Returns phase diagram data for up to 3 elements.
    Uses pymatgen + Materials Project API to fetch formation energies,
    then builds the convex hull for the phase diagram.
    """
    el_list = [e.strip() for e in elements.split(",") if e.strip()]
    if len(el_list) < 2 or len(el_list) > 3:
        raise HTTPException(400, "Provide 2–3 elements for binary/ternary phase diagrams")

    try:
        data = await _build_phase_diagram(el_list)
        return data
    except Exception as exc:
        raise HTTPException(500, str(exc))


@router.get("/stability")
async def phase_stability(formula: str = Query(...)):
    """Returns phase stability information for a given formula from OPTIMADE."""
    try:
        from apps.api.data.optimade import lookup_composition
        entry = await lookup_composition(formula)
        if entry is None:
            return {"formula": formula, "found": False}
        attrs = entry.get("attributes", {})
        return {
            "formula": formula,
            "found": True,
            "formation_energy_eV_per_atom": attrs.get("formation_energy_per_atom"),
            "density_g_cm3": attrs.get("density"),
        }
    except Exception as exc:
        raise HTTPException(500, str(exc))


@router.get("/hull")
async def hull_distance(
    composition: str = Query(
        ...,
        description="Composition as 'Element:at%' pairs, e.g. Al:50,Ti:50",
    ),
    formation_energy: float = Query(
        ...,
        description="Predicted formation energy in eV/atom (from /api/predict)",
    ),
):
    """
    Returns the distance above the DFT convex hull (eV/atom) for a given
    composition and predicted formation energy.

    The hull is built from all Materials Project GGA entries in the relevant
    chemical system.  A value near 0 means thermodynamically stable; values
    > 100 meV/atom indicate likely decomposition into more stable phases.
    """
    try:
        comp_dict: dict[str, float] = {}
        for pair in composition.split(","):
            el, frac = pair.strip().split(":")
            comp_dict[el.strip()] = float(frac.strip())
    except Exception:
        raise HTTPException(400, "Invalid composition format. Use 'El:frac,El:frac', e.g. Al:50,Ti:50")

    if len(comp_dict) < 2:
        raise HTTPException(400, "Need at least 2 elements to query the hull")

    result = await _compute_hull_distance(comp_dict, formation_energy)
    return result


async def _compute_hull_distance(comp_dict: dict[str, float], formation_energy: float) -> dict[str, Any]:
    """Fetch phase diagram and compute e_above_hull for the given composition."""
    from apps.api.config import settings

    if not settings.mp_api_key:
        return {
            "e_above_hull": None,
            "stability":    "unknown",
            "error":        "MP_API_KEY not configured",
        }

    elements = list(comp_dict.keys())
    try:
        from mp_api.client import MPRester
        from pymatgen.analysis.phase_diagram import PhaseDiagram, PDEntry
        from pymatgen.core import Composition

        with MPRester(api_key=settings.mp_api_key) as mpr:
            entries = mpr.get_entries_in_chemsys(
                elements,
                additional_criteria={"thermo_types": ["GGA_GGA+U"]},
            )

        if not entries:
            return {
                "e_above_hull": None,
                "stability":    "unknown",
                "error":        "No entries returned from Materials Project",
            }

        pd   = PhaseDiagram(entries)
        comp = Composition(comp_dict)
        # PDEntry total energy = formation_energy_per_atom × n_atoms
        test_entry = PDEntry(comp, formation_energy * sum(comp.values()))
        e_hull = float(pd.get_e_above_hull(test_entry))

        if e_hull < 0.025:
            stability = "stable"
            note = "On or near the convex hull — thermodynamically stable or marginally metastable"
        elif e_hull < 0.100:
            stability = "metastable"
            note = (
                f"{e_hull * 1000:.0f} meV/atom above hull — metastable; "
                "may persist as a solid solution or with kinetic stabilisation"
            )
        else:
            stability = "unstable"
            note = (
                f"{e_hull * 1000:.0f} meV/atom above hull — thermodynamically unstable; "
                "expected to decompose into more stable phases"
            )

        return {
            "e_above_hull": round(e_hull, 4),
            "e_above_hull_meV": round(e_hull * 1000, 1),
            "stability":    stability,
            "note":         note,
            "elements":     elements,
            "source":       "mp_dft_convex_hull",
        }
    except Exception as exc:
        return {
            "e_above_hull": None,
            "stability":    "unknown",
            "error":        str(exc),
        }


async def _build_phase_diagram(elements: list[str]) -> dict[str, Any]:
    """
    Fetch formation energies from Materials Project and build a convex-hull
    phase diagram using pymatgen.
    """
    from apps.api.config import settings

    if not settings.mp_api_key:
        return {"elements": elements, "stable_phases": [], "error": "MP_API_KEY not configured"}

    try:
        from mp_api.client import MPRester
        from pymatgen.analysis.phase_diagram import PhaseDiagram
        from pymatgen.entries.computed_entries import ComputedEntry
        from pymatgen.core import Composition

        with MPRester(api_key=settings.mp_api_key) as mpr:
            # Fetch all entries in the chemsys (e.g. "Al-Mg-Si") — includes all sub-systems
            entries = mpr.get_entries_in_chemsys(elements, additional_criteria={"thermo_types": ["GGA_GGA+U"]})

        if not entries:
            return {"elements": elements, "stable_phases": [], "error": "No entries returned from MP"}

        pd = PhaseDiagram(entries)
        stable = [
            {
                "formula": e.composition.reduced_formula,
                "formation_energy": round(pd.get_form_energy_per_atom(e), 4),
            }
            for e in pd.stable_entries
        ]
        # Sort by formation energy ascending (most stable first), then drop pure elements duplicates
        stable.sort(key=lambda x: x["formation_energy"])
        return {"elements": elements, "stable_phases": stable, "n_entries": len(entries)}
    except Exception as exc:
        return {"elements": elements, "stable_phases": [], "error": str(exc)}
