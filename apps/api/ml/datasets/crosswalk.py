"""
apps.api.ml.datasets.crosswalk
===============================

Canonical-name resolver across alloy designation systems.

Three or four naming systems coexist for most engineering alloys:
* AA (Aluminum Association):  ``6061``, ``7075``, ``A356``
* UNS (Unified Numbering):    ``A96061``, ``A97075``, ``A03560``
* AISI / SAE:                 ``4140``, ``4340`` for steels
* DIN / EN:                   ``1.7225``, ``1.6582`` for steels;
                              ``EN AW-6061`` for Al
* JIS:                        ``SCM440`` ≡ ``AISI 4140``, ``A6061`` ≡ ``6061``

This module provides ``canonical_name(designation)`` which collapses any of
the above to a single canonical key, so we can deduplicate across data
sources without losing valid distinct entries.
"""
import re


# Manual cross-reference table — only the alloys we curate.  Extending this
# is cheap; getting it wrong is expensive (would merge two distinct alloys).
_ALIASES = {
    # ── Aluminum (AA → canonical, plus common temper-less aliases) ──
    "6061":       ["aa6061",  "uns a96061", "en aw-6061", "a6061", "en aw 6061"],
    "6063":       ["aa6063",  "uns a96063", "en aw-6063"],
    "6082":       ["aa6082",  "uns a96082", "en aw-6082"],
    "2024":       ["aa2024",  "uns a92024", "en aw-2024"],
    "2014":       ["aa2014",  "uns a92014", "en aw-2014"],
    "7075":       ["aa7075",  "uns a97075", "en aw-7075"],
    "7050":       ["aa7050",  "uns a97050"],
    "7178":       ["aa7178",  "uns a97178"],
    "5052":       ["aa5052",  "uns a95052"],
    "5083":       ["aa5083",  "uns a95083"],
    "5086":       ["aa5086",  "uns a95086"],
    "5454":       ["aa5454",  "uns a95454"],
    "1100":       ["aa1100",  "uns a91100"],
    "1050":       ["aa1050",  "uns a91050"],
    "3003":       ["aa3003",  "uns a93003"],
    "a356":       ["a03560",  "uns a03560"],
    "a357":       ["a03570",  "uns a03570"],
    "a380":       ["a03800",  "uns a03800"],

    # ── Steel (AISI/SAE → canonical) ──
    "aisi 1018":  ["uns g10180", "1018"],
    "aisi 1020":  ["uns g10200", "1020"],
    "aisi 1045":  ["uns g10450", "1045"],
    "aisi 1080":  ["uns g10800", "1080"],
    "aisi 4130":  ["uns g41300", "4130", "scm430", "30crmo4"],
    "aisi 4140":  ["uns g41400", "4140", "scm440", "42crmo4", "1.7225"],
    "aisi 4340":  ["uns g43400", "4340", "snm439", "1.6582"],
    "aisi 304":   ["uns s30400", "304",  "1.4301", "sus 304"],
    "aisi 316":   ["uns s31600", "316",  "1.4401", "sus 316"],
    "aisi 410":   ["uns s41000", "410",  "1.4006"],
    "aisi 420":   ["uns s42000", "420",  "1.4021"],
    "aisi 431":   ["uns s43100", "431"],
    "17-4 ph":    ["uns s17400", "17-4ph", "17-4 ph", "stainless 17-4"],
    "17-7 ph":    ["uns s17700", "17-7ph", "17-7 ph"],
    "ph 13-8 mo": ["uns s13800", "13-8 ph", "ph13-8mo"],

    # ── Titanium (ASTM Grade → canonical) ──
    "grade 1":    ["cp ti gr1", "astm gr1", "cp-ti-1"],
    "grade 2":    ["cp ti gr2", "astm gr2", "cp-ti-2"],
    "grade 3":    ["cp ti gr3", "astm gr3", "cp-ti-3"],
    "grade 4":    ["cp ti gr4", "astm gr4", "cp-ti-4"],
    "grade 5":    ["ti-6al-4v", "ti 6-4", "ti64", "ti-6-4"],
    "grade 23":   ["ti-6al-4v eli", "ti64 eli"],
    "grade 7":    ["ti-pd",   "ti-0.15pd"],

    # ── Nickel (trade name → canonical) ──
    "inconel 600":    ["uns n06600", "alloy 600", "in 600"],
    "inconel 601":    ["uns n06601", "alloy 601", "in 601"],
    "inconel 625":    ["uns n06625", "alloy 625", "in 625"],
    "inconel 690":    ["uns n06690", "alloy 690"],
    "inconel 706":    ["uns n09706", "alloy 706"],
    "inconel 718":    ["uns n07718", "alloy 718"],
    "inconel x-750":  ["uns n07750", "x-750",   "x750"],
    "hastelloy c-276":["uns n10276", "alloy c-276"],
    "hastelloy x":    ["uns n06002", "alloy x"],
    "waspaloy":       ["uns n07001"],
    "rene 41":        ["uns n07041", "r-41"],
    "rene 80":        ["uns n07080"],
    "udimet 500":     ["u-500", "u500"],
    "udimet 700":     ["u-700", "u700"],
    "cmsx-4":         ["pwa-1486"],     # very close compositions; track if real
}


def _normalise(s: str) -> str:
    """Lower-case, strip dashes/spaces/periods."""
    return re.sub(r"[\s\-\.]+", " ", s.strip().lower())


def canonical_name(designation: str) -> str:
    """Return the canonical key for a free-form alloy designation.

    Strips trailing temper codes (everything after a hyphen or whitespace
    starting with T/H/O/F/W or matching a known temper pattern) so that
    e.g. ``"6061-T6"`` and ``"AA6061-O"`` both map to ``"6061"``.

    >>> canonical_name("6061-T6")
    '6061'
    >>> canonical_name("AA6061-T651")
    '6061'
    >>> canonical_name("AISI 4140 Q&T")
    'aisi 4140'
    >>> canonical_name("UNS A92024-T81")
    '2024'
    """
    n = _normalise(designation)

    # Strip common trailing temper codes
    n = re.sub(r"\s+(t\d+\w*|h\d+\w*|o|f|w\d*|q&t|annealed|sta|hardened|aged.*)$", "", n)
    # Strip parenthetical
    n = re.sub(r"\s*\([^)]*\)\s*", " ", n).strip()

    # Reverse-lookup in aliases
    for canonical, aliases in _ALIASES.items():
        if n == canonical:
            return canonical
        if n in aliases:
            return canonical
        # Allow loose matching: "aa6061" or "a96061" with the digits
        for alias in aliases:
            if _normalise(alias) == n:
                return canonical
    return n


def list_aliases(canonical: str) -> list:
    """Return all known aliases for a canonical designation."""
    return list(_ALIASES.get(canonical, []))
