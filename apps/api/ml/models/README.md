# Vendored ML model weights

## M3GNet-Eform-MP-2018.6.1

Formation-energy checkpoint for `m3gnet_predictor.py`.

**Not committed** (weights are gitignored — `*.pt` + this dir's `model.json`).
They are fetched at Docker build time by `fetch_m3gnet_weights.py`, which
downloads them from the Hugging Face Hub:

    https://huggingface.co/materialyze/M3GNet-Eform-MP-2018.6.1

### Why vendored instead of matgl's auto-download

History: `matgl==1.1.3`'s `load_model("M3GNet-Eform-MP-2018.6.1")` fetched
from a `github.com/materialsvirtuallab/matgl/raw/main/pretrained_models/…`
path that **no longer exists** (matgl moved model hosting to the HF
`materialyze` org). The dead URL meant a fresh process couldn't load M3GNet
and the predictor silently degraded to a Miedema heuristic — caught by the MP
formation-energy stress test (see `docs/SCORECARD.md`).

We have since migrated to **`matgl==4.0.2`** (pyg-era, no dgl), which is also
the version that can actually *deserialize* these current-format weights
(matgl 1.1.3 raised "Bad serialized model"). matgl 4.x's named load would now
fetch from HF, but we keep vendoring + loading by local path so a cold start
never depends on a live network call and the build stays reproducible.

### Provenance

`materialyze` is the matgl maintainers' own org: `materialsvirtuallab/m3gnet`
was transferred to `materialyzeai/m3gnet`, and matgl's current source loads
pretrained models from the HF `materialyze/` namespace. These are the same
canonical files matgl 1.1.3 was designed to load, just rehosted.

To fetch locally: `python apps/api/ml/models/fetch_m3gnet_weights.py`
