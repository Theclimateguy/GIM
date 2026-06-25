#!/usr/bin/env python3
"""Golden-safe diagnostic: how much geographic signal does GIM's conflict block ignore?

GIM's escalation/`border_incident` target is chosen by argmax(conflict_level + 0.5*(1-trust)) — with NO
adjacency term (gim/core/geopolitics._auto_security_action). This script quantifies whether that matters,
WITHOUT changing the core:

  1. base rate  — fraction of country pairs that are geographic neighbours (the chance level).
  2. real world — UCDP/PRIO INTERSTATE conflict dyads (1990-2023): how often are the two states neighbours?
  3. GIM        — run the model and record each actor's escalation target; how often is it a neighbour?

If real interstate conflict is far more local than chance while GIM's escalation targets are not, geography
carries large unused signal and wiring it in (adjacency for border_incident, distance for migration) is
worthwhile. If GIM is already as local as reality, it is not. Pure measurement; nothing is wired in here.

Run: python3 scripts/diagnose_border_geography.py
"""
from __future__ import annotations

import csv
import os
import re
import statistics
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from gim.geography import build_geography, all_geojson_names    # noqa: E402
from gim.core.world_factory import make_world_from_csv          # noqa: E402
from gim.core.simulation import step_world                      # noqa: E402
from gim.core.policy import simple_rule_based_policy            # noqa: E402

STATE = os.path.join(REPO, "data", "agent_states_operational_2026_calibrated.csv")
UCDP = os.path.join(REPO, "data", "external", "raw", "ucdp-prio-acd-241.csv")
WINDOW = (1990, 2023)
RUN_YEARS = 20
ESCALATION_CONFLICT_FLOOR = 0.45   # the border_incident trigger gate in _auto_security_action


# UCDP side spelling -> geojson country name (only where they differ from the geojson `name`).
_UCDP_TO_GEOJSON = {
    "DR Congo": "Democratic Republic of the Congo", "Congo": "Republic of the Congo",
    "Bosnia-Herzegovina": "Bosnia and Herzegovina", "Ivory Coast": "Cote d'Ivoire",
    "Macedonia": "North Macedonia", "Yugoslavia": "Serbia", "Serbia": "Serbia",
    "Tanzania": "United Republic of Tanzania", "Guinea-Bissau": "Guinea Bissau",
    "United States of America": "United States of America", "Cambodia": "Cambodia",
}


def _clean(side: str) -> str:
    return re.sub(r"\s*\(.*?\)", "", str(side)).replace("Government of", "").strip()


def _resolve_geojson(name: str, geo) -> str | None:
    if name in geo.centroids:
        return name
    alias = _UCDP_TO_GEOJSON.get(name)
    return alias if alias and alias in geo.centroids else None


def real_conflict_locality(geo):
    """Interstate dyads over the FULL world geography (not just GIM agents) — a credible sample."""
    dyads = set()
    with open(UCDP, encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            if str(r.get("type_of_conflict", "")).strip() != "2":   # interstate only
                continue
            try:
                yr = int(float(r.get("year", "")))
            except ValueError:
                continue
            if not (WINDOW[0] <= yr <= WINDOW[1]):
                continue
            a = _resolve_geojson(_clean(r.get("side_a", "")), geo)
            b = _resolve_geojson(_clean(r.get("side_b", "")), geo)
            if a and b and a != b:
                dyads.add(frozenset((a, b)))
    return _summarise(geo, [tuple(d) for d in dyads])


def gim_escalation_locality(geo):
    world = make_world_from_csv(STATE, base_year=2026)
    pol = {aid: simple_rule_based_policy for aid in world.agents}
    mem: dict = {}
    pairs = []
    for _ in range(RUN_YEARS):
        for aid, rels in world.relations.items():
            best, best_score = None, ESCALATION_CONFLICT_FLOOR
            for tid, rel in rels.items():
                if tid == aid or rel.conflict_level < ESCALATION_CONFLICT_FLOOR:
                    continue
                score = rel.conflict_level + 0.5 * (1.0 - rel.trust)
                if score > best_score:
                    best_score, best = score, tid
            if best is not None:
                pairs.append((world.agents[aid].name, world.agents[best].name))
        world = step_world(world, pol, memory=mem, enable_extreme_events=False)
    return _summarise(geo, pairs)


def _summarise(geo, pairs):
    located = [(a, b) for a, b in pairs if geo.is_matched(a) and geo.is_matched(b)]
    if not located:
        return {"n": 0, "n_located": 0, "adj_frac": float("nan"), "median_km": float("nan")}
    adj = sum(geo.is_adjacent(a, b) for a, b in located)
    dists = [geo.distance_km(a, b) for a, b in located]
    return {"n": len(pairs), "n_located": len(located),
            "adj_frac": adj / len(located), "median_km": statistics.median(dists)}


def main() -> int:
    geo_world = build_geography(all_geojson_names())   # full reference world (credible conflict sample)
    geo_agents = build_geography()                     # GIM's 57 agents (the model's own set)
    base_world = geo_world.adjacency_base_rate()
    base_agents = geo_agents.adjacency_base_rate()
    print("Golden-safe geography diagnostic — does GIM's conflict block ignore distance?\n")
    print(f"geography: {len(geo_agents.matched)}/{len(geo_agents.matched) + len(geo_agents.unmatched)} "
          f"GIM agents matched; {len(geo_world.matched)} reference-world countries")
    print(f"chance adjacency: world {base_world:.1%}  |  GIM-agent subset {base_agents:.1%}\n")

    real = real_conflict_locality(geo_world)
    gim = gim_escalation_locality(geo_agents)
    MIN_REAL = 12   # don't trust the real-world lift below this many located dyads

    def line(tag, d, base):
        if d["n_located"] == 0:
            print(f"{tag}: no geo-located pairs"); return float("nan")
        lift = d["adj_frac"] / base if base else float("nan")
        print(f"{tag}: {d['n_located']} located pairs (of {d['n']}); "
              f"adjacent = {d['adj_frac']:.0%} ({lift:.1f}x chance); median dist = {d['median_km']:.0f} km")
        return lift

    real_lift = line("REAL  (UCDP interstate, 1990-2023, full world)", real, base_world)
    gim_lift = line(f"GIM   ({RUN_YEARS}y run, escalation targets)", gim, base_agents)

    real_trustworthy = real["n_located"] >= MIN_REAL
    real_local = real_trustworthy and real_lift >= 3.0
    gim_local = gim["n_located"] > 0 and gim_lift >= 3.0
    print()
    if not real_trustworthy:
        print(f"VERDICT: only {real['n_located']} interstate dyads geo-located (<{MIN_REAL}) — too few to "
              "trust the real-world lift here; the territorial-conflict literature (most interstate "
              "conflict is between neighbours) is the better anchor. GIM escalation lift "
              f"{gim_lift:.1f}x chance, median {gim['median_km']:.0f} km, suggests weak geographic locality.")
    elif real_local and not gim_local:
        print("VERDICT: real interstate conflict is strongly LOCAL, GIM's escalation targets are NOT —"
              " geography carries large unused signal; wiring adjacency into the conflict block is justified.")
    elif real_local and gim_local:
        print("VERDICT: both are local — GIM's relational structure already proxies geography reasonably;"
              " explicit distance would add modest value.")
    else:
        print("VERDICT: real interstate conflict is not especially local in this sample — geography adds little;"
              " revisit with a larger/again sample before investing.")
    print("\nNote: measurement only — nothing wired into the core. Aggregates/city-states unmatched"
          " (excluded from the geographic pairs, ~6.5% of GDP).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
