"""National capability index (CINC-style) to ground `military_power` (F3).

GIM's `technology.military_power` is an ungrounded scalar (default ~1.0). The field-standard
measure of national power is the **Composite Index of National Capability (CINC)** (Correlates of
War, National Material Capabilities): the average of a state's *share* of the international system
across six components — military expenditure, military personnel, energy consumption, iron/steel
production, urban population, total population.

GIM tracks three of these (or close proxies): total population, energy consumption, and GDP (an
industrial-output proxy standing in for iron/steel; military spending is also used when nonzero).
This module computes a CINC-style capability **share** (0–1, summing to 1 across the modelled
world) from those components — an observable, standard grounding for `military_power`.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List

# [F3+] SIPRI 2023 milex grounding file (built by scripts/build_milex_grounding.py).
_MILEX_GROUNDING_CSV = Path(__file__).resolve().parents[1] / "data" / "external" / "sipri_milex_2023.csv"


def load_military_spending(world, csv_path: str | Path | None = None) -> int:
    """[F3+] Populate `economy.military_spending` from the SIPRI grounding CSV (id -> US$m).

    Returns the number of agents populated. No-ops (returns 0) if the file is absent, so a
    checkout without the data file degrades gracefully to the 3-component proxy CINC.
    """
    path = Path(csv_path) if csv_path is not None else _MILEX_GROUNDING_CSV
    if not path.exists():
        return 0
    n = 0
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            agent = world.agents.get(row.get("id", ""))
            if agent is None:
                continue
            agent.economy.military_spending = max(0.0, float(row["military_spending_musd"]))
            n += 1
    return n


def _component_vectors(world) -> Dict[str, Dict[str, float]]:
    """Per-agent raw values for each available CINC-style component."""
    pop, energy, gdp, milex = {}, {}, {}, {}
    for aid, a in world.agents.items():
        pop[aid] = max(0.0, float(a.economy.population))
        e = a.resources.get("energy")
        energy[aid] = max(0.0, float(e.consumption)) if e is not None else 0.0
        gdp[aid] = max(0.0, float(a.economy.gdp))
        milex[aid] = max(0.0, float(getattr(a.economy, "military_spending", 0.0)))
    comps = {"population": pop, "energy": energy, "gdp": gdp, "military_spending": milex}
    # Drop components that are all-zero (e.g. military_spending unpopulated in the state).
    return {k: v for k, v in comps.items() if sum(v.values()) > 0.0}


def composite_capability_index(world) -> Dict[str, float]:
    """CINC-style capability share per agent (0–1, sums to 1 over the modelled world)."""
    comps = _component_vectors(world)
    aids = list(world.agents.keys())
    if not comps:
        n = max(1, len(aids))
        return {aid: 1.0 / n for aid in aids}
    # Each component: share of world total; CINC = mean of the component shares.
    shares = {aid: 0.0 for aid in aids}
    for vec in comps.values():
        total = sum(vec.values())
        if total <= 0:
            continue
        for aid in aids:
            shares[aid] += vec[aid] / total
    k = len(comps)
    return {aid: shares[aid] / k for aid in aids}


def ground_military_power(world, scale_to_mean_one: bool = True) -> None:
    """Set each agent's `technology.military_power` to its CINC-style capability.

    By default rescaled so the mean is ~1.0 (preserving the original scalar's scale/units, which
    other code may assume), while the *relative* values become the data-grounded capability shares.
    """
    cinc = composite_capability_index(world)
    n = max(1, len(cinc))
    mean = (sum(cinc.values()) / n) or 1.0
    for aid, a in world.agents.items():
        share = cinc.get(aid, mean)
        a.technology.military_power = (share / mean) if scale_to_mean_one else share


def capability_ranking(world, top: int = 10) -> List[tuple]:
    cinc = composite_capability_index(world)
    names = {aid: a.name for aid, a in world.agents.items()}
    rows = sorted(((names[aid], v) for aid, v in cinc.items()), key=lambda r: -r[1])
    return rows[:top]
