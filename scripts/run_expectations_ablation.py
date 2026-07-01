#!/usr/bin/env python3
"""Crisis-scenario ablation for E4.3 near-rational expectations — the honest test.

The baseline (events-off) forward ablation showed the expectations channel barely moves the smooth
trajectory (~+0.1% GDP-2100). The honest claim is that it is a *stress-response* feature: it bites
when shocks open a gap between the model-consistent forecast and the backward-looking proxy. This
script makes that contrast explicit -- it runs the expectations channel OFF vs ON under two
environments, CALM (extreme events off) and CRISIS (extreme events on), with common random numbers
(same seed) so the shocks are identical and the only difference is how agents form expectations.

Reports world GDP-2100 and the volatility of annual world-GDP growth and world-mean inflation.

Run: python3 scripts/run_expectations_ablation.py
"""
from __future__ import annotations

import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gim.core.params import default_params       # noqa: E402
from gim.core.policy import make_policy_map       # noqa: E402
from gim.core.rng import seed_world               # noqa: E402
from gim.core.simulation import step_world        # noqa: E402
from gim.core.world_factory import make_world_from_csv  # noqa: E402

STATE = "data/agent_states_operational.csv"
YEARS = 74  # 2026 -> 2100
EXP_ON = {"EXPECTATIONS_HORIZON": 3, "EXPECTATIONS_FORESIGHT": 0.5, "EXPECTATIONS_INFLATION_WEIGHT": 0.65}


def _world_gdp(w):
    return sum(a.economy.gdp for a in w.agents.values())


def _world_infl(w):
    n = len(w.agents)
    return sum(float(getattr(a.economy, "inflation", 0.0)) for a in w.agents.values()) / max(n, 1)


def run(exp_on: bool, events: bool):
    w = make_world_from_csv(STATE, base_year=2023)
    w.params = default_params().with_overrides(EXP_ON if exp_on else {})
    seed_world(w, 0)
    pol = make_policy_map(w.agents.keys(), mode="simple")
    gdp = [_world_gdp(w)]
    infl = [_world_infl(w)]
    for _ in range(YEARS):
        w = step_world(w, pol, enable_extreme_events=events)
        gdp.append(_world_gdp(w))
        infl.append(_world_infl(w))
    growth = [(gdp[i + 1] - gdp[i]) / gdp[i] for i in range(len(gdp) - 1) if gdp[i] > 0]
    return {
        "gdp2100": gdp[-1],
        "gdp_growth_vol": statistics.pstdev(growth) * 100,   # %-points
        "infl_vol": statistics.pstdev(infl) * 100,           # %-points
    }


def main() -> int:
    print("E4.3 expectations ablation — off vs on, under calm vs crisis (common random numbers)\n")
    print(f"{'environment':>10} | {'expectations':>12} | {'GDP2100($T)':>11} | {'growth vol':>10} | {'infl vol':>9}")
    print("-" * 66)
    rows = {}
    for env, events in (("calm", False), ("crisis", True)):
        for label, on in (("off", False), ("on", True)):
            r = run(on, events)
            rows[(env, label)] = r
            print(f"{env:>10} | {label:>12} | {r['gdp2100']:>11.1f} | {r['gdp_growth_vol']:>9.2f}% | {r['infl_vol']:>8.2f}%")

    def eff(env, key):
        return rows[(env, "on")][key] - rows[(env, "off")][key]
    print("\nexpectations effect (on - off):")
    for env in ("calm", "crisis"):
        dg = 100 * (rows[(env, "on")]["gdp2100"] / rows[(env, "off")]["gdp2100"] - 1)
        print(f"  {env:>6}: GDP2100 {dg:+.2f}%   growth-vol {eff(env, 'gdp_growth_vol'):+.2f}pp   "
              f"infl-vol {eff(env, 'infl_vol'):+.2f}pp")
    print("\nReading: a small calm effect but a materially larger crisis effect confirms the channel is a "
          "stress-response feature, not a baseline-growth shifter.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
