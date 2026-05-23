"""
apps.api.ml.temper.encoding
============================

Canonical temper vocabularies and encoders.

The model learns temper as a one-hot vector concatenated to the
composition features.  We use a per-family vocabulary because temper
semantics are family-specific: ``"Annealed"`` for an aluminium alloy
means recrystallised + slowly cooled (the O temper), whereas
``"Annealed"`` for a steel means austenitised + slowly cooled (still a
different microstructure outcome).

Each family also has an optional **strength index** ∈ [0, 1] that
captures the qualitative ordering O < T4 < T6 < T7 (or N < Q&T) — a
soft hint to the regressor that interpolates sensibly across tempers
within a family.

Public API
----------
``canonicalise_temper(family, raw_temper)``
    Normalise a free-form temper string to one of the family's canonical
    codes (e.g. ``"Hot rolled"`` → ``"Hot-rolled"``, ``"q&t"`` → ``"Q&T"``).

``encode_temper(family, temper) -> np.ndarray``
    Return a one-hot vector + strength-index float as a flat array.

``default_temper_for_family(family) -> str``
    Modal temper used when the caller doesn't specify one.  Returning a
    sensible default lets the API accept ``temper=None`` without breaking.

``TEMPER_VOCABULARY``
    The full per-family canonical list.  Persisted to the model bundle.
"""
import re
import numpy as np


# ─────────────────────────────────────────────────────────────────────────────
# Canonical vocabularies, ordered roughly by strength (O → T6 → T8x → ...).
# The order matters for the strength index; alphabetical ordering would mix
# soft and hard tempers and give the regressor a less useful gradient.
# ─────────────────────────────────────────────────────────────────────────────

TEMPER_VOCABULARY: dict = {
    "aluminum": [
        # Soft / annealed
        "O", "F",
        # Solution-treated (no aging)
        "T351", "T4", "T3",
        # Stabilised / partial aging
        "T5", "T1", "T2",
        # Peak-aged (T6 family)
        "T6", "T651", "T61",
        # Overaged (T7 family)
        "T7", "T73", "T7351", "T74", "T7451", "T7651", "T7751",
        # Cold-worked + aged (T8 family — highest strength)
        "T8", "T81", "T83", "T84", "T851", "T87", "T8511", "T6511", "T8E74", "T8771",
        # Strain-hardened (H series — non-heat-treatable Al)
        "H12", "H14", "H18", "H19",
        "H22", "H24", "H25",
        "H32", "H34", "H38",
        "H111", "H116", "H321",
    ],
    "titanium": [
        "Annealed", "Mill-annealed", "Duplex anneal",
        "β-anneal",
        "STA", "HIP+Aged",
    ],
    "nickel": [
        "Annealed", "Solution",
        "Aged", "SX-Aged",
    ],
    "general_steel": [
        # Soft
        "Annealed",
        # Hot-finished / as-rolled / TMCP structural
        "Hot-rolled", "As-rolled", "Normalised", "TMCP",
        # Cold-finished
        "Cold-drawn", "Cold-rolled",
        # Quenched & tempered (with optional temperature suffix)
        "Q&T", "Q&T 300", "Q&T 400", "Q&T 425", "Q&T 450", "Q&T 650",
        # Case-hardened
        "Carburised", "Carburised + Q&T",
        # PH aging (one canonical per condition)
        "H900", "H950", "H1000", "H1025", "H1050", "H1150",
        # Misc
        "Weathering", "HSLA",
    ],
}


# ── Aliases per family (free-form → canonical) ──────────────────────────────

_ALIASES: dict = {
    "aluminum": {
        # Capitalisation / spacing variants
        "o": "O", "f": "F", "as-fabricated": "F",
        # Common synonyms
        "annealed": "O", "ann": "O",
        # T-family hyphens, dashes
        "t-6": "T6", "t 6": "T6",
        "t-651": "T651", "t 651": "T651",
        "t-7351": "T7351", "t 7351": "T7351",
        # H-family
        "h-14": "H14", "h-32": "H32",
    },
    "titanium": {
        # All-lower variants
        "ann": "Annealed", "annealed": "Annealed",
        "mill annealed": "Mill-annealed", "mill-anneal": "Mill-annealed",
        "duplex annealed": "Duplex anneal", "duplex-anneal": "Duplex anneal",
        "beta-anneal": "β-anneal", "beta anneal": "β-anneal", "b-anneal": "β-anneal",
        "sta": "STA", "solution treated and aged": "STA",
        "hip aged": "HIP+Aged", "hip + aged": "HIP+Aged",
    },
    "nickel": {
        "ann": "Annealed", "annealed": "Annealed",
        "solution": "Solution", "solution annealed": "Solution",
        "aged": "Aged", "precipitation aged": "Aged",
        "sx aged": "SX-Aged", "sx-aged": "SX-Aged", "single crystal": "SX-Aged",
    },
    "general_steel": {
        "annealed": "Annealed", "ann": "Annealed",
        "hot rolled": "Hot-rolled", "hr": "Hot-rolled",
        "as rolled": "As-rolled", "as-rolled": "As-rolled",
        "normalised": "Normalised", "normalized": "Normalised", "n": "Normalised",
        "cold drawn": "Cold-drawn", "cd": "Cold-drawn",
        "cold rolled": "Cold-rolled", "cr": "Cold-rolled",
        "q&t": "Q&T", "quenched and tempered": "Q&T",
        "carburised": "Carburised", "carburized": "Carburised",
        "tmcp": "TMCP",
        # PH-stainless aging (collapse e.g. "H 950" to "H950")
    },
}


# ── Strength index per temper (0 = annealed soft, 1 = peak/over-aged) ───────
# Used as an *auxiliary* feature so the regressor can interpolate sensibly
# across tempers of the same composition.

