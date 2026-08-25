#!/usr/bin/env python3
"""Score the model's 2015-2023 backtest vs observations and no-skill baselines (P2-A).

Reports RMSE and skill scores (vs persistence and naive trend) for world GDP, global CO2,
and global temperature. Writes results/scoring-<ts>/scoring.json + manifest.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gim.historical_backtest import load_historical_observed_fixture, run_historical_backtest
from gim.results import build_run_artifacts, write_json_artifact, write_run_manifest
from gim.scoring import score_series


def _world_gdp_series(by_year_country: dict) -> dict:
    return {int(y): float(sum(v.values())) for y, v in by_year_country.items()}


def main() -> int:
    obs = load_historical_observed_fixture()
    obs_gdp = _world_gdp_series(obs["gdp_trillions_by_year"])
    obs_co2 = {int(y): float(v) for y, v in obs["global_co2_gtco2"].items()}
    obs_temp = {int(y): float(v) for y, v in obs["temperature_c_preindustrial"].items()}

    result = run_historical_backtest()
    pred_gdp = {int(y): float(sum(v.values())) for y, v in result.predicted_gdp_trillions.items()}
    pred_co2 = {int(y): float(v) for y, v in result.predicted_global_co2_gtco2.items()}
    pred_temp = {int(y): float(v) for y, v in result.predicted_temperature_c.items()}

    anchor = min(obs_temp)
    train = [anchor, anchor + 1, anchor + 2]
    scores = {
        "world_gdp": score_series(pred_gdp, obs_gdp, anchor_year=anchor, train_years=train),
        "global_co2": score_series(pred_co2, obs_co2, anchor_year=anchor, train_years=train),
        "temperature": score_series(pred_temp, obs_temp, anchor_year=anchor, train_years=train),
    }

    artifacts = build_run_artifacts("scoring")
    path = write_json_artifact({"anchor_year": anchor, "scores": scores}, artifacts.run_dir / "scoring.json")
    write_run_manifest(
        {"command": "scoring", "run_id": artifacts.run_id,
         "summary": {"scores": scores, "created_at": datetime.now().isoformat(timespec="seconds")},
         "outputs": {"scoring_json": str(path)}},
        artifacts.run_dir,
    )

    print("Out-of-sample skill (anchor year", anchor, "-> forecast forward):")
    for metric, s in scores.items():
        print(f"  {metric:12s} RMSE={s['model_rmse']:.4g}  "
              f"skill_vs_persistence={s['skill_vs_persistence']:+.3f}  "
              f"skill_vs_trend={s['skill_vs_trend']:+.3f}")
    print(f"Artifacts: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
