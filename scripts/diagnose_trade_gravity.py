#!/usr/bin/env python3
"""Golden-safe diagnostic: does gravity-vs-flat trade initialisation move the ENSEMBLE aggregate?

GIM initialises every bilateral trade_intensity flat at 0.5 (world_factory). Trade gravity (bilateral
trade ∝ GDP_i·GDP_j / distance^δ, δ≈0.9 — the most robust regularity in trade economics, Head & Mayer
2014) is empirically the right structure. The strategic question: would grounding trade in gravity give
a SUBSTANTIAL gain in the headline ensemble forecast — which tracks GLOBAL SUMS (world_gdp, temperature,
co2)? Hypothesis: no — geography reshuffles WHO trades with WHOM, a redistribution that nearly cancels
in the sum; the network is transformed but the aggregate barely moves.

This sets gravity intensities on a copy of the world (no core change) and compares the central
trajectory to the flat baseline. Pure measurement.

Run: python3 scripts/diagnose_trade_gravity.py
"""
from __future__ import annotations

import math
import os
import statistics
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from gim.geography import build_geography                 # noqa: E402
from gim.core.world_factory import make_world_from_csv    # noqa: E402
from gim.core.simulation import step_world                # noqa: E402
from gim.core.policy import simple_rule_based_policy      # noqa: E402

STATE = os.path.join(REPO, "data", "agent_states_operational_2026_calibrated.csv")
DELTA = 0.9          # gravity distance elasticity (Head & Mayer 2014 ~ -0.9)
RUN_YEARS = 20


def _set_gravity_trade(world, geo):
    """Overwrite trade_intensity with a gravity prediction, sigmoid-mapped to [0,1], mean ≈ 0.5.

    Centring at 0.5 matches the flat baseline's LEVEL, so any aggregate difference is due to the
    redistribution (network STRUCTURE), not a change in average trade level.
    """
    name = {aid: a.name for aid, a in world.agents.items()}
    gdp = {aid: max(a.economy.gdp, 1e-9) for aid, a in world.agents.items()}
    dists = [d for d in (geo.distance_km(name[i], name[j])
                         for i in world.agents for j in world.agents if i < j) if d]
    med = statistics.median(dists) if dists else 5000.0

    raw = {}
    for i, rels in world.relations.items():
        for j in rels:
            d = geo.distance_km(name[i], name[j]) if (geo.is_matched(name[i]) and geo.is_matched(name[j])) else None
            d = d if d and d > 1.0 else med
            raw[(i, j)] = math.log(gdp[i] * gdp[j]) - DELTA * math.log(d)
    vals = list(raw.values())
    mu, sd = statistics.fmean(vals), (statistics.pstdev(vals) or 1.0)
    corr_n = 0
    for (i, j), lg in raw.items():
        world.relations[i][j].trade_intensity = 1.0 / (1.0 + math.exp(-(lg - mu) / sd))
    return raw, name


def _run(world):
    pol = {aid: simple_rule_based_policy for aid in world.agents}
    mem: dict = {}
    for _ in range(RUN_YEARS):
        world = step_world(world, pol, memory=mem, enable_extreme_events=False)
    gs = world.global_state
    return {"world_gdp": sum(a.economy.gdp for a in world.agents.values()),
            "temperature": gs.temperature_global, "co2": gs.co2}


def _structure(world, raw, name, geo):
    """Correlation of trade_intensity with -ln(distance): ~0 for flat, strongly + under gravity."""
    xs, ys = [], []
    for i, rels in world.relations.items():
        for j, rel in rels.items():
            if i < j and geo.is_matched(name[i]) and geo.is_matched(name[j]):
                d = geo.distance_km(name[i], name[j])
                if d and d > 1:
                    xs.append(-math.log(d)); ys.append(rel.trade_intensity)
    if len(xs) < 3:
        return float("nan"), 0.0
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    den = math.sqrt(sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys)) or 1e-9
    return cov / den, statistics.pstdev(ys)


def main() -> int:
    geo = build_geography()
    print("Trade-gravity diagnostic — does gravity-vs-flat trade move the ensemble aggregate?\n")

    w_flat = make_world_from_csv(STATE, base_year=2026)
    name = {aid: a.name for aid, a in w_flat.agents.items()}
    corr_flat, sd_flat = _structure(w_flat, {}, name, geo)
    flat = _run(w_flat)

    w_grav = make_world_from_csv(STATE, base_year=2026)
    raw, name = _set_gravity_trade(w_grav, geo)
    corr_grav, sd_grav = _structure(w_grav, raw, name, geo)
    grav = _run(w_grav)

    print("network STRUCTURE at t0 (trade_intensity vs -ln distance):")
    print(f"  flat   : corr = {corr_flat:+.2f}   spread(sd) = {sd_flat:.3f}  (uniform 0.5)")
    print(f"  gravity: corr = {corr_grav:+.2f}   spread(sd) = {sd_grav:.3f}  (distance-decayed)\n")

    print(f"central {RUN_YEARS}y forecast (global aggregates):")
    for k in ("world_gdp", "temperature", "co2"):
        a, b = flat[k], grav[k]
        d = 100.0 * (b - a) / a if a else float("nan")
        print(f"  {k:12s}: flat {a:12.3f}  gravity {b:12.3f}  -> {d:+.2f}%")

    gdp_shift = abs(100.0 * (grav["world_gdp"] - flat["world_gdp"]) / flat["world_gdp"])
    print()
    print("VERDICT: gravity TRANSFORMS the trade network (corr ~0 -> strong) but world_gdp shifts "
          f"{gdp_shift:.2f}% over {RUN_YEARS}y -- " +
          ("≈ no leverage on the headline aggregate forecast, as hypothesised: the gain (if any) is in "
           "network realism / shock propagation, not aggregate skill." if gdp_shift < 3.0 else
           "a non-trivial aggregate shift -- worth a fuller ensemble check."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
