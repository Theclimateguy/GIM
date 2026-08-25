#!/usr/bin/env python3
"""E15 -- calibrate the resource demand elasticities against the new price targets.

Two defects were localised by tracing supply and demand through the 2015-2023 backtest:

  ENERGY. `ENERGY_DEMAND_POP_ELASTICITY` and `ENERGY_DEMAND_INCOME_ELASTICITY` are BOTH 0.0,
  the second with the comment "energy demand handled by ENERGY_DEMAND_PRICE_RESPONSE". But a
  price response is a one-time shift for a constant price, so energy demand never grows with
  population or income. Supply is likewise static (0.650 every year), so demand/supply is
  exactly 1.0000 in every year and the clearing price cannot move. The observed World Bank
  energy index moved +62% over the same window.

  METALS. Fixed separately: the base-year `production` is total supply, and recycling was
  added on top of it, injecting a permanent ~45% glut. With
  METALS_BASE_PRIMARY_NET_OF_RECYCLING the metals price RMSE falls 0.9293 -> 0.3969, but the
  price is then nearly flat (1.000 -> 1.049) where the observed index rose 55%, so the demand
  elasticity is now the binding term there too.

Rather than hand-pick values, this sweeps both income elasticities against the price targets
added to the backtest, and checks that GDP, CO2 and temperature do not degrade. The IEA
anchor for the energy value: global primary energy intensity improved about 2%/yr over
2010-2019 and about 1.2%/yr over 2019-2023 against world GDP growth near 3%/yr, implying an
income elasticity of roughly 0.33-0.6.

Writes Paper/revision/results/e15_demand_elasticity_calibration.json
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from gim.calibration_hm import PRICE_TOLERANCES                     # noqa: E402
from gim.historical_backtest import run_historical_backtest         # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results",
                   "e15_demand_elasticity_calibration.json")
ENERGY_GRID = [0.0, 0.3, 0.5, 0.8]
METALS_GRID = [0.7, 1.3, 2.0]
ANCHOR_GRID = [0.15, 0.05, 0.0]          # PRICE_ANCHOR_PULL: the third thing pinning energy
BUFFER = {"PRICE_BUFFER_YEARS_ENERGY": 0.25,
          "PRICE_BUFFER_YEARS_FOOD": 0.30,
          "PRICE_BUFFER_YEARS_METALS": 0.25}
BASE = {"METALS_BASE_PRIMARY_NET_OF_RECYCLING": True, **BUFFER}


def score(ov: dict) -> dict:
    r = run_historical_backtest(params_override=ov or None,
                                temperature_variability_sigma_override=0.0)
    pr = dict(r.resource_price_rmse)
    imp = {k: pr[k] / PRICE_TOLERANCES[f"price_{k}"] for k in pr}
    return {
        "price_rmse": pr,
        "price_implausibility": imp,
        "price_implausibility_max": max(imp.values()),
        "gdp_rmse": float(r.gdp_rmse_trillions),
        "country_gdp_rmse_pooled": float(np.sqrt(np.mean(
            [v ** 2 for v in r.country_gdp_rmse_trillions.values()]))),
        "co2_rmse": float(r.global_co2_rmse_gtco2),
        "temp_rmse": float(r.temperature_rmse_c),
        "energy_price_path": [round(r.predicted_resource_prices[y]["energy"], 4)
                              for y in sorted(r.predicted_resource_prices)],
        "metals_price_path": [round(r.predicted_resource_prices[y]["metals"], 4)
                              for y in sorted(r.predicted_resource_prices)],
    }


def main() -> int:
    ref = score({})
    base = score(BASE)
    print("observed index (energy):", [round(v, 3) for v in
          [1.0, 0.848, 1.049, 1.352, 1.184, 0.797, 1.443, 2.308, 1.618]])
    print(f"\n{'config':38s} {'I_energy':>9s} {'I_food':>7s} {'I_metals':>9s} "
          f"{'cty GDP':>8s} {'CO2':>7s} {'temp':>7s}")

    def show(label, s):
        i = s["price_implausibility"]
        print(f"{label:38s} {i['energy']:9.3f} {i['food']:7.3f} {i['metals']:9.3f} "
              f"{s['country_gdp_rmse_pooled']:8.4f} {s['co2_rmse']:7.4f} {s['temp_rmse']:7.4f}")

    show("current (no fixes)", ref)
    show("metals recycling fix only", base)

    grid = {}
    for a in ANCHOR_GRID:
        for e in ENERGY_GRID:
            for m in METALS_GRID:
                ov = dict(BASE)
                ov["PRICE_ANCHOR_PULL"] = a
                ov["ENERGY_DEMAND_INCOME_ELASTICITY"] = e
                ov["METALS_DEMAND_INCOME_ELASTICITY"] = m
                s = score(ov)
                grid[f"a{a:g}_e{e:g}_m{m:g}"] = {"price_anchor_pull": a,
                                                 "energy_income_elasticity": e,
                                                 "metals_income_elasticity": m, **s}
                show(f"anchor={a:g} energy={e:g} metals={m:g}", s)

    # pick on price skill, refuse anything that degrades the core outputs
    tol_gdp = ref["country_gdp_rmse_pooled"] * 1.02
    tol_co2 = ref["co2_rmse"] * 1.02
    tol_t = ref["temp_rmse"] * 1.02
    ok = {k: v for k, v in grid.items()
          if v["country_gdp_rmse_pooled"] <= tol_gdp and v["co2_rmse"] <= tol_co2
          and v["temp_rmse"] <= tol_t}
    best = min(ok, key=lambda k: sum(ok[k]["price_implausibility"].values())) if ok else None
    print(f"\nadmissible (core outputs within 2% of current): {len(ok)}/{len(grid)}")
    if best:
        b = grid[best]
        print(f"best on summed price implausibility: {best}  anchor={b['price_anchor_pull']:g} "
              f"energy={b['energy_income_elasticity']:g} metals={b['metals_income_elasticity']:g}")
        print(f"   I: energy {b['price_implausibility']['energy']:.3f}  "
              f"food {b['price_implausibility']['food']:.3f}  "
              f"metals {b['price_implausibility']['metals']:.3f}")
        print(f"   energy path: {b['energy_price_path']}")
        print(f"   metals path: {b['metals_price_path']}")

    payload = {
        "experiment": "E15",
        "question": "What demand elasticities does the price-aware backtest select, and do "
                    "they cost anything on GDP, CO2 or temperature?",
        "iea_anchor": ("global primary energy intensity improved ~2%/yr 2010-2019 and ~1.2%/yr "
                       "2019-2023 against ~3%/yr world GDP growth, implying an income "
                       "elasticity of roughly 0.33-0.6"),
        "price_tolerances": dict(PRICE_TOLERANCES),
        "reference_current": ref,
        "metals_fix_only": base,
        "grid": grid,
        "admissible_keys": sorted(ok),
        "selected": best,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(os.path.abspath(OUT), "w") as fh:
        json.dump(payload, fh, indent=1)
    print("\nwrote", os.path.abspath(OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
