"""Geographic substrate for GIM agents, derived from data/world_countries.geojson.

GOLDEN-SAFE: a standalone data/diagnostic asset. Nothing here is imported by the simulation core; it
exists to (a) reconstruct a spatial graph — centroid great-circle distance + shared-border adjacency —
for the country agents, and (b) let scripts measure how much geographic signal the geography-FREE
conflict block currently ignores (`_auto_security_action` picks its escalation target by
argmax(conflict_level + 0.5*(1-trust)), with no adjacency term).

Aggregate agents ("Rest of <Region>") have no single polygon and are left unmatched (≈6.5% of GDP);
they are reported, not silently dropped. Centroids use the polygon centroid, which is approximate for
multi-part states (e.g. the US with Alaska, Russia across the dateline) — adequate for a diagnostic.
"""

from __future__ import annotations

import csv
import json
import math
import os
from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

from shapely import STRtree
from shapely.geometry import shape

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEOJSON = os.path.join(_REPO, "data", "world_countries.geojson")
STATE = os.path.join(_REPO, "data", "agent_states_operational.csv")

# GIM agent `name` -> geojson `name` (only where they differ).
_AGENT_TO_GEO = {
    "United States": "United States of America",
    "Korea, Rep.": "South Korea",
    "Turkiye": "Turkey",
    "Viet Nam": "Vietnam",
    "Egypt, Arab Rep.": "Egypt",
    "Czechia": "Czech Republic",
    "Hong Kong SAR": "Hong Kong",
    "Singapore": "Singapore",
}

# Tolerance (degrees) for shared-border detection on simplified polygons (~28 km); also catches
# countries separated by a narrow strait, which is acceptable for a "near-adjacency" diagnostic.
ADJACENCY_EPS_DEG = 0.25


def great_circle_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


@dataclass
class Geography:
    centroids: Dict[str, Tuple[float, float]]   # agent name -> (lat, lon)
    adjacency: Set[FrozenSet[str]]              # {frozenset({a, b}), ...} land/near neighbours
    matched: List[str]
    unmatched: List[str]

    def is_matched(self, name: str) -> bool:
        return name in self.centroids

    def distance_km(self, a: str, b: str) -> Optional[float]:
        if a not in self.centroids or b not in self.centroids:
            return None
        (la1, lo1), (la2, lo2) = self.centroids[a], self.centroids[b]
        return great_circle_km(la1, lo1, la2, lo2)

    def is_adjacent(self, a: str, b: str) -> bool:
        return frozenset((a, b)) in self.adjacency

    def adjacency_base_rate(self) -> float:
        n = len(self.matched)
        pairs = n * (n - 1) / 2
        return len(self.adjacency) / pairs if pairs else float("nan")


def _agent_names() -> List[str]:
    with open(STATE, newline="") as fh:
        return [r["name"] for r in csv.DictReader(fh)]


def all_geojson_names() -> List[str]:
    """Every country name in the geojson — used to build the full-world reference geography."""
    with open(GEOJSON) as fh:
        return [f["properties"]["name"] for f in json.load(fh)["features"]]


def build_geography(
    agent_names: Optional[List[str]] = None, eps_deg: float = ADJACENCY_EPS_DEG
) -> Geography:
    agent_names = agent_names if agent_names is not None else _agent_names()
    with open(GEOJSON) as fh:
        geo = {f["properties"]["name"]: shape(f["geometry"]) for f in json.load(fh)["features"]}

    centroids: Dict[str, Tuple[float, float]] = {}
    geoms = {}
    matched: List[str] = []
    unmatched: List[str] = []
    for name in agent_names:
        gname = name if name in geo else _AGENT_TO_GEO.get(name)
        if gname is None or gname not in geo:
            unmatched.append(name)
            continue
        g = geo[gname]
        c = g.centroid
        centroids[name] = (c.y, c.x)
        geoms[name] = g
        matched.append(name)

    adjacency: Set[FrozenSet[str]] = set()
    names = list(geoms)
    geom_list = [geoms[n] for n in names]
    tree = STRtree(geom_list)
    for i, a in enumerate(names):
        for j in tree.query(geom_list[i].buffer(eps_deg)):
            if j <= i:
                continue
            if geom_list[i].distance(geom_list[j]) <= eps_deg:
                adjacency.add(frozenset((a, names[j])))
    return Geography(centroids, adjacency, matched, unmatched)


__all__ = ["Geography", "build_geography", "great_circle_km", "ADJACENCY_EPS_DEG"]
