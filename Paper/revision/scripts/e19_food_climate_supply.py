#!/usr/bin/env python3
"""E19 -- derive the food supply response jointly with the climate-yield prior.

Two literature priors, no invented numbers:

  FOOD_YIELD_TEMP_SENS      Zhao et al. 2017 PNAS 114(35):9326-9331. Per degree C of warming,
                            global yields fall: wheat 6.0%, rice 3.2%, maize 7.4%, soybean
                            3.1%. Four independent method families converge. Unweighted mean
                            ~4.9%/degC; production weighting toward maize pushes it to ~5.5%.
                            Zhao EXCLUDES CO2 fertilisation, adaptation and genetic
                            improvement.
  FOOD_SUPPLY_PRICE_ELAST   Haile et al. 2016 AJAE and Iqbal et al. 2018 Agricultural
                            Economics: aggregate own-price GROWING-AREA elasticity across
                            corn, soy, wheat and rice is 0.024 short run and 0.143 long run,
                            with crop-level long-run values from 0.045 (rice) to 0.793 (soy).
                            Total supply response adds the yield-intensity margin on top of
                            area, putting the aggregate long-run supply elasticity at roughly
                            0.2-0.3.

These compose without double counting: Zhao's figure is the no-adaptation loss, and the
price elasticity IS the model's adaptation mechanism.

Before this the model had NO climate channel into food production -- warming did not touch
crops anywhere, which is why Appendix B's crop scenario has to inject a yield cut by hand --
and food production was frozen at its base-year value in every forward year while demand grew
33%, driving the price to 4.68 by 2053 against a real record of roughly flat real food prices.

Reports, for each pair: the 2053 food price and supply, demand/supply, the implied annual
supply growth, the historical fit, and the food price implausibility against the observed
World Bank index.

Writes Paper/revision/results/e19_food_climate_supply.json
"""
from __future__ import annotations

import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from gim.calibration_hm import PRICE_TOLERANCES                 # noqa: E402
from gim.core.policy import make_policy_map                     # noqa: E402
from gim.core.simulation import step_world                      # noqa: E402
from gim.historical_backtest import run_historical_backtest     # noqa: E402
from gim.runtime import load_world                              # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results",
                   "e19_food_climate_supply.json")
HORIZON = 30

# Zhao's four crop values and the two aggregates they support.
ZHAO = {"wheat": 0.060, "rice": 0.032, "maize": 0.074, "soybean": 0.031}
TEMP_GRID = [0.0, 0.049, 0.055]          # off, unweighted mean, production-weighted
ELAST_GRID = [0.0, 0.143, 0.20, 0.30]    # off, literature area-only, and two supply values


def forward(ov: dict) -> dict:
    world = load_world(forward_init=True)
    if ov:
        world.params = world.params.with_overrides(ov)
    pol = make_policy_map(list(world.agents.keys()), mode="simple")
    first = None
    for t in range(HORIZON):
        world = step_world(world, pol, enable_extreme_events=False)
        if t == 0:
            first = sum(max(0.0, a.resources["food"].production)
                        for a in world.agents.values() if a.resources.get("food"))
    sup = dem = 0.0
    for a in world.agents.values():
        r = a.resources.get("food")
        if r:
            sup += max(0.0, r.production)
            dem += max(0.0, r.consumption)
    growth = ((sup / first) ** (1.0 / (HORIZON - 1)) - 1.0) if first and first > 0 else float("nan")
    return {"price_2053": float(world.global_state.prices["food"]),
            "supply_2053": float(sup), "demand_2053": float(dem),
            "demand_over_supply": float(dem / max(sup, 1e-9)),
            "implied_annual_supply_growth": float(growth),
            "temperature_2053": float(world.global_state.temperature_global)}


def main() -> int:
    print("Zhao 2017 per-degree yield loss:", {k: f"{v:.1%}" for k, v in ZHAO.items()})
    print(f"  unweighted mean {sum(ZHAO.values())/len(ZHAO):.3%}/degC\n")
    print(f"{'temp sens':>10s} {'elast':>7s} | {'price 2053':>11s} {'supply':>9s} {'D/S':>7s} "
          f"{'supply g/yr':>12s} | {'fit gdp':>8s} {'I_food':>7s}")

    grid = {}
    for ts in TEMP_GRID:
        for el in ELAST_GRID:
            ov = {"FOOD_YIELD_TEMP_SENS": ts, "FOOD_SUPPLY_PRICE_ELAST": el}
            f = forward(ov)
            bt = run_historical_backtest(params_override=ov,
                                         temperature_variability_sigma_override=0.0)
            i_food = bt.resource_price_rmse["food"] / PRICE_TOLERANCES["price_food"]
            row = {"temp_sens": ts, "elasticity": el, **f,
                   "fit_gdp_rmse": float(bt.gdp_rmse_trillions),
                   "fit_co2_rmse": float(bt.global_co2_rmse_gtco2),
                   "fit_temp_rmse": float(bt.temperature_rmse_c),
                   "price_implausibility_food": float(i_food)}
            grid[f"t{ts:g}_e{el:g}"] = row
            print(f"{ts:10.3f} {el:7.3f} | {f['price_2053']:11.3f} {f['supply_2053']:9.1f} "
                  f"{f['demand_over_supply']:7.4f} {f['implied_annual_supply_growth']:12.4%} | "
                  f"{bt.gdp_rmse_trillions:8.4f} {i_food:7.3f}")

    payload = {
        "experiment": "E19",
        "question": "What food supply response do the climate-yield and agricultural "
                    "supply-elasticity priors jointly imply?",
        "priors": {
            "yield_temperature": {
                "source": "Zhao et al. 2017, PNAS 114(35):9326-9331",
                "per_crop_loss_per_degC": ZHAO,
                "unweighted_mean": sum(ZHAO.values()) / len(ZHAO),
                "note": "excludes CO2 fertilisation, adaptation and genetic improvement",
            },
            "supply_price_elasticity": {
                "source": "Haile et al. 2016 AJAE; Iqbal et al. 2018 Agricultural Economics",
                "aggregate_area_elasticity_short_run": 0.024,
                "aggregate_area_elasticity_long_run": 0.143,
                "crop_long_run_range": [0.045, 0.793],
                "note": "total supply adds the yield-intensity margin on top of area, putting "
                        "the aggregate long-run supply elasticity near 0.2-0.3",
            },
        },
        "real_world_anchors": {
            "food_production_growth_per_year": "~2% (FAO, decelerating)",
            "real_food_prices": "roughly flat over decades",
        },
        "config": {"horizon": HORIZON, "policy": "simple", "extreme_events": False,
                   "forward_init": True},
        "grid": grid,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(os.path.abspath(OUT), "w") as fh:
        json.dump(payload, fh, indent=1)
    print("\nwrote", os.path.abspath(OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
