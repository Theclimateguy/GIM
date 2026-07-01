"""Timing bench + interactive/background member-size policy (THE-66).

Run a quick bench (CI-fast) or the paper-grade full bench (57×10, 500 members):

    python3 -m gim2.perf --quick
    python3 -m gim2.perf --full

The bench demonstrates the baseline cache: ``scenario(warm-base)`` reuses the base
ensemble computed by the preceding run at the same config, so only the scenario
ensemble is recomputed (~half the cold cost).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any, Callable, Dict

from . import scenario as S
from .dose_response import compute_dose
from .scenario import BACKGROUND_MEMBERS, INTERACTIVE_MEMBERS


def recommended_members(*, interactive: bool) -> int:
    """Interactive runs use a responsive ensemble; background jobs use the full size."""
    return INTERACTIVE_MEMBERS if interactive else BACKGROUND_MEMBERS


def _time(fn: Callable[[], Any]) -> float:
    t0 = time.perf_counter()
    fn()
    return round(time.perf_counter() - t0, 3)


def benchmark(*, members: int, years: int, max_agents: int, seed: int = 2026, jobs: int = 0) -> Dict[str, Any]:
    common = dict(years=years, max_agents=max_agents, seed=seed)
    rows: Dict[str, float] = {}

    S.clear_baseline_cache()
    rows["ensemble"] = _time(lambda: S.compute_ensemble(members=members, jobs=jobs, **common))
    rows["sensitivity(Morris r=6)"] = _time(lambda: S.compute_sensitivity(metric="world_gdp", r=6, **common))
    rows["weak_signals"] = _time(lambda: S.compute_weak(levers=["energy_shock"], **{**common, "years": max(12, years)}))

    S.clear_baseline_cache()
    rows["scenario(cold)"] = _time(lambda: S.compute_scenario(
        levers=["decarbonization"], magnitude=1.0, members=members, jobs=jobs, **common))
    rows["scenario(warm-base)"] = _time(lambda: S.compute_scenario(
        levers=["carbon_price"], magnitude=1.0, members=members, jobs=jobs, **common))
    rows["dose(3pt,warm-base)"] = _time(lambda: compute_dose(
        lever="growth", grid=[0.0, 0.5, 1.0], metric="world_gdp", members=members, **common))

    return {
        "config": {"members": members, "years": years, "max_agents": max_agents, "seed": seed, "jobs": jobs},
        "policy": {"interactive_members": INTERACTIVE_MEMBERS, "background_members": BACKGROUND_MEMBERS},
        "seconds": rows,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="gim2.perf", description="GIM17 v2 timing bench")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--quick", action="store_true", help="fast bench (40×, 20 countries)")
    g.add_argument("--full", action="store_true", help="paper-grade bench (500×, 57 countries)")
    p.add_argument("--jobs", type=int, default=0)
    args = p.parse_args(argv)
    if args.full:
        result = benchmark(members=BACKGROUND_MEMBERS, years=10, max_agents=57, jobs=args.jobs)
    else:
        result = benchmark(members=40, years=10, max_agents=20, jobs=args.jobs)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
