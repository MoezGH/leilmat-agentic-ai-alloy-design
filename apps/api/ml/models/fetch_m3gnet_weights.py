"""
Fetch the M3GNet-Eform-MP-2018.6.1 checkpoint for the formation-energy
predictor and vendor it into the image at build time.

Why this exists
---------------
History: we used to pin ``matgl==1.1.3``, whose
``load_model("M3GNet-Eform-MP-2018.6.1")`` downloaded the checkpoint from
``github.com/materialsvirtuallab/matgl/raw/main/pretrained_models/…`` — a
path matgl deleted when it moved model hosting to the Hugging Face Hub. That
URL 404'd, so a fresh process couldn't load M3GNet and the predictor silently
fell back to a Miedema heuristic (≈ no better than predicting zero — see
docs/SCORECARD.md Appendix C). This was caught by the MP formation-energy
stress test.

We have since migrated to ``matgl==4.0.2`` (pyg-era, no dgl), whose named
load fetches from the HF ``materialyze`` org and would work online. We keep
vendoring the weights anyway so a cold start never depends on a live network
call (and so the build is reproducible). matgl 4.x is also the version that
can actually deserialize these (current-format) weights — matgl 1.1.3 could
not read them ("Bad serialized model").

Provenance / trust
------------------
The weights are the SAME canonical checkpoint, rehosted by the matgl
maintainers' own org:
  * ``materialsvirtuallab/m3gnet`` (GitHub) was transferred to
    ``materialyzeai/m3gnet``; the team rebranded model distribution to
    "Materialyze".
  * matgl's current source (``materialsvirtuallab/matgl`` main) loads
    pretrained models from the Hugging Face ``materialyze/`` org — i.e.
    the official matgl package fetches these exact files from here.
So ``materialyze/M3GNet-Eform-MP-2018.6.1`` on HF is the canonical source,
not a third-party mirror.

Run at Docker build (best-effort): if the fetch fails, the loader falls
back to matgl's remote path (and ultimately the Miedema heuristic), so a
build never hard-fails on this.
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

HF_BASE = "https://huggingface.co/materialyze/M3GNet-Eform-MP-2018.6.1/resolve/main"
FILES = ["model.json", "model.pt", "state.pt"]
DEST = Path(__file__).parent / "M3GNet-Eform-MP-2018.6.1"


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    for fname in FILES:
        target = DEST / fname
        if target.exists() and target.stat().st_size > 0:
            print(f"[fetch_m3gnet] {fname} already present — skipping")
            continue
        url = f"{HF_BASE}/{fname}"
        print(f"[fetch_m3gnet] downloading {url}")
        try:
            urllib.request.urlretrieve(url, target)
        except Exception as exc:  # best-effort — loader falls back if missing
            print(f"[fetch_m3gnet] WARN: failed to fetch {fname}: {exc}")
            return 1
    # Sanity: model.json must be valid JSON, not an HTML error page.
    try:
        import json
        json.loads((DEST / "model.json").read_text())
    except Exception as exc:
        print(f"[fetch_m3gnet] WARN: model.json invalid ({exc}); removing dir")
        for f in FILES:
            (DEST / f).unlink(missing_ok=True)
        return 1
    print(f"[fetch_m3gnet] OK — weights in {DEST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
