#!/usr/bin/env python3
"""E16 -- do resource prices reach anything downstream?

Across all 36 configurations of E15 -- spanning the metals recycling fix, the price-buffer
cap, energy income elasticities 0 to 0.8, metals 0.7 to 2.0 and price anchor pulls 0.15 to
0.0 -- the GDP, CO2 and temperature RMSEs were IDENTICAL to four decimal places. Prices moved;
nothing else did.

That is either a coincidence of small price moves or a structural fact about the coupling.
This separates the two by forcing large price changes directly and measuring what follows:
the energy price is multiplied by a factor held for the whole run, and world GDP, inflation,
unemployment, emissions and social tension are compared against the unforced baseline.

If a 3x energy price leaves world output and inflation unchanged, then the
resources -> economy channel does not exist in any operational sense, and the paper's
"integrated" claim cannot rest on it.

Writes Paper/revision/results/e16_price_downstream_reach.json
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from gim.core import resources as res_mod             # noqa: E402
from gim.core.policy import make_policy_map           # noqa: E402
from gim.core.simulation import step_world            # noqa: E402
from gim.runtime import load_world                    # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results",
                   "e16_price_downstream_reach.json")
HORIZON = 10
FACTORS = [1.0, 1.5, 2.0, 3.0, 5.0]

_ORIG = res_mod.update_global_resource_prices
_FORCE = {"factor": 1.0, "resource": "energy"}


def _patched(world, *a, **kw):
    _ORIG(world, *a, **kw)
    if _FORCE["factor"] != 1.0:
        r = _FORCE["resource"]
        world.global_state.prices[r] = float(world.global_state.prices[r]) * _FORCE["factor"]


res_mod.update_global_resource_prices = _patched
# simulation.py imports the symbol directly, so rebind it there too
from gim.core import simulation as _sim               # noqa: E402
if hasattr(_sim, "update_global_resource_prices"):
    _sim.update_global_resource_prices = _patched


def run(factor: float, resource: str) -> dict:
    _FORCE.update(factor=factor, resource=resource)
    world = load_world(forward_init=True)
    ids = list(world.agents.keys())
    pol = make_policy_map(ids, mode="simple")
    for _ in range(HORIZON):
        world = step_world(world, pol, enable_extreme_events=False)
    _FORCE["factor"] = 1.0
    return {
        "world_gdp": float(sum(world.agents[a].economy.gdp for a in ids)),
        "mean_inflation": float(np.mean([world.agents[a].economy.inflation for a in ids])),
        "mean_unemployment": float(np.mean([world.agents[a].economy.unemployment for a in ids])),
        "global_co2": float(sum(world.agents[a].climate.co2_annual_emissions for a in ids)),
        "mean_tension": float(np.mean([world.agents[a].society.social_tension for a in ids])),
        "final_price": float(world.global_state.prices[resource]),
    }


def main() -> int:
    results = {}
    for resource in ("energy", "food", "metals"):
        base = run(1.0, resource)
        rows = {}
        print(f"\n--- forcing the {resource} price ---")
        print(f"{'factor':>7s} {'final price':>12s} {'world GDP':>12s} {'d%':>8s} "
              f"{'inflation':>10s} {'d%':>8s} {'CO2':>9s} {'d%':>8s} {'tension':>8s} {'d%':>8s}")
        for f in FACTORS:
            r = run(f, resource)
            d = {k: (100.0 * (r[k] - base[k]) / base[k] if base[k] else float("nan"))
                 for k in ("world_gdp", "mean_inflation", "global_co2", "mean_tension")}
            rows[f"x{f:g}"] = {"forced_factor": f, **r, "pct_change_vs_base": d}
            print(f"{f:7.1f} {r['final_price']:12.4f} {r['world_gdp']:12.3f} "
                  f"{d['world_gdp']:+8.4f} {r['mean_inflation']:10.5f} "
                  f"{d['mean_inflation']:+8.4f} {r['global_co2']:9.3f} {d['global_co2']:+8.4f} "
                  f"{r['mean_tension']:8.5f} {d['mean_tension']:+8.4f}")
        worst = max(abs(rows[k]["pct_change_vs_base"]["world_gdp"]) for k in rows)
        results[resource] = {"baseline": base, "forced": rows,
                             "max_abs_world_gdp_pct_change": worst,
                             "reaches_economy": bool(worst > 0.01)}
    payload = {
        "experiment": "E16",
        "question": "Does a forced change in a resource price reach GDP, inflation, "
                    "emissions or social tension?",
        "config": {"horizon": HORIZON, "factors": FACTORS, "policy": "simple",
                   "extreme_events": False, "forward_init": True},
        "results": results,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(os.path.abspath(OUT), "w") as fh:
        json.dump(payload, fh, indent=1)
    print("\nreaches the economy:",
          {k: v["reaches_economy"] for k, v in results.items()})
    print("wrote", os.path.abspath(OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
