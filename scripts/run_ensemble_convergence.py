#!/usr/bin/env python3
"""Monte-Carlo convergence and sampling error of the ensemble percentile bands.

The headline uncertainty figure uses an N=80 ensemble. This harness checks that the reported
final-year percentiles (p5/p50/p95) are not an artifact of that small sample, by:

  1. Convergence: drawing one N=N_MAX member set, then reporting the final-year p5/p50/p95 of
     each headline metric on nested subsamples (N_GRID, default 80,250,500).
  2. Monte-Carlo standard error: bootstrapping the N_MAX member set (resample members with
     replacement, recompute each percentile) to attach a +/- sampling error to every reported
     quantile -- i.e., how much the band edge would wobble if the ensemble were redrawn.

This answers "is the N=80 interval trustworthy?" with a number rather than an assertion.

Env: ENS_MAX (default 500), N_GRID (default 80,250,500), BOOT_N (default 2000),
ENS_YEARS (10), ENS_MAX_AGENTS (25), ENS_SEED (2026), STATE_CSV, ENS_JOBS.

    python3 scripts/run_ensemble_convergence.py
"""
from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gim.ensemble import EnsembleConfig, _run_member

METRICS = ("world_gdp", "temperature", "co2")
PCTS = (5.0, 25.0, 50.0, 75.0, 95.0)


def main() -> int:
    n_max = int(os.getenv("ENS_MAX", "500"))
    n_grid = [int(x) for x in os.getenv("N_GRID", "80,250,500").split(",")]
    boot_n = int(os.getenv("BOOT_N", "2000"))
    years = int(os.getenv("ENS_YEARS", "10"))
    max_agents = int(os.getenv("ENS_MAX_AGENTS", "25"))
    seed = int(os.getenv("ENS_SEED", "2026"))
    state_csv = os.getenv("STATE_CSV", "data/agent_states_operational.csv")
    n_jobs = int(os.getenv("ENS_JOBS", "0")) or (os.cpu_count() or 1)

    cfg = EnsembleConfig(state_csv=state_csv, n_members=n_max, years=years,
                         max_agents=max_agents, master_seed=seed, prior_set="key")
    print(f"Ensemble convergence: N_max={n_max}, subsamples={n_grid}, "
          f"years={years}, agents={max_agents}, seed={seed}")
    t0 = datetime.now()

    # Draw the full member set once (member i is seeded from (master_seed, i) -> nested & reproducible).
    args = [{"config": cfg, "index": i} for i in range(n_max)]
    if n_jobs <= 1:
        trajectories = [_run_member(a) for a in args]
    else:
        with ProcessPoolExecutor(max_workers=n_jobs) as ex:
            trajectories = list(ex.map(_run_member, args))

    # final-year value per member, per metric
    final = {m: np.array([t[-1][m] for t in trajectories], dtype=float) for m in METRICS}
    elapsed = (datetime.now() - t0).total_seconds()

    rng = np.random.default_rng(seed)
    out = {
        "experiment": "Ensemble Monte-Carlo convergence + percentile sampling error",
        "config": {"n_max": n_max, "n_grid": n_grid, "boot_n": boot_n, "years": years,
                   "max_agents": max_agents, "seed": seed},
        "metrics": {},
        "elapsed_sec": round(elapsed, 1),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    for m in METRICS:
        vals_full = final[m]
        # 1. convergence on nested subsamples
        conv = {}
        for n in n_grid:
            sub = vals_full[:n]
            conv[n] = {f"p{int(p)}": round(float(np.percentile(sub, p)), 4) for p in PCTS}
        # 2. bootstrap MC standard error of each percentile at N_max
        mc_se = {}
        for p in PCTS:
            boot = np.empty(boot_n)
            for b in range(boot_n):
                idx = rng.integers(0, n_max, size=n_max)
                boot[b] = np.percentile(vals_full[idx], p)
            mc_se[f"p{int(p)}"] = {
                "estimate": round(float(np.percentile(vals_full, p)), 4),
                "se": round(float(boot.std(ddof=1)), 4),
                "ci95": [round(float(np.percentile(boot, 2.5)), 4),
                         round(float(np.percentile(boot, 97.5)), 4)],
            }
        out["metrics"][m] = {"convergence": conv, "mc_error_at_nmax": mc_se}
        e = mc_se
        print(f"  {m:12s} N={n_max}: p5={e['p5']['estimate']:.4g}+/-{e['p5']['se']:.3g}  "
              f"p50={e['p50']['estimate']:.4g}+/-{e['p50']['se']:.3g}  "
              f"p95={e['p95']['estimate']:.4g}+/-{e['p95']['se']:.3g}")

    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "results", "ensemble_convergence")
    os.makedirs(out_dir, exist_ok=True)
    fp = os.path.join(out_dir, "ensemble_convergence.json")
    with open(fp, "w") as fh:
        json.dump(out, fh, indent=2)
        fh.write("\n")
    print(f"Done in {elapsed:.1f}s. ledger -> {os.path.relpath(fp, os.getcwd())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
