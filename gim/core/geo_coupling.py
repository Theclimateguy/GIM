"""Shared geographic-coupling helpers for the simulation core.

Several channels couple to geography (conflict contagion, trade gravity, social-tension spillover, …).
They all need the same two primitives — a cached Geography object and an agent-id adjacency map — plus
the one-time gravity trade initialiser. Keeping them here avoids duplication and import cycles.

GOLDEN-SAFE: the shapely-backed geography module is imported LAZILY, only when a geographic flag is on,
so the core stays standard-library-only (and golden-identical) when every geo flag is off.
"""

from __future__ import annotations

import math
import statistics
from typing import Dict

from .core import WorldState


def geography_for(world: WorldState):
    """Cached Geography object for the world's agents; None if shapely/geojson unavailable."""
    gs = world.global_state
    if hasattr(gs, "_geo_obj"):
        return gs._geo_obj
    obj = None
    try:
        from ..geography import build_geography
        obj = build_geography([a.name for a in world.agents.values()])
    except Exception:
        obj = None
    setattr(gs, "_geo_obj", obj)
    return obj


def adjacency(world: WorldState) -> Dict[str, set]:
    """{agent_id -> set of geographically adjacent agent_ids}, built once and cached on the world."""
    cached = getattr(world.global_state, "_geo_adjacency_ids", None)
    if cached is not None:
        return cached
    adj: Dict[str, set] = {aid: set() for aid in world.agents}
    geo = geography_for(world)
    if geo is not None:
        name_to_id = {a.name: aid for aid, a in world.agents.items()}
        for pair in geo.adjacency:
            a, b = tuple(pair)
            ia, ib = name_to_id.get(a), name_to_id.get(b)
            if ia is not None and ib is not None:
                adj[ia].add(ib)
                adj[ib].add(ia)
    setattr(world.global_state, "_geo_adjacency_ids", adj)
    return adj


def apply_trade_gravity_once(world: WorldState, cal) -> None:
    """[GRAVITY] One-time: replace flat trade_intensity with a gravity prediction
    (GDP_i·GDP_j / distance^delta), sigmoid-mapped to [0,1] with mean ~0.5 so only the network STRUCTURE
    changes, not the average trade level. `delta` is the literature distance elasticity (Head & Mayer
    2014 ~0.9) — an anchored structural prior, not a tuned knob. No-op when geography is unavailable.
    """
    gs = world.global_state
    if getattr(gs, "_trade_gravity_applied", False):
        return
    setattr(gs, "_trade_gravity_applied", True)
    geo = geography_for(world)
    if geo is None:
        return
    delta = float(getattr(cal, "TRADE_GRAVITY_DIST_ELASTICITY", 0.9))
    name = {aid: a.name for aid, a in world.agents.items()}
    gdp = {aid: max(float(a.economy.gdp), 1e-9) for aid, a in world.agents.items()}
    dists = [d for d in (geo.distance_km(name[i], name[j])
                         for i in world.agents for j in world.agents if i < j) if d]
    med = statistics.median(dists) if dists else 5000.0
    raw: Dict[tuple, float] = {}
    for i, rels in world.relations.items():
        for j in rels:
            matched = geo.is_matched(name[i]) and geo.is_matched(name[j])
            d = geo.distance_km(name[i], name[j]) if matched else None
            d = d if (d and d > 1.0) else med
            raw[(i, j)] = math.log(gdp[i] * gdp[j]) - delta * math.log(d)
    if not raw:
        return
    vals = list(raw.values())
    mu = statistics.fmean(vals)
    sd = statistics.pstdev(vals) or 1.0
    for (i, j), lg in raw.items():
        world.relations[i][j].trade_intensity = 1.0 / (1.0 + math.exp(-(lg - mu) / sd))


__all__ = ["geography_for", "adjacency", "apply_trade_gravity_once"]
