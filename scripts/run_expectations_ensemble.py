#!/usr/bin/env python3
"""Ensemble crisis ablation for E4.3 near-rational expectations — is the stress-response ROBUST?

The single-seed ablation (scripts/run_expectations_ablation.py) found expectations ON cuts GDP-2100
under crisis (~-2%) but barely moves it under calm (~0). One seed is a demonstration, not a test.
This script repeats the off-vs-on, calm-vs-crisis contrast across N seeds — common random numbers
WITHIN each seed (identical shocks; only expectation-formation differs) — and reports the DISTRIBUTION
of the on-off GDP-2100 effect. The stress-response claim survives only if, across seeds:

  * crisis effect is robustly negative (CI excludes 0),
  * calm effect straddles 0,
  * the paired (crisis - calm) gap is robustly negative.

Run: python3 scripts/run_expectations_ensemble.py [N_SEEDS=20]
"""
from __future__ import annotations

import math
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

# t_0.975 by degrees of freedom (fallback to the normal 1.96 for large df).
_T975 = {1: 12.71, 2: 4.30, 3: 3.18, 4: 2.78, 5: 2.57, 6: 2.45, 7: 2.36, 8: 2.31, 9: 2.26,
         10: 2.23, 11: 2.20, 12: 2.18, 13: 2.16, 14: 2.14, 15: 2.13, 16: 2.12, 17: 2.11,
         18: 2.10, 19: 2.09, 20: 2.09, 24: 2.06, 29: 2.05, 39: 2.02, 49: 2.01}


def _world_gdp(w):
    return sum(a.economy.gdp for a in w.agents.values())


def run_gdp2100(exp_on: bool, events: bool, seed: int) -> float:
    w = make_world_from_csv(STATE, base_year=2023)
    w.params = default_params().with_overrides(EXP_ON if exp_on else {})
    seed_world(w, seed)
    pol = make_policy_map(w.agents.keys(), mode="simple")
    for _ in range(YEARS):
        w = step_world(w, pol, enable_extreme_events=events)
    return _world_gdp(w)


def _t(df: int) -> float:
    if df <= 0:
        return float("nan")
    if df in _T975:
        return _T975[df]
    return 1.96 if df >= 50 else _T975[min(_T975, key=lambda k: abs(k - df))]


def describe(xs: list[float]) -> dict:
    n = len(xs)
    m = statistics.mean(xs)
    sd = statistics.stdev(xs) if n > 1 else 0.0
    se = sd / math.sqrt(n) if n else 0.0
    h = _t(n - 1) * se
    return {"n": n, "mean": m, "median": statistics.median(xs), "sd": sd,
            "lo": m - h, "hi": m + h, "min": min(xs), "max": max(xs),
            "share_neg": sum(1 for x in xs if x < 0) / n}


def _fmt(d: dict) -> str:
    return (f"mean {d['mean']:+.2f}%  95%CI [{d['lo']:+.2f}, {d['hi']:+.2f}]  "
            f"median {d['median']:+.2f}%  sd {d['sd']:.2f}  range [{d['min']:+.2f}, {d['max']:+.2f}]  "
            f"share<0 {d['share_neg']*100:.0f}%")


def main() -> int:
    n_seeds = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    print(f"E4.3 expectations ENSEMBLE ablation — {n_seeds} seeds, on-off GDP-2100 effect (CRN within seed)\n")
    eff = {"calm": [], "crisis": []}
    for seed in range(n_seeds):
        line = [f"seed {seed:>2}:"]
        for env, events in (("calm", False), ("crisis", True)):
            off = run_gdp2100(False, events, seed)
            on = run_gdp2100(True, events, seed)
            e = 100.0 * (on / off - 1.0)
            eff[env].append(e)
            line.append(f"{env} {e:+.2f}%")
        print("  ".join(line), flush=True)

    calm, crisis = describe(eff["calm"]), describe(eff["crisis"])
    paired = [c - k for c, k in zip(eff["crisis"], eff["calm"])]
    pd = describe(paired)
    share_cris_below = sum(1 for d in paired if d < 0) / len(paired)

    print("\n=== distribution of the expectations (on - off) GDP-2100 effect ===")
    print(f"  CALM   : {_fmt(calm)}")
    print(f"  CRISIS : {_fmt(crisis)}")
    print(f"  PAIRED crisis-calm : mean {pd['mean']:+.2f}pp  95%CI [{pd['lo']:+.2f}, {pd['hi']:+.2f}]  "
          f"share(crisis<calm) {share_cris_below*100:.0f}%")

    crisis_neg = crisis["hi"] < 0
    calm_straddles = calm["lo"] <= 0 <= calm["hi"]
    gap_neg = pd["hi"] < 0
    print("\n=== verdict ===")
    print(f"  crisis effect robustly negative (CI<0):       {crisis_neg}")
    print(f"  calm effect straddles 0:                      {calm_straddles}")
    print(f"  paired crisis-calm gap robustly negative:     {gap_neg}")
    if crisis_neg and gap_neg:
        print("  -> STRESS-RESPONSE VALIDATED across the ensemble (not a single-seed artefact).")
    elif gap_neg:
        print("  -> Partial: crisis is reliably MORE adverse than calm, but the crisis CI touches 0.")
    else:
        print("  -> NOT robust: the single-seed contrast does not survive the ensemble.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
