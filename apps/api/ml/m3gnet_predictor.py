"""
DFT-grade formation energy via M3GNet (Chen & Ong, Nat. Comput. Sci. 2022).

We use the `M3GNet-Eform-MP-2018.6.1` pretrained checkpoint which directly
outputs formation energy per atom for a given crystal structure.

Accuracy caveat: M3GNet's *published* MP-holdout MAE (~50 meV/atom) is for
relaxed ground-state structures.  Our pipeline feeds the model a single
random-substitution supercell (not a relaxed ground state), so the measured
MAE on our canonical reference set is far higher — ~225 meV/atom overall and
~312 meV/atom for ordered intermetallics (see ``docs/SCORECARD.md``).  Treat
the output as a screening-grade stability indicator, not a DFT substitute.

Workflow:
  1. Take an arbitrary alloy composition (atomic %)
  2. Build a representative ~32-atom supercell using the majority element's
     ground-state crystal lattice (FCC for Al/Cu/Ni, BCC for Fe/W/Mo/V/Cr,
     HCP for Mg/Ti/Zn/Zr). Randomly substitute atoms to match composition.
  3. Run M3GNet on the supercell
  4. Cache result keyed on a canonical composition string + seed

Limitations:
- A single random supercell is not the most-stable solid solution; we average
  N=3 random structures and report the mean ± std as uncertainty.
- For ordered intermetallics, the result is approximate (~150-300 meV/atom error).
- For solid solutions in the dilute limit, accuracy improves to ~50 meV/atom.
- The conformal ± band is fit on ~13 canonical intermetallics and is currently
  evaluated IN-SAMPLE (no held-out exchangeable set), so the advertised "90 %
  coverage" has no out-of-sample guarantee — treat the interval as indicative,
  not calibrated.  It is also homoscedastic (one band for all compositions).
- First model load is ~7s on CPU; subsequent predictions ~0.3s each.
"""
from __future__ import annotations

import functools
import hashlib
import threading
import time
import warnings
from typing import Any

import numpy as np


warnings.filterwarnings("ignore", message="The given NumPy array is not writable")
warnings.filterwarnings("ignore", category=UserWarning, module="matgl")

# ─────────────────────────────────────────────────────────────────────────
# Crystal-structure heuristics: ground-state lattice per pure element
# (engineering-relevant subset)
# ─────────────────────────────────────────────────────────────────────────

GROUND_STATE_LATTICE: dict[str, tuple[str, float]] = {
    # FCC (a₀ in Å)
    "Al": ("fcc", 4.05), "Cu": ("fcc", 3.61), "Ni": ("fcc", 3.52),
    "Au": ("fcc", 4.08), "Ag": ("fcc", 4.09), "Pt": ("fcc", 3.92),
    "Pd": ("fcc", 3.89), "Pb": ("fcc", 4.95), "Rh": ("fcc", 3.80),
    "Ir": ("fcc", 3.84), "Ca": ("fcc", 5.58),

    # BCC
    "Fe": ("bcc", 2.87), "Cr": ("bcc", 2.88), "V":  ("bcc", 3.03),
    "Mo": ("bcc", 3.15), "W":  ("bcc", 3.17), "Nb": ("bcc", 3.30),
    "Ta": ("bcc", 3.30), "Na": ("bcc", 4.23), "K":  ("bcc", 5.23),
    "Ba": ("bcc", 5.02), "Li": ("bcc", 3.49),

    # HCP — using simplified bulk; ase.build.bulk handles c/a automatically
    "Mg": ("hcp", 3.21), "Ti": ("hcp", 2.95), "Zn": ("hcp", 2.66),
    "Zr": ("hcp", 3.23), "Co": ("hcp", 2.51), "Be": ("hcp", 2.29),
    "Re": ("hcp", 2.76), "Sc": ("hcp", 3.31), "Y":  ("hcp", 3.65),

    # Diamond / covalent (Si, Ge)
    "Si": ("diamond", 5.43), "Ge": ("diamond", 5.66),

    # Misc (default fallback: FCC)
    "Mn": ("bcc", 8.91), "Sn": ("fcc", 4.59),
}

DEFAULT_LATTICE: tuple[str, float] = ("fcc", 4.0)


# ─────────────────────────────────────────────────────────────────────────
# Lazy model load (run in background thread on first use to avoid blocking)
# ─────────────────────────────────────────────────────────────────────────

