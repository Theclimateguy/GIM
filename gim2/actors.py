"""Per-actor states for the answer screen.

Turns the per-agent trajectories already captured for the cascade (`gim2.cascade`)
into a readable «кто в выигрыше / кто в проигрыше» view: each country's terminal Δ
across domains, its crisis timeline, a composite winner/loser score, and a
**map-ready geo payload** (country → per-domain value) for a Leaflet choropleth
joined to ``data/world_countries.geojson`` by country name.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .cascade import ActorRun, _med

# Model country name -> geojson feature name (`data/world_countries.geojson`).
_GEO_ALIAS: Dict[str, str] = {
    "United States": "United States of America",
    "Korea, Rep.": "South Korea",
    "Turkiye": "Turkey",
    "Viet Nam": "Vietnam",
    "Egypt, Arab Rep.": "Egypt",
    "Czechia": "Czech Republic",
}
# Real countries absent from the 180-feature geojson (kept in the list, off the map).
_NO_GEO = {"Singapore", "Hong Kong SAR"}

# Map layers exposed for the choropleth (good/bad valence handled in the UI).
GEO_DOMAINS = ["gdp_pct", "tension", "debt_pct", "crisis_years"]


def _terminal(rows: List[List[Dict[str, Any]]], year: int, aid: str, key: str) -> float:
    return _med([traj[year]["a"][aid][key] for traj in rows if aid in traj[year]["a"]])


def build_actor_states(run: ActorRun, top_k: int = 5) -> Dict[str, Any]:
    base, scen, world, t = run.base, run.scen, run.world, run.horizon - 1
    if not base or not scen:
        return {"actors": [], "leaders": [], "laggards": [], "geo": {"domains": GEO_DOMAINS, "countries": []}}

    actors: List[Dict[str, Any]] = []
    for aid, agent in world.agents.items():
        def b(key: str) -> float:
            return _terminal(base, t, aid, key)

        def s(key: str) -> float:
            return _terminal(scen, t, aid, key)

        gdp_b, debt_b = b("gdp"), b("debt")
        gdp_pct = round((s("gdp") - gdp_b) / gdp_b * 100.0, 2) if abs(gdp_b) > 1e-9 else 0.0
        debt_pct = round((s("debt") - debt_b) / debt_b * 100.0, 2) if abs(debt_b) > 1e-9 else 0.0
        tension_d = round(s("tension") - b("tension"), 4)
        infl_pp = round((s("inflation") - b("inflation")) * 100.0, 2)
        unemp_pp = round((s("unemployment") - b("unemployment")) * 100.0, 2)
        crisis_s = s("debt_crisis_years") + s("fx_crisis_years") + s("regime_crisis_years")
        crisis_b = b("debt_crisis_years") + b("fx_crisis_years") + b("regime_crisis_years")
        crisis_added = round(crisis_s - crisis_b, 2)

        # Composite (higher = better): GDP up is good; tension/debt/crisis up are bad.
        score = round(gdp_pct - 60.0 * tension_d - 0.5 * debt_pct - 3.0 * crisis_added, 2)
        verdict = "выигрыш" if score > 0.5 else "проигрыш" if score < -0.5 else "нейтрально"

        aggregate = aid.startswith("AG_") or agent.name.startswith("Rest of")
        mappable = (not aggregate) and agent.name not in _NO_GEO

        actors.append({
            "id": aid, "name": agent.name, "region": agent.region,
            "score": score, "verdict": verdict, "aggregate": aggregate, "mappable": mappable,
            "geo_name": _GEO_ALIAS.get(agent.name, agent.name),
            "domains": {
                "gdp_pct": gdp_pct, "tension": tension_d, "debt_pct": debt_pct,
                "inflation_pp": infl_pp, "unemployment_pp": unemp_pp,
                "crisis_years": round(crisis_s, 1), "crisis_added": crisis_added,
            },
        })

    actors.sort(key=lambda a: a["score"], reverse=True)
    leaders = actors[:top_k]
    laggards = list(reversed(actors))[:top_k]
    geo_countries = [
        {"id": a["id"], "name": a["name"], "geo_name": a["geo_name"], "score": a["score"], **a["domains"]}
        for a in actors if a["mappable"]
    ]
    return {
        "actors": actors,
        "leaders": leaders,
        "laggards": laggards,
        "geo": {"domains": GEO_DOMAINS, "countries": geo_countries},
    }


__all__ = ["build_actor_states", "GEO_DOMAINS"]
