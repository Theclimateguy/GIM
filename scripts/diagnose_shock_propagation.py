#!/usr/bin/env python3
"""G3 — does a shock cascade LOCALLY (gravity trade) or UNIFORMLY (flat trade)? (Appendix B realism)

GIM already propagates sovereign stress through the trade network: a country's effective interest rate
rises with its trade-weighted exposure to distressed partners (debt-spread contagion,
gim/core/economy.py:~339, weighted by effective_trade_intensity). With FLAT trade (every link 0.5) that
exposure is distance-agnostic, so a debt shock spreads to everyone equally — unrealistic. With
GRAVITY trade, exposure decays with distance, so the shock concentrates on geographic neighbours — the
empirical pattern.

This injects a deep debt shock into a hub country and measures every other country's borrowing-cost
response as a function of distance, flat vs gravity. No stepping needed — the contagion is in the rate.

Run: python3 scripts/diagnose_shock_propagation.py
"""
from __future__ import annotations

import math
import os
import statistics
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from gim.geography import build_geography                              # noqa: E402
from gim.core.world_factory import make_world_from_csv                # noqa: E402
from gim.core.params import default_params                            # noqa: E402
from gim.core.economy import compute_effective_interest_rate          # noqa: E402
from gim.core.political_dynamics import _apply_trade_gravity_once      # noqa: E402

STATE = os.path.join(REPO, "data", "agent_states_operational.csv")
ORIGINS = ["Germany", "China", "United States", "Brazil", "India"]   # hubs, averaged for robustness


def _corr(xs, ys):
    if len(xs) < 3:
        return float("nan")
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    den = math.sqrt(sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys)) or 1e-9
    return cov / den


def _rates(world):
    return {aid: compute_effective_interest_rate(a, world) for aid, a in world.agents.items()}


def _gradient(geo, gravity: bool, origin_name: str):
    world = make_world_from_csv(STATE, base_year=2023)
    name = {aid: a.name for aid, a in world.agents.items()}
    by_name = {a.name: aid for aid, a in world.agents.items()}
    if origin_name not in by_name:
        return None
    if gravity:
        world.params = default_params().with_overrides({"TRADE_GRAVITY_INIT": True})
        _apply_trade_gravity_once(world, world.params)

    base = _rates(world)
    origin = by_name[origin_name]
    world.agents[origin].economy.public_debt = 3.0 * max(world.agents[origin].economy.gdp, 1e-9)
    world.agents[origin].risk.debt_crisis_prone = 0.9
    shocked = _rates(world)

    xs, ys = [], []
    for aid in world.agents:
        if aid == origin:
            continue
        d = geo.distance_km(name[origin], name[aid]) if (geo.is_matched(origin_name) and geo.is_matched(name[aid])) else None
        if d and d > 1:
            xs.append(-math.log(d))                 # closeness
            ys.append(shocked[aid] - base[aid])     # borrowing-cost rise (basis of cascade)
    if len(xs) < 5:
        return None
    # near third vs far third by distance
    order = sorted(range(len(xs)), key=lambda i: xs[i])   # ascending closeness = farthest first
    k = max(1, len(order) // 3)
    far = statistics.fmean(ys[i] for i in order[:k])
    near = statistics.fmean(ys[i] for i in order[-k:])
    return {"corr": _corr(xs, ys), "near": near, "far": far}


def _summary(geo, gravity):
    rows = [r for o in ORIGINS if (r := _gradient(geo, gravity, o))]
    corr = statistics.fmean(r["corr"] for r in rows)
    near = statistics.fmean(r["near"] for r in rows)
    far = statistics.fmean(r["far"] for r in rows)
    ratio = near / far if far > 1e-9 else float("inf")
    return corr, near, far, ratio, len(rows)


def main() -> int:
    geo = build_geography()
    print("G3 — shock propagation: does a debt shock cascade locally (gravity) or uniformly (flat)?\n")
    print(f"hubs shocked (averaged): {ORIGINS}\n")
    print(f"{'trade network':<16}{'corr(Δrate, closeness)':>24}{'near/far Δrate':>18}")
    out = {}
    for label, grav in (("flat (current)", False), ("gravity", True)):
        corr, near, far, ratio, n = _summary(geo, grav)
        out[label] = (corr, ratio)
        print(f"{label:<16}{corr:>+24.2f}{ratio:>18.1f}x")

    corr_flat = out["flat (current)"][0]
    corr_grav = out["gravity"][0]
    print()
    if corr_grav - corr_flat > 0.2:
        print("VERDICT: under GRAVITY a debt shock concentrates on geographic neighbours (borrowing costs "
              "rise far more for near than far countries); under FLAT it spreads ~uniformly. The "
              "cross-domain shock propagation becomes geographically realistic — the Appendix B claim, "
              "demonstrated. (Golden unaffected: feature off by default; backtest in band, see G1.)")
    else:
        print("VERDICT: no clear locality gain in this channel — investigate before claiming realism.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
