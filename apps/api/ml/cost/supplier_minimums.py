"""
apps.api.ml.cost.supplier_minimums
====================================

Lot-size adjustment via supplier-minimum overhead.

Specialty alloys (Ni-base, Ti, PH-stainless, Co-base) carry a fixed
"per-pour" minimum charge from mill or distributor.  This is the cost
of melting a fresh heat, certifying it, and changing over the line —
it doesn't scale with how much you actually buy.  For small orders
(say 25 kg of a custom-spec alloy) the minimum charge can DOUBLE the
effective $/kg.

Per-pour minimums by family (USD), based on Sandvik / TIMET / Carpenter
RFQ data:

* Plain-carbon / low-alloy steel:  ~  $200 / pour
* Stainless steel:                 ~  $500 / pour
* PH-stainless / tool steel:       ~$1,500 / pour
* Aluminum (commercial):           ~  $300 / pour
* Aluminum (aerospace):            ~$1,000 / pour
* Titanium:                        ~$2,500 / pour
* Nickel superalloy:               ~$3,000 / pour
* Cobalt-base superalloy:          ~$3,500 / pour
* Refractory (Re, Ta, Nb-rich):    ~$5,000 / pour
"""
MINIMUM_OVERHEAD_USD: dict[str, float] = {
    "plain_carbon_steel":  200.0,
    "low_alloy_steel":     250.0,
    "stainless":           500.0,
    "ph_stainless":       1500.0,
    "tool_steel":         1500.0,
    "aluminum_commercial": 300.0,
    "aluminum_aerospace":1000.0,
    "titanium":           2500.0,
    "nickel":             3000.0,
    "cobalt":             3500.0,
    "copper":              400.0,
    "magnesium":           500.0,
    "refractory":         5000.0,
}


def overhead_for_family(family: str) -> float:
    """Return the minimum-pour overhead (USD) for *family*."""
    return MINIMUM_OVERHEAD_USD.get(family, 500.0)


def classify_family(composition: dict[str, float], cert: str) -> str:
    """Pick the right minimum-overhead bucket from composition + cert.

    Returns one of the keys in ``MINIMUM_OVERHEAD_USD``.
    """
    total = sum(composition.values())
    if total <= 0:
        return "plain_carbon_steel"
    fracs = {el: v / total for el, v in composition.items()}

    # Refractory: Re or Ta alone ≥ 2 wt% (Nb up to ~5% is normal in
    # standard Ni superalloys like IN 718 and isn't a refractory marker).
    if fracs.get("Re", 0) >= 0.02 or fracs.get("Ta", 0) >= 0.02:
        return "refractory"
    if fracs.get("Ni", 0) >= 0.40:
        return "nickel"
    if fracs.get("Co", 0) >= 0.30:
        return "cobalt"
    if fracs.get("Ti", 0) >= 0.50:
        return "titanium"
    if fracs.get("Mg", 0) >= 0.50:
        return "magnesium"
    if fracs.get("Cu", 0) >= 0.50:
        return "copper"
    if fracs.get("Al", 0) >= 0.80:
        if cert in ("AMS", "AMS_class_I", "AMS_class_II", "MIL-DTL"):
            return "aluminum_aerospace"
        return "aluminum_commercial"
    if fracs.get("Fe", 0) >= 0.50:
        # Steel sub-family classification
        cr = fracs.get("Cr", 0)
        c  = fracs.get("C",  0)
        cu = fracs.get("Cu", 0)
        ni = fracs.get("Ni", 0)
        # PH-stainless: Cr 12-17 % AND (Cu > 3 % OR Ni > 5 %)
        if 0.12 <= cr <= 0.18 and (cu >= 0.03 or ni >= 0.05):
            return "ph_stainless"
        # Stainless (Cr ≥ 10.5 %)
        if cr >= 0.105:
            return "stainless"
        # Tool steel: V or W > 0.5 % or C > 0.8 %
        if (fracs.get("V", 0) >= 0.005 or fracs.get("W", 0) >= 0.005 or c >= 0.008):
            return "tool_steel"
        # Low-alloy: any Cr, Mo, Ni > 0.3 %
        if (cr >= 0.003 or fracs.get("Mo", 0) >= 0.003 or ni >= 0.003):
            return "low_alloy_steel"
        return "plain_carbon_steel"
    return "plain_carbon_steel"


def overhead_per_kg(family_key: str, lot_kg: float) -> float:
    """Per-kg amortisation of the minimum pour fee over the lot."""
    if lot_kg <= 0:
        return 0.0
    return overhead_for_family(family_key) / float(lot_kg)
