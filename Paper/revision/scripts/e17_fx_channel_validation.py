#!/usr/bin/env python3
"""E17 -- does the repaired fx channel fire at a plausible rate?

E12 found the currency-crisis trigger structurally dead: `net_exports` is written only by
executed bilateral trade deals, no scripted policy proposes any, so the current account was
identically zero and the conjunction could never complete -- although its other two
conditions coincided in 63.68% of agent-years.

The repair has three parts, all switchable:
  RESOURCE_TRADE_GDP_SHARE      convert resource trade value into GDP units (it was ~300x too
                                large: the world sum of net import bills was 3190% of world GDP)
  IMPORT_COVER_TOTAL_MULTIPLIER months-of-cover is defined against TOTAL imports, not the
                                resource bill alone
  STRUCTURAL_TRADE_BALANCE      write the resource trade balance into net_exports, demeaned pro
                                rata to GDP so the world closes exactly

A repaired channel that fires constantly is no more useful than one that never fires. The
reference is the observed frequency of currency crises: Laeven & Valencia's banking, currency
and sovereign debt crisis database records currency crises in roughly 3-5% of country-years
over 1970-2017. This measures ONSETS per agent-year, not active years, because a long
`FX_CRISIS_MAX_YEARS` inflates the active count without implying more crises.

Writes Paper/revision/results/e17_fx_channel_validation.json
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from gim.core.policy import make_policy_map          # noqa: E402
from gim.core.simulation import step_world           # noqa: E402
from gim.core.social import _fx_crisis_inputs        # noqa: E402
from gim.runtime import load_world                   # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results",
                   "e17_fx_channel_validation.json")
HORIZON = 30
BASE_YEAR = 2023
REPAIR = {"STRUCTURAL_TRADE_BALANCE": True}
# Laeven & Valencia: currency crises in roughly 3-5% of country-years, 1970-2017.
TARGET_LO, TARGET_HI = 0.03, 0.05

THRESHOLD_GRID = [
    {},
    {"FX_CRISIS_CURRENT_ACCOUNT_DEFICIT_THRESHOLD": -0.06},
    {"FX_CRISIS_CURRENT_ACCOUNT_DEFICIT_THRESHOLD": -0.08},
    {"FX_CRISIS_RESERVE_MONTHS_THRESHOLD": 2.0},
    {"FX_CRISIS_CURRENT_ACCOUNT_DEFICIT_THRESHOLD": -0.06,
     "FX_CRISIS_RESERVE_MONTHS_THRESHOLD": 2.0},
    {"FX_CRISIS_CURRENT_ACCOUNT_DEFICIT_THRESHOLD": -0.08,
     "FX_CRISIS_RESERVE_MONTHS_THRESHOLD": 2.0},
    {"FX_CRISIS_EXTERNAL_DEBT_THRESHOLD": 0.70,
     "FX_CRISIS_CURRENT_ACCOUNT_DEFICIT_THRESHOLD": -0.06,
     "FX_CRISIS_RESERVE_MONTHS_THRESHOLD": 2.0},
]


def run(overrides: dict) -> dict:
    world = load_world(forward_init=True)
    if overrides:
        world.params = world.params.with_overrides(overrides)
    ids = list(world.agents.keys())
    pol = make_policy_map(ids, mode="simple")
    prev = {a: 0 for a in ids}
    onsets, active, per_agent = 0, 0, Counter()
    ca_all, cov_all, ext_all = [], [], []
    for _ in range(HORIZON):
        world = step_world(world, pol, enable_extreme_events=False)
        for a in ids:
            y = int(world.agents[a].risk.fx_crisis_active_years)
            if y > 0:
                active += 1
            if y == 1 and prev[a] == 0:
                onsets += 1
                per_agent[a] += 1
            prev[a] = y
            f = _fx_crisis_inputs(world.agents[a], world)
            ca_all.append(f["current_account_ratio"])
            cov_all.append(f["fx_cover_months"])
            ext_all.append(f["external_debt_ratio"])
    # Agents that cannot have a conventional currency crisis are exempt by construction, so the
    # frequency has to be computed over ELIGIBLE agent-years, not all of them.
    from gim.core.params import resolve_params
    _cal = resolve_params(world)
    _exempt = set(getattr(_cal, "FX_CRISIS_MONETARY_EXEMPT_AGENTS", ()) or ())
    eligible = [a for a in ids
                if a not in _exempt and getattr(world.agents[a], "name", None) not in _exempt]
    n_obs = len(ids) * HORIZON
    n_eligible_obs = max(1, len(eligible) * HORIZON)
    ca, cov, ext = np.array(ca_all), np.array(cov_all), np.array(ext_all)
    return {
        "overrides": {k: v for k, v in overrides.items()},
        "n_agent_years": n_obs,
        "onsets": onsets,
        "onset_rate_per_agent_year": onsets / n_obs,
        "n_eligible_agents": len(eligible),
        "onset_rate_per_eligible_agent_year": onsets / n_eligible_obs,
        "active_agent_years": active,
        "active_rate": active / n_obs,
        "n_distinct_agents_affected": len(per_agent),
        "mean_onsets_per_affected_agent": (sum(per_agent.values()) / len(per_agent)
                                           if per_agent else 0.0),
        "mean_duration_years": active / onsets if onsets else float("nan"),
        "current_account_median": float(np.median(ca)),
        "current_account_p05": float(np.quantile(ca, 0.05)),
        "cover_months_median": float(np.median(cov)),
        "share_cover_below_3mo": float((cov < 3.0).mean()),
        "share_external_debt_above_0.5": float((ext > 0.5).mean()),
    }


def main() -> int:
    dead = run({})
    print(f"reference run: onsets {dead['onsets']}, "
          f"rate/eligible {dead['onset_rate_per_eligible_agent_year']:.4f}, "
          f"eligible agents {dead['n_eligible_agents']}")

    rows = {}
    print(f"\n{'thresholds':58s} {'onsets':>7s} {'rate/el':>8s} {'agents':>7s} "
          f"{'dur':>6s} {'active':>8s}")
    for extra in THRESHOLD_GRID:
        ov = {**REPAIR, **extra}
        r = run(ov)
        label = ", ".join(f"{k.replace('FX_CRISIS_','').lower()}={v:g}"
                          for k, v in extra.items()) or "published thresholds"
        rows[label] = r
        rate = r["onset_rate_per_eligible_agent_year"]
        flag = "  <-- in range" if TARGET_LO <= rate <= TARGET_HI else ""
        print(f"{label:58s} {r['onsets']:7d} {rate:8.4f} "
              f"{r['n_distinct_agents_affected']:7d} {r['mean_duration_years']:6.2f} "
              f"{r['active_rate']:8.3f}{flag}")

    in_range = [k for k, v in rows.items()
                if TARGET_LO <= v["onset_rate_per_eligible_agent_year"] <= TARGET_HI]
    payload = {
        "experiment": "E17",
        "question": "After repair, does the fx channel fire at a plausible frequency?",
        "reference": ("Laeven & Valencia crisis database: currency crises in roughly 3-5% of "
                      "country-years, 1970-2017"),
        "target_onset_rate": [TARGET_LO, TARGET_HI],
        "config": {"horizon": HORIZON, "base_year": BASE_YEAR, "policy": "simple",
                   "extreme_events": False, "forward_init": True},
        "before_repair": dead,
        "after_repair_by_thresholds": rows,
        "threshold_sets_in_target_range": in_range,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(os.path.abspath(OUT), "w") as fh:
        json.dump(payload, fh, indent=1)
    print(f"\nin target range {TARGET_LO:.0%}-{TARGET_HI:.0%}: {in_range or 'none'}")
    print("wrote", os.path.abspath(OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
