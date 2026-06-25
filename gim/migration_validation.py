"""S2 — migration gravity-elasticity validation (social-domain analogue of the D6 check).

GIM's migration mechanism (`gim.core.social.update_migration_flows`) is a *trade-linkage* gravity, not
a physical-distance gravity: it has no bilateral distance field, so the destination "proximity" weight
is the trade intensity. This module exercises the SHIPPED engine on a controlled synthetic world and
recovers its gravity elasticities, to compare against the international-migration gravity literature
(Beine, Bertoli & Fernandez-Huertas Moraga 2016; Ramos 2017).

We build one relatively poor origin and many richer destinations (richer than baseline, so they do not
back-migrate); each destination's post-step population gain then equals the bilateral flow from the
origin, so the flows are read off the REAL engine without re-implementing its formula.

Recovered elasticities (log-log OLS of bilateral flow):
  - mass (origin population)   -> expected exactly 1 (canonical gravity mass term);
  - destination income LEVEL   -> positive, order ~1 (gravity income elasticity ~0.5-1.5);
  - income GAP and linkage     -> exactly 1 (the engine is linear in the income gap and the linkage).

Honest scope: this anchors the income channel's sign/order and the population-mass unit-elasticity, and
documents that GIM substitutes trade linkage for the gravity distance/contiguity term (a positive
linkage elasticity, not a -1 distance elasticity). The functional form is gap-linear, not log-linear,
so the income-level elasticity is operating-point dependent (reported, not hidden).
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

import numpy as np

from .core.core import (
    AgentState,
    ClimateSubState,
    CulturalState,
    EconomyState,
    GlobalState,
    RelationState,
    ResourceSubState,
    RiskState,
    SocietyState,
    TechnologyState,
    WorldState,
)
from .core.social import update_migration_flows


def _agent(agent_id: str, gdp_pc: float, population: float, conflict: float = 0.0) -> AgentState:
    economy = EconomyState(
        gdp=max(gdp_pc * population / 1e12, 1e-6),
        capital=1.0,
        population=population,
        public_debt=0.5,
        fx_reserves=0.2,
    )
    economy.gdp_per_capita = gdp_pc
    return AgentState(
        id=agent_id,
        type="country",
        name=agent_id,
        region="test",
        economy=economy,
        resources={
            "energy": ResourceSubState(own_reserve=10.0, production=1.0, consumption=1.0),
            "food": ResourceSubState(own_reserve=10.0, production=1.0, consumption=1.0),
            "metals": ResourceSubState(own_reserve=10.0, production=1.0, consumption=1.0),
        },
        society=SocietyState(trust_gov=0.6, social_tension=0.2, inequality_gini=40.0),
        climate=ClimateSubState(climate_risk=0.3),
        culture=CulturalState(),
        technology=TechnologyState(),
        risk=RiskState(
            water_stress=0.3, regime_stability=0.8, debt_crisis_prone=0.3, conflict_proneness=conflict
        ),
    )


def build_migration_world(
    dest_incomes: Sequence[float],
    dest_linkages: Sequence[float],
    *,
    baseline: float = 20_000.0,
    origin_income_frac: float = 0.4,
    origin_pop: float = 50_000_000.0,
    dest_pop: float = 200_000_000.0,
    origin_conflict: float = 0.0,
) -> Tuple[WorldState, List[str]]:
    """One poor origin 'O' + a grid of richer destinations 'D{i}' (no back-migration).

    `dest_incomes` and `dest_linkages` are paired, one entry per destination.
    """
    if len(dest_incomes) != len(dest_linkages):
        raise ValueError("dest_incomes and dest_linkages must be the same length")

    origin = _agent("O", baseline * origin_income_frac, origin_pop, conflict=origin_conflict)
    agents = {origin.id: origin}
    relations: Dict[str, Dict[str, RelationState]] = {origin.id: {}}
    dest_ids: List[str] = []
    for i, (income, linkage) in enumerate(zip(dest_incomes, dest_linkages)):
        did = f"D{i}"
        agents[did] = _agent(did, income, dest_pop, conflict=0.0)
        relations[did] = {}
        relations[origin.id][did] = RelationState(
            trade_intensity=float(linkage), trust=0.5, conflict_level=0.0, trade_barrier=0.0
        )
        dest_ids.append(did)

    world = WorldState(
        time=0,
        agents=agents,
        global_state=GlobalState(co2=3270.0, temperature_global=1.2, biodiversity_index=0.72),
        relations=relations,
    )
    world.global_state.baseline_gdp_pc = baseline
    return world, dest_ids


def measure_bilateral_flows(world: WorldState, dest_ids: Sequence[str]) -> Dict[str, float]:
    """Run the SHIPPED migration engine once; bilateral flow = each destination's population gain."""
    before = {d: world.agents[d].economy.population for d in dest_ids}
    update_migration_flows(world)
    return {d: world.agents[d].economy.population - before[d] for d in dest_ids}


def _ols(y: np.ndarray, *cols: np.ndarray) -> np.ndarray:
    x = np.column_stack([np.ones_like(y), *cols])
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    return beta


def gravity_elasticities(
    baseline: float = 20_000.0, origin_income_frac: float = 0.4
) -> Dict[str, float]:
    """Recover GIM migration's gravity elasticities from the shipped engine."""
    incomes = [1.2, 1.6, 2.0, 3.0, 4.0, 6.0, 8.0]
    linkages = [0.1, 0.2, 0.4, 0.6, 0.8]
    grid_income: List[float] = []
    grid_linkage: List[float] = []
    for inc in incomes:
        for lk in linkages:
            grid_income.append(inc * baseline)
            grid_linkage.append(lk)

    world, dest_ids = build_migration_world(
        grid_income, grid_linkage, baseline=baseline, origin_income_frac=origin_income_frac
    )
    flows = measure_bilateral_flows(world, dest_ids)
    f = np.array([flows[d] for d in dest_ids])
    inc = np.array(grid_income)
    lk = np.array(grid_linkage)
    gap = (inc - baseline * origin_income_frac) / baseline

    logf = np.log(f)
    income_beta = _ols(logf, np.log(inc), np.log(lk))      # income LEVEL + linkage
    gap_beta = _ols(logf, np.log(gap), np.log(lk))         # income GAP + linkage

    # Mass (origin-population) elasticity: a pure scale check — doubling origin pop doubles every flow.
    w1, ids1 = build_migration_world([2.0 * baseline], [0.5], baseline=baseline,
                                     origin_income_frac=origin_income_frac, origin_pop=50_000_000.0)
    w2, ids2 = build_migration_world([2.0 * baseline], [0.5], baseline=baseline,
                                     origin_income_frac=origin_income_frac, origin_pop=100_000_000.0)
    flow1 = measure_bilateral_flows(w1, ids1)[ids1[0]]
    flow2 = measure_bilateral_flows(w2, ids2)[ids2[0]]
    mass_elasticity = np.log(flow2 / flow1) / np.log(2.0)

    return {
        "income_level_elasticity": float(income_beta[1]),
        "linkage_elasticity": float(income_beta[2]),
        "gap_elasticity": float(gap_beta[1]),
        "mass_elasticity": float(mass_elasticity),
        "n_destinations": float(len(dest_ids)),
    }


__all__ = [
    "build_migration_world",
    "measure_bilateral_flows",
    "gravity_elasticities",
]
