#!/usr/bin/env python3
"""Robustness of the Morris screening: convergence in trajectory count r + seed stability.

The headline sensitivity figure uses a screening-budget Morris design (r=8 trajectories).
This harness quantifies whether the *ranking* of influential parameters is an artifact of
that small budget or a stable conclusion, by:

  1. Convergence in r: re-running Morris at r in R_GRID (default 8,16,32) at a fixed seed,
     and reporting, for each r, the top-k set and the Spearman rank correlation of the full
     mu* vector against the largest-r run (the reference).
  2. Seed stability: re-running Morris at the screening budget (r=R_STAB, default 8) across
     SEED_GRID (default 2026,1,7,42,123), reporting how often each parameter lands in the
     top-k and the mean pairwise top-k Jaccard overlap.

For each output metric this answers the reviewer's question directly: the screening rank of
the dominant drivers is reported as stable (or not) with a number, not asserted.

Env: METRIC (temperature|co2|world_gdp|mean_social_tension), R_GRID, R_STAB, SEED_GRID,
TOPK (default 5), SENS_YEARS (10), SENS_MAX_AGENTS (25), STATE_CSV.

    METRIC=world_gdp python3 scripts/run_sensitivity_robustness.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from itertools import combinations

import numpy as np
from scipy.stats import spearmanr

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gim.core.priors import key_priors
from gim.sensitivity import bounds_for, make_output_fn, morris, rank


def _topk_set(ranking, k):
    return [n for n, _ in ranking[:k]]


def _jaccard(a, b):
    sa, sb = set(a), set(b)
    return len(sa & sb) / len(sa | sb) if (sa | sb) else 1.0


def main() -> int:
    metric = os.getenv("METRIC", "world_gdp")
    r_grid = [int(x) for x in os.getenv("R_GRID", "8,16,32").split(",")]
    r_stab = int(os.getenv("R_STAB", "8"))
    seed_grid = [int(x) for x in os.getenv("SEED_GRID", "2026,1,7,42,123").split(",")]
    topk = int(os.getenv("TOPK", "5"))
    years = int(os.getenv("SENS_YEARS", "10"))
    max_agents = int(os.getenv("SENS_MAX_AGENTS", "25"))
    state_csv = os.getenv("STATE_CSV", "data/agent_states_operational.csv")
    model_seed = int(os.getenv("SENS_SEED", "2026"))

    priors = key_priors()
    names = list(priors.keys())
    bounds = bounds_for(priors, names)
    fn = make_output_fn(metric, state_csv, years=years, max_agents=max_agents, seed=model_seed)

    print(f"Robustness: metric={metric} factors={len(names)} r_grid={r_grid} "
          f"seeds={seed_grid} topk={topk}")
    t0 = datetime.now()

    # --- 1. Convergence in r (fixed Morris design seed = model_seed) ---
    conv = {}
    mu_by_r = {}
    for r in r_grid:
        res = morris(names, bounds, fn, r=r, levels=4, seed=model_seed)
        rk = rank(res, by="mu_star")
        conv[r] = {"top": _topk_set(rk, topk),
                   "ranking": [(n, round(v, 4)) for n, v in rk[:12]]}
        mu_by_r[r] = np.array([res[n]["mu_star"] for n in names])
        print(f"  r={r:>3}: top{topk} = {conv[r]['top']}")
    r_ref = max(r_grid)
    for r in r_grid:
        rho, _ = spearmanr(mu_by_r[r], mu_by_r[r_ref])
        conv[r]["spearman_vs_ref"] = round(float(rho), 4)
        conv[r]["topk_jaccard_vs_ref"] = round(_jaccard(conv[r]["top"], conv[r_ref]["top"]), 3)

    # --- 2. Seed stability at the screening budget ---
    stab_tops = {}
    membership = {n: 0 for n in names}
    for s in seed_grid:
        res = morris(names, bounds, fn, r=r_stab, levels=4, seed=s)
        rk = rank(res, by="mu_star")
        top = _topk_set(rk, topk)
        stab_tops[s] = top
        for n in top:
            membership[n] += 1
        print(f"  seed={s:>5} (r={r_stab}): top{topk} = {top}")
    pairwise = [_jaccard(stab_tops[a], stab_tops[b]) for a, b in combinations(seed_grid, 2)]
    mean_jaccard = float(np.mean(pairwise)) if pairwise else 1.0
    stable_core = sorted([n for n, c in membership.items() if c == len(seed_grid)])
    freq = {n: c for n, c in sorted(membership.items(), key=lambda kv: -kv[1]) if c > 0}

    elapsed = (datetime.now() - t0).total_seconds()
    out_obj = {
        "experiment": "Morris screening robustness (r-convergence + seed stability)",
        "metric": metric,
        "n_factors": len(names),
        "topk": topk,
        "config": {"years": years, "max_agents": max_agents, "model_seed": model_seed},
        "convergence_in_r": conv,
        "r_reference": r_ref,
        "seed_stability": {
            "r": r_stab,
            "seeds": seed_grid,
            "tops": stab_tops,
            "membership_count": freq,
            "stable_core_topk_all_seeds": stable_core,
            "mean_pairwise_topk_jaccard": round(mean_jaccard, 3),
        },
        "elapsed_sec": round(elapsed, 1),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "results", "sensitivity_robustness")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"robustness_{metric}.json")
    with open(out, "w") as fh:
        json.dump(out_obj, fh, indent=2)
        fh.write("\n")
    print(f"Done in {elapsed:.1f}s. Spearman(r={r_grid[0]} vs r={r_ref})="
          f"{conv[r_grid[0]]['spearman_vs_ref']}, "
          f"seed top{topk} Jaccard={mean_jaccard:.3f}, stable core={stable_core}")
    print(f"ledger -> {os.path.relpath(out, os.getcwd())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
