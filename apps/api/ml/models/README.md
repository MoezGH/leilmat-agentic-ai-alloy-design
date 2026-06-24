# Vendored ML model weights

## M3GNet-Eform-MP-2018.6.1

Formation-energy checkpoint for `m3gnet_predictor.py`.

**Not committed** (weights are gitignored — `*.pt` + this dir's `model.json`).
They are fetched at Docker build time by `fetch_m3gnet_weights.py`, which
downloads them from the Hugging Face Hub:

    https://huggingface.co/materialyze/M3GNet-Eform-MP-2018.6.1

### Why vendored instead of matgl's auto-download

`matgl==1.1.3`'s `load_model("M3GNet-Eform-MP-2018.6.1")` fetches from a
`github.com/materialsvirtuallab/matgl/raw/main/pretrained_models/…` path
that **no longer exists** (matgl moved model hosting to the HF `materialyze`
org; matgl is now at 4.x). The dead URL means a fresh process can't load
M3GNet and the predictor silently degrades to a Miedema heuristic — caught
by the MP formation-energy stress test (see `docs/SCORECARD.md`). Vendoring
the weights + loading by local path makes M3GNet load offline-reliably with
no dependency bump.

### Provenance

`materialyze` is the matgl maintainers' own org: `materialsvirtuallab/m3gnet`
was transferred to `materialyzeai/m3gnet`, and matgl's current source loads
pretrained models from the HF `materialyze/` namespace. These are the same
canonical files matgl 1.1.3 was designed to load, just rehosted.

To fetch locally: `python apps/api/ml/models/fetch_m3gnet_weights.py`
