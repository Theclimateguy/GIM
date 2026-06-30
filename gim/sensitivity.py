"""Global sensitivity analysis: Morris screening + Sobol variance decomposition (Phase 1-D).

Two standard methods, implemented natively on numpy and validated against the analytical
Ishigami benchmark (see tests/test_sensitivity.py):

- **Morris elementary effects** (Morris 1991; Campolongo et al. 2007): cheap screening over
  many factors. Reports mu* (mean |elementary effect|, ~ overall influence) and sigma
  (~ non-linearity / interaction). Cost: r*(D+1) model runs.
- **Sobol indices** (Sobol 2001; Saltelli et al. 2010 estimators): variance decomposition on
  the reduced influential set. Reports S1 (first-order) and ST (total, incl. interactions).
  Cost: N*(D+2) model runs.

The model is wrapped as a deterministic scalar function of a parameter vector (the world RNG
is held at a fixed seed, so sensitivity reflects parameters, not stochastic noise). Factor
ranges are the prior [low, high] bounds.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .core.params import default_params
from .core.policy import make_policy_map
from .core.priors import Prior
from .core.rng import seed_world
from .core.simulation import step_world
from .core.world_factory import make_world_from_csv

# A model-output function maps {param_name: value} -> scalar output.
OutputFn = Callable[[Dict[str, float]], float]


def _scale(unit: np.ndarray, bounds: Sequence[Tuple[float, float]]) -> np.ndarray:
    low = np.array([b[0] for b in bounds], dtype=float)
    high = np.array([b[1] for b in bounds], dtype=float)
    return low + unit * (high - low)


def morris(
    names: Sequence[str],
    bounds: Sequence[Tuple[float, float]],
    func: OutputFn,
    r: int = 10,
    levels: int = 4,
    seed: int = 0,
) -> Dict[str, Dict[str, float]]:
    """Morris elementary-effects screening. Returns {name: {mu_star, mu, sigma}}."""
    rng = np.random.default_rng(seed)
    D = len(names)
    p = levels
    delta = p / (2.0 * (p - 1))
    B = np.tril(np.ones((D + 1, D)), -1)
    Jm = np.ones((D + 1, D))
    grid = np.arange(0.0, 1.0 - delta + 1e-9, 1.0 / (p - 1))

    effects: List[List[float]] = [[] for _ in range(D)]
    for _ in range(r):
        xstar = rng.choice(grid, size=D)
        Dstar = np.diag(rng.choice([-1.0, 1.0], size=D))
        perm = rng.permutation(D)
        Pstar = np.eye(D)[perm]
        Bstar = (Jm * xstar + (delta / 2.0) * ((2.0 * B - Jm) @ Dstar + Jm)) @ Pstar
        Bstar = np.clip(Bstar, 0.0, 1.0)
        X = _scale(Bstar, bounds)
        Y = np.array([func({n: float(v) for n, v in zip(names, row)}) for row in X])
        for k in range(D):
            diff = Bstar[k + 1] - Bstar[k]
            j = int(np.argmax(np.abs(diff)))
            step = diff[j]
            if step != 0.0:
                effects[j].append(float((Y[k + 1] - Y[k]) / step))

    out: Dict[str, Dict[str, float]] = {}
    for j, name in enumerate(names):
        arr = np.array(effects[j]) if effects[j] else np.array([0.0])
        out[name] = {
            "mu_star": float(np.mean(np.abs(arr))),
            "mu": float(np.mean(arr)),
            "sigma": float(np.std(arr)),
        }
    return out


def sobol(
    names: Sequence[str],
    bounds: Sequence[Tuple[float, float]],
    func: OutputFn,
    n_base: int = 256,
    seed: int = 0,
) -> Dict[str, Dict[str, float]]:
    """Sobol first-order (S1) and total (ST) indices (Saltelli 2010 / Jansen estimators)."""
    rng = np.random.default_rng(seed)
    D = len(names)
    A = rng.random((n_base, D))
    Bm = rng.random((n_base, D))

    def _eval(M: np.ndarray) -> np.ndarray:
        X = _scale(M, bounds)
        return np.array([func({n: float(v) for n, v in zip(names, row)}) for row in X])

    yA = _eval(A)
    yB = _eval(Bm)
    var = float(np.var(np.concatenate([yA, yB])))
    out: Dict[str, Dict[str, float]] = {}
    if var <= 0.0:
        return {n: {"S1": 0.0, "ST": 0.0} for n in names}
    for i in range(D):
        ABi = A.copy()
        ABi[:, i] = Bm[:, i]
        yABi = _eval(ABi)
        s1 = float(np.mean(yB * (yABi - yA)) / var)          # Saltelli 2010
        st = float(0.5 * np.mean((yA - yABi) ** 2) / var)     # Jansen 2010
        out[names[i]] = {"S1": s1, "ST": st}
    return out


def make_output_fn(
    output_metric: str,
    state_csv: str,
    years: int = 10,
    max_agents: int = 100,
    base_year: int = 2023,
    seed: int = 2026,
) -> OutputFn:
    """Wrap the model as a deterministic scalar function of a parameter-override vector."""
    base = default_params()

    def _metric(world) -> float:
        agents = world.agents.values()
        if output_metric == "temperature":
            return float(world.global_state.temperature_global)
        if output_metric == "co2":
            return float(world.global_state.co2)
        if output_metric == "world_gdp":
            return float(sum(a.economy.gdp for a in agents))
        if output_metric == "mean_social_tension":
            t = [a.society.social_tension for a in agents]
            return float(sum(t) / len(t)) if t else 0.0
        raise ValueError(f"Unknown output metric: {output_metric}")

    def fn(overrides: Dict[str, float]) -> float:
        ps = base.with_overrides(overrides)
        world = make_world_from_csv(state_csv, max_agents=max_agents, base_year=base_year)
        world.params = ps
        seed_world(world, seed)  # fixed RNG seed: output is a deterministic function of params
        policies = make_policy_map(world.agents.keys(), mode="simple")
        for _ in range(years):
            step_world(world, policies)
        return _metric(world)

    return fn


def rank(result: Dict[str, Dict[str, float]], by: str = "mu_star") -> List[Tuple[str, float]]:
    return sorted(((n, d[by]) for n, d in result.items()), key=lambda kv: kv[1], reverse=True)


def bounds_for(priors: Dict[str, Prior], names: Sequence[str]) -> List[Tuple[float, float]]:
    return [(priors[n].low, priors[n].high) for n in names]


__all__ = ["morris", "sobol", "make_output_fn", "rank", "bounds_for", "OutputFn"]
