#!/usr/bin/env python3
"""Global sensitivity analysis over the model priors (Phase 1-D).

Morris screening (default) or Sobol indices for a chosen output metric, over the selected
priors. Writes results/sensitivity-<ts>/sensitivity.json + manifest.

Env: SENS_METRIC (temperature|co2|world_gdp|mean_social_tension), SENS_METHOD (morris|sobol),
SENS_PRIORS (key|all), SENS_NAMES (comma list; default all of the chosen prior set),
SENS_R, SENS_NBASE, SENS_YEARS, SENS_MAX_AGENTS, SENS_SEED, STATE_CSV.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gim.core.priors import all_priors, key_priors
from gim.results import build_run_artifacts, write_json_artifact, write_run_manifest
from gim.sensitivity import bounds_for, make_output_fn, morris, rank, sobol


def main() -> int:
    metric = os.getenv("SENS_METRIC", "temperature")
    method = os.getenv("SENS_METHOD", "morris")
    prior_set = os.getenv("SENS_PRIORS", "key")
    priors = key_priors() if prior_set == "key" else all_priors()
    names_env = os.getenv("SENS_NAMES")
    names = [n.strip() for n in names_env.split(",")] if names_env else list(priors.keys())
    names = [n for n in names if n in priors]

    state_csv = os.getenv("STATE_CSV", "data/agent_states_operational_2026_calibrated.csv")
    years = int(os.getenv("SENS_YEARS", "10"))
    max_agents = int(os.getenv("SENS_MAX_AGENTS", "100"))
    seed = int(os.getenv("SENS_SEED", "2026"))

    fn = make_output_fn(metric, state_csv, years=years, max_agents=max_agents, seed=seed)
    bounds = bounds_for(priors, names)

    print(f"Sensitivity: method={method} metric={metric} factors={len(names)} priors={prior_set}")
    t0 = datetime.now()
    if method == "sobol":
        n_base = int(os.getenv("SENS_NBASE", "128"))
        result = sobol(names, bounds, fn, n_base=n_base, seed=seed)
        order_key = "ST"
    else:
        r = int(os.getenv("SENS_R", "10"))
        result = morris(names, bounds, fn, r=r, levels=4, seed=seed)
        order_key = "mu_star"
    elapsed = (datetime.now() - t0).total_seconds()

    ranking = rank(result, by=order_key)
    artifacts = build_run_artifacts("sensitivity")
    sens_path = write_json_artifact(
        {"method": method, "metric": metric, "prior_set": prior_set, "factors": names,
         "indices": result, "ranking": ranking},
        artifacts.run_dir / "sensitivity.json",
    )
    write_run_manifest(
        {"command": "sensitivity", "run_id": artifacts.run_id,
         "inputs": {"metric": metric, "method": method, "prior_set": prior_set,
                    "n_factors": len(names), "years": years, "max_agents": max_agents},
         "summary": {"elapsed_sec": round(elapsed, 1),
                     "top10": ranking[:10],
                     "created_at": datetime.now().isoformat(timespec="seconds")},
         "outputs": {"sensitivity_json": str(sens_path)}},
        artifacts.run_dir,
    )

    print(f"Done in {elapsed:.1f}s. Top drivers of {metric} (by {order_key}):")
    for name, value in ranking[:12]:
        print(f"  {name:28s} {order_key}={value:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