_model_lock = threading.Lock()
_model = None
_model_load_failed = False
_model_load_status = "not_started"   # not_started | loading | loaded | failed
_model_load_elapsed_s: float | None = None
_model_load_error: str | None = None


def _load_model_blocking():
    global _model, _model_load_failed, _model_load_status, _model_load_elapsed_s, _model_load_error
    with _model_lock:
        if _model is not None or _model_load_failed:
            return _model
        _model_load_status = "loading"
        try:
            import matgl
            import torch
            # Seed torch + force deterministic algorithms so the same input
            # structure gives the same energy across Python processes. Without
            # this, the model can drift by ~30 meV/atom between runs due to
            # non-deterministic CPU BLAS ops in PyTorch's default config.
            torch.manual_seed(42)
            try:
                torch.use_deterministic_algorithms(True, warn_only=True)
            except Exception:
                pass

            print("[m3gnet] Loading M3GNet-Eform-MP-2018.6.1...")
            t0 = time.time()
            _model = matgl.load_model("M3GNet-Eform-MP-2018.6.1")
            # Put the model in eval mode (no dropout / training-time noise)
            try:
                _model.eval()
                for m in getattr(_model, "model", []) if hasattr(_model, "model") else []:
                    m.eval()
            except Exception:
                pass
            _model_load_elapsed_s = round(time.time() - t0, 2)
            _model_load_status = "loaded"
            print(f"[m3gnet] Loaded in {_model_load_elapsed_s:.1f}s")
        except Exception as exc:
            print(f"[m3gnet] Model load failed: {exc}")
            _model_load_failed = True
            _model_load_status = "failed"
            _model_load_error = str(exc)
    return _model


def preload_m3gnet_async():
    """Trigger a background thread to load the model — call from app startup."""
    threading.Thread(target=_load_model_blocking, daemon=True).start()


# ─────────────────────────────────────────────────────────────────────────
# Structure builder: composition → ASE Atoms → pymatgen Structure
# ─────────────────────────────────────────────────────────────────────────

def _base_supercell(majority: str, lattice_type: str, a0: float, target_atoms: int):
    """Build an all-majority supercell (~target_atoms big). Returns the ASE
    Atoms object plus the conventional-cell stride so callers can identify
    sublattice membership by atom index."""
    from ase.build import bulk
    try:
        atoms = bulk(majority, crystalstructure=lattice_type, a=a0, cubic=True)
    except (RuntimeError, ValueError):
        atoms = bulk(majority, crystalstructure="fcc", a=4.0, cubic=True)
        lattice_type = "fcc"
    stride = len(atoms)   # atoms per conventional cell (FCC=4, BCC=2, HCP=?, …)
    rep = max(1, round((target_atoms / stride) ** (1 / 3)))
    atoms = atoms.repeat((rep, rep, rep))
    return atoms, lattice_type, stride


def _detect_ordering(norm: dict[str, float], lattice_type: str) -> tuple[str, str, str] | None:
    """
    Recognise a binary composition / lattice pair that corresponds to a known
    stoichiometric ordering. Returns (ordering_name, majority_el, minority_el)
    or None if no pattern applies.

    Patterns covered:
        L12  — FCC at 75:25  (Ni3Al, Cu3Au-style — same Bravais lattice as host)

    NOTE on what we *don't* cover yet:
        L10 (FCC 50:50, e.g. TiAl) and B2 (BCC 50:50, e.g. NiAl) are real
        structures but their lattice constants differ substantially from the
        host element's (e.g. real NiAl B2 has a≈2.88 Å vs host Ni FCC at 3.52).
        Building those orderings on the host's lattice introduces strain that
        worsens predictions (validated empirically against the canonical
        phases). Better handled by an MP-structure lookup in a future commit.
    """
    if len(norm) != 2:
        return None
    (a, fa), (b, fb) = sorted(norm.items(), key=lambda kv: -kv[1])
    # `a` is now the majority. Tolerance ±3 at%.
    if lattice_type == "fcc" and abs(fa - 0.75) < 0.03:
        return ("L12", a, b)
    return None


