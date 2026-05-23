"""
Model-status health endpoint.

The frontend polls `GET /api/health/models` while the canvas is loading so it
can show a small "loading…" indicator on the formation-energy property card
during M3GNet's ~7-second cold start. Without this, the first prediction
silently falls back to the Miedema heuristic and the user sees stale data.

Response schema:
    {
      "m3gnet": {
        "status": "not_started" | "loading" | "loaded" | "failed",
        "elapsed_load_s": 0.7,
        "error": null
      },
      "calibrator": {
        "status": "not_started" | "fitting" | "fitted" | "failed",
        "elapsed_fit_s": 1.8,
        "n_calibration": 13,
        "q_eV_per_atom": 0.31,
        "error": null
      },
      "yield_strength": {
        "aluminum": {"present": true, "n_training": 29, "cv_mae_MPa": 58, "has_conformal": true},
        "titanium": {...},
        "nickel":   {...},
        "steel":    {...}
      }
    }
"""
from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

from fastapi import APIRouter

router = APIRouter()

MODELS_DIR = Path(__file__).parent.parent.parent.parent / "models"

_YS_FILES = {
    "aluminum": "aluminum_ys_rf.pkl",
    "titanium": "titanium_ys_rf.pkl",
    "nickel":   "nickel_ys_rf.pkl",
    "steel":    "yield_strength_rf.pkl",
}


def _ys_status() -> dict[str, dict[str, Any]]:
    """Cheap probe of the four YS model bundles — just reads metadata, not
    the full pickle (we don't want this to thrash GC on every poll)."""
    out: dict[str, dict[str, Any]] = {}
    for family, filename in _YS_FILES.items():
        path = MODELS_DIR / filename
        if not path.exists():
            out[family] = {"present": False, "error": "model file missing — run training"}
            continue
        try:
            with open(path, "rb") as f:
                bundle = pickle.load(f)
            out[family] = {
                "present":        True,
                "n_training":     bundle.get("n_samples"),
                "cv_mae_MPa":     round(bundle.get("cv_mae_MPa") or 0, 1),
                "y_min":          bundle.get("y_min"),
                "y_max":          bundle.get("y_max"),
                "domain":         bundle.get("domain"),
                "has_ood":        bool(bundle.get("ood")),
                "has_conformal":  bool(bundle.get("conformal")),
                "size_kB":        round(path.stat().st_size / 1024, 1),
            }
        except Exception as exc:
            out[family] = {"present": True, "error": f"unreadable: {exc}"}
    return out


@router.get("/models")
def models_health() -> dict[str, Any]:
    """Live state of the prediction stack — used by the frontend to show
    a loading indicator on formation-energy predictions during M3GNet warm-up."""
    from apps.api.ml.m3gnet_predictor import health_snapshot
    return {
        **health_snapshot(),
        "yield_strength": _ys_status(),
    }