_STRENGTH_INDEX: dict = {
    "aluminum": {
        "O": 0.00, "F": 0.05,
        "T1": 0.20, "T2": 0.25,
        "T3": 0.45, "T4": 0.40, "T351": 0.45,
        "T5": 0.50,
        "T6": 0.75, "T61": 0.70, "T651": 0.78,
        "T7": 0.60, "T73": 0.65, "T7351": 0.65, "T74": 0.65,
        "T7451": 0.70, "T7651": 0.80, "T7751": 0.85,
        "T8": 0.85, "T81": 0.88, "T83": 0.90, "T84": 0.90, "T851": 0.85,
        "T87": 0.92, "T8511": 0.92, "T6511": 1.00, "T8E74": 0.88, "T8771": 0.90,
        "H12": 0.15, "H14": 0.30, "H18": 0.55, "H19": 0.60,
        "H22": 0.20, "H24": 0.30, "H25": 0.30,
        "H32": 0.30, "H34": 0.40, "H38": 0.55,
        "H111": 0.15, "H116": 0.35, "H321": 0.40,
    },
    "titanium": {
        "Annealed": 0.30, "Mill-annealed": 0.35, "Duplex anneal": 0.50,
        "β-anneal": 0.55,
        "STA": 0.90, "HIP+Aged": 0.85,
    },
    "nickel": {
        "Annealed": 0.20, "Solution": 0.25,
        "Aged": 0.85, "SX-Aged": 0.95,
    },
    "general_steel": {
        "Annealed": 0.10,
        "Hot-rolled": 0.20, "As-rolled": 0.20, "Normalised": 0.30, "TMCP": 0.45,
        "Cold-drawn": 0.55, "Cold-rolled": 0.55,
        "Q&T":      0.65,
        "Q&T 300":  0.85, "Q&T 400":  0.75, "Q&T 425":  0.70,
        "Q&T 450":  0.65, "Q&T 650":  0.50,
        "Carburised": 0.55, "Carburised + Q&T": 0.75,
        "H900": 0.95, "H950": 0.90, "H1000": 0.85,
        "H1025": 0.80, "H1050": 0.70, "H1150": 0.60,
        "Weathering": 0.30, "HSLA": 0.45,
    },
}


# ── Family-level default temper (modal value in our training data) ──────────

DEFAULT_TEMPER: dict = {
    "aluminum":      "T6",        # 18 entries, the most common peak-aged temper
    "titanium":      "STA",       # 17 entries
    "nickel":        "Aged",      # 32 entries
    "general_steel": "Annealed",  # 30 entries (broad baseline)
}


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    """Lowercase + collapse whitespace; preserve hyphens / ampersands."""
    return re.sub(r"\s+", " ", s.strip().lower())


def canonicalise_temper(family: str, raw_temper) -> str:
    """Map a free-form temper string to a canonical code for *family*.

    Returns the matched canonical name if known, otherwise the **default
    temper** for the family.  Never raises — unknown tempers degrade
    gracefully to the modal one (with a wider CI as a result, since the
    model isn't conditioned on the user's actual temper).
    """
    if family not in TEMPER_VOCABULARY:
        raise ValueError(f"Unknown family {family!r}; valid: {list(TEMPER_VOCABULARY)}")
    if raw_temper is None:
        return DEFAULT_TEMPER[family]

    raw = str(raw_temper).strip()
    if not raw:
        return DEFAULT_TEMPER[family]

    # Direct match on the canonical vocabulary
    vocab = TEMPER_VOCABULARY[family]
    if raw in vocab:
        return raw

    # Case-insensitive direct match
    lower_to_canon = {t.lower(): t for t in vocab}
    if raw.lower() in lower_to_canon:
        return lower_to_canon[raw.lower()]

    # Aliases
    aliases = _ALIASES.get(family, {})
    normed = _norm(raw)
    if normed in aliases:
        return aliases[normed]

    # Q&T with degree suffix — strip "°C" / "C" and collapse spacing
    m = re.match(r"^q&t\s*(\d{3})(?:\s*°?\s*c)?$", normed)
    if m and family == "general_steel":
        suffix = m.group(1)
        candidate = f"Q&T {suffix}"
        if candidate in vocab:
            return candidate
        return "Q&T"

    # PH-stainless aging codes with optional space: "H 950" → "H950"
    m = re.match(r"^h\s*(\d{3,4})$", normed)
    if m and family == "general_steel":
        candidate = f"H{m.group(1)}"
        if candidate in vocab:
            return candidate

    # Default
    return DEFAULT_TEMPER[family]


def encode_temper(family: str, temper) -> np.ndarray:
    """Encode a temper as ``[one_hot..., strength_index]`` for *family*.

    Output shape: ``(len(TEMPER_VOCABULARY[family]) + 1,)``.
    """
    if family not in TEMPER_VOCABULARY:
        raise ValueError(f"Unknown family {family!r}")
    canonical = canonicalise_temper(family, temper)
    vocab = TEMPER_VOCABULARY[family]
    one_hot = np.zeros(len(vocab), dtype=float)
    if canonical in vocab:
        one_hot[vocab.index(canonical)] = 1.0
    strength = _STRENGTH_INDEX.get(family, {}).get(canonical, 0.5)
    return np.concatenate([one_hot, [strength]])


def default_temper_for_family(family: str) -> str:
    """Return the family's default canonical temper."""
    return DEFAULT_TEMPER[family]


def temper_feature_dim(family: str) -> int:
    """Number of features added by ``encode_temper`` for *family*."""
    return len(TEMPER_VOCABULARY[family]) + 1


def list_tempers(family: str) -> list:
    """Return the canonical temper list for *family* (UI dropdown)."""
    return list(TEMPER_VOCABULARY[family])