def _build_ordered_supercell(composition: dict[str, float], target_atoms: int = 32):
    """
    For binary compositions that match a recognised stoichiometric ordering
    (L12, B2, L10), build a supercell with the minority element placed on a
    specific sublattice rather than at random.

    Returns a pymatgen Structure, or None if no ordering pattern applies.
    """
    from pymatgen.io.ase import AseAtomsAdaptor

    norm = {el: v / sum(composition.values()) for el, v in composition.items() if v > 0}
    if not norm:
        return None
    majority = max(norm, key=norm.get)
    lattice_type, a0 = GROUND_STATE_LATTICE.get(majority, DEFAULT_LATTICE)
    if lattice_type == "diamond":
        return None

    ordering = _detect_ordering(norm, lattice_type)
    if ordering is None:
        return None
    name, maj, minor = ordering

    atoms, lattice_type, stride = _base_supercell(majority, lattice_type, a0, target_atoms)
    n_total = len(atoms)

    if name == "L12":
        # FCC stride = 4. Put `minor` on every 4th atom (one sublattice → 25%).
        symbols = [minor if (i % stride == 0) else maj for i in range(n_total)]
    else:
        return None

    atoms.set_chemical_symbols(symbols)
    return AseAtomsAdaptor.get_structure(atoms)


def _build_supercell(composition: dict[str, float], target_atoms: int = 32, seed: int = 42):
    """
    Build a representative supercell for the given composition.

    Strategy:
    1. Identify majority element → use its ground-state crystal lattice
    2. Build an N×N×N supercell of that lattice (~32 atoms)
    3. Randomly assign atoms to match composition fractions (round to integer counts)
    """
    from ase.build import bulk
    from pymatgen.io.ase import AseAtomsAdaptor

    norm = {el: v / sum(composition.values()) for el, v in composition.items() if v > 0}
    if not norm:
        return None

    majority = max(norm, key=norm.get)
    lattice_type, a0 = GROUND_STATE_LATTICE.get(majority, DEFAULT_LATTICE)

    # ASE structure — diamond not supported by bulk(), fallback to FCC for Si/Ge
    if lattice_type == "diamond":
        lattice_type = "diamond"
    try:
        atoms = bulk(majority, crystalstructure=lattice_type, a=a0, cubic=True)
    except (RuntimeError, ValueError):
        atoms = bulk(majority, crystalstructure="fcc", a=4.0, cubic=True)
        lattice_type = "fcc"

    # Tile to reach ~target_atoms total
    n_base = len(atoms)
    rep = max(1, round((target_atoms / n_base) ** (1 / 3)))
    atoms = atoms.repeat((rep, rep, rep))

    n_total = len(atoms)
    # Compute integer atom counts for each element
    counts = {el: round(frac * n_total) for el, frac in norm.items()}
    diff = n_total - sum(counts.values())
    # Top up / trim from majority element to ensure total matches
    counts[majority] += diff

    # Build the symbol list with random shuffling
    symbols = []
    for el, n in counts.items():
        symbols.extend([el] * max(0, n))
    rng = np.random.default_rng(seed)
    rng.shuffle(symbols)
    if len(symbols) != n_total:
        # Pad/trim to exact n_total
        symbols = (symbols + [majority] * n_total)[:n_total]

    atoms.set_chemical_symbols(symbols)
    structure = AseAtomsAdaptor.get_structure(atoms)
    return structure


# ─────────────────────────────────────────────────────────────────────────
# Prediction with N-replica averaging for uncertainty
# ─────────────────────────────────────────────────────────────────────────

_cache: dict[str, dict[str, Any]] = {}

# Conformal calibrator (fit on first request from canonical-phase residuals)
_calibrator = None
_calibrator_lock = threading.Lock()
_calibrator_status = "not_started"          # not_started | fitting | fitted | failed
_calibrator_elapsed_s: float | None = None
_calibrator_error: str | None = None


def health_snapshot() -> dict[str, Any]:
    """Return a JSON-friendly summary of M3GNet + calibrator load state.

    Used by `GET /api/health/models` so the frontend can show a "loading"
    indicator on formation-energy predictions until M3GNet is warm.
    """
    return {
        "m3gnet": {
            "status":        _model_load_status,
            "elapsed_load_s": _model_load_elapsed_s,
            "error":         _model_load_error,
        },
        "calibrator": {
            "status":        _calibrator_status,
            "elapsed_fit_s": _calibrator_elapsed_s,
            "n_calibration": _calibrator.n_calibration if _calibrator is not None else None,
            "q_eV_per_atom": round(_calibrator.q, 4) if _calibrator is not None else None,
            "error":         _calibrator_error,
        },
    }


