"""
apps.api.ml.microstructure.interpret
====================================

Layer 1 of the dendrite interpretation stack — pure numerical analysis of
the phase-field output.  No LLM, no opinions; just measurements an
LLM (Layer 2) or a metallurgist can reason about.

Public entry point
------------------
``analyse_dendrite(frames, params, sim_metadata)`` returns a dict shaped like:

    {
        "n_arms_detected":         6,
        "n_arms_expected":         6,                # from anisotropy order N
        "regime":                  "dendritic",      # planar | spherical | cellular | dendritic
        "side_branch_amplitude":   "strong",         # none | weak | moderate | strong
        "tip_velocity_dimless":    0.024,            # cells per dimensionless time unit
        "symmetry_score":          0.93,             # 1.0 = perfect N-fold; 0 = no preferred order
        "circularity":             0.42,             # 1.0 = circle; lower = more branched
        "boundary_touching":       false,
        "solid_fraction_final":    0.302,
        "growth_phase":            "developed",      # nucleation | early | developed | impinging
        "quality_warnings":        ["..."],
    }

All measurements are on the *final* frame; tip velocity uses the late
frames for a steady-state estimate.

This module is intentionally numpy + scipy.ndimage only — no OpenCV, no
sklearn — to stay fast on the FastAPI worker (target < 50 ms per call).
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy import ndimage, signal
from scipy.fft import rfft, rfftfreq


# ─────────────────────────────────────────────────────────────────────
# Field utilities
# ─────────────────────────────────────────────────────────────────────

def _solid_mask(phi: np.ndarray, threshold: float = 0.5) -> np.ndarray:
    """Boolean mask of the solid region."""
    return phi > threshold


def _center_of_mass(mask: np.ndarray) -> tuple[float, float]:
    """Return (cy, cx) — row, column indices of the solid centroid."""
    cy, cx = ndimage.center_of_mass(mask.astype(np.float32))
    return float(cy), float(cx)


def _boundary_touching(mask: np.ndarray, margin: int = 3) -> bool:
    """True if the solid has reached within ``margin`` cells of any edge."""
    if not mask.any():
        return False
    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    H, W = mask.shape
    return bool(rows.min() < margin or rows.max() > H - 1 - margin
                or cols.min() < margin or cols.max() > W - 1 - margin)


# ─────────────────────────────────────────────────────────────────────
# Angular profile + arm count
# ─────────────────────────────────────────────────────────────────────

def _angular_radius_profile(
    mask: np.ndarray,
    center: tuple[float, float],
    n_bins: int = 180,
) -> np.ndarray:
    """For each angular bin (0..2π), the maximum radius at which the
    field is solid.  Length = ``n_bins``.

    Returns radii in *cell* units (not physical length).  Zero means no
    solid pixel found in that angular sector.
    """
    cy, cx = center
    H, W = mask.shape
    ys, xs = np.where(mask)
    if ys.size == 0:
        return np.zeros(n_bins, dtype=np.float32)
    dy = ys - cy
    dx = xs - cx
    r = np.hypot(dy, dx)
    theta = np.arctan2(dy, dx)   # (-pi, pi]
    bin_idx = ((theta + np.pi) / (2 * np.pi) * n_bins).astype(np.int32) % n_bins

    profile = np.zeros(n_bins, dtype=np.float32)
    # np.maximum.at gives us per-bin max
    np.maximum.at(profile, bin_idx, r)
    return profile


def _count_arms(
    profile: np.ndarray,
    prominence_frac: float = 0.18,
    min_separation_deg: float = 22.0,
    flatness_tol: float = 0.22,
) -> tuple[int, list[int]]:
    """Count radial peaks in the angular profile → arm count.

    A "peak" is a local maximum that stands out by at least
    ``prominence_frac`` of the profile's range.  Peaks closer than
    ``min_separation_deg`` are merged.

    ``flatness_tol`` short-circuits the detector on essentially-flat
    profiles: if the relative variation (max-min)/max is below this
    threshold, the shape is a disc/seed and we return 0 arms.  Otherwise
    pixel-discretisation ripples on a perfect disc would each register
    as a "peak" and we'd report dozens of phantom arms.

    Returns ``(n_arms, peak_bin_indices)``.
    """
    n_bins = profile.size
    if profile.max() <= 1.5:
        return 0, []  # no solid → no arms

    # Flatness check on the non-zero bins only.  For small/round shapes,
    # angular-bin discretisation leaves some bins empty (no solid pixel
    # within that wedge), so (max - min)/max would always be 1.0 even
    # for a perfect disc.  std/mean over the non-zero bins is robust:
    # a disc gets std/mean ≈ 0.05-0.15, an arms-bearing dendrite ≥ 0.35.
    nonzero = profile[profile > 0]
    if nonzero.size and (nonzero.std() / max(nonzero.mean(), 1e-6)) < flatness_tol:
        return 0, []  # essentially circular — disc/seed, no arm structure

    # Wrap the profile by tiling so peaks near the 0/2π seam are detected
    tiled = np.concatenate([profile, profile, profile])
    prom = (profile.max() - profile.min()) * prominence_frac
    min_sep_bins = max(1, int(round(min_separation_deg / 360.0 * n_bins)))
    peaks, _ = signal.find_peaks(tiled, prominence=prom, distance=min_sep_bins)

    # Keep peaks that fall in the middle tile [n_bins, 2*n_bins)
    inside = peaks[(peaks >= n_bins) & (peaks < 2 * n_bins)]
    unique = sorted(set((p % n_bins) for p in inside))
    return len(unique), unique


def _symmetry_score(profile: np.ndarray, n_fold_expected: int) -> float:
    """How much of the angular signal sits on the expected N-fold harmonic.

    1.0 = profile is dominated by the N-fold component (perfect symmetry).
    0.0 = energy spread across all harmonics (no preferred order).
    """
    if profile.max() <= 1.5:
        return 0.0
    # Remove DC and normalise
    sig = profile - profile.mean()
    if np.allclose(sig, 0):
        return 0.0
    spectrum = np.abs(rfft(sig))
    # Harmonic indices of an N-fold pattern: N, 2N, 3N, ...
    nfold_power = sum(
        spectrum[k] ** 2
        for k in range(n_fold_expected, len(spectrum), n_fold_expected)
    )
    total_power = (spectrum ** 2).sum()
    if total_power <= 0:
        return 0.0
    return float(min(1.0, nfold_power / total_power))


def _circularity(mask: np.ndarray) -> float:
    """4πA / P² — 1.0 for a perfect circle, lower for branched shapes.

    Uses a quick perimeter estimate via Sobel-edge length.
    """
    area = float(mask.sum())
    if area <= 0:
        return 0.0
    # Perimeter ≈ count of boundary pixels (4-connected)
    edge = mask & ~ndimage.binary_erosion(mask)
    perimeter = float(edge.sum())
    if perimeter <= 0:
        return 0.0
    return float(min(1.0, 4 * math.pi * area / (perimeter ** 2)))


# ─────────────────────────────────────────────────────────────────────
# Side-branch detection
# ─────────────────────────────────────────────────────────────────────

def _side_branch_amplitude(
    mask: np.ndarray,
    center: tuple[float, float],
    arm_directions_deg: list[float],
) -> tuple[str, float]:
    """Probe perpendicular to each arm at progressive radial fractions
    and measure how spiky the perpendicular extent is.

    Returns ``(qualitative_bucket, amplitude_norm)`` where
    ``amplitude_norm`` is the std-dev of perpendicular-extent samples
    along the arm normalised by the arm's own length.

    Empirically: < 0.02 ≈ "none"; 0.02-0.05 ≈ "weak";
    0.05-0.12 ≈ "moderate"; > 0.12 ≈ "strong".
    """
    if not arm_directions_deg:
        return "none", 0.0
    cy, cx = center
    amps: list[float] = []
    for theta_deg in arm_directions_deg:
        theta = math.radians(theta_deg)
        # Direction along arm
        dirx, diry = math.cos(theta), math.sin(theta)
        # Perpendicular direction
        perx, pery = -diry, dirx
        # Walk along arm in 1-cell increments until we exit the solid;
        # at each step measure the perpendicular half-width.
        widths: list[float] = []
        for s in range(2, 200):  # cap the walk
            px = cx + s * dirx
            py = cy + s * diry
            if not (0 <= px < mask.shape[1] - 1 and 0 <= py < mask.shape[0] - 1):
                break
            # If the arm centerline itself is liquid, we've gone past the tip
            if not mask[int(round(py)), int(round(px))]:
                break
            # March perpendicular both ways until we exit
            half = 0.0
            for sign in (+1, -1):
                for k in range(1, 60):
                    qx = px + sign * k * perx
                    qy = py + sign * k * pery
                    if not (0 <= qx < mask.shape[1] - 1
                            and 0 <= qy < mask.shape[0] - 1):
                        break
                    if not mask[int(round(qy)), int(round(qx))]:
                        break
                    half = max(half, float(k))
            widths.append(half)
        if len(widths) >= 6:
            w = np.asarray(widths[2:-1], dtype=np.float32)  # trim endpoints
            arm_len = float(len(widths))
            if arm_len > 0 and w.size:
                # Std-dev of perpendicular widths, normalised by arm length
                amps.append(float(np.std(w) / max(arm_len, 1.0)))
    if not amps:
        return "none", 0.0
    amp = float(np.mean(amps))
    if amp < 0.02:
        return "none", amp
    if amp < 0.05:
        return "weak", amp
    if amp < 0.12:
        return "moderate", amp
    return "strong", amp


# ─────────────────────────────────────────────────────────────────────
# Temporal: tip velocity from frame sequence
# ─────────────────────────────────────────────────────────────────────

def _tip_velocity_dimless(frames: list[dict]) -> float | None:
    """Estimate the steady-state tip velocity by tracking the maximum
    radial extent of the solid across the *late* half of the frames.

    Returns velocity in **cells / dimensionless-time-unit** (Kobayashi
    convention).  ``None`` if fewer than 3 frames or no growth.

    Note: ``frames`` here is the *internal* Taichi list with raw ``phi``
    arrays, not the rendered PNG list returned from the public endpoint.
    """
    if len(frames) < 3:
        return None
    try:
        # Use the *true* phase-field array, which solidification.py
        # discards before serialisation but keeps in the Taichi result.
        radii: list[tuple[float, float]] = []
        for f in frames:
            phi = f.get("phi")
            if phi is None:
                continue
            mask = phi > 0.5
            if not mask.any():
                continue
            cy, cx = _center_of_mass(mask)
            ys, xs = np.where(mask)
            r_max = float(np.hypot(ys - cy, xs - cx).max())
            t = float(f.get("time_s", 0.0))
            radii.append((t, r_max))
        if len(radii) < 3:
            return None
        # Linear fit through the late-half points for steady-state
        late = radii[len(radii) // 2:]
        t_arr = np.array([p[0] for p in late], dtype=np.float64)
        r_arr = np.array([p[1] for p in late], dtype=np.float64)
        if t_arr.max() <= t_arr.min():
            return None
        slope = float(np.polyfit(t_arr, r_arr, 1)[0])
        return slope if slope > 0 else None
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────
# Regime classification + growth phase
# ─────────────────────────────────────────────────────────────────────

def _classify_regime(
    n_arms: int,
    n_arms_expected: int,
    side_branch_amp: str,
    circularity: float,
    solid_fraction: float,
) -> str:
    """Bucket into planar | spherical | cellular | dendritic.

    Heuristic — calibrated against the canonical Kobayashi runs at
    grid=120, N=6, ΔT=1.0 (dendritic) and N=6, ΔT=0.3 (cellular).
    """
    if solid_fraction < 0.002:
        return "nucleation"   # seed not grown yet
    if circularity > 0.85:
        return "spherical"    # essentially the initial seed, no anisotropy yet
    if n_arms < max(1, n_arms_expected // 2):
        return "cellular"     # smooth growth without sharp tips
    if side_branch_amp in ("moderate", "strong"):
        return "dendritic"
    if n_arms >= n_arms_expected - 1:
        return "early dendritic"  # arms exist but side-branches still developing
    return "cellular"


def _growth_phase(solid_fraction: float, boundary_touching: bool) -> str:
    """Where in the growth history are we?"""
    if solid_fraction < 0.005:
        return "nucleation"
    if solid_fraction < 0.05:
        return "early"
    if solid_fraction < 0.25 and not boundary_touching:
        return "developed"
    if boundary_touching:
        return "impinging"
    return "developed"


# ─────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────

def analyse_dendrite(
    frames: list[dict],
    params: dict[str, float],
    sim_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run all the Layer-1 measurements and return a single summary dict.

    Parameters
    ----------
    frames
        The raw Taichi-result frame list (each entry has ``phi``, ``T``,
        ``time_s``, ``solid_fraction``, ``step``).  This is the
        *internal* list, not the PNG-serialised public one.
    params
        Kobayashi parameters used for the run (``N``, ``T_bath``,
        ``theta_0``, …).
    sim_metadata
        Optional extra context to passthrough into the result.

    Returns
    -------
    dict
        See module docstring for the schema.
    """
    if not frames:
        return {
            "n_arms_detected": 0,
            "n_arms_expected": int(params.get("N", 6)),
            "regime": "no_data",
            "side_branch_amplitude": "none",
            "side_branch_amp_score": 0.0,
            "tip_velocity_dimless": None,
            "symmetry_score": 0.0,
            "circularity": 0.0,
            "boundary_touching": False,
            "solid_fraction_final": 0.0,
            "growth_phase": "nucleation",
            "quality_warnings": ["no frames returned from simulator"],
        }

    final = frames[-1]
    phi = final["phi"]
    mask = _solid_mask(phi)
    sf_final = float(mask.mean())
    n_expected = int(round(params.get("N", 6)))

    warnings: list[str] = []

    if not mask.any():
        warnings.append("final frame is fully liquid; nucleation failed")
        return {
            "n_arms_detected":      0,
            "n_arms_expected":      n_expected,
            "regime":               "nucleation",
            "side_branch_amplitude":"none",
            "side_branch_amp_score":0.0,
            "tip_velocity_dimless": None,
            "symmetry_score":       0.0,
            "circularity":          0.0,
            "boundary_touching":    False,
            "solid_fraction_final": 0.0,
            "growth_phase":         "nucleation",
            "quality_warnings":     warnings,
        }

    center = _center_of_mass(mask)
    profile = _angular_radius_profile(mask, center, n_bins=180)
    n_arms, peak_bins = _count_arms(profile)

    arm_directions_deg = [
        (b / profile.size) * 360.0 - 180.0 for b in peak_bins
    ]
    amp_label, amp_score = _side_branch_amplitude(mask, center, arm_directions_deg)
    sym = _symmetry_score(profile, max(2, n_expected))
    circ = _circularity(mask)
    boundary = _boundary_touching(mask)
    if boundary:
        warnings.append("solid has reached the simulation-box boundary; "
                        "tip velocity and morphology unreliable past this point")

    tip_v = _tip_velocity_dimless(frames)
    regime = _classify_regime(n_arms, n_expected, amp_label, circ, sf_final)
    phase = _growth_phase(sf_final, boundary)

    if n_arms and abs(n_arms - n_expected) >= 2:
        warnings.append(
            f"detected {n_arms} arms but anisotropy order is N={n_expected}; "
            "morphology may be deformed by boundary or insufficient resolution"
        )

    return {
        "n_arms_detected":       n_arms,
        "n_arms_expected":       n_expected,
        "regime":                regime,
        "side_branch_amplitude": amp_label,
        "side_branch_amp_score": round(amp_score, 4),
        "tip_velocity_dimless":  round(tip_v, 4) if tip_v is not None else None,
        "symmetry_score":        round(sym, 3),
        "circularity":           round(circ, 3),
        "boundary_touching":     boundary,
        "solid_fraction_final":  round(sf_final, 4),
        "growth_phase":          phase,
        "quality_warnings":      warnings,
        # Provenance for downstream consumers
        "source":                "dendrite_image_analysis_v1",
        "calibration":           "heuristic",
        "_meta": {
            "anisotropy_N":      n_expected,
            "T_bath":            float(params.get("T_bath", 0.5)),
            "theta_0_rad":       float(params.get("theta_0", 0.0)),
        },
    }
