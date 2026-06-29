"""Monte-Carlo ensemble runtime for uncertainty quantification (Phase 1-C).

Draws parameter vectors from the literature-grounded priors (`gim.core.priors`), attaches
each as a per-run ``world.params`` context, runs N independent fully-seeded worlds, and
aggregates the trajectories into percentile fan bands for the headline indicators.

Members are independent and deterministic: member ``i`` is seeded from
``(master_seed, i)``, so the whole ensemble is reproducible and order-independent — it can
run serially or across processes with identical results. This relies on Phase-0 determinism
(world-scoped RNG) and Phase-1-A parameter isolation (no global mutation).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

from .core.params import default_params
from .core.priors import all_priors, key_priors, sample_parameter_set
from .core.policy import make_policy_map
from .core.rng import seed_world
from .core.simulation import step_world
from .core.world_factory import make_world_from_csv

# Headline indicators tracked per simulated year for fan charts.
METRICS: tuple[str, ...] = (
    "world_gdp",
    "world_population",
    "temperature",
    "co2",
    "n_debt_crises",
    "n_regime_crises",
    "n_wars",
    "mean_social_tension",
)

DEFAULT_PERCENTILES: tuple[float, ...] = (5.0, 25.0, 50.0, 75.0, 95.0)


@dataclass(frozen=True)
class EnsembleConfig:
    state_csv: str
    n_members: int = 500
    years: int = 10
    base_year: int = 2026
    max_agents: int = 100
    master_seed: int = 2026
    prior_set: str = "key"  # "key" (literature core) or "all" (adds long tail)
    n_jobs: int = 0  # 0 => auto (cpu_count), 1 => serial


def _member_seed(master_seed: int, index: int) -> int:
    return (int(master_seed) * 1_000_003 + int(index)) & 0x7FFFFFFF


def _collect_metrics(world) -> Dict[str, float]:
    agents = world.agents.values()
    gs = world.global_state
    n_debt = sum(1 for a in agents if getattr(a.risk, "debt_crisis_active_years", 0) > 0)
    n_regime = sum(1 for a in agents if getattr(a.risk, "regime_crisis_active_years", 0) > 0)
    war_pairs = 0
    for rels in world.relations.values():
        for rel in rels.values():
            if getattr(rel, "at_war", False):
                war_pairs += 1
    tensions = [a.society.social_tension for a in agents]
    return {
        "world_gdp": float(sum(a.economy.gdp for a in agents)),
        "world_population": float(sum(a.economy.population for a in agents)),
        "temperature": float(gs.temperature_global),
        "co2": float(gs.co2),
        "n_debt_crises": float(n_debt),
        "n_regime_crises": float(n_regime),
        "n_wars": float(war_pairs // 2),  # directed relations -> undirected pairs
        "mean_social_tension": float(sum(tensions) / len(tensions)) if tensions else 0.0,
    }


def _run_member(args: Dict[str, Any]) -> List[Dict[str, float]]:
    """Run one ensemble member; returns a per-year list of metric dicts (years+1 entries)."""
    cfg: EnsembleConfig = args["config"]
    index: int = args["index"]
    seed = _member_seed(cfg.master_seed, index)

    priors = key_priors() if cfg.prior_set == "key" else all_priors()
    import random

    sampled = sample_parameter_set(default_params(), priors, random.Random(seed))

    world = make_world_from_csv(cfg.state_csv, max_agents=cfg.max_agents, base_year=cfg.base_year)
    world.params = sampled
    seed_world(world, seed)
    policies = make_policy_map(world.agents.keys(), mode="simple")

    trajectory = [_collect_metrics(world)]
    for _ in range(cfg.years):
        step_world(world, policies)
        trajectory.append(_collect_metrics(world))
    return trajectory


def _percentile(sorted_values: Sequence[float], pct: float) -> float:
    if not sorted_values:
        return float("nan")
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    rank = (pct / 100.0) * (len(sorted_values) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = rank - lo
    return float(sorted_values[lo] * (1.0 - frac) + sorted_values[hi] * frac)


@dataclass
class EnsembleResult:
    config: EnsembleConfig
    years: List[int]
    bands: Dict[str, Dict[str, List[float]]]  # metric -> {"p5","p25","p50","p75","p95","mean"} -> per-year
    n_members: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "config": {
                "state_csv": self.config.state_csv,
                "n_members": self.config.n_members,
                "years": self.config.years,
                "base_year": self.config.base_year,
                "max_agents": self.config.max_agents,
                "master_seed": self.config.master_seed,
                "prior_set": self.config.prior_set,
            },
            "years": self.years,
            "n_members": self.n_members,
            "metrics": self.bands,
            "percentiles": list(DEFAULT_PERCENTILES),
        }


def _aggregate(trajectories: List[List[Dict[str, float]]], years: int) -> Dict[str, Dict[str, List[float]]]:
    bands: Dict[str, Dict[str, List[float]]] = {}
    keys = ["p5", "p25", "p50", "p75", "p95", "mean"]
    for metric in METRICS:
        series: Dict[str, List[float]] = {k: [] for k in keys}
        for t in range(years + 1):
            vals = sorted(traj[t][metric] for traj in trajectories)
            for pct, key in zip(DEFAULT_PERCENTILES, ["p5", "p25", "p50", "p75", "p95"]):
                series[key].append(_percentile(vals, pct))
            series["mean"].append(sum(vals) / len(vals) if vals else float("nan"))
        bands[metric] = series
    return bands


def run_ensemble(
    config: EnsembleConfig,
    progress: Optional[Callable[[int, int], None]] = None,
) -> EnsembleResult:
    """Run the Monte-Carlo ensemble and return percentile fan bands."""
    n = config.n_members
    args = [{"config": config, "index": i} for i in range(n)]

    n_jobs = config.n_jobs or (os.cpu_count() or 1)
    trajectories: List[Optional[List[Dict[str, float]]]] = [None] * n

    if n_jobs <= 1:
        for i, a in enumerate(args):
            trajectories[i] = _run_member(a)
            if progress:
                progress(i + 1, n)
    else:
        from concurrent.futures import ProcessPoolExecutor, as_completed

        with ProcessPoolExecutor(max_workers=n_jobs) as ex:
            futures = {ex.submit(_run_member, a): a["index"] for a in args}
            done = 0
            for fut in as_completed(futures):
                idx = futures[fut]
                trajectories[idx] = fut.result()
                done += 1
                if progress:
                    progress(done, n)

    completed = [t for t in trajectories if t is not None]
    bands = _aggregate(completed, config.years)
    return EnsembleResult(
        config=config,
        years=list(range(config.years + 1)),
        bands=bands,
        n_members=len(completed),
    )


__all__ = ["EnsembleConfig", "EnsembleResult", "run_ensemble", "METRICS", "DEFAULT_PERCENTILES"]
