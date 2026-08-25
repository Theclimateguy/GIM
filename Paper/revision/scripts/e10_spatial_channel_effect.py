#!/usr/bin/env python3
"""E10 -- is the spatial channel doing anything?

Section 6's fifth regularity: "The diffusion itself is coded (neighbour spillover weight
0.05); the non-coded part is that switching it on moves the 2015-2023 retrospective fit by
under a quarter of a percent -- spatially realistic propagation at no cost in anchor."

As written this claims the channel is FREE, not that it is RIGHT, and the paper explicitly
declines to check whether the resulting spatial autocorrelation matches the record. A
channel that changes neither the fit nor the forward trajectory is inert, and an inert
channel is not a regularity. E1 already found that severing all cross-country coupling
barely moved the crisis series (mean 7.07 vs 6.97 per year).

This measures the effect size of the two spatial weights on both sides of the claim:
  (a) the 2015-2023 retrospective fit -- does the "under a quarter percent" hold, and
  (b) the 30-year forward trajectory -- does the channel move anything at all downstream,
      including the cross-country dispersion of tension it is supposed to create.

If the answer to (b) is also "nothing", the honest statement is that the channel is
currently inert at its calibrated weight, which belongs in Limitations rather than in a
section about what the loop produces.

Writes Paper/revision/results/e10_spatial_channel_effect.json
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from gim.core.policy import make_policy_map            # noqa: E402
from gim.core.simulation import step_world             # noqa: E402
from gim.historical_backtest import run_historical_backtest  # noqa: E402
from gim.runtime import load_world                     # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results",
                   "e10_spatial_channel_effect.json")
HORIZON = 30

CONFIGS = {
    "headline_spatial_on": {},
    "tension_diffusion_off": {"GEOGRAPHY_TENSION_LINKS": False,
                              "GEO_TENSION_SPILLOVER_W": 0.0},
    "climate_diffusion_off": {"GEOGRAPHY_CLIMATE_LINKS": False,
                              "GEO_CLIMATE_SPILLOVER_W": 0.0},
    "all_spatial_off": {"GEOGRAPHY_TENSION_LINKS": False,
                        "GEO_TENSION_SPILLOVER_W": 0.0,
                        "GEOGRAPHY_CLIMATE_LINKS": False,
                        "GEO_CLIMATE_SPILLOVER_W": 0.0,
                        "GEO_CONTAGION_W": 0.0},
    "tension_diffusion_x4": {"GEO_TENSION_SPILLOVER_W": 0.20},
}


def forward_metrics(overrides: dict) -> dict:
    world = load_world(forward_init=True)
    if overrides:
        world.params = world.params.with_overrides(overrides)
    policies = make_policy_map(list(world.agents.keys()), mode="simple")
    ids = list(world.agents.keys())
    out = []
    for _ in range(HORIZON):
        world = step_world(world, policies, enable_extreme_events=False)
        ten = np.array([world.agents[a].society.social_tension for a in ids])
        out.append({
            "mean_tension": float(ten.mean()),
            "sd_tension": float(ten.std()),
            "world_gdp": float(sum(world.agents[a].economy.gdp for a in ids)),
            "temperature": float(world.global_state.temperature_global),
            "n_regime_crisis": int(sum(world.agents[a].risk.regime_crisis_active_years > 0
                                       for a in ids)),
        })
    return {
        "final_mean_tension": out[-1]["mean_tension"],
        # the dispersion the channel is supposed to shape: diffusion should COMPRESS it
        "final_sd_tension": out[-1]["sd_tension"],
        "sd_tension_path": [o["sd_tension"] for o in out],
        "final_world_gdp": out[-1]["world_gdp"],
        "final_temperature": out[-1]["temperature"],
        "total_regime_crisis_agent_years": int(sum(o["n_regime_crisis"] for o in out)),
    }


def fit_metrics(overrides: dict) -> dict:
    res = run_historical_backtest(params_override=overrides or None,
                                  temperature_variability_sigma_override=0.0)
    return {
        # country_gdp_rmse_trillions is a per-country dict; pool it as an RMS so the
        # comparison uses the same metric the paper reports at country level.
        "country_gdp_rmse_trillions": float(
            np.sqrt(np.mean([v ** 2 for v in res.country_gdp_rmse_trillions.values()]))),
        "gdp_rmse_trillions": float(res.gdp_rmse_trillions),
        "global_co2_rmse_gtco2": float(res.global_co2_rmse_gtco2),
        "temperature_rmse_c": float(res.temperature_rmse_c),
    }


def main() -> int:
    results = {}
    for name, ov in CONFIGS.items():
        results[name] = {"overrides": {k: (v if isinstance(v, (int, float, bool)) else str(v))
                                       for k, v in ov.items()},
                         "fit": fit_metrics(ov), "forward": forward_metrics(ov)}

    base_fit = results["headline_spatial_on"]["fit"]
    base_fwd = results["headline_spatial_on"]["forward"]
    for name, r in results.items():
        if name == "headline_spatial_on":
            continue
        r["fit_relative_change_pct"] = {
            k: (100.0 * (r["fit"][k] - base_fit[k]) / base_fit[k]) if base_fit[k] else float("nan")
            for k in base_fit
        }
        r["forward_relative_change_pct"] = {
            k: (100.0 * (r["forward"][k] - base_fwd[k]) / base_fwd[k])
            if isinstance(base_fwd[k], (int, float)) and base_fwd[k] else float("nan")
            for k in ("final_mean_tension", "final_sd_tension", "final_world_gdp",
                      "final_temperature", "total_regime_crisis_agent_years")
        }

    print(f"{'config':26s} {'cty GDP RMSE':>13s} {'d%':>7s} | {'fwd sd(tension)':>16s} {'d%':>7s} "
          f"| {'regime agent-yrs':>17s} {'d%':>7s}")
    for name, r in results.items():
        f, w = r["fit"], r["forward"]
        if name == "headline_spatial_on":
            print(f"{name:26s} {f['country_gdp_rmse_trillions']:13.6f} {'--':>7s} | "
                  f"{w['final_sd_tension']:16.6f} {'--':>7s} | "
                  f"{w['total_regime_crisis_agent_years']:17d} {'--':>7s}")
        else:
            print(f"{name:26s} {f['country_gdp_rmse_trillions']:13.6f} "
                  f"{r['fit_relative_change_pct']['country_gdp_rmse_trillions']:+7.3f} | "
                  f"{w['final_sd_tension']:16.6f} "
                  f"{r['forward_relative_change_pct']['final_sd_tension']:+7.3f} | "
                  f"{w['total_regime_crisis_agent_years']:17d} "
                  f"{r['forward_relative_change_pct']['total_regime_crisis_agent_years']:+7.3f}")

    payload = {
        "experiment": "E10",
        "question": "Does the spatial channel change the fit, the forward trajectory, or "
                    "the cross-country dispersion it is supposed to shape?",
        "config": {"horizon": HORIZON, "policy": "simple", "extreme_events": False,
                   "forward_init": True,
                   "headline_weights": {"GEO_TENSION_SPILLOVER_W": 0.05,
                                        "GEO_CLIMATE_SPILLOVER_W": 0.10,
                                        "GEO_CONTAGION_W": 0.03}},
        "results": results,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(os.path.abspath(OUT), "w") as fh:
        json.dump(payload, fh, indent=1)
    print("wrote", os.path.abspath(OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
