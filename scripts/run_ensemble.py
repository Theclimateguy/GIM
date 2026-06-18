#!/usr/bin/env python3
"""Run the Monte-Carlo uncertainty ensemble and save percentile fan-band artifacts (P1-C).

Env knobs: STATE_CSV, ENS_MEMBERS, ENS_YEARS, ENS_MAX_AGENTS, ENS_SEED, ENS_PRIORS
(key|all), ENS_JOBS. Writes results/ensemble-<ts>/ensemble.json + run_manifest.json.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gim.ensemble import EnsembleConfig, run_ensemble
from gim.fan_charts import render_fan_charts
from gim.results import build_run_artifacts, write_json_artifact, write_run_manifest


def main() -> int:
    cfg = EnsembleConfig(
        state_csv=os.getenv("STATE_CSV", "data/agent_states_operational_2026_calibrated.csv"),
        n_members=int(os.getenv("ENS_MEMBERS", "500")),
        years=int(os.getenv("ENS_YEARS", "10")),
        max_agents=int(os.getenv("ENS_MAX_AGENTS", "100")),
        master_seed=int(os.getenv("ENS_SEED", "2026")),
        prior_set=os.getenv("ENS_PRIORS", "key"),
        n_jobs=int(os.getenv("ENS_JOBS", "0")),
    )
    print(f"Ensemble: {cfg.n_members} members x {cfg.years}y, priors={cfg.prior_set}, seed={cfg.master_seed}")

    def _progress(done: int, total: int) -> None:
        if done == total or done % max(1, total // 10) == 0:
            print(f"  {done}/{total} members")

    t0 = datetime.now()
    result = run_ensemble(cfg, progress=_progress)
    elapsed = (datetime.now() - t0).total_seconds()

    artifacts = build_run_artifacts("ensemble")
    ens_path = write_json_artifact(result.to_dict(), artifacts.run_dir / "ensemble.json")
    fan_path = artifacts.run_dir / "fan_charts.html"
    fan_path.write_text(render_fan_charts(result), encoding="utf-8")
    manifest = write_run_manifest(
        {
            "command": "ensemble",
            "run_id": artifacts.run_id,
            "inputs": result.to_dict()["config"],
            "summary": {
                "n_members": result.n_members,
                "elapsed_sec": round(elapsed, 1),
                "final_year": {
                    m: {
                        "p5": result.bands[m]["p5"][-1],
                        "p50": result.bands[m]["p50"][-1],
                        "p95": result.bands[m]["p95"][-1],
                    }
                    for m in ("world_gdp", "temperature", "co2")
                },
                "created_at": datetime.now().isoformat(timespec="seconds"),
            },
            "outputs": {"ensemble_json": str(ens_path), "fan_charts_html": str(fan_path)},
        },
        artifacts.run_dir,
    )

    print(f"\nDone in {elapsed:.1f}s. Final-year fan bands (p5 / p50 / p95):")
    for m in ("world_gdp", "temperature", "co2"):
        b = result.bands[m]
        print(f"  {m:14s} {b['p5'][-1]:.4g} / {b['p50'][-1]:.4g} / {b['p95'][-1]:.4g}")
    print(f"Artifacts: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
