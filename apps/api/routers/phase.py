"""
GET /api/phase/diagram?elements=Al,Mg,Si  — return phase diagram data
GET /api/phase/stability?formula=Al2Mg    — return phase stability for a formula
GET /api/phase/hull?composition=Al:50,Ti:50&formation_energy=-0.12
                                          — distance above convex hull (eV/atom)
"""
from fastapi import APIRouter, Query, HTTPException
from typing import Any

router = APIRouter()


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
