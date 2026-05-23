"""
Bayesian multi-objective inverse design.

Uses BoTorch's qExpectedHypervolumeImprovement (qEHVI) acquisition with
SingleTaskGP surrogates, one per objective. Search proceeds:
  1. Sobol-sequence initial design (n_init points)
  2. Fit GPs to (X, Y_objectives)
  3. qEHVI proposes a batch of points balancing improvement of the Pareto front
  4. Evaluate via predict_properties, append, repeat for n_iterations

Falls back to random Dirichlet search if BoTorch fails (single-objective
problems, GP fitting issues, etc.)
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class PropertyTarget:
    name: str
    min_val: float | None = None
    max_val: float | None = None
    optimize: str = "maximize"  # "maximize" | "minimize" | "range"


@dataclass
class InverseDesignRequest:
    elements: list[str]
    targets: list[PropertyTarget]
    n_candidates: int = 12
    n_iterations: int = 5        # BO rounds after Sobol seed
    n_init: int = 16             # Sobol seed size
    batch_size: int = 4          # acquisitions per round
    seed: int = 42
    # Optional per-element bounds on the raw search variable. The composition
    # is renormalised to sum to 1 at evaluation time, so these are *biases* on
    # the simplex direction, not exact atomic-% bounds. Use large lower bounds
    # on majority elements to force a particular family (e.g. Ti=[5,10] others=[1e-3, 1]).
    element_bounds: dict[str, tuple[float, float]] | None = None


@dataclass
class Candidate:
    composition: dict[str, float]
    properties: dict[str, Any]
    pareto_rank: int = 0
    score: float = 0.0
    is_pareto: bool = False
    method: str = "bo_qehvi"


# ─────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────

def _normalize_to_composition(x: np.ndarray, elements: list[str]) -> dict[str, float]:
    """Renormalise an [0,1]^n vector to a composition dict summing to 100."""
    vals = np.asarray(x, dtype=float).flatten()
    s = vals.sum()
    if s <= 0:
        return {el: round(100.0 / len(elements), 2) for el in elements}
    normalised = vals / s * 100.0
    return {el: round(float(v), 2) for el, v in zip(elements, normalised)}


def _objective_value(prop_value: Any, target: PropertyTarget) -> float | None:
    """Convert raw property value → maximisation objective for BoTorch."""
    if prop_value is None:
        return None
    v = float(prop_value)
    if target.optimize == "maximize":
        # Reward exceeding min_val; higher value = better
        if target.min_val is not None:
            return v - target.min_val
        return v
    if target.optimize == "minimize":
        # Reward being below max_val; we maximise the negative
        if target.max_val is not None:
            return target.max_val - v
        return -v
    if target.optimize == "range":
        if target.min_val is None or target.max_val is None:
            return -abs(v)
        mid = (target.min_val + target.max_val) / 2
        width = max((target.max_val - target.min_val) / 2, 1e-6)
        # Distance-to-midpoint; closer to mid = higher value
        return -abs(v - mid) / width
    return None


def _aggregate_score(props: dict, targets: list[PropertyTarget]) -> float:
    s = 0.0
    for t in targets:
        v = _objective_value(props.get(t.name), t)
        if v is not None:
            s += v
    return s


# ─────────────────────────────────────────────────────────────────────────
# BoTorch driver (the real Bayesian optimisation)
# ─────────────────────────────────────────────────────────────────────────

def _run_bo(request: InverseDesignRequest) -> list[Candidate] | None:
    """
    Returns a list of candidates from BoTorch qEHVI, or None if BO is
    inapplicable / fails (caller will fall back to random search).
    """
    try:
        import torch
        from botorch.fit import fit_gpytorch_mll
        from botorch.models import SingleTaskGP, ModelListGP
        from botorch.models.transforms import Standardize
        from botorch.acquisition.multi_objective.monte_carlo import qExpectedHypervolumeImprovement
        from botorch.utils.multi_objective.box_decompositions.non_dominated import FastNondominatedPartitioning
        from botorch.utils.multi_objective.pareto import is_non_dominated
        from botorch.utils.sampling import draw_sobol_samples
        from botorch.optim.optimize import optimize_acqf
        from botorch.sampling.normal import SobolQMCNormalSampler
        from gpytorch.mlls import SumMarginalLogLikelihood
    except ImportError:
        return None

    from apps.api.ml.matgl_models import predict_properties

    n_dim = len(request.elements)
    n_obj = len(request.targets)
    if n_obj < 2 or n_dim < 2:
        return None  # qEHVI needs ≥2 objectives and ≥2 design dims

    torch.manual_seed(request.seed)
    np.random.seed(request.seed)

    tkwargs = {"dtype": torch.double, "device": "cpu"}
    if request.element_bounds:
        lower = [request.element_bounds.get(el, (1e-3, 1.0))[0] for el in request.elements]
        upper = [request.element_bounds.get(el, (1e-3, 1.0))[1] for el in request.elements]
    else:
        lower = [1e-3] * n_dim
        upper = [1.0] * n_dim
    bounds = torch.tensor([lower, upper], **tkwargs)

    # ── 1. Sobol seed ─────────────────────────────────────────────────
    X = draw_sobol_samples(bounds=bounds, n=request.n_init, q=1, seed=request.seed).squeeze(1).to(**tkwargs)
    compositions: list[dict[str, float]] = []
    properties_list: list[dict[str, Any]] = []
    obj_rows: list[list[float]] = []

    for i in range(X.shape[0]):
        comp = _normalize_to_composition(X[i].cpu().numpy(), request.elements)
        props = predict_properties(comp)
        compositions.append(comp)
        properties_list.append(props)
        obj_rows.append([_objective_value(props.get(t.name), t) or -1e6 for t in request.targets])

    Y = torch.tensor(obj_rows, **tkwargs)

    # ── 2. BO loop ────────────────────────────────────────────────────
    for it in range(request.n_iterations):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                models = [SingleTaskGP(X, Y[:, i:i+1], outcome_transform=Standardize(m=1)) for i in range(n_obj)]
                model = ModelListGP(*models)
                mll = SumMarginalLogLikelihood(model.likelihood, model)
                fit_gpytorch_mll(mll)

                # Reference point slightly below worst evaluated point per objective
                ref_point = (Y.min(dim=0).values - 0.1 * (Y.max(dim=0).values - Y.min(dim=0).values + 1e-6)).tolist()

                partitioning = FastNondominatedPartitioning(
                    ref_point=torch.tensor(ref_point, **tkwargs),
                    Y=Y,
                )
                sampler = SobolQMCNormalSampler(sample_shape=torch.Size([64]))
                acqf = qExpectedHypervolumeImprovement(
                    model=model,
                    ref_point=ref_point,
                    partitioning=partitioning,
                    sampler=sampler,
                )

                new_X, _ = optimize_acqf(
                    acq_function=acqf,
                    bounds=bounds,
                    q=request.batch_size,
                    num_restarts=8,
                    raw_samples=128,
                    sequential=True,
                )
                new_X = new_X.to(**tkwargs)
        except Exception as exc:
            print(f"[BO iter {it}] acquisition failed → continuing with collected data: {exc}")
            break

        # Evaluate new points
        new_obj_rows = []
        for i in range(new_X.shape[0]):
            comp = _normalize_to_composition(new_X[i].cpu().numpy(), request.elements)
            props = predict_properties(comp)
            compositions.append(comp)
            properties_list.append(props)
            new_obj_rows.append([_objective_value(props.get(t.name), t) or -1e6 for t in request.targets])

        X = torch.cat([X, new_X])
        Y = torch.cat([Y, torch.tensor(new_obj_rows, **tkwargs)])

    # ── 3. Pareto identification ──────────────────────────────────────
    pareto_mask = is_non_dominated(Y).cpu().numpy()

    # ── 4. Build candidate list, sort Pareto-first then by aggregate score
    candidates: list[Candidate] = []
    for i in range(len(compositions)):
        agg = _aggregate_score(properties_list[i], request.targets)
        candidates.append(Candidate(
            composition=compositions[i],
            properties=properties_list[i],
            score=agg,
            is_pareto=bool(pareto_mask[i]),
            method="bo_qehvi",
        ))

    candidates.sort(key=lambda c: (not c.is_pareto, -c.score))
    for rank, c in enumerate(candidates, start=1):
        c.pareto_rank = rank

    return candidates[: request.n_candidates]


# ─────────────────────────────────────────────────────────────────────────
# Random-search fallback (kept for robustness)
# ─────────────────────────────────────────────────────────────────────────

def _run_random_search(request: InverseDesignRequest) -> list[Candidate]:
    from apps.api.ml.matgl_models import predict_properties

    rng = np.random.default_rng(request.seed)
    n = max(request.n_candidates * 3, 30)
    compositions = []
    for _ in range(n):
        fracs = rng.dirichlet(np.ones(len(request.elements)))
        compositions.append({el: round(float(f) * 100, 2) for el, f in zip(request.elements, fracs)})

    cands = []
    for comp in compositions:
        props = predict_properties(comp)
        agg = _aggregate_score(props, request.targets)
        cands.append(Candidate(composition=comp, properties=props, score=agg, method="random_search"))

    cands.sort(key=lambda c: -c.score)
    for rank, c in enumerate(cands[: request.n_candidates], start=1):
        c.pareto_rank = rank
        c.is_pareto = rank == 1
    return cands[: request.n_candidates]


# ─────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────

def run_inverse_design(request: InverseDesignRequest) -> list[Candidate]:
    """Try BoTorch qEHVI first; fall back to random search on failure."""
    result = _run_bo(request)
    if result is not None and len(result) > 0:
        return result
    print("[inverse_design] BoTorch unavailable / inapplicable — falling back to random search")
    return _run_random_search(request)
