#!/usr/bin/env python3
"""Compute the Social Cost of Carbon (deterministic + probabilistic) — Phase 3-B/C.

Env: STATE_CSV, SCC_YEARS, SCC_PULSE (GtCO2), SCC_SAMPLES, SCC_MAX_AGENTS, SCC_SEED.
Writes results/scc-<ts>/scc.json + manifest.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gim.results import build_run_artifacts, write_json_artifact, write_run_manifest
from gim.scc import scc_distribution, scc_multi_horizon, social_cost_of_carbon


def main() -> int:
    csv = os.getenv("STATE_CSV", "data/agent_states_operational.csv")
    years = int(os.getenv("SCC_YEARS", "30"))
    pulse = float(os.getenv("SCC_PULSE", "10.0"))
    samples = int(os.getenv("SCC_SAMPLES", "50"))
    max_agents = int(os.getenv("SCC_MAX_AGENTS", "100"))
    seed = int(os.getenv("SCC_SEED", "2026"))

    t0 = datetime.now()
    central = social_cost_of_carbon(csv, years=years, pulse_gtco2=pulse, max_agents=max_agents, seed=seed)
    horizons = scc_multi_horizon(csv, horizons=(30, 100, 200), pulse_gtco2=pulse, max_agents=max_agents, seed=seed)
    dist = scc_distribution(csv, n_samples=samples, years=years, pulse_gtco2=pulse,
                            max_agents=max_agents, master_seed=seed)
    elapsed = (datetime.now() - t0).total_seconds()

    payload = {"central": central, "horizons": horizons,
               "distribution": {k: v for k, v in dist.items() if k != "samples"},
               "samples": dist["samples"]}
    artifacts = build_run_artifacts("scc")
    path = write_json_artifact(payload, artifacts.run_dir / "scc.json")
    write_run_manifest(
        {"command": "scc", "run_id": artifacts.run_id,
         "summary": {"central_scc": central["scc_usd_per_tco2"], "distribution": dist["percentiles"],
                     "elapsed_sec": round(elapsed, 1), "created_at": datetime.now().isoformat(timespec="seconds")},
         "outputs": {"scc_json": str(path)}},
        artifacts.run_dir,
    )

    p = dist["percentiles"]
    print("SCC by horizon ($/tCO2): " + "  ".join(f"{h}y=${v:.1f}" for h, v in sorted(horizons.items())))
    print(f"Central SCC (eta={central['eta']}, rho={central['rho']}): "
          f"${central['scc_usd_per_tco2']:.2f}/tCO2  (horizon {years}y)")
    print(f"Probabilistic SCC ($/tCO2): p5={p['p5']:.1f}  median={p['p50']:.1f}  p95={p['p95']:.1f}  mean={dist['mean']:.1f}")
    print(f"Done in {elapsed:.1f}s. Artifacts: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
