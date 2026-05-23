"""
Sprint 8 — hierarchical cost endpoints.

POST /api/cost/compute   — full cost breakdown for a composition
GET  /api/cost/options   — vocabulary for form / cert / heat-treatment dropdowns
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()


class CostRequest(BaseModel):
    composition: dict
    form:        str  = Field("plate", description="ingot, plate, bar, sheet, wire, powder, …")
    cert:        str  = Field("commercial",
                              description="commercial, ASTM, ASME, AMS, MIL-DTL, NACE, …")
    ht:          str | None = Field(None, description="Heat-treatment code or temper")
    lot_kg:      float= Field(100.0, gt=0,
                              description="Order quantity in kg (smaller lots amortise "
                                          "less of the supplier-minimum overhead)")


@router.post("/compute")
async def compute(req: CostRequest):
    """Return a full hierarchical cost breakdown for the given composition.

    The reply mirrors :func:`apps.api.ml.cost.compute_cost` 1-for-1:

    ```
    {
      "USD_per_kg":                12.40,
      "USD_per_kg_no_overhead":    11.50,
      "breakdown": {
        "spot_price_USD_per_kg":   3.50,
        "form_factor_multiplier":  1.20,
        "certification_multiplier":1.75,
        "heat_treatment_class":    "T6",
        "heat_treatment_multiplier":1.20,
        "supplier_overhead_USD":   1000,
        "supplier_overhead_per_kg":2.00,
        "lot_kg":                  500
      },
      "family":          "aluminum_aerospace",
      "form":            "plate",
      "certification":   "AMS",
      "contributions":   [...],
      "source":          "cost_v2_hierarchical",
      "calibration":     "spot_prices_2025_q2",
      "provenance":      {...}
    }
    ```
    """
    try:
        from apps.api.ml.cost import compute_cost
        return compute_cost(
            composition=req.composition,
            form=req.form, cert=req.cert, ht=req.ht, lot_kg=req.lot_kg,
        )
    except Exception as exc:
        raise HTTPException(500, f"cost computation failed: {exc}")


@router.get("/options")
async def options():
    """Vocabularies for the UI dropdowns (forms / certifications / treatments)."""
    from apps.api.ml.cost import available_options
    return available_options()
