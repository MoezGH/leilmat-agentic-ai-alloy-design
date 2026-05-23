"""
OPTIMADE-compatible connector for Materials Project, AFLOW, and OQMD.
Provides a unified interface to query alloy properties from open databases.
"""
from __future__ import annotations

from typing import Any
import httpx

# Public OPTIMADE base URLs
PROVIDERS = {
    "mp": "https://optimade.materialsproject.org",
    "aflow": "https://aflow.org/API/optimade/",
    "oqmd": "https://oqmd.org/optimade",
}


async def query_by_elements(elements: list[str], provider: str = "mp") -> list[dict[str, Any]]:
    """
    Query the OPTIMADE API for structures containing the given elements.
    Returns a list of structure entries with their properties.
    """
    base = PROVIDERS.get(provider, PROVIDERS["mp"])
    formula_filter = " AND ".join(f'elements HAS "{el}"' for el in elements)
    params = {
        "filter": formula_filter,
        "response_fields": "chemical_formula_reduced,elements,nelements,density,formation_energy_per_atom",
        "page_limit": 50,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"{base}/v1/structures", params=params)
        resp.raise_for_status()
        data = resp.json()
    return data.get("data", [])


async def lookup_composition(formula: str, provider: str = "mp") -> dict[str, Any] | None:
    """
    Look up a specific reduced formula in a database.
    Returns the best matching entry or None.
    """
    base = PROVIDERS.get(provider, PROVIDERS["mp"])
    params = {
        "filter": f'chemical_formula_reduced = "{formula}"',
        "response_fields": "chemical_formula_reduced,elements,density,formation_energy_per_atom,lattice_vectors",
        "page_limit": 1,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"{base}/v1/structures", params=params)
        if resp.status_code != 200:
            return None
        data = resp.json()
    entries = data.get("data", [])
    return entries[0] if entries else None


async def get_phase_stability(elements: list[str]) -> dict[str, Any]:
    """
    Fetch formation energies for all binary/ternary combinations of elements
    to support phase diagram construction.
    """
    entries = await query_by_elements(elements, provider="mp")
    return {
        "elements": elements,
        "entries": [
            {
                "formula": e.get("attributes", {}).get("chemical_formula_reduced"),
                "formation_energy": e.get("attributes", {}).get("formation_energy_per_atom"),
                "density": e.get("attributes", {}).get("density"),
            }
            for e in entries
        ],
    }