def _get_calibrator():
    """Return the cached SplitConformalPredictor for M3GNet, fitting it on
    first call from the canonical_phases reference set.

    Calibration data are the |M3GNet − MP-PBE| residuals on the 13 stoichio-
    metric intermetallics in canonical_phases.CANONICAL_INTERMETALLICS. The
    resulting interval has marginal 90% coverage *on that calibration set*;
    for solid-solution compositions the guarantee is approximate (the
    exchangeability assumption is approximate).
    """
    global _calibrator, _calibrator_status, _calibrator_elapsed_s, _calibrator_error
    if _calibrator is not None:
        return _calibrator
    with _calibrator_lock:
        if _calibrator is not None:
            return _calibrator
        _calibrator_status = "fitting"
        try:
            from apps.api.ml.calibration import fit_simple_conformal
            from apps.api.ml.eval.canonical_phases import CANONICAL_INTERMETALLICS

            # NB: fit on the ~13 CANONICAL_INTERMETALLICS, the same set the
            # coverage test evaluates → in-sample.  See module docstring; the
            # 90 % band has no out-of-sample guarantee until a held-out set exists.
            print("[m3gnet] Fitting conformal calibrator from canonical phases...")
            t0 = time.time()
            residuals = []
            for entry in CANONICAL_INTERMETALLICS:
                # Predict without caching, to avoid recursive cache use during fit
                pred = _predict_uncalibrated(entry["composition"])
                if pred.get("value") is None:
                    continue
                residuals.append(abs(pred["value"] - entry["ref_eV_per_atom"]))
            if len(residuals) < 4:
                msg = f"only {len(residuals)} residuals available — need ≥4"
                print(f"[m3gnet] Calibration aborted: {msg}")
                _calibrator_status = "failed"
                _calibrator_error = msg
                return None
            _calibrator = fit_simple_conformal(np.array(residuals), alpha=0.10)
            _calibrator_elapsed_s = round(time.time() - t0, 2)
            _calibrator_status = "fitted"
            print(f"[m3gnet] Calibrator: q={_calibrator.q:.3f} eV/atom, "
                  f"empirical coverage on cal set={_calibrator.empirical_coverage:.1%} "
                  f"(target 90%, n={_calibrator.n_calibration}) in {_calibrator_elapsed_s:.1f}s")
        except Exception as exc:
            print(f"[m3gnet] Calibrator fit failed: {exc}")
            _calibrator_status = "failed"
            _calibrator_error = str(exc)
    return _calibrator


def _cache_key(composition: dict[str, float]) -> str:
    key = "|".join(f"{el}:{round(v, 3)}" for el, v in sorted(composition.items()))
    return hashlib.md5(key.encode()).hexdigest()


def _predict_uncalibrated(
    composition: dict[str, float],
    n_replicas: int = 6,
    timeout_s: float = 8.0,
) -> dict[str, Any]:
    """Internal: M3GNet prediction WITHOUT conformal interval wrapping.

    Returns {value, uncertainty (config spread), source, n_replicas, ...}.
    The public formation_energy_m3gnet calls this and then wraps the result
    with the conformal calibrator. Calibration itself also calls this so it
    can compute residuals without recursion.
    """
    elements_present = [el for el, v in composition.items() if v > 0]
    if len(elements_present) == 1:
        return {
            "value": 0.0,
            "uncertainty": 0.0,
            "source": "by_definition",
            "note": "Pure element — formation energy is zero by definition",
        }

    model = _load_model_blocking()
    if model is None:
        return {"value": None, "source": "m3gnet_dft", "error": "model unavailable"}

    energies: list[float] = []
    candidate_labels: list[str] = []
    t_start = time.time()
    try:
        # 0. MP-structure lookup — when the composition is close to a known
        # stable phase, MP gives us the real ground-state structure with
        # correct lattice constants and ordering. On that relaxed input
        # M3GNet approaches its published bench (~50 meV/atom MAE); the
        # random-supercell fallback below is much coarser (see module docstring).
        try:
            from apps.api.ml.mp_structure_lookup import get_mp_structure
            mp_struct = get_mp_structure(composition)
        except Exception as exc:
            print(f"[m3gnet] MP lookup skipped: {exc}")
            mp_struct = None
        if mp_struct is not None:
            energies.append(float(model.predict_structure(mp_struct)))
            candidate_labels.append("mp_lookup")

        # 1. Deterministic ordered candidate (L12 on FCC 75:25)
        ordered_structure = _build_ordered_supercell(composition, target_atoms=32)
        if ordered_structure is not None:
            energies.append(float(model.predict_structure(ordered_structure)))
            candidate_labels.append("ordered")

        # 2. Random supercells
        for seed in range(42, 42 + n_replicas):
            if time.time() - t_start > timeout_s:
                break
            structure = _build_supercell(composition, target_atoms=32, seed=seed)
            if structure is None:
                continue
            energies.append(float(model.predict_structure(structure)))
            candidate_labels.append(f"random_{seed - 42}")
    except Exception as exc:
        return {"value": None, "source": "m3gnet_dft", "error": str(exc)}

    if not energies:
        return {"value": None, "source": "m3gnet_dft", "error": "no candidate structures could be built"}

    arr = np.array(energies)
    config_spread = float(arr.max() - arr.min())

    # Prediction strategy: mean across all candidates (MP-lookup, ordered,
    # random replicas). Empirically the mean is more robust than picking any
    # single candidate:
    #   - Single-candidate "MP-lookup as truth" overshoots on phases that
    #     M3GNet doesn't reproduce well (e.g. θ-Al2Cu, antifluorite Mg2Si —
    #     M3GNet gives them ~-0.5 eV/atom vs MP's ~-0.1 to -0.2).
    #   - Single-candidate "min of random" picks lucky-low artifacts.
    # Averaging the MP candidate in with the supercell candidates partially
    # corrects the supercell upward bias on L12 phases without amplifying
    # M3GNet's intrinsic errors elsewhere.
    value = float(arr.mean())
    uncertainty = max(config_spread / 2.0, float(arr.std())) + 0.05

    return {
        "value": round(value, 4),
        "uncertainty": round(uncertainty, 4),
        "source": "m3gnet_dft",
        "n_replicas": len(energies),
        "mp_lookup_used": "mp_lookup" in candidate_labels,
        "ordered_used": "ordered" in candidate_labels,
        "energy_range_eV": [round(float(arr.min()), 4), round(float(arr.max()), 4)],
        "elapsed_s": round(time.time() - t_start, 2),
    }


