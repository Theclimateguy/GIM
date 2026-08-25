#!/usr/bin/env python3
"""E18 -- is the climate spatial channel broken, or just switched off?

E10 measured the climate-risk diffusion channel as EXACTLY inert: 0.000% on forward
cross-country tension dispersion and 0.00% on regime crises. I read that as "there is no
climate -> society path". That reading was wrong, and this corrects it.

`gim/core/climate.py:400-412` (`apply_climate_extreme_events`) reads `climate_risk` and
WRITES `society.social_tension` and `society.trust_gov`. The path exists. But every
deterministic experiment here -- and the paper's headline runs -- sets
`enable_extreme_events=False`, which closes it.

That leaves climate_risk with only linear consumers in a deterministic run:
  `climate.py:529`   effective_damage_multiplier = base * (1 + DAMAGE_RISK_ADJ * (1 - risk))
  `economy.py:393`   climate_adaptation_share = CLIMATE_ADAPT_BASE + SENS * risk
Diffusion toward the neighbourhood mean is mean-preserving, and a mean-preserving
redistribution of a LINEAR function changes nothing in aggregate. Hence exactly 0.000%.
The one nonlinear consumer, the climate-org threshold at `institutions.py:393`
(`if climate_risk < 0.5: continue`), only fires for members of a climate organisation.

So the hypothesis is that the channel is not broken but invisible in the reported
configuration. This runs the same ablation with extreme events ON, over a seeded ensemble
because the events are stochastic, and reports whether diffusion then moves anything.

Writes Paper/revision/results/e18_climate_spatial_with_events.json
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from gim.core.policy import make_policy_map          # noqa: E402
from gim.core.rng import seed_world                  # noqa: E402
from gim.core.simulation import step_world           # noqa: E402
from gim.runtime import load_world                   # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results",
                   "e18_climate_spatial_with_events.json")
HORIZON = 30
N_SEEDS = 12

CONFIGS = {
    "climate_diffusion_on": {},
    "climate_diffusion_off": {"GEOGRAPHY_CLIMATE_LINKS": False,
                              "GEO_CLIMATE_SPILLOVER_W": 0.0},
    "climate_diffusion_x3": {"GEO_CLIMATE_SPILLOVER_W": 0.30},
}


def run(overrides: dict, seed: int, events: bool) -> dict:
    world = load_world(forward_init=True)
    if overrides:
        world.params = world.params.with_overrides(overrides)
    seed_world(world, seed)
    ids = list(world.agents.keys())
    pol = make_policy_map(ids, mode="simple")
    shock_years = 0
    for _ in range(HORIZON):
        world = step_world(world, pol, enable_extreme_events=events)
        shock_years += sum(
            1 for a in ids
            if float(getattr(world.agents[a].economy, "climate_shock_years", 0.0)) > 0.0
        )
    ten = np.array([world.agents[a].society.social_tension for a in ids])
    risk = np.array([world.agents[a].climate.climate_risk for a in ids])
    return {
        "mean_tension": float(ten.mean()),
        "sd_tension": float(ten.std()),
        "mean_climate_risk": float(risk.mean()),
        "sd_climate_risk": float(risk.std()),
        "mean_trust": float(np.mean([world.agents[a].society.trust_gov for a in ids])),
        "world_gdp": float(sum(world.agents[a].economy.gdp for a in ids)),
        "regime_crisis_agents": int(sum(
            world.agents[a].risk.regime_crisis_active_years > 0 for a in ids)),
        "climate_shock_agent_years": shock_years,
    }


def summarise(rows: list) -> dict:
    keys = rows[0].keys()
    return {k: float(np.mean([r[k] for r in rows])) for k in keys}


def main() -> int:
    payload = {
        "experiment": "E18",
        "question": "Is the climate spatial channel inert, or only invisible with extreme "
                    "events switched off?",
        "config": {"horizon": HORIZON, "n_seeds": N_SEEDS, "policy": "simple",
                   "forward_init": True},
        "results": {},
    }

    for events in (False, True):
        tag = "events_on" if events else "events_off"
        print(f"\n--- extreme events {'ON' if events else 'OFF'} "
              f"({N_SEEDS if events else 1} seed{'s' if events else ''}) ---")
        seeds = range(N_SEEDS) if events else [0]
        block = {}
        for name, ov in CONFIGS.items():
            rows = [run(ov, s, events) for s in seeds]
            block[name] = summarise(rows)
        base = block["climate_diffusion_on"]
        print(f"{'config':26s} {'sd(tension)':>12s} {'d%':>8s} {'sd(risk)':>10s} {'d%':>8s} "
              f"{'regime':>7s} {'d%':>8s} {'shock-yrs':>10s}")
        for name, r in block.items():
            def pct(k):
                return 100.0 * (r[k] - base[k]) / base[k] if base[k] else float("nan")
            print(f"{name:26s} {r['sd_tension']:12.6f} {pct('sd_tension'):+8.3f} "
                  f"{r['sd_climate_risk']:10.6f} {pct('sd_climate_risk'):+8.3f} "
                  f"{r['regime_crisis_agents']:7.2f} {pct('regime_crisis_agents'):+8.3f} "
                  f"{r['climate_shock_agent_years']:10.1f}")
            block[name] = {**r, "pct_vs_diffusion_on": {k: pct(k) for k in r}}
        payload["results"][tag] = block

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(os.path.abspath(OUT), "w") as fh:
        json.dump(payload, fh, indent=1)
    print("\nwrote", os.path.abspath(OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
