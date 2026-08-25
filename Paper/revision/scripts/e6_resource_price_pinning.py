#!/usr/bin/env python3
"""E6 -- do the global resource prices pin at their caps in forward simulation?

`scripts/integration_benchmark/gim_benchmark.py` carries this as honesty note N1 in a
docstring: "GIM's global resource-PRICE subsystem saturates at its caps within one
forward year (energy -> 5.0 ceiling, food -> 0.3 floor). Price-mediated transmission is
therefore not usable in forward sim."

If true, that is a limitation of the resources block that belongs in the manuscript's
Limitations section, not in a script docstring -- and it constrains what the integration
benchmark can claim, because every shock there has to be injected downstream of prices.

This measures it directly: the price path of each resource over 30 forward years, the
year each price first reaches a bound, and the number of years it spends pinned.

Writes Paper/revision/results/e6_resource_price_pinning.json
"""
from __future__ import annotations

import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from gim.core.policy import make_policy_map          # noqa: E402
from gim.core.simulation import step_world           # noqa: E402
from gim.runtime import load_world                   # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results",
                   "e6_resource_price_pinning.json")
HORIZON = 30
BASE_YEAR = 2023
RESOURCES = ("energy", "food", "metals")
TOL = 1e-6


# gim/core/resources.py:329-334 -- the clamp is a hard-coded default argument, not a
# calibration parameter, and is the same for all three resources.
PRICE_MIN = 0.3
PRICE_MAX = 5.0


def price_bounds(params):
    named = {r: (PRICE_MIN, PRICE_MAX) for r in RESOURCES}
    generic = {"PRICE_MIN": PRICE_MIN, "PRICE_MAX": PRICE_MAX,
               "PRICE_ANCHOR_PULL": params.get("PRICE_ANCHOR_PULL"),
               "MARKET_CLEARING": params.get("MARKET_CLEARING"),
               "PRICE_ADJUST_ALPHA": params.get("PRICE_ADJUST_ALPHA")}
    return named, generic


def main() -> int:
    payload = {"experiment": "E6",
               "question": "Do global resource prices pin at their bounds in forward "
                           "simulation, as gim_benchmark.py note N1 states?",
               "config": {"horizon": HORIZON, "base_year": BASE_YEAR,
                          "policy": "simple", "extreme_events": False},
               "runs": {}}

    for label, forward in (("forward_init", True), ("historical_init", False)):
        world = load_world(forward_init=forward)
        params = world.params
        named, generic = price_bounds(params)
        policies = make_policy_map(list(world.agents.keys()), mode="simple")

        paths = {r: [float(world.global_state.prices[r])] for r in RESOURCES}
        for _ in range(HORIZON):
            world = step_world(world, policies, enable_extreme_events=False)
            for r in RESOURCES:
                paths[r].append(float(world.global_state.prices[r]))

        run = {"named_bounds": {r: named[r] for r in RESOURCES},
               "generic_bounds": generic, "paths": paths, "diagnosis": {}}

        for r in RESOURCES:
            p = paths[r]
            lo, hi = named[r]
            # fall back to observed extrema when no named bound exists
            obs_hi, obs_lo = max(p), min(p)
            hits_hi = [i for i, v in enumerate(p) if hi is not None and abs(v - hi) < TOL]
            hits_lo = [i for i, v in enumerate(p) if lo is not None and abs(v - lo) < TOL]
            # constancy: how many years is the price identical to the previous year?
            flat = sum(1 for a, b in zip(p, p[1:]) if abs(a - b) < TOL)
            run["diagnosis"][r] = {
                "start": p[0], "end": p[-1], "min": obs_lo, "max": obs_hi,
                "first_year_at_upper_bound": (BASE_YEAR + hits_hi[0]) if hits_hi else None,
                "first_year_at_lower_bound": (BASE_YEAR + hits_lo[0]) if hits_lo else None,
                "years_at_upper_bound": len(hits_hi),
                "years_at_lower_bound": len(hits_lo),
                "years_unchanged_from_previous": flat,
                "share_of_horizon_unchanged": flat / HORIZON,
                "total_variation": sum(abs(b - a) for a, b in zip(p, p[1:])),
            }
            d = run["diagnosis"][r]
            print(f"{label:16s} {r:7s} {p[0]:.4f} -> {p[-1]:.4f}  "
                  f"range [{obs_lo:.4f}, {obs_hi:.4f}]  "
                  f"unchanged {flat}/{HORIZON} yrs  "
                  f"total variation {d['total_variation']:.4f}")
        payload["runs"][label] = run
        print()

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(os.path.abspath(OUT), "w") as fh:
        json.dump(payload, fh, indent=1)
    print("wrote", os.path.abspath(OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
