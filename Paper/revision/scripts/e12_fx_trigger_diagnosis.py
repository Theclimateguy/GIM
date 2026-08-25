#!/usr/bin/env python3
"""E12 -- fix 2: why does the fx crisis trigger never fire?

E1 found zero fx crises across 30 years, 57 agents and every coupling configuration. The
trigger (gim/core/social.py:_fx_crisis_inputs + check_fx_crisis) is a conjunction of three
conditions:

    external_debt_ratio    > FX_CRISIS_EXTERNAL_DEBT_THRESHOLD          (0.50)
    current_account_ratio  < FX_CRISIS_CURRENT_ACCOUNT_DEFICIT_THRESHOLD (-0.04)
    fx_cover_months        < FX_CRISIS_RESERVE_MONTHS_THRESHOLD          (3.0)

A conjunction can fail in three different ways, and they need different fixes:
  (a) one of the three inputs never moves at all -- a plumbing bug;
  (b) each condition fires sometimes but never simultaneously -- a specification problem;
  (c) all three are simply far from their thresholds -- a calibration problem.

This records the three inputs per agent per year over a 30-year forward run and reports,
for each condition, how often it is met, how close it gets, and how often pairs and the
full triple coincide. `n_two_of_three` is the diagnostic number: if it is large while
`n_three_of_three` is zero, the trigger is over-specified rather than mis-plumbed.

Writes Paper/revision/results/e12_fx_trigger_diagnosis.json
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

from gim.core.params import resolve_params           # noqa: E402
from gim.core.policy import make_policy_map          # noqa: E402
from gim.core.simulation import step_world           # noqa: E402
from gim.core.social import _fx_crisis_inputs        # noqa: E402
from gim.runtime import load_world                   # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results",
                   "e12_fx_trigger_diagnosis.json")
HORIZON = 30
BASE_YEAR = 2023


def main() -> int:
    world = load_world(forward_init=True)
    cal = resolve_params(world)
    thr = {
        "external_debt_ratio": float(cal.FX_CRISIS_EXTERNAL_DEBT_THRESHOLD),
        "current_account_ratio": float(cal.FX_CRISIS_CURRENT_ACCOUNT_DEFICIT_THRESHOLD),
        "fx_cover_months": float(cal.FX_CRISIS_RESERVE_MONTHS_THRESHOLD),
    }
    print("thresholds:", thr)

    policies = make_policy_map(list(world.agents.keys()), mode="simple")
    ids = list(world.agents.keys())

    rec = {k: [] for k in thr}
    met = {k: 0 for k in thr}
    combo = Counter()
    n_obs = 0
    per_agent_best = {a: 0 for a in ids}

    for _ in range(HORIZON):
        world = step_world(world, policies, enable_extreme_events=False)
        for aid in ids:
            agent = world.agents[aid]
            f = _fx_crisis_inputs(agent, world)
            ed = float(f["external_debt_ratio"])
            ca = float(f["current_account_ratio"])
            fc = float(f["fx_cover_months"])
            rec["external_debt_ratio"].append(ed)
            rec["current_account_ratio"].append(ca)
            rec["fx_cover_months"].append(fc)
            c1 = ed > thr["external_debt_ratio"]
            c2 = ca < thr["current_account_ratio"]
            c3 = fc < thr["fx_cover_months"]
            met["external_debt_ratio"] += int(c1)
            met["current_account_ratio"] += int(c2)
            met["fx_cover_months"] += int(c3)
            combo[(c1, c2, c3)] += 1
            per_agent_best[aid] = max(per_agent_best[aid], int(c1) + int(c2) + int(c3))
            n_obs += 1

    dist = {}
    for k, v in rec.items():
        v = np.array(v)
        dist[k] = {
            "min": float(v.min()), "p05": float(np.quantile(v, 0.05)),
            "median": float(np.median(v)), "p95": float(np.quantile(v, 0.95)),
            "max": float(v.max()), "sd": float(v.std()),
            "threshold": thr[k],
            "share_meeting_condition": met[k] / n_obs,
            "is_constant": bool(v.std() < 1e-12),
        }

    n_two = sum(c for k, c in combo.items() if sum(k) == 2)
    n_three = sum(c for k, c in combo.items() if sum(k) == 3)

    if any(d["is_constant"] for d in dist.values()):
        verdict = "plumbing: at least one input never moves"
    elif n_three == 0 and n_two > 0:
        verdict = ("over-specified: the three conditions each fire but never coincide "
                   "-- the conjunction is the problem, not the levels")
    elif n_three == 0:
        verdict = "calibration: conditions rarely fire even individually"
    else:
        verdict = "trigger does fire"

    print(f"\nobservations: {n_obs} agent-years ({len(ids)} agents x {HORIZON} years)\n")
    print(f"{'input':24s} {'threshold':>10s} {'min':>10s} {'median':>10s} {'max':>10s} "
          f"{'sd':>9s} {'% meeting':>10s}")
    for k, d in dist.items():
        print(f"{k:24s} {d['threshold']:10.3f} {d['min']:10.3f} {d['median']:10.3f} "
              f"{d['max']:10.3f} {d['sd']:9.4f} {d['share_meeting_condition']*100:9.2f}%")

    print("\nconjunction (external_debt, current_account, fx_cover):")
    for k in sorted(combo, key=lambda t: -combo[t]):
        print(f"   {str(k):22s} {combo[k]:7d}  ({combo[k]/n_obs*100:5.2f}%)")
    print(f"\n   two of three: {n_two} ({n_two/n_obs*100:.2f}%)   "
          f"all three: {n_three}")
    print(f"   agents ever reaching 2/3: "
          f"{sum(1 for v in per_agent_best.values() if v >= 2)}/{len(ids)}   "
          f"3/3: {sum(1 for v in per_agent_best.values() if v == 3)}/{len(ids)}")
    print(f"\nverdict: {verdict}")

    payload = {
        "experiment": "E12",
        "question": "Which of the three fx-trigger conditions blocks, and is the failure "
                    "plumbing, specification or calibration?",
        "config": {"horizon": HORIZON, "base_year": BASE_YEAR, "n_agents": len(ids),
                   "n_observations": n_obs, "thresholds": thr},
        "input_distributions": dist,
        "conjunction_counts": {str(k): v for k, v in combo.items()},
        "n_two_of_three": n_two,
        "n_three_of_three": n_three,
        "agents_ever_two_of_three": sum(1 for v in per_agent_best.values() if v >= 2),
        "verdict": verdict,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(os.path.abspath(OUT), "w") as fh:
        json.dump(payload, fh, indent=1)
    print("wrote", os.path.abspath(OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
