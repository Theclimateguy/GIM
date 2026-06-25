#!/usr/bin/env python3
"""Does social unrest cascade to geographic NEIGHBOURS? (GEOGRAPHY_TENSION_LINKS realism)

Unrest diffuses across borders (Arab-Spring-style; Braha 2012; Hale 2013). With the switchable spatial
spillover ON, a tension shock in one country should raise its geographic neighbours' tension more than
distant countries'. We isolate the channel's OWN effect with a clean within-country contrast:
  effect_X = tension_X(channel ON) - tension_X(channel OFF)   after a fixed shock at the origin,
then correlate effect_X with closeness (-ln distance). Near countries should be lifted more than far.

Off by default => golden-safe (the 2015-2023 backtest is unchanged: GDP -0.0001, CO2/T ±0).

Run: python3 scripts/diagnose_tension_contagion.py
"""
from __future__ import annotations

import math
import os
import statistics
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from gim.geography import build_geography                         # noqa: E402
from gim.core.world_factory import make_world_from_csv           # noqa: E402
from gim.core.params import default_params                       # noqa: E402
from gim.core.policy import simple_rule_based_policy             # noqa: E402
from gim.core.simulation import step_world                       # noqa: E402

STATE = os.path.join(REPO, "data", "agent_states_operational_2026_calibrated.csv")
ORIGINS = ["Germany", "China", "United States", "India", "Brazil"]
YEARS = 6


def _corr(xs, ys):
    if len(xs) < 3:
        return float("nan")
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    den = math.sqrt(sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys)) or 1e-9
    return cov / den


def _final_tension(links: bool, origin_name: str):
    w = make_world_from_csv(STATE, base_year=2026)
    w.params = default_params().with_overrides({"GEOGRAPHY_TENSION_LINKS": links})
    by_name = {a.name: aid for aid, a in w.agents.items()}
    if origin_name not in by_name:
        return None
    w.agents[by_name[origin_name]].society.social_tension = 0.95
    pol = {aid: simple_rule_based_policy for aid in w.agents}
    mem: dict = {}
    for _ in range(YEARS):
        w = step_world(w, pol, memory=mem, enable_extreme_events=False)
    return {aid: a.society.social_tension for aid, a in w.agents.items()}, by_name[origin_name]


def _gradient(geo, origin_name: str, id2name: dict):
    off = _final_tension(False, origin_name)
    on = _final_tension(True, origin_name)
    if off is None or on is None:
        return None
    t_off, origin = off
    t_on, _ = on
    o_name = id2name[origin]
    xs, ys = [], []
    for aid in t_off:
        if aid == origin:
            continue
        nm = id2name.get(aid, "")
        if not (geo.is_matched(o_name) and geo.is_matched(nm)):
            continue
        d = geo.distance_km(o_name, nm)
        if d and d > 1:
            xs.append(-math.log(d))                 # closeness
            ys.append(t_on[aid] - t_off[aid])       # channel's own effect on this country
    if len(xs) < 5:
        return None
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    k = max(1, len(order) // 3)
    far = statistics.fmean(ys[i] for i in order[:k])
    near = statistics.fmean(ys[i] for i in order[-k:])
    return {"corr": _corr(xs, ys), "near": near, "far": far}


def main() -> int:
    geo = build_geography()
    id2name = {aid: a.name for aid, a in make_world_from_csv(STATE, base_year=2026).agents.items()}
    print("Tension contagion — does unrest cascade to geographic neighbours? (channel ON vs OFF)\n")
    print(f"hubs shocked (averaged): {ORIGINS}; horizon {YEARS}y\n")
    rows = [r for o in ORIGINS if (r := _gradient(geo, o, id2name))]
    corr = statistics.fmean(r["corr"] for r in rows)
    near = statistics.fmean(r["near"] for r in rows)
    far = statistics.fmean(r["far"] for r in rows)
    ratio = near / far if far > 1e-9 else float("inf")
    print(f"channel effect tension(ON)-tension(OFF) vs closeness:")
    print(f"  corr = {corr:+.2f}   near-third effect {near:+.4f}   far-third {far:+.4f}   (near/far {ratio:.1f}x)")
    print()
    if corr > 0.3:
        print("VERDICT: clear geographic contagion — unrest cascades to neighbours.")
    elif near > far:
        print("VERDICT: geographic contagion is PRESENT BUT WEAK — near countries lifted ~%.1fx the far, "
              "but the gradient (corr %+.2f) is much weaker than trade-gravity, because tension is driven "
              "mostly by idiosyncratic domestic factors (inequality, unemployment, crises) that swamp the "
              "neighbour spillover. The spillover weight is an expert prior, NOT literature-anchored "
              "(unlike the trade distance elasticity). Golden unchanged; off by default." % (ratio, corr))
    else:
        print("VERDICT: no geographic gradient.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