def formation_energy_m3gnet(
    composition: dict[str, float],
    n_replicas: int = 6,
    timeout_s: float = 8.0,
) -> dict[str, Any]:
    """
    Predict formation energy via M3GNet on multiple candidate supercells,
    then wrap the point estimate in a conformal 90% prediction interval.

    Strategy:
      1. Build candidate structures (one L12-ordered if composition matches,
         plus N=6 random supercells with different seeds).
      2. Predict each with M3GNet; report the mean as ŷ, configurational
         spread as a raw uncertainty.
      3. Wrap ŷ in [ŷ − q, ŷ + q] using a conformal quantile q fit from the
         |M3GNet − MP-PBE| residuals on the canonical phases set.

    For pure elements the formation energy is 0 by definition and we return
    a degenerate interval [0, 0] with source="by_definition".

    Returned dict:
        {value, ci_low, ci_high, uncertainty (=half-width), coverage,
         calibration ("conformal" or "configurational_only"),
         source, n_replicas, ordered_used, energy_range_eV, elapsed_s}
    """
    # Cache hit?
    ck = _cache_key(composition)
    if ck in _cache:
        return _cache[ck]

    # Compute the uncalibrated point estimate
    raw = _predict_uncalibrated(composition, n_replicas=n_replicas, timeout_s=timeout_s)
    if raw.get("value") is None:
        return raw

    # Pure-element path skips conformal entirely
    if raw.get("source") == "by_definition":
        out = {
            **raw,
            "ci_low": 0.0,
            "ci_high": 0.0,
            "coverage": 1.0,
            "calibration": "by_definition",
        }
        _cache[ck] = out
        return out

    # Wrap with conformal calibrator (fit on first request from canonical phases)
    calibrator = _get_calibrator()
    if calibrator is not None:
        ci_low, ci_high, half = calibrator.interval(raw["value"])
        out = {
            **raw,
            "ci_low":         round(ci_low, 4),
            "ci_high":        round(ci_high, 4),
            "uncertainty":    round(half, 4),               # override config spread with calibrated half-width
            "coverage":       round(1 - calibrator.alpha, 2),
            "calibration":    "conformal",
            "n_calibration":  calibrator.n_calibration,
        }
    else:
        # Fallback: configurational spread (legacy, no coverage guarantee)
        unc = raw["uncertainty"]
        out = {
            **raw,
            "ci_low":      round(raw["value"] - unc, 4),
            "ci_high":     round(raw["value"] + unc, 4),
            "coverage":    None,
            "calibration": "configurational_only",
        }
    _cache[ck] = out
    return out
