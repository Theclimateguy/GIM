"""Dose-response sweep for the v2 line (THE-65 / THE-69).

Sweeps one grounded lever's magnitude over a grid and reports the **terminal
delta** (scenario − baseline) of a metric — the model's non-zero slope where
sectoral models are flat (Fig. 6–9). Reuses the same frozen member runner and the
same baseline as :func:`gim2.scenario.compute_scenario`, so a dose point at the
selected magnitude equals the corresponding scenario delta.
"""

from __future__ import annotations

import shlex
import threading
from typing import Any, Dict, List, Optional, Sequence

from gim.ensemble import METRICS, _percentile

from . import SCHEMA
from . import levers as L
from . import projections as P
from .scenario import Progress, baseline_trajectories, build_config, run_trajectories


def _median(values: Sequence[float]) -> float:
    return _percentile(sorted(values), 50.0)


def compute_dose(
    *, state_csv=None, lever: str, grid=(0.0, 0.25, 0.5, 0.75, 1.0, 1.25), metric="world_gdp",
    actors=None, members=120, years=10, max_agents=100, seed=2026,
    progress: Progress = None, cancel: Optional[threading.Event] = None,
) -> Dict[str, Any]:
    if lever not in L.GROUNDED_LEVERS:
        raise ValueError(f"unknown lever {lever!r}; allowed: {', '.join(sorted(L.GROUNDED_LEVERS))}")
    if metric not in METRICS:
        raise ValueError(f"unknown metric {metric!r}; allowed: {', '.join(METRICS)}")

    config = build_config(state_csv=state_csv, members=members, years=years,
                          max_agents=max_agents, seed=seed, prior_set="key", jobs=0)
    grid = [float(g) for g in grid]
    total = (len(grid) + 1) * config.n_members  # baseline + one ensemble per grid point

    base = baseline_trajectories(config, progress=progress,
                                 progress_offset=0, progress_total=total, cancel=cancel)
    base_terminal = [float(b[-1][metric]) for b in base]
    base_terminal_median = _median(base_terminal)

    terminal_delta: List[float] = []
    terminal_scenario: List[float] = []
    for gi, g in enumerate(grid):
        offset = (gi + 1) * config.n_members
        if g <= 0.0:
            scen = base  # the natural zero-anchor: no lever == baseline
            if progress:
                progress(offset + config.n_members, total)
        else:
            sel = L.make_selection([f"{lever}={g}"], actors=actors)
            scen = run_trajectories(config, sel, progress=progress,
                                    progress_offset=offset, progress_total=total, cancel=cancel)
        deltas = [float(scen[i][-1][metric]) - base_terminal[i] for i in range(len(base))]
        terminal_delta.append(_median(deltas))
        terminal_scenario.append(_median([float(s[-1][metric]) for s in scen]))

    return {
        "schema": SCHEMA,
        "mode": "dose_response",
        "lever": lever,
        "config": {"state_csv": config.state_csv, "n_members": config.n_members, "years": config.years,
                   "max_agents": config.max_agents, "master_seed": config.master_seed, "metric": metric,
                   "actors": list(actors or [])},
        "projection": P.dose_projection(metric, grid, terminal_delta, terminal_scenario, base_terminal_median),
    }


def run_dose_cli(args) -> Dict[str, Any]:
    out = compute_dose(state_csv=args.state_csv, lever=args.lever, grid=args.grid, metric=args.metric,
                       actors=args.actors, members=args.members, years=args.years,
                       max_agents=args.max_agents, seed=args.seed)
    cli = ["python3", "-m", "gim2", "dose", "--lever", args.lever, "--metric", args.metric,
           "--grid", *[str(g) for g in args.grid], "--members", str(args.members),
           "--years", str(args.years), "--max-agents", str(args.max_agents), "--seed", str(args.seed)]
    if args.actors:
        cli += ["--actors", *args.actors]
    out["equiv_cli"] = " ".join(shlex.quote(str(p)) for p in cli)
    return out


__all__ = ["compute_dose", "run_dose_cli"]
